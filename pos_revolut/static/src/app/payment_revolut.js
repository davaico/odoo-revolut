import { refundAllowances } from "./refund_allowances";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";
import { Component, useState } from "@odoo/owl";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { roundCurrency } from "@point_of_sale/app/models/utils/currency";
import { floatIsZero, roundPrecision } from "@web/core/utils/numbers";
import {
    RevolutPaymentState, isRevolut, isRevolutRefund, orderActions,
    paymentActions, paymentOutcome, paymentResponseSuccessful, restorePaymentLine,
} from "./revolut_payment_state";

async function restoreRefundOriginals(pos, order) {
    // Paid originals may leave the POS cache on reload. Restore the relation
    // before Odoo serializes the return for settlement.
    const missingOriginals = order.lines
        .filter((line) => !line.refunded_orderline_id && line.raw.refunded_orderline_id)
        .map((line) => line.raw.refunded_orderline_id);
    if (missingOriginals.length) {
        await pos.data.read("pos.order.line", missingOriginals);
    }
}

export function hasRevolutExposure(order) {
    return orderActions(order).hasExposure;
}

function isRevolutNegativeOriginal(line) {
    return line?.qty < 0 && !line.refunded_orderline_id &&
        line.order_id?.payment_ids?.some((payment) => payment.revolut_operation_id ||
            payment.payment_method_id?.use_payment_terminal === "revolut");
}

function financialSnapshot(order) {
    return {
        amount_total: roundCurrency(order.get_total_with_tax(), order.currency),
        pricelist_id: order.pricelist_id?.id || false,
        fiscal_position_id: order.fiscal_position_id?.id || false,
        restaurant: order.config?.module_pos_restaurant ? {
            preset_id: order.preset_id?.id || false,
            table_id: order.table_id?.id || false,
        } : false,
        lines: order.lines.map((line) => ({
            uuid: line.uuid,
            product_id: line.product_id.id,
            qty: line.qty,
            price_unit: line.price_unit,
            discount: line.discount || 0,
            tax_ids: (line.tax_ids || []).map((tax) => tax.id),
            ...(line.refunded_orderline_id ? { refunded_orderline_id: line.refunded_orderline_id.id } : {}),
        })),
    };
}

class RefundAllocationDialog extends Component {
    static template = "pos_revolut.RefundAllocationDialog";
    static components = { Dialog };
    static props = ["sources", "paymentMethodId", "maximumMinor", "decimalPlaces", "currencySymbol", "onConfirm", "close"];

    setup() {
        const eligible = this.props.sources.filter((source) =>
            source.payment_method_id === this.props.paymentMethodId && source.remaining_minor > 0
        );
        const selectedId = eligible.length === 1 ? eligible[0].operation_id : false;
        this.state = useState({
            operationId: selectedId,
            amount: selectedId ? this.defaultAmount(eligible[0]) : "",
            tipAmount: selectedId ? this.defaultTip(eligible[0]) : "0",
            error: "",
        });
    }

    get title() {
        return _t("Allocate Revolut refund");
    }

    get selectedSource() {
        return this.props.sources.find((source) => source.operation_id === this.state.operationId);
    }

    defaultAmount(source) {
        const available = source.allowances.baseMinor;
        return (Math.min(available, this.props.maximumMinor) /
            10 ** this.props.decimalPlaces).toFixed(this.props.decimalPlaces);
    }

    defaultTip(source) {
        return ((source.terminal_tip_evidence ? source.allowances.tipMinor : 0) /
            10 ** this.props.decimalPlaces).toFixed(this.props.decimalPlaces);
    }

    selectSource(event) {
        this.state.operationId = Number(event.target.value);
        this.state.amount = this.defaultAmount(this.selectedSource);
        this.state.tipAmount = this.defaultTip(this.selectedSource);
        this.state.error = "";
    }

    updateAmount(event) {
        this.state.amount = event.target.value;
        this.state.error = "";
    }

    updateTip(event) {
        this.state.tipAmount = event.target.value;
        this.state.error = "";
    }

    confirm() {
        const source = this.selectedSource;
        const factor = 10 ** this.props.decimalPlaces;
        const numeric = Number(this.state.amount);
        const baseMinor = Math.round(numeric * factor);
        const tipNumeric = source?.terminal_tip_evidence ? Number(this.state.tipAmount) : 0;
        const tipMinor = Math.round(tipNumeric * factor);
        const minor = baseMinor + tipMinor;
        if (!source || source.payment_method_id !== this.props.paymentMethodId ||
            !Number.isFinite(numeric) || minor <= 0 ||
            baseMinor < 0 || tipMinor < 0 || !Number.isFinite(tipNumeric) ||
            Math.abs(numeric * factor - baseMinor) > 0.000001 ||
            Math.abs(tipNumeric * factor - tipMinor) > 0.000001 ||
            (baseMinor > source.allowances.baseMinor ||
                tipMinor > source.allowances.tipMinor) ||
            minor > source.remaining_minor || minor > this.props.maximumMinor) {
            this.state.error = _t("Choose an original Revolut payment and an amount within its remaining balance and this return.");
            return;
        }
        this.props.onConfirm({ operationId: source.operation_id, amount: minor / factor,
            ...(source.terminal_tip_evidence ? { baseAmountMinor: baseMinor, tipAmountMinor: tipMinor } : {}) });
        this.props.close();
    }
}

function chooseRefundAllocation(dialog, sources, paymentMethodId, line, currency) {
    const decimalPlaces = currency.decimal_places ?? 2;
    const factor = 10 ** decimalPlaces;
    const totals = [...new Set(sources.map((source) => source.return_total_minor))];
    // The server allocates the original collected base and tip. Native cash
    // rounding of a newly created return can differ from that checked total.
    const otherPaid = line.pos_order_id.payment_ids.filter((payment) => payment.uuid !== line.uuid)
        .reduce((total, payment) => total + Math.max(0, Math.round(-payment.amount * factor)), 0);
    const maximumMinor = totals.length === 1 && Number.isSafeInteger(totals[0]) && totals[0] > 0
        ? Math.max(0, totals[0] - otherPaid)
        : Math.round(Math.abs(line.amount) * factor);
    const availableSources = sources.map((source) => ({
        ...source,
        allowances: refundAllowances(source, line.pos_order_id.payment_ids, line.uuid, factor),
    }));
    return new Promise((resolve) => {
        dialog.add(RefundAllocationDialog, {
            sources: availableSources, paymentMethodId, maximumMinor, decimalPlaces,
            currencySymbol: currency.symbol,
            onConfirm: resolve,
        }, { onClose: () => resolve(false) });
    });
}

export class PaymentRevolut extends PaymentInterface {
    get fast_payments() {
        // Refunds retain an explicit Send action before allocation, as they
        // may need a different original tender from the default full balance.
        return !this.pos.get_order()._isRefundOrder();
    }

    setup() {
        super.setup(...arguments);
        this.paymentState = new RevolutPaymentState({
            methodId: this.payment_method_id.id,
            sessionId: this.pos.session.id,
            currencyId: this.pos.currency.id,
            adapter: {
                call: (method, args) => this.pos.data.call("pos.payment.method", method, args),
                financialSnapshot,
                preparePayment: (order, line) => this._preparePayment(order, line),
                recoverPayment: async (order, line) => {
                    const result = await this.pos.data.call("pos.order", "revolut_recover_unstarted_payment", [
                        order.id, order.uuid, line.uuid, this.payment_method_id.id,
                        line.amount, this.pos.currency.id,
                    ]);
                    if (Number.isSafeInteger(result?.recovery_revision)) {
                        order.uiState.revolutRecoveryRevision = result.recovery_revision;
                    }
                    return result;
                },
                removeRecoveredPayment: async (order, line) => {
                    // Editable local amounts, including zero, may differ from
                    // the saved tender. Retire its canonical server identity.
                    const state = await this.pos.data.call("pos.order", "revolut_checkout_state", [order.id, order.uuid]);
                    const saved = state.data["pos.payment"]?.find((payment) =>
                        payment.id === line.id && payment.uuid === line.uuid);
                    const retired = state.recovered_tenders?.[line.uuid];
                    const amount = saved?.amount ?? (retired?.state === "retired" &&
                        retired.payment_id === line.id && retired.method_id === this.payment_method_id.id
                        ? retired.minor / 10 ** this.pos.currency.decimal_places : undefined);
                    if (!Number.isFinite(amount)) {
                        throw new Error(_t("The original saved tender could not be identified."));
                    }
                    return this.pos.data.call("pos.order", "revolut_remove_unstarted_payment", [
                        order.id, order.uuid, line.uuid, this.payment_method_id.id,
                        amount, this.pos.currency.id,
                    ]);
                },
                prepareRefund: (order, line) => this._prepareRefund(order, line),
                restoreRefundOriginals: (order) => restoreRefundOriginals(this.pos, order),
                chooseAllocation: (sources, line) => chooseRefundAllocation(
                    this.env.services.dialog, sources, this.payment_method_id.id,
                    line, this.pos.currency
                ),
                setRefundAmount: (line, amount) => {
                    line.uiState.revolutSelectingAllocation = true;
                    try {
                        line.set_amount(-amount);
                    } finally {
                        line.uiState.revolutSelectingAllocation = false;
                    }
                },
                discardRefund: (line) => line.pos_order_id.remove_paymentline(line),
                setVerified: (line, result, restoration) => this._setVerified(line, result, restoration),
                showError: (line, state) => this._showResultError(line, state),
                showPreparationError: (line, reason, message) => this._showPreparationError(reason, message),
            },
        });
    }

    send_payment_request(uuid) {
        const order = this.pos.get_order();
        return this.paymentState.request(order, order.get_paymentline_by_uuid(uuid));
    }

    send_payment_cancel(order, uuid) {
        return this.paymentState.cancel(order, order.get_paymentline_by_uuid(uuid));
    }

    async _refreshAuthorizedOrder(order, isCurrent = () => true) {
        if (!Number.isInteger(order.id)) {
            throw new Error(_t("Save this order online before preparing payment."));
        }
        const state = await this.pos.data.call("pos.order", "revolut_checkout_state", [order.id, order.uuid]);
        if (!isCurrent()) {
            return;
        }
        const missing = await this.pos.data.missingRecursive(state.data);
        if (!isCurrent()) {
            return;
        }
        // Native missingRecursive can return an empty or partial accumulator
        // when connectivity changes after the checkout RPC has succeeded.
        if (this.pos.data.network.offline || !missing["pos.order"]?.some(
            (record) => record.id === order.id && record.uuid === order.uuid
        )) {
            throw new Error(_t("Could not load canonical checkout data. Reconnect and check status."));
        }
        this.pos.models.loadData(missing, [], false);
        for (const payment of order.payment_ids.filter(isRevolut)) {
            const verified = payment.uiState.revolutSnapshot;
            if (verified?.state === "verified" && payment.transaction_id === verified.payment_id &&
                payment.payment_ref_no === verified.order_id) {
                // Cash-plan admission reloads saved fields before the local
                // terminal receipt has been synced. Restore its verified
                // reference before the final native checkout serializes it.
                this._setReceipt(payment, verified);
            }
        }
        order.uiState.revolutAuthority = state.authority;
        order.uiState.revolutRecoveryRevision = state.recovery_revision || 0;
        return state;
    }

    async _preparePayment(order, line) {
        if (order.uiState.revolutPreparingPayment) {
            throw new Error(_t("Wait for this checkout's current preparation before preparing another tender."));
        }
        order.uiState.revolutPreparingPayment = true;
        try {
            // Capture Cash corrections before canonical refresh replaces the
            // saved payment records. The server admits this exact plan.
            const plan = order.payment_ids.filter((payment) => payment.amount !== 0).map((payment) => ({
                uuid: payment.uuid,
                payment_method_id: payment.payment_method_id.id,
                amount: payment.uiState.revolutSnapshot?.base_amount_minor !== undefined
                    ? payment.uiState.revolutSnapshot.base_amount_minor / 10 ** this.pos.currency.decimal_places
                    : payment.amount,
            }));
            // Capture this request's tender authority before native save can be
            // delayed. Refreshing another tender's retirement must not admit an
            // old request for a tender recovered while that save was in flight.
            const recoveryRevision = line.uiState.revolutRecoveryRevision || 0;
            if (order.preset_id?.needsSlot && !order.preset_time) {
                throw new Error(_t("Please select an available pickup time slot before starting Revolut payment. If there are no slots for this day, choose another date in pickup scheduling."));
            }
            if (!order.revolut_has_authority_exposure) {
                await this.pos.syncAllOrders({ orders: [order], force: true, throw: true });
            }
            const current = this.pos.models["pos.order"].getBy("uuid", order.uuid);
            if (!current || !Number.isInteger(current.id)) {
                throw new Error(_t("The draft was not saved. Reconnect and save it before payment."));
            }
            const checkout = await this._refreshAuthorizedOrder(current);
            const disposition = checkout.recovered_tenders?.[line.uuid];
            if (disposition && (disposition.state === "retired" || disposition.revision > recoveryRevision)) {
                const error = new Error(_t("Recovery changed this tender while payment was being prepared. Use Check status before resuming the original line."));
                error.revolutRecoveryRequired = true;
                throw error;
            }
            const result = await this.pos.data.call("pos.order", "revolut_prepare_payment", [
                current.id, current.uuid, current.uiState.revolutAuthority?.cart_version || 0, plan,
                current.uiState.revolutRecoveryRevision || 0,
            ]);
            await this._refreshAuthorizedOrder(current);
            if (result.status === "approval_required") {
                throw new Error(_t("A POS manager must open this saved order in their own Odoo session and approve its exact Revolut cart version. Then use Resume."));
            }
            if (result.status === "review_required" || result.status === "stale") {
                throw new Error(_t("The server updated this cart's prices, taxes or version. Review the displayed cart and payment allocations, then use Resume."));
            }
            return result;
        } finally {
            order.uiState.revolutPreparingPayment = false;
        }
    }

    async _prepareRefund(order, line) {
        const amount = line.amount;
        const saved = await this.pos.syncAllOrders({ orders: [order], force: true, throw: true });
        const current = this.pos.models["pos.order"].getBy("uuid", order.uuid);
        const payment = current?.get_paymentline_by_uuid(line.uuid);
        if (!saved?.some((returned) => returned.uuid === order.uuid) ||
            !current || !Number.isInteger(current.id) || !payment ||
            !Number.isInteger(payment.id) || payment.amount !== amount) {
            throw new Error(_t("The return was not saved. Reconnect and save it before refunding."));
        }
    }

    async _setVerified(line, result, { isCurrent }) {
        if (result.authorization_id || (isRevolutRefund(line) && Number.isInteger(line.pos_order_id.id))) {
            await this._refreshAuthorizedOrder(line.pos_order_id, isCurrent);
        }
        if (!isCurrent()) {
            return;
        }
        this._setVerifiedReferences(line, result);
    }

    _setVerifiedReferences(line, result) {
        line.transaction_id = result.payment_id;
        line.payment_ref_no = result.order_id;
        this._setReceipt(line, result);
    }

    _setReceipt(line, result) {
        const receipt = isRevolutRefund(line)
            ? _t("Revolut refund: %s; original order: %s", result.order_id, result.original_order_id)
            : _t("Revolut payment: %s", result.payment_id);
        // A native server refresh can replace the ticket while retaining local
        // UI state. Restore the actual reference without appending it twice.
        if (!line.ticket?.includes(receipt)) {
            line.set_receipt_info(receipt);
        }
    }

    _showPreparationError(reason, message) {
        const messages = {
            originals: {
                title: _t("Revolut refund"),
                body: _t("Could not load the original sale. No refund was sent. Check the return and try again."),
            },
            sources: {
                title: _t("Revolut refund"),
                body: _t("Could not load the original payment balances. No refund was sent. Check the return and try again."),
            },
            balance: {
                title: _t("No Revolut refund balance"),
                body: _t("No original Revolut payment has a remaining balance for this return. Review prior refunds."),
            },
        };
        const feedback = messages[reason];
        this.env.services.dialog.add(AlertDialog, {
            ...feedback,
            body: typeof message === "string" ? `${message}\n\n${feedback.body}` : feedback.body,
        });
    }

    _showResultError(line, state) {
        if (state === "register_access_denied") {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Revolut register access required"),
                body: _t("Your backend user cannot access Revolut on this register. Ask an administrator to check your register grant. Existing payments and refunds remain unchanged; recover their status after access is restored."),
            });
            return;
        }
        if (state === "checkout_restore_failed") {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Revolut checkout recovery"),
                body: _t("Revolut verified this payment or refund, but Odoo could not restore the checkout data. Reconnect, then choose Check status to finish this same sale or return. No new charge or refund will be sent."),
            });
            return;
        }
        if (state === "recovery_required") {
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Revolut tender recovery changed"),
                body: _t("Recovery changed this tender while payment was being prepared. No new payment request was sent. Use Check status to recover the original line before resuming or removing it."),
            });
            return;
        }
        if (["snapshot_invalid", "authority_required"].includes(state)) {
            const message = line.uiState.revolutRejectionMessage;
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Revolut cart needs correction"),
                body: [
                    ...(typeof message === "string" ? [message] : []),
                    isRevolutRefund(line)
                        ? _t("No refund request was sent from this line. Correct the return, then use Resume, or remove this line. Check status only checks for an existing refund.")
                        : _t("No payment request was sent from this line. Correct the cart, then use Resume, or remove this line. Check status only checks for an existing payment."),
                ].join("\n\n"),
            });
            return;
        }
        if (isRevolutRefund(line)) {
            const messages = {
                discovery_interrupted: _t("Could not check for an existing Revolut refund. No refund request was sent from this line. Retry after the connection returns, or remove this line and choose another eligible original payment method."),
                discovery_timed_out: _t("The check for an existing Revolut refund timed out. No refund request was sent from this line. Retry after the connection returns, or remove this line and choose another eligible original payment method."),
                no_refund_attempt: _t("Odoo confirmed that no refund request was sent from this line. You can use Resume to retry this same line, or remove it."),
                failed: _t("The Revolut refund failed. A POS manager can remove this failed line and add a new refund line for the same remaining amount. Keep completed allocations unchanged."),
                interrupted: _t("Communication with Revolut was interrupted. The refund may have succeeded. Choose Check status to reconcile the existing refund."),
                timed_out: _t("The 60-second Revolut waiting limit expired. The refund remains unresolved. Choose Check status to reconcile the existing refund."),
                unresolved: _t("The Revolut refund is unresolved and cannot be cancelled. Choose Check status to reconcile the existing refund; do not issue another refund or substitute another payment method."),
            };
            this.env.services.dialog.add(AlertDialog, {
                title: _t("Revolut refund"),
                body: messages[state] || messages.unresolved,
            });
            return;
        }
        const messages = {
            discovery_interrupted: _t("Could not check for an existing Revolut payment. No payment request was sent from this line. Retry after the connection returns, or remove this line and choose another payment method."),
            discovery_timed_out: _t("The check for an existing Revolut payment timed out. No payment request was sent from this line. Retry after the connection returns, or remove this line and choose another payment method."),
            retired_recovered: _t("Odoo already removed this unstarted payment line. Remove its local copy; this retired line cannot be resumed."),
            terminal_busy: _t("Another Revolut payment is using this order or terminal. No payment request was sent from this line. Use Resume after the terminal is released, or remove this line. Check status only checks for an existing payment."),
            terminal_unavailable: _t("The Revolut terminal is unavailable. No charge was sent. Check the terminal before retrying."),
            terminal_check_failed: _t("The Revolut terminal connection check failed. No charge was sent. Check the connection before retrying."),
            declined: _t("The Revolut payment was declined. You can retry."),
            failed: _t("The Revolut payment failed. You can retry."),
            cancelled: _t("The Revolut payment was cancelled. You can retry."),
            processing: _t("The Revolut payment is processing and cannot be cancelled. Wait for its verified result."),
            interrupted: _t("Communication with Revolut was interrupted. The payment may have succeeded. Choose Check status to check the existing payment without sending a new charge."),
            timed_out: _t("The 60-second Revolut waiting limit expired. The payment is unresolved. Choose Check status to check the existing payment without sending a new charge."),
            unresolved: _t("The Revolut result is unresolved. Do not charge again or use this terminal until the payment is reconciled. Use Check status to reconcile the existing payment."),
        };
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Revolut Terminal"),
            body: messages[state] || messages.unresolved,
        });
    }
}

patch(PosPayment.prototype, {
    setup() {
        super.setup(...arguments);
        this.uiState = this.uiState || {};
    },

    setupState() {
        super.setupState(...arguments);
        restorePaymentLine(this);
    },

    handle_payment_response(isPaymentSuccessful) {
        return super.handle_payment_response(paymentResponseSuccessful(this, isPaymentSuccessful));
    },

    set_amount() {
        if (this.pos_order_id?.uiState.revolutPreparingPayment || !paymentActions(this).canEditAmount) {
            return;
        }
        return super.set_amount(...arguments);
    },

    export_for_printing() {
        const data = { ...super.export_for_printing(...arguments), is_revolut: isRevolut(this) };
        // Server-reconciled refunds have native transaction references even
        // when no browser collected a terminal ticket. Export a display-only
        // reference so historical reprints never need payment/refund discovery.
        if (data.is_revolut && !data.ticket && this.transaction_id) {
            data.ticket = isRevolutRefund(this)
                ? _t("Revolut refund: %s", this.transaction_id)
                : _t("Revolut payment: %s", this.transaction_id);
        }
        return data;
    },

    delete() {
        if (this.pos_order_id?.uiState.revolutPreparingPayment || !paymentActions(this).canDelete) {
            return false;
        }
        return super.delete(...arguments);
    },
});

patch(PosStore.prototype, {
    async postSyncAllOrders(orders) {
        const result = await super.postSyncAllOrders(...arguments);
        for (const order of orders) {
            for (const line of order.payment_ids.filter(isRevolut)) {
                line.payment_method_id.payment_terminal.paymentState.afterSync(order, line);
            }
        }
        return result;
    },

    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        // Native startup reloads shared draft statuses after local state was
        // restored. Recover the checked action only after that final merge.
        for (const line of this.models['pos.payment'].filter(isRevolut)) {
            await line.payment_method_id.payment_terminal.paymentState.restore(line.pos_order_id, line);
        }
        return result;
    },

    async set_tip() {
        if (hasRevolutExposure(this.get_order())) {
            this.dialog.add(AlertDialog, { title: _t("Revolut terminal tip"),
                body: _t("The terminal records the customer's tip during payment. This exposed order cannot accept an Odoo tip edit.") });
            return false;
        }
        return super.set_tip(...arguments);
    },

    async addLineToOrder(values, order) {
        if (hasRevolutExposure(order)) {
            this.dialog.add(AlertDialog, { title: _t("Revolut cart frozen"),
                body: _t("Recover or reconcile the original payment before changing this cart.") });
            return false;
        }
        return super.addLineToOrder(...arguments);
    },
});

patch(TicketScreen.prototype, {
    _onUpdateSelectedOrderline({ buffer }) {
        const order = this.getSelectedOrder();
        const line = order?.lines.find((item) => item.id === this.getSelectedOrderlineId());
        if (!isRevolutNegativeOriginal(line)) {
            return super._onUpdateSelectedOrderline(...arguments);
        }
        const detail = this.getToRefundDetail(line);
        if (detail.destination_order) {
            return this.numberBuffer.reset();
        }
        const available = Math.abs(line.qty) - Math.abs(line.refunded_qty);
        const quantity = buffer == null || buffer === "" ? 0 : Math.abs(parseFloat(buffer));
        if (!Number.isFinite(quantity) || quantity > available) {
            this.numberBuffer.reset();
            this.dialog.add(AlertDialog, {
                title: _t("Maximum Exceeded"),
                body: _t("The requested quantity is higher than the remaining original quantity."),
            });
            return;
        }
        detail.qty = quantity;
    },

    async addAdditionalRefundInfo(original, order) {
        const result = await super.addAdditionalRefundInfo(...arguments);
        if (this.pos.config.use_presets && order.lines.length &&
            order.lines.every((line) => line.refunded_orderline_id?.order_id === original)) {
            // A new sale's default preset must not replace the policy of the
            // original transaction when native Restaurant creates its return.
            order.update({ pricelist_id: original.pricelist_id,
                fiscal_position_id: original.fiscal_position_id });
        }
        // Native creation uses -selected quantity for every line. Preserve
        // its product, prices, taxes and lots while reversing a negative
        // original with the opposite sign before it reaches PaymentScreen.
        for (const line of order.lines) {
            if (isRevolutNegativeOriginal(line.refunded_orderline_id)) {
                line.qty = Math.abs(line.qty);
            }
        }
        if (order.lines.length && order.lines.every((line) => {
            const source = line.refunded_orderline_id;
            return source && source.get_price_with_tax() <= 0 &&
                source.order_id.payment_ids.some((payment) => payment.revolut_operation_id ||
                    payment.payment_method_id?.use_payment_terminal === "revolut");
        })) {
            // A remaining adjustment reverses its native quantity without
            // collecting money. Load the server's conserved zero target before
            // the native PaymentScreen decides whether it needs a tender.
            await this.pos.syncAllOrders({ orders: [order], force: true, throw: true });
        }
        return result;
    },
});

patch(PosOrderline.prototype, {
    prepareBaseLineForTaxesComputationExtraValues() {
        const values = super.prepareBaseLineForTaxesComputationExtraValues(...arguments);
        const evidence = this.extra_tax_data;
        if (hasRevolutExposure(this.order_id) && this.qty === 1 &&
            evidence?.revolut_tip_product_id === this.product_id.id &&
            evidence.currency_id === values.currency_id.id &&
            evidence.price_unit === values.price_unit && evidence.quantity === values.quantity &&
            evidence.discount === values.discount) {
            // Native 18 does not import persisted manual tax bases. Use the
            // server's frozen product and components, including after a config
            // change, for both line and receipt totals.
            values.manual_total_excluded_currency = evidence.manual_total_excluded_currency;
            values.manual_tax_amounts = evidence.manual_tax_amounts;
        }
        return values;
    },

    set_quantity(quantity) {
        if (hasRevolutExposure(this.order_id)) {
            return false;
        }
        const original = this.refunded_orderline_id;
        if (!isRevolutNegativeOriginal(original)) {
            return super.set_quantity(...arguments);
        }
        const value = typeof quantity === "number" ? quantity : parseFloat(quantity || 0);
        const others = original.refund_orderline_ids.filter((line) =>
            line !== this && line.order_id?.state !== "cancel");
        const available = Math.abs(original.qty) - others.reduce((sum, line) => sum + Math.abs(line.qty), 0);
        const unit = this.product_id.uom_id;
        const decimals = this.models["decimal.precision"].find(
            (precision) => precision.name === "Product Unit of Measure").digits;
        const rounded = unit
            ? roundPrecision(value, unit.rounding
                ? Math.max(unit.rounding, Math.pow(10, -decimals)) : 1)
            : value;
        if (!Number.isFinite(value) || value < 0 || value > available || rounded > available) {
            return {
                title: _t("Invalid return quantity"),
                body: _t("Reverse this adjustment with a positive quantity within its remaining original quantity."),
            };
        }
        this.uiState.oldQty = this.qty;
        this.qty = rounded;
        const detail = original.order_id.uiState.lineToRefund[original.uuid];
        if (detail) {
            detail.qty = rounded;
        }
        for (const child of this.combo_line_ids) {
            child.set_quantity((child.qty / this.uiState.oldQty || 1) * rounded, true);
        }
        return true;
    },
    set_unit_price() {
        return hasRevolutExposure(this.order_id) ? false : super.set_unit_price(...arguments);
    },
    set_discount() {
        return hasRevolutExposure(this.order_id) ? false : super.set_discount(...arguments);
    },
    delete() {
        return hasRevolutExposure(this.order_id) ? false : super.delete(...arguments);
    },
});

patch(PosOrder.prototype, {
    _isRefundOrder() {
        // A cold draft load retains the original ID before its related
        // record is fetched. It must keep the native refund workflow.
        return super._isRefundOrder(...arguments) || this.lines.some((line) =>
            line.refunded_orderline_id || line.raw.refunded_orderline_id);
    },

    setupState() {
        super.setupState(...arguments);
        // Preparation belongs to the current browser request, not a cached
        // draft restored after that request has been interrupted.
        this.uiState.revolutPreparingPayment = false;
    },

    get taxTotals() {
        const totals = super.taxTotals;
        if (!this.revolut_has_authority_exposure) {
            return totals;
        }
        // Odoo 18 checkout, status, receipt and is_paid all consume this
        // structure. Keep its native tax breakdown, with the server's target
        // defining the payable balance and the difference shown as rounding.
        const sign = this.revolut_payable_target < 0 ? -1 : 1;
        const remaining = roundCurrency(
            Math.abs(this.revolut_payable_target) - sign * this.get_total_paid(), this.currency);
        return {
            ...totals,
            order_sign: sign,
            order_rounding: roundCurrency(
                Math.abs(this.revolut_payable_target) - totals.order_total, this.currency),
            order_remaining: remaining,
            order_has_zero_remaining: floatIsZero(remaining, this.currency.decimal_places),
        };
    },

    get_total_with_tax() {
        return this.revolut_has_authority_exposure
            ? this.revolut_payable_target : super.get_total_with_tax(...arguments);
    },

    getTotalDue() {
        return this.revolut_has_authority_exposure
            ? this.revolut_payable_target : super.getTotalDue(...arguments);
    },

    get_rounding_applied() {
        // The authorized target already includes its rounding. Native 18
        // validation adds this method to get_total_with_tax, so do not add it
        // again. Keep the rounding detail in the exported receipt data.
        return this.revolut_has_authority_exposure ? 0 : super.get_rounding_applied(...arguments);
    },

    get_due() {
        return this.revolut_has_authority_exposure
            ? roundCurrency(this.revolut_payable_target < 0
                ? Math.min(0, this.revolut_payable_target - this.get_total_paid())
                : Math.max(0, this.revolut_payable_target - this.get_total_paid()), this.currency)
            : super.get_due(...arguments);
    },

    get_change() {
        return this.revolut_has_authority_exposure
            ? roundCurrency(this.revolut_payable_target < 0
                ? Math.min(0, this.get_total_paid() - this.revolut_payable_target)
                : Math.max(0, this.get_total_paid() - this.revolut_payable_target), this.currency)
            : super.get_change(...arguments);
    },

    getDefaultAmountDueToPayIn(paymentMethod) {
        if (!this.revolut_has_authority_exposure) {
            return super.getDefaultAmountDueToPayIn(...arguments);
        }
        const due = this.get_due();
        // Global rounding is already part of the authorized target. Cash-only
        // rounding still applies when the cashier adds the remaining Cash.
        return this.config.only_round_cash_method && this.shouldRound(paymentMethod)
            ? this.getRoundedRemaining(this.config.rounding_method, due) : due;
    },

    electronic_payment_in_progress() {
        const actions = orderActions(this);
        if (!actions.hasRefundException) {
            return super.electronic_payment_in_progress(...arguments);
        }
        return actions.electronicPaymentInProgress;
    },

    add_paymentline() {
        if (this.uiState.revolutPreparingPayment || orderActions(this).blocksAlternativeTender) {
            return false;
        }
        return super.add_paymentline(...arguments);
    },

    remove_paymentline(line) {
        if (this.uiState.revolutPreparingPayment || !paymentActions(line).canDelete) {
            return false;
        }
        const retired = line.uiState?.revolutRetiredPayment;
        const result = super.remove_paymentline(...arguments);
        if (retired?.orderId === this.id && retired.paymentId === line.id) {
            // The recovery RPC already unlinked this exact server record.
            // Native deletion queues an ORM command even for silent deletes;
            // acknowledge only that command to preserve other pending edits.
            const commands = this.models.commands["pos.order"];
            const key = `payment_ids_${this.id}`;
            for (const pending of [commands.delete, commands.unlink]) {
                const remaining = (pending.get(key) || []).filter((id) => id !== retired.paymentId);
                if (remaining.length) {
                    pending.set(key, remaining);
                } else {
                    pending.delete(key);
                }
            }
        }
        return result;
    },
});

patch(PaymentScreen.prototype, {
    get isRefundOrder() {
        return this.currentOrder._isRefundOrder();
    },
    async addNewPaymentLine(paymentMethod) {
        if (orderActions(this.currentOrder).blocksAlternativeTender) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut reconciliation required"),
                body: _t("Reconcile the unresolved Revolut payment before adding another tender."),
            });
            return false;
        }
        return super.addNewPaymentLine(...arguments);
    },
    async validateOrder() {
        const order = this.currentOrder;
        const refunds = order.payment_ids.filter(isRevolutRefund);
        if (refunds.length) {
            await restoreRefundOriginals(this.pos, order);
            if (this.currentOrder !== order || order.state !== "draft") {
                return false;
            }
            const restored = [];
            // Loading original/related records can replace locally restored
            // references with the saved waiting draft. Recover committed refund
            // evidence after those reads, before native checkout serializes it.
            for (const line of refunds) {
                await line.payment_method_id.payment_terminal.paymentState.restore(order, line);
                if (this.currentOrder !== order || order.state !== "draft" ||
                    !order.payment_ids.includes(line) || line.pos_order_id !== order) {
                    return false;
                }
                const snapshot = line.uiState.revolutSnapshot;
                if (snapshot?.state === "verified" && snapshot.payment_id && snapshot.order_id &&
                    snapshot.operation_id === line.uiState.revolutOperationId &&
                    line.uiState.revolutCheckoutRestored === true) {
                    restored.push({ line, snapshot });
                }
            }
            // Each canonical refresh includes every tender. Only after the last
            // refresh, project all successfully restored refund references so a
            // later tender cannot erase an earlier tender's verified metadata.
            for (const { line, snapshot } of restored) {
                if (order.payment_ids.includes(line) && line.pos_order_id === order &&
                    line.uiState.revolutSnapshot === snapshot &&
                    snapshot.operation_id === line.uiState.revolutOperationId) {
                    line.payment_method_id.payment_terminal._setVerifiedReferences(line, snapshot);
                    line.uiState.revolutCheckoutRestored = true;
                    line.set_payment_status("done");
                }
            }
        }
        if (orderActions(this.currentOrder).blocksCheckout) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut reconciliation required"),
                body: _t("This order has an unresolved Revolut payment. Check its status before completing checkout."),
            });
            return false;
        }
        const sale = this.currentOrder.payment_ids.find((line) => isRevolut(line) && !isRevolutRefund(line));
        if (sale && this.currentOrder.revolut_has_authority_exposure &&
            this.currentOrder.payment_ids.some((line) => line.payment_method_id.is_cash_count)) {
            this.numberBuffer.capture();
            // A Cash tender added after card verification must be admitted by
            // the server before native validation synchronizes the paid order.
            await sale.payment_method_id.payment_terminal._preparePayment(this.currentOrder, sale);
        }
        return super.validateOrder(...arguments);
    },

    async sendPaymentRequest(line, options = {}) {
        if (!isRevolut(line)) {
            return super.sendPaymentRequest(...arguments);
        }
        return line.payment_method_id.payment_terminal.paymentState.screenRequest(
            this.currentOrder, line, async () => {
                if (isRevolutRefund(line)) {
                    return this._sendRevolutRefundRequest(line);
                }
                try {
                    return await super.sendPaymentRequest(line);
                } finally {
                    this.pos.paymentTerminalInProgress = false;
                }
            }, options
        );
    },

    async _sendRevolutRefundRequest(line) {
        // Revolut refunds use the Merchant API, not the physical terminal.
        // Keep native checkout behavior without acquiring or releasing Odoo's
        // shared terminal flag: another order may be taking a card payment.
        const order = line.pos_order_id;
        this.numberBuffer.capture();
        order.payment_ids.forEach((payment) => { payment.can_be_reversed = false; });
        const successful = await line.pay();
        if (successful && order.is_paid() && this.pos.config.auto_validate_terminal_payment &&
            this.pos.get_order()?.uuid === order.uuid) {
            this.validateOrder(false);
        }
    },

    updateSelectedPaymentline() {
        // Freeze tender edits while preparing without covering native Cancel
        // and Delete, which must still request cancellation before dispatch.
        if (this.currentOrder.uiState.revolutPreparingPayment ||
            !paymentActions(this.selectedPaymentLine).canEditAmount) {
            this.numberBuffer.reset();
            return;
        }
        return super.updateSelectedPaymentline(...arguments);
    },

    async sendPaymentCancel(line) {
        if (!isRevolut(line)) {
            return super.sendPaymentCancel(...arguments);
        }
        return line.payment_method_id.payment_terminal.paymentState.screenCancel(
            this.currentOrder, line,
            () => this.sendPaymentRequest(line),
            () => {
                if (!isRevolutRefund(line)) {
                    this.pos.paymentTerminalInProgress = false;
                }
            }
        );
    },

    async deletePaymentLine(uuid) {
        const line = this.paymentLines.find((payment) => payment.uuid === uuid);
        const order = this.currentOrder;
        const actions = paymentActions(line);
        if (!actions.canDelete || line?.uiState.revolutRecoveryRequired) {
            if (!(actions.shouldCancelBeforeDelete || line.uiState.revolutRecoveryRequired) ||
                !await this.sendPaymentCancel(line)) {
                return;
            }
            if (line.uiState.revolutRecoveryRequired &&
                !await line.payment_method_id.payment_terminal.paymentState.removeRecoveredPayment(order, line)) {
                return;
            }
        }
        if (isRevolut(line) && !isRevolutRefund(line) && Number.isInteger(line.id)) {
            // Native removal only queues an in-memory command lost on refresh.
            // Require durable, idempotent server retirement before hiding it.
            if (!line.uiState.revolutRetiredPayment &&
                !await line.payment_method_id.payment_terminal.paymentState.removeRecoveredPayment(order, line)) {
                return;
            }
            order.remove_paymentline(line);
            if (this.currentOrder === order) {
                this.numberBuffer.reset();
            }
            return;
        }
        return super.deletePaymentLine(...arguments);
    },

    async sendForceDone(line) {
        if (isRevolut(line)) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut verification required"),
                body: _t("A Revolut payment cannot be forced to done. Wait for server verification or reconcile the unresolved payment."),
            });
            return false;
        }
        return super.sendForceDone(...arguments);
    },
});

patch(PaymentScreenPaymentLines.prototype, {
    revolutPaymentStatus(line) {
        if (paymentOutcome(line) === "checkout_restore_failed") {
            return _t("Verified — reconnect and Check status to restore checkout");
        }
        if (line.uiState.revolutSnapshot?.awaiting_tip_details) {
            return _t("Payment received — verifying payment details");
        }
        const outcome = paymentOutcome(line);
        if (outcome === "register_access_denied") {
            return _t("Register access required — contact an administrator");
        }
        if (isRevolutRefund(line)) {
            const messages = {
                discovery_interrupted: _t("Connection check failed — no refund request sent"),
                discovery_timed_out: _t("Connection check timed out — no refund request sent"),
                discovery_cancelled: _t("No refund request sent"),
                no_refund_attempt: _t("No refund request sent — Resume or remove this line"),
                snapshot_invalid: _t("Correct the return — no refund request sent"),
                failed: _t("Refund failed — remove this line to retry"),
                pending: _t("Refund pending"),
                interrupted: _t("Communication interrupted — refund unresolved"),
                timed_out: _t("Waiting limit expired — refund unresolved"),
            };
            return messages[outcome] || _t("Refund unresolved");
        }
        const messages = {
            discovery_interrupted: _t("Connection check failed — no payment request sent"),
            discovery_timed_out: _t("Connection check timed out — no payment request sent"),
            discovery_cancelled: _t("No payment request sent"),
            snapshot_invalid: _t("Correct the cart — no payment request sent"),
            authority_required: _t("Review or approve the cart — no new payment request sent"),
            recovery_required: _t("Tender recovery changed — Check status before resuming"),
            unstarted_recovered: _t("No payment request sent — Resume or remove this line"),
            retired_recovered: _t("This payment line was removed — remove its local copy"),
            terminal_busy: _t("Terminal busy — no payment request sent"),
            terminal_unavailable: _t("Terminal unavailable — no charge sent"),
            terminal_check_failed: _t("Terminal connection check failed — no charge sent"),
            declined: _t("Payment declined"),
            failed: _t("Payment failed"),
            cancelled: _t("Payment cancelled"),
            interrupted: _t("Communication interrupted — payment unresolved"),
            timed_out: _t("Waiting limit expired — payment unresolved"),
        };
        return messages[outcome] || _t("Payment unresolved");
    },

    revolutCanRetry(line) {
        return paymentActions(line).retrySafe;
    },

    revolutCanResume(line) {
        return paymentActions(line).canResume;
    },
});

register_payment_method("revolut", PaymentRevolut);

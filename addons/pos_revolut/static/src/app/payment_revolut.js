import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { patch } from "@web/core/utils/patch";
import { Component, useState } from "@odoo/owl";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";
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

function discardUnstartedRefund(order, line) {
    line.uiState.revolutStarted = false;
    // This line never reached the server. Remove it so a different tender can
    // complete the return without carrying an unallocated terminal payment.
    order.removePaymentline(line);
}

export function hasRevolutExposure(order) {
    return orderActions(order).hasExposure;
}

function financialSnapshot(order) {
    return {
        amount_total: order.currency.round(order.priceIncl),
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
            error: "",
        });
    }

    get title() {
        return _t("Allocate Revolut refund");
    }

    get selectedSource() {
        return this.props.sources.find((source) => source.operation_id === this.state.operationId);
    }

    get maximumAmount() {
        return (this.props.maximumMinor / 10 ** this.props.decimalPlaces).toFixed(this.props.decimalPlaces);
    }

    defaultAmount(source) {
        return (Math.min(source.remaining_minor, this.props.maximumMinor) /
            10 ** this.props.decimalPlaces).toFixed(this.props.decimalPlaces);
    }

    selectSource(event) {
        this.state.operationId = Number(event.target.value);
        this.state.amount = this.defaultAmount(this.selectedSource);
        this.state.error = "";
    }

    updateAmount(event) {
        this.state.amount = event.target.value;
        this.state.error = "";
    }

    confirm() {
        const source = this.selectedSource;
        const factor = 10 ** this.props.decimalPlaces;
        const numeric = Number(this.state.amount);
        const minor = Math.round(numeric * factor);
        if (!source || source.payment_method_id !== this.props.paymentMethodId ||
            !Number.isFinite(numeric) || minor <= 0 ||
            Math.abs(numeric * factor - minor) > 0.000001 ||
            minor > source.remaining_minor || minor > this.props.maximumMinor) {
            this.state.error = _t("Choose an original Revolut payment and an amount within its remaining balance and this return.");
            return;
        }
        this.props.onConfirm({ operationId: source.operation_id, amount: minor / factor });
        this.props.close();
    }
}

function chooseRefundAllocation(dialog, sources, paymentMethodId, amount, currency) {
    const decimalPlaces = currency.decimal_places ?? 2;
    const maximumMinor = Math.round(Math.abs(amount) * 10 ** decimalPlaces);
    return new Promise((resolve) => {
        dialog.add(RefundAllocationDialog, {
            sources, paymentMethodId, maximumMinor, decimalPlaces,
            currencySymbol: currency.symbol,
            onConfirm: resolve,
        }, { onClose: () => resolve(false) });
    });
}

export class PaymentRevolut extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.paymentState = new RevolutPaymentState({
            methodId: this.payment_method_id.id,
            sessionId: this.pos.session.id,
            currencyId: this.pos.currency.id,
            adapter: {
                call: (method, args) => this.pos.data.call("pos.payment.method", method, args),
                financialSnapshot,
                restoreRefundOriginals: (order) => restoreRefundOriginals(this.pos, order),
                chooseAllocation: (sources, line) => chooseRefundAllocation(
                    this.env.services.dialog, sources, this.payment_method_id.id,
                    line.amount, this.pos.currency
                ),
                setRefundAmount: (line, amount) => {
                    line.uiState.revolutSelectingAllocation = true;
                    try {
                        line.setAmount(-amount);
                    } finally {
                        line.uiState.revolutSelectingAllocation = false;
                    }
                },
                discardRefund: (line) => discardUnstartedRefund(line.pos_order_id, line),
                setVerified: (line, result) => this._setVerified(line, result),
                showError: (line, state) => this._showResultError(line, state),
                showPreparationError: (line, reason) => this._showPreparationError(reason),
            },
        });
    }

    sendPaymentRequest(uuid) {
        const order = this.pos.getOrder();
        return this.paymentState.request(order, order.getPaymentlineByUuid(uuid));
    }

    sendPaymentCancel(order, uuid) {
        return this.paymentState.cancel(order, order.getPaymentlineByUuid(uuid));
    }

    _setVerified(line, result) {
        line.transaction_id = result.payment_id;
        line.payment_ref_no = result.order_id;
        if (!line.uiState.revolutReceiptSet) {
            line.setReceiptInfo(isRevolutRefund(line)
                ? _t("Revolut refund: %s; original order: %s", result.order_id, result.original_order_id)
                : _t("Revolut payment: %s", result.payment_id));
            line.uiState.revolutReceiptSet = true;
        }
    }

    _showPreparationError(reason) {
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
        this.env.services.dialog.add(AlertDialog, messages[reason]);
    }

    _showResultError(line, state) {
        if (isRevolutRefund(line)) {
            const messages = {
                discovery_interrupted: _t("Could not check for an existing Revolut refund. No refund request was sent from this line. Retry after the connection returns, or remove this line and choose another eligible original payment method."),
                discovery_timed_out: _t("The check for an existing Revolut refund timed out. No refund request was sent from this line. Retry after the connection returns, or remove this line and choose another eligible original payment method."),
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
    initState() {
        super.initState(...arguments);
        this.uiState = this.uiState || {};
    },

    restoreState() {
        super.restoreState(...arguments);
        restorePaymentLine(this);
    },

    handlePaymentResponse(isPaymentSuccessful) {
        return super.handlePaymentResponse(paymentResponseSuccessful(this, isPaymentSuccessful));
    },

    setAmount() {
        if (!paymentActions(this).canEditAmount) {
            return;
        }
        return super.setAmount(...arguments);
    },

    delete() {
        if (!paymentActions(this).canDelete) {
            return false;
        }
        return super.delete(...arguments);
    },
});

patch(PosOrder.prototype, {
    electronicPaymentInProgress() {
        const actions = orderActions(this);
        if (!actions.hasRefundException) {
            return super.electronicPaymentInProgress(...arguments);
        }
        return actions.electronicPaymentInProgress;
    },

    addPaymentline(paymentMethod) {
        if (orderActions(this).blocksAlternativeTender) {
            return {
                status: false,
                data: _t("Reconcile the unresolved Revolut payment before adding another tender."),
            };
        }
        return super.addPaymentline(...arguments);
    },

    removePaymentline(line) {
        if (!paymentActions(line).canDelete) {
            return false;
        }
        return super.removePaymentline(...arguments);
    },
});

patch(PaymentScreen.prototype, {
    async validateOrder() {
        if (orderActions(this.currentOrder).blocksCheckout) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut reconciliation required"),
                body: _t("This order has an unresolved Revolut payment. Check its status before completing checkout."),
            });
            return false;
        }
        if (this.currentOrder.payment_ids.some(isRevolutRefund)) {
            await restoreRefundOriginals(this.pos, this.currentOrder);
        }
        return super.validateOrder(...arguments);
    },

    async sendPaymentRequest(line, options = {}) {
        if (!isRevolut(line)) {
            return super.sendPaymentRequest(...arguments);
        }
        return line.payment_method_id.payment_terminal.paymentState.screenRequest(
            this.currentOrder, line, () => super.sendPaymentRequest(line), options
        );
    },

    updateSelectedPaymentline() {
        if (!paymentActions(this.selectedPaymentLine).canEditAmount) {
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
            () => { this.pos.paymentTerminalInProgress = false; }
        );
    },

    async deletePaymentLine(uuid) {
        const line = this.paymentLines.find((payment) => payment.uuid === uuid);
        const actions = paymentActions(line);
        if (!actions.canDelete) {
            if (actions.shouldCancelBeforeDelete && await this.sendPaymentCancel(line)) {
                this.currentOrder.removePaymentline(line);
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
        const outcome = paymentOutcome(line);
        if (isRevolutRefund(line)) {
            const messages = {
                discovery_interrupted: _t("Connection check failed — no refund request sent"),
                discovery_timed_out: _t("Connection check timed out — no refund request sent"),
                discovery_cancelled: _t("No refund request sent"),
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
        return line.uiState.revolutStartRejected === "terminal_busy" &&
            paymentActions(line).retrySafe;
    },
});

register_payment_method("revolut", PaymentRevolut);

import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";

const POLL_INTERVAL_MS = 1000;
const PAYMENT_TIMEOUT_MS = 60000;
const FINAL_FAILURE_STATES = new Set(["declined", "failed", "cancelled", "unresolved"]);

class ForegroundTimeout extends Error {}

function isRevolut(line) {
    return line?.payment_method_id?.use_payment_terminal === "revolut";
}

function isLocked(line) {
    return isRevolut(line) && !line.uiState?.revolutSnapshot?.retry_safe &&
        (line.uiState?.revolutStarted || ["retry", "waiting", "waitingCard", "waitingCancel"].includes(line.getPaymentStatus()));
}

function needsReconciliation(line) {
    return isLocked(line) && line.uiState?.revolutSnapshot?.state !== "verified";
}

export function hasRevolutExposure(order) {
    return order?.payment_ids?.some((line) => isRevolut(line) &&
        (isLocked(line) || line.uiState?.revolutStarting || line.transaction_id ||
            line.getPaymentStatus() === "done"));
}

function financialSnapshot(order) {
    return {
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
        })),
    };
}

// Bound the whole foreground wait, including slow or disconnected RPCs. A late
// server response remains durable and is reconciled on the next cashier action.
async function beforeDeadline(promise, deadline) {
    let timer;
    try {
        return await Promise.race([
            promise,
            new Promise((resolve, reject) => {
                timer = setTimeout(() => reject(new ForegroundTimeout()), Math.max(0, deadline - Date.now()));
            }),
        ]);
    } finally {
        clearTimeout(timer);
    }
}

export class PaymentRevolut extends PaymentInterface {
    setup() {
        super.setup(...arguments);
        this.requests = new Map();
        this.cancellations = new Map();
    }

    sendPaymentRequest(uuid) {
        if (this.requests.has(uuid)) {
            return this.requests.get(uuid);
        }
        const order = this.pos.getOrder();
        const line = order.getPaymentlineByUuid(uuid);
        const request = this._waitForPayment(order, line).finally(() => this.requests.delete(uuid));
        this.requests.set(uuid, request);
        return request;
    }

    async _waitForPayment(order, line) {
        const deadline = Date.now() + PAYMENT_TIMEOUT_MS;
        const started = line.uiState.revolutStarted;
        line.uiState.revolutStarted = true;
        line.setPaymentStatus("waiting");
        try {
            let result = line.uiState.revolutSnapshot;
            let discovered = false;
            if (!started && !result?.operation_id) {
                result = await beforeDeadline(this.pos.data.call(
                    "pos.payment.method", "revolut_find_payment",
                    [[this.payment_method_id.id], order.uuid, line.uuid]
                ), deadline);
                discovered = Boolean(result);
            }
            if (!result || (result.retry_safe && !discovered)) {
                const previousOperationId = result?.retry_safe ? result.operation_id : false;
                line.uiState.revolutPreviousOperationId = previousOperationId;
                line.uiState.revolutSnapshot = false;
                line.uiState.revolutOperationId = false;
                line.uiState.revolutStarting = true;
                try {
                    result = await beforeDeadline(this.pos.data.call(
                        "pos.payment.method", "revolut_start_payment", [
                            [this.payment_method_id.id], this.pos.session.id,
                            order.uuid, line.uuid, line.amount, this.pos.currency.id,
                            previousOperationId, financialSnapshot(order),
                        ]
                    ), deadline);
                } finally {
                    line.uiState.revolutStarting = false;
                }
            } else if (!result?.operation_id) {
                this._showResultError(line, "interrupted");
                return false;
            } else if (result.state !== "verified" && !result.retry_safe) {
                line.uiState.revolutOperationId = result.operation_id;
                result = await beforeDeadline(this._operationCall("revolut_poll_payment", order, line), deadline);
            }
            this._remember(line, result);
            while (Date.now() < deadline) {
                // Cancellation and polling share the authoritative latest result.
                if (this.cancellations.has(line.uuid)) {
                    await beforeDeadline(this.cancellations.get(line.uuid), deadline);
                }
                result = line.uiState.revolutSnapshot;
                if (result.state === "verified") {
                    this._setVerified(line, result);
                    return true;
                }
                if (FINAL_FAILURE_STATES.has(result.state)) {
                    this._showResultError(line, result.local_outcome || result.state);
                    return false;
                }
                line.setPaymentStatus("waitingCard");
                await beforeDeadline(new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS)), deadline);
                if (!this.cancellations.has(line.uuid)) {
                    this._remember(line, await beforeDeadline(
                        this._operationCall("revolut_poll_payment", order, line), deadline
                    ));
                }
            }
            throw new ForegroundTimeout();
        } catch (error) {
            if (line.uiState.revolutSnapshot?.state === "verified") {
                this._setVerified(line, line.uiState.revolutSnapshot);
                return true;
            }
            const outcome = error instanceof ForegroundTimeout ? "timed_out" : "interrupted";
            line.uiState.revolutLocalOutcome = outcome;
            if (outcome === "timed_out" && line.uiState.revolutOperationId) {
                // Do not extend the foreground limit by waiting for this RPC.
                this._operationCall("revolut_mark_timeout", order, line).catch(() => {});
            }
            this._showResultError(line, outcome);
            return false;
        }
    }

    _operationCall(method, order, line) {
        return this.pos.data.call("pos.payment.method", method, [
            [this.payment_method_id.id], line.uiState.revolutOperationId,
            order.uuid, line.uuid,
        ]);
    }

    _remember(line, result) {
        const previous = line.uiState.revolutSnapshot;
        // An older poll must never overwrite a cancellation or verified payment.
        if (previous?.operation_id === result.operation_id &&
            (previous.state === "verified" || (previous.retry_safe && !result.retry_safe && result.state !== "verified"))) {
            return;
        }
        line.uiState.revolutSnapshot = result;
        line.uiState.revolutOperationId = result.operation_id;
        line.uiState.revolutLocalOutcome = result.local_outcome || false;
    }

    _setVerified(line, result) {
        line.transaction_id = result.payment_id;
        line.payment_ref_no = result.order_id;
        if (!line.uiState.revolutReceiptSet) {
            line.setReceiptInfo(_t("Revolut payment: %s", result.payment_id));
            line.uiState.revolutReceiptSet = true;
        }
    }

    sendPaymentCancel(order, uuid) {
        if (this.cancellations.has(uuid)) {
            return this.cancellations.get(uuid);
        }
        const line = order.getPaymentlineByUuid(uuid);
        const cancellation = this._cancelPayment(order, line).finally(() => this.cancellations.delete(uuid));
        this.cancellations.set(uuid, cancellation);
        return cancellation;
    }

    async _cancelPayment(order, line) {
        const deadline = Date.now() + PAYMENT_TIMEOUT_MS;
        try {
            if (line.uiState.revolutStarting) {
                this._showResultError(line, "unresolved");
                return false;
            }
            if (!line.uiState.revolutOperationId) {
                const result = await beforeDeadline(this.pos.data.call(
                    "pos.payment.method", "revolut_find_payment",
                    [[this.payment_method_id.id], order.uuid, line.uuid]
                ), deadline);
                if (!result || result.operation_id === line.uiState.revolutPreviousOperationId) {
                    this._showResultError(line, "interrupted");
                    return false;
                }
                this._remember(line, result);
            }
            this._remember(line, await beforeDeadline(
                this._operationCall("revolut_cancel_payment", order, line), deadline
            ));
            const result = line.uiState.revolutSnapshot;
            if (result.state === "verified") {
                this._setVerified(line, result);
                line.setPaymentStatus("done");
                return false;
            }
            this._showResultError(line, result.provider_state === "processing" ? "processing" : result.local_outcome || result.state);
            return result.retry_safe === true;
        } catch (error) {
            this._showResultError(line, error instanceof ForegroundTimeout ? "timed_out" : "interrupted");
            return false;
        }
    }

    _showResultError(line, state) {
        if (["interrupted", "timed_out"].includes(state)) {
            line.uiState.revolutLocalOutcome = state;
        }
        const providerState = line.uiState.revolutSnapshot?.provider_state;
        if (state === "failed" && ["terminal_unavailable", "terminal_check_failed"].includes(providerState)) {
            state = providerState;
        }
        const messageKey = `${line.uiState.revolutOperationId}:${state}`;
        if (line.uiState.revolutMessage === messageKey) {
            return;
        }
        line.uiState.revolutMessage = messageKey;
        const messages = {
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
        this.uiState.revolutScreenRequest = false;
        this.uiState.revolutStarting = false;
        if (isRevolut(this) && this.uiState.revolutStarted && this.getPaymentStatus() !== "done") {
            // Foreground promises do not survive a reload. Resume through reconciliation.
            this.setPaymentStatus("retry");
        }
    },

    handlePaymentResponse(isPaymentSuccessful) {
        if (isRevolut(this) && this.uiState.revolutSnapshot?.state === "verified") {
            // A late foreground failure must not undo cancellation's verified result.
            isPaymentSuccessful = true;
        }
        return super.handlePaymentResponse(isPaymentSuccessful);
    },

    setAmount() {
        if (isLocked(this)) {
            return;
        }
        return super.setAmount(...arguments);
    },

    delete() {
        if (isLocked(this)) {
            return false;
        }
        return super.delete(...arguments);
    },
});

patch(PosOrder.prototype, {
    addPaymentline(paymentMethod) {
        if (this.payment_ids.some(needsReconciliation)) {
            return {
                status: false,
                data: _t("Reconcile the unresolved Revolut payment before adding another tender."),
            };
        }
        return super.addPaymentline(...arguments);
    },

    removePaymentline(line) {
        if (isLocked(line)) {
            return false;
        }
        return super.removePaymentline(...arguments);
    },
});

patch(PaymentScreen.prototype, {
    async validateOrder() {
        if (this.currentOrder.payment_ids.some(needsReconciliation)) {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut reconciliation required"),
                body: _t("This order has an unresolved Revolut payment. Check its status before completing checkout."),
            });
            return false;
        }
        return super.validateOrder(...arguments);
    },

    async sendPaymentRequest(line) {
        if (!isRevolut(line)) {
            return super.sendPaymentRequest(...arguments);
        }
        if (line.uiState.revolutScreenRequest) {
            return;
        }
        line.uiState.revolutScreenRequest = true;
        try {
            return await super.sendPaymentRequest(...arguments);
        } finally {
            line.uiState.revolutScreenRequest = false;
        }
    },

    updateSelectedPaymentline() {
        if (isLocked(this.selectedPaymentLine)) {
            this.numberBuffer.reset();
            return;
        }
        return super.updateSelectedPaymentline(...arguments);
    },

    async sendPaymentCancel(line) {
        if (!isRevolut(line)) {
            return super.sendPaymentCancel(...arguments);
        }
        line.setPaymentStatus("waitingCancel");
        const safe = await line.payment_method_id.payment_terminal.sendPaymentCancel(this.currentOrder, line.uuid);
        if (line.uiState.revolutSnapshot?.state === "verified") {
            line.setPaymentStatus("done");
            if (!line.uiState.revolutScreenRequest) {
                await this.sendPaymentRequest(line);
            }
        } else if (safe || !line.uiState.revolutScreenRequest) {
            line.setPaymentStatus("retry");
            this.pos.paymentTerminalInProgress = false;
        } else {
            line.setPaymentStatus("waitingCard");
        }
        return safe;
    },

    async deletePaymentLine(uuid) {
        const line = this.paymentLines.find((payment) => payment.uuid === uuid);
        if (isLocked(line)) {
            if (line.uiState.revolutSnapshot?.state !== "verified" && await this.sendPaymentCancel(line)) {
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
        const snapshot = line.uiState.revolutSnapshot;
        const outcome = ["terminal_unavailable", "terminal_check_failed"].includes(snapshot?.provider_state)
            ? snapshot.provider_state
            : line.uiState.revolutLocalOutcome || snapshot?.local_outcome || snapshot?.state;
        const messages = {
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
});

register_payment_method("revolut", PaymentRevolut);

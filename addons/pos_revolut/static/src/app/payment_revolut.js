import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { register_payment_method } from "@point_of_sale/app/services/pos_store";
import { PaymentInterface } from "@point_of_sale/app/utils/payment/payment_interface";

const POLL_INTERVAL_MS = 1000;
const PAYMENT_TIMEOUT_MS = 90000;
const FINAL_FAILURE_STATES = new Set(["declined", "failed", "cancelled", "unresolved"]);

export class PaymentRevolut extends PaymentInterface {
    async sendPaymentRequest(uuid) {
        await super.sendPaymentRequest(...arguments);
        const order = this.pos.getOrder();
        const line = order.getPaymentlineByUuid(uuid);
        line.setPaymentStatus("waiting");

        try {
            let result = await this.pos.data.call(
                "pos.payment.method",
                "revolut_start_payment",
                [
                    [this.payment_method_id.id],
                    this.pos.session.id,
                    order.uuid,
                    line.uuid,
                    line.amount,
                    this.pos.currency.id,
                ]
            );
            line.uiState.revolutOperationId = result.operation_id;
            const deadline = Date.now() + PAYMENT_TIMEOUT_MS;
            while (Date.now() < deadline) {
                if (result.state === "verified") {
                    line.transaction_id = result.payment_id;
                    line.payment_ref_no = result.order_id;
                    line.setReceiptInfo(
                        _t("Revolut payment: %s", result.payment_id)
                    );
                    return true;
                }
                if (FINAL_FAILURE_STATES.has(result.state)) {
                    this._showResultError(result.state);
                    return false;
                }
                line.setPaymentStatus("waitingCard");
                await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
                result = await this.pos.data.call(
                    "pos.payment.method",
                    "revolut_poll_payment",
                    [
                        [this.payment_method_id.id],
                        result.operation_id,
                        order.uuid,
                        line.uuid,
                    ]
                );
            }
            await this.pos.data.call(
                "pos.payment.method",
                "revolut_mark_timeout",
                [
                    [this.payment_method_id.id],
                    line.uiState.revolutOperationId,
                    order.uuid,
                    line.uuid,
                ]
            );
            this._showResultError("unresolved");
            return false;
        } catch (error) {
            const { message } = error.data || error;
            this._showError(message || _t("The Revolut payment could not be completed."));
            return false;
        }
    }

    async sendPaymentCancel(order, uuid) {
        await super.sendPaymentCancel(...arguments);
        const line = order.getPaymentlineByUuid(uuid);
        if (line.uiState.revolutOperationId) {
            try {
                await this.pos.data.call(
                    "pos.payment.method",
                    "revolut_mark_timeout",
                    [
                        [this.payment_method_id.id],
                        line.uiState.revolutOperationId,
                        order.uuid,
                        line.uuid,
                    ]
                );
            } catch {
                // The server already retains the durable operation and claim.
            }
        }
        this._showResultError("unresolved");
        return false;
    }

    _showResultError(state) {
        const messages = {
            declined: _t("The Revolut payment was declined."),
            failed: _t("The Revolut payment failed."),
            cancelled: _t("The Revolut payment was cancelled."),
            unresolved: _t(
                "The Revolut result is unresolved. Do not retry or use this terminal until the payment is reconciled."
            ),
        };
        this._showError(messages[state] || messages.unresolved);
    }

    _showError(message) {
        this.env.services.dialog.add(AlertDialog, {
            title: _t("Revolut Terminal"),
            body: message,
        });
    }
}

patch(PaymentScreen.prototype, {
    async sendForceDone(line) {
        if (line.payment_method_id.use_payment_terminal === "revolut") {
            this.dialog.add(AlertDialog, {
                title: _t("Revolut verification required"),
                body: _t(
                    "A Revolut payment cannot be forced to done. Wait for server verification or reconcile the unresolved payment."
                ),
            });
            return false;
        }
        return super.sendForceDone(...arguments);
    },
});

register_payment_method("revolut", PaymentRevolut);

import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";

patch(PaymentScreen.prototype, {
    addRevolutSplitLine(method) {
        if (method.use_payment_terminal !== "revolut" || this.isRefundOrder ||
            this.pos.paymentTerminalInProgress || this.currentOrder.remainingDue <= 0) {
            return;
        }
        // Use the native editable pending line and Send action. The ordinary
        // payment-method button keeps its automatic full-balance behavior.
        const result = this.currentOrder.addPaymentline(method);
        if (result.status) {
            this.numberBuffer.set(result.data.amount.toString());
        } else {
            this.dialog.add(AlertDialog, { title: _t("Revolut allocation"), body: result.data });
        }
    },
});

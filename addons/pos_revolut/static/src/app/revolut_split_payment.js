import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { useEffect, useRef } from "@odoo/owl";

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const screen = useRef("revolutPaymentScreen");
        useEffect(() => {
            if (this.revolutAllocationLineUuid === this.selectedPaymentLine?.uuid) {
                // Amount keys still go to the native number buffer. Enter now
                // activates Send instead of creating another pending line.
                screen.el?.querySelector(".send_payment_request")?.focus();
                this.revolutAllocationLineUuid = null;
            }
        }, () => [this.selectedPaymentLine?.uuid]);
    },

    addRevolutSplitLine(method) {
        if (method.use_payment_terminal !== "revolut" || this.isRefundOrder ||
            this.pos.paymentTerminalInProgress || this.currentOrder.remainingDue <= 0) {
            return;
        }
        // Use the native editable pending line and Send action. The ordinary
        // payment-method button keeps its automatic full-balance behavior.
        const result = this.currentOrder.addPaymentline(method);
        if (result.status) {
            this.revolutAllocationLineUuid = result.data.uuid;
            this.numberBuffer.set(result.data.amount.toString());
        } else {
            this.dialog.add(AlertDialog, { title: _t("Revolut allocation"), body: result.data });
        }
    },
});

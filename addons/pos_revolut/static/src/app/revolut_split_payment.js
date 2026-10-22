import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { useEffect, useRef } from "@odoo/owl";

patch(PaymentScreenPaymentLines.prototype, {
    setup() {
        super.setup(...arguments);
        const lines = useRef("revolutPaymentLines");
        useEffect(() => {
            const line = this.props.paymentLines.find((payment) => payment.isSelected());
            if (line?.uiState.revolutAllocationFocus) {
                // Amount keys still go to the native number buffer. Enter now
                // activates Send instead of creating another pending line.
                lines.el.querySelector(".send_payment_request")?.focus();
                line.uiState.revolutAllocationFocus = false;
            }
        });
    },
});

patch(PaymentScreen.prototype, {
    addRevolutSplitLine(method) {
        if (method.use_payment_terminal !== "revolut" || this.isRefundOrder ||
            this.pos.paymentTerminalInProgress || this.currentOrder.get_due() <= 0) {
            return;
        }
        // Use the native editable pending line and Send action. The ordinary
        // payment-method button keeps its automatic full-balance behavior.
        const result = this.currentOrder.add_paymentline(method);
        if (result) {
            result.uiState.revolutAllocationFocus = true;
            // Odoo 18 appends digits to set() values. Match its native payment
            // line selection so the first key replaces the displayed default.
            this.numberBuffer.reset();
        } else {
            this.dialog.add(AlertDialog, { title: _t("Revolut allocation"),
                body: _t("Reconcile the unresolved Revolut payment before adding another tender.") });
        }
    },
});

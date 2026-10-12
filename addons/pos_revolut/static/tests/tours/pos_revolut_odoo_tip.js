import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as NumberPopup from "@point_of_sale/../tests/generic_helpers/number_popup_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_odoo_tip_rejection", {
    steps: () => {
        let identity;
        return [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickTipButton(),
            NumberPopup.enterValue("1"),
            Dialog.confirm(),
            PaymentScreen.totalIs("13.34"),
            PaymentScreen.clickPaymentMethod("Revolut"),
            {
                content: "Native preparation explains the configured Odoo tip rejection",
                trigger: ".modal:contains('Remove the Odoo-entered tip before using terminal-selected tips.')",
            },
            Dialog.confirm(),
            {
                content: "The rejected draft has no exposure and native terminal busy state is released",
                trigger: ".payment-screen .electronic_status:contains('no new payment request sent')",
                run() {
                    const pos = window.posmodel;
                    const order = pos.getOrder();
                    const line = order.payment_ids.find((payment) => payment.payment_method_id.use_payment_terminal === "revolut");
                    identity = { orderUuid: order.uuid, lineUuid: line?.uuid };
                    if (!Number.isInteger(order.id) || order.getTip() !== 1 ||
                        !line?.uiState.revolutUndispatched || line.uiState.revolutStarted ||
                        line.uiState.revolutOperationId || line.uiState.revolutSnapshot ||
                        line.isDone() || line.transaction_id || line.payment_ref_no ||
                        pos.paymentTerminalInProgress) {
                        throw new Error("Odoo tip rejection lost non-dispatch proof or native safety state");
                    }
                },
            },
            PaymentScreen.clickPaymentlineDelButton("Revolut", "13.34"),
            PaymentScreen.emptyPaymentlines("13.34"),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Cash", "13.34"),
            {
                content: "Safe removal completes the same native order through its cash lane",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.getOrder();
                    if (order.uuid !== identity.orderUuid || order.getPaymentlineByUuid(identity.lineUuid)) {
                        throw new Error("Cash completion changed the order or retained the rejected Revolut tender");
                    }
                },
            },
        ].flat();
    },
});

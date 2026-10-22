import { PaymentInterface } from "@point_of_sale/app/payment/payment_interface";
import { register_payment_method } from "@point_of_sale/app/store/pos_store";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { registry } from "@web/core/registry";

const REFERENCE = "OTHER_TERMINAL_NATIVE_REFERENCE";

// This asset is loaded only by the POS test bundle. Mock the unrelated terminal
// response while retaining native registration, pay(), completion and printing.
class OtherTerminalTest extends PaymentInterface {
    async send_payment_request(uuid) {
        this.requests = (this.requests || 0) + 1;
        const payment = this.pos.get_order().get_paymentline_by_uuid(uuid);
        payment.transaction_id = REFERENCE;
        payment.set_receipt_info(REFERENCE);
        return true;
    }
}

register_payment_method("other_terminal_test", OtherTerminalTest);

registry.category("web_tour.tours").add("pos_revolut_other_terminal_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Other terminal"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Other terminal", "12.34"),
        {
            content: "The unrelated terminal completed and printed through native POS once",
            trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${REFERENCE}')`,
            run() {
                const order = window.posmodel.get_order();
                const payment = order.payment_ids.find((line) =>
                    line.payment_method_id.use_payment_terminal === "other_terminal_test");
                if (!order.is_paid() || !payment?.is_done() || payment.amount !== 12.34 ||
                    payment.transaction_id !== REFERENCE ||
                    payment.payment_method_id.payment_terminal.requests !== 1 ||
                    payment.revolut_operation_id || payment.revolut_refund_operation_id) {
                    throw new Error("Installing Revolut changed native unrelated-terminal checkout");
                }
            },
        },
    ].flat(),
});

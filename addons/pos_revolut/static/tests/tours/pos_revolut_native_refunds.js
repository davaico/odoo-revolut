import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { registry } from "@web/core/registry";

function refundReference() {
    const reference = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
    return {
        trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${reference}')`,
        run() {
            if (document.querySelector(".receipt-screen .pos-receipt").textContent.split(reference).length !== 2) {
                throw new Error("Native return receipt lost or duplicated its refund reference");
            }
        },
    };
}

function returnOriginal(quantity) {
    return [
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        ...[...quantity].map((key) => ({
            trigger: `.ticket-screen .numpad button:contains('${key}')`, run: "click",
        })),
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_partial_refund", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        returnOriginal("0.5"),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-amount", run() {
            if (Number(this.anchor.value) !== 6.17) {
                throw new Error("A half-quantity return must refund exactly 6.17");
            }
        } },
        { trigger: ".revolut-refund-confirm", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-6.17"),
        ReceiptScreen.totalAmountContains("-6.17"),
        refundReference(),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_mixed_funding_refund", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickNumpad("4 . 3 4"),
        PaymentScreen.selectedPaymentlineHas("Cash", "4.34"),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "4.34"),
        ReceiptScreen.paymentLineContains("Revolut", "8.00"),
        returnOriginal("1"),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-amount", run() {
            if (Number(this.anchor.value) !== 8) {
                throw new Error("The card allocation cannot consume the original 4.34 Cash funding");
            }
        } },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".payment-screen .electronic_status:contains('Refund Successful')" },
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-8.00"),
        ReceiptScreen.paymentLineContains("Cash", "-4.34"),
        ReceiptScreen.totalAmountContains("-12.34"),
        refundReference(),
    ].flat(),
});

import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

function collectAdjustmentSale() {
    return [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.addOrderline("Return adjustment"),
        { trigger: ".product-screen .numpad button:contains('+/-')", run: "click" },
        ProductScreen.selectedOrderlineHasDirect("Return adjustment", "-1"),
        {
            trigger: ".product-screen",
            run() {
                const order = window.posmodel.getOrder();
                if (order.lines.length !== 2 || !order.lines.some((line) => line.qty === -1 && line.price_unit === 1) ||
                        order.currency.round(order.priceIncl) !== 11.34) {
                    throw new Error(`Negative adjustment sale fixture changed: ${JSON.stringify({
                        total: order.priceIncl, lines: order.lines.map((line) => ({qty: line.qty, price: line.price_unit})),
                    })}`);
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "11.34"),
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_negative_quantity_adjustment", {
    steps: () => [
        collectAdjustmentSale(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("11.34"),
        { trigger: ".ticket-screen .orderline:contains('Desk Pad')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        { trigger: ".ticket-screen .orderline:contains('Return adjustment')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        {
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.getOrder();
                const line = order.lines.find((item) => item.product_id.display_name === "Return adjustment");
                if (order.lines.length !== 2 || !line?.refunded_orderline_id || line.qty !== 1 ||
                        line.refunded_orderline_id.qty !== -1 || line.price_unit !== 1) {
                    throw new Error("Native selection did not reverse the negative original quantity");
                }
                if (!line.setQuantity(2)?.title || !line.setQuantity(-1)?.title || line.qty !== 1) {
                    throw new Error("Native adjustment editing lost the original quantity cap or sign");
                }
                line.setQuantity(0.5);
                if (line.qty !== 0.5 || line.price_unit !== 1) {
                    throw new Error("Native partial adjustment editing changed the original price");
                }
                line.setQuantity(1);
                if (line.qty !== 1 || line.price_unit !== 1) {
                    throw new Error("Native adjustment could not restore the remaining original quantity");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-11.34"),
        {
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.getOrder();
                const line = order.lines.find((item) => item.refunded_orderline_id?.qty === -1);
                if (line?.qty !== 1 || line.price_unit !== 1 || order.priceIncl !== -11.34 ||
                        order.remainingDue !== 0 || !order.payment_ids.some((payment) =>
                            payment.amount === -11.34 && payment.isDone())) {
                    throw new Error("Native adjustment receipt lost verified quantities or the collected refund amount");
                }
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_remaining_adjustment_zero_return", {
    steps: () => [
        collectAdjustmentSale(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("11.34"),
        {
            trigger: ".ticket-screen .order-row.active .order-name",
            run() {
                window.adjustmentOriginalHistoryName = this.anchor.textContent.trim();
            },
        },
        { trigger: ".ticket-screen .orderline:contains('Desk Pad')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-11.34"),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        {
            trigger: ".ticket-screen .order-row",
            run() {
                const original = [...document.querySelectorAll(".ticket-screen .order-row")].find((row) =>
                    row.querySelector(".order-name")?.textContent.trim() === window.adjustmentOriginalHistoryName);
                if (!original) {
                    throw new Error("Original sale disappeared while its adjustment remained unreturned");
                }
                original.click();
            },
        },
        { trigger: ".ticket-screen .orderline:contains('Return adjustment')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        {
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.getOrder();
                const line = order.lines[0];
                if (!Number.isInteger(order.id) || order.lines.length !== 1 || line.qty !== 1 ||
                        line.refunded_orderline_id?.qty !== -1 || order.priceIncl !== 0 ||
                        order.remainingDue !== 0 || order.payment_ids.length) {
                    throw new Error("Remaining adjustment did not load its conserved zero target before native checkout");
                }
            },
        },
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        {
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.getOrder();
                if (order.priceIncl !== 0 || order.payment_ids.length || order.lines[0].qty !== 1) {
                    throw new Error("Zero native adjustment return invented a payment or lost its reversed quantity");
                }
            },
        },
    ].flat(),
});

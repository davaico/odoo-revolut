import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as PartnerList from "@point_of_sale/../tests/tours/utils/partner_list_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

function originalSale(method) {
    return [
        Chrome.startPoS(),
        { trigger: "body:not(:has(.pos-loader))" },
        FloorScreen.clickTable("1"),
        { trigger: ".revolut-preset-button:contains('Takeout')", run: "click" },
        { trigger: ".modal .selection-item:contains('Dine In')", run: "click" },
        ...(method === "Revolut" ? [ProductScreen.clickPartnerButton(),
            PartnerList.clickPartner("Restaurant original policy customer")] : []),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod(method),
        ...(method === "Bank" ? PaymentScreen.clickValidate() : []),
        ReceiptScreen.isShown(),
        {
            content: "The original Restaurant sale uses customer policy B while the default remains A",
            trigger: ".receipt-screen",
            run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                if (order.pricelist_id?.name !== "Restaurant original prices B" ||
                    order.fiscal_position_id?.name !== "Restaurant original taxes B" ||
                    pos.config.default_preset_id?.pricelist_id?.name !== "Restaurant default prices A") {
                    throw new Error("Restaurant original sale did not establish distinct original and default policies");
                }
                sessionStorage.setItem("restaurantReturnOriginal", JSON.stringify({
                    uuid: order.uuid, lineUuid: order.lines[0].uuid,
                    pricelistId: order.pricelist_id.id, fiscalId: order.fiscal_position_id.id,
                    partnerId: order.partner_id?.id || false,
                }));
            },
        },
    ].flat();
}

function nativeReturn() {
    return [
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        {
            content: "Native refund creation retains the original customer, taxes, prices and source line",
            trigger: ".product-screen",
            run() {
                const original = JSON.parse(sessionStorage.getItem("restaurantReturnOriginal"));
                const order = window.posmodel.get_order();
                if (!order._isRefundOrder() || order.pricelist_id?.id !== original.pricelistId ||
                    order.fiscal_position_id?.id !== original.fiscalId ||
                    (order.partner_id?.id || false) !== original.partnerId ||
                    order.lines[0]?.refunded_orderline_id?.uuid !== original.lineUuid ||
                    order.lines[0]?.refunded_orderline_id?.order_id?.uuid !== original.uuid ||
                    order.get_total_with_tax() !== -12.34) {
                    throw new Error("Default Restaurant sale preset replaced the native return's original policy: " +
                        JSON.stringify({ original, pricelist: order.pricelist_id?.name,
                            fiscal: order.fiscal_position_id?.name, total: order.get_total_with_tax() }));
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_restaurant_bank_return_policy", {
    steps: () => [
        originalSale("Bank"),
        refresh(),
        { trigger: ".floor-screen .floor-map" },
        nativeReturn(),
        PaymentScreen.clickPaymentMethod("Bank"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Bank", "-12.34"),
        ReceiptScreen.totalAmountContains("-12.34"),
        { trigger: ".receipt-screen", run() { sessionStorage.removeItem("restaurantReturnOriginal"); } },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_revolut_return_policy", {
    steps: () => [
        originalSale("Revolut"),
        refresh(),
        { trigger: ".floor-screen .floor-map" },
        nativeReturn(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-amount", run() {
            if (Number(this.anchor.value) !== 12.34) {
                throw new Error("Restaurant return changed the original card allocation");
            }
        } },
        { trigger: ".revolut-refund-confirm", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        ReceiptScreen.totalAmountContains("-12.34"),
        { trigger: ".receipt-screen .pos-payment-terminal-receipt:contains('6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf')" },
        { trigger: ".receipt-screen", run() { sessionStorage.removeItem("restaurantReturnOriginal"); } },
    ].flat(),
});

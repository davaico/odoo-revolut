import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PartnerList from "@point_of_sale/../tests/tours/utils/partner_list_util";
import * as FloorScreen from "@pos_restaurant/../tests/tours/utils/floor_screen_util";
import * as SplitBillScreen from "@pos_restaurant/../tests/tours/utils/split_bill_screen_util";
import * as TipScreen from "@pos_restaurant/../tests/tours/utils/tip_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_restaurant_context_checkout", {
    steps: () => [
        Chrome.startPoS(),
        { trigger: "body:not(:has(.pos-loader))" },
        { trigger: ".floor-map .table:has(.label:contains('1')):not(.syncing)", run: "click" },
        { trigger: ".product-screen .revolut-preset-button:contains('Takeout')", run: "click" },
        { trigger: ".modal .selection-item:contains('Dine In')", run: "click" },
        ProductScreen.addOrderline("Desk Pad"),
        {
            content: "The selected preset applies its configured fiscal policy",
            trigger: ".product-screen .revolut-preset-button:contains('Dine In')",
            run() {
                const order = window.posmodel.get_order();
                if (order.preset_id?.name !== "Dine In" ||
                    order.fiscal_position_id?.name !== "Restaurant context fiscal policy") {
                    throw new Error("Restaurant sale context did not apply its fiscal policy");
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        {
            content: "Open the native adjustment screen for the captured order",
            trigger: ".receipt-screen",
            run() { window.posmodel.showScreen("TipScreen"); },
        },
        TipScreen.setCustomTip("1"),
        TipScreen.clickSettle(),
        { trigger: ".modal:contains('Revolut terminal tip'):contains('unsupported')" },
        Dialog.confirm(),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_unexposed_controls", {
    steps: () => [
        Chrome.startPoS(),
        { trigger: "body:not(:has(.pos-loader))" },
        FloorScreen.clickTable("1"),
        ProductScreen.clickControlButton("Split"),
        SplitBillScreen.clickOrderline("Desk Pad"),
        SplitBillScreen.clickPay(),
        {
            content: "A native split retains its selected sale context",
            trigger: ".product-screen",
            run() {
                const order = window.posmodel.get_order();
                if (order.preset_id?.name !== "Dine In" ||
                    order.fiscal_position_id?.name !== "Restaurant context fiscal policy" ||
                    order.lines[0].qty !== 1 || order.get_total_with_tax() !== 12.34) {
                    throw new Error("Native Restaurant split lost its selected sale context");
                }
            },
        },
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.clickContinueOrder(),
        Chrome.clickPlanButton(),
        FloorScreen.clickTable("1"),
        ProductScreen.clickControlButton("Transfer / Merge"),
        FloorScreen.clickTable("2"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Bank"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Bank", "24.68"),
    ].flat(),
});

function showRestaurantProducts() {
    return {
        trigger: ".product-screen, .payment-screen",
        run() {
            if (this.anchor.matches(".payment-screen")) {
                this.anchor.querySelector(".back-button").click();
            }
        },
    };
}

registry.category("web_tour.tours").add("pos_revolut_restaurant_customer_requirement", {
    steps: () => [
        Chrome.startPoS(),
        { trigger: "body:not(:has(.pos-loader))" },
        FloorScreen.clickTable("1"),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Bank"),
        PaymentScreen.clickValidate(),
        { trigger: ".modal:contains('customer with an address')" },
        Dialog.confirm(),
        showRestaurantProducts(),
        ProductScreen.clickPartnerButton(),
        PartnerList.searchCustomerValue("Restaurant addressed guest"),
        PartnerList.clickPartner("Restaurant addressed guest"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Bank", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_native_guards", {
    steps: () => [
        Chrome.startPoS(),
        { trigger: "body:not(:has(.pos-loader))" },
        FloorScreen.clickTable("1"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Retain the original authorized order and pending payment",
            trigger: ".payment-screen .electronic_status:contains('Waiting for card')",
            run() {
                const order = window.posmodel.get_order();
                const payment = order.payment_ids[0];
                sessionStorage.setItem("revolutRestaurantIdentity", JSON.stringify({
                    orderUuid: order.uuid, paymentUuid: payment.uuid,
                    operationId: payment.uiState.revolutSnapshot.operation_id,
                }));
            },
        },
        showRestaurantProducts(),
        ProductScreen.clickControlButton("Split"),
        SplitBillScreen.clickOrderline("Desk Pad"),
        SplitBillScreen.clickPay(),
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        SplitBillScreen.clickBack(),
        ProductScreen.clickControlButton("Transfer / Merge"),
        FloorScreen.clickTable("2"),
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "The native transfer guard leaves both source and destination intact",
            trigger: ".product-screen",
            run() {
                const pos = window.posmodel;
                const identity = JSON.parse(sessionStorage.getItem("revolutRestaurantIdentity"));
                const source = pos.models["pos.order"].getBy("uuid", identity.orderUuid);
                const destination = pos.get_order();
                if (source.table_id?.table_number !== 1 || source.lines[0].qty !== 2 ||
                    destination.table_id?.table_number !== 2 || destination.lines[0].qty !== 1) {
                    throw new Error("Native transfer changed protected Restaurant financial contents");
                }
            },
        },
        ProductScreen.clickControlButton("Transfer / Merge"),
        FloorScreen.clickTable("1"),
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        showRestaurantProducts(),
        ProductScreen.clickControlButton("Transfer / Merge"),
        FloorScreen.clickTable("3"),
        {
            content: "Moving to an empty table preserves the same order and attempt",
            trigger: ".payment-screen .electronic_status:contains('Waiting for card')",
            run() {
                const identity = JSON.parse(sessionStorage.getItem("revolutRestaurantIdentity"));
                const order = window.posmodel.get_order();
                if (order.uuid !== identity.orderUuid || order.table_id?.table_number !== 3 ||
                    order.payment_ids[0].uuid !== identity.paymentUuid ||
                    order.payment_ids[0].uiState.revolutSnapshot.operation_id !== identity.operationId) {
                    throw new Error("Table-only move changed the original Revolut identity");
                }
            },
        },
        Chrome.clickPlanButton(),
        FloorScreen.linkTables("3", "2"),
        { trigger: ".modal:contains('Revolut')" },
        Dialog.confirm(),
        { trigger: ".modal:contains('Revolut')" },
        Dialog.confirm(),
        refresh(),
        { trigger: ".floor-screen .floor-map" },
        FloorScreen.clickTable("3"),
        {
            content: "Refresh restores the same pending original at its new table",
            trigger: ".product-screen, .payment-screen",
            run() {
                const identity = JSON.parse(sessionStorage.getItem("revolutRestaurantIdentity"));
                const order = window.posmodel.get_order();
                const payment = order.get_paymentline_by_uuid(identity.paymentUuid);
                if (order.uuid !== identity.orderUuid || order.table_id?.table_number !== 3 ||
                    order.lines[0].qty !== 2 || order.get_total_with_tax() !== 24.68 ||
                    !payment || payment.uiState.revolutSnapshot?.operation_id !== identity.operationId) {
                    throw new Error("Restaurant refresh lost the original financial attempt");
                }
                sessionStorage.removeItem("revolutRestaurantIdentity");
            },
        },
    ].flat(),
});

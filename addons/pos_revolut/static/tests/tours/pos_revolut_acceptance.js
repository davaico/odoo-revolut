import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_manager_configuration", {
    steps: () => [
        {
            trigger: ".o_field_widget[name=payment_method_type] .o_select_menu_toggler",
            run: "click",
        },
        {
            trigger: ".o_field_selection_menu .dropdown-item:contains('Terminal')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=use_payment_terminal] .o_select_menu_toggler",
            run: "click",
        },
        {
            trigger: ".o_field_selection_menu .dropdown-item:contains('Revolut')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=revolut_location_id] input",
            run: "edit 123e4567-e89b-12d3-a456-426614174000",
        },
        {
            trigger: ".o_field_widget[name=revolut_terminal_id] input",
            run: "edit 0e53f673-7705-473a-a263-89a3e7647c3d",
        },
        {
            trigger: ".o_field_widget[name=revolut_fulfilment_type] .o_select_menu_toggler",
            run: "click",
        },
        {
            trigger: ".o_field_selection_menu .dropdown-item:contains('Eat In')",
            run: "click",
        },
        {
            trigger: ".o_field_widget[name=revolut_secret_reference] input",
            run: "edit ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: "button[name=action_revolut_check_connection]",
            run: "click",
        },
        {
            trigger: '.o_notification_content:contains("Counter 1 is online.")',
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_retail_starts", {
    steps: () => [
        ...Chrome.startPoS(),
        {
            trigger: ".product-screen .product-list",
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_starts", {
    steps: () => [
        ...Chrome.startPoS(),
        {
            trigger: ".floor-screen .floor-map",
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_guards", {
    steps: () => [
        {
            content: "Open Restaurant PoS when the register is closed",
            trigger: ".screen-login .btn.open-register-btn, .floor-screen .floor-map",
            run() {
                if (this.anchor.matches(".screen-login .btn.open-register-btn")) {
                    this.anchor.click();
                }
            },
        },
        { trigger: ".floor-screen .floor-map" },
        {
            content: "A settled Revolut line cannot move into another order",
            trigger: ".floor-screen .floor-map",
            async run() {
                const pos = window.posmodel;
                const method = pos.models["pos.payment.method"].find(
                    (item) => item.use_payment_terminal === "revolut"
                );
                if (!method) {
                    throw new Error("Revolut method was not loaded in Restaurant POS");
                }
                const source = pos.createNewOrder();
                const destination = pos.createNewOrder();
                const payment = source.addPaymentline(method);
                if (!payment.status) {
                    throw new Error("Could not add a Revolut line to the test order");
                }
                payment.data.setPaymentStatus("done");
                const merged = await pos.mergeOrders(source, destination);
                if (merged !== false || !source.getPaymentlineByUuid(payment.data.uuid)) {
                    throw new Error("Restaurant merge moved a protected Revolut payment");
                }
                window.revolutRestaurantGuardOrders = { source, destination };
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
        {
            content: "A transfer into another order is also guarded",
            trigger: ".floor-screen .floor-map",
            async run() {
                const { source, destination } = window.revolutRestaurantGuardOrders;
                const transferred = await window.posmodel.transferOrder(
                    source.uuid, null, destination
                );
                if (transferred !== false || !source.payment_ids.length) {
                    throw new Error("Restaurant transfer moved a protected Revolut payment");
                }
                delete window.revolutRestaurantGuardOrders;
            },
        },
        { trigger: ".modal:contains('Revolut payment attached to this order')" },
        Dialog.confirm(),
    ],
});

registry.category("web_tour.tours").add("pos_revolut_verified_checkout", {
    steps: () =>
        [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Revolut"),
            {
                content: "Revolut payment is waiting for the customer",
                trigger: ".payment-screen .electronic_status:contains('Waiting for card')",
            },
            {
                content: "The Revolut force-done action remains guarded",
                trigger: ".payment-screen .send_force_done",
                run: "click",
            },
            {
                trigger: ".modal:contains('Revolut verification required')",
            },
            Dialog.confirm(),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Revolut", "12.34"),
            ReceiptScreen.totalAmountContains("12.34"),
        ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_split_cash_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.enterPaymentLineAmount("Cash", "8"),
        PaymentScreen.selectedPaymentlineHas("Cash", "8.00"),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "8.00"),
        ReceiptScreen.paymentLineContains("Revolut", "4.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_reload_late_success", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
        Dialog.confirm(),
        refresh(),
        {
            content: "Lose volatile payment state after reloading the POS",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const line = window.posmodel.getOrder().payment_ids.find(
                    (payment) => payment.payment_method_id.use_payment_terminal === "revolut"
                );
                line.uiState.revolutStarted = false;
                line.uiState.revolutSnapshot = false;
                line.uiState.revolutOperationId = false;
                const order = window.posmodel.getOrder();
                order.removePaymentline(line);
                if (!order.getPaymentlineByUuid(line.uuid)) {
                    throw new Error("Unresolved Revolut line was removable after reload");
                }
            },
        },
        {
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run: "click",
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_pending_cancel", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            trigger: ".payment-screen .electronic_status:contains('Waiting for card')",
        },
        {
            trigger: ".payment-screen .send_payment_cancel",
            run: "click",
        },
        {
            trigger: ".modal:contains('The Revolut payment was cancelled')",
        },
        Dialog.confirm(),
        {
            content: "Cancelled payment remains unpaid and can be retried",
            trigger: ".payment-screen .send_payment_request",
        },
    ].flat(),
});

function revolutCheckoutSteps() {
    return [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_declined_retry", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".modal:contains('The Revolut payment was declined')" },
        Dialog.confirm(),
        { trigger: ".payment-screen .electronic_status:contains('Payment declined')" },
        {
            content: "A double click on Retry sends only one replacement charge",
            trigger: ".payment-screen .send_payment_request:contains('Retry')",
            run() {
                this.anchor.click();
                this.anchor.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_failed", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".modal:contains('The Revolut payment failed')" },
        Dialog.confirm(),
        { trigger: ".payment-screen .electronic_status:contains('Payment failed')" },
        { trigger: ".payment-screen .send_payment_request:contains('Retry')" },
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_interrupted", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
        Dialog.confirm(),
        {
            content: "An uncertain payment can only be checked, never charged again",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run: "click",
        },
        { trigger: ".payment-screen .electronic_status:contains('Communication interrupted')" },
        PaymentScreen.clickNumpad("9"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        { trigger: ".payment-screen .send_payment_request:contains('Check status')" },
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_timed_out", {
    steps: () => {
        let originalNow;
        return [
            ...revolutCheckoutSteps(),
            {
                content: "Advance the browser clock beyond the 60-second foreground limit",
                trigger: ".payment-screen .electronic_status:contains('Waiting for card')",
                run() {
                    originalNow = Date.now;
                    Date.now = () => originalNow() + 60001;
                },
            },
            {
                trigger: ".modal:contains('60-second Revolut waiting limit expired')",
                run() {
                    Date.now = originalNow;
                },
            },
            Dialog.confirm(),
            { trigger: ".payment-screen .electronic_status:contains('Waiting limit expired')" },
            { trigger: ".payment-screen .send_payment_request:contains('Check status')" },
            PaymentScreen.clickNumpad("9"),
            PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
        ].flat();
    },
});

registry.category("web_tour.tours").add("pos_revolut_processing", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        PaymentScreen.clickNumpad("9"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
        PaymentScreen.clickCancelButton(),
        { trigger: ".modal:contains('processing and cannot be cancelled')" },
        Dialog.confirm(),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_cancel_race", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        PaymentScreen.clickCancelButton(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
    ].flat(),
});

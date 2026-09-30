import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const PAYMENT_REFERENCE = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const REFUND_REFERENCE = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";

function receiptContainsReference(reference) {
    return { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${reference}')` };
}

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

registry.category("web_tour.tours").add("pos_revolut_other_tenders_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "12.34"),
        ReceiptScreen.clickNextOrder(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Bank"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Bank", "12.34"),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_starts", {
    steps: () => [
        ...Chrome.startPoS(),
        {
            trigger: ".floor-screen .floor-map",
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_restaurant_checkout", {
    steps: () => [
        Chrome.startPoS(),
        {
            content: "Open the Restaurant table",
            trigger: ".floor-map .table:has(.label:contains('1')):not(.syncing)",
            run: "click",
        },
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
    ].flat(),
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
            ReceiptScreen.isShown().map((step) => ({ ...step, timeout: 20000 })),
            ReceiptScreen.paymentLineContains("Revolut", "12.34"),
            receiptContainsReference(PAYMENT_REFERENCE),
            ReceiptScreen.totalAmountContains("12.34"),
            {
                content: "Merchant credentials and card data are absent from POS models",
                trigger: ".receipt-screen",
                run() {
                    const pos = window.posmodel;
                    const method = pos.models["pos.payment.method"].find(
                        (item) => item.use_payment_terminal === "revolut"
                    );
                    if (!method) {
                        throw new Error("Revolut method is missing from POS models");
                    }
                    for (const field of [
                        "revolut_secret_reference", "revolut_location_id",
                        "revolut_terminal_id", "revolut_environment",
                    ]) {
                        if (method[field]) {
                            throw new Error(`Server-only Revolut field reached POS: ${field}`);
                        }
                    }
                    const payment = pos.getOrder().payment_ids.find(
                        (item) => item.payment_method_id === method
                    );
                    if (!payment) {
                        throw new Error("Verified Revolut payment is missing from the receipt order");
                    }
                    const canaries = [
                        "CARDHOLDER_CANARY_TICKET_11", "PAN_CANARY_TICKET_11",
                        "test-only-not-a-credential",
                    ];
                    const seen = new WeakSet();
                    let visited = 0;
                    function checkBrowserData(value, path) {
                        if (typeof value === "string" && canaries.some((item) => value.includes(item))) {
                            throw new Error(`Sensitive value reached POS data at ${path}`);
                        }
                        if (!value || typeof value !== "object" || seen.has(value)) {
                            return;
                        }
                        if (++visited > 5000) {
                            throw new Error("POS data scan exceeded its safety limit");
                        }
                        seen.add(value);
                        for (const field of Object.keys(value)) {
                            const child = value[field];
                            if (/cardholder|card_number|^pan$|cvv|secret/i.test(field) && child) {
                                throw new Error(`Sensitive field reached POS data at ${path}.${field}`);
                            }
                            // Odoo relation fields point to reactive records, not POS payload data.
                            if (/_ids?$/.test(field)) {
                                if (typeof child === "string") {
                                    checkBrowserData(child, `${path}.${field}`);
                                }
                                continue;
                            }
                            if (typeof child !== "object" || !child ||
                                    Array.isArray(child) || Object.getPrototypeOf(child) === Object.prototype) {
                                checkBrowserData(child, `${path}.${field}`);
                            }
                        }
                    }
                    checkBrowserData(method.data || method, "payment method");
                    checkBrowserData(payment.data || payment, "payment");
                    checkBrowserData(payment.uiState.revolutSnapshot, "payment RPC snapshot");
                    checkBrowserData(pos.getOrder().data || pos.getOrder(), "order");
                },
            },
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

registry.category("web_tour.tours").add("pos_revolut_processing_multiple_cards", {
    steps: () => {
        let identity;
        return [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            {
                content: "Prepare a partial card line before sending its amount to the terminal",
                trigger: ".payment-screen",
                run() {
                    const pos = window.posmodel;
                    const order = pos.getOrder();
                    const method = pos.config.payment_method_ids.find((item) => item.name === "Revolut");
                    const result = order.addPaymentline(method);
                    if (!result.status) {
                        throw new Error("Could not prepare the partial Revolut line");
                    }
                    identity = { orderUuid: order.uuid, lineUuid: result.data.uuid };
                },
            },
            PaymentScreen.enterPaymentLineAmount("Revolut", "12.33"),
            PaymentScreen.selectedPaymentlineHas("Revolut", "12.33"),
            { trigger: ".payment-screen .send_payment_request:contains('Send')", run: "click" },
            { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
            {
                content: "A captured partial card line leaves exactly one penny due on the unchanged order",
                trigger: ".payment-screen .electronic_status:contains('Payment Successful')",
                run() {
                    const order = window.posmodel.getOrder();
                    const line = order.getPaymentlineByUuid(identity.lineUuid);
                    if (order.uuid !== identity.orderUuid || order.isPaid() ||
                        order.currency.round(order.remainingDue) !== 0.01 || order.payment_ids.length !== 1 ||
                        !line.isDone() || line.amount !== 12.33 || !line.transaction_id ||
                        line.uiState.revolutSnapshot.state !== "verified") {
                        throw new Error("Processing incorrectly settled or changed the partial card order");
                    }
                    identity.paymentId = line.transaction_id;
                },
            },
            PaymentScreen.clickPaymentMethod("Revolut"),
            { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
            ReceiptScreen.isShown(),
            {
                content: "Both card lines complete automatically with their own verified references",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.getOrder();
                    const first = order.getPaymentlineByUuid(identity.lineUuid);
                    const second = order.payment_ids.find((item) => item.uuid !== identity.lineUuid);
                    if (order.uuid !== identity.orderUuid || order.payment_ids.length !== 2 ||
                        !order.isPaid() || !first.isDone() || !second?.isDone() ||
                        first.transaction_id !== identity.paymentId || first.amount !== 12.33 ||
                        second.amount !== 0.01 || !second.transaction_id ||
                        second.transaction_id === first.transaction_id ||
                        second.uiState.revolutSnapshot.state !== "verified") {
                        throw new Error("Multiple card checkout lost a verified allocation or required manual recovery");
                    }
                },
            },
        ].flat();
    },
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
        receiptContainsReference(PAYMENT_REFERENCE),
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
                async run() {
                    const line = window.posmodel.getOrder().payment_ids.find(
                        (item) => item.payment_method_id.use_payment_terminal === "revolut"
                    );
                    const deadline = Date.now() + 10000;
                    while (line.uiState.revolutSnapshot?.provider_state !== "authentication_challenge" &&
                            Date.now() < deadline) {
                        await new Promise((resolve) => setTimeout(resolve, 100));
                    }
                    if (line.uiState.revolutSnapshot?.provider_state !== "authentication_challenge" ||
                        line.isDone() || !line.uiState.revolutSnapshot.payment_id) {
                        throw new Error("The timeout regression did not observe a guarded underlying payment");
                    }
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

registry.category("web_tour.tours").add("pos_revolut_malformed_processing", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".modal:contains('The Revolut result is unresolved')" },
        Dialog.confirm(),
        { trigger: ".payment-screen .send_payment_request:contains('Check status')", run: "click" },
        { trigger: ".payment-screen .electronic_status:contains('Payment unresolved')" },
        PaymentScreen.clickNumpad("9"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        { trigger: ".payment-screen .send_payment_request:contains('Check status')" },
        {
            content: "Malformed processing evidence retains the unpaid line and known payment reference",
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.getOrder();
                const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                if (order.isPaid() || !line || line.amount !== 12.34 || line.isDone() ||
                    line.transaction_id || line.uiState.revolutSnapshot.state !== "unresolved" ||
                    !line.uiState.revolutSnapshot.payment_id || line.uiState.revolutSnapshot.retry_safe) {
                    throw new Error("Malformed payment evidence released a financial guard");
                }
            },
        },
    ].flat(),
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
        receiptContainsReference(PAYMENT_REFERENCE),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_full_refund", {
    steps: () => [
        ...revolutCheckoutSteps(),
        ReceiptScreen.isShown(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-sources .revolut-refund-source:checked" },
        {
            trigger: ".revolut-refund-amount",
            run() {
                if (Number(this.anchor.value) !== 12.34) {
                    throw new Error(`Expected a 12.34 refund allocation, found ${this.anchor.value}`);
                }
            },
        },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".payment-screen .electronic_status:contains('Refund in process')" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        receiptContainsReference(REFUND_REFERENCE),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_refund_reload", {
    steps: () => [
        ...revolutCheckoutSteps(),
        ReceiptScreen.isShown(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".modal:contains('The refund may have succeeded')" },
        Dialog.confirm(),
        refresh(),
        {
            content: "Fail the first original-sale read after refund reload",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const pos = window.posmodel;
                const order = pos.getOrder();
                const payment = order.payment_ids.find((line) =>
                    line.payment_method_id.use_payment_terminal === "revolut"
                );
                const missingOriginal = order.lines.find((line) =>
                    !line.refunded_orderline_id && line.raw.refunded_orderline_id
                );
                if (!payment || !missingOriginal) {
                    throw new Error("Refund or missing original sale was not restored after reload");
                }
                window.revolutRefundRecovery = { orderUuid: order.uuid, lineUuid: payment.uuid };
                payment.uiState.revolutStarted = true;
                payment.uiState.revolutSnapshot = false;
                payment.uiState.revolutOperationId = false;
                const read = pos.data.read.bind(pos.data);
                let failed = false;
                pos.data.read = async (model, ids, ...args) => {
                    if (!failed && model === "pos.order.line" &&
                        ids.includes(missingOriginal.raw.refunded_orderline_id)) {
                        failed = true;
                        throw new Error("Simulated original-sale read failure");
                    }
                    return read(model, ids, ...args);
                };
            },
        },
        { trigger: ".payment-screen .send_payment_request:contains('Check status')", run: "click" },
        { trigger: ".modal:contains('The refund may have succeeded')" },
        Dialog.confirm(),
        {
            content: "Uncertain refund keeps its identity and financial guards",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const order = window.posmodel.getOrder();
                const { orderUuid, lineUuid } = window.revolutRefundRecovery;
                const payment = order.getPaymentlineByUuid(lineUuid);
                if (order.uuid !== orderUuid || !payment ||
                    payment.uiState.revolutLocalOutcome !== "interrupted" ||
                    order.removePaymentline(payment) !== false ||
                    !order.getPaymentlineByUuid(lineUuid)) {
                    throw new Error("Uncertain refund was lost or became removable");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Cash"),
        { trigger: ".modal:contains('Reconcile the unresolved Revolut payment')" },
        Dialog.confirm(),
        PaymentScreen.clickValidate(),
        { trigger: ".modal:contains('Revolut reconciliation required')" },
        Dialog.confirm(),
        {
            content: "Repeated status checks cannot dispatch another refund",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                this.anchor.click();
                this.anchor.click();
            },
        },
        { trigger: ".payment-screen .electronic_status:contains('Refund in process')" },
        { trigger: ".revolut-refund-reference:contains('6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf')" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        receiptContainsReference(REFUND_REFERENCE),
        {
            content: "The recovered refund retained the return and payment identities",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.getOrder();
                const { orderUuid, lineUuid } = window.revolutRefundRecovery;
                if (order.uuid !== orderUuid || !order.getPaymentlineByUuid(lineUuid)) {
                    throw new Error("Recovered refund changed its return or payment identity");
                }
                delete window.revolutRefundRecovery;
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_refund_failed", {
    steps: () => [
        ...revolutCheckoutSteps(),
        ReceiptScreen.isShown(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".modal:contains('The Revolut refund failed')" },
        Dialog.confirm(),
        { trigger: ".payment-screen .electronic_status:contains('Refund failed')" },
        { trigger: ".revolut-refund-reference:contains('6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf')" },
        PaymentScreen.clickNumpad("9"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "-12.34"),
        PaymentScreen.clickValidate(),
        { trigger: ".modal:contains('Revolut reconciliation required')" },
        Dialog.confirm(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.selectedPaymentlineHas("Cash", "-12.34"),
        PaymentScreen.clickValidate(),
        { trigger: ".modal:contains('Revolut reconciliation required')" },
        Dialog.confirm(),
    ].flat(),
});

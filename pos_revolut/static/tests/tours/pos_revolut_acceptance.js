import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";
import { reopenRevolutOrder } from "./recovery_order_util";

const PAYMENT_REFERENCE = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const REFUND_REFERENCE = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";

registry.category("web_tour.tours").add("pos_revolut_environment_blocked", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            trigger: ".modal:contains('Revolut test environment'):contains('Production Revolut access is disabled')",
            run() {
                const text = this.anchor.textContent;
                if (!text.includes("sandbox terminal") || !text.includes("production environment") ||
                    /ODOO_REVOLUT_SECRET_|Bearer|test-only-not-a-credential/.test(text)) {
                    throw new Error("Deployment feedback must explain safe testing without credentials");
                }
                if (document.querySelector(".receipt-screen")) {
                    throw new Error("A restricted production payment cannot complete checkout");
                }
            },
        },
        Dialog.confirm(),
        { trigger: ".payment-screen" },
    ].flat(),
});

function focusPaymentControl(selector) {
    return {
        content: "Payment controls are keyboard reachable with a visible focus indicator",
        trigger: selector,
        async run(helpers) {
            this.anchor.focus();
            // Retry is the last control; Hoot does not wrap past the last tab stop.
            await helpers.press("Shift+Tab");
            await helpers.press("Tab");
            const style = getComputedStyle(this.anchor);
            if (document.activeElement !== this.anchor || this.anchor.tabIndex < 0 ||
                style.outlineStyle !== "solid" || parseFloat(style.outlineWidth) < 2) {
                throw new Error(`Payment control lacks keyboard focus or a visible outline: ${this.anchor.className}; active=${document.activeElement.className}; outline=${style.outlineStyle} ${style.outlineWidth}`);
            }
        },
    };
}

function receiptContainsReference(reference) {
    return {
        trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${reference}')`,
        run() {
            if (document.querySelector(".revolut-receipt-download, .revolut-receipt-selection")) {
                throw new Error("Retired Revolut document controls remain on checkout");
            }
            const receipt = document.querySelector(".receipt-screen .pos-receipt");
            if (receipt.textContent.split(reference).length !== 2) {
                throw new Error("Native receipt must contain its Revolut reference exactly once");
            }
        },
    };
}

registry.category("web_tour.tours").add("pos_revolut_manager_configuration", {
    steps: () => [
        {
            trigger: ".o_field_widget[name=payment_method_type] select",
            run: 'selectByLabel Terminal',
        },
        {
            trigger: ".o_field_widget[name=use_payment_terminal] select",
            run: 'selectByLabel Revolut',
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
            trigger: ".o_field_widget[name=revolut_fulfilment_type] select",
            run: 'selectByLabel Eat In',
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
                        if (method[field] || method.raw[field]) {
                            throw new Error(`Server-only Revolut field reached POS: ${field}`);
                        }
                    }
                    const payment = pos.get_order().payment_ids.find(
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
                    for (const [name, record] of [
                        ["payment method", method], ["payment", payment], ["order", pos.get_order()],
                    ]) {
                        // Native 18 retains the original loader payload in raw,
                        // including unknown fields that serialize() can omit.
                        // Inspect both boundaries, without treating model-field
                        // schema definitions as customer payment data.
                        checkBrowserData(record.raw, `${name} loader payload`);
                        checkBrowserData(record.serialize(), `${name} serialized payload`);
                    }
                    checkBrowserData(payment.uiState.revolutSnapshot, "payment RPC snapshot");
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
        ReceiptScreen.receiptAmountTotalIs("12.34"),
        {
            content: "The exact split balance produces no rounding adjustment or change",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.get_order();
                if (order.get_due() !== 0 || order.get_change() !== 0 ||
                    document.querySelector(".receipt-rounding")) {
                    throw new Error("Cash-first split rounded the card amount or left an inconsistent balance");
                }
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_rounded_split_cash_checkout", {
    steps: () => {
        let orderUuid;
        return [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.enterPaymentLineAmount("Cash", "8"),
            PaymentScreen.selectedPaymentlineHas("Cash", "8.00"),
            {
                content: "Keep the original order identity before sending the rounded card allocation",
                trigger: ".payment-screen",
                run() { orderUuid = window.posmodel.get_order().uuid; },
            },
            PaymentScreen.clickPaymentMethod("Revolut"),
            { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
            ReceiptScreen.isShown(),
            ReceiptScreen.receiptAmountTotalIs("12.34"),
            ReceiptScreen.receiptRoundingAmountIs("0.01"),
            ReceiptScreen.receiptToPayAmountIs("12.35"),
            ReceiptScreen.paymentLineContains("Cash", "8.00"),
            ReceiptScreen.paymentLineContains("Revolut", "4.35"),
            {
                content: "The rounded split completed the same order with no remaining balance or change",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.get_order();
                    if (order.uuid !== orderUuid || !order.is_paid() ||
                        order.getTotalDue() !== 12.35 || order.get_due() !== 0 ||
                        order.get_change() !== 0 || order.taxTotals.order_remaining !== 0) {
                        throw new Error("Rounded split checkout changed identity or left an inconsistent native balance");
                    }
                },
            },
        ].flat();
    },
});

registry.category("web_tour.tours").add("pos_revolut_cash_correction_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.enterPaymentLineAmount("Cash", "5"),
        PaymentScreen.selectedPaymentlineHas("Cash", "5.00"),
        { trigger: ".revolut-choose-amount", run: "click" },
        PaymentScreen.enterPaymentLineAmount("Revolut", "4"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "4.00"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        { trigger: ".payment-screen .electronic_status:contains('Payment Successful')" },
        PaymentScreen.clickPaymentline("Cash", "5.00"),
        PaymentScreen.enterPaymentLineAmount("Cash", "3"),
        PaymentScreen.selectedPaymentlineHas("Cash", "3.00"),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "3.00"),
        ReceiptScreen.paymentLineContains("Revolut", "4.00"),
        ReceiptScreen.paymentLineContains("Revolut", "5.34"),
        ReceiptScreen.receiptAmountTotalIs("12.34"),
    ].flat(),
});

for (const rounded of [false, true]) {
    registry.category("web_tour.tours").add(rounded
        ? "pos_revolut_rounded_card_cash_checkout" : "pos_revolut_card_cash_checkout", {
        steps: () => {
            let orderUuid;
            const cardAmount = rounded ? "4.32" : "4.34";
            return [
                Chrome.startPoS(),
                ProductScreen.addOrderline("Desk Pad"),
                ProductScreen.clickPayButton(),
                { trigger: ".revolut-choose-amount", run: "click" },
                PaymentScreen.enterPaymentLineAmount("Revolut", cardAmount),
                PaymentScreen.selectedPaymentlineHas("Revolut", cardAmount),
                {
                    content: "Keep the native order identity before the partial card collection",
                    trigger: ".payment-screen .send_payment_request",
                    run() {
                        orderUuid = window.posmodel.get_order().uuid;
                        this.anchor.click();
                    },
                },
                { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
                { trigger: ".payment-screen .electronic_status:contains('Payment Successful')" },
                PaymentScreen.clickPaymentMethod("Cash"),
                PaymentScreen.selectedPaymentlineHas("Cash", "8.00"),
                PaymentScreen.clickValidate(),
                ReceiptScreen.isShown(),
                ReceiptScreen.receiptAmountTotalIs("12.34"),
                ...(rounded ? [
                    ReceiptScreen.receiptRoundingAmountIs("-0.02"),
                    ReceiptScreen.receiptToPayAmountIs("12.32"),
                ] : []),
                ReceiptScreen.paymentLineContains("Revolut", cardAmount),
                ReceiptScreen.paymentLineContains("Cash", "8.00"),
                {
                    content: "The remaining Cash tender settles the original verified card sale",
                    trigger: ".receipt-screen",
                    run() {
                        const order = window.posmodel.get_order();
                        if (order.uuid !== orderUuid || !order.is_paid() ||
                            order.get_due() !== 0 || order.get_change() !== 0) {
                            throw new Error("Card-first Cash completion lost identity or financial balance");
                        }
                    },
                },
            ].flat();
        },
    });
}

registry.category("web_tour.tours").add("pos_revolut_processing_multiple_cards", {
    steps: () => {
        let identity;
        return [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            { trigger: ".revolut-choose-amount", run: "click" },
            {
                content: "Choosing an amount creates an editable line without sending a terminal request",
                trigger: ".payment-screen .send_payment_request:contains('Send')",
                run() {
                    const pos = window.posmodel;
                    const order = pos.get_order();
                    const line = order.payment_ids[0];
                    if (order.payment_ids.length !== 1 || line.payment_status !== "pending" ||
                        line.uiState.revolutSnapshot?.operation_id) {
                        throw new Error("Choosing the allocation dispatched a payment before amount entry");
                    }
                    identity = { orderUuid: order.uuid, lineUuid: line.uuid };
                    // Odoo 18's instructional tour pointer is an overlay, and
                    // its native number buffer ignores keys while overlays are
                    // present. Remove only that test marker before exercising
                    // the real keyboard path; retain dialogs and other guards.
                    for (const overlay of Object.values(pos.env.services.overlay.overlays)) {
                        if (overlay.component.name === "TourPointer") {
                            overlay.remove();
                        }
                    }
                },
            },
            ..."12.33".split("").map((key) => ({
                trigger: ".payment-screen",
                run: `press ${key}`,
            })),
            PaymentScreen.selectedPaymentlineHas("Revolut", "12.33"),
            {
                content: "Enter sends the allocation without reactivating Choose amount",
                trigger: ".payment-screen",
                run(helpers) {
                    if (!document.activeElement.matches(".send_payment_request")) {
                        throw new Error("Expected Send to have focus before Enter");
                    }
                    return helpers.press("Enter");
                },
            },
            { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
            {
                content: "A captured partial card line leaves exactly one penny due on the unchanged order",
                trigger: ".payment-screen .electronic_status:contains('Payment Successful')",
                run() {
                    const order = window.posmodel.get_order();
                    const line = order.get_paymentline_by_uuid(identity.lineUuid);
                    if (order.uuid !== identity.orderUuid || order.is_paid() ||
                        order.get_due() !== 0.01 || order.payment_ids.length !== 1 ||
                        !line.is_done() || line.amount !== 12.33 || !line.transaction_id ||
                        line.uiState.revolutSnapshot.state !== "verified") {
                        throw new Error("Processing incorrectly settled or changed the partial card order");
                    }
                    identity.paymentId = line.transaction_id;
                },
            },
            focusPaymentControl(".payment-screen .paymentmethod:contains('Revolut')"),
            { trigger: ".payment-screen", run: "press Enter" },
            { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
            ReceiptScreen.isShown(),
            {
                content: "Both card lines complete automatically with their own verified references",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.get_order();
                    const first = order.get_paymentline_by_uuid(identity.lineUuid);
                    const second = order.payment_ids.find((item) => item.uuid !== identity.lineUuid);
                    if (order.uuid !== identity.orderUuid || order.payment_ids.length !== 2 ||
                        !order.is_paid() || !first.is_done() || !second?.is_done() ||
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
        {
            trigger: ".payment-screen",
            run() { sessionStorage.setItem("revolutLateSuccessOrder", window.posmodel.get_order().uuid); },
        },
        refresh(),
        ...reopenRevolutOrder(() => sessionStorage.getItem("revolutLateSuccessOrder")),
        {
            content: "Lose volatile payment state after reloading the POS",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const line = window.posmodel.get_order().payment_ids.find(
                    (payment) => payment.payment_method_id.use_payment_terminal === "revolut"
                );
                line.uiState.revolutStarted = false;
                line.uiState.revolutSnapshot = false;
                line.uiState.revolutOperationId = false;
                const order = window.posmodel.get_order();
                order.remove_paymentline(line);
                if (!order.get_paymentline_by_uuid(line.uuid)) {
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
        {
            trigger: ".receipt-screen",
            run() {
                if (window.posmodel.get_order().uuid !== sessionStorage.getItem("revolutLateSuccessOrder")) {
                    throw new Error("Late success completed another native order");
                }
                sessionStorage.removeItem("revolutLateSuccessOrder");
            },
        },
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
        focusPaymentControl(".payment-screen .send_payment_cancel"),
        { trigger: ".payment-screen", run: "press Enter" },
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
        focusPaymentControl(".payment-screen .send_payment_request:contains('Retry')"),
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

for (const [outcome, feedback, status] of [
    ["terminal_unavailable", "The Revolut terminal is unavailable", "Terminal unavailable"],
    ["terminal_check_failed", "The Revolut terminal connection check failed", "Terminal connection check failed"],
]) {
    registry.category("web_tour.tours").add(`pos_revolut_${outcome}`, {
        steps: () => {
            let identity;
            return [
                ...revolutCheckoutSteps(),
                { trigger: `.modal:contains('${feedback}'):contains('No charge was sent')` },
                Dialog.confirm(),
                {
                    content: "An unavailable terminal leaves the same native order unpaid and safely retryable",
                    trigger: `.payment-screen .electronic_status:contains('${status}')`,
                    run() {
                        const order = window.posmodel.get_order();
                        const line = order.get_selected_paymentline();
                        const snapshot = line.uiState.revolutSnapshot;
                        if (order.is_paid() || line.is_done() || snapshot.state !== "failed" ||
                            snapshot.provider_state !== outcome || !snapshot.retry_safe ||
                            line.transaction_id || line.payment_ref_no) {
                            throw new Error("Terminal preflight failure did not retain truthful unpaid retry state");
                        }
                        identity = { orderUuid: order.uuid, lineUuid: line.uuid,
                            operationId: snapshot.operation_id };
                    },
                },
                focusPaymentControl(".payment-screen .send_payment_request:contains('Retry')"),
                { trigger: ".payment-screen", run: "press Enter" },
                { trigger: `.modal:contains('${feedback}'):contains('No charge was sent')` },
                Dialog.confirm(),
                {
                    content: "Keyboard Retry reconciles the previous attempt and preserves the unpaid line",
                    trigger: `.payment-screen .electronic_status:contains('${status}')`,
                    run() {
                        const pos = window.posmodel;
                        const order = pos.get_order();
                        const line = order.get_paymentline_by_uuid(identity.lineUuid);
                        const snapshot = line?.uiState.revolutSnapshot;
                        if (order.uuid !== identity.orderUuid || order.is_paid() ||
                            order.payment_ids.length !== 1 || !line || line.is_done() ||
                            snapshot?.operation_id === identity.operationId || snapshot?.state !== "failed" ||
                            snapshot?.provider_state !== outcome || !snapshot.retry_safe ||
                            pos.paymentTerminalInProgress || line.amount !== 12.34 ||
                            line.transaction_id || line.payment_ref_no) {
                            throw new Error("Keyboard Retry lost payment identity or retained a false terminal busy state");
                        }
                    },
                },
            ].flat();
        },
    });
}

registry.category("web_tour.tours").add("pos_revolut_interrupted", {
    steps: () => [
        ...revolutCheckoutSteps(),
        { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
        Dialog.confirm(),
        focusPaymentControl(".payment-screen .send_payment_request:contains('Check status')"),
        { trigger: ".payment-screen", run: "press Enter" },
        {
            content: "Repeated status checks explain the current uncertainty without sending another charge",
            trigger: ".modal:contains('Communication with Revolut was interrupted')",
        },
        Dialog.confirm(),
        { trigger: ".payment-screen .electronic_status:contains('Communication interrupted')" },
        PaymentScreen.clickNumpad("9"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        {
            content: "Unsuccessful removal continues to explain why the original uncertain payment stays protected",
            trigger: ".modal:contains('Communication with Revolut was interrupted')",
        },
        Dialog.confirm(),
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
                    const line = window.posmodel.get_order().payment_ids.find(
                        (item) => item.payment_method_id.use_payment_terminal === "revolut"
                    );
                    const deadline = Date.now() + 10000;
                    while (line.uiState.revolutSnapshot?.provider_state !== "authentication_challenge" &&
                            Date.now() < deadline) {
                        await new Promise((resolve) => setTimeout(resolve, 100));
                    }
                    if (line.uiState.revolutSnapshot?.provider_state !== "authentication_challenge" ||
                        line.is_done() || !line.uiState.revolutSnapshot.payment_id) {
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
        {
            content: "Repeated status checks explain that malformed payment evidence is still unresolved",
            trigger: ".modal:contains('The Revolut result is unresolved')",
        },
        Dialog.confirm(),
        { trigger: ".payment-screen .electronic_status:contains('Payment unresolved')" },
        PaymentScreen.clickNumpad("9"),
        PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        {
            content: "Unsuccessful removal explains the retained financial guard for malformed evidence",
            trigger: ".modal:contains('The Revolut result is unresolved')",
        },
        Dialog.confirm(),
        { trigger: ".payment-screen .send_payment_request:contains('Check status')" },
        {
            content: "Malformed processing evidence retains the unpaid line and known payment reference",
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.get_order();
                const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                if (order.is_paid() || !line || line.amount !== 12.34 || line.is_done() ||
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
        { trigger: ".payment-screen .send_payment_cancel", run: "click" },
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
        { trigger: ".payment-screen .send_payment_cancel", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        receiptContainsReference(PAYMENT_REFERENCE),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_full_refund", {
    steps: () => [
        ...revolutCheckoutSteps(),
        ReceiptScreen.isShown(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
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
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".modal:contains('The refund may have succeeded')" },
        Dialog.confirm(),
        {
            content: "Retain the saved uncertain return identity and discard cached original records",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                if (!Number.isInteger(order.id)) {
                    throw new Error("The uncertain refund's native return was not saved before reload");
                }
                sessionStorage.setItem("revolutRefundReloadOrder", order.uuid);
                pos.data._debouncedSync.cancel();
                pos.data.syncDataWithIndexedDB = () => {};
                await pos.data.resetIndexedDB();
            },
        },
        refresh(),
        ...reopenRevolutOrder(() => sessionStorage.getItem("revolutRefundReloadOrder")),
        {
            content: "Fail the first original-sale read after refund reload",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const pos = window.posmodel;
                const order = pos.get_order();
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
                const order = window.posmodel.get_order();
                const { orderUuid, lineUuid } = window.revolutRefundRecovery;
                const payment = order.get_paymentline_by_uuid(lineUuid);
                if (order.uuid !== orderUuid || !payment ||
                    payment.uiState.revolutLocalOutcome !== "interrupted" ||
                    order.remove_paymentline(payment) !== false ||
                    !order.get_paymentline_by_uuid(lineUuid)) {
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
                const order = window.posmodel.get_order();
                const { orderUuid, lineUuid } = window.revolutRefundRecovery;
                if (order.uuid !== orderUuid || !order.get_paymentline_by_uuid(lineUuid)) {
                    throw new Error("Recovered refund changed its return or payment identity");
                }
                delete window.revolutRefundRecovery;
                sessionStorage.removeItem("revolutRefundReloadOrder");
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_refund_failed", {
    steps: () => [
        ...revolutCheckoutSteps(),
        ReceiptScreen.isShown(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
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

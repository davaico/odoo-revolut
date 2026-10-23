import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

function resumeSteps({ external = true, split = false, checkStatus = false, completedReload = false } = {}) {
    return [
        ...(checkStatus ? [{ trigger: ".o_form_view button[name='action_check_status']", run: "click" }] : []),
        ...(external ? [
            { trigger: ".o_form_view button[name='action_open_native_completion']", run: "click" },
            { trigger: ".modal .o_data_cell[name='quantity']", run: "click" },
            { trigger: ".modal .o_field_widget[name='quantity'] input", run: "edit 1" },
            { trigger: ".modal button[name='action_prepare']", run: "click" },
            { trigger: ".o_form_view button[name='action_continue_external_native_return']", run: "click" },
        ] : [
            { trigger: ".o_form_view button[name='action_recover_return']", run: "click" },
        ]),
        PaymentScreen.isShown(),
        {
            trigger: ".payment-screen .electronic_status:contains('Refund Successful')",
            run() {
                const order = window.posmodel.get_order();
                sessionStorage.setItem("revolutManagerResume", JSON.stringify({
                    uuid: order.uuid, id: order.id, payments: order.payment_ids.map((line) => line.id),
                }));
            },
        },
        refresh(),
        {
            trigger: ".payment-screen .electronic_status:contains('Refund Successful')",
            run() {
                const order = window.posmodel.get_order();
                const before = JSON.parse(sessionStorage.getItem("revolutManagerResume"));
                if (order.uuid !== before.uuid || order.id !== before.id ||
                    JSON.stringify(order.payment_ids.map((line) => line.id)) !== JSON.stringify(before.payments)) {
                    throw new Error("Manager reload replaced the saved return or its existing reimbursement");
                }
            },
        },
        ...(split ? [
            {
                trigger: ".payment-screen",
                run() {
                    const order = window.posmodel.get_order();
                    if (order.get_due() !== -6.17 || order.payment_ids.length !== 1 ||
                            order.payment_ids[0].payment_method_id.is_cash_count) {
                        throw new Error("Recovered card refund must leave its manual Cash share outstanding");
                    }
                },
            },
            PaymentScreen.clickPaymentMethod("Cash"),
        ] : []),
        ...(completedReload ? [{
            content: "Preserve ordinary register navigation while consuming completed recovery",
            trigger: ".payment-screen",
            run() {
                const url = new URL(window.location.href);
                url.searchParams.append("resume_test", "first");
                url.searchParams.append("resume_test", "second");
                url.hash = "retained-register-fragment";
                window.history.replaceState({ resumeTest: "retained" }, "", url);
                sessionStorage.setItem("revolutManagerNavigation", JSON.stringify({
                    query: [...url.searchParams].filter(([name]) => name !== "revolut_return_uuid"),
                    path: url.pathname, length: window.history.length,
                }));
            },
        }] : []),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.totalAmountContains("-12.34"),
        ReceiptScreen.paymentLineContains("Revolut", split ? "-6.17" : "-12.34"),
        ...(split ? [ReceiptScreen.paymentLineContains("Cash", "-6.17")] : []),
        ...(completedReload ? [
            {
                trigger: ".receipt-screen",
                run() {
                    const url = new URL(window.location.href);
                    const before = JSON.parse(sessionStorage.getItem("revolutManagerNavigation"));
                    if (url.searchParams.has("revolut_return_uuid") ||
                            JSON.stringify([...url.searchParams]) !== JSON.stringify(before.query) ||
                            url.pathname !== before.path || url.hash !== "#retained-register-fragment" ||
                            window.history.state?.resumeTest !== "retained" || window.history.length !== before.length) {
                        throw new Error("Completed recovery must consume only its resume parameter and replace history in place");
                    }
                },
            },
            ReceiptScreen.clickNextOrder(),
            { trigger: ".product-screen" },
            refresh(),
            {
                content: "Reload after completing recovery must not warn about the already-paid return",
                trigger: "body:has(.product-screen)",
                run() {
                    const warning = document.querySelector(".modal");
                    if (warning) {
                        throw new Error("Completed return recovery warned after reload: " + warning.textContent);
                    }
                    if (new URLSearchParams(window.location.search).has("revolut_return_uuid")) {
                        throw new Error("Completed return recovery left its one-time resume URL behind");
                    }
                },
            },
        ] : []),
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_external_resume", {
    steps: () => resumeSteps(),
});
registry.category("web_tour.tours").add("pos_revolut_external_resume_mixed", {
    steps: () => resumeSteps({ split: true }),
});
registry.category("web_tour.tours").add("pos_revolut_manager_restore_return", {
    steps: () => resumeSteps({ external: false }),
});

registry.category("web_tour.tours").add("pos_revolut_manager_resume_waiting", {
    steps: () => resumeSteps({ external: false, checkStatus: true }),
});
registry.category("web_tour.tours").add("pos_revolut_manager_resume_mixed", {
    steps: () => resumeSteps({ external: false, split: true, checkStatus: true }),
});

registry.category("web_tour.tours").add("pos_revolut_manager_completed_return_reload", {
    steps: () => resumeSteps({ external: false, checkStatus: true, completedReload: true }),
});

registry.category("web_tour.tours").add("pos_revolut_manager_completed_mixed_return_reload", {
    steps: () => resumeSteps({ external: false, split: true, checkStatus: true, completedReload: true }),
});

registry.category("web_tour.tours").add("pos_revolut_invalid_return_resume", {
    steps: () => [
        {
            content: "Recovery waits for native cashier login without consuming its navigation",
            trigger: ".screen-login .btn.open-register-btn",
            run() {
                if (document.querySelector(".modal") ||
                        !new URLSearchParams(window.location.search).has("revolut_return_uuid")) {
                    throw new Error("Return recovery bypassed native cashier login");
                }
            },
        },
        Chrome.startPoS(),
        {
            content: "An invalid recovery target keeps its explicit warning and does not consume navigation",
            trigger: ".modal:contains('Revolut return unavailable')",
            run() {
                if (!new URLSearchParams(window.location.search).has("revolut_return_uuid")) {
                    throw new Error("Invalid return recovery was silently consumed");
                }
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_external_historical_reprint", {
    steps: () => [
        Chrome.startPoS(),
        {
            trigger: ".product-screen",
            run() {
                window.externalReceiptCopies = [];
                window.print = (receipt) => {
                    const text = receipt.textContent;
                    const order = window.posmodel.models["pos.order"].getAll().find((item) =>
                        item.pos_reference === "Historical external return");
                    const reference = order.payment_ids.find((line) => line.transaction_id).transaction_id;
                    if (!receipt.classList.contains("pos-receipt") ||
                            !text.includes("Desk Pad") || !text.includes("-12.34") ||
                            !text.includes(reference) || text.split("Revolut refund:").length !== 2) {
                        throw new Error("Historical external receipt lost its amount, products or refund identity");
                    }
                    window.externalReceiptCopies.push(text);
                    document.body.dataset.externalReceiptCopies = window.externalReceiptCopies.length;
                };
            },
        },
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        { trigger: ".ticket-screen .order-row:contains('Historical external return')", run: "click" },
        { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
        { trigger: "body[data-external-receipt-copies='1'] .control-button:contains('Print Receipt'):not(:has(.fa-spin))" },
        { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
        {
            trigger: "body[data-external-receipt-copies='2'] .control-button:contains('Print Receipt'):not(:has(.fa-spin))",
            run() {
                if (window.externalReceiptCopies[0] !== window.externalReceiptCopies[1]) {
                    throw new Error("Repeated external return receipt changed its contents");
                }
            },
        },
    ].flat(),
});

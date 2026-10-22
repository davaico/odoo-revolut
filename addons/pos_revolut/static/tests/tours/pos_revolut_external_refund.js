import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

function resumeSteps({ external = true, split = false } = {}) {
    return [
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
        ...(split ? [PaymentScreen.clickPaymentMethod("Cash")] : []),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.totalAmountContains("-12.34"),
        ReceiptScreen.paymentLineContains("Revolut", split ? "-6.17" : "-12.34"),
        ...(split ? [ReceiptScreen.paymentLineContains("Cash", "-6.17")] : []),
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

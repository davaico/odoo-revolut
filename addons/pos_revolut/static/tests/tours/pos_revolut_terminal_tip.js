import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const IDENTITY_KEY = "revolutTerminalTipIdentity";
const PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";

registry.category("web_tour.tours").add("pos_revolut_tipped_processing_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        // No dialog acknowledgement, manual Check status or Validate step:
        // a warning during authorisation prevents this tour reaching receipt.
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "14.34"),
        { trigger: ".receipt-screen .receipt-total:contains('14.34')" },
        { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${PAYMENT_ID}')` },
    ].flat(),
});

function assertWaiting() {
    const order = window.posmodel.getOrder();
    const line = order.payment_ids.find((payment) => payment.payment_method_id.use_payment_terminal === "revolut");
    if (!line?.uiState.revolutSnapshot?.awaiting_tip_details || line.isDone() ||
        order.state !== "draft" || order.priceIncl !== 12.34 || line.amount !== 12.34 ||
        order.lines.some((item) => item.product_id === order.config.tip_product_id)) {
        throw new Error("Captured payment completed or projected an unproven tip before the report");
    }
    sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({
        orderUuid: order.uuid, lineUuid: line.uuid,
        operationId: line.uiState.revolutSnapshot.operation_id,
    }));
}

registry.category("web_tour.tours").add("pos_revolut_terminal_tip_report_reload", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Captured gross waits for separately authenticated terminal tip details",
            trigger: ".payment-screen .electronic_status:contains('Payment received'):contains('verifying payment details')",
            run() { assertWaiting(); },
        },
        { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
        Dialog.confirm(),
        {
            content: "The original captured payment remains unpaid and reserved after report interruption",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() { assertWaiting(); },
        },
        refresh(),
        {
            content: "Reload recovers the same reserved payment without creating another charge",
            trigger: ".pos",
            async run() {
                const saved = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                const order = window.posmodel.getOrder();
                const line = order.getPaymentlineByUuid(saved.lineUuid);
                if (order.uuid !== saved.orderUuid || !line || line.isDone() || line.amount !== 12.34) {
                    throw new Error(`Reload replaced the captured payment or prematurely completed it: ${JSON.stringify({
                        saved, order: order.uuid, screen: window.posmodel.getScreen?.(),
                        payments: order.payment_ids.map((item) => ({uuid: item.uuid, amount: item.amount,
                            status: item.getPaymentStatus(), uiState: item.uiState})),
                    })}`);
                }
                const check = document.querySelector(".payment-screen .send_payment_request");
                if (!check?.textContent.includes("Check status")) {
                    throw new Error(`Reload cannot resume the captured payment: ${JSON.stringify({
                        screen: window.posmodel.getScreen?.(), order: order.uuid,
                        status: line.getPaymentStatus(), uiState: line.uiState,
                        buttons: [...document.querySelectorAll(".send_payment_request")].map((item) => item.textContent),
                    })}`);
                }
                check.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "14.34"),
        {
            content: "Native success banner separates base and terminal tip",
            trigger: ".receipt-screen .o_payment_successful:contains('12.34'):contains('2.00 tip')",
        },
        {
            content: "The printable native receipt totals the captured gross",
            trigger: ".receipt-screen .receipt-total:contains('14.34')",
        },
        { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${PAYMENT_ID}')` },
        {
            content: "Authenticated tip and gross tender are projected exactly once before native checkout",
            trigger: ".receipt-screen",
            run() {
                const saved = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                const order = window.posmodel.getOrder();
                const line = order.getPaymentlineByUuid(saved.lineUuid);
                const tips = order.lines.filter((item) => item.product_id === order.config.tip_product_id);
                if (order.uuid !== saved.orderUuid || !line?.isDone() || line.amount !== 14.34 ||
                    line.transaction_id !== PAYMENT_ID || line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.uiState.revolutSnapshot.operation_id !== saved.operationId ||
                    order.priceIncl !== 14.34 || tips.length !== 1 || tips[0].prices.total_included_currency !== 2) {
                    throw new Error("Verified checkout duplicated or omitted terminal tip/payment evidence");
                }
                sessionStorage.removeItem(IDENTITY_KEY);
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_global_rounded_tip_return", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Review the server's unrounded canonical base if required",
            trigger: ".modal:contains('Revolut cart needs correction'), .receipt-screen",
            run() {
                const confirm = document.querySelector(".modal .btn-primary");
                confirm?.click();
            },
        },
        {
            content: "Explicitly resume the reviewed rounded allocation",
            trigger: ".payment-screen .send_payment_request:contains('Resume'), .receipt-screen",
            run() {
                const resume = document.querySelector(".payment-screen .send_payment_request");
                resume?.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "10.03"),
        { trigger: ".receipt-screen .receipt-to-pay:contains('10.03'), .receipt-screen .receipt-total:contains('10.03')" },
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("10.03"),
        { trigger: ".ticket-screen .orderline:contains('Desk Pad')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        { trigger: ".ticket-screen .orderline:contains('Verified terminal tip')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        {
            content: "The new native return has not yet been saved",
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.getOrder();
                if (Number.isInteger(order.id) || order.lines.length !== 2 ||
                    order.lines.some((line) => line.qty !== -1 || !line.refunded_orderline_id)) {
                    throw new Error("The full original goods and tip were not selected into an unsaved return");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-sources .revolut-refund-source:checked" },
        {
            content: "Server-authorized components retain original rounding and exact collected tip",
            trigger: ".revolut-refund-confirm",
            run() {
                const base = Number(document.querySelector(".revolut-refund-amount").value);
                const tip = Number(document.querySelector(".revolut-refund-tip").value);
                if (base !== 10 || tip !== 0.03) {
                    throw new Error(`Expected frozen base10.00 plus tip0.03, received ${base} + ${tip}`);
                }
                this.anchor.click();
            },
        },
        {
            content: "Verified refund automatically completes native checkout with the exact frozen target",
            trigger: ".modal .modal-content, body:not(:has(.modal)) .payment-screen, .receipt-screen",
            async run() {
                const deadline = performance.now() + 8000;
                while (!document.querySelector(".receipt-screen") && performance.now() < deadline) {
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                const order = window.posmodel.getOrder();
                const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                if (!line?.isDone() || line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.amount !== -10.03 || order.priceIncl !== -10.03 || order.remainingDue !== 0 ||
                    !document.querySelector(".receipt-screen")) {
                    throw new Error(`Refund did not automatically checkout at its frozen native target: ${JSON.stringify({
                        total: order.priceIncl, rounded: order.roundedPriceIncl, due: order.remainingDue,
                        paid: order.amountPaid, isPaid: order.isPaid(), refundInProcess: order.isRefundInProcess(),
                        automatic: window.posmodel.config.auto_validate_terminal_payment,
                        dialog: document.querySelector(".modal")?.textContent,
                        payments: order.payment_ids.map((item) => ({amount: item.amount, status: item.payment_status,
                            snapshot: item.uiState.revolutSnapshot})),
                    })}`);
                }
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-10.03"),
        { trigger: ".receipt-screen .receipt-to-pay:contains('-10.03'), .receipt-screen .receipt-total:contains('-10.03')" },
        {
            content: "Verified return projects the exact original gross without rounding the tip again",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.getOrder();
                const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                if (!line?.isDone() || line.amount !== -10.03 || order.priceIncl !== -10.03 ||
                    line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.uiState.revolutSnapshot.return_total_minor !== 1003) {
                    throw new Error("Full return did not retain the server-verified gross target");
                }
            },
        },
    ].flat(),
});

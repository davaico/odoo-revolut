import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const IDENTITY_KEY = "revolutTerminalTipIdentity";
const PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";

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
            trigger: ".payment-screen .electronic_status:contains('Payment received'):contains('awaiting terminal tip details')",
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
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const saved = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                const order = window.posmodel.getOrder();
                const line = order.getPaymentlineByUuid(saved.lineUuid);
                if (order.uuid !== saved.orderUuid || !line || line.isDone() || line.amount !== 12.34) {
                    throw new Error("Reload replaced the captured payment or prematurely completed it");
                }
                this.anchor.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "14.34"),
        ReceiptScreen.totalAmountContains("14.34"),
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

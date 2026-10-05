import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const REFUND_REFERENCE = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const RECOVERY_KEY = "revolut-refund-server-recovery";

registry.category("web_tour.tours").add("pos_revolut_refund_server_recovery", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
        {
            content: "Leave the completed refund as an unfinished native return",
            trigger: ".payment-screen",
            run() {
                window.posmodel.config.auto_validate_terminal_payment = false;
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        {
            content: "Forget browser data after completion and retain only the recovery identities",
            trigger: ".payment-screen .electronic_status:contains('Refund Successful')",
            async run() {
                const pos = window.posmodel;
                const order = pos.getOrder();
                const payment = order.payment_ids.find((line) => line.amount < 0);
                if (!Number.isInteger(order.id) || !Number.isInteger(payment?.id) ||
                    payment.transaction_id !== REFUND_REFERENCE || order.state !== "draft") {
                    throw new Error("The return and selected allocation were not persisted before refunding");
                }
                sessionStorage.setItem(RECOVERY_KEY, JSON.stringify({
                    orderUuid: order.uuid, lineUuid: payment.uuid, orderId: order.id,
                }));
                // This affects only the disposable HttpCase browser. Disable
                // cache writers so it cannot repopulate after the reset.
                pos.data.debouncedSynchronizeLocalDataInIndexedDB.cancel();
                pos.data.synchronizeLocalDataInIndexedDB = async () => {};
                pos.data.synchronizeServerDataInIndexedDB = async () => {};
                await pos.data.resetIndexedDB();
            },
        },
        refresh(),
        {
            content: "Recover the native return from server data with its completed refund",
            trigger: ".pos-content",
            run() {
                const pos = window.posmodel;
                const saved = JSON.parse(sessionStorage.getItem(RECOVERY_KEY));
                const order = pos.models["pos.order"].getBy("uuid", saved.orderUuid);
                const payment = order?.getPaymentlineByUuid(saved.lineUuid);
                if (!order || order.id !== saved.orderId || !payment ||
                    payment.getPaymentStatus() !== "done" ||
                    payment.transaction_id !== REFUND_REFERENCE ||
                    payment.payment_ref_no !== REFUND_REFERENCE ||
                    payment.uiState.revolutSnapshot?.state !== "verified") {
                    throw new Error("Completed refund evidence was not restored from the persisted return");
                }
                pos.setOrder(order);
                order.selectPaymentline(payment);
                pos.navigate("PaymentScreen", { orderUuid: order.uuid });
            },
        },
        { trigger: ".payment-screen .electronic_status:contains('Refund Successful')" },
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        {
            content: "The normal return receipt contains the existing refund exactly once",
            trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${REFUND_REFERENCE}')`,
            run() {
                const receipt = document.querySelector(".receipt-screen .pos-receipt");
                if (receipt.textContent.split(REFUND_REFERENCE).length !== 2) {
                    throw new Error("Refund reference was lost or duplicated on the recovered receipt");
                }
                sessionStorage.removeItem(RECOVERY_KEY);
            },
        },
    ].flat(),
});

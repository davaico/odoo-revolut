import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

const REFUND_ID = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const SAVED_RETURN = "revolut-closed-original-return";

function openHistoricalReturn() {
    return [
        Chrome.startPoS(),
        {
            trigger: ".product-screen",
            run() {
                if (window.posmodel.models["pos.order"].some((order) =>
                    order.pos_reference === "Historical native Revolut sale")) {
                    throw new Error("The closed-session original unexpectedly came from the startup cache");
                }
            },
        },
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrder("Historical native Revolut sale"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
    ].flat();
}

function finishReturn() {
    return [
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-amount", run() {
            if (Number(this.anchor.value) !== 12.34) {
                throw new Error("Historical original lost its captured refundable balance");
            }
        } },
        { trigger: ".revolut-refund-confirm", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        ReceiptScreen.totalAmountContains("-12.34"),
        {
            trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${REFUND_ID}')`,
            run() {
                const receipt = document.querySelector(".receipt-screen .pos-receipt");
                if (receipt.textContent.split(REFUND_ID).length !== 2) {
                    throw new Error("Native return receipt lost or duplicated the historical refund reference");
                }
                sessionStorage.removeItem(SAVED_RETURN);
            },
        },
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_closed_original_refund", {
    steps: () => [openHistoricalReturn(), finishReturn()].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_unavailable_original_refund", {
    steps: () => [
        openHistoricalReturn(),
        {
            content: "Persist the native return and lose every local original record",
            trigger: ".payment-screen",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                await pos.syncAllOrders({ orders: [order], force: true, throw: true });
                const saved = pos.models["pos.order"].getBy("uuid", order.uuid);
                if (!Number.isInteger(saved?.id) || !saved.lines[0].refunded_orderline_id) {
                    throw new Error("Native return did not persist its original association");
                }
                sessionStorage.setItem(SAVED_RETURN, JSON.stringify({
                    orderUuid: saved.uuid, orderId: saved.id,
                    originalLineId: saved.lines[0].refunded_orderline_id.id,
                }));
                pos.data._debouncedSync.cancel();
                pos.data.syncDataWithIndexedDB = () => {};
                await pos.data.resetIndexedDB();
            },
        },
        refresh(),
        {
            content: "Recover the draft through native loading with only its saved original reference",
            trigger: ".pos-content",
            run() {
                const pos = window.posmodel;
                const saved = JSON.parse(sessionStorage.getItem(SAVED_RETURN));
                const order = pos.models["pos.order"].getBy("uuid", saved.orderUuid);
                if (!order || order.id !== saved.orderId ||
                    order.lines[0].raw.refunded_orderline_id !== saved.originalLineId ||
                    order.lines[0].refunded_orderline_id) {
                    throw new Error("Saved return did not exercise native missing-original serialization");
                }
                if (!order._isRefundOrder()) {
                    throw new Error("Native saved return lost refund identity while its original was unavailable");
                }
                const read = pos.data.read.bind(pos.data);
                let interrupted = false;
                pos.data.read = async (model, ids, ...args) => {
                    if (!interrupted && model === "pos.order.line" && ids.includes(saved.originalLineId)) {
                        interrupted = true;
                        document.body.dataset.originalReadInterrupted = "true";
                        throw new Error("Simulated unavailable closed-session original");
                    }
                    return read(model, ids, ...args);
                };
                pos.set_order(order);
                pos.showScreen("PaymentScreen", { orderUuid: order.uuid });
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: "body[data-original-read-interrupted='true'] .modal:contains('Could not load the original sale')" },
        Dialog.confirm(),
        {
            content: "An unavailable original discards only the undispatched tender",
            trigger: ".payment-screen",
            run() {
                const pos = window.posmodel;
                const saved = JSON.parse(sessionStorage.getItem(SAVED_RETURN));
                const order = pos.get_order();
                if (order.id !== saved.orderId || order.uuid !== saved.orderUuid || order.payment_ids.length) {
                    throw new Error("Unavailable original dispatched a refund or replaced its native return");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-amount", run() {
            const saved = JSON.parse(sessionStorage.getItem(SAVED_RETURN));
            const order = window.posmodel.get_order();
            if (order.lines[0].refunded_orderline_id?.id !== saved.originalLineId ||
                Number(this.anchor.value) !== 12.34) {
                throw new Error("Retry failed to load the saved original through native record loading");
            }
        } },
        { trigger: ".revolut-refund-confirm", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        ReceiptScreen.totalAmountContains("-12.34"),
        {
            trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${REFUND_ID}')`,
            run() {
                const saved = JSON.parse(sessionStorage.getItem(SAVED_RETURN));
                const order = window.posmodel.get_order();
                if (order.id !== saved.orderId || order.uuid !== saved.orderUuid ||
                    document.querySelector(".receipt-screen .pos-receipt").textContent.split(REFUND_ID).length !== 2) {
                    throw new Error("Recovered native return changed ownership or duplicated its refund receipt");
                }
                sessionStorage.removeItem(SAVED_RETURN);
            },
        },
    ].flat(),
});

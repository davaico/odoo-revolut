import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

const REFUND_REFERENCE = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const RECOVERY_KEY = "revolut-refund-server-recovery";

function savedReturn() {
    const pos = window.posmodel;
    const saved = JSON.parse(sessionStorage.getItem(RECOVERY_KEY));
    const order = pos.models["pos.order"].getBy("uuid", saved.orderUuid);
    const payment = order?.get_paymentline_by_uuid(saved.lineUuid);
    if (!order || order.id !== saved.orderId || !payment) {
        throw new Error("Reload replaced the saved native return or its refund line");
    }
    pos.set_order(order);
    order.select_paymentline(payment);
    pos.showScreen("PaymentScreen", { orderUuid: order.uuid });
    return { order, payment, saved };
}

async function forgetBrowserData(order, payment) {
    const pos = window.posmodel;
    sessionStorage.setItem(RECOVERY_KEY, JSON.stringify({
        orderUuid: order.uuid, lineUuid: payment.uuid, orderId: order.id,
        operationId: payment.uiState.revolutSnapshot.operation_id,
    }));
    // This affects only the disposable HttpCase browser. Disable
    // cache writers so it cannot repopulate after the reset.
    pos.data._debouncedSync.cancel();
    pos.data.syncDataWithIndexedDB = () => {};
    await pos.data.resetIndexedDB();
}

registry.category("web_tour.tours").add("pos_revolut_refund_server_recovery", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        {
            content: "Leave the completed refund as an unfinished native return",
            trigger: ".payment-screen",
            run() {
                window.posmodel.config.auto_validate_terminal_payment = false;
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        {
            content: "Forget browser data after completion and retain only the recovery identities",
            trigger: ".payment-screen .electronic_status:contains('Refund Successful')",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                const payment = order.payment_ids.find((line) => line.amount < 0);
                if (!Number.isInteger(order.id) || !Number.isInteger(payment?.id) ||
                    payment.transaction_id !== REFUND_REFERENCE || order.state !== "draft") {
                    throw new Error("The return and selected allocation were not persisted before refunding");
                }
                await forgetBrowserData(order, payment);
            },
        },
        refresh(),
        {
            content: "Recover the native return from server data with its completed refund",
            trigger: ".pos-content",
            run() {
                const { order, payment } = savedReturn();
                if (payment.get_payment_status() !== "done" ||
                    payment.transaction_id !== REFUND_REFERENCE ||
                    payment.payment_ref_no !== REFUND_REFERENCE ||
                    payment.uiState.revolutSnapshot?.state !== "verified" ||
                    order.revolut_payable_target !== -12.34 ||
                    !order.revolut_has_authority_exposure) {
                    throw new Error("Completed refund evidence was not restored from the persisted return");
                }
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

registry.category("web_tour.tours").add("pos_revolut_pending_refund_server_recovery", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        {
            content: "Interrupt foreground polling after the server has saved the pending refund",
            trigger: ".payment-screen",
            run() {
                const pos = window.posmodel;
                const call = pos.data.call.bind(pos.data);
                let interrupted = false;
                pos.data.call = async (model, method, args, ...rest) => {
                    if (!interrupted && model === "pos.payment.method" &&
                        method === "revolut_poll_refund") {
                        interrupted = true;
                        throw new Error("Simulated foreground refund polling interruption");
                    }
                    return call(model, method, args, ...rest);
                };
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".modal:contains('The refund may have succeeded')" },
        Dialog.confirm(),
        {
            content: "Forget all local payment evidence while retaining the saved pending return",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            async run() {
                const order = window.posmodel.get_order();
                const payment = order.payment_ids.find((line) => line.amount < 0);
                if (!Number.isInteger(order.id) || !Number.isInteger(payment?.id) ||
                    order.state !== "draft" || payment.is_done() ||
                    payment.uiState.revolutSnapshot?.state !== "pending" ||
                    payment.uiState.revolutSnapshot.order_id !== REFUND_REFERENCE) {
                    throw new Error("The pending refund was not saved before losing browser evidence");
                }
                await forgetBrowserData(order, payment);
            },
        },
        refresh(),
        {
            content: "Server-only recovery restores pending evidence without completing or restarting the refund",
            trigger: ".pos-content",
            run() {
                const { order, payment, saved } = savedReturn();
                const snapshot = payment.uiState.revolutSnapshot;
                if (order.state !== "draft" || payment.is_done() ||
                    payment.get_payment_status() !== "retry" ||
                    snapshot?.state !== "pending" || snapshot.operation_id !== saved.operationId ||
                    snapshot.order_id !== REFUND_REFERENCE || !payment.uiState.revolutStarted ||
                    payment.uiState.revolutUndispatched) {
                    throw new Error("Pending refund startup lost evidence or completed without checking Revolut");
                }
                payment.set_amount(-1);
                if (payment.amount !== -12.34 || order.remove_paymentline(payment) !== false ||
                    !order.get_paymentline_by_uuid(saved.lineUuid)) {
                    throw new Error("Server-only pending refund recovery lost its financial guards");
                }
            },
        },
        { trigger: ".payment-screen .send_payment_request:contains('Check status')" },
        PaymentScreen.clickPaymentMethod("Cash"),
        { trigger: ".modal:contains('Reconcile the unresolved Revolut payment')" },
        Dialog.confirm(),
        PaymentScreen.clickValidate(),
        { trigger: ".modal:contains('Revolut reconciliation required')" },
        Dialog.confirm(),
        {
            content: "Repeated explicit checks recover the same pending refund",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                this.anchor.click();
                this.anchor.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-12.34"),
        {
            content: "Recovered checkout retains the saved refund identities and references exactly once",
            trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${REFUND_REFERENCE}')`,
            run() {
                const pos = window.posmodel;
                const saved = JSON.parse(sessionStorage.getItem(RECOVERY_KEY));
                const order = pos.get_order();
                const payment = order.get_paymentline_by_uuid(saved.lineUuid);
                const receipt = document.querySelector(".receipt-screen .pos-receipt");
                if (order.uuid !== saved.orderUuid || order.id !== saved.orderId ||
                    !payment?.is_done() || payment.transaction_id !== REFUND_REFERENCE ||
                    payment.payment_ref_no !== REFUND_REFERENCE ||
                    payment.uiState.revolutSnapshot?.state !== "verified" ||
                    payment.uiState.revolutSnapshot.operation_id !== saved.operationId ||
                    receipt.textContent.split(REFUND_REFERENCE).length !== 2) {
                    throw new Error("Pending refund recovery replaced or duplicated the verified allocation");
                }
                sessionStorage.removeItem(RECOVERY_KEY);
            },
        },
    ].flat(),
});

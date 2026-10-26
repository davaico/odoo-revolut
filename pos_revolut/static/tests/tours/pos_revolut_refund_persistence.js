import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const REFUND_REFERENCE = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const RECOVERY_KEY = "revolut-refund-server-recovery";

registry.category("web_tour.tours").add("pos_revolut_refund_stale_native_recovery", {
    steps: () => {
        const steps = registry.category("web_tour.tours").get("pos_revolut_refund_server_recovery").steps();
        const index = steps.findIndex((step) => step.content ===
            "Recover the native return from server data with its completed refund");
        const recovered = steps[index].run;
        steps[index].run = async function () {
            recovered();
            const { payment } = savedReturn();
            await window.posmodel.data.read("pos.payment", [payment.id]);
            if (payment.transaction_id || payment.payment_ref_no ||
                payment.uiState.revolutCheckoutRestored !== true) {
                throw new Error("Expected native refresh to erase references while retaining the restored flag");
            }
        };
        steps.splice(index + 1, 1);
        const settled = steps.findIndex((step, stepIndex) => stepIndex > index &&
            step.trigger === ".pos .receipt-screen");
        if (settled >= 0) {
            steps[settled] = { trigger: ".modal, .receipt-screen", run() {
                const modal = document.querySelector(".modal");
                if (modal) throw new Error("Refreshed refund checkout rejected: " + modal.textContent);
            } };
        }
        return steps;
    },
});

function savedReturn() {
    const pos = window.posmodel;
    const saved = JSON.parse(sessionStorage.getItem(RECOVERY_KEY));
    const order = pos.models["pos.order"].getBy("uuid", saved.orderUuid);
    const payment = order?.getPaymentlineByUuid(saved.lineUuid);
    if (!order || order.id !== saved.orderId || !payment) {
        throw new Error("Reload replaced the saved native return or its refund line");
    }
    pos.setOrder(order);
    order.selectPaymentline(payment);
    pos.navigate("PaymentScreen", { orderUuid: order.uuid });
    return { order, payment, saved };
}

registry.category("web_tour.tours").add("pos_revolut_two_refunds_stale_native_recovery", {
    steps: () => {
        const steps = registry.category("web_tour.tours").get("pos_revolut_refund_server_recovery").steps();
        const confirm = steps.findIndex((step) => step.trigger === ".revolut-refund-confirm");
        steps.splice(confirm, 0, { trigger: ".revolut-refund-amount", run() {
            this.anchor.value = "6.17";
            this.anchor.dispatchEvent(new Event("input", { bubbles: true }));
        } });
        const forget = steps.findIndex((step) => step.content ===
            "Forget browser data after completion and retain only the recovery identities");
        steps[forget].run = async function () {
            const order = window.posmodel.getOrder();
            const payment = order.payment_ids.find((line) =>
                line.uiState.revolutSnapshot?.payment_id === REFUND_REFERENCE);
            if (!Number.isInteger(order.id) || !Number.isInteger(payment?.id) ||
                order.payment_ids.length !== 2 || order.payment_ids.some((line) =>
                    line.uiState.revolutSnapshot?.state !== "verified")) {
                throw new Error("Expected two committed refund allocations on the saved return");
            }
            sessionStorage.setItem(RECOVERY_KEY + "-tenders", JSON.stringify(order.payment_ids.map((line) => ({
                id: line.id, uuid: line.uuid, operationId: line.uiState.revolutOperationId,
                reference: line.uiState.revolutSnapshot.payment_id,
            }))));
            await forgetBrowserData(order, payment);
        };
        steps.splice(forget, 0,
            { trigger: ".payment-screen .electronic_status:contains('Refund Successful')" },
            PaymentScreen.clickPaymentMethod("Revolut"),
            { trigger: ".payment-screen .send_refund_request", run: "click" },
            { trigger: ".revolut-refund-confirm", run: "click" },
            { trigger: ".payment-screen .paymentline:contains('6c2f3842-c34d-4cc3-a0fc-9ae40b04dfb0') .electronic_status:contains('Refund Successful')" },
        );
        const index = steps.findIndex((step) => step.content ===
            "Recover the native return from server data with its completed refund");
        steps[index].run = async function () {
            const { order } = savedReturn();
            if (order.payment_ids.length !== 2) {
                throw new Error("Expected two distinct completed refund tenders");
            }
            await window.posmodel.data.read("pos.payment", order.payment_ids.map((line) => line.id));
            if (!order.payment_ids.some((line) => !line.transaction_id)) {
                throw new Error("Expected the saved waiting refund to replace its restored references");
            }
        };
        steps.splice(index + 1, 1);
        const receipt = steps.findIndex((step) => step.trigger?.includes("-12.34"));
        if (receipt >= 0) {
            steps[receipt] = ReceiptScreen.paymentLineContains("Revolut", "-6.17");
        }
        steps.push({ trigger: ".receipt-screen", run() {
            const order = window.posmodel.getOrder();
            const saved = JSON.parse(sessionStorage.getItem(RECOVERY_KEY + "-tenders"));
            const receiptText = document.querySelector(".receipt-screen .pos-receipt").textContent;
            for (const tender of saved) {
                const line = order.getPaymentlineByUuid(tender.uuid);
                if (line?.id !== tender.id || line.uiState.revolutOperationId !== tender.operationId ||
                    line.transaction_id !== tender.reference || line.payment_ref_no !== tender.reference ||
                    !line.isDone() || receiptText.split(tender.reference).length !== 2) {
                    throw new Error("Native checkout replaced a refund identity or lost or duplicated its reference");
                }
            }
            sessionStorage.removeItem(RECOVERY_KEY + "-tenders");
        } });
        return steps.flat();
    },
});

async function forgetBrowserData(order, payment) {
    const pos = window.posmodel;
    sessionStorage.setItem(RECOVERY_KEY, JSON.stringify({
        orderUuid: order.uuid, lineUuid: payment.uuid, orderId: order.id,
        operationId: payment.uiState.revolutSnapshot.operation_id,
    }));
    // This affects only the disposable HttpCase browser. Disable
    // cache writers so it cannot repopulate after the reset.
    pos.data.debouncedSynchronizeLocalDataInIndexedDB.cancel();
    pos.data.synchronizeLocalDataInIndexedDB = async () => {};
    pos.data.synchronizeServerDataInIndexedDB = async () => {};
    await pos.data.resetIndexedDB();
}

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
                await forgetBrowserData(order, payment);
            },
        },
        refresh(),
        {
            content: "Recover the native return from server data with its completed refund",
            trigger: ".pos-content",
            run() {
                const { order, payment } = savedReturn();
                if (payment.getPaymentStatus() !== "done" ||
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
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
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
        { trigger: ".payment-screen .send_refund_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        { trigger: ".modal:contains('The refund may have succeeded')" },
        Dialog.confirm(),
        {
            content: "Forget all local payment evidence while retaining the saved pending return",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            async run() {
                const order = window.posmodel.getOrder();
                const payment = order.payment_ids.find((line) => line.amount < 0);
                if (!Number.isInteger(order.id) || !Number.isInteger(payment?.id) ||
                    order.state !== "draft" || payment.isDone() ||
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
                if (order.state !== "draft" || payment.isDone() ||
                    payment.getPaymentStatus() !== "retry" ||
                    snapshot?.state !== "pending" || snapshot.operation_id !== saved.operationId ||
                    snapshot.order_id !== REFUND_REFERENCE || !payment.uiState.revolutStarted ||
                    payment.uiState.revolutUndispatched) {
                    throw new Error("Pending refund startup lost evidence or completed without checking Revolut");
                }
                payment.setAmount(-1);
                if (payment.amount !== -12.34 || order.removePaymentline(payment) !== false ||
                    !order.getPaymentlineByUuid(saved.lineUuid)) {
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
                const order = pos.getOrder();
                const payment = order.getPaymentlineByUuid(saved.lineUuid);
                const receipt = document.querySelector(".receipt-screen .pos-receipt");
                if (order.uuid !== saved.orderUuid || order.id !== saved.orderId ||
                    !payment?.isDone() || payment.transaction_id !== REFUND_REFERENCE ||
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

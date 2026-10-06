import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const KEY = "revolutVerifiedCheckoutRecovery";
const PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";
const ORDER_ID = "d40466e0-2188-41d0-bebb-aa3a930663a8";
const REFUND_ID = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";

function saved() {
    return JSON.parse(sessionStorage.getItem(KEY));
}

function current() {
    const pos = window.posmodel;
    const identity = saved();
    const order = pos.models["pos.order"].getBy("uuid", identity.orderUuid);
    const line = order?.getPaymentlineByUuid(identity.lineUuid);
    return { pos, order, line, identity };
}

function interceptCheckout(kind, reset = true) {
    const pos = window.posmodel;
    if (reset) {
        sessionStorage.setItem(KEY, JSON.stringify({
            orderUuid: pos.getOrder().uuid, starts: [],
        }));
    }
    const call = pos.data.call.bind(pos.data);
    const control = window.revolutCheckoutRecovery = {
        attempts: 0, kind, release: null, unhandled: [], originalCall: call,
    };
    window.addEventListener("unhandledrejection", (event) => control.unhandled.push(event.reason));
    const method = pos.models["pos.payment.method"].find((item) => item.use_payment_terminal === "revolut");
    method.payment_terminal.paymentState.checkoutRestoreTimeoutMs = 100;
    pos.data.call = async (model, rpc, args, ...rest) => {
        const identity = saved();
        if (model === "pos.payment.method" &&
            ["revolut_find_payment", "revolut_find_refund", "revolut_start_payment", "revolut_start_refund"].includes(rpc)) {
            const start = rpc.startsWith("revolut_start_");
            if (args[start ? 2 : 1] === identity.orderUuid) {
                const lineUuid = args[start ? 3 : 2];
                if (identity.lineUuid && identity.lineUuid !== lineUuid) {
                    throw new Error("Checkout restoration replaced the original payment line");
                }
                sessionStorage.setItem(KEY, JSON.stringify({ ...identity, lineUuid,
                    starts: start ? [...identity.starts, rpc] : identity.starts }));
            }
        }
        const { line } = current();
        if (model === "pos.order" && rpc === "revolut_checkout_state" &&
            args[1] === identity.orderUuid && line?.uiState.revolutSnapshot?.state === "verified") {
            control.attempts++;
            // Preparation and verification remain real server calls. Only
            // delivery of canonical browser checkout data is interrupted.
            if (control.kind === "reject") {
                throw new Error("Simulated verified checkout connection loss");
            }
            if (control.kind === "timeout") {
                return new Promise(() => {});
            }
            if (control.kind === "hold") {
                const result = await call(model, rpc, args, ...rest);
                await new Promise((resolve) => { control.release = resolve; });
                return result;
            }
        }
        return call(model, rpc, args, ...rest);
    };
}

async function waitNativeRequest() {
    const { order, line } = current();
    const owner = line.payment_method_id.payment_terminal.paymentState.owner(order, line);
    await Promise.all([owner.request, owner.screenRequest]);
    await new Promise((resolve) => requestAnimationFrame(resolve));
}

function assertRecoverable(refund) {
    const { pos, order, line, identity } = current();
    const snapshot = line?.uiState.revolutSnapshot;
    const control = window.revolutCheckoutRecovery;
    if (!order || !line || order.uuid !== identity.orderUuid ||
        line.isDone() || line.getPaymentStatus() !== "retry" || order.state !== "draft" ||
        snapshot?.state !== "verified" || !snapshot.operation_id ||
        snapshot.payment_id !== (refund ? REFUND_ID : PAYMENT_ID) ||
        snapshot.order_id !== (refund ? REFUND_ID : ORDER_ID) ||
        line.uiState.revolutLocalOutcome !== "checkout_restore_failed" ||
        pos.paymentTerminalInProgress || control.unhandled.length ||
        identity.starts.length !== 1 ||
        (refund && (!Number.isInteger(order.id) || !Number.isInteger(line.id))) ||
        (identity.operationId && snapshot.operation_id !== identity.operationId)) {
        throw new Error(`Verified checkout must retain evidence, remain unpaid and release native busy state: ${JSON.stringify({
            identity, orderState: order?.state, lineState: line?.getPaymentStatus(),
            snapshot, localOutcome: line?.uiState.revolutLocalOutcome,
            busy: pos.paymentTerminalInProgress, unhandled: control.unhandled.map(String),
        })}`);
    }
    sessionStorage.setItem(KEY, JSON.stringify({ ...identity, orderId: order.id,
        operationId: snapshot.operation_id, snapshot }));
}

function failureSteps(refund) {
    return [
        { trigger: ".modal:contains('Check status')" },
        Dialog.confirm(),
        {
            content: "Verified financial evidence stays unpaid while canonical checkout is unavailable",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            async run() {
                await waitNativeRequest();
                assertRecoverable(refund);
            },
        },
    ].flat();
}

for (const refund of [false, true]) {
    for (const kind of ["reject", "timeout"]) {
        const reload = !refund && kind === "reject";
        registry.category("web_tour.tours").add(`pos_revolut_${refund ? "refund" : "payment"}_checkout_${kind}`, {
            steps: () => [
                Chrome.startPoS(),
                ProductScreen.addOrderline("Desk Pad"),
                ProductScreen.clickPayButton(),
                ...(refund ? [
                    PaymentScreen.clickPaymentMethod("Revolut"),
                    ReceiptScreen.isShown(),
                    Chrome.clickOrders(),
                    TicketScreen.selectFilter("Paid"),
                    TicketScreen.selectOrderByPrice("12.34"),
                    { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
                    TicketScreen.confirmRefund(),
                    PaymentScreen.isShown(),
                ] : []),
                {
                    content: `Interrupt only canonical checkout ${kind} after real server verification`,
                    trigger: ".payment-screen",
                    run() { interceptCheckout(kind); },
                },
                PaymentScreen.clickPaymentMethod("Revolut"),
                ...(refund ? [
                    { trigger: ".payment-screen .send_refund_request", run: "click" },
                    { trigger: ".revolut-refund-confirm", run: "click" },
                ] : []),
                ...failureSteps(refund),
                PaymentScreen.clickValidate(),
                { trigger: ".modal:contains('Revolut reconciliation required')" },
                Dialog.confirm(),
                {
                    content: "Double Check status remains one bounded read-only restoration attempt",
                    trigger: ".payment-screen .send_payment_request:contains('Check status')",
                    async run() {
                        const control = window.revolutCheckoutRecovery;
                        const before = control.attempts;
                        this.anchor.click();
                        this.anchor.click();
                        await new Promise((resolve) => requestAnimationFrame(resolve));
                        await waitNativeRequest();
                        if (control.attempts !== before + 1) {
                            throw new Error("Double Check status duplicated canonical restoration");
                        }
                    },
                },
                ...failureSteps(refund),
                ...(reload ? [
                    refresh(),
                    {
                        content: "Reload retains the original verified line and read-only retry action",
                        trigger: ".pos-content",
                        run() {
                            const { pos, order, line } = current();
                            if (!order || !line) {
                                throw new Error("Reload lost the original saved checkout or its payment line");
                            }
                            pos.setOrder(order);
                            order.selectPaymentline(line);
                            pos.navigate("PaymentScreen", { orderUuid: order.uuid });
                            interceptCheckout(kind, false);
                            assertRecoverable(refund);
                        },
                    },
                ] : []),
                {
                    content: "Reconnect and restore canonical checkout through the native payment lifecycle",
                    trigger: ".payment-screen .send_payment_request:contains('Check status')",
                    async run() {
                        const control = window.revolutCheckoutRecovery;
                        control.kind = "hold";
                        current().line.payment_method_id.payment_terminal.paymentState.checkoutRestoreTimeoutMs = 5000;
                        const before = control.attempts;
                        this.anchor.click();
                        this.anchor.click();
                        const deadline = performance.now() + 3000;
                        while (!control.release && performance.now() < deadline) {
                            await new Promise((resolve) => setTimeout(resolve, 10));
                        }
                        const { order, line } = current();
                        if (!control.release || control.attempts !== before + 1 ||
                            line.isDone() || order.state !== "draft" ||
                            document.querySelector(".receipt-screen")) {
                            throw new Error("Financial verification completed checkout before canonical restoration");
                        }
                        control.release();
                    },
                },
                ReceiptScreen.isShown(),
                ReceiptScreen.paymentLineContains("Revolut", refund ? "-12.34" : "12.34"),
                {
                    content: "Canonical checkout settles the original payment or return exactly once",
                    trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${refund ? REFUND_ID : PAYMENT_ID}')`,
                    run() {
                        const { pos, order, line, identity } = current();
                        const reference = refund ? REFUND_ID : PAYMENT_ID;
                        const receipt = document.querySelector(".receipt-screen .pos-receipt");
                        if (pos.getOrder().uuid !== identity.orderUuid || order.id !== identity.orderId ||
                            order.state !== "paid" || !line?.isDone() ||
                            line.uiState.revolutSnapshot?.state !== "verified" ||
                            line.uiState.revolutSnapshot.operation_id !== identity.operationId ||
                            line.transaction_id !== reference || line.payment_ref_no !== (refund ? REFUND_ID : ORDER_ID) ||
                            order.priceIncl !== (refund ? -12.34 : 12.34) || order.remainingDue !== 0 ||
                            identity.starts.length !== 1 || pos.paymentTerminalInProgress ||
                            window.revolutCheckoutRecovery.unhandled.length ||
                            receipt.textContent.split(reference).length !== 2) {
                            throw new Error("Restored checkout lost identity, totals or duplicated verified references");
                        }
                        pos.data.call = window.revolutCheckoutRecovery.originalCall;
                        sessionStorage.removeItem(KEY);
                    },
                },
            ].flat(),
        });
    }
}

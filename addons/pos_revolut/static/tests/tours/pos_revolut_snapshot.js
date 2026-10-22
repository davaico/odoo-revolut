import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";
import { reopenRevolutOrder } from "./recovery_order_util";

const IDENTITY_KEY = "revolutSnapshotIdentity";
const STARTS_KEY = "revolutSnapshotStarts";
const SAVES_KEY = "revolutSnapshotSaves";

function identity() {
    return JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
}

function starts() {
    return JSON.parse(sessionStorage.getItem(STARTS_KEY) || "[]");
}

function saves() {
    return JSON.parse(sessionStorage.getItem(SAVES_KEY) || "[]");
}

function observeRpc({ rejectPayment = false } = {}) {
    const pos = window.posmodel;
    const call = pos.data.call.bind(pos.data);
    window.revolutSnapshotRpcs = new Set();
    pos.data.call = (model, method, args, ...rest) => {
        if (model === "pos.order" && method === "sync_from_ui") {
            const draft = args[0].find((order) => order.uuid === identity().orderUuid);
            if (draft) {
                const line = draft.lines.find((command) => command[2]?.qty !== undefined)?.[2];
                let tracked;
                tracked = call(model, method, args, ...rest).catch((error) => {
                    sessionStorage.setItem(SAVES_KEY, JSON.stringify([...saves(), {
                        orderUuid: draft.uuid, qty: line?.qty,
                        message: error?.data?.message || error.message,
                    }]));
                    throw error;
                }).finally(() => window.revolutSnapshotRpcs.delete(tracked));
                window.revolutSnapshotRpcs.add(tracked);
                return tracked;
            }
        }
        if (model !== "pos.payment.method" || !method.startsWith("revolut_")) {
            return call(model, method, args, ...rest);
        }
        const find = method === "revolut_find_payment" || method === "revolut_find_refund";
        const start = method === "revolut_start_payment" || method === "revolut_start_refund";
        const saved = identity();
        if ((find || start) && args[find ? 1 : 2] === saved.orderUuid) {
            const lineUuid = args[find ? 2 : 3];
            if (saved.lineUuid && saved.lineUuid !== lineUuid) {
                throw new Error("Snapshot recovery changed the payment-line identity");
            }
            sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({ ...saved, lineUuid }));
        }
        let tracked;
        tracked = call(model, method, args, ...rest).then((result) => {
            if (rejectPayment && method === "revolut_find_payment") {
                // Keep the payment amount selected from the valid cart. The
                // actual adapter must serialize this numeric cart quantity.
                pos.get_order().lines[0].qty = 1e10;
                rejectPayment = false;
            }
            if (start && args[2] === saved.orderUuid) {
                sessionStorage.setItem(STARTS_KEY, JSON.stringify([...starts(), {
                    orderUuid: args[2], lineUuid: args[3], amount: args[4],
                    qty: method === "revolut_start_refund"
                        ? args[6].lines[0].qty : pos.get_order().lines[0].qty,
                    result,
                }]));
            }
            return result;
        }).finally(() => window.revolutSnapshotRpcs.delete(tracked));
        window.revolutSnapshotRpcs.add(tracked);
        return tracked;
    };
}

async function finishRpc() {
    const order = window.posmodel.get_order();
    const line = order.get_paymentline_by_uuid(identity().lineUuid);
    const owner = line.payment_method_id.payment_terminal.paymentState.owner(order, line);
    // Reloaded returns restore their original sale through data.read before the
    // Revolut lookup. Wait for native screen/lifecycle completion, not only the
    // financial RPC tracker, before testing that preparation has unlocked.
    await Promise.all([owner.screenRequest, owner.request]);
    while (window.revolutSnapshotRpcs.size) {
        await Promise.all([...window.revolutSnapshotRpcs]);
    }
}

function checkUndispatchedLine(refund) {
    const order = window.posmodel.get_order();
    const saved = identity();
    const line = order.get_paymentline_by_uuid(saved.lineUuid);
    if (order.uuid !== saved.orderUuid || !line || line.is_done() ||
        line.uiState.revolutStarted || line.uiState.revolutSnapshot ||
        line.uiState.revolutOperationId || line.uiState.revolutOriginalOperationId ||
        line.transaction_id || line.payment_ref_no ||
        line.uiState.revolutStartRejected !== (refund ? "snapshot_invalid" : "authority_required")) {
        throw new Error("Snapshot rejection lost identity or retained financial exposure");
    }
    const requestedAmount = refund ? -10 : 10;
    const beforeEdit = {
        amount: line.amount, status: line.get_payment_status(),
        uiState: { ...line.uiState }, requestedAmount,
    };
    line.set_amount(requestedAmount);
    if (line.amount !== requestedAmount) {
        throw new Error(`A demonstrably undispatched line remained locked: ${JSON.stringify({
            ...beforeEdit, actualAmount: line.amount,
        })}`);
    }
    line.set_amount(refund ? -12.34 : 12.34);
    if (!refund) {
        if (starts().length !== 0) {
            throw new Error("Invalid preparation reached a financial start RPC");
        }
        return;
    }
    const rejected = saves().filter((request) => request.qty === -1e10);
    if (starts().length !== 0 || rejected.length !== 1 ||
        rejected[0].orderUuid !== saved.orderUuid ||
        !rejected[0].message?.includes("Correct the cart before starting payment") ||
        !line.uiState.revolutRejectionMessage?.includes("Correct the cart before starting payment")) {
        throw new Error("Invalid return did not fail native persistence before any refund dispatch with actionable feedback");
    }
}

function checkStatusTwice(refund) {
    return {
        content: "Repeated Check status stays read-only for the invalid snapshot",
        trigger: ".payment-screen .revolut_check_status:contains('Check status')",
        async run() {
            const count = starts().length;
            this.anchor.click();
            this.anchor.click();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await finishRpc();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            if (starts().length !== count) {
                throw new Error("Check status dispatched a financial request");
            }
            checkUndispatchedLine(refund);
        },
    };
}

function saleSteps() {
    return [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
    ].flat();
}

function returnSteps() {
    return [
        ...saleSteps(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
    ].flat();
}

function rejectedSteps(refund) {
    return [
        ...(refund ? returnSteps() : saleSteps()),
        {
            content: "Observe the real financial RPC and retain cart/payment identity",
            trigger: ".payment-screen",
            run() {
                sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({
                    orderUuid: window.posmodel.get_order().uuid,
                }));
                sessionStorage.setItem(STARTS_KEY, "[]");
                sessionStorage.setItem(SAVES_KEY, "[]");
                observeRpc({ rejectPayment: !refund });
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        ...(refund ? [
            { trigger: ".payment-screen .send_payment_request", run: "click" },
            { trigger: ".revolut-refund-sources .revolut-refund-source:checked" },
            {
                content: "Submit an invalid real return quantity after read-only allocation discovery",
                trigger: ".revolut-refund-confirm",
                run() {
                    window.posmodel.get_order().lines[0].qty = -1e10;
                    this.anchor.click();
                },
            },
        ] : []),
        { trigger: refund
            ? ".modal:contains('Revolut cart needs correction'):contains('Correct the cart before starting payment')"
            : ".modal:contains('Revolut cart needs correction'):contains('Correct the cart')" },
        Dialog.confirm(),
        {
            content: "Actionable snapshot feedback leaves the original unpaid line editable",
            trigger: `.payment-screen .electronic_status:contains('${refund
                ? "Correct the return" : "Review or approve the cart"}')`,
            async run() {
                checkUndispatchedLine(refund);
                if (refund && await window.posmodel.data.call(
                    "pos.revolut.refund.operation", "search_count",
                    [[["order_uuid", "=", identity().orderUuid]]]
                ) !== 0) {
                    throw new Error("Invalid native return persistence created a refund reservation");
                }
            },
        },
        checkStatusTwice(refund),
        {
            content: "Correct the real cart without replacing the order or payment line",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                if (refund) {
                    // Restore the field corrupted by this fixture. Native
                    // setQuantity rejects it because refundedQty counts the
                    // injected current return as already refunded quantity.
                    order.lines[0].qty = -1;
                } else {
                    order.lines[0].set_quantity(1);
                }
                checkUndispatchedLine(refund);
                // Both payment preparation and refund dispatch require a
                // native draft. Save the correction before reload so server
                // recovery cannot restore the rejected contents.
                await pos.syncAllOrders({ orders: [order], force: true, throw: true });
            },
        },
    ].flat();
}

for (const refund of [false, true]) {
    registry.category("web_tour.tours").add(`pos_revolut_${refund ? "refund" : "payment"}_snapshot_recovery`, {
        steps: () => [
            ...rejectedSteps(refund),
            refresh(),
            ...reopenRevolutOrder(() => identity().orderUuid),
            {
                content: "Reload retains definite non-dispatch proof and stable identities",
                trigger: ".payment-screen .send_payment_request:contains('Resume')",
                run() {
                    observeRpc();
                    checkUndispatchedLine(refund);
                    if (refund && window.posmodel.get_order().lines[0].qty !== -1) {
                        throw new Error(`Reload lost the corrected return quantity: ${window.posmodel.get_order().lines[0].qty}`);
                    }
                },
            },
            checkStatusTwice(refund),
            {
                content: "Explicit repeated Resume submits one corrected financial request",
                trigger: ".payment-screen .send_payment_request:contains('Resume')",
                async run() {
                    this.anchor.click();
                    this.anchor.click();
                    if (refund) {
                        const deadline = performance.now() + 3000;
                        while (!document.querySelector(".revolut-refund-source:checked") && performance.now() < deadline) {
                            await new Promise((resolve) => setTimeout(resolve, 100));
                        }
                        if (!document.querySelector(".revolut-refund-source:checked")) {
                            const order = window.posmodel.get_order();
                            throw new Error(`Corrected return Resume did not offer allocation: ${JSON.stringify({
                                qty: order.lines[0].qty, total: order.get_total_with_tax(),
                                dialog: document.querySelector(".modal")?.textContent,
                                payments: order.payment_ids.map((line) => ({ amount: line.amount,
                                    status: line.payment_status, snapshot: line.uiState.revolutSnapshot })),
                            })}`);
                        }
                    }
                },
            },
            ...(refund ? [
                { trigger: ".revolut-refund-sources .revolut-refund-source:checked" },
                { trigger: ".revolut-refund-confirm", run: "click" },
            ] : []),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Revolut", refund ? "-12.34" : "12.34"),
            {
                content: "Corrected checkout preserves identity and requires server verification",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.get_order();
                    const saved = identity();
                    const line = order.get_paymentline_by_uuid(saved.lineUuid);
                    const accepted = starts().filter((request) => request.result?.operation_id);
                    if (order.uuid !== saved.orderUuid || !line?.is_done() ||
                        line.uiState.revolutSnapshot?.state !== "verified" ||
                        accepted.length !== 1 || accepted[0].qty !== (refund ? -1 : 1)) {
                        throw new Error("Corrected checkout lacked one verified start on the original identity");
                    }
                    sessionStorage.removeItem(IDENTITY_KEY);
                    sessionStorage.removeItem(STARTS_KEY);
                    sessionStorage.removeItem(SAVES_KEY);
                },
            },
        ].flat(),
    });
}

registry.category("web_tour.tours").add("pos_revolut_payment_snapshot_cash_alternative", {
    steps: () => [
        ...rejectedSteps(false),
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        PaymentScreen.emptyPaymentlines("12.34"),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "12.34"),
        {
            content: "Cash checkout removes the proven undispatched line without another financial start",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.get_order();
                const saved = identity();
                if (order.uuid !== saved.orderUuid || order.get_paymentline_by_uuid(saved.lineUuid) ||
                    starts().length !== 0) {
                    throw new Error("Cash checkout retained the rejected line or dispatched another payment");
                }
                sessionStorage.removeItem(IDENTITY_KEY);
                sessionStorage.removeItem(STARTS_KEY);
                sessionStorage.removeItem(SAVES_KEY);
            },
        },
    ].flat(),
});

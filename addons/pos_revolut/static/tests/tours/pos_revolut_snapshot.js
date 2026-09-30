import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const IDENTITY_KEY = "revolutSnapshotIdentity";
const STARTS_KEY = "revolutSnapshotStarts";

function identity() {
    return JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
}

function starts() {
    return JSON.parse(sessionStorage.getItem(STARTS_KEY) || "[]");
}

function observeRpc({ rejectPayment = false } = {}) {
    const pos = window.posmodel;
    const call = pos.data.call.bind(pos.data);
    window.revolutSnapshotRpcs = new Set();
    pos.data.call = (model, method, args, ...rest) => {
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
                pos.getOrder().lines[0].qty = 1e10;
                rejectPayment = false;
            }
            if (start && args[2] === saved.orderUuid) {
                sessionStorage.setItem(STARTS_KEY, JSON.stringify([...starts(), {
                    orderUuid: args[2], lineUuid: args[3], amount: args[4],
                    qty: args[method === "revolut_start_refund" ? 6 : 7].lines[0].qty,
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
    const order = window.posmodel.getOrder();
    const line = order.getPaymentlineByUuid(identity().lineUuid);
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
    const order = window.posmodel.getOrder();
    const saved = identity();
    const line = order.getPaymentlineByUuid(saved.lineUuid);
    if (order.uuid !== saved.orderUuid || !line || line.isDone() ||
        line.uiState.revolutStarted || line.uiState.revolutSnapshot ||
        line.uiState.revolutOperationId || line.uiState.revolutOriginalOperationId ||
        line.transaction_id || line.payment_ref_no ||
        line.uiState.revolutStartRejected !== "snapshot_invalid") {
        throw new Error("Snapshot rejection lost identity or retained financial exposure");
    }
    const requestedAmount = refund ? -10 : 10;
    const beforeEdit = {
        amount: line.amount, status: line.getPaymentStatus(),
        uiState: { ...line.uiState }, requestedAmount,
    };
    line.setAmount(requestedAmount);
    if (line.amount !== requestedAmount) {
        throw new Error(`A demonstrably undispatched line remained locked: ${JSON.stringify({
            ...beforeEdit, actualAmount: line.amount,
        })}`);
    }
    line.setAmount(refund ? -12.34 : 12.34);
    const rejected = starts().filter((request) => request.result?.start_rejected);
    if (rejected.length !== 1 || rejected[0].qty !== (refund ? -1e10 : 1e10) ||
        rejected[0].amount !== (refund ? -12.34 : 12.34)) {
        throw new Error("The actual POS adapter did not submit the invalid numeric cart");
    }
    const result = rejected[0].result;
    if (result.start_rejected !== "snapshot_invalid" || result.dispatched !== false ||
        result.order_uuid !== saved.orderUuid || result.payment_line_uuid !== saved.lineUuid ||
        result.previous_operation_id !== false || result.operation_id ||
        !result.message?.includes("Correct the cart before starting payment")) {
        throw new Error("Snapshot feedback lacked authoritative actionable non-dispatch proof");
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
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
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
                    orderUuid: window.posmodel.getOrder().uuid,
                }));
                sessionStorage.setItem(STARTS_KEY, "[]");
                observeRpc({ rejectPayment: !refund });
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        ...(refund ? [
            { trigger: ".payment-screen .send_refund_request", run: "click" },
            { trigger: ".revolut-refund-sources .revolut-refund-source:checked" },
            {
                content: "Submit an invalid real return quantity after read-only allocation discovery",
                trigger: ".revolut-refund-confirm",
                run() {
                    window.posmodel.getOrder().lines[0].qty = -1e10;
                    this.anchor.click();
                },
            },
        ] : []),
        { trigger: ".modal:contains('Revolut cart needs correction'):contains('Correct the cart before starting payment')" },
        Dialog.confirm(),
        {
            content: "Actionable snapshot feedback leaves the original unpaid line editable",
            trigger: `.payment-screen .electronic_status:contains('${refund
                ? "Correct the return" : "Correct the cart"}')`,
            run() { checkUndispatchedLine(refund); },
        },
        checkStatusTwice(refund),
        {
            content: "Correct the real cart without replacing the order or payment line",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            run() {
                window.posmodel.getOrder().lines[0].qty = refund ? -1 : 1;
                checkUndispatchedLine(refund);
            },
        },
    ].flat();
}

for (const refund of [false, true]) {
    registry.category("web_tour.tours").add(`pos_revolut_${refund ? "refund" : "payment"}_snapshot_recovery`, {
        steps: () => [
            ...rejectedSteps(refund),
            refresh(),
            {
                content: "Reload retains definite non-dispatch proof and stable identities",
                trigger: ".payment-screen .send_payment_request:contains('Resume')",
                run() {
                    observeRpc();
                    checkUndispatchedLine(refund);
                },
            },
            checkStatusTwice(refund),
            {
                content: "Explicit repeated Resume submits one corrected financial request",
                trigger: ".payment-screen .send_payment_request:contains('Resume')",
                run() {
                    this.anchor.click();
                    this.anchor.click();
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
                    const order = window.posmodel.getOrder();
                    const saved = identity();
                    const line = order.getPaymentlineByUuid(saved.lineUuid);
                    const accepted = starts().filter((request) => request.result?.operation_id);
                    if (order.uuid !== saved.orderUuid || !line?.isDone() ||
                        line.uiState.revolutSnapshot?.state !== "verified" ||
                        accepted.length !== 1 || accepted[0].qty !== (refund ? -1 : 1)) {
                        throw new Error("Corrected checkout lacked one verified start on the original identity");
                    }
                    sessionStorage.removeItem(IDENTITY_KEY);
                    sessionStorage.removeItem(STARTS_KEY);
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
                const order = window.posmodel.getOrder();
                const saved = identity();
                if (order.uuid !== saved.orderUuid || order.getPaymentlineByUuid(saved.lineUuid) ||
                    starts().length !== 1) {
                    throw new Error("Cash checkout retained the rejected line or dispatched another payment");
                }
                sessionStorage.removeItem(IDENTITY_KEY);
                sessionStorage.removeItem(STARTS_KEY);
            },
        },
    ].flat(),
});

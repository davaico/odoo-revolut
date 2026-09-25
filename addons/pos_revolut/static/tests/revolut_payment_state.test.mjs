import assert from "node:assert/strict";
import { test } from "node:test";
import {
    ForegroundTimeout, RevolutPaymentState, paymentActions, orderActions,
    paymentOutcome, paymentResponseSuccessful, restorePaymentLine,
} from "../src/app/revolut_payment_state.js";

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((done, fail) => { resolve = done; reject = fail; });
    return { promise, resolve, reject };
}

class ControlledClock {
    time = 0;
    waiting = [];

    now = () => this.time;

    wait = (duration) => new Promise((resolve) => {
        this.waiting.push({ at: this.time + duration, resolve });
    });

    before = (promise, deadline) => Promise.race([
        promise,
        this.wait(Math.max(0, deadline - this.time)).then(() => { throw new ForegroundTimeout(); }),
    ]);

    advance(duration) {
        this.time += duration;
        const due = this.waiting.filter(({ at }) => at <= this.time);
        this.waiting = this.waiting.filter(({ at }) => at > this.time);
        for (const timer of due) {
            timer.resolve();
        }
    }
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

function fixture({ refund = false, call, chooseAllocation = async () => false } = {}) {
    const clock = new ControlledClock();
    const order = { uuid: "order-1", payment_ids: [], isRefund: refund };
    const line = {
        uuid: "line-1", amount: refund ? -12.34 : 12.34, pos_order_id: order,
        payment_method_id: { use_payment_terminal: "revolut" }, uiState: {},
        payment_status: "pending", transaction_id: false,
        getPaymentStatus() { return this.payment_status; },
        setPaymentStatus(status) { this.payment_status = status; },
    };
    order.payment_ids.push(line);
    const calls = [];
    const errors = [];
    const adapter = {
        async call(method, args) {
            calls.push({ method, args });
            return call?.(method, args, calls) ?? false;
        },
        financialSnapshot: () => ({ amount_total: 12.34 }),
        restoreRefundOriginals: async () => {},
        chooseAllocation,
        setRefundAmount(payment, amount) { payment.amount = -amount; },
        discardRefund(payment) { order.payment_ids = order.payment_ids.filter((item) => item !== payment); },
        setVerified(payment, result) {
            payment.transaction_id = result.payment_id;
            payment.payment_ref_no = result.order_id;
        },
        showError(payment, state) { errors.push(state); },
    };
    const state = new RevolutPaymentState({ adapter, clock, methodId: 7, sessionId: 8, currencyId: 9 });
    return { state, clock, order, line, calls, errors };
}

test("verified cancellation result survives an older failed poll", async () => {
    const olderPoll = deferred();
    const { state, clock, order, line, calls } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                return { operation_id: 1, state: "pending" };
            }
            if (method === "revolut_poll_payment") {
                return olderPoll.promise;
            }
            if (method === "revolut_cancel_payment") {
                return { operation_id: 1, state: "verified", payment_id: "pay-1", order_id: "rev-1" };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    clock.advance(1000);
    await tick();
    assert.equal(await state.cancel(order, line), false);
    olderPoll.resolve({ operation_id: 1, state: "failed", retry_safe: true });
    assert.equal(await request, true);
    assert.equal(paymentResponseSuccessful(line, false), true);
    assert.equal(line.payment_ref_no, "rev-1");
    assert.equal(paymentActions(line).blocksCheckout, false);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("verified poll survives a later cancellation transport failure", async () => {
    const poll = deferred();
    const cancellation = deferred();
    const { state, clock, order, line, errors } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                return { operation_id: 5, state: "pending" };
            }
            if (method === "revolut_poll_payment") {
                return poll.promise;
            }
            if (method === "revolut_cancel_payment") {
                return cancellation.promise;
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    clock.advance(1000);
    await tick();
    const cancel = state.cancel(order, line);
    poll.resolve({ operation_id: 5, state: "verified", payment_id: "pay-5", order_id: "rev-5" });
    await tick();
    cancellation.reject(new Error("connection lost after verification"));
    assert.equal(await cancel, false);
    assert.equal(await request, true);
    assert.equal(paymentOutcome(line), "verified");
    assert.equal(line.payment_ref_no, "rev-5");
    assert.deepEqual(errors, []);
});

test("foreground deadline keeps an uncertain start protected and reload reconciles it", async () => {
    const lostStart = deferred();
    let finds = 0;
    const { state, clock, order, line, calls } = fixture({
        call(method) {
            if (method === "revolut_find_payment") {
                return ++finds === 1 ? false : { operation_id: 2, state: "pending" };
            }
            if (method === "revolut_start_payment") {
                return lostStart.promise;
            }
            if (method === "revolut_poll_payment") {
                return { operation_id: 2, state: "verified", payment_id: "pay-2", order_id: "rev-2" };
            }
            return false;
        },
    });
    const first = state.request(order, line);
    await tick();
    clock.advance(60000);
    assert.equal(await first, false);
    assert.equal(line.uiState.revolutLocalOutcome, "timed_out");
    assert.equal(paymentActions(line).blocksCheckout, true);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    restorePaymentLine(line);
    assert.equal(await state.request(order, line), true);
    lostStart.resolve({ operation_id: 2, state: "failed", retry_safe: true });
    await tick();
    assert.equal(line.transaction_id, "pay-2");
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("repeated requests share one dispatch while separate split-tender lines stay independent", async () => {
    const pendingStart = deferred();
    const { state, order, line, calls } = fixture({
        call(method, args) {
            if (method === "revolut_start_payment") {
                return args[3] === "line-1" ? pendingStart.promise :
                    { operation_id: 4, state: "verified", payment_id: "pay-4", order_id: "rev-4" };
            }
            return false;
        },
    });
    const other = { ...line, uuid: "line-2", uiState: {}, payment_status: "pending" };
    order.payment_ids.push(other);
    const first = state.request(order, line);
    assert.equal(state.request(order, line), first);
    assert.equal(await state.request(order, other), true);
    assert.equal(paymentActions(other).blocksCheckout, false);
    assert.equal(orderActions(order).blocksCheckout, true);
    pendingStart.resolve({ operation_id: 3, state: "verified", payment_id: "pay-3", order_id: "rev-3" });
    assert.equal(await first, true);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 2);
});

test("refund dismissal never dispatches and dispatched refunds cannot be cancelled", async () => {
    const { state, order, line, calls } = fixture({
        refund: true,
        call(method) {
            if (method === "revolut_refund_sources") {
                return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
            }
            return false;
        },
    });
    assert.equal(await state.request(order, line), false);
    assert.equal(order.payment_ids.length, 0);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
    order.payment_ids.push(line);
    line.uiState.revolutStarted = true;
    line.uiState.revolutOperationId = 11;
    line.uiState.revolutSnapshot = { operation_id: 11, state: "pending" };
    assert.equal(await state.cancel(order, line), false);
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(calls.some(({ method }) => method === "revolut_cancel_payment"), false);
});

test("a safe payment replacement stays on the same logical line and retains its predecessor", async () => {
    let starts = 0;
    const { state, order, line, calls } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                return ++starts === 1
                    ? { operation_id: 20, state: "declined", retry_safe: true }
                    : { operation_id: 21, state: "verified", payment_id: "pay-21", order_id: "rev-21" };
            }
            return false;
        },
    });
    assert.equal(await state.request(order, line), false);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(await state.request(order, line), true);
    assert.equal(line.transaction_id, "pay-21");
    const startsSent = calls.filter(({ method }) => method === "revolut_start_payment");
    assert.equal(startsSent.length, 2);
    assert.equal(startsSent[1].args[6], 20);
});

test("reloaded refund reconciles its existing operation and preserves its reference", async () => {
    const { state, order, line, calls } = fixture({
        refund: true,
        call(method) {
            if (method === "revolut_find_refund") {
                return { operation_id: 31, state: "pending" };
            }
            if (method === "revolut_poll_refund") {
                return { operation_id: 31, state: "verified", payment_id: "refund-31", order_id: "rev-refund-31" };
            }
            return false;
        },
    });
    line.uiState.revolutStarted = true;
    restorePaymentLine(line);
    assert.equal(line.payment_status, "retry");
    assert.equal(await state.request(order, line), true);
    assert.equal(line.payment_ref_no, "rev-refund-31");
    assert.equal(paymentActions(line).blocksCheckout, false);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
});

test("a failed refund can be removed for replacement but cannot be edited or settled", () => {
    const { order, line } = fixture({ refund: true });
    line.uiState.revolutStarted = true;
    line.uiState.revolutSnapshot = { operation_id: 41, state: "failed", retry_safe: true };
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(paymentActions(line).canEditAmount, false);
    assert.equal(orderActions(order).blocksAlternativeTender, false);
    assert.equal(orderActions(order).blocksCheckout, true);
});

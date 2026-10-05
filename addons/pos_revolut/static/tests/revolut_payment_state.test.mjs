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

const busyRejection = {
    start_rejected: "terminal_busy", dispatched: false,
    order_uuid: "order-1", payment_line_uuid: "line-1", previous_operation_id: false,
};

const snapshotRejection = {
    ...busyRejection, start_rejected: "snapshot_invalid",
    message: "Revolut cart quantity is unsupported. Correct the cart before starting payment.",
};

function fixture({ refund = false, call, chooseAllocation = async () => false,
    restoreRefundOriginals = async () => {},
    prepareRefund = async () => {},
    preparePayment = async () => ({status:"prepared", authorization_id:1, cart_version:1, tender_revision:1}),
    projectVerified = async () => {} } = {}) {
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
    const preparationErrors = [];
    const preparationMessages = [];
    const adapter = {
        preparePayment,
        prepareRefund,
        async call(method, args) {
            calls.push({ method, args });
            return call?.(method, args, calls) ?? false;
        },
        financialSnapshot: () => ({ amount_total: 12.34 }),
        restoreRefundOriginals,
        chooseAllocation,
        setRefundAmount(payment, amount) { payment.amount = -amount; },
        discardRefund(payment) { order.payment_ids = order.payment_ids.filter((item) => item !== payment); },
        async setVerified(payment, result) {
            await projectVerified(payment, result);
            payment.transaction_id = result.payment_id;
            payment.payment_ref_no = result.order_id;
        },
        showError(payment, state) { errors.push(state); },
        showPreparationError(payment, reason, message) {
            preparationErrors.push(reason);
            preparationMessages.push(message);
        },
    };
    const state = new RevolutPaymentState({ adapter, clock, methodId: 7, sessionId: 8, currencyId: 9 });
    return { state, clock, order, line, calls, errors, preparationErrors, preparationMessages };
}

test("refund dispatch waits until its selected return allocation is saved", async () => {
    const saved = deferred();
    let amountAtSave;
    const { state, order, line, calls } = fixture({
        refund: true,
        chooseAllocation: async () => ({ operationId: 10, amount: 5 }),
        prepareRefund: async (returnOrder, payment) => {
            amountAtSave = payment.amount;
            await saved.promise;
            returnOrder.id = 42;
        },
        call(method) {
            if (method === "revolut_refund_sources") {
                return [{ operation_id: 10, remaining_minor: 1234 }];
            }
            if (method === "revolut_start_refund") {
                assert.equal(order.id, 42);
                return { operation_id: 20, state: "verified", payment_id: "refund-20", order_id: "refund-20" };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    assert.equal(amountAtSave, -5);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
    assert.equal(line.uiState.revolutStarted, undefined);
    saved.resolve();
    assert.equal(await request, true);
    assert.equal(line.transaction_id, "refund-20");
});

test("a failed return save preserves completed allocations and permits an explicit safe retry", async () => {
    let failSave = true;
    const { state, order, line, calls, errors } = fixture({
        refund: true,
        chooseAllocation: async () => ({ operationId: 10, amount: 5 }),
        prepareRefund: async () => {
            if (failSave) {
                throw new Error("Reconnect and save the return before refunding.");
            }
        },
        call(method) {
            if (method === "revolut_refund_sources") {
                return [{ operation_id: 10, remaining_minor: 500 }];
            }
            if (method === "revolut_start_refund") {
                return { operation_id: 20, state: "verified", payment_id: "refund-20", order_id: "refund-20" };
            }
            return false;
        },
    });
    const completed = { ...line, uuid: "completed-line", amount: -7.34,
        payment_status: "done", transaction_id: "refund-19",
        uiState: { revolutSnapshot: { operation_id: 19, state: "verified" } } };
    order.payment_ids.unshift(completed);
    assert.equal(await state.request(order, line), false);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
    assert.deepEqual(errors, ["snapshot_invalid"]);
    assert.equal(line.uiState.revolutUndispatched, true);
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(paymentActions(completed).canDelete, false);
    assert.equal(completed.transaction_id, "refund-19");
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    failSave = false;
    assert.equal(await state.request(order, line), true);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_refund").length, 1);
    assert.equal(order.payment_ids[0], completed);
});

test("cancelling while a return saves prevents a late refund dispatch", async () => {
    const saved = deferred();
    const { state, order, line, calls } = fixture({
        refund: true,
        chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
        prepareRefund: () => saved.promise,
        call(method) {
            if (method === "revolut_refund_sources") {
                return [{ operation_id: 10, remaining_minor: 1234 }];
            }
            if (method === "revolut_start_refund") {
                return { operation_id: 20, state: "verified", payment_id: "refund-20", order_id: "refund-20" };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    const cancel = state.cancel(order, line);
    saved.resolve();
    assert.equal(await request, false);
    assert.equal(await cancel, true);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
    assert.equal(paymentActions(line).canDelete, true);
});

test("an invalid refund source snapshot exposes the server correction message without dispatching", async () => {
    const { state, order, line, calls, preparationErrors, preparationMessages } = fixture({
        refund: true,
        call(method) {
            if (method === "revolut_refund_sources") {
                throw { data: { message: snapshotRejection.message } };
            }
            return false;
        },
    });
    assert.equal(await state.request(order, line), false);
    assert.deepEqual(preparationErrors, ["sources"]);
    assert.deepEqual(preparationMessages, [snapshotRejection.message]);
    assert.deepEqual(order.payment_ids, []);
    assert.equal(calls.some(({ method }) => method.includes("revolut_start_")), false);
});

test("a definitive snapshot rejection leaves the same unpaid payment editable and removable", async () => {
    const { state, order, line, calls, errors } = fixture({
        call(method) {
            return method === "revolut_start_payment" ? snapshotRejection : false;
        },
    });
    assert.equal(await state.request(order, line), false);
    line.setPaymentStatus("retry");
    assert.equal(paymentOutcome(line), "snapshot_invalid");
    assert.deepEqual(errors, ["snapshot_invalid"]);
    assert.equal(line.uiState.revolutRejectionMessage, snapshotRejection.message);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(paymentActions(line).retrySafe, true);
    assert.equal(orderActions(order).blocksAlternativeTender, false);
    assert.equal(paymentResponseSuccessful(line, true), false);
    assert.equal(line.transaction_id, false);
    assert.equal(line.uuid, "line-1");
    assert.equal(order.uuid, "order-1");
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("a definitive refund snapshot rejection releases its fresh allocation for correction and explicit resume", async () => {
    let rejected = true;
    const { state, order, line, calls, errors } = fixture({
        refund: true,
        chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
        call(method) {
            if (method === "revolut_refund_sources") {
                return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
            }
            if (method === "revolut_start_refund") {
                return rejected ? snapshotRejection : {
                    operation_id: 64, state: "verified", payment_id: "refund-64", order_id: "rev-64",
                };
            }
            return false;
        },
    });
    assert.equal(await state.request(order, line), false);
    line.setPaymentStatus("retry");
    assert.deepEqual(errors, ["snapshot_invalid"]);
    assert.equal(line.uiState.revolutOriginalOperationId, false);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(paymentActions(line).retrySafe, true);
    restorePaymentLine(line);
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    rejected = false;
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_refund").length, 1);
    const resumed = state.request(order, line);
    assert.equal(state.request(order, line), resumed);
    assert.equal(await resumed, true);
    assert.equal(line.transaction_id, "refund-64");
    assert.equal(line.payment_ref_no, "rev-64");
    assert.equal(line.uuid, "line-1");
    assert.equal(order.uuid, "order-1");
    assert.equal(calls.filter(({ method }) => method === "revolut_start_refund").length, 2);
});

test("a restored rejected refund stays guarded until read-only original restoration finishes", async () => {
    const originalRead = deferred();
    const { state, order, line, calls } = fixture({
        refund: true,
        restoreRefundOriginals: () => originalRead.promise,
    });
    Object.assign(line.uiState, {
        revolutUndispatched: true, revolutStartRejected: "snapshot_invalid",
        revolutLocalOutcome: "snapshot_invalid",
    });
    restorePaymentLine(line);
    const checking = state.screenRequest(order, line, async () => {
        const result = await state.request(order, line);
        line.setPaymentStatus("retry");
        return result;
    }, { checkOnly: true });
    await tick();
    const repeated = state.screenRequest(order, line, () => assert.fail("duplicate status check"));
    assert.equal(calls.length, 0);
    assert.equal(paymentActions(line).canEditAmount, false);
    assert.equal(line.uiState.revolutDiscovering, true);
    originalRead.resolve();
    assert.deepEqual(await Promise.all([checking, repeated]), [false, false]);
    assert.deepEqual(calls.map(({ method }) => method), ["revolut_find_refund"]);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(line.uiState.revolutDiscovering, false);
    assert.equal(paymentOutcome(line), "snapshot_invalid");
});

for (const refund of [false, true]) {
    for (const [reason, response] of [
        ["exception with snapshot wording", new Error(snapshotRejection.message)],
        ["missing response", false],
        ["different order", { ...snapshotRejection, order_uuid: "other-order" }],
        ["different payment line", { ...snapshotRejection, payment_line_uuid: "other-line" }],
        ["different predecessor", { ...snapshotRejection, previous_operation_id: 65 }],
        ["missing dispatch proof", { ...snapshotRejection, dispatched: undefined }],
        ["possible dispatch", { ...snapshotRejection, dispatched: true }],
        ["provider reference", { ...snapshotRejection, order_id: "rev-uncertain" }],
        ["refund reference", { ...snapshotRejection, refund_id: "refund-uncertain" }],
    ]) {
        test(`${refund ? "refund" : "payment"} ${reason} cannot establish a safe snapshot rejection`, async () => {
            const { state, order, line, calls } = fixture({
                refund,
                chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
                call(method) {
                    if (method === "revolut_refund_sources") {
                        return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                    }
                    if (method.includes("revolut_start_")) {
                        if (response instanceof Error) {
                            throw response;
                        }
                        return response;
                    }
                    return false;
                },
            });
            assert.equal(await state.request(order, line), false);
            line.setPaymentStatus("retry");
            restorePaymentLine(line);
            assert.equal(await state.request(order, line, { checkOnly: true }), false);
            assert.equal(paymentActions(line).canDelete, false);
            assert.equal(paymentActions(line).canEditAmount, false);
            assert.equal(paymentActions(line).retrySafe, false);
            assert.equal(orderActions(order).blocksCheckout, true);
            assert.equal(orderActions(order).blocksAlternativeTender, true);
            assert.equal(calls.filter(({ method }) => method.includes("revolut_start_")).length, 1);
        });
    }
}

test("documented processing observations stay guarded until capture on the same attempt", async () => {
    const states = [
        "pending", "authentication_challenge", "authentication_verified",
        "authorisation_started", "authorisation_passed", "authorised", "capture_started", "captured",
    ];
    let observation = 0;
    const { state, clock, order, line, calls, errors } = fixture({
        call(method) {
            if (method === "revolut_start_payment" || method === "revolut_poll_payment") {
                if (method === "revolut_poll_payment") {
                    observation += 1;
                }
                return {
                    operation_id: 70, state: states[observation] === "captured" ? "verified" : "pending",
                    provider_state: states[observation], payment_id: "pay-70",
                    payment_intent_id: "intent-70", order_id: "rev-70", retry_safe: false,
                };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    assert.equal(state.request(order, line), request);
    await tick();
    for (const providerState of states.slice(0, -1)) {
        assert.equal(line.uiState.revolutSnapshot.provider_state, providerState);
        assert.equal(line.getPaymentStatus(), "waitingCard");
        assert.equal(paymentResponseSuccessful(line, true), false);
        assert.equal(line.transaction_id, false);
        assert.equal(paymentActions(line).canEditAmount, false);
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(paymentActions(line).retrySafe, false);
        assert.equal(orderActions(order).blocksCheckout, true);
        clock.advance(1000);
        await tick();
    }
    assert.equal(await request, true);
    assert.equal(line.transaction_id, "pay-70");
    assert.equal(line.payment_ref_no, "rev-70");
    assert.equal(paymentResponseSuccessful(line, true), true);
    assert.deepEqual(errors, []);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
    assert.deepEqual(calls.filter(({ method }) => method === "revolut_poll_payment")
        .map(({ args }) => args.slice(1)), Array(7).fill([70, "order-1", "line-1"]));
});

for (const [processing, final] of [["declining", "declined"], ["failing", "failed"], ["cancelling", "cancelled"]]) {
    test(`early processing observes ${processing} before final ${final}`, async () => {
        let polls = 0;
        const { state, clock, order, line, calls, errors } = fixture({
            call(method) {
                if (method === "revolut_start_payment") {
                    return { operation_id: 71, state: "pending", provider_state: "authorisation_started" };
                }
                if (method === "revolut_poll_payment") {
                    return ++polls === 1
                        ? { operation_id: 71, state: "pending", provider_state: processing }
                        : { operation_id: 71, state: final, provider_state: final, retry_safe: true };
                }
                return false;
            },
        });
        const request = state.request(order, line);
        await tick();
        clock.advance(1000);
        await tick();
        assert.equal(line.uiState.revolutSnapshot.provider_state, processing);
        assert.equal(paymentActions(line).retrySafe, false);
        clock.advance(1000);
        assert.equal(await request, false);
        assert.equal(line.transaction_id, false);
        assert.equal(paymentActions(line).retrySafe, true);
        assert.equal(paymentResponseSuccessful(line, true), false);
        assert.deepEqual(errors, [final]);
        assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
    });
}

test("valid processing times out and a later check recovers capture without starting again", async () => {
    let captured = false;
    const { state, clock, order, line, calls, errors } = fixture({
        call(method) {
            if (method === "revolut_start_payment" || method === "revolut_poll_payment") {
                return {
                    operation_id: 72, state: captured ? "verified" : "pending",
                    provider_state: captured ? "captured" : "authentication_challenge",
                    payment_id: "pay-72", order_id: "rev-72",
                };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    clock.advance(60000);
    assert.equal(await request, false);
    assert.deepEqual(errors, ["timed_out"]);
    assert.equal(line.transaction_id, false);
    assert.equal(paymentActions(line).retrySafe, false);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    assert.equal(calls.filter(({ method }) => method === "revolut_mark_timeout").length, 1);
    captured = true;
    assert.equal(await state.request(order, line, { checkOnly: true }), true);
    assert.equal(line.transaction_id, "pay-72");
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("unresolved evidence stops foreground polling even with a prior documented processing state", async () => {
    const { state, clock, order, line, calls, errors } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                return { operation_id: 73, state: "pending", provider_state: "authentication_verified" };
            }
            if (method === "revolut_poll_payment") {
                return { operation_id: 73, state: "unresolved", provider_state: "authentication_verified" };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    clock.advance(1000);
    assert.equal(await request, false);
    clock.advance(60000);
    await tick();
    assert.deepEqual(errors, ["unresolved"]);
    assert.equal(paymentActions(line).retrySafe, false);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(paymentResponseSuccessful(line, true), false);
    assert.equal(calls.filter(({ method }) => method === "revolut_poll_payment").length, 1);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("definitive terminal-busy rejection leaves the same unpaid line removable", async () => {
    const { state, clock, order, line, calls, errors } = fixture({
        call(method) {
            return method === "revolut_start_payment" ? busyRejection : false;
        },
    });
    const request = state.request(order, line);
    await tick();
    clock.advance(60000);
    assert.equal(await request, false);
    line.setPaymentStatus("retry");
    assert.equal(paymentOutcome(line), "terminal_busy");
    assert.deepEqual(errors, ["terminal_busy"]);
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(paymentActions(line).retrySafe, true);
    assert.equal(orderActions(order).blocksAlternativeTender, false);
    assert.equal(paymentResponseSuccessful(line, true), false);
    assert.equal(line.transaction_id, false);
    assert.equal(line.uuid, "line-1");
    assert.equal(order.uuid, "order-1");
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("terminal-busy status checks stay read-only and explicit resume preserves restored identity", async () => {
    let busy = true;
    const { state, order, line, calls } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                return busy ? busyRejection : {
                    operation_id: 60, state: "verified", payment_id: "pay-60", order_id: "rev-60",
                };
            }
            return false;
        },
    });
    const rejected = state.request(order, line);
    assert.equal(state.request(order, line), rejected);
    assert.equal(await rejected, false);
    line.setPaymentStatus("retry");
    restorePaymentLine(line);
    const restored = { ...line, uiState: structuredClone(line.uiState) };
    order.payment_ids = [restored];
    assert.equal(await state.request(order, restored, { checkOnly: true }), false);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
    assert.equal(paymentOutcome(restored), "terminal_busy");
    assert.equal(paymentActions(restored).canDelete, true);
    busy = false;
    assert.equal(await state.request(order, restored, { checkOnly: true }), false);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
    const resumed = state.request(order, restored);
    assert.equal(state.request(order, restored), resumed);
    assert.equal(await resumed, true);
    assert.equal(restored.transaction_id, "pay-60");
    assert.equal(restored.payment_ref_no, "rev-60");
    assert.equal(order.uuid, "order-1");
    assert.equal(restored.uuid, "line-1");
    assert.deepEqual(calls.filter(({ method }) => method === "revolut_start_payment")
        .map(({ args }) => args.slice(2, 4)), [["order-1", "line-1"], ["order-1", "line-1"]]);
});

test("repeated explicit busy starts stay removable and report each definitive rejection", async () => {
    const { state, order, line, errors, calls } = fixture({
        call(method) {
            return method === "revolut_start_payment" ? busyRejection : false;
        },
    });
    assert.equal(await state.request(order, line), false);
    assert.equal(await state.request(order, line), false);
    assert.equal(paymentActions(line).canDelete, true);
    assert.deepEqual(errors, ["terminal_busy", "terminal_busy"]);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 2);
});

test("a busy replacement preserves its safe predecessor through restoration and explicit resume", async () => {
    let starts = 0;
    const { state, order, line, calls } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                starts += 1;
                if (starts === 1) {
                    return { operation_id: 61, state: "declined", retry_safe: true };
                }
                if (starts === 2) {
                    return { ...busyRejection, previous_operation_id: 61 };
                }
                return { operation_id: 62, state: "verified", payment_id: "pay-62", order_id: "rev-62" };
            }
            return false;
        },
    });
    assert.equal(await state.request(order, line), false);
    assert.equal(await state.request(order, line), false);
    line.setPaymentStatus("retry");
    restorePaymentLine(line);
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    assert.equal(starts, 2);
    assert.equal(await state.request(order, line), true);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment")[2].args[6], 61);
    assert.equal(line.transaction_id, "pay-62");
});

for (const [reason, response] of [
    ["transport exception with busy text", new Error("An existing Revolut payment blocks this order or terminal.")],
    ["missing response", false],
    ["different order", { ...busyRejection, order_uuid: "other-order" }],
    ["different payment line", { ...busyRejection, payment_line_uuid: "other-line" }],
    ["different predecessor", { ...busyRejection, previous_operation_id: 61 }],
    ["missing dispatch proof", { ...busyRejection, dispatched: undefined }],
    ["possible dispatch", { ...busyRejection, dispatched: true }],
    ["surviving provider reference", { ...busyRejection, order_id: "rev-uncertain" }],
]) {
    test(`${reason} cannot establish a safe terminal-busy rejection`, async () => {
        const { state, order, line, calls, errors } = fixture({
            call(method) {
                if (method === "revolut_start_payment") {
                    if (response instanceof Error) {
                        throw response;
                    }
                    return response;
                }
                return false;
            },
        });
        assert.equal(await state.request(order, line), false);
        line.setPaymentStatus("retry");
        restorePaymentLine(line);
        assert.equal(await state.request(order, line, { checkOnly: true }), false);
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(paymentActions(line).retrySafe, false);
        assert.equal(orderActions(order).blocksCheckout, true);
        assert.equal(orderActions(order).blocksAlternativeTender, true);
        assert.deepEqual(errors, ["interrupted"]);
        assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
    });
}

test("a start rejection from lookup cannot clear an uncertain start", async () => {
    const { state, order, line, calls } = fixture({
        call(method) {
            return method === "revolut_find_payment" ? busyRejection : false;
        },
    });
    line.uiState.revolutStarted = true;
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    assert.equal(paymentOutcome(line), "interrupted");
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(calls.some(({ method }) => method === "revolut_start_payment"), false);
});

test("a discovered operation overrides earlier terminal-busy recovery", async () => {
    let finds = 0;
    const { state, order, line, calls } = fixture({
        call(method) {
            if (method === "revolut_start_payment") {
                return busyRejection;
            }
            if (method === "revolut_find_payment" && ++finds > 1) {
                return { operation_id: 63, state: "pending", provider_state: "processing" };
            }
            if (method === "revolut_poll_payment") {
                return { operation_id: 63, state: "unresolved", provider_state: "processing" };
            }
            return false;
        },
    });
    assert.equal(await state.request(order, line), false);
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    line.setPaymentStatus("retry");
    restorePaymentLine(line);
    assert.equal(line.uiState.revolutOperationId, 63);
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(paymentActions(line).canEditAmount, false);
    assert.equal(paymentActions(line).retrySafe, false);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("a late terminal-busy start response cannot clear a foreground timeout", async () => {
    const start = deferred();
    const { state, clock, order, line, calls } = fixture({
        call(method) {
            return method === "revolut_start_payment" ? start.promise : false;
        },
    });
    const request = state.request(order, line);
    await tick();
    clock.advance(60000);
    assert.equal(await request, false);
    start.resolve(busyRejection);
    await tick();
    assert.equal(paymentOutcome(line), "timed_out");
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
});

test("the payment busy contract cannot unlock a dispatched refund", async () => {
    const { state, order, line, calls } = fixture({
        refund: true,
        chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
        call(method) {
            if (method === "revolut_refund_sources") {
                return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
            }
            return method === "revolut_start_refund" ? busyRejection : false;
        },
    });
    assert.equal(await state.request(order, line), false);
    line.setPaymentStatus("retry");
    restorePaymentLine(line);
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_refund").length, 1);
});

for (const refund of [false, true]) {
    test(`${refund ? "refund" : "payment"} discovery rejection can resume one first start on the same line`, async () => {
        let finds = 0;
        const { state, order, line, calls, errors } = fixture({
            refund,
            chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
            call(method) {
                if (method === `revolut_find_${refund ? "refund" : "payment"}` && ++finds === 1) {
                    throw new Error("read-only lookup unavailable");
                }
                if (method === "revolut_refund_sources") {
                    return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                }
                if (method === `revolut_start_${refund ? "refund" : "payment"}`) {
                    return { operation_id: 50, state: "verified", payment_id: "paid-50", order_id: "rev-50" };
                }
                return false;
            },
        });
        assert.equal(await state.request(order, line), false);
        line.setPaymentStatus("retry");
        assert.deepEqual(order.payment_ids, [line]);
        assert.equal(paymentActions(line).canDelete, true);
        assert.equal(paymentActions(line).canEditAmount, true);
        assert.equal(orderActions(order).blocksAlternativeTender, false);
        assert.equal(paymentActions(line).retrySafe, true);
        assert.deepEqual(errors, ["discovery_interrupted"]);
        restorePaymentLine(line);
        assert.equal(await state.request(order, line), true);
        assert.equal(order.uuid, "order-1");
        assert.equal(line.uuid, "line-1");
        assert.equal(line.transaction_id, "paid-50");
        assert.equal(line.payment_ref_no, "rev-50");
        const starts = calls.filter(({ method }) => method.includes("revolut_start_"));
        assert.equal(starts.length, 1);
        assert.deepEqual(starts[0].args.slice(2, 4), ["order-1", "line-1"]);
    });

    test(`${refund ? "refund" : "payment"} discovery timeout unlocks preparation and ignores its late result`, async () => {
        const lookup = deferred();
        let finds = 0;
        const { state, clock, order, line, calls, errors } = fixture({
            refund,
            chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
            call(method) {
                if (method === `revolut_find_${refund ? "refund" : "payment"}`) {
                    return ++finds === 1 ? lookup.promise : false;
                }
                if (method === "revolut_refund_sources") {
                    return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                }
                if (method === `revolut_start_${refund ? "refund" : "payment"}`) {
                    return { operation_id: 51, state: "verified", payment_id: "paid-51", order_id: "rev-51" };
                }
                return false;
            },
        });
        const first = state.request(order, line);
        assert.equal(state.request(order, line), first);
        await tick();
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(paymentActions(line).canEditAmount, false);
        assert.equal(orderActions(order).blocksAlternativeTender, true);
        assert.equal(orderActions(order).blocksCheckout, true);
        clock.advance(60000);
        assert.equal(await first, false);
        line.setPaymentStatus("retry");
        assert.deepEqual(errors, ["discovery_timed_out"]);
        assert.equal(paymentActions(line).canDelete, true);
        assert.equal(orderActions(order).blocksAlternativeTender, false);
        assert.equal(orderActions(order).blocksCheckout, false);
        assert.equal(paymentResponseSuccessful(line, true), false);
        assert.equal(calls.some(({ method }) => method.includes("revolut_start_")), false);
        restorePaymentLine(line);
        const resumed = state.request(order, line);
        assert.equal(state.request(order, line), resumed);
        assert.equal(await resumed, true);
        lookup.resolve({ operation_id: 99, state: "verified", payment_id: "stale", order_id: "stale" });
        await tick();
        assert.equal(line.transaction_id, "paid-51");
        assert.equal(line.payment_ref_no, "rev-51");
        assert.equal(calls.filter(({ method }) => method.includes("revolut_start_")).length, 1);
        assert.equal(line.uuid, "line-1");
    });

    test(`${refund ? "refund" : "payment"} cancellation racing initial discovery prevents a first start`, async () => {
        const lookup = deferred();
        const { state, order, line, calls } = fixture({
            refund,
            call(method) {
                if (method.includes("revolut_find_")) {
                    return lookup.promise;
                }
                if (method === "revolut_refund_sources") {
                    return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                }
                if (method.includes("revolut_start_")) {
                    return { operation_id: 52, state: "verified", payment_id: "paid-52", order_id: "rev-52" };
                }
                return false;
            },
            chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
        });
        const request = state.request(order, line);
        await tick();
        const cancellation = state.cancel(order, line);
        lookup.resolve(false);
        assert.equal(await request, false);
        assert.equal(await cancellation, true);
        assert.equal(paymentActions(line).canDelete, true);
        assert.equal(line.transaction_id, false);
        assert.equal(calls.filter(({ method }) => method.includes("revolut_find_")).length, 1);
        assert.equal(calls.some(({ method }) => method.includes("revolut_start_") ||
            method === "revolut_cancel_payment"), false);
    });

    test(`${refund ? "refund" : "payment"} resumed discovery restores an existing operation before any start`, async () => {
        let finds = 0;
        const { state, order, line, calls } = fixture({
            refund,
            call(method) {
                if (method.includes("revolut_find_")) {
                    if (++finds === 1) {
                        throw new Error("lookup unavailable");
                    }
                    return { operation_id: 53, state: "pending", order_id: "rev-53" };
                }
                if (method.includes("revolut_poll_")) {
                    if (finds === 2) {
                        throw new Error("poll unavailable after discovery");
                    }
                    return { operation_id: 53, state: "verified", payment_id: "paid-53", order_id: "rev-53" };
                }
                return false;
            },
        });
        assert.equal(await state.request(order, line), false);
        line.setPaymentStatus("retry");
        restorePaymentLine(line);
        assert.equal(await state.request(order, line), false);
        assert.equal(line.uiState.revolutOperationId, 53);
        assert.equal(line.uiState.revolutSnapshot.order_id, "rev-53");
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(orderActions(order).blocksAlternativeTender, true);
        finds = 3;
        assert.equal(await state.request(order, line), true);
        assert.equal(line.payment_ref_no, "rev-53");
        assert.equal(calls.some(({ method }) => method.includes("revolut_start_")), false);
    });

    test(`${refund ? "refund" : "payment"} lost start response and empty discovery never unlock uncertain money`, async () => {
        const { state, order, line, calls } = fixture({
            refund,
            chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
            call(method) {
                if (method === "revolut_refund_sources") {
                    return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                }
                if (method.includes("revolut_start_")) {
                    throw new Error("response lost after dispatch");
                }
                return false;
            },
        });
        assert.equal(await state.request(order, line), false);
        line.setPaymentStatus("retry");
        restorePaymentLine(line);
        assert.equal(await state.request(order, line), false);
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(paymentActions(line).canEditAmount, false);
        assert.equal(paymentActions(line).retrySafe, false);
        assert.equal(orderActions(order).blocksCheckout, true);
        assert.equal(orderActions(order).blocksAlternativeTender, true);
        assert.equal(calls.filter(({ method }) => method.includes("revolut_start_")).length, 1);
        assert.equal(line.uuid, "line-1");
    });

    if (refund) {
        test("authoritative refund absence proof unlocks only the same undispatched line", async () => {
            const { state, order, line, calls, errors } = fixture({
                refund: true,
                chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
                call(method) {
                    if (method === "revolut_refund_sources") {
                        return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                    }
                    if (method === "revolut_start_refund") {
                        throw new Error("reservation rejected before dispatch");
                    }
                    if (method === "revolut_confirm_refund_absence") {
                        return {
                            dispatched: false, start_rejected: "no_refund_attempt",
                            order_uuid: order.uuid, payment_line_uuid: line.uuid,
                        };
                    }
                    return false;
                },
            });
            assert.equal(await state.request(order, line), false);
            assert.equal(paymentActions(line).canDelete, false);
            assert.equal(await state.request(order, line, { checkOnly: true }), false);
            assert.equal(paymentActions(line).canDelete, true);
            assert.equal(paymentActions(line).retrySafe, true);
            assert.equal(orderActions(order).blocksCheckout, false);
            assert.equal(line.uiState.revolutOriginalOperationId, false);
            assert.equal(line.uuid, "line-1");
            assert.equal(calls.filter(({ method }) => method === "revolut_start_refund").length, 1);
            assert.equal(calls.filter(({ method }) => method === "revolut_confirm_refund_absence").length, 1);
            assert.deepEqual(calls.find(({ method }) => method === "revolut_confirm_refund_absence").args,
                [[7], order.uuid, line.uuid, state.sessionId]);
            assert.equal(errors.at(-1), "no_refund_attempt");
        });

        test("refund absence proof for a different line never unlocks the uncertain line", async () => {
            const { state, order, line, calls } = fixture({
                refund: true,
                chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
                call(method) {
                    if (method === "revolut_refund_sources") {
                        return [{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }];
                    }
                    if (method === "revolut_start_refund") {
                        throw new Error("response lost after dispatch");
                    }
                    if (method === "revolut_confirm_refund_absence") {
                        return {
                            dispatched: false, start_rejected: "no_refund_attempt",
                            order_uuid: order.uuid, payment_line_uuid: "another-line",
                        };
                    }
                    return false;
                },
            });
            assert.equal(await state.request(order, line), false);
            assert.equal(await state.request(order, line, { checkOnly: true }), false);
            assert.equal(paymentActions(line).canDelete, false);
            assert.equal(orderActions(order).blocksCheckout, true);
            assert.equal(calls.filter(({ method }) => method === "revolut_start_refund").length, 1);
        });
    }

    test(`${refund ? "refund" : "payment"} restored legacy waiting state stays protected when discovery is empty`, async () => {
        const { state, order, line, calls } = fixture({
            refund,
            call(method) {
                return method.includes("revolut_start_")
                    ? { operation_id: 54, state: "verified", payment_id: "paid-54", order_id: "rev-54" }
                    : false;
            },
        });
        line.setPaymentStatus("waiting");
        restorePaymentLine(line);
        // Odoo changes the status before invoking the terminal interface.
        line.setPaymentStatus("waiting");
        assert.equal(await state.request(order, line), false);
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(orderActions(order).blocksAlternativeTender, true);
        assert.equal(calls.some(({ method }) => method.includes("revolut_start_")), false);
    });

    test(`${refund ? "refund" : "payment"} surviving transaction evidence overrides undispatched preparation`, async () => {
        const { state, order, line, calls } = fixture({ refund });
        line.uiState.revolutUndispatched = true;
        line.payment_ref_no = "surviving-reference";
        assert.equal(await state.request(order, line), false);
        assert.equal(line.payment_ref_no, "surviving-reference");
        assert.equal(paymentActions(line).canDelete, false);
        assert.equal(paymentActions(line).retrySafe, false);
        assert.equal(orderActions(order).blocksCheckout, true);
        assert.equal(calls.some(({ method }) => method.includes("revolut_start_")), false);
    });
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

test("refund balance discovery stays guarded and dismissal cannot dispatch its late allocation", async () => {
    const sources = deferred();
    const { state, order, line, calls } = fixture({
        refund: true,
        call(method) {
            if (method === "revolut_refund_sources") {
                return sources.promise;
            }
            if (method === "revolut_start_refund") {
                return { operation_id: 55, state: "verified", payment_id: "paid-55", order_id: "rev-55" };
            }
            return false;
        },
        chooseAllocation: async () => ({ operationId: 10, amount: 12.34 }),
    });
    const request = state.request(order, line);
    await tick();
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    const cancellation = state.cancel(order, line);
    sources.resolve([{ operation_id: 10, payment_method_id: 7, remaining_minor: 1234 }]);
    assert.equal(await request, false);
    assert.equal(await cancellation, true);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
    assert.equal(paymentActions(line).canDelete, true);
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

test("lost refund response and failed original read keep the same line for recovery", async () => {
    let originalReads = 0;
    const { state, order, line, calls, errors, preparationErrors } = fixture({
        refund: true,
        async restoreRefundOriginals() {
            if (++originalReads === 1) {
                throw new Error("original sale temporarily unavailable");
            }
        },
        call(method) {
            if (method === "revolut_find_refund") {
                return { operation_id: 32, state: "unresolved", original_order_id: "sale-32" };
            }
            if (method === "revolut_poll_refund") {
                return { operation_id: 32, state: "verified", payment_id: "refund-32",
                    order_id: "rev-refund-32", original_order_id: "sale-32" };
            }
            return false;
        },
    });
    line.uiState.revolutStarted = true;
    line.uiState.revolutOriginalOperationId = 12;
    restorePaymentLine(line);
    assert.equal(await state.request(order, line), false);
    assert.deepEqual(order.payment_ids, [line]);
    assert.equal(order.uuid, "order-1");
    assert.equal(line.uuid, "line-1");
    assert.equal(line.uiState.revolutOriginalOperationId, 12);
    assert.equal(paymentOutcome(line), "interrupted");
    assert.deepEqual(errors, ["interrupted"]);
    assert.deepEqual(preparationErrors, []);
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.deepEqual(calls, []);

    assert.equal(await state.request(order, line), true);
    assert.equal(line.transaction_id, "refund-32");
    assert.equal(line.payment_ref_no, "rev-refund-32");
    assert.equal(line.uiState.revolutOperationId, 32);
    assert.deepEqual(calls.map(({ method }) => method), ["revolut_find_refund", "revolut_poll_refund"]);
    assert.deepEqual(calls.map(({ args }) => args.slice(1, 4)), [
        ["order-1", "line-1"], [32, "order-1", "line-1"],
    ]);
});

test("surviving refund reference protects a line without a local start snapshot", async () => {
    let originalReads = 0;
    let finds = 0;
    const { state, order, line, calls, errors } = fixture({
        refund: true,
        async restoreRefundOriginals() {
            if (++originalReads === 1) {
                throw new Error("original sale unavailable");
            }
        },
        call(method) {
            if (method === "revolut_find_refund") {
                return ++finds === 1 ? false : { operation_id: 43, state: "pending" };
            }
            if (method === "revolut_poll_refund") {
                return { operation_id: 43, state: "verified", payment_id: "refund-43",
                    order_id: "rev-refund-43" };
            }
            return false;
        },
    });
    line.uiState.revolutOriginalOperationId = 12;
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(orderActions(order).blocksAlternativeTender, true);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(await state.request(order, line), false);
    assert.deepEqual(order.payment_ids, [line]);
    assert.equal(paymentOutcome(line), "interrupted");
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(await state.request(order, line), false);
    assert.deepEqual(errors, ["interrupted"]);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
    assert.equal(await state.request(order, line), true);
    assert.equal(line.payment_ref_no, "rev-refund-43");
    assert.deepEqual(calls.map(({ method }) => method), [
        "revolut_find_refund", "revolut_confirm_refund_absence",
        "revolut_find_refund", "revolut_poll_refund",
    ]);
});

test("known refund reference survives an original-read timeout and is polled on retry", async () => {
    let originalReads = 0;
    const { state, order, line, calls, errors, preparationErrors } = fixture({
        refund: true,
        async restoreRefundOriginals() {
            if (++originalReads === 1) {
                throw new ForegroundTimeout();
            }
        },
        call(method) {
            if (method === "revolut_poll_refund") {
                return { operation_id: 44, state: "verified", payment_id: "refund-44",
                    order_id: "rev-refund-44", original_order_id: "sale-44" };
            }
            return false;
        },
    });
    line.uiState.revolutStarted = true;
    line.uiState.revolutOperationId = 44;
    line.uiState.revolutSnapshot = { operation_id: 44, state: "unresolved",
        order_id: "rev-refund-44", original_order_id: "sale-44" };
    assert.equal(await state.request(order, line), false);
    assert.deepEqual(order.payment_ids, [line]);
    assert.equal(line.uiState.revolutSnapshot.order_id, "rev-refund-44");
    assert.equal(line.uiState.revolutOperationId, 44);
    assert.equal(paymentOutcome(line), "timed_out");
    assert.deepEqual(errors, ["timed_out"]);
    assert.deepEqual(preparationErrors, []);
    assert.equal(paymentActions(line).canDelete, false);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(await state.request(order, line), true);
    assert.equal(line.payment_ref_no, "rev-refund-44");
    assert.deepEqual(calls.map(({ method }) => method), [
        "revolut_mark_refund_timeout", "revolut_poll_refund",
    ]);
    assert.equal(calls.some(({ method }) => method === "revolut_start_refund"), false);
});

test("original-read failure before refund dispatch dismisses the allocation", async () => {
    const { state, order, line, calls, errors, preparationErrors } = fixture({
        refund: true,
        async restoreRefundOriginals() { throw new Error("original sale unavailable"); },
    });
    assert.equal(await state.request(order, line), false);
    assert.deepEqual(order.payment_ids, []);
    assert.deepEqual(preparationErrors, ["originals"]);
    assert.deepEqual(errors, []);
    assert.deepEqual(calls, []);
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


test("cancelling payment preparation settles the native screen without dispatch or timeout", async () => {
    const prepared = deferred();
    const { state, clock, order, line, calls } = fixture({
        preparePayment: () => prepared.promise,
        call(method) {
            if (method === "revolut_start_payment") {
                return { operation_id: 80, state: "pending", order_id: "rev-80" };
            }
            return false;
        },
    });
    let busy = true;
    let requestResult;
    let cancelResult;
    const request = state.screenRequest(order, line, () => state.request(order, line))
        .then((result) => { requestResult = result; });
    await tick();
    const cancellation = state.screenCancel(order, line,
        () => { throw new Error("Cancellation must not resume an undispatched payment"); },
        () => { busy = false; }).then((result) => { cancelResult = result; });
    prepared.resolve({ status: "prepared", authorization_id: 1, cart_version: 1, tender_revision: 1 });
    await tick();
    assert.deepEqual(calls.map(({ method }) => method), ["revolut_find_payment"]);
    assert.equal(requestResult, false);
    assert.equal(cancelResult, true);
    await Promise.all([request, cancellation]);
    assert.equal(clock.now(), 0);
    assert.equal(busy, false);
    assert.equal(line.getPaymentStatus(), "retry");
    assert.equal(line.uiState.revolutUndispatched, true);
    assert.equal(line.uiState.revolutDiscovering, false);
    assert.equal(paymentActions(line).canDelete, true);
    assert.equal(paymentActions(line).canEditAmount, true);
    assert.equal(orderActions(order).blocksAlternativeTender, false);
    assert.equal(line.transaction_id, false);
});

test("cancelling explicit retry preparation preserves the prior final attempt without provider mutation", async () => {
    const prepared = deferred();
    const previous = { operation_id: 79, state: "declined", retry_safe: true,
        order_id: "rev-79", payment_id: "declined-79", provider_state: "declined" };
    const { state, clock, order, line, calls, errors } = fixture({
        preparePayment: () => prepared.promise,
        call(method) {
            if (method === "revolut_cancel_payment") {
                return { ...previous, state: "cancelled", provider_state: "cancelled" };
            }
            if (method === "revolut_start_payment") {
                return { operation_id: 82, state: "verified", order_id: "rev-82", payment_id: "paid-82" };
            }
            return false;
        },
    });
    line.uiState.revolutSnapshot = previous;
    line.uiState.revolutOperationId = previous.operation_id;
    line.setPaymentStatus("retry");
    const request = state.request(order, line);
    await tick();
    const cancellation = state.cancel(order, line);
    assert.equal(state.cancel(order, line), cancellation);
    prepared.resolve({ status: "prepared", authorization_id: 1, cart_version: 1, tender_revision: 1 });
    assert.equal(await request, false);
    assert.equal(await cancellation, true);
    assert.deepEqual(calls, []);
    assert.deepEqual(errors, []);
    assert.equal(clock.now(), 0);
    assert.equal(line.uiState.revolutSnapshot, previous);
    assert.equal(line.uiState.revolutOperationId, 79);
    assert.equal(line.uiState.revolutPreviousOperationId, undefined);
    assert.equal(paymentOutcome(line), "declined");
    assert.equal(paymentActions(line).retrySafe, true);
    assert.equal(paymentActions(line).canDelete, true);
    restorePaymentLine(line);
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    assert.deepEqual(calls, []);
    const resumed = state.request(order, line);
    assert.equal(state.request(order, line), resumed);
    assert.equal(await resumed, true);
    assert.deepEqual(calls.map(({ method }) => method), ["revolut_start_payment"]);
    assert.equal(calls[0].args[6], 79);
    assert.equal(previous.state, "declined");
    assert.equal(line.uiState.revolutSnapshot.operation_id, 82);
    assert.equal(line.transaction_id, "paid-82");
});

for (const priorAttempt of [false, true]) {
    for (const failure of ["rejected", "review_required", "timed_out"]) {
        test(`cancelled ${priorAttempt ? "retry" : "fresh"} preparation ${failure} never dispatches a late result`, async () => {
            const prepared = deferred();
            const previous = { operation_id: 78, state: "failed", retry_safe: true, order_id: "rev-78" };
            const { state, clock, order, line, calls } = fixture({
                preparePayment: () => prepared.promise,
            });
            if (priorAttempt) {
                line.uiState.revolutSnapshot = previous;
                line.uiState.revolutOperationId = 78;
                line.setPaymentStatus("retry");
            }
            const request = state.request(order, line);
            await tick();
            const cancellation = state.cancel(order, line);
            assert.equal(state.cancel(order, line), cancellation);
            if (failure === "rejected") {
                prepared.reject(new Error("Draft persistence failed"));
            } else if (failure === "review_required") {
                prepared.resolve({ status: "review_required", message: "Review the canonical cart" });
            } else {
                clock.advance(60000);
            }
            assert.equal(await request, false);
            assert.equal(await cancellation, true);
            assert.equal(line.uiState.revolutDiscovering, false);
            assert.equal(paymentActions(line).canDelete, true);
            assert.equal(paymentActions(line).retrySafe, true);
            if (priorAttempt) {
                assert.equal(line.uiState.revolutSnapshot, previous);
                assert.equal(line.uiState.revolutOperationId, 78);
            } else {
                assert.equal(line.uiState.revolutUndispatched, true);
                assert.equal(line.uiState.revolutStarted, false);
                assert.equal(line.transaction_id, false);
            }
            if (failure === "timed_out") {
                prepared.resolve({ status: "prepared", authorization_id: 1, cart_version: 1, tender_revision: 1 });
                await tick();
            }
            assert.deepEqual(calls.map(({ method }) => method), priorAttempt ? [] : ["revolut_find_payment"]);
        });
    }
}

test("a cancelled preparation stays undispatched through check and reload until one explicit resume", async () => {
    const prepared = deferred();
    const { state, clock, order, line, calls } = fixture({
        preparePayment: () => prepared.promise,
        call(method) {
            if (method === "revolut_start_payment") {
                return { operation_id: 81, state: "verified", order_id: "rev-81", payment_id: "paid-81" };
            }
            return false;
        },
    });
    const request = state.request(order, line);
    await tick();
    const cancellation = state.cancel(order, line);
    assert.equal(state.cancel(order, line), cancellation);
    prepared.resolve({ status: "prepared", authorization_id: 1, cart_version: 1, tender_revision: 1 });
    assert.equal(await request, false);
    assert.equal(await cancellation, true);
    assert.equal(await state.cancel(order, line), true);
    line.setPaymentStatus("retry");
    assert.equal(paymentOutcome(line), "discovery_cancelled");
    assert.equal(await state.request(order, line, { checkOnly: true }), false);
    const reloaded = { ...line, uiState: { ...line.uiState } };
    order.payment_ids = [reloaded];
    restorePaymentLine(reloaded);
    assert.equal(await state.request(order, reloaded, { checkOnly: true }), false);
    assert.equal(calls.some(({ method }) => method !== "revolut_find_payment"), false);
    const resumed = state.screenRequest(order, reloaded, () => state.request(order, reloaded));
    const repeated = state.screenRequest(order, reloaded, () => state.request(order, reloaded));
    assert.deepEqual(await Promise.all([resumed, repeated]), [true, true]);
    assert.equal(calls.filter(({ method }) => method === "revolut_start_payment").length, 1);
    assert.equal(reloaded.transaction_id, "paid-81");
    assert.equal(reloaded.payment_ref_no, "rev-81");
    assert.equal(reloaded.uuid, "line-1");
    assert.equal(clock.now(), 0);
});

test("preparation rejection keeps an untouched line editable and sends no start", async () => {
    const {state, order, line, calls, errors} = fixture({
        preparePayment: async () => { throw new Error("Review the canonical cart"); },
    });
    assert.equal(await state.request(order,line),false);
    assert.equal(calls.some(({method}) => method === "revolut_start_payment"),false);
    assert.equal(line.uiState.revolutUndispatched,true);
    assert.equal(line.uiState.revolutStarted,false);
    assert.equal(paymentActions(line).canEditAmount,true);
    assert.equal(paymentActions(line).canDelete,true);
    assert.equal(paymentActions(line).blocksCheckout,false);
    assert.equal(paymentOutcome(line),"authority_required");
    assert.deepEqual(errors,["authority_required"]);
});

test("verified checkout waits for the canonical gross and tip projection", async () => {
    const projection = deferred();
    const {state, order, line, calls} = fixture({
        projectVerified: async () => projection.promise,
        call(method) {
            if (method === "revolut_start_payment") {
                return {operation_id:1,state:"verified",payment_id:"captured",order_id:"provider-order"};
            }
            return false;
        },
    });
    let finished = false;
    const request = state.request(order,line).then((result) => {finished=true;return result;});
    await tick();
    assert.equal(finished,false);
    assert.equal(line.transaction_id,false);
    assert.equal(calls.filter(({method})=>method==="revolut_start_payment").length,1);
    projection.resolve();
    assert.equal(await request,true);
    assert.equal(line.transaction_id,"captured");
});

test("a deferred unresolved status stays guarded until a fresh late capture", async () => {
    let polls = 0;
    const { state, clock, order, line, calls, errors } = fixture({
        call(method) {
            if (method === "revolut_find_payment") {
                return { operation_id: 74, state: "unresolved", retry_safe: false };
            }
            if (method === "revolut_poll_payment") {
                polls++;
                return polls === 1
                    ? { operation_id: 74, state: "unresolved", observation_deferred: true, retry_safe: false }
                    : { operation_id: 74, state: "verified", payment_id: "pay-74", order_id: "rev-74" };
            }
            return false;
        },
    });
    line.uiState.revolutStarted = true;
    let finished = false;
    const request = state.request(order, line, { checkOnly: true }).then((result) => {
        finished = true;
        return result;
    });
    await tick();
    clock.advance(999);
    await tick();
    assert.equal(finished, false);
    assert.equal(paymentActions(line).retrySafe, false);
    assert.equal(orderActions(order).blocksCheckout, true);
    assert.equal(line.transaction_id, false);
    assert.deepEqual(errors, []);
    clock.advance(1);
    assert.equal(await request, true);
    assert.equal(line.transaction_id, "pay-74");
    assert.equal(polls, 2);
    assert.equal(calls.some(({ method }) => method === "revolut_start_payment"), false);
});

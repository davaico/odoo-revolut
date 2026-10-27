import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { isRevolutRefund, paymentActions, orderActions } from "../src/app/revolut_payment_state.js";

const source = readFileSync(new URL("../src/app/payment_revolut.js", import.meta.url), "utf8");
const method = source.split("patch(PaymentScreen.prototype, {")[1]
    .split("    async sendPaymentRequest(")[0].trim().replace(/,$/, "");
assert.match(method, /^async validateOrder\(\)/);
const createPatch = new Function("isRevolutRefund", "paymentActions", "orderActions",
    "restoreRefundOriginals", "AlertDialog", "_t", `return { ${method} };`);

function fixture(count = 1) {
    const events = [];
    const order = { state: "draft", payment_ids: [] };
    const screen = { currentOrder: order, pos: {}, dialog: { add() { events.push("blocked"); } } };
    const hooks = { originals: async () => {}, restore: async () => {} };
    for (let index = 1; index <= count; index++) {
        const snapshot = { state: "verified", operation_id: index,
            payment_id: `refund-${index}`, order_id: `refund-${index}` };
        const line = {
            amount: -5, pos_order_id: order, transaction_id: false, payment_ref_no: false,
            payment_status: "retry", uiState: { revolutSnapshot: snapshot,
                revolutOperationId: index, revolutCheckoutRestored: false },
            getPaymentStatus() { return this.payment_status; },
            setPaymentStatus(status) { this.payment_status = status; },
            payment_method_id: { use_payment_terminal: "revolut", payment_terminal: {
                paymentState: { async restore(current, target) {
                    events.push(`restore-${index}`);
                    for (const sibling of current.payment_ids) {
                        sibling.transaction_id = false;
                        sibling.payment_ref_no = false;
                    }
                    target.uiState.revolutCheckoutRestored = true;
                    await hooks.restore(current, target, index);
                } },
                _setVerifiedReferences(target, verified) {
                    events.push(`project-${index}`);
                    target.transaction_id = verified.payment_id;
                    target.payment_ref_no = verified.order_id;
                },
            } },
        };
        order.payment_ids.push(line);
    }
    const patch = createPatch(isRevolutRefund, paymentActions, orderActions,
        async () => { events.push("originals"); await hooks.originals(); }, class {}, (value) => value);
    Object.setPrototypeOf(patch, { validateOrder() { events.push("validate"); return true; } });
    return { order, screen, events, hooks, validate: () => patch.validateOrder.call(screen) };
}

test("all verified refund references are projected after the final shared refresh", async () => {
    const context = fixture(2);
    assert.equal(await context.validate(), true);
    assert.deepEqual(context.events, ["originals", "restore-1", "restore-2", "project-1", "project-2", "validate"]);
    for (const line of context.order.payment_ids) {
        assert.equal(line.transaction_id, line.uiState.revolutSnapshot.payment_id);
        assert.equal(line.payment_ref_no, line.uiState.revolutSnapshot.order_id);
        assert.equal(line.payment_status, "done");
    }
});

for (const active of [false, true]) {
    test(`pending refund blocks validation without disturbing ${active ? "active discovery" : "pending evidence"}`, async () => {
        const context = fixture(2);
        const pending = context.order.payment_ids[1];
        pending.uiState.revolutSnapshot.state = "pending";
        pending.uiState.revolutDiscovering = active;
        pending.uiState.revolutStarting = active;
        const original = structuredClone(pending.uiState);
        assert.equal(await context.validate(), false);
        assert.deepEqual(context.events, ["blocked"]);
        assert.deepEqual(pending.uiState, original);
    });
}

for (const mutation of ["order", "state", "membership", "ownership"]) {
    test(`recovery aborts when ${mutation} changes during its await`, async () => {
        const context = fixture();
        context.hooks.restore = async (order, line) => {
            if (mutation === "order") context.screen.currentOrder = { state: "draft", payment_ids: [] };
            if (mutation === "state") order.state = "paid";
            if (mutation === "membership") order.payment_ids = [];
            if (mutation === "ownership") line.pos_order_id = {};
        };
        assert.equal(await context.validate(), false);
        assert.deepEqual(context.events, ["originals", "restore-1"]);
    });
}

for (const identity of ["snapshot", "operation"]) {
    test(`later refresh cannot project stale ${identity} identity`, async () => {
        const context = fixture(2);
        context.hooks.restore = async (order, line, index) => {
            if (index !== 2) return;
            const first = order.payment_ids[0];
            if (identity === "snapshot") first.uiState.revolutSnapshot = { ...first.uiState.revolutSnapshot };
            else first.uiState.revolutOperationId = 99;
            first.uiState.revolutCheckoutRestored = false;
        };
        assert.equal(await context.validate(), false);
        assert.equal(context.events.includes("project-1"), false);
        assert.equal(context.events.includes("validate"), false);
    });
}

test("ordinary verified sale validates without refund recovery", async () => {
    const context = fixture();
    context.order.payment_ids[0].amount = 5;
    context.order.payment_ids[0].uiState.revolutCheckoutRestored = true;
    assert.equal(await context.validate(), true);
    assert.deepEqual(context.events, ["validate"]);
});

test("a previous checkout restoration failure still requires explicit Check status", async () => {
    const context = fixture();
    const line = context.order.payment_ids[0];
    line.uiState.revolutLocalOutcome = "checkout_restore_failed";
    const original = structuredClone(line.uiState);
    assert.equal(await context.validate(), false);
    assert.deepEqual(context.events, ["blocked"]);
    assert.deepEqual(line.uiState, original);
});

test("order switch while loading original sale aborts before refund restoration", async () => {
    const context = fixture();
    context.hooks.originals = async () => { context.screen.currentOrder = {}; };
    assert.equal(await context.validate(), false);
    assert.deepEqual(context.events, ["originals"]);
});

test("failed canonical restoration leaves checkout blocked", async () => {
    const context = fixture();
    context.hooks.restore = async (order, line) => {
        line.uiState.revolutCheckoutRestored = false;
        line.uiState.revolutLocalOutcome = "checkout_restore_failed";
    };
    assert.equal(await context.validate(), false);
    assert.deepEqual(context.events, ["originals", "restore-1", "blocked"]);
});

test("ordinary cash checkout does not run refund recovery", async () => {
    const context = fixture();
    context.order.payment_ids[0].payment_method_id.use_payment_terminal = false;
    assert.equal(await context.validate(), true);
    assert.deepEqual(context.events, ["validate"]);
});

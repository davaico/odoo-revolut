import assert from "node:assert/strict";
import { test } from "node:test";
import { refundAllowances } from "../src/app/refund_allowances.js";

test("selected source allowances exclude other base and tip allocations without subtracting provider balance twice", () => {
    const source = { remaining_minor: 650, remaining_base_minor: 500, remaining_tip_minor: 150,
        return_base_minor: 1000, return_tip_minor: 200, return_total_minor: 1200 };
    const payments = [
        { uuid: "current", amount: -6.5 },
        { uuid: "cash", amount: -4, payment_method_id: { type: "cash" } },
        { uuid: "card", amount: -1.5, payment_method_id: { use_payment_terminal: "revolut" },
            uiState: { revolutSnapshot: { base_amount_minor: 100, tip_amount_minor: 50 } } },
    ];
    assert.deepEqual(refundAllowances(source, payments, "current", 100), { baseMinor: 500, tipMinor: 150, maximumMinor: 650 });
    assert.deepEqual(refundAllowances({ ...source, remaining_base_minor: 300, remaining_minor: 450 }, payments, "current", 100),
        { baseMinor: 300, tipMinor: 150, maximumMinor: 650 });
});

test("unknown card components conservatively reserve base and tip; positive entries never increase allowance", () => {
    const source = { remaining_minor: 1200, remaining_base_minor: 1000, remaining_tip_minor: 200,
        return_base_minor: 1000, return_tip_minor: 200, return_total_minor: 1200 };
    const payments = [
        { uuid: "unknown", amount: -1.5, payment_method_id: { use_payment_terminal: "revolut" } },
        { uuid: "positive-cash", amount: 10, payment_method_id: { type: "cash" } },
    ];
    assert.deepEqual(refundAllowances(source, payments, "current", 100),
        { baseMinor: 850, tipMinor: 50, maximumMinor: 1050 });
});

test("cash allocations reduce base while leaving the terminal tip allowance available", () => {
    const source = { remaining_minor: 1200, remaining_base_minor: 1000, remaining_tip_minor: 200,
        return_base_minor: 1000, return_tip_minor: 200, return_total_minor: 1200 };
    assert.deepEqual(refundAllowances(source, [{ uuid: "cash", amount: -10 }], "current", 100),
        { baseMinor: 0, tipMinor: 200, maximumMinor: 200 });
});

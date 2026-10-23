import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";

const IDENTITY_KEY = "revolutBusyIdentity";
const CALLS_KEY = "revolutBusyCalls";
const BLOCKER_ORDER_UUID = "d40466e0-2188-41d0-bebb-aa3a93066000";
const BLOCKER_LINE_UUID = "4ca74d24-7b42-451a-91fb-8aca308e2600";

function identity() {
    return JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
}

function calls() {
    return JSON.parse(sessionStorage.getItem(CALLS_KEY) || "[]");
}

function starts() {
    return calls().filter((call) => call.method === "revolut_start_payment" &&
        call.orderUuid === identity().orderUuid);
}

async function preserveInflightSnapshot(pos) {
    // Model reload before the next native 200ms persistence debounce. Save
    // actual in-flight state, never manufacture financial/recovery flags.
    pos.data._debouncedSync.cancel();
    await pos.data.indexedDB.delete("pos.payment", [identity().lineUuid]);
    const writes = [];
    const create = pos.data.indexedDB.create.bind(pos.data.indexedDB);
    pos.data.indexedDB.create = (...args) => {
        const write = create(...args);
        writes.push(write);
        return write;
    };
    pos.data.syncDataWithIndexedDB(pos.data.records);
    await Promise.all(writes);
    pos.data._debouncedSync.cancel();
    pos.data.indexedDB.create = async () => [];
    pos.data.syncDataWithIndexedDB = () => {};
    const stored = (await pos.data.indexedDB.readAll(["pos.payment"]))["pos.payment"]
        .find((line) => line.uuid === identity().lineUuid);
    const state = JSON.parse(stored?.JSONuiState || "{}");
    if (stored?.payment_status !== "waiting" || state.revolutStarted !== true ||
        state.revolutStarting !== true || state.revolutUndispatched !== false) {
        throw new Error("The reload fixture did not persist the actual in-flight payment");
    }
}

function observeRpc() {
    const pos = window.posmodel;
    const call = pos.data.call.bind(pos.data);
    window.revolutBusyRpcs = new Set();
    pos.data.call = (model, method, args, ...rest) => {
        if (model !== "pos.payment.method" || !method.startsWith("revolut_")) {
            return call(model, method, args, ...rest);
        }
        const start = method === "revolut_start_payment";
        const find = method === "revolut_find_payment";
        const orderUuid = args[find ? 1 : 2];
        const lineUuid = args[find ? 2 : 3];
        if (start && orderUuid === identity().orderUuid) {
            const saved = identity();
            if (saved.lineUuid && saved.lineUuid !== lineUuid) {
                throw new Error("Terminal-busy recovery changed the payment-line identity");
            }
            sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({ ...saved, lineUuid }));
        }
        let tracked;
        tracked = call(model, method, args, ...rest).then(async (result) => {
            if (start && orderUuid === identity().orderUuid &&
                identity().persistInflight && starts().length === 1) {
                await preserveInflightSnapshot(pos);
            }
            sessionStorage.setItem(CALLS_KEY, JSON.stringify([
                ...calls(), { method, orderUuid, lineUuid, result },
            ]));
            return result;
        }).finally(() => window.revolutBusyRpcs.delete(tracked));
        window.revolutBusyRpcs.add(tracked);
        return tracked;
    };
}

async function finishRpc() {
    while (window.revolutBusyRpcs.size) {
        await Promise.all([...window.revolutBusyRpcs]);
    }
}

function checkUndispatchedLine() {
    const order = window.posmodel.get_order();
    const saved = identity();
    const line = order.get_paymentline_by_uuid(saved.lineUuid);
    if (order.uuid !== saved.orderUuid || !line || line.is_done() ||
        line.uiState.revolutStarted || line.uiState.revolutOperationId ||
        line.transaction_id || line.payment_ref_no) {
        throw new Error("A definitively busy rejection retained dispatched money or lost identity");
    }
    line.set_amount(10);
    if (line.amount !== 10) {
        throw new Error("The definitively undispatched amount remained locked");
    }
    line.set_amount(12.34);
    for (const request of starts()) {
        const result = request.result;
        if (result?.start_rejected !== "terminal_busy" || result.dispatched !== false ||
            result.order_uuid !== saved.orderUuid || result.payment_line_uuid !== saved.lineUuid ||
            result.previous_operation_id !== false || result.operation_id) {
            throw new Error("Busy feedback lacked authoritative identity-bound non-dispatch proof");
        }
    }
}

function checkStatusTwice() {
    return {
        content: "Repeated Check status calls stay read-only for the rejected line",
        trigger: ".payment-screen .revolut_check_status:contains('Check status')",
        async run() {
            const count = starts().length;
            this.anchor.click();
            this.anchor.click();
            // Odoo schedules the native pay() call after the click handler.
            // Wait for it to enter the adapter, then for the rendered retry
            // state after the real transport and lifecycle have completed.
            await new Promise((resolve) => requestAnimationFrame(resolve));
            await finishRpc();
            await new Promise((resolve) => requestAnimationFrame(resolve));
            if (starts().length !== count) {
                throw new Error("Check status dispatched a new financial start");
            }
            checkUndispatchedLine();
        },
    };
}

function busySaleSteps(persistInflight = false) {
    return [
        Chrome.startPoS(),
        {
            content: "Use a customer order independent of the saved blocker draft",
            trigger: ".product-screen",
            run() {
                const pos = window.posmodel;
                const blocker = pos.models["pos.order"].getBy("uuid", BLOCKER_ORDER_UUID);
                if (!blocker || !Number.isInteger(blocker.id)) {
                    throw new Error("The terminal blocker was not saved as a native draft");
                }
                if (pos.get_order().uuid === BLOCKER_ORDER_UUID) {
                    pos.add_new_order();
                }
            },
        },
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        {
            content: "An independent order reserves the terminal through the real start RPC",
            trigger: ".payment-screen",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                const method = pos.models["pos.payment.method"].getAll().find((paymentMethod) =>
                    paymentMethod.use_payment_terminal === "revolut"
                );
                const saved = {
                    persistInflight,
                    orderUuid: order.uuid,
                    // Native 18 persists the incoming order name as its
                    // receipt number when the new draft is first saved.
                    receiptReference: order.name,
                    blockerOrderUuid: BLOCKER_ORDER_UUID,
                    blockerLineUuid: BLOCKER_LINE_UUID,
                    methodId: method.id,
                };
                const blockerOrder = pos.models["pos.order"].getBy("uuid", BLOCKER_ORDER_UUID);
                if (order.uuid === blockerOrder.uuid || blockerOrder.session_id.id !== pos.session.id) {
                    throw new Error("The blocker must remain a separate order in the original session");
                }
                sessionStorage.setItem(IDENTITY_KEY, JSON.stringify(saved));
                sessionStorage.setItem(CALLS_KEY, "[]");
                observeRpc();
                const prepared = await pos.data.call("pos.order", "revolut_prepare_payment", [
                    blockerOrder.id, saved.blockerOrderUuid, 0,
                    [{ uuid: saved.blockerLineUuid, payment_method_id: method.id, amount: 12.34 }],
                ]);
                if (prepared.status !== "prepared") {
                    throw new Error("The saved blocker did not obtain canonical cart authority");
                }
                const blocker = await pos.data.call("pos.payment.method", "revolut_start_payment", [
                    [method.id], pos.session.id, saved.blockerOrderUuid, saved.blockerLineUuid,
                    12.34, pos.currency.id, false, false,
                    prepared.authorization_id, prepared.cart_version, prepared.tender_revision,
                ]);
                if (!blocker.operation_id || blocker.state !== "pending") {
                    throw new Error("The independent order did not reserve the terminal");
                }
                sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({
                    ...saved, blockerOperationId: blocker.operation_id,
                }));
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".modal:contains('No payment request was sent')" },
        Dialog.confirm(),
        {
            content: "Busy feedback permits editing only after an authoritative non-dispatch result",
            trigger: ".payment-screen .electronic_status:contains('Terminal busy')",
            run: checkUndispatchedLine,
        },
    ].flat();
}

function busyRecoverySteps(persistInflight = false) {
    return [
        ...busySaleSteps(persistInflight),
        checkStatusTwice(),
        {
            content: "Repeated explicit Resume attempts cannot bypass another order's terminal lock",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            run() {
                this.anchor.click();
                this.anchor.click();
            },
        },
        { trigger: ".modal:contains('No payment request was sent')" },
        Dialog.confirm(),
        refresh(),
        Chrome.clickMenuOption("Orders"),
        {
            content: "Reopen the original rejected sale through the native Orders list",
            trigger: ".ticket-screen .order-row",
            async run(helpers) {
                const reference = identity().receiptReference;
                const rows = [...document.querySelectorAll(".ticket-screen .order-row")].filter((row) =>
                    [...row.querySelectorAll(".col")].some((column) => column.textContent.trim() === reference));
                if (rows.length !== 1) {
                    throw new Error("The rejected sale could not be identified by its original receipt number");
                }
                await helpers.dblclick(rows[0]);
            },
        },
        {
            content: "Reconcile a possibly stale in-flight browser snapshot without a new start",
            trigger: ".payment-screen .send_payment_request:contains('Resume'), .payment-screen .send_payment_request:contains('Check status')",
            run() {
                observeRpc();
                window.revolutBusyReloadStartCount = starts().length;
                window.revolutBusyReloadChecked = this.anchor.textContent.trim() === "Check status";
                if (identity().persistInflight && !window.revolutBusyReloadChecked) {
                    throw new Error("An in-flight snapshot must require reconciliation before Resume");
                }
                if (window.revolutBusyReloadChecked) {
                    this.anchor.click();
                }
            },
        },
        {
            content: "Reload preserves definite rejection and editable payment identity",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            run() {
                if (starts().length !== window.revolutBusyReloadStartCount) {
                    throw new Error("Reload reconciliation dispatched a new payment start");
                }
                const line = window.posmodel.get_order().get_paymentline_by_uuid(identity().lineUuid);
                if (window.revolutBusyReloadChecked && !line.uiState.revolutRecoveredUnstarted) {
                    throw new Error("Resume after uncertain reload requires server non-dispatch proof");
                }
                checkUndispatchedLine();
            },
        },
        checkStatusTwice(),
        {
            content: "Cancel the independent pending request through its public RPC",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            async run() {
                const saved = identity();
                const result = await window.posmodel.data.call(
                    "pos.payment.method", "revolut_cancel_payment", [[saved.methodId],
                        saved.blockerOperationId, saved.blockerOrderUuid, saved.blockerLineUuid]
                );
                if (result.state !== "cancelled") {
                    throw new Error("The independent order did not release its terminal lock");
                }
            },
        },
        checkStatusTwice(),
        {
            content: "After terminal release, a double Resume creates one intended payment",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            run() {
                this.anchor.click();
                this.anchor.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        {
            content: "Verified checkout retains the rejected order and payment-line identities",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.get_order();
                const saved = identity();
                const line = order.get_paymentline_by_uuid(saved.lineUuid);
                if (order.uuid !== saved.orderUuid || !line?.is_done() ||
                    line.uiState.revolutSnapshot?.state !== "verified") {
                    throw new Error("Recovered checkout changed identity or lacked verified payment");
                }
                const accepted = starts().filter((request) => request.result?.operation_id);
                if (accepted.length !== 1) {
                    throw new Error(`Expected one accepted Resume, found ${accepted.length}`);
                }
                sessionStorage.removeItem(IDENTITY_KEY);
                sessionStorage.removeItem(CALLS_KEY);
            },
        },
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_busy_recovery", {
    steps: () => busyRecoverySteps(),
});
registry.category("web_tour.tours").add("pos_revolut_busy_inflight_reload", {
    steps: () => busyRecoverySteps(true),
});

registry.category("web_tour.tours").add("pos_revolut_busy_cash_alternative", {
    steps: () => [
        ...busySaleSteps(),
        checkStatusTwice(),
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        PaymentScreen.emptyPaymentlines("12.34"),
        PaymentScreen.clickPaymentMethod("Cash"),
        PaymentScreen.clickValidate(),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Cash", "12.34"),
        {
            content: "Cash checkout removes only the definitively rejected line",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.get_order();
                const saved = identity();
                if (order.uuid !== saved.orderUuid || order.get_paymentline_by_uuid(saved.lineUuid)) {
                    throw new Error("Cash checkout lost the order or kept the rejected line");
                }
                sessionStorage.removeItem(IDENTITY_KEY);
                sessionStorage.removeItem(CALLS_KEY);
            },
        },
    ].flat(),
});

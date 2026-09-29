import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const IDENTITY_KEY = "revolutBusyIdentity";
const CALLS_KEY = "revolutBusyCalls";

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
        tracked = call(model, method, args, ...rest).then((result) => {
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
    const order = window.posmodel.getOrder();
    const saved = identity();
    const line = order.getPaymentlineByUuid(saved.lineUuid);
    if (order.uuid !== saved.orderUuid || !line || line.isDone() ||
        line.uiState.revolutStarted || line.uiState.revolutOperationId ||
        line.transaction_id || line.payment_ref_no) {
        throw new Error("A definitively busy rejection retained dispatched money or lost identity");
    }
    line.setAmount(10);
    if (line.amount !== 10) {
        throw new Error("The definitively undispatched amount remained locked");
    }
    line.setAmount(12.34);
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

function busySaleSteps() {
    return [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        {
            content: "An independent order reserves the terminal through the real start RPC",
            trigger: ".payment-screen",
            async run() {
                const pos = window.posmodel;
                const order = pos.getOrder();
                const method = pos.models["pos.payment.method"].getAll().find((paymentMethod) =>
                    paymentMethod.use_payment_terminal === "revolut"
                );
                const saved = {
                    orderUuid: order.uuid,
                    blockerOrderUuid: crypto.randomUUID(),
                    blockerLineUuid: crypto.randomUUID(),
                    methodId: method.id,
                };
                sessionStorage.setItem(IDENTITY_KEY, JSON.stringify(saved));
                sessionStorage.setItem(CALLS_KEY, "[]");
                observeRpc();
                const blocker = await pos.data.call("pos.payment.method", "revolut_start_payment", [
                    [method.id], pos.session.id, saved.blockerOrderUuid, saved.blockerLineUuid,
                    12.34, pos.currency.id, false, {
                        amount_total: 12.34,
                        pricelist_id: order.pricelist_id?.id || false,
                        fiscal_position_id: order.fiscal_position_id?.id || false,
                        restaurant: false,
                        lines: order.lines.map((line) => ({
                            uuid: line.uuid, product_id: line.product_id.id,
                            qty: line.qty, price_unit: line.price_unit, discount: line.discount || 0,
                            tax_ids: line.tax_ids.map((tax) => tax.id),
                        })),
                    },
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

registry.category("web_tour.tours").add("pos_revolut_busy_recovery", {
    steps: () => [
        ...busySaleSteps(),
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
        {
            content: "Reload preserves definite rejection and editable payment identity",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            run() {
                observeRpc();
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
                const order = window.posmodel.getOrder();
                const saved = identity();
                const line = order.getPaymentlineByUuid(saved.lineUuid);
                if (order.uuid !== saved.orderUuid || !line?.isDone() ||
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
    ].flat(),
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
                const order = window.posmodel.getOrder();
                const saved = identity();
                if (order.uuid !== saved.orderUuid || order.getPaymentlineByUuid(saved.lineUuid)) {
                    throw new Error("Cash checkout lost the order or kept the rejected line");
                }
                sessionStorage.removeItem(IDENTITY_KEY);
                sessionStorage.removeItem(CALLS_KEY);
            },
        },
    ].flat(),
});

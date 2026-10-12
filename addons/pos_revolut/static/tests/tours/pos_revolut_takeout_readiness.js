import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";

function beginTakeout(loseSlotAfterCapture = false) {
    return [
        {
            content: "Open the already configured Restaurant register",
            trigger: ".screen-login .btn.open-register-btn, .floor-screen .floor-map",
            timeout: 30000,
            run() {
                if (this.anchor.matches(".screen-login .btn.open-register-btn")) {
                    this.anchor.click();
                }
            },
        },
        { trigger: ".floor-screen .floor-map", timeout: 30000 },
        { trigger: ".floor-map .table:has(.label:contains('1')):not(.syncing)", run: "click" },
        ProductScreen.addOrderline("Desk Pad"),
        {
            content: "Prepare native timed Takeout with today's closed calendar and no slot",
            trigger: ".product-screen",
            run() {
                const pos = window.posmodel;
                const order = pos.getOrder();
                const preset = pos.models["pos.preset"].find((item) => item.name === "Takeout");
                if (!preset?.needsSlot) {
                    throw new Error("Expected native timed Takeout fixture");
                }
                order.setPreset(preset);
                order.table_id = false;
                order.preset_time = false;
                const evidence = window.revolutTakeoutEvidence = {
                    orderUuid: order.uuid, events: [], starts: 0, preparations: 0,
                    loseSlotAfterCapture,
                };
                const record = (phase) => evidence.events.push({
                    phase, presetTime: order.preset_time?.toISO() || null,
                    orderState: order.state,
                });
                const call = pos.data.call.bind(pos.data);
                pos.data.call = async (model, rpc, args, ...rest) => {
                    if (model === "pos.order" && rpc === "revolut_prepare_payment") {
                        evidence.preparations++;
                    }
                    if (model === "pos.payment.method" && rpc === "revolut_start_payment") {
                        evidence.starts++;
                        evidence.lineUuid = args[3];
                        record("start");
                    }
                    return call(model, rpc, args, ...rest);
                };
                // POS pages are available when this tour runs, while the
                // shared test bundle also loads in the manager backend.
                const screenPrototype = registry.category("pos_pages").get("PaymentScreen").component.prototype;
                const validate = screenPrototype.validateOrder;
                screenPrototype.validateOrder = function (...args) {
                    if (this.currentOrder?.uuid === order.uuid) {
                        record("validation");
                    }
                    return validate.apply(this, args);
                };
                // Capture evidence at the native payment boundary, after real
                // mocked-provider verification and before automatic validation.
                const paymentPrototype = registry.category("pos_available_models").get("pos.payment").prototype;
                const pay = paymentPrototype.pay;
                paymentPrototype.pay = async function (...args) {
                    const successful = await pay.apply(this, args);
                    if (this.pos_order_id.uuid === order.uuid && successful) {
                        record("capture");
                        evidence.operationId = this.uiState.revolutSnapshot.operation_id;
                        evidence.paymentId = this.transaction_id;
                        if (evidence.loseSlotAfterCapture) {
                            // Model recovery of a captured legacy draft whose
                            // required scheduling is absent. Financial transport
                            // and native validation still run normally.
                            order.preset_time = false;
                            await pos.syncAllOrders({ orders: [order], force: true, throw: true });
                            record("scheduling_lost");
                        }
                    }
                    return successful;
                };
            },
        },
        ProductScreen.clickPayButton(),
    ].flat();
}

function nativeSlotSteps() {
    return [
        {
            content: "Open native pickup scheduling",
            trigger: ".payment-screen",
            run() {
                window.revolutTakeoutScheduling = window.posmodel.openPresetTiming();
            },
        },
        {
            content: "Today's closed day has no selectable pickup times",
            trigger: ".modal .alert-warning:contains('No slot available for this day')",
            run() {
                if (document.querySelector(".modal .preset-slot-button:not(.d-none)")) {
                    const visible = [...document.querySelectorAll(".modal .preset-slot-button")]
                        .some((button) => button.getClientRects().length);
                    if (visible) {
                        throw new Error("Closed date exposed a pickup slot");
                    }
                }
            },
        },
        {
            content: "Choose an available date using native scheduling",
            trigger: ".modal .btn.btn-secondary:not(.o_colorlist_item_color_transparent_6)",
            run: "click",
        },
        { trigger: ".modal .preset-slot-button", run: "click" },
        {
            trigger: ".payment-screen",
            async run() {
                // The native picker closes before its draft-save RPC finishes.
                // Await that public action before sending payment or Validate.
                await window.revolutTakeoutScheduling;
                const order = window.posmodel.getOrder();
                if (!order.preset_time || !order.presetRequirementsFilled) {
                    throw new Error("Native slot selection did not satisfy Takeout scheduling");
                }
            },
        },
    ];
}

function originalTenderReceipt() {
    return [
        ReceiptScreen.isShown().map((step) => ({ ...step, timeout: 30000 })),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        {
            content: "Native receipt retains the original captured tender and payment reference",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.getOrder();
                const evidence = window.revolutTakeoutEvidence;
                const line = order.getPaymentlineByUuid(evidence.lineUuid);
                if (!line || order.uuid !== evidence.orderUuid || order.payment_ids.length !== 1 ||
                    evidence.starts !== 1 ||
                    line.transaction_id !== evidence.paymentId || !line.isDone() || order.state !== "paid") {
                    throw new Error(`Scheduling checkout replaced or recollected the original tender: ${JSON.stringify({
                        orderUuid: order.uuid, orderState: order.state, payments: order.payment_ids.length,
                        lineUuid: line?.uuid,
                        paymentId: line?.transaction_id, done: line?.isDone(), evidence,
                    })}`);
                }
            },
        },
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_takeout_missing_slot_blocked", {
    steps: () => [
        ...beginTakeout(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Missing pickup time gives actionable feedback before preparation or dispatch",
            trigger: ".modal:contains('Revolut cart needs correction')",
            run() {
                const evidence = window.revolutTakeoutEvidence;
                if (evidence.preparations !== 0 || evidence.starts !== 0 ||
                    !/time slot/i.test(this.anchor.textContent)) {
                    throw new Error(`Takeout scheduling must be checked locally before financial preparation: ${JSON.stringify(evidence)}`);
                }
            },
        },
        Dialog.confirm(),
        ...nativeSlotSteps(),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_takeout_valid_slot_automatic_checkout", {
    steps: () => [
        ...beginTakeout(),
        ...nativeSlotSteps(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ...originalTenderReceipt(),
        {
            content: "One verified capture invokes native automatic validation with scheduling already satisfied",
            trigger: ".receipt-screen",
            run() {
                const evidence = window.revolutTakeoutEvidence;
                if (evidence.events.map((event) => event.phase).join(",") !== "start,capture,validation" ||
                    evidence.events.some((event) => !event.presetTime) ||
                    new Set(evidence.events.map((event) => event.presetTime)).size !== 1) {
                    throw new Error(`Valid pickup slot did not complete automatically: ${JSON.stringify(evidence)}`);
                }
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_takeout_captured_scheduling_recovery", {
    steps: () => [
        ...beginTakeout(true),
        ...nativeSlotSteps(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".modal:contains('Slot required')", timeout: 30000 },
        Dialog.confirm(),
        {
            content: "A captured tender remains Draft under native scheduling requirements",
            trigger: ".payment-screen .electronic_status:contains('Payment Successful')",
            async run() {
                const pos = window.posmodel;
                const order = pos.getOrder();
                const evidence = window.revolutTakeoutEvidence;
                const line = order.getPaymentlineByUuid(evidence.lineUuid);
                if (order.state !== "draft" || order.preset_time || !line.isDone() ||
                    evidence.events.map((event) => event.phase).join(",") !== "start,capture,scheduling_lost,validation") {
                    throw new Error(`Captured legacy draft bypassed native scheduling: ${JSON.stringify(evidence)}`);
                }
                const preparations = evidence.preparations;
                const successful = await line.payment_method_id.payment_terminal.sendPaymentRequest(line.uuid);
                if (!successful || evidence.starts !== 1 || evidence.preparations !== preparations ||
                    line.transaction_id !== evidence.paymentId || order.preset_time) {
                    throw new Error("Missing scheduling blocked status recovery or recollected the payment");
                }
            },
        },
        ...nativeSlotSteps(),
        PaymentScreen.clickValidate(),
        ...originalTenderReceipt(),
    ].flat(),
});

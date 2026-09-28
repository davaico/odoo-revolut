import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";
import { registry } from "@web/core/registry";

const IDENTITY_KEY = "revolutDiscoveryIdentity";

function failInitialDiscovery(refund) {
    return {
        content: "Fail the initial read-only lookup before any financial start",
        trigger: ".payment-screen",
        run() {
            const pos = window.posmodel;
            const call = pos.data.call.bind(pos.data);
            let failed = false;
            pos.data.call = async (model, method, args, ...rest) => {
                if (!failed && model === "pos.payment.method" &&
                    method === `revolut_find_${refund ? "refund" : "payment"}`) {
                    failed = true;
                    sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({
                        orderUuid: args[1], lineUuid: args[2],
                    }));
                    throw new Error("Simulated read-only discovery failure");
                }
                return call(model, method, args, ...rest);
            };
        },
    };
}

function checkUndispatchedLine(refund) {
    return {
        content: "The same undispatched line can be edited and remains unpaid",
        trigger: ".payment-screen .send_payment_request:contains('Retry')",
        run() {
            const order = window.posmodel.getOrder();
            const { orderUuid, lineUuid } = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
            const line = order.getPaymentlineByUuid(lineUuid);
            if (order.uuid !== orderUuid || !line || line.isDone() ||
                line.uiState.revolutStarted || line.uiState.revolutOperationId ||
                line.transaction_id || line.payment_ref_no) {
                throw new Error("Discovery failure changed identity or retained dispatched money");
            }
            line.setAmount(refund ? -10 : 10);
            if (line.amount !== (refund ? -10 : 10)) {
                throw new Error("Undispatched amount remained locked");
            }
            line.setAmount(refund ? -12.34 : 12.34);
        },
    };
}

function checkSettledIdentity() {
    return {
        content: "Verified checkout preserves the recovered order and payment identities",
        trigger: ".receipt-screen",
        run() {
            const order = window.posmodel.getOrder();
            const { orderUuid, lineUuid } = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
            const line = order.getPaymentlineByUuid(lineUuid);
            if (order.uuid !== orderUuid || !line?.isDone() ||
                line.uiState.revolutSnapshot?.state !== "verified") {
                throw new Error("Recovered settlement changed identity or lacked verification");
            }
            sessionStorage.removeItem(IDENTITY_KEY);
        },
    };
}

function saleSteps(split = false) {
    return [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ...(split ? ProductScreen.clickDisplayedProduct("Desk Pad") : []),
        ProductScreen.clickPayButton(),
    ].flat();
}

function returnSteps(split = false) {
    return [
        ...saleSteps(split),
        ...(split ? [
            PaymentScreen.clickPaymentMethod("Cash"),
            {
                trigger: ".paymentline.selected:contains('Cash')",
                run() {
                    window.posmodel.getOrder().payment_ids.find((line) =>
                        line.payment_method_id.name === "Cash"
                    ).setAmount(12.34);
                },
            },
        ] : []),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice(split ? "24.68" : "12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        PaymentScreen.isShown(),
    ].flat();
}

for (const refund of [false, true]) {
    const kind = refund ? "refund" : "payment";
    const failedDiscoverySteps = (alternative = false) => [
        ...(refund ? returnSteps(alternative) : saleSteps()),
        failInitialDiscovery(refund),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ...(refund ? [{ trigger: ".payment-screen .send_refund_request", run: "click" }] : []),
        { trigger: `.modal:contains('No ${kind} request was sent from this line')` },
        Dialog.confirm(),
        checkUndispatchedLine(refund),
    ].flat();

    registry.category("web_tour.tours").add(`pos_revolut_${kind}_discovery_recovery`, {
        steps: () => [
            ...failedDiscoverySteps(),
            refresh(),
            checkUndispatchedLine(refund),
            {
                content: "Explicit repeated retries share one first financial start",
                trigger: ".payment-screen .send_payment_request:contains('Retry')",
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
            { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${refund
                ? "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf" : "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"}')` },
            checkSettledIdentity(),
        ].flat(),
    });

    registry.category("web_tour.tours").add(`pos_revolut_${kind}_discovery_alternative`, {
        steps: () => [
            ...failedDiscoverySteps(true),
            PaymentScreen.clickPaymentlineDelButton("Revolut", refund ? "-12.34" : "12.34"),
            PaymentScreen.emptyPaymentlines(refund ? "-12.34" : "12.34"),
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Cash", refund ? "-12.34" : "12.34"),
            {
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.getOrder();
                    const { orderUuid, lineUuid } = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                    if (order.uuid !== orderUuid || order.getPaymentlineByUuid(lineUuid)) {
                        throw new Error("Alternative tender failed to remove only the undispatched line");
                    }
                    sessionStorage.removeItem(IDENTITY_KEY);
                },
            },
        ].flat(),
    });
}

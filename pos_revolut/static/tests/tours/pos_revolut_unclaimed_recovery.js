import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { registry } from "@web/core/registry";

function cart(order) {
    return JSON.stringify(order.lines.map((line) => ({
        uuid: line.uuid, product: line.product_id.id, qty: line.qty,
        price: line.price_unit, discount: line.discount || 0,
        taxes: line.tax_ids.map((tax) => tax.id),
    })));
}

registry.category("web_tour.tours").add("pos_revolut_unclaimed_worker_recovery", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        {
            content: "Retain the intended cart before the original worker stops",
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.get_order();
                window.revolutStoppedWorker = { orderUuid: order.uuid, cart: cart(order) };
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
        Dialog.confirm(),
        {
            content: "Read the durable original reservation without restarting its worker",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                const line = order.payment_ids.find((payment) =>
                    payment.payment_method_id.use_payment_terminal === "revolut"
                );
                const saved = window.revolutStoppedWorker;
                saved.lineUuid = line.uuid;
                saved.methodId = line.payment_method_id.id;
                const operation = await pos.data.call("pos.payment.method", "revolut_find_payment", [
                    [saved.methodId], order.uuid, line.uuid,
                ]);
                if (!operation?.operation_id || operation.retry_safe ||
                    operation.state !== "unresolved" ||
                    order.uuid !== saved.orderUuid || cart(order) !== saved.cart) {
                    throw new Error("Stopped worker lost its original reservation or authorized cart");
                }
                saved.operationId = operation.operation_id;
                const observed = await pos.data.call("pos.payment.method", "revolut_poll_payment", [
                    [saved.methodId], saved.operationId, order.uuid, line.uuid,
                ]);
                if (observed.operation_id !== saved.operationId || observed.retry_safe ||
                    observed.state !== operation.state) {
                    throw new Error("Read-only status released or restarted the stopped reservation");
                }
                // Cancellation shares the bounded observation cadence. Follow
                // the public server advice before the cashier's next action.
                await new Promise((resolve) => setTimeout(resolve, observed.next_check_seconds * 1000));
            },
        },
        PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
        { trigger: ".modal:contains('The Revolut payment was cancelled')" },
        Dialog.confirm(),
        PaymentScreen.emptyPaymentlines("12.34"),
        {
            content: "Native deletion safely cancels only the original payment attempt",
            trigger: ".payment-screen",
            async run() {
                const pos = window.posmodel;
                const order = pos.get_order();
                const saved = window.revolutStoppedWorker;
                const operation = await pos.data.call("pos.payment.method", "revolut_find_payment", [
                    [saved.methodId], saved.orderUuid, saved.lineUuid,
                ]);
                if (operation.operation_id !== saved.operationId ||
                    operation.state !== "cancelled" || operation.retry_safe !== true ||
                    order.get_paymentline_by_uuid(saved.lineUuid) ||
                    order.uuid !== saved.orderUuid || cart(order) !== saved.cart) {
                    throw new Error("Cashier cancellation lost history or changed the intended sale");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        {
            content: "The available terminal verifies the unchanged original sale",
            trigger: ".receipt-screen .pos-payment-terminal-receipt:contains('2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf')",
            run() {
                const order = window.posmodel.get_order();
                const saved = window.revolutStoppedWorker;
                const line = order.payment_ids.find((payment) =>
                    payment.payment_method_id.use_payment_terminal === "revolut"
                );
                if (order.uuid !== saved.orderUuid || cart(order) !== saved.cart ||
                    !line?.is_done() || line.uuid === saved.lineUuid || line.amount !== 12.34 ||
                    line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.transaction_id !== "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf") {
                    throw new Error("Recovery completed a different cart or lacked verified payment");
                }
                delete window.revolutStoppedWorker;
            },
        },
    ].flat(),
});

import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { ConnectionLostError } from "@web/core/network/rpc";
import { formatTraceback } from "@web/core/errors/error_utils";
import { registry } from "@web/core/registry";

const KEY = "revolutLostPaidSync";
const saved = () => JSON.parse(sessionStorage.getItem(KEY));

registry.category("web_tour.tours").add("pos_revolut_lost_paid_sync_response", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        {
            content: "Lose only the response after the actual paid order has been saved",
            trigger: ".payment-screen",
            run() {
                const pos = window.posmodel;
                sessionStorage.setItem(KEY, JSON.stringify({ orderUuid: pos.get_order().uuid,
                    replies: 0, lost: false }));
                let responseLoss;
                const consoleError = console.error;
                console.error = (...args) => {
                    // Native error_service formats this exact injected error
                    // after displaying its real offline warning. HttpCase 18
                    // marks even filtered console errors as failed, so demote
                    // only this one exact object/traceback and restore logging.
                    const expectedTraceback = responseLoss && formatTraceback(responseLoss);
                    if (responseLoss && args.length === 1 &&
                        (args[0] === responseLoss || args[0] === expectedTraceback)) {
                        console.error = consoleError;
                        sessionStorage.setItem(KEY, JSON.stringify({ ...saved(), observedLosses: 1 }));
                        console.warn(...args);
                        return;
                    }
                    consoleError.apply(console, args);
                };
                const call = pos.data.call.bind(pos.data);
                pos.data.call = async (model, method, args, ...rest) => {
                    const paidSync = model === "pos.order" && method === "sync_from_ui" &&
                        args[0].some((order) => order.uuid === saved().orderUuid && order.state === "paid");
                    const result = await call(model, method, args, ...rest);
                    if (!paidSync) {
                        return result;
                    }
                    const identity = saved();
                    const order = result["pos.order"].find((record) => record.uuid === identity.orderUuid);
                    const line = pos.get_order().payment_ids.find((payment) =>
                        payment.payment_method_id.use_payment_terminal === "revolut");
                    const payment = result["pos.payment"].find((record) => record.uuid === line.uuid);
                    if (order.state !== "paid" || line.uiState.revolutSnapshot?.state !== "verified" ||
                        !Number.isInteger(order.id) || !Number.isInteger(payment.id) ||
                        payment.transaction_id !== line.transaction_id || payment.payment_ref_no !== line.payment_ref_no) {
                        throw new Error("A lost response must follow real saved and verified native payment effects");
                    }
                    sessionStorage.setItem(KEY, JSON.stringify({ ...identity, replies: identity.replies + 1,
                        lost: true, orderId: order.id, lineId: payment.id, lineUuid: line.uuid,
                        reference: order.pos_reference, transaction: payment.transaction_id,
                        paymentReference: payment.payment_ref_no }));
                    if (!identity.lost) {
                        responseLoss = new ConnectionLostError("/pos_revolut/tests/lost-paid-sync-response");
                        throw responseLoss;
                    }
                    return result;
                };
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        { trigger: ".modal:contains('Connection Lost'):contains('limited functionality')" },
        Dialog.confirm(),
        {
            content: "Retry the native pending sync queue without collecting payment again",
            trigger: ".receipt-screen",
            async run() {
                const pos = window.posmodel;
                const identity = saved();
                const order = pos.get_order();
                if (!identity.lost || identity.observedLosses !== 1 || identity.replies !== 1 ||
                    order.uuid !== identity.orderUuid ||
                    !pos.getPendingOrder().orderToUpdate.some((pending) => pending.uuid === identity.orderUuid)) {
                    throw new Error("The lost paid response did not retain the original pending native order");
                }
                const result = await pos.syncAllOrders({ throw: true });
                if (result.length !== 1 || result[0].id !== identity.orderId || saved().replies !== 2) {
                    throw new Error("Native sync retry replaced or duplicated the saved paid order");
                }
            },
        },
        refresh(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        {
            content: "The original paid receipt reloads with its one original verified tender",
            trigger: ".ticket-screen .order-row.highlight",
            run() {
                const pos = window.posmodel;
                const identity = saved();
                const orders = pos.models["pos.order"].filter((order) => order.uuid === identity.orderUuid);
                const order = orders[0];
                const line = order?.get_paymentline_by_uuid(identity.lineUuid);
                if (orders.length !== 1 || order.id !== identity.orderId || order.state !== "paid" ||
                    !this.anchor.textContent.includes(identity.reference) || order.payment_ids.length !== 1 ||
                    line?.id !== identity.lineId || !line.is_done() || line.amount !== 12.34 ||
                    line.transaction_id !== identity.transaction || line.payment_ref_no !== identity.paymentReference) {
                    throw new Error("Reload of the lost-response checkout changed its saved order, tender or verified references");
                }
                sessionStorage.removeItem(KEY);
            },
        },
    ].flat(),
});

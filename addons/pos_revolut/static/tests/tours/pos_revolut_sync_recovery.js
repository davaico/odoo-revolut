import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import { registry } from "@web/core/registry";

for (const refund of [false, true]) {
    registry.category("web_tour.tours").add(`pos_revolut_sync_recovery_${refund ? "refund" : "payment"}`, {
        steps: () => [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            {
                trigger: ".payment-screen",
                run() {
                    const pos = window.posmodel;
                    const method = pos.models["pos.payment.method"].find((item) => item.use_payment_terminal === "revolut");
                    pos.get_order().add_paymentline(method);
                },
            },
            {
                trigger: ".paymentline.selected",
                async run() {
                    const pos = window.posmodel;
                    const order = pos.get_order();
                    const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                    const call = pos.data.call.bind(pos.data);
                    // Mock a delayed draft response at the transport boundary,
                    // then exercise native loadConnectedData and postSyncAllOrders.
                    pos.data.call = async (model, method, ...args) => {
                        if (model === "pos.payment.method" && method.startsWith("revolut_")) {
                            throw new Error("Recovery of a stale draft must not dispatch or poll");
                        }
                        const result = await call(model, method, ...args);
                        if (model === "pos.order" && method === "sync_from_ui") {
                            for (const payment of result["pos.payment"] || []) {
                                if (payment.uuid === line.uuid) {
                                    payment.payment_status = "waiting";
                                    if (refund) payment.amount = -12.34;
                                }
                            }
                        }
                        return result;
                    };
                    line.uiState.revolutSnapshot = {
                        operation_id: 987654, state: refund ? "pending" : "cancelled", retry_safe: !refund,
                    };
                    line.uiState.revolutOperationId = 987654;
                    line.uiState.revolutStarted = true;
                    line.set_payment_status("retry");
                    await pos.syncAllOrders({ orders: [order], force: true, throw: true });
                    const current = pos.get_order().get_paymentline_by_uuid(line.uuid);
                    if (current.get_payment_status() !== "retry" || current.uiState.revolutOperationId !== 987654) {
                        throw new Error("Native draft merge hid recovery or changed operation identity");
                    }
                },
            },
            {
                trigger: refund ? ".electronic_status:contains('Refund pending')" : ".electronic_status:contains('Payment cancelled')",
            },
            {
                trigger: refund ? ".send_payment_request:contains('Check status')" : ".send_payment_request:contains('Retry')",
            },
        ].flat(),
    });
}

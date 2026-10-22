import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { registry } from "@web/core/registry";

// Hold actual transport results so the production preparation adapter still
// saves, authorizes and refreshes the native draft. No financial RPC is mocked.
for (const stage of ["draft", "authorization", "refresh"]) {
    let release;
    let identity;
    const financialCalls = [];
    registry.category("web_tour.tours").add(`pos_revolut_cancel_preparation_${stage}`, {
        steps: () => [
            Chrome.startPoS(),
            { trigger: "body:not(:has(.pos-loader))" },
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            {
                trigger: ".payment-screen",
                run() {
                    const pos = window.posmodel;
                    const call = pos.data.call.bind(pos.data);
                    const sync = pos.syncAllOrders.bind(pos);
                    let held = false;
                    financialCalls.length = 0;
                    const hold = async (result) => {
                        const order = pos.get_order();
                        const line = order.payment_ids.find((payment) => payment.uiState.revolutDiscovering);
                        if (!held && line) {
                            held = true;
                            identity = { orderUuid: order.uuid, lineUuid: line.uuid };
                            await new Promise((resolve) => {
                                release = resolve;
                                document.querySelector(".payment-screen").dataset.preparationHeld = stage;
                            });
                        }
                        return result;
                    };
                    pos.syncAllOrders = async (...args) => {
                        const result = await sync(...args);
                        return stage === "draft" ? hold(result) : result;
                    };
                    pos.data.call = async (model, method, ...args) => {
                        if (model === "pos.payment.method" &&
                            ["revolut_start_payment", "revolut_cancel_payment", "revolut_mark_timeout"].includes(method)) {
                            financialCalls.push(method);
                        }
                        const result = await call(model, method, ...args);
                        return model === "pos.order" &&
                            ((stage === "authorization" && method === "revolut_prepare_payment") ||
                                (stage === "refresh" && method === "revolut_checkout_state"))
                            ? hold(result) : result;
                    };
                },
            },
            PaymentScreen.clickPaymentMethod("Revolut"),
            {
                content: `Cancel through native line deletion while ${stage} is pending`,
                trigger: `.payment-screen[data-preparation-held='${stage}'] .paymentline.selected .delete-button`,
                run() {
                    const bounds = this.anchor.getBoundingClientRect();
                    const hit = document.elementFromPoint(bounds.left + bounds.width / 2,
                        bounds.top + bounds.height / 2);
                    if (!hit || !this.anchor.contains(hit)) {
                        throw new Error(`Native preparation cancellation is covered by ${hit?.className || "another surface"}`);
                    }
                    this.anchor.click();
                    const line = window.posmodel.get_order().get_paymentline_by_uuid(identity.lineUuid);
                    if (line.get_payment_status() !== "waitingCancel") {
                        throw new Error("Native deletion did not request cancellation during preparation");
                    }
                    release();
                },
            },
            PaymentScreen.emptyPaymentlines("12.34"),
            {
                content: "Cancellation releases native busy state and retains the saved authorized draft",
                trigger: ".payment-screen",
                run() {
                    const pos = window.posmodel;
                    const order = pos.get_order();
                    if (pos.paymentTerminalInProgress || order.uuid !== identity.orderUuid ||
                        !Number.isInteger(order.id) || !order.uiState.revolutAuthority?.cart_version ||
                        order.get_paymentline_by_uuid(identity.lineUuid) || financialCalls.length) {
                        throw new Error("Cancelled preparation dispatched, stayed busy or discarded its draft");
                    }
                },
            },
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Cash", "12.34"),
            {
                trigger: ".receipt-screen",
                run() {
                    if (window.posmodel.get_order().uuid !== identity.orderUuid || financialCalls.length) {
                        throw new Error("Alternative tender changed the saved order or started Revolut");
                    }
                },
            },
        ].flat(),
    });
}

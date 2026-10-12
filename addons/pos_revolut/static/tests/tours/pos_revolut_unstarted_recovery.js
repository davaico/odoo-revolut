import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import { registry } from "@web/core/registry";
import { refresh } from "@point_of_sale/../tests/generic_helpers/utils";

function savedTender() {
    const pos = window.posmodel;
    const candidates = pos.models["pos.order"].filter((order) => order.state === "draft" &&
        Number.isInteger(order.id) && order.payment_ids.some((line) =>
            line.payment_method_id.use_payment_terminal === "revolut" &&
            Number.isInteger(line.id) && line.amount === 12.34 && !line.transaction_id && !line.payment_ref_no));
    if (candidates.length !== 1) {
        throw new Error("Expected the one original saved unstarted Revolut sale");
    }
    const order = candidates[0];
    const line = order.payment_ids.find((payment) => payment.payment_method_id.use_payment_terminal === "revolut");
    pos.setOrder(order);
    order.selectPaymentline(line);
    pos.navigate("PaymentScreen", { orderUuid: order.uuid });
    return { pos, order, line };
}

registry.category("web_tour.tours").add("pos_revolut_unstarted_prepare_failure", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".modal:contains('Configure a valid terminal tip product before Revolut payment')" },
        Dialog.confirm(),
        {
            content: "Keep the exact saved waiting tender without local failure evidence",
            trigger: ".payment-screen .send_payment_request:contains('Resume')",
            run() {
                const pos = window.posmodel;
                const order = pos.getOrder();
                const line = order.payment_ids.find((payment) => payment.payment_method_id.use_payment_terminal === "revolut");
                if (!Number.isInteger(order.id) || !Number.isInteger(line?.id) ||
                    line.transaction_id || line.payment_ref_no || line.uiState.revolutSnapshot ||
                    line.uiState.revolutOperationId || pos.paymentTerminalInProgress) {
                    throw new Error("Failed native preparation lost persistence or created financial evidence");
                }
                // Simulate the pre-fix waiting fixture's lost UI evidence. The
                // native saved draft is retained; no browser storage is cleared.
                line.uiState = {};
                line.setPaymentStatus("waiting");
            },
        },
    ].flat(),
});

for (const action of ["resume", "cash_removal", "offline_resume"]) {
    registry.category("web_tour.tours").add(`pos_revolut_unstarted_${action}`, {
        steps: () => [
            Chrome.startPoS(),
            {
                content: "Reload the original saved tender after its ephemeral preparation evidence is lost",
                trigger: ".pos-content",
                run() {
                    const { line } = savedTender();
                    line.uiState = {};
                    line.setPaymentStatus("waiting");
                },
            },
            refresh(),
            {
                content: "A fresh native browser recovers the original waiting sale from saved draft data",
                trigger: ".pos-content",
                run() {
                    const { pos, order, line } = savedTender();
                    window.revolutUnstartedIdentity = { orderUuid: order.uuid, lineUuid: line.uuid,
                        orderId: order.id, lineId: line.id, financialCalls: [] };
                    if (line.getPaymentStatus() !== "retry" || line.uiState.revolutSnapshot ||
                        line.uiState.revolutRecoveredUnstarted || pos.paymentTerminalInProgress) {
                        throw new Error("Reload fabricated operation evidence or safe recovery authority");
                    }
                    const call = pos.data.call.bind(pos.data);
                    let offlineRecovery = action === "offline_resume";
                    pos.data.call = async (model, method, ...args) => {
                        if (offlineRecovery && model === "pos.order" &&
                            method === "revolut_recover_unstarted_payment") {
                            offlineRecovery = false;
                            throw new Error("Disposable native recovery is offline");
                        }
                        if (model === "pos.payment.method" &&
                            ["revolut_start_payment", "revolut_cancel_payment"].includes(method)) {
                            window.revolutUnstartedIdentity.financialCalls.push(method);
                        }
                        return call(model, method, ...args);
                    };
                },
            },
            ...(action === "offline_resume" ? [
                { trigger: ".payment-screen .send_payment_request:contains('Check status')", run: "click" },
                { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
                Dialog.confirm(),
                {
                    content: "Offline recovery leaves the exact tender guarded and releases native busy state",
                    trigger: ".payment-screen .send_payment_request:contains('Check status')",
                    run() {
                        const { pos, order, line } = savedTender();
                        const saved = window.revolutUnstartedIdentity;
                        if (line.uiState.revolutRecoveredUnstarted || line.uiState.revolutUndispatched ||
                            pos.paymentTerminalInProgress || saved.financialCalls.length ||
                            line.uuid !== saved.lineUuid || order.uuid !== saved.orderUuid) {
                            throw new Error("Offline recovery unlocked money, replaced the tender or stranded native busy state");
                        }
                    },
                },
            ] : []),
            ...(action !== "cash_removal" ? [
                { trigger: ".payment-screen .send_payment_request:contains('Check status')", run: "click" },
                {
                    content: "Recovery exposes Resume without dispatch or replacing the tender",
                    trigger: ".payment-screen .send_payment_request:contains('Resume')",
                    run() {
                        const { pos, order, line } = savedTender();
                        const saved = window.revolutUnstartedIdentity;
                        if (saved.financialCalls.length || !line.uiState.revolutRecoveredUnstarted ||
                            order.uuid !== saved.orderUuid || line.uuid !== saved.lineUuid ||
                            line.id !== saved.lineId || pos.paymentTerminalInProgress) {
                            throw new Error("Recovery charged, replaced the tender or kept native busy state");
                        }
                        this.anchor.click();
                    },
                },
                ReceiptScreen.isShown(),
                ReceiptScreen.paymentLineContains("Revolut", "12.34"),
                {
                    trigger: ".receipt-screen",
                    run() {
                        const pos = window.posmodel;
                        const saved = window.revolutUnstartedIdentity;
                        const order = pos.getOrder();
                        const line = order.getPaymentlineByUuid(saved.lineUuid);
                        if (order.uuid !== saved.orderUuid || order.id !== saved.orderId ||
                            line?.id !== saved.lineId || !line.isDone() ||
                            line.uiState.revolutSnapshot?.state !== "verified" ||
                            saved.financialCalls.join() !== "revolut_start_payment" || pos.paymentTerminalInProgress) {
                            throw new Error("Explicit Resume did not verify exactly one charge on the original tender");
                        }
                    },
                },
            ] : [
                PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
                PaymentScreen.emptyPaymentlines("12.34"),
                {
                    trigger: ".payment-screen",
                    run() {
                        const pos = window.posmodel;
                        const saved = window.revolutUnstartedIdentity;
                        if (pos.getOrder().uuid !== saved.orderUuid ||
                            pos.getOrder().getPaymentlineByUuid(saved.lineUuid) ||
                            saved.financialCalls.length || pos.paymentTerminalInProgress) {
                            throw new Error("Safe removal charged, discarded the sale or kept native busy state");
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
                        const saved = window.revolutUnstartedIdentity;
                        if (window.posmodel.getOrder().uuid !== saved.orderUuid || saved.financialCalls.length) {
                            throw new Error("Alternative tender changed the original sale or dispatched Revolut");
                        }
                    },
                },
            ]),
        ].flat(),
    });
}

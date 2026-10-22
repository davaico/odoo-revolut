import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { registry } from "@web/core/registry";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";

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
    pos.set_order(order);
    order.select_paymentline(line);
    pos.showScreen("PaymentScreen", { orderUuid: order.uuid });
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
                const order = pos.get_order();
                const line = order.payment_ids.find((payment) => payment.payment_method_id.use_payment_terminal === "revolut");
                if (!Number.isInteger(order.id) || !Number.isInteger(line?.id) ||
                    line.transaction_id || line.payment_ref_no || line.uiState.revolutSnapshot ||
                    line.uiState.revolutOperationId || pos.paymentTerminalInProgress) {
                    throw new Error("Failed native preparation lost persistence or created financial evidence");
                }
                // Simulate the pre-fix waiting fixture's lost UI evidence. The
                // native saved draft is retained; no browser storage is cleared.
                line.uiState = {};
                line.set_payment_status("waiting");
            },
        },
    ].flat(),
});

for (const action of ["resume", "cash_removal", "offline_resume", "lost_removal_cash"]) {
    registry.category("web_tour.tours").add(`pos_revolut_unstarted_${action}`, {
        steps: () => [
            Chrome.startPoS(),
            {
                content: "Reload the original saved tender after its ephemeral preparation evidence is lost",
                trigger: ".pos-content",
                run() {
                    const { line } = savedTender();
                    line.uiState = {};
                    line.set_payment_status("waiting");
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
                    if (line.get_payment_status() !== "retry" || line.uiState.revolutSnapshot ||
                        line.uiState.revolutRecoveredUnstarted || pos.paymentTerminalInProgress) {
                        throw new Error("Reload fabricated operation evidence or safe recovery authority");
                    }
                    const call = pos.data.call.bind(pos.data);
                    let offlineRecovery = action === "offline_resume";
                    let lostRemoval = action === "lost_removal_cash";
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
                        const result = await call(model, method, ...args);
                        if (lostRemoval && model === "pos.order" &&
                            method === "revolut_remove_unstarted_payment") {
                            lostRemoval = false;
                            throw new Error("Disposable browser lost the committed removal response");
                        }
                        return result;
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
            ...(action === "lost_removal_cash" ? [
                PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
                { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
                Dialog.confirm(),
                {
                    content: "A lost committed removal response retains the original local tender and releases native busy state",
                    trigger: ".payment-screen .send_payment_request:contains('Check status')",
                    run() {
                        const pos = window.posmodel;
                        const saved = window.revolutUnstartedIdentity;
                        const order = pos.get_order();
                        const line = order.get_paymentline_by_uuid(saved.lineUuid);
                        if (!line || line.id !== saved.lineId || !line.uiState.revolutRecoveryRequired ||
                            line.uiState.revolutRecoveredUnstarted || line.uiState.revolutUndispatched ||
                            order.uuid !== saved.orderUuid || saved.financialCalls.length ||
                            pos.paymentTerminalInProgress) {
                            throw new Error("Lost removal response discarded the local identity, unlocked money or kept native busy state");
                        }
                        this.anchor.click();
                    },
                },
                {
                    content: "Read the durable retired disposition without offering Resume or sending a provider operation",
                    trigger: ".payment-screen .electronic_status:contains('This payment line was removed')",
                    run() {
                        const pos = window.posmodel;
                        const saved = window.revolutUnstartedIdentity;
                        const line = pos.get_order().get_paymentline_by_uuid(saved.lineUuid);
                        if (!line?.uiState.revolutRecoveredRetired || !line.uiState.revolutRecoveryRequired ||
                            line.id !== saved.lineId || saved.financialCalls.length || pos.paymentTerminalInProgress ||
                            [...document.querySelectorAll(".send_payment_request")].some((button) =>
                                button.textContent.trim() === "Resume")) {
                            throw new Error("Retired recovery allowed a charge or lost durable removal authority");
                        }
                    },
                },
            ] : []),
            ...(!["cash_removal", "lost_removal_cash"].includes(action) ? [
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
                        const order = pos.get_order();
                        const line = order.get_paymentline_by_uuid(saved.lineUuid);
                        if (order.uuid !== saved.orderUuid || order.id !== saved.orderId ||
                            line?.id !== saved.lineId || !line.is_done() ||
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
                        if (pos.get_order().uuid !== saved.orderUuid ||
                            pos.get_order().get_paymentline_by_uuid(saved.lineUuid) ||
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
                        if (window.posmodel.get_order().uuid !== saved.orderUuid || saved.financialCalls.length) {
                            throw new Error("Alternative tender changed the original sale or dispatched Revolut");
                        }
                    },
                },
            ]),
        ].flat(),
    });
}

registry.category("web_tour.tours").add("pos_revolut_stale_preparation_recovery", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        {
            content: "Hold the real native draft-save response before cart preparation continues",
            trigger: ".payment-screen",
            run() {
                const pos = window.posmodel;
                const sync = pos.syncAllOrders.bind(pos);
                const call = pos.data.call.bind(pos.data);
                let held = false;
                window.revolutStalePreparation = { financialCalls: [] };
                pos.syncAllOrders = async (...args) => {
                    const result = await sync(...args);
                    const order = pos.get_order();
                    const line = order.payment_ids.find((payment) => payment.uiState.revolutDiscovering);
                    if (!held && line) {
                        held = true;
                        Object.assign(window.revolutStalePreparation, {
                            orderId: order.id, orderUuid: order.uuid, lineId: line.id,
                            lineUuid: line.uuid, methodId: line.payment_method_id.id,
                        });
                        await new Promise((resolve) => {
                            window.revolutStalePreparation.release = resolve;
                            document.querySelector(".payment-screen").dataset.stalePreparationHeld = "true";
                        });
                    }
                    return result;
                };
                pos.data.call = async (model, method, ...args) => {
                    if (model === "pos.payment.method" &&
                        ["revolut_start_payment", "revolut_cancel_payment"].includes(method)) {
                        window.revolutStalePreparation.financialCalls.push(method);
                    }
                    return call(model, method, ...args);
                };
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "A competing server recovery fences the saved tender while its preparation response is held",
            trigger: ".payment-screen[data-stale-preparation-held='true']",
            async run() {
                const pos = window.posmodel;
                const saved = window.revolutStalePreparation;
                const proof = await pos.data.call("pos.order", "revolut_recover_unstarted_payment", [
                    saved.orderId, saved.orderUuid, saved.lineUuid, saved.methodId, 12.34, pos.currency.id,
                ]);
                if (proof.recovery_status !== "unstarted" || proof.dispatched !== false ||
                    proof.payment_id !== saved.lineId || saved.financialCalls.length) {
                    throw new Error("Competing recovery lost the original native tender or dispatched payment");
                }
                // Deliberately leave the originating browser's local authority
                // unchanged, as when recovery came from another POS browser.
                saved.release();
            },
        },
        { trigger: ".modal:contains('Recovery changed this tender while payment was being prepared')" },
        Dialog.confirm(),
        {
            content: "The delayed preparation cannot adopt the new recovery authority or send a charge",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() {
                const pos = window.posmodel;
                const saved = window.revolutStalePreparation;
                const line = pos.get_order().get_paymentline_by_uuid(saved.lineUuid);
                if (!line || line.id !== saved.lineId || saved.financialCalls.length ||
                    line.uiState.revolutUndispatched || line.uiState.revolutRecoveredUnstarted ||
                    pos.paymentTerminalInProgress) {
                    throw new Error("Stale preparation unlocked the tender or sent a charge");
                }
                this.anchor.click();
            },
        },
        { trigger: ".payment-screen .send_payment_request:contains('Resume')", run: "click" },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "12.34"),
        {
            content: "Explicit recovery and Resume verify exactly one charge on the original saved tender",
            trigger: ".receipt-screen",
            run() {
                const pos = window.posmodel;
                const saved = window.revolutStalePreparation;
                const order = pos.get_order();
                const line = order.get_paymentline_by_uuid(saved.lineUuid);
                if (order.uuid !== saved.orderUuid || order.id !== saved.orderId ||
                    line?.id !== saved.lineId || !line.is_done() ||
                    line.uiState.revolutSnapshot?.state !== "verified" ||
                    saved.financialCalls.join() !== "revolut_start_payment" || pos.paymentTerminalInProgress) {
                    throw new Error("Explicit Resume replaced the tender, remained busy or failed to verify exactly one charge");
                }
            },
        },
    ].flat(),
});

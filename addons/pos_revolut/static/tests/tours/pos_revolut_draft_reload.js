import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";
import { reopenRevolutOrder } from "./recovery_order_util";

function tenderSnapshot() {
    const pos = window.posmodel;
    const order = pos.get_order();
    const snapshot = {
        orderUuid: order.uuid, orderId: order.id,
        lines: order.payment_ids.map((line) => ({
            uuid: line.uuid, id: line.id, amount: line.amount, status: line.payment_status,
        })),
        modelUuids: pos.models["pos.payment"].filter((line) => line.pos_order_id === order)
            .map((line) => line.uuid),
        rows: document.querySelectorAll(".payment-screen .paymentline:not(.electronic_payment)").length,
        cart: order.lines.map((line) => ({ id: line.id, uuid: line.uuid, qty: line.qty })),
        total: order.get_total_with_tax(),
        cartDeletes: order.getCommand("delete", "lines"),
    };
    return snapshot;
}

function assertAllocation() {
    return {
        content: "Refresh restores the exact pending allocation once, without the removed cancelled tender",
        trigger: ".payment-screen",
        async run() {
            const expected = JSON.parse(sessionStorage.getItem("ticket68Draft"));
            const cancelled = JSON.parse(sessionStorage.getItem("ticket68Cancelled"));
            const actual = tenderSnapshot();
            const order = window.posmodel.get_order();
            const [line] = actual.lines;
            if (actual.orderUuid !== expected.orderUuid || actual.orderId !== expected.orderId ||
                actual.lines.length !== 1 || actual.rows !== 1 || actual.modelUuids.length !== 1 ||
                line.uuid !== expected.lines[0].uuid || actual.modelUuids[0] !== line.uuid ||
                (Number.isInteger(expected.lines[0].id) && line.id !== expected.lines[0].id) ||
                line.status !== "pending" || line.amount !== 12.34 || order.is_paid()) {
                throw new Error("Draft reload introduced an extra or altered Revolut tender: " +
                    JSON.stringify({ expected, cancelled, actual }));
            }
            const [saved] = await window.posmodel.data.call("pos.order", "read", [
                [order.id], ["payment_ids", "state"],
            ]);
            if (saved.state !== "draft" || saved.payment_ids.includes(cancelled.lines[0].id)) {
                throw new Error("Reload retained the removed tender on the server or paid the draft");
            }
        },
    };
}

for (const variant of ["synced", "local", "minimal", "offline", "lost_response", "zero_before_remove"]) {
    registry.category("web_tour.tours").add(`pos_revolut_cancelled_unsent_reload_${variant}`, {
        steps: () => [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Revolut"),
            { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
            { trigger: ".payment-screen .send_payment_cancel", run: "click" },
            { trigger: ".modal:contains('The Revolut payment was cancelled')" },
            Dialog.confirm(),
            {
                trigger: ".payment-screen .send_payment_request:contains('Retry')",
                run() {
                    sessionStorage.setItem("ticket68Cancelled", JSON.stringify(tenderSnapshot()));
                    if (["offline", "lost_response"].includes(variant)) {
                        const pos = window.posmodel;
                        const call = pos.data.call.bind(pos.data);
                        let failRemoval = true;
                        pos.data.call = async (model, method, ...args) => {
                            if (failRemoval && model === "pos.order" && method === "revolut_remove_unstarted_payment") {
                                failRemoval = false;
                                if (variant === "offline") {
                                    throw new Error("Disposable removal transport is offline");
                                }
                                await call(model, method, ...args);
                                throw new Error("Disposable browser lost the committed removal response");
                            }
                            return call(model, method, ...args);
                        };
                    }
                },
            },
            PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
            ...(["offline", "lost_response"].includes(variant) ? [
                { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
                Dialog.confirm(),
                {
                    content: "An unconfirmed removal retains the original tender for explicit recovery",
                    trigger: ".payment-screen .send_payment_request:contains('Retry')",
                    run() {
                        const expected = JSON.parse(sessionStorage.getItem("ticket68Cancelled"));
                        const actual = tenderSnapshot();
                        if (actual.lines.length !== 1 || actual.rows !== 1 ||
                            actual.lines[0].uuid !== expected.lines[0].uuid ||
                            actual.lines[0].id !== expected.lines[0].id || window.posmodel.get_order().is_paid()) {
                            throw new Error("Unconfirmed removal discarded or replaced the original tender");
                        }
                    },
                },
                PaymentScreen.clickPaymentlineDelButton("Revolut", "12.34"),
            ] : []),
            PaymentScreen.emptyPaymentlines("12.34"),
            { trigger: ".revolut-choose-amount", run: "click" },
            {
                trigger: ".payment-screen .send_payment_request:contains('Send')",
                run() {
                    const modal = document.querySelector(".modal");
                    if (modal) {
                        throw new Error("Unexpected allocation modal: " + modal.textContent);
                    }
                },
            },
            ...(variant !== "minimal" ? [
                PaymentScreen.clickNumpad("0"),
                PaymentScreen.selectedPaymentlineHas("Revolut", "0.00"),
                ..."12.34".split("").map((key) => PaymentScreen.clickNumpad(key)),
                PaymentScreen.selectedPaymentlineHas("Revolut", "12.34"),
            ] : []),
            {
                content: "Retain the single unsent allocation before real native browser refresh",
                trigger: ".payment-screen .send_payment_request:contains('Send')",
                async run() {
                    const pos = window.posmodel;
                    const order = pos.get_order();
                    const snapshot = tenderSnapshot();
                    if (snapshot.lines.length !== 1 || snapshot.lines[0].status !== "pending" || order.is_paid()) {
                        throw new Error("Expected exactly one unsent unpaid allocation before refresh");
                    }
                    if (["synced", "zero_before_remove"].includes(variant)) {
                        await pos.syncAllOrders({ orders: [order], force: true, throw: true });
                    }
                    sessionStorage.setItem("ticket68Draft", JSON.stringify(tenderSnapshot()));
                    // Let the native IndexedDB debounce persist the last key
                    // before refresh, without saving the allocation to Odoo.
                    const cancelled = JSON.parse(sessionStorage.getItem("ticket68Cancelled")).lines[0];
                    const selected = order.payment_ids[0];
                    const deadline = Date.now() + 5000;
                    while (true) {
                        const cached = (await pos.data.indexedDB.readAll(["pos.payment"]))["pos.payment"] || [];
                        if (cached.some((line) => line.uuid === selected.uuid && line.amount === 12.34) &&
                            !cached.some((line) => line.uuid === cancelled.uuid)) {
                            break;
                        }
                        if (Date.now() > deadline) {
                            throw new Error("Native draft cache did not persist the final allocation edit");
                        }
                        await new Promise((resolve) => setTimeout(resolve, 50));
                    }
                },
            },
            refresh(),
            ...reopenRevolutOrder(() => JSON.parse(sessionStorage.getItem("ticket68Draft")).orderUuid),
            assertAllocation(),
            refresh(),
            ...reopenRevolutOrder(() => JSON.parse(sessionStorage.getItem("ticket68Draft")).orderUuid),
            assertAllocation(),
            ...(variant === "zero_before_remove" ? [
                PaymentScreen.clickNumpad("0"),
                PaymentScreen.selectedPaymentlineHas("Revolut", "0.00"),
            ] : []),
            PaymentScreen.clickPaymentlineDelButton("Revolut", variant === "zero_before_remove" ? "0.00" : "12.34"),
            PaymentScreen.emptyPaymentlines("12.34"),
            {
                trigger: ".payment-screen",
                async run() {
                    const pos = window.posmodel;
                    const order = pos.get_order();
                    await pos.syncAllOrders({ orders: [order], force: true, throw: true });
                    const [saved] = await pos.data.call("pos.order", "read", [[order.id], ["payment_ids", "state"]]);
                    if (saved.payment_ids.length || saved.state !== "draft" || order.payment_ids.length) {
                        throw new Error("Explicit pending-line removal did not preserve the empty unpaid draft");
                    }
                    sessionStorage.removeItem("ticket68Draft");
                    sessionStorage.removeItem("ticket68Cancelled");
                },
            },
        ].flat(),
    });
}

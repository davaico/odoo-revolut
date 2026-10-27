import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as Dialog from "@point_of_sale/../tests/tours/utils/dialog_util";
import * as NumberPopup from "@point_of_sale/../tests/tours/utils/number_popup_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { registry } from "@web/core/registry";
import { reopenRevolutOrder } from "@pos_revolut/../tests/tours/recovery_order_util";

const IDENTITY_KEY = "revolutTerminalTipIdentity";
const PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf";

registry.category("web_tour.tours").add("pos_revolut_tipped_processing_checkout", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        // No dialog acknowledgement, manual Check status or Validate step:
        // a warning during authorisation prevents this tour reaching receipt.
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "14.34"),
        { trigger: ".receipt-screen .receipt-total:contains('14.34')" },
        { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${PAYMENT_ID}')` },
    ].flat(),
});

for (const integralGoods of [false, true]) {
    const total = integralGoods ? "100.03" : "12.37";
    registry.category("web_tour.tours").add(integralGoods
        ? "pos_revolut_taxed_terminal_tip_rounding_checkout" : "pos_revolut_taxed_terminal_tip_checkout", {
        steps: () => [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            PaymentScreen.clickPaymentMethod("Revolut"),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Revolut", total),
            ReceiptScreen.receiptAmountTotalIs(total),
            {
                content: "Native receipt preserves the reported gross and configured tip tax without artificial rounding",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.get_order();
                    const tips = order.lines.filter((line) => line.product_id === order.config.tip_product_id);
                    if (tips.length !== 1 || tips[0].get_price_with_tax() !== 0.03 ||
                        order.taxTotals.order_total !== Number(total) || order.taxTotals.order_rounding !== 0 ||
                        order.get_due() !== 0 || order.get_change() !== 0 ||
                        document.querySelector(".receipt-rounding")) {
                        throw new Error(`Native taxed-tip receipt changed the collected gross or disguised it as rounding: ${JSON.stringify({
                            tipGross: tips[0]?.get_price_with_tax(), nativeTotal: order.taxTotals.order_total,
                            rounding: order.taxTotals.order_rounding, due: order.get_due(), change: order.get_change(),
                            roundingLine: document.querySelector(".receipt-rounding")?.textContent,
                            extra: tips[0]?.extra_tax_data,
                        })}`);
                    }
                },
            },
            { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${PAYMENT_ID}')` },
            ...(integralGoods ? [
                {
                    trigger: ".receipt-screen",
                    run() {
                        const order = window.posmodel.get_order();
                        sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({
                            orderUuid: order.uuid, tipProductId: order.config.tip_product_id.id,
                        }));
                    },
                },
                refresh(),
                { trigger: "body:not(:has(.pos-loader))" },
                Chrome.clickMenuOption("Orders"),
                TicketScreen.selectFilter("Paid"),
                TicketScreen.selectOrderByPrice(total),
                {
                    content: "Reload preserves the original taxed tip after the configured product changes",
                    trigger: ".ticket-screen .order-row.highlight",
                    run() {
                        const saved = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                        const pos = window.posmodel;
                        const order = pos.models["pos.order"].getBy("uuid", saved.orderUuid);
                        const tips = order?.lines.filter((line) => line.product_id?.id === saved.tipProductId);
                        if (!pos.config.tip_product_id || pos.config.tip_product_id.id === saved.tipProductId || tips?.length !== 1 ||
                            tips[0].get_price_with_tax() !== 0.03 ||
                            order.taxTotals.order_total !== Number(total) || order.taxTotals.order_rounding !== 0 ||
                            order.payment_ids.length !== 1 || order.payment_ids[0].amount !== Number(total)) {
                            throw new Error(`Reload changed the frozen tip: ${JSON.stringify({
                                saved, configuredTip: pos.config.tip_product_id?.id,
                                lines: order?.lines.map((line) => ({product: line.product_id?.id,
                                    extra: line.extra_tax_data})),
                                tipGross: tips?.[0]?.get_price_with_tax(), total: order?.taxTotals.order_total,
                                rounding: order?.taxTotals.order_rounding,
                            })}`);
                        }
                        window.print = (receipt) => {
                            if (!receipt?.classList.contains("pos-receipt") ||
                                !receipt.querySelector(".receipt-total")?.textContent.includes(total) ||
                                receipt.querySelector(".receipt-rounding") ||
                                !receipt.textContent.includes("Verified terminal tip") ||
                                receipt.textContent.split(`Revolut payment: ${PAYMENT_ID}`).length !== 2) {
                                throw new Error("Native reprint changed the original tip, total or payment reference");
                            }
                            document.body.dataset.revolutTaxedTipReprint = "true";
                        };
                    },
                },
                { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
                {
                    trigger: "body[data-revolut-taxed-tip-reprint='true']",
                    run() { sessionStorage.removeItem(IDENTITY_KEY); },
                },
            ] : []),
        ].flat(),
    });
}

registry.category("web_tour.tours").add("pos_revolut_tipped_split_cash_checkout", {
    steps: () => {
        let identity;
        return [
            Chrome.startPoS(),
            ProductScreen.addOrderline("Desk Pad"),
            ProductScreen.clickPayButton(),
            { trigger: ".revolut-choose-amount", run: "click" },
            PaymentScreen.enterPaymentLineAmount("Revolut", "4.34"),
            PaymentScreen.selectedPaymentlineHas("Revolut", "4.34"),
            {
                trigger: ".payment-screen .send_payment_request",
                run() {
                    const order = window.posmodel.get_order();
                    identity = { orderUuid: order.uuid, lineUuid: order.get_selected_paymentline().uuid };
                    this.anchor.click();
                },
            },
            {
                content: "The terminal tip increases the collected gross while leaving the goods balance due",
                trigger: ".payment-screen .electronic_status:contains('Payment Successful')",
                run() {
                    const order = window.posmodel.get_order();
                    const line = order.get_paymentline_by_uuid(identity.lineUuid);
                    if (!line.is_done() || line.amount !== 6.34 || order.get_due() !== 8 ||
                        order.get_total_with_tax() !== 14.34 || order.is_paid() ||
                        line.uiState.revolutSnapshot?.base_amount_minor !== 434 ||
                        line.uiState.revolutSnapshot?.terminal_tip_minor !== 200) {
                        throw new Error("Terminal tip paid another tender's goods balance");
                    }
                    identity.operationId = line.uiState.revolutOperationId;
                },
            },
            PaymentScreen.clickTipButton(),
            NumberPopup.enterValue("5"),
            Dialog.confirm(),
            {
                content: "The native tip action gives specific guidance after a terminal capture",
                trigger: ".modal:contains('This exposed order cannot accept an Odoo tip edit.')",
            },
            Dialog.confirm(),
            {
                content: "Rejecting native tip adjustment preserves the verified tip and payment identity",
                trigger: ".payment-screen",
                run() {
                    const order = window.posmodel.get_order();
                    const line = order.get_paymentline_by_uuid(identity.lineUuid);
                    const tips = order.lines.filter((item) => item.product_id === order.config.tip_product_id);
                    if (order.uuid !== identity.orderUuid || order.get_tip() !== 2 || order.get_due() !== 8 ||
                        tips.length !== 1 || tips[0].get_price_with_tax() !== 2 ||
                        line.amount !== 6.34 || line.transaction_id !== PAYMENT_ID ||
                        line.uiState.revolutOperationId !== identity.operationId) {
                        throw new Error("Rejected tip adjustment mutated the captured financial order");
                    }
                },
            },
            PaymentScreen.clickPaymentMethod("Cash"),
            PaymentScreen.selectedPaymentlineHas("Cash", "8.00"),
            PaymentScreen.clickValidate(),
            ReceiptScreen.isShown(),
            ReceiptScreen.paymentLineContains("Revolut", "6.34"),
            ReceiptScreen.paymentLineContains("Cash", "8.00"),
            ReceiptScreen.receiptAmountTotalIs("14.34"),
            { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${PAYMENT_ID}')` },
            {
                content: "The original split sale settles exactly once with its independent terminal tip",
                trigger: ".receipt-screen",
                run() {
                    const order = window.posmodel.get_order();
                    const line = order.get_paymentline_by_uuid(identity.lineUuid);
                    if (order.uuid !== identity.orderUuid || order.payment_ids.length !== 2 ||
                        !line.is_done() || line.amount !== 6.34 || order.get_due() !== 0 ||
                        order.get_change() !== 0 || !order.is_paid()) {
                        throw new Error("Split tip checkout duplicated the order or tender");
                    }
                },
            },
        ].flat();
    },
});

function assertWaiting() {
    const order = window.posmodel.get_order();
    const line = order.payment_ids.find((payment) => payment.payment_method_id.use_payment_terminal === "revolut");
    if (!line?.uiState.revolutSnapshot?.awaiting_tip_details || line.is_done() ||
        order.state !== "draft" || order.get_total_with_tax() !== 12.34 || line.amount !== 12.34 ||
        order.lines.some((item) => item.product_id === order.config.tip_product_id)) {
        throw new Error("Captured payment completed or projected an unproven tip before the report");
    }
    sessionStorage.setItem(IDENTITY_KEY, JSON.stringify({
        orderUuid: order.uuid, lineUuid: line.uuid,
        operationId: line.uiState.revolutSnapshot.operation_id,
    }));
}

registry.category("web_tour.tours").add("pos_revolut_terminal_tip_report_reload", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Captured gross waits for separately authenticated terminal tip details",
            trigger: ".payment-screen .electronic_status:contains('Payment received'):contains('verifying payment details')",
            run() { assertWaiting(); },
        },
        { trigger: ".modal:contains('Communication with Revolut was interrupted')" },
        Dialog.confirm(),
        {
            content: "The original captured payment remains unpaid and reserved after report interruption",
            trigger: ".payment-screen .send_payment_request:contains('Check status')",
            run() { assertWaiting(); },
        },
        refresh(),
        reopenRevolutOrder(() => JSON.parse(sessionStorage.getItem(IDENTITY_KEY)).orderUuid),
        {
            content: "Reload recovers the same reserved payment without creating another charge",
            trigger: ".pos",
            async run() {
                const saved = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                const order = window.posmodel.get_order();
                const line = order.get_paymentline_by_uuid(saved.lineUuid);
                if (order.uuid !== saved.orderUuid || !line || line.is_done() || line.amount !== 12.34) {
                    throw new Error(`Reload replaced the captured payment or prematurely completed it: ${JSON.stringify({
                        saved, order: order.uuid, screen: window.posmodel.getScreen?.(),
                        payments: order.payment_ids.map((item) => ({uuid: item.uuid, amount: item.amount,
                            status: item.get_payment_status(), uiState: item.uiState})),
                    })}`);
                }
                const check = document.querySelector(".payment-screen .send_payment_request");
                if (!check?.textContent.includes("Check status")) {
                    throw new Error(`Reload cannot resume the captured payment: ${JSON.stringify({
                        screen: window.posmodel.getScreen?.(), order: order.uuid,
                        status: line.get_payment_status(), uiState: line.uiState,
                        buttons: [...document.querySelectorAll(".send_payment_request")].map((item) => item.textContent),
                    })}`);
                }
                check.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "14.34"),
        {
            content: "Native success banner separates base and terminal tip",
            trigger: ".receipt-screen .o_payment_successful:contains('12.34'):contains('2.00 tip')",
        },
        {
            content: "The printable native receipt totals the captured gross",
            trigger: ".receipt-screen .receipt-total:contains('14.34')",
        },
        { trigger: `.receipt-screen .pos-payment-terminal-receipt:contains('${PAYMENT_ID}')` },
        {
            content: "Authenticated tip and gross tender are projected exactly once before native checkout",
            trigger: ".receipt-screen",
            run() {
                const saved = JSON.parse(sessionStorage.getItem(IDENTITY_KEY));
                const order = window.posmodel.get_order();
                const line = order.get_paymentline_by_uuid(saved.lineUuid);
                const tips = order.lines.filter((item) => item.product_id === order.config.tip_product_id);
                if (order.uuid !== saved.orderUuid || !line?.is_done() || line.amount !== 14.34 ||
                    line.transaction_id !== PAYMENT_ID || line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.uiState.revolutSnapshot.operation_id !== saved.operationId ||
                    order.get_total_with_tax() !== 14.34 || tips.length !== 1 || tips[0].get_price_with_tax() !== 2) {
                    throw new Error("Verified checkout duplicated or omitted terminal tip/payment evidence");
                }
                sessionStorage.removeItem(IDENTITY_KEY);
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_global_rounded_tip_return", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Review the server's unrounded canonical base if required",
            trigger: ".modal:contains('Revolut cart needs correction'), .receipt-screen",
            run() {
                const confirm = document.querySelector(".modal .btn-primary");
                confirm?.click();
            },
        },
        {
            content: "Explicitly resume the reviewed rounded allocation",
            trigger: ".payment-screen .send_payment_request:contains('Resume'), .receipt-screen",
            run() {
                const resume = document.querySelector(".payment-screen .send_payment_request");
                resume?.click();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "10.03"),
        { trigger: ".receipt-screen .receipt-to-pay:contains('10.03'), .receipt-screen .receipt-total:contains('10.03')" },
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("10.03"),
        { trigger: ".ticket-screen .orderline:contains('Desk Pad')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        { trigger: ".ticket-screen .orderline:contains('Verified terminal tip')", run: "click" },
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        {
            content: "The new native return has not yet been saved",
            trigger: ".payment-screen",
            run() {
                const order = window.posmodel.get_order();
                if (Number.isInteger(order.id) || order.lines.length !== 2 ||
                    order.lines.some((line) => line.qty !== -1 || !line.refunded_orderline_id)) {
                    throw new Error("The full original goods and tip were not selected into an unsaved return");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-sources .revolut-refund-source:checked" },
        {
            content: "Server-authorized components retain original rounding and exact collected tip",
            trigger: ".revolut-refund-confirm",
            run() {
                const base = Number(document.querySelector(".revolut-refund-amount").value);
                const tip = Number(document.querySelector(".revolut-refund-tip").value);
                if (base !== 10 || tip !== 0.03) {
                    throw new Error(`Expected frozen base10.00 plus tip0.03, received ${base} + ${tip}`);
                }
                this.anchor.click();
            },
        },
        {
            content: "Verified refund automatically completes native checkout with the exact frozen target",
            trigger: ".modal .modal-content, body:not(:has(.modal)) .payment-screen, .receipt-screen",
            async run() {
                const deadline = performance.now() + 8000;
                while (!document.querySelector(".receipt-screen") && performance.now() < deadline) {
                    await new Promise((resolve) => setTimeout(resolve, 100));
                }
                const order = window.posmodel.get_order();
                const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                if (!line?.is_done() || line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.amount !== -10.03 || order.get_total_with_tax() !== -10.03 || order.get_due() !== 0 ||
                    !document.querySelector(".receipt-screen")) {
                    throw new Error(`Refund did not automatically checkout at its frozen native target: ${JSON.stringify({
                        total: order.get_total_with_tax(), rounded: order.getTotalDue(), due: order.get_due(),
                        paid: order.get_total_paid(), isPaid: order.is_paid(), refundInProcess: order.electronic_payment_in_progress(),
                        automatic: window.posmodel.config.auto_validate_terminal_payment,
                        dialog: document.querySelector(".modal")?.textContent,
                        payments: order.payment_ids.map((item) => ({amount: item.amount, status: item.payment_status,
                            snapshot: item.uiState.revolutSnapshot})),
                    })}`);
                }
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "-10.03"),
        { trigger: ".receipt-screen .receipt-to-pay:contains('-10.03'), .receipt-screen .receipt-total:contains('-10.03')" },
        {
            content: "Verified return projects the exact original gross without rounding the tip again",
            trigger: ".receipt-screen",
            run() {
                const order = window.posmodel.get_order();
                const line = order.payment_ids.find((item) => item.payment_method_id.use_payment_terminal === "revolut");
                if (!line?.is_done() || line.amount !== -10.03 || order.get_total_with_tax() !== -10.03 ||
                    line.uiState.revolutSnapshot?.state !== "verified" ||
                    line.uiState.revolutSnapshot.return_total_minor !== 1003) {
                    throw new Error("Full return did not retain the server-verified gross target");
                }
            },
        },
    ].flat(),
});

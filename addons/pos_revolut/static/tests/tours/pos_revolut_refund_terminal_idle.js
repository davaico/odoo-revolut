import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as PaymentScreen from "@point_of_sale/../tests/tours/utils/payment_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/tours/utils/product_screen_util";
import * as ReceiptScreen from "@pos_revolut/../tests/tours/receipt_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_refund_terminal_idle", {
    steps: () => [
        Chrome.startPoS(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        ReceiptScreen.isShown(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .numpad button:contains('1')", run: "click" },
        TicketScreen.confirmRefund(),
        ProductScreen.clickPayButton(),
        PaymentScreen.isShown(),
        {
            content: "Hold refund observation while opening another order",
            trigger: ".payment-screen",
            run() {
                const pos = window.posmodel;
                const call = pos.data.call.bind(pos.data);
                window.revolutPendingReturn = pos.get_order();
                const hold = new Promise((resolve) => { window.releaseRevolutRefund = resolve; });
                const saleHold = new Promise((resolve) => { window.releaseRevolutSale = resolve; });
                let saleStarted;
                window.revolutSaleStarted = new Promise((resolve) => { saleStarted = resolve; });
                pos.data.call = async (model, method, args, ...rest) => {
                    if (model === "pos.payment.method" && method === "revolut_poll_refund") {
                        await hold;
                    }
                    if (model === "pos.payment.method" && method === "revolut_start_payment") {
                        const result = await call(model, method, args, ...rest);
                        saleStarted();
                        await saleHold;
                        return result;
                    }
                    return call(model, method, args, ...rest);
                };
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .send_payment_request", run: "click" },
        { trigger: ".revolut-refund-confirm", run: "click" },
        {
            content: "A pending API refund leaves the physical terminal available",
            trigger: ".payment-screen .electronic_status:contains('Refund in process')",
            run() {
                if (window.posmodel.paymentTerminalInProgress) {
                    throw new Error("Pending Revolut refund incorrectly marks the terminal busy");
                }
                window.posmodel.add_new_order();
                window.posmodel.showScreen("ProductScreen");
            },
        },
        ProductScreen.addOrderline("One cent item"),
        ProductScreen.clickPayButton(),
        {
            content: "The new order can select Revolut without refreshing",
            trigger: ".payment-screen .paymentmethod:contains('Revolut')",
            run() {
                if (this.anchor.classList.contains("opacity-50") || window.posmodel.paymentTerminalInProgress) {
                    throw new Error("Revolut is disabled on the new order after a refund");
                }
            },
        },
        PaymentScreen.clickPaymentMethod("Revolut"),
        {
            content: "Refund completion preserves the terminal lock of the new card payment",
            trigger: ".modal .modal-body, body:not(:has(.modal)) .payment-screen .paymentline:contains('Revolut')",
            async run() {
                const modal = document.querySelector(".modal");
                if (modal) {
                    throw new Error(`Next sale was blocked: ${modal.textContent}`);
                }
                await window.revolutSaleStarted;
                const pos = window.posmodel;
                if (!pos.paymentTerminalInProgress) {
                    throw new Error("The real card payment did not mark the terminal busy");
                }
                const returned = window.revolutPendingReturn;
                const line = returned.payment_ids.find((payment) => payment.amount < 0);
                window.releaseRevolutRefund();
                await line.payment_method_id.payment_terminal.paymentState.owner(returned, line).screenRequest;
                if (!line.is_done() || line.uiState.revolutSnapshot?.state !== "verified" ||
                    pos.get_order().uuid === returned.uuid || pos.get_order().state !== "draft" ||
                    !pos.paymentTerminalInProgress) {
                    throw new Error("Background refund completion corrupted the active checkout");
                }
                window.releaseRevolutSale();
            },
        },
        ReceiptScreen.isShown(),
        ReceiptScreen.paymentLineContains("Revolut", "0.01"),
        {
            content: "Completed sale releases the terminal for subsequent orders",
            trigger: ".receipt-screen",
            run() {
                if (window.posmodel.paymentTerminalInProgress) {
                    throw new Error("Completed card payment left the terminal busy");
                }
                window.posmodel.add_new_order();
                window.posmodel.showScreen("ProductScreen");
            },
        },
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        {
            trigger: ".payment-screen .paymentmethod:contains('Revolut')",
            run() {
                if (this.anchor.classList.contains("opacity-50")) {
                    throw new Error("Revolut remained greyed out on the subsequent order");
                }
            },
        },
    ].flat(),
});

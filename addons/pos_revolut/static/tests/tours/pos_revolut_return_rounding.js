import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_native_conserved_refund_receipt", {
    steps: () => [
        Chrome.startPoS(),
        {
            trigger: ".product-screen",
            run() {
                // Replace only the physical output dialog after native
                // OrderReceipt renders its real freshly loaded order data.
                window.print = (receipt) => {
                    if (!receipt?.classList.contains("pos-receipt")) {
                        throw new Error("Native rounding receipt was not rendered");
                    }
                    const amount = (selector, expected) => {
                        const text = receipt.querySelector(selector)?.textContent || "";
                        if (!text.includes(expected)) {
                            throw new Error(`${selector} lost conserved amount ${expected}: ${text}`);
                        }
                    };
                    amount(".receipt-total", "-9.25");
                    amount(".receipt-rounding", "0.01");
                    amount(".receipt-to-pay", "-9.25");
                    amount(".paymentlines", "-9.25");
                    const ticket = receipt.querySelector(".pos-payment-terminal-receipt")?.textContent.trim();
                    if (!ticket?.startsWith("Revolut refund:") ||
                            receipt.textContent.split(ticket).length !== 2) {
                        throw new Error("Native receipt lost or duplicated its refund reference");
                    }
                    if (!receipt.textContent.includes("Desk Pad") ||
                            !receipt.textContent.includes("0.75") ||
                            !receipt.textContent.includes("12.34")) {
                        throw new Error("Native receipt changed the original product quantity or unit price");
                    }
                    document.body.dataset.nativeConservedRefundPrinted = "true";
                };
            },
        },
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        {
            trigger: ".ticket-screen .order-row:has(.order-name:contains('Historical conserved remaining return'))",
            run: "click",
        },
        { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
        { trigger: "body[data-native-conserved-refund-printed='true']" },
    ].flat(),
});

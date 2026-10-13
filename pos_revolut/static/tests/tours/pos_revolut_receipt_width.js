import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("pos_revolut_receipt_reference_width", {
    steps: () => [
        Chrome.startPoS(),
        {
            trigger: ".product-screen",
            run() {
                // Observe the native rendered document at the print boundary.
                // No provider call or financial record is changed by this adapter.
                window.print = (receipt) => {
                    const fixture = receipt.cloneNode(true);
                    fixture.style.position = "absolute";
                    document.body.appendChild(fixture);
                    try {
                        const reference = fixture.querySelector(".pos-payment-terminal-receipt pre");
                        if (!reference?.textContent.includes("Revolut payment:")) {
                            throw new Error("The native receipt lost its Revolut reference");
                        }
                        const originalText = reference.textContent;
                        for (const width of ["58mm", "80mm"]) {
                            fixture.style.width = width;
                            if (reference.scrollWidth > reference.clientWidth + 1) {
                                throw new Error(`Revolut reference overflows ${width} paper`);
                            }
                            if (reference.textContent !== originalText || reference.clientHeight === 0) {
                                throw new Error("Wrapping must retain the entire printable reference");
                            }
                        }
                        document.body.dataset.revolutReferencePrint = "passed";
                    } finally {
                        fixture.remove();
                    }
                };
            },
        },
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        { trigger: ".ticket-screen .order-row:has(.order-name:contains('Historical native Revolut sale'))", run: "click" },
        { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
        { trigger: "body[data-revolut-reference-print='passed']" },
    ].flat(),
});

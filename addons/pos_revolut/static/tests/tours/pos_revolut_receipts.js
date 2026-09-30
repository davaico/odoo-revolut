import * as Chrome from "@point_of_sale/../tests/pos/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/pos/tours/utils/ticket_screen_util";
import * as ProductScreen from "@point_of_sale/../tests/pos/tours/utils/product_screen_util";
import * as PaymentScreen from "@point_of_sale/../tests/pos/tours/utils/payment_screen_util";
import * as ReceiptScreen from "@point_of_sale/../tests/pos/tours/utils/receipt_screen_util";
import * as Dialog from "@point_of_sale/../tests/generic_helpers/dialog_util";
import { registry } from "@web/core/registry";

function watchReceiptDownloads() {
    return {
        trigger: ".product-screen",
        run() {
            const open = XMLHttpRequest.prototype.open;
            window.revolutReceiptDownloads = [];
            XMLHttpRequest.prototype.open = function (method, url, ...args) {
                if (String(url).startsWith("/pos_revolut/receipt/")) {
                    this.addEventListener("load", async () => {
                        if (this.status === 200) {
                            const signature = await this.response.slice(0, 5).text();
                            if (signature !== "%PDF-" || this.response.type !== "application/pdf") {
                                throw new Error("Receipt download did not return an actual PDF");
                            }
                            const disposition = this.getResponseHeader("Content-Disposition") || "";
                            if (!disposition.includes(".pdf")) {
                                throw new Error("Receipt download has no PDF filename");
                            }
                            window.revolutReceiptDownloads.push(String(url));
                            document.body.dataset.revolutReceiptDownloads = window.revolutReceiptDownloads.length;
                        }
                    });
                }
                return open.call(this, method, url, ...args);
            };
        },
    };
}

function pdfDownloaded(count) {
    return {
        trigger: `body[data-revolut-receipt-downloads='${count}']`,
        timeout: 30000,
    };
}

function openHistoricalReceiptSelection() {
    return [
        Chrome.startPoS(),
        watchReceiptDownloads(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .revolut-receipt-download", run: "click" },
        { trigger: ".revolut-receipt-selection" },
    ].flat();
}

function distinctReceiptDownloads(expectedRefunds) {
    return {
        trigger: ".revolut-receipt-selection",
        run() {
            const urls = window.revolutReceiptDownloads;
            if (new Set(urls).size !== expectedRefunds + 1 ||
                    urls.filter((url) => url.includes("/refund/")).length !== expectedRefunds ||
                    urls.filter((url) => url.includes("/payment/")).length !== 1) {
                throw new Error("Payment and refund receipts were not individually downloaded");
            }
        },
    };
}

registry.category("web_tour.tours").add("pos_revolut_historical_receipt_download", {
    steps: () => [
        Chrome.startPoS(),
        watchReceiptDownloads(),
        Chrome.clickOrders(),
        TicketScreen.selectFilter("Paid"),
        TicketScreen.selectOrderByPrice("12.34"),
        { trigger: ".ticket-screen .revolut-receipt-download", run: "click" },
        pdfDownloaded(1),
        { trigger: ".ticket-screen .revolut-receipt-download:not(:disabled)", run: "click" },
        pdfDownloaded(2),
        {
            trigger: ".ticket-screen",
            run() {
                const [first, second] = window.revolutReceiptDownloads;
                if (first !== second || !first.includes("/payment/")) {
                    throw new Error("Reprinting did not preserve the selected payment receipt");
                }
            },
        },
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_current_receipt_retry", {
    steps: () => [
        Chrome.startPoS(),
        watchReceiptDownloads(),
        ProductScreen.addOrderline("Desk Pad"),
        ProductScreen.clickPayButton(),
        PaymentScreen.clickPaymentMethod("Revolut"),
        { trigger: ".payment-screen .electronic_status:contains('Waiting for card')" },
        ReceiptScreen.isShown().map((step) => ({ ...step, timeout: 30000 })),
        { trigger: ".receipt-screen .revolut-receipt-download", run: "click" },
        { trigger: ".modal:contains('Revolut receipt download failed')" },
        { trigger: ".modal:contains('The payment or refund outcome has not changed.')" },
        Dialog.confirm(),
        { trigger: ".receipt-screen .revolut-receipt-download:not(:disabled)", run: "click" },
        pdfDownloaded(1),
        { trigger: ".receipt-screen .revolut-receipt-download:not(:disabled)", run: "click" },
        pdfDownloaded(2),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_partial_refund_receipts", {
    steps: () => [
        openHistoricalReceiptSelection(),
        { trigger: ".revolut-receipt-selection [data-kind=payment]:contains('12.34')", run: "click" },
        pdfDownloaded(1),
        { trigger: ".revolut-receipt-selection [data-kind=refund]:nth-child(2):contains('6.17'):not(:disabled)", run: "click" },
        pdfDownloaded(2),
        { trigger: ".revolut-receipt-selection [data-kind=refund]:last-child:contains('6.17'):not(:disabled)", run: "click" },
        pdfDownloaded(3),
        distinctReceiptDownloads(2),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_full_refund_receipts", {
    steps: () => [
        openHistoricalReceiptSelection(),
        { trigger: ".revolut-receipt-selection [data-kind=payment]:contains('12.34')", run: "click" },
        pdfDownloaded(1),
        { trigger: ".revolut-receipt-selection [data-kind=refund]:contains('12.34'):not(:disabled)", run: "click" },
        pdfDownloaded(2),
        distinctReceiptDownloads(1),
    ].flat(),
});

registry.category("web_tour.tours").add("pos_revolut_admin_receipt_links", {
    steps: () => [
        { trigger: ".o_form_view" },
        { trigger: ".o_notebook .nav-link:contains('Revolut Receipts')", run: "click" },
        { trigger: ".o_field_widget[name=revolut_receipt_links] a[href*='/payment/']", run: "click" },
        { trigger: ".o_field_widget[name=revolut_receipt_links] li:nth-child(2) a[href*='/refund/']:contains('6.17')", run: "click" },
        { trigger: ".o_field_widget[name=revolut_receipt_links] li:last-child a[href*='/refund/']:contains('6.17')", run: "click" },
        {
            trigger: ".o_field_widget[name=revolut_receipt_links]",
            async run() {
                const links = [...document.querySelectorAll(".o_field_widget[name=revolut_receipt_links] a")];
                if (links.length !== 3 || new Set(links.map((link) => link.href)).size !== 3) {
                    throw new Error("Administration did not preserve the payment and two refund downloads");
                }
                for (const link of links) {
                    const response = await fetch(link.href);
                    const blob = await response.blob();
                    if (!response.ok || blob.type !== "application/pdf" ||
                            await blob.slice(0, 5).text() !== "%PDF-") {
                        throw new Error("Administration receipt link did not return a real PDF");
                    }
                }
            },
        },
    ],
});

registry.category("web_tour.tours").add("pos_revolut_admin_full_refund_receipt_links", {
    steps: () => [
        { trigger: ".o_form_view" },
        { trigger: ".o_notebook .nav-link:contains('Revolut Receipts')", run: "click" },
        { trigger: ".o_field_widget[name=revolut_receipt_links] a[href*='/payment/']", run: "click" },
        { trigger: ".o_field_widget[name=revolut_receipt_links] a[href*='/refund/']:contains('12.34')", run: "click" },
        {
            trigger: ".o_field_widget[name=revolut_receipt_links]",
            async run() {
                const links = [...document.querySelectorAll(".o_field_widget[name=revolut_receipt_links] a")];
                if (links.length !== 2 || new Set(links.map((link) => link.href)).size !== 2) {
                    throw new Error("Administration did not preserve original payment after full refund");
                }
                for (const link of links) {
                    const response = await fetch(link.href);
                    const blob = await response.blob();
                    if (!response.ok || blob.type !== "application/pdf" ||
                            await blob.slice(0, 5).text() !== "%PDF-") {
                        throw new Error("Administration receipt link did not return a real PDF");
                    }
                }
            },
        },
    ],
});

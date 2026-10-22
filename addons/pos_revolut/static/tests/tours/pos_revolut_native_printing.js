import * as Chrome from "@point_of_sale/../tests/tours/utils/chrome_util";
import * as TicketScreen from "@point_of_sale/../tests/tours/utils/ticket_screen_util";
import { refresh } from "@point_of_sale/../tests/tours/utils/common";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

// Observe the browser output boundary after native OrderReceipt rendering. Only
// the physical print dialog is replaced; all POS loading/rendering/write RPCs run.
function observeNativePrinting() {
    return {
        trigger: ".product-screen",
        run() {
            window.nativeReceiptPrints = [];
            const send = XMLHttpRequest.prototype.send;
            XMLHttpRequest.prototype.send = function (body) {
                if (typeof body === "string" && body.startsWith("{")) {
                    const params = JSON.parse(body).params;
                    const count = params?.args?.[1]?.nb_print;
                    if (params?.model === "pos.order" && params.method === "write" && count) {
                        this.addEventListener("load", () => {
                            if (JSON.parse(this.responseText).result === true) {
                                document.body.dataset.nativePrintCount = count;
                            }
                        });
                    }
                }
                return send.call(this, body);
            };
            window.print = (receipt) => {
                if (!receipt?.classList.contains("pos-receipt")) {
                    throw new Error("Native printing did not render an Odoo receipt");
                }
                const text = receipt.textContent;
                if (!text.includes("Desk Pad") || !text.includes("12.34") ||
                        text.split("Revolut payment:").length !== 2) {
                    throw new Error("Historical receipt lost sale details or duplicated Revolut references");
                }
                window.nativeReceiptPrints.push(text);
                document.body.dataset.nativeReceiptPrints = window.nativeReceiptPrints.length;
            };
            // Native account_move.downloadPdf opens this public URL. Fetch the
            // same authenticated URL instead of opening a tab. Odoo's shared-
            // cursor test mode renders HTML; actual PDF bytes are checked by
            // the disposable normal-server verification outside HttpCase.
            // browser.open binds window.open at module startup. Observe that
            // documented browser test adapter, after the native invoice action
            // has resolved its real URL, without patching POS/account methods.
            const open = browser.open;
            browser.open = (url, ...args) => {
                const nativeUrl = new URL(url, window.location.href);
                if (!nativeUrl.pathname.startsWith("/account/download_invoice_documents/")) {
                    return open(url, ...args);
                }
                fetch(url).then(async (response) => {
                    const blob = await response.blob();
                    if (!response.ok) {
                        throw new Error(`Native invoice download failed: ${response.status}`);
                    }
                    const isPdf = await blob.slice(0, 5).text() === "%PDF-";
                    if (isPdf) {
                        if (blob.type !== "application/pdf") {
                            throw new Error("Native invoice PDF has an unexpected content type");
                        }
                    } else {
                        // ir.actions.report._pre_render_qweb_pdf falls back to
                        // HTML when current_test/test_enable is active. Native
                        // invoice attachments may still label those bytes PDF.
                        const invoiceId = nativeUrl.pathname.split("/").at(-2);
                        const html = new DOMParser().parseFromString(await blob.text(), "text/html");
                        const article = html.querySelector(
                            `.article[data-oe-model='account.move'][data-oe-id='${invoiceId}']`
                        );
                        const text = article?.textContent || "";
                        if (!text.includes("Historical native invoice customer") ||
                                !text.includes("Desk Pad") || !text.includes("12.34")) {
                            throw new Error("Native test-mode invoice lost its identity or sale contents");
                        }
                    }
                    document.body.dataset.nativeInvoiceRendering = isPdf ? "pdf" : "test-html";
                    document.body.dataset.nativeInvoiceDownloaded = "true";
                }).catch((error) => {
                    document.body.dataset.nativeInvoiceError = error.message;
                });
                return { closed: false };
            };
        },
    };
}

function openHistoricalOrder(start = true) {
    return [
        ...(start ? [Chrome.startPoS()] : []),
        observeNativePrinting(),
        Chrome.clickMenuOption("Orders"),
        TicketScreen.selectFilter("Paid"),
        { trigger: ".ticket-screen .order-row:contains('Historical native Revolut sale')", run: "click" },
        {
            trigger: ".ticket-screen .order-row.highlight:contains('Historical native Revolut sale')",
            run() {
                if (document.querySelector(".revolut-receipt-download, .revolut-receipt-selection")) {
                    throw new Error("Retired Revolut document controls remain in history");
                }
            },
        },
    ].flat();
}

registry.category("web_tour.tours").add("pos_revolut_native_historical_receipt", {
    steps: () => [
        openHistoricalOrder(),
        { trigger: ".ticket-screen .edit-order-payment:contains('Details')", run: "click" },
        {
            trigger: ".modal .o_form_view",
            run() {
                if (document.querySelector(".modal .o_field_widget[name=revolut_receipt_links]") ||
                        [...document.querySelectorAll(".modal .nav-link")].some((tab) =>
                            tab.textContent.includes("Revolut Receipts"))) {
                    throw new Error("Retired Revolut receipt tab remains in native Details");
                }
            },
        },
        { trigger: ".modal .btn-close", run: "click" },
        { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
        { trigger: "body[data-native-receipt-prints='1'][data-native-print-count='1']" },
        { trigger: ".ticket-screen .control-button:contains('Print Receipt')", run: "click" },
        {
            trigger: "body[data-native-receipt-prints='2'][data-native-print-count='2']",
            run() {
                if (window.nativeReceiptPrints[0] !== window.nativeReceiptPrints[1]) {
                    throw new Error("Reprinting changed the historical receipt contents");
                }
            },
        },
    ].flat(),
});

for (const [name, label] of [
    ["pos_revolut_native_invoice_retrieval", "Reprint Invoice"],
    ["pos_revolut_native_later_invoice", "Invoice"],
]) {
    registry.category("web_tour.tours").add(name, {
        steps: () => [
            openHistoricalOrder(),
            { trigger: `.ticket-screen .control-button:contains('${label}')`, run: "click" },
            {
                trigger: "body[data-native-invoice-downloaded='true'], body[data-native-invoice-error]",
                timeout: 30000,
                run() {
                    if (document.body.dataset.nativeInvoiceError) {
                        throw new Error(document.body.dataset.nativeInvoiceError);
                    }
                },
            },
            // Retrieve the persisted invoice again after a fresh browser load.
            refresh(),
            openHistoricalOrder(false),
            { trigger: ".ticket-screen .control-button:contains('Reprint Invoice')", run: "click" },
            { trigger: "body[data-native-invoice-downloaded='true']", timeout: 30000 },
        ].flat(),
    });
}

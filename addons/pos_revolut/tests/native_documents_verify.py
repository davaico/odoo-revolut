"""Verify committed financial history and actual PDFs with no test-mode fallback."""
import json
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import requests
from odoo.tools.pdf import PdfFileReader

for attempt in range(30):
    try:
        if requests.get("http://odoo:8069/web/login", timeout=2).status_code == 200:
            break
    except (requests.ConnectionError, requests.Timeout):
        pass
    time.sleep(1)
else:
    raise AssertionError("Disposable native report HTTP service did not become ready")

env["ir.config_parameter"].set_param("report.url", "http://odoo:8069")
env.cr.commit()
fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut_test.native_documents"))
native = env(context={**env.context, "allowed_company_ids": [fixture["company"]]})
orders = native["pos.order"].browse(fixture["orders"])
invoices = native["account.move"].browse(fixture["invoices"])
source = native["pos.revolut.payment.operation"].browse(fixture["sources"])
refunds = native["pos.revolut.refund.operation"].browse(fixture["refunds"])
session = native["pos.session"].browse(fixture["sessions"])
output = Path("/var/lib/odoo/native-documents")
output.mkdir(exist_ok=True)


def financial_evidence(*, invoice_action=False):
    native.invalidate_all()
    return {
        "orders": orders.read(["state", "session_id", "amount_total", "amount_tax", "account_move", "to_invoice",
                               *([] if invoice_action else ["write_date"])]),
        "invoices": invoices.read(["state", "name", "amount_total", "amount_tax", "line_ids", "write_date"]),
        "payments": orders.payment_ids.read(["amount", "transaction_id", "payment_ref_no",
                                              *([] if invoice_action else ["write_date"])]),
        "source": source.read(["state", "amount_minor", "revolut_order_id", "revolut_payment_id",
                               *([] if invoice_action else ["write_date"])]),
        "refunds": refunds.read(["state", "amount_minor", "revolut_order_id",
                                 *([] if invoice_action else ["write_date"])]),
        "session": session.read(["state", "move_id", "write_date"]),
        "counts": {name: native[name].sudo().search_count([]) for name in (
            "pos.order", "pos.payment", "stock.picking", "stock.move", "account.move",
            "account.payment", "pos.revolut.payment.operation", "pos.revolut.refund.operation",
            "pos.revolut.payment.dispatch",
        )},
    }


def check_pdf(content, invoice, amount):
    assert content.startswith(b"%PDF-"), "Actual PDF required; HTML fallback is not acceptance"
    reader = PdfFileReader(BytesIO(content))
    assert len(reader.pages) == 1, "Synthetic native document must fit on one readable page"
    text = " ".join(" ".join(page.extractText() for page in reader.pages).split())
    assert "PROFORMA" not in text.upper(), "A proforma fallback is not the saved accounting invoice"
    for expected in (invoice.name, invoice.invoice_origin, "Historical document customer",
                     "Historical document service", amount, invoice.currency_id.symbol):
        assert expected and expected in text, (expected, text)
    if invoice.id == fixture["tip_invoice"]:
        for expected in ("Authenticated conserved terminal tip", "Tip tax 20%", "100.07", "0.02", "0.07"):
            assert expected in text, (expected, text)
        assert invoice.amount_total == 100.09 and invoice.amount_untaxed == 100.07
        assert invoice.amount_tax == 0.02
        assert invoice.invoice_line_ids.filtered("revolut_terminal_tip_line_id").price_subtotal == 0.07
    return text


client = requests.Session()
login = client.post("http://odoo:8069/web/session/authenticate", json={
    "jsonrpc": "2.0", "method": "call", "params": {
        "db": env.cr.dbname, "login": "admin", "password": "admin",
    }, "id": 1,
}, timeout=10).json()
assert login.get("result", {}).get("uid"), "Disposable report login failed"
# Enable the synthetic company's native documents for this authenticated admin.
client.cookies.set("cids", str(fixture["company"]))

with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Native document verification must not contact Revolut")) as provider:
    # Odoo 18's download route returns a proforma if no legal PDF has been
    # generated yet. Exercise native manual Print/Send preparation once, with
    # fallback disabled, then verify retrieval of its saved accounting PDFs.
    native["account.move.send"]._generate_and_send_invoices(
        invoices, sending_methods={"manual"}, allow_fallback_pdf=False,
    )
    for invoice, amount in zip(invoices, fixture["amounts"]):
        assert invoice.invoice_pdf_report_id
        check_pdf(invoice.invoice_pdf_report_id.raw, invoice, amount)
    env.cr.commit()
    before = financial_evidence()
    for index, (invoice, amount) in enumerate(zip(invoices, fixture["amounts"])):
        pdf, extension = native["ir.actions.report"].with_context(force_report_rendering=True)._render_qweb_pdf(
            "account.account_invoices", [invoice.id],
        )
        assert extension == "pdf"
        check_pdf(pdf, invoice, amount)
        (output / f"{index}-native-{invoice.move_type}.pdf").write_bytes(pdf)
        # Native download may create a cached attachment once; financial data
        # and duplicate counts must remain unchanged on the first retrieval too.
        url = invoice.action_invoice_download_pdf()["url"]
        # Release report asset writes before an independent HTTP cursor reads.
        env.cr.commit()
        attachments = None
        for download in range(2):
            response = client.get("http://odoo:8069" + url, timeout=60)
            assert response.status_code == 200, response.status_code
            check_pdf(response.content, invoice, amount)
            assert response.content == invoice.invoice_pdf_report_id.raw
            (output / f"{index}-download-{download}.pdf").write_bytes(response.content)
            after = financial_evidence()
            assert after == before, {
                key: {"before": before[key], "after": value}
                for key, value in after.items() if value != before[key]
            }
            current = native["ir.attachment"].sudo().search_count([
                ("res_model", "=", "account.move"), ("res_id", "=", invoice.id),
            ])
            if attachments is not None:
                assert current == attachments, "Repeated native retrieval created another attachment"
            attachments = current
        print(f"NATIVE_PDF_OK {invoice.move_type} {invoice.name} total={amount} origin={invoice.invoice_origin}")
    for _read in range(2):
        for order in orders:
            data = order.get_ticket_screen_order_data()
            assert data["pos.order"][0]["id"] == order.id
            assert data["pos.payment"][0]["transaction_id"] == order.payment_ids.transaction_id
        assert financial_evidence() == before
    # Calling the explicit native Invoice action again writes its already-true
    # to_invoice flag and relinks existing tenders/operations, updating technical
    # timestamps. Verify idempotent financial
    # identity/counts separately; plain history/download retrieval above is strict.
    invoicing_before = financial_evidence(invoice_action=True)
    for _invoice in range(2):
        for order in orders:
            assert order.action_pos_order_invoice()["res_id"] == order.account_move.id
        after = financial_evidence(invoice_action=True)
        assert after == invoicing_before, {
            key: {"before": invoicing_before[key], "after": value}
            for key, value in after.items() if value != invoicing_before[key]
        }
    assert set(session.mapped("state")) == {"closed"}
    provider.assert_not_called()
print("NATIVE_DOCUMENTS_VERIFY_OK: actual QWeb PDFs, repeated authenticated downloads and historical reads; financial history unchanged")

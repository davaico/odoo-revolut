"""Verify preserved history after a real upgrade from receipt-enabled runtime."""
import json
import time
from io import BytesIO

import requests
from odoo.tools.pdf import PdfFileReader
from unittest.mock import patch

# Wait only for the isolated report/asset service, which has no external route.
for attempt in range(30):
    try:
        if requests.get("http://odoo:8069/web/login", timeout=2).status_code == 200:
            break
    except requests.ConnectionError:
        pass
    time.sleep(1)
else:
    raise AssertionError("Disposable native report HTTP service did not become ready")
env["ir.config_parameter"].set_param("report.url", "http://odoo:8069")
env.cr.commit()

fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut.receipt_retirement_fixture"))
assert "pos.revolut.receipt" not in env.registry, "Retired custom document model remains registered"
assert not hasattr(env["pos.order"], "revolut_receipt_options")
assert "revolut_receipt_links" not in env["pos.order"]._fields
for xmlid in (
    "view_pos_order_revolut_receipts", "action_report_revolut_payment_receipt",
    "action_report_revolut_refund_receipt", "paperformat_revolut_receipt",
    "report_revolut_receipt_layout", "report_revolut_receipt_container",
    "report_revolut_receipt_document", "report_revolut_payment_receipt", "report_revolut_refund_receipt",
):
    assert not env.ref(f"pos_revolut.{xmlid}", raise_if_not_found=False), xmlid
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Upgrade verification must not contact Revolut")) as provider:
    for row in fixture["records"]:
        record = env[row["model"]].browse(row["values"]["id"]).exists()
        assert record, row["model"]
        actual = json.loads(json.dumps(record.read(list(row["values"]))[0], default=str))
        assert actual == row["values"], (row["model"], actual, row["values"])
        if row["model"] == "ir.attachment":
            assert record.checksum == fixture["attachment_checksum"]
            assert record.raw.startswith(b"%PDF-")
    payment = env["pos.revolut.payment.operation"].browse(fixture["payment"])
    assert payment.verified_at and payment.receipt_merchant_snapshot
    assert not payment.deployment_blocking
    invoice = payment.pos_order_id.account_move
    pdf, extension = env["ir.actions.report"].with_context(force_report_rendering=True)._render_qweb_pdf(
        "account.account_invoices", [invoice.id])
    assert extension == "pdf" and pdf.startswith(b"%PDF-")
    reader = PdfFileReader(BytesIO(pdf))
    text = " ".join(" ".join(page.extractText() for page in reader.pages).split())
    for expected in (invoice.name, "Preserved sale", "12.34", invoice.currency_id.symbol):
        assert expected in text, (expected, text)
    # Check the native authenticated invoice-download action separately from
    # QWeb rendering, using disposable default credentials only.
    client = requests.Session()
    login = client.post("http://odoo:8069/web/session/authenticate", json={
        "jsonrpc": "2.0", "method": "call", "params": {
            "db": env.cr.dbname, "login": "admin", "password": "admin",
        }, "id": 1,
    }, timeout=10).json()
    assert login.get("result", {}).get("uid"), "Disposable report login failed"
    url = invoice.action_invoice_download_pdf()["url"]
    for download in range(2):
        response = client.get("http://odoo:8069" + url, timeout=30)
        assert response.status_code == 200 and response.content.startswith(b"%PDF-"), response.status_code
        downloaded = PdfFileReader(BytesIO(response.content))
        download_text = " ".join(" ".join(page.extractText() for page in downloaded.pages).split())
        assert invoice.name in download_text and "12.34" in download_text
    print("NATIVE_INVOICE_PDF_OK: actual QWeb and repeated authenticated native downloads; invoice reference, product, amount and currency extracted", flush=True)
    provider.assert_not_called()
print("RECEIPT_RETIREMENT_VERIFY_OK: all stored financial/document values unchanged; retired interfaces absent; native invoice renders", flush=True)

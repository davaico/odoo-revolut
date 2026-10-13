"""Remove standalone document registrations before validating native order views.

Financial rows, legacy merchant snapshots and saved customer PDFs are retained.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # The old inherited form references a computed field removed in this
    # release. Waiting for normal obsolete XML cleanup breaks view validation.
    for identifier in (
        "view_pos_order_revolut_receipts",
        "action_report_revolut_payment_receipt",
        "action_report_revolut_refund_receipt",
        "report_revolut_payment_receipt",
        "report_revolut_refund_receipt",
        "report_revolut_receipt_document",
        "report_revolut_receipt_container",
        "report_revolut_receipt_layout",
        "paperformat_revolut_receipt",
    ):
        record = env.ref(f"pos_revolut.{identifier}", raise_if_not_found=False)
        if record:
            record.unlink()

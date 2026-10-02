"""Seed receipt-enabled history in the old runtime, without provider traffic."""
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields

assert "pos.revolut.receipt" in env.registry
location, terminal = str(uuid4()), str(uuid4())
method = env["pos.payment.method"].create({
    "name": "Receipt retirement terminal", "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": location, "revolut_terminal_id": terminal,
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
})
config = env["pos.config"].create({
    "name": "Receipt retirement register", "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True,
})
session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
product = env["product.product"].create({
    "name": "Preserved sale", "type": "service", "available_in_pos": True,
    "list_price": 12.34, "taxes_id": [Command.clear()],
})
event = fields.Datetime.now() - timedelta(days=8)
order_uuid, payment_uuid = str(uuid4()), str(uuid4())
payload = {
    "uuid": order_uuid, "name": "Receipt retirement original", "session_id": session.id,
    "user_id": env.uid, "state": "paid", "sequence_number": 1,
    "pricelist_id": config.pricelist_id.id, "fiscal_position_id": False,
    "amount_total": 12.34, "amount_tax": 0, "amount_paid": 12.34, "amount_return": 0,
    "date_order": fields.Datetime.to_string(event), "to_invoice": False,
    "lines": [Command.create({
        "uuid": str(uuid4()), "product_id": product.id, "qty": 1,
        "price_unit": 12.34, "discount": 0, "tax_ids": [Command.set([])],
        "price_subtotal": 12.34, "price_subtotal_incl": 12.34, "pack_lot_ids": [],
    })],
    "payment_ids": [Command.create({
        "uuid": payment_uuid, "payment_method_id": method.id, "amount": 12.34,
        "payment_status": "done", "transaction_id": str(uuid4()),
    })],
}
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Upgrade fixtures must not contact Revolut")) as provider:
    source = env["pos.revolut.payment.operation"].create({
        "payment_method_id": method.id, "company_id": method.company_id.id,
        "pos_config_id": config.id, "pos_session_id": session.id,
        "order_uuid": order_uuid, "payment_line_uuid": payment_uuid,
        "amount": 12.34, "amount_minor": 1234, "currency_id": session.currency_id.id,
        "currency_code": session.currency_id.name, "environment": "sandbox",
        "location_id": location, "terminal_id": terminal, "fulfilment_type": "eat_in",
        "secret_reference": method.revolut_secret_reference, "state": "verified",
        "provider_state": "captured", "verified_at": event,
        "revolut_order_id": str(uuid4()), "revolut_payment_intent_id": str(uuid4()),
        "revolut_payment_id": payload["payment_ids"][0][2]["transaction_id"],
        "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
    })
    env["pos.order"].sync_from_ui([payload])
    source.invalidate_recordset()
    original = source.pos_order_id
    refund_uuid, refund_payment_uuid, refund_reference = [str(uuid4()) for _ in range(3)]
    returned = dict(payload, uuid=refund_uuid, name="Receipt retirement partial return",
                    amount_total=-6.17, amount_paid=-6.17)
    returned["lines"] = [Command.create(dict(payload["lines"][0][2],
        uuid=str(uuid4()), qty=-0.5, price_subtotal=-6.17, price_subtotal_incl=-6.17,
        refunded_orderline_id=original.lines.id))]
    returned["payment_ids"] = [Command.create({
        "uuid": refund_payment_uuid, "payment_method_id": method.id, "amount": -6.17,
        "payment_status": "done", "transaction_id": refund_reference,
    })]
    refund = env["pos.revolut.refund.operation"].create({
        "original_operation_id": source.id, "pos_session_id": session.id,
        "order_uuid": refund_uuid, "payment_line_uuid": refund_payment_uuid,
        "amount": 6.17, "amount_minor": 617, "return_total_minor": 617,
        "currency_id": session.currency_id.id, "state": "verified",
        "provider_state": "completed", "verified_at": event + timedelta(days=1),
        "revolut_order_id": refund_reference,
        "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(returned),
    })
    env["pos.order"].sync_from_ui([returned])
    refund.invalidate_recordset()
    assert source.receipt_merchant_snapshot and refund.receipt_merchant_snapshot
    assert len(original.revolut_receipt_options()) == 2
    # Preserve a customer document independently of report registrations.
    pdf, extension = env["ir.actions.report"].with_context(force_report_rendering=True)._render_qweb_pdf(
        "pos_revolut.action_report_revolut_payment_receipt", [source.id])
    assert extension == "pdf" and pdf.startswith(b"%PDF-")
    attachment = env["ir.attachment"].create({
        "name": "Previously downloaded Revolut receipt.pdf", "type": "binary",
        "raw": pdf, "mimetype": "application/pdf", "res_model": "pos.order", "res_id": original.id,
    })
    # An already-existing native accounting document must also survive.
    partner = env["res.partner"].create({"name": "Retained invoice customer"})
    original.partner_id = partner
    original.with_context(generate_pdf=False).action_pos_order_invoice()
    assert original.account_move.state == "posted"
    session.write({"state": "closed"})
    provider.assert_not_called()

def stored(record):
    names = [name for name, field in record._fields.items()
             if field.store and field.type not in {"one2many", "many2many", "binary"}]
    return record.read(names)[0]

records = [source, refund, original, refund.pos_order_id, original.account_move,
           source.pos_payment_id, refund.pos_payment_id, session, attachment]
env["ir.config_parameter"].set_param("pos_revolut.receipt_retirement_fixture", json.dumps({
    "records": [{"model": record._name, "values": stored(record)} for record in records],
    "attachment_checksum": attachment.checksum,
    "payment": source.id, "refund": refund.id,
}, default=str))
env.cr.commit()
print("RECEIPT_RETIREMENT_SEED_OK: paid/invoiced sale, partial return, closed session, stored PDF and merchant evidence", flush=True)

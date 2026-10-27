"""Seed reviewed-main financial history in an isolated guarded old runtime."""
import json
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields


assert "return_allocation" not in env["pos.revolut.refund.operation"]._fields
location, terminal = str(uuid4()), str(uuid4())
method = env["pos.payment.method"].create({
    "name": "Return rounding upgrade terminal", "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": location, "revolut_terminal_id": terminal,
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
})
config = env["pos.config"].create({
    "name": "Return rounding upgrade register", "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True, "revolut_user_ids": [Command.link(env.uid)],
})
session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
product = env["product.product"].create({
    "name": "Preserved fractional refund sale", "type": "service", "available_in_pos": True,
    "list_price": 12.34, "taxes_id": [Command.clear()],
})


def make_sale(label):
    payload = {
        "uuid": str(uuid4()), "name": label, "session_id": session.id, "user_id": env.uid,
        "state": "paid", "sequence_number": 1, "pricelist_id": config.pricelist_id.id,
        "fiscal_position_id": False, "amount_total": 12.34, "amount_tax": 0,
        "amount_paid": 12.34, "amount_return": 0, "to_invoice": False,
        "date_order": fields.Datetime.to_string(fields.Datetime.now()),
        "lines": [Command.create({
            "uuid": str(uuid4()), "product_id": product.id, "qty": 1,
            "price_unit": 12.34, "discount": 0, "tax_ids": [Command.set([])],
            "price_subtotal": 12.34, "price_subtotal_incl": 12.34, "pack_lot_ids": [],
        })],
        "payment_ids": [Command.create({
            "uuid": str(uuid4()), "payment_method_id": method.id, "amount": 12.34,
            "payment_status": "done", "transaction_id": str(uuid4()),
        })],
    }
    source = env["pos.revolut.payment.operation"].create({
        "payment_method_id": method.id, "company_id": method.company_id.id,
        "pos_config_id": config.id, "pos_session_id": session.id,
        "order_uuid": payload["uuid"], "payment_line_uuid": payload["payment_ids"][0][2]["uuid"],
        "amount": 12.34, "amount_minor": 1234, "currency_id": session.currency_id.id,
        "currency_code": session.currency_id.name, "environment": "sandbox",
        "location_id": location, "terminal_id": terminal, "fulfilment_type": "eat_in",
        "secret_reference": method.revolut_secret_reference, "state": "verified",
        "provider_state": "captured", "verified_at": fields.Datetime.now(),
        "revolut_order_id": str(uuid4()), "revolut_payment_intent_id": str(uuid4()),
        "revolut_payment_id": payload["payment_ids"][0][2]["transaction_id"],
        "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
    })
    env["pos.order"].sync_from_ui([deepcopy(payload)])
    source.invalidate_recordset()
    return source, payload


def return_payload(source, original, quantity, amount, state):
    payload = deepcopy(original)
    payload.update(uuid=str(uuid4()), name="Preserved fractional return", state=state,
                   amount_total=-amount, amount_paid=-amount if state == "paid" else 0)
    payload["lines"][0][2].update(uuid=str(uuid4()), qty=-quantity,
        price_subtotal=-12.34 * quantity, price_subtotal_incl=-12.34 * quantity,
        refunded_orderline_id=source.pos_order_id.lines.id)
    payload["payment_ids"][0][2].update(uuid=str(uuid4()), amount=-amount,
        payment_status="done" if state == "paid" else "waiting", transaction_id=False)
    return payload


def make_refund(source, payload, state, reference):
    return env["pos.revolut.refund.operation"].create({
        "original_operation_id": source.id, "pos_session_id": session.id,
        "order_uuid": payload["uuid"], "payment_line_uuid": payload["payment_ids"][0][2]["uuid"],
        "amount": 3.09, "amount_minor": 309, "return_total_minor": 309,
        "currency_id": session.currency_id.id, "state": state,
        "provider_state": "completed" if state == "verified" else "pending",
        "local_outcome": False if state == "verified" else "interrupted",
        "verified_at": fields.Datetime.now() if state == "verified" else False,
        "revolut_order_id": reference,
        "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
    })


with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Upgrade fixtures must not contact Revolut")) as provider:
    source, original = make_sale("Completed historical quarter original")
    quarter = return_payload(source, original, 0.25, 3.09, "paid")
    reference = str(uuid4())
    quarter["payment_ids"][0][2]["transaction_id"] = reference
    completed = make_refund(source, quarter, "verified", reference)
    env["pos.order"].sync_from_ui([deepcopy(quarter)])
    completed.invalidate_recordset()
    uncertain_source, uncertain_original = make_sale("Uncertain historical quarter original")
    uncertain_payload = return_payload(uncertain_source, uncertain_original, 0.25, 3.09, "draft")
    saved = env["pos.order"].sync_from_ui([deepcopy(uncertain_payload)])
    uncertain_order = env["pos.order"].browse(next(
        row["id"] for row in saved["pos.order"] if row["uuid"] == uncertain_payload["uuid"]))
    uncertain = make_refund(uncertain_source, uncertain_payload, "unresolved", str(uuid4()))
    uncertain.write({"pos_order_id": uncertain_order.id})
    provider.assert_not_called()


def stored(record):
    names = [name for name, field in record._fields.items()
             if field.store and field.type not in {"one2many", "many2many", "binary"}]
    return record.read(names)[0]


records = [source, uncertain_source, completed, uncertain, source.pos_order_id,
           uncertain_source.pos_order_id, completed.pos_order_id, uncertain_order,
           source.pos_payment_id, uncertain_source.pos_payment_id, completed.pos_payment_id,
           uncertain_order.payment_ids, source.pos_order_id.lines, uncertain_source.pos_order_id.lines,
           completed.pos_order_id.lines, uncertain_order.lines]
remaining = return_payload(source, original, 0.75, 9.26, "draft")
env["ir.config_parameter"].set_param("pos_revolut.return_rounding_upgrade_fixture", json.dumps({
    "records": [{"model": record._name, "values": stored(record)} for record in records],
    "method_id": method.id, "source_id": source.id, "completed_id": completed.id,
    "uncertain_id": uncertain.id, "remaining_payload": remaining,
    "uncertain_payload": uncertain_payload,
}, default=str))
env.cr.commit()
print("RETURN_ROUNDING_UPGRADE_SEED_OK: completed 309-cent quarter and immutable uncertain quarter", flush=True)

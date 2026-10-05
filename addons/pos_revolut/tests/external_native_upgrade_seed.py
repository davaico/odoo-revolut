"""Record real old-runtime external refund/acknowledgement history before upgrade."""
import json
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.service.model import call_kw
from odoo.tests.common import new_test_user


assert "native_lot_snapshot" not in env["pos.revolut.refund.operation"]._fields
assert "historical_acknowledged_at" not in env["pos.revolut.refund.operation"]._fields
manager = new_test_user(
    env, login=f"external_upgrade_manager_{uuid4()}",
    groups="base.group_user,point_of_sale.group_pos_manager",
    company_id=env.company.id, company_ids=[Command.set([env.company.id])],
)
method = env["pos.payment.method"].create({
    "name": "External native upgrade terminal", "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
})
config = env["pos.config"].create({
    "name": "External native upgrade register", "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True,
    "revolut_user_ids": [Command.set([env.uid, manager.id])],
})
session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
product = env["product.product"].create({
    "name": "Preserved external refund original service", "type": "service",
    "available_in_pos": True, "list_price": 12.34, "taxes_id": [Command.clear()],
})
context = {"allowed_company_ids": [env.company.id], "generate_pdf": False}


def make_sale(label):
    values = {
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
        "order_uuid": values["uuid"], "payment_line_uuid": values["payment_ids"][0][2]["uuid"],
        "amount": 12.34, "amount_minor": 1234, "currency_id": session.currency_id.id,
        "currency_code": session.currency_id.name, "environment": "sandbox",
        "location_id": method.revolut_location_id, "terminal_id": method.revolut_terminal_id,
        "fulfilment_type": "eat_in", "secret_reference": method.revolut_secret_reference,
        "state": "verified", "provider_state": "captured", "verified_at": fields.Datetime.now(),
        "revolut_order_id": str(uuid4()), "revolut_payment_intent_id": str(uuid4()),
        "revolut_payment_id": values["payment_ids"][0][2]["transaction_id"],
        "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(values),
    })
    env["pos.order"].sync_from_ui([deepcopy(values)])
    source.invalidate_recordset()
    assert source.pos_order_id.state == "paid"
    source.credential_id.write({"next_refund_discovery_at": "2100-01-01"})
    return source


def external(source, state):
    # The mocked evidence seam starts after authenticated provider discovery;
    # all subsequent historical acknowledgement is the actual old public API.
    return env["pos.revolut.refund.operation"].create({
        "origin": "external", "original_operation_id": source.id,
        "pos_session_id": session.id, "amount": 12.34, "amount_minor": 1234,
        "currency_id": session.currency_id.id, "state": state,
        "provider_state": "completed" if state == "verified" else "processing",
        "verified_at": fields.Datetime.now() if state == "verified" else False,
        "revolut_order_id": str(uuid4()), "next_reconcile_at": False,
    })


with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Old upgrade fixtures must not contact Merchant HTTP")) as provider:
    verified_source = make_sale("Historical acknowledged external refund sale")
    pending_source = make_sale("Historical pending external refund sale")
    completed = external(verified_source, "verified")
    pending = external(pending_source, "pending")
    call_kw(env["pos.revolut.refund.operation"].with_user(manager),
            "action_acknowledge_native_reconciliation", [[completed.id]], {"context": context})
    completed.invalidate_recordset()
    assert completed.native_reconciliation_status == "reconciled"
    assert completed.native_reconciled_by == manager
    assert completed.native_reconciled_at
    assert not completed.pos_order_id and not completed.pos_payment_id
    provider.assert_not_called()

# Manager access can schedule stored dependency recomputations. Capture the
# durable old-runtime rows after those writes, rather than stale admin cache.
env.flush_all()
env.invalidate_all()


def stored(record):
    names = [name for name, field in record._fields.items()
             if field.store and field.type not in {"one2many", "many2many", "binary"}]
    values = record.read(names)[0]
    # Display names are UI labels; stored relationship IDs prove preservation.
    return {name: value[0] if record._fields[name].type == "many2one" and value else value
            for name, value in values.items()}


records = [verified_source, pending_source, completed, pending,
           verified_source.pos_order_id, pending_source.pos_order_id,
           verified_source.pos_payment_id, pending_source.pos_payment_id,
           verified_source.pos_order_id.lines, pending_source.pos_order_id.lines]
env["ir.config_parameter"].set_param("pos_revolut.external_native_upgrade_fixture", json.dumps({
    "records": [{"model": record._name, "values": stored(record)} for record in records],
    "manager_id": manager.id, "company_id": env.company.id,
    "method_id": method.id, "session_id": session.id,
    "completed_id": completed.id, "pending_id": pending.id,
    "verified_source_id": verified_source.id, "pending_source_id": pending_source.id,
    "acknowledged_at": completed.native_reconciled_at,
    "completed_line_id": verified_source.pos_order_id.lines.id,
    "pending_line_id": pending_source.pos_order_id.lines.id,
}, default=str))
env.cr.commit()
print("EXTERNAL_NATIVE_UPGRADE_SEED_OK: verified historical acknowledgement and pending external financial history", flush=True)

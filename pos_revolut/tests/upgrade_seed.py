"""Seed actual 19.0.1.8.0 payment history; run only in the disposable upgrade DB."""
import json
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from odoo import Command, fields


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    return result


assert "authorization_id" not in env["pos.revolut.payment.operation"]._fields
product = env["product.product"].create({
    "name": "Upgrade goods", "type": "service", "available_in_pos": True,
    "list_price": 12.34, "taxes_id": [Command.clear()],
})
tip_product = env["product.product"].create({
    "name": "Upgrade configured tip", "type": "service", "list_price": 0,
    "taxes_id": [Command.clear()],
})
history = []
for scenario in ("unexposed", "safe_failed", "verified", "uncertain", "closed_verified", "closed_uncertain"):
    location, terminal = str(uuid4()), str(uuid4())
    method = env["pos.payment.method"].create({
        "name": f"Upgrade {scenario}", "payment_method_type": "terminal",
        "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
        "revolut_location_id": location, "revolut_terminal_id": terminal,
        "revolut_fulfilment_type": "eat_in",
        "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
    })
    config = env["pos.config"].create({
        "name": f"Upgrade {scenario}", "payment_method_ids": [Command.link(method.id)],
        "auto_validate_terminal_payment": True, "tip_product_id": tip_product.id,
    })
    session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
    order_uuid, line_uuid = str(uuid4()), str(uuid4())
    payload = {
        "uuid": order_uuid, "name": f"Upgrade {scenario}", "session_id": session.id,
        "user_id": env.uid, "state": "draft", "sequence_number": 1,
        "pricelist_id": config.pricelist_id.id, "fiscal_position_id": False,
        "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
        "date_order": fields.Datetime.to_string(fields.Datetime.now()), "to_invoice": False,
        "lines": [Command.create({
            "uuid": str(uuid4()), "product_id": product.id, "qty": 1,
            "price_unit": 12.34, "discount": 0, "tax_ids": [Command.set([])],
            "price_subtotal": 12.34, "price_subtotal_incl": 12.34, "pack_lot_ids": [],
        })],
        "payment_ids": [Command.create({
            "uuid": line_uuid, "payment_method_id": method.id, "amount": 12.34,
            "payment_status": "waiting", "transaction_id": False, "name": fields.Datetime.now(),
        })],
    }
    saved = env["pos.order"].sync_from_ui([payload])
    order = env["pos.order"].browse(next(row["id"] for row in saved["pos.order"] if row["uuid"] == order_uuid))
    snapshot = env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
    env.cr.commit()
    operation = env["pos.revolut.payment.operation"]
    if scenario != "unexposed":
        provider_order, intent, payment = str(uuid4()), str(uuid4()), str(uuid4())
        responses = [response({"terminals": [{
            "id": terminal, "online": True, "operation_mode": "pos", "location_id": location,
        }]}), response({"id": provider_order}), response({"id": intent, "state": "pending"})]
        if scenario == "safe_failed":
            responses = [response({"terminals": []})]
        elif scenario.endswith("uncertain"):
            responses[-1] = requests.Timeout("Upgrade fixture lost dispatch response")
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=responses):
            started = method.revolut_start_payment(session.id, order_uuid, line_uuid, 12.34,
                                                   config.currency_id.id, False, snapshot)
        env.cr.rollback()
        env.invalidate_all()
        operation = env["pos.revolut.payment.operation"].browse(started["operation_id"])
        if scenario.endswith("verified"):
            with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=[
                response({"id": intent, "order_id": provider_order, "state": "completed", "payment_id": payment}),
                response({"id": payment, "order_id": provider_order, "amount": 1234,
                          "currency": config.currency_id.name, "state": "captured"}),
            ]):
                observed = method.revolut_poll_payment(operation.id, order_uuid, line_uuid)
                assert observed["state"] == "verified", observed
            env.cr.rollback()
            env.invalidate_all()
            order = env["pos.order"].browse(order.id)
            payload.update(id=order.id, state="paid", amount_paid=12.34)
            payload["lines"] = [Command.update(order.lines.id, payload["lines"][0][2])]
            values = payload["payment_ids"][0][2]
            values.update(payment_status="done", transaction_id=payment)
            payload["payment_ids"] = [Command.update(order.payment_ids.id, values)]
            env["pos.order"].sync_from_ui([payload])
        elif scenario == "safe_failed":
            assert operation.state == "failed" and operation.retry_safe
        else:
            assert not operation.retry_safe and operation.state != "verified"
    if scenario.startswith("closed_"):
        session.write({"state": "closed"})
    fields_to_preserve = [
        "state", "amount", "amount_minor", "order_uuid", "payment_line_uuid", "currency_code",
        "financial_snapshot", "revolut_order_id", "revolut_payment_intent_id", "revolut_payment_id", "retry_safe",
    ]
    history.append({
        "scenario": scenario, "order_id": order.id, "method_id": method.id, "session_id": session.id,
        "operation_id": operation.id if operation else False,
        "operation_values": operation.read(fields_to_preserve)[0] if operation else False,
        "payload": payload,
    })
    env.cr.commit()
env["ir.config_parameter"].set_param("pos_revolut.upgrade_fixture", json.dumps(history, default=str))
env.cr.commit()
print("UPGRADE_SEED_OK: old runtime, six historical states", flush=True)

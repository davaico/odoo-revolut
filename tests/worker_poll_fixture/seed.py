"""Seed two real cashier authorities; financial dispatch is mocked, never live."""

import json
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields
from odoo.tests.common import new_test_user


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    return result


fixture = []
product = env["product.product"].create({
    "name": "Worker probe goods", "type": "service", "available_in_pos": True,
    "list_price": 12.34, "taxes_id": [Command.clear()],
})
for index in (1, 2):
    cashier = new_test_user(
        env, login=f"worker_probe_cashier_{index}", password="probe-only-password",
        groups="base.group_user,point_of_sale.group_pos_user", company_id=env.company.id,
    )
    location, terminal, order_uuid, line_uuid = [str(uuid4()) for _ in range(4)]
    provider_order, provider_intent = [str(uuid4()) for _ in range(2)]
    method = env["pos.payment.method"].create({
        "name": f"Worker probe terminal {index}", "payment_method_type": "terminal",
        "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
        "revolut_location_id": location, "revolut_terminal_id": terminal,
        "revolut_fulfilment_type": "eat_in",
        "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
    })
    config = env["pos.config"].create({
        "name": f"Worker probe register {index}",
        "payment_method_ids": [Command.link(method.id)],
        "revolut_user_ids": [Command.link(cashier.id)],
        "auto_validate_terminal_payment": True,
    })
    session = env["pos.session"].create({
        "config_id": config.id, "user_id": cashier.id, "state": "opened",
    })
    payload = {
        "uuid": order_uuid, "name": f"Worker probe {index}", "session_id": session.id,
        "user_id": cashier.id, "state": "draft", "sequence_number": 1,
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
    saved = env["pos.order"].with_user(cashier).sync_from_ui([payload])
    order_id = next(item["id"] for item in saved["pos.order"] if item["uuid"] == order_uuid)
    env.cr.commit()
    prepared = env["pos.order"].with_user(cashier).revolut_prepare_payment(
        order_id, order_uuid, 0,
        [{"uuid": line_uuid, "payment_method_id": method.id, "amount": 12.34}],
    )
    assert prepared["status"] == "prepared", prepared
    with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=[
        response({"terminals": [{"id": terminal, "online": True,
                                 "operation_mode": "pos", "location_id": location}]}),
        response({"id": provider_order}), response({"id": provider_intent, "state": "pending"}),
    ]) as provider:
        started = method.with_user(cashier).revolut_start_payment(
            session.id, order_uuid, line_uuid, 12.34, config.currency_id.id, False, False,
            prepared["authorization_id"], prepared["cart_version"], prepared["tender_revision"],
        )
        assert started["state"] == "pending", started
        assert len(provider.call_args_list) == 3
        assert sum(call.args[0] == "POST" for call in provider.call_args_list) == 2
    env.cr.rollback()
    env.invalidate_all()
    fixture.append({
        "cashier": index, "login": cashier.login, "uid": cashier.id,
        "method_id": method.id, "operation_id": started["operation_id"],
        "order_uuid": order_uuid, "line_uuid": line_uuid,
        "provider_order": provider_order, "provider_intent": provider_intent,
        "terminal": terminal, "currency": config.currency_id.name,
    })
# Retain the production cron worker count, but quiesce scheduled jobs to isolate
# HTTP contention. Cron overlap is independently covered by existing tests.
env["ir.cron"].search([]).write({"active": False})
env.cr.commit()
root = Path("/var/lib/odoo/status-poll-probe")
root.mkdir()
(root / "fixture.json").write_text(json.dumps(fixture))
print("WORKER_PROBE_SEED_OK: two granted cashiers, authorized pending operations, four mocked financial POSTs", flush=True)

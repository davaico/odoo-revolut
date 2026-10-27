"""Seed an old, unresolved payment without any credential authority model."""

import json
from uuid import uuid4

from odoo import Command


assert "credential_id" not in env["pos.revolut.payment.operation"]._fields
reference = "ODOO_REVOLUT_SECRET_TEST_TERMINAL"
location, terminal, order_uuid, line_uuid, provider_order, intent = [str(uuid4()) for _ in range(6)]
method = env["pos.payment.method"].create({
    "name": "Historical credential review", "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": location, "revolut_terminal_id": terminal,
    "revolut_fulfilment_type": "eat_in", "revolut_secret_reference": reference,
})
config = env["pos.config"].create({
    "name": "Historical credential review", "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True,
})
session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
operation = env["pos.revolut.payment.operation"].create({
    "payment_method_id": method.id, "company_id": method.company_id.id,
    "pos_config_id": config.id, "pos_session_id": session.id,
    "order_uuid": order_uuid, "payment_line_uuid": line_uuid,
    "amount": 0.01, "amount_minor": 1,
    "currency_id": session.currency_id.id, "currency_code": session.currency_id.name,
    "environment": "sandbox", "location_id": location, "terminal_id": terminal,
    "fulfilment_type": "eat_in", "secret_reference": reference,
    "state": "pending", "provider_state": "pending",
    "revolut_order_id": provider_order, "revolut_payment_intent_id": intent,
    "blocking_order_key": f"{method.company_id.id}:{order_uuid}",
    "blocking_terminal_key": f"{method.company_id.id}:sandbox:{terminal}",
})
fixture = {
    "method_id": method.id, "operation_id": operation.id,
    "company_id": method.company_id.id, "order_uuid": order_uuid,
    "line_uuid": line_uuid, "provider_order": provider_order,
    "intent": intent, "reference": reference,
    "order_lock": operation.blocking_order_key,
    "terminal_lock": operation.blocking_terminal_key,
}
env["ir.config_parameter"].set_param("pos_revolut.credential_upgrade_fixture", json.dumps(fixture))
env.cr.commit()
print("CREDENTIAL_UPGRADE_SEED_OK: historical unresolved attempt retained", flush=True)

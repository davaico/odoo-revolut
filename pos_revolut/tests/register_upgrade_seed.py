"""Seed existing users/registers and an uncertain operation before grants exist."""

import json
from uuid import uuid4

from odoo import Command
from odoo.tests.common import new_test_user


assert "revolut_user_ids" not in env["pos.config"]._fields
manager = new_test_user(env, login="register_upgrade_manager", groups="point_of_sale.group_pos_manager")
location, terminal, order_uuid, line_uuid, provider_order, intent, payment = [str(uuid4()) for _ in range(7)]
method = env["pos.payment.method"].create({
    "name": "Register upgrade terminal", "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": location, "revolut_terminal_id": terminal,
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
})
config = env["pos.config"].create({
    "name": "Register upgrade existing register", "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True,
})
session = env["pos.session"].create({"config_id": config.id, "state": "opened", "user_id": manager.id})
operation = env["pos.revolut.payment.operation"].create({
    "payment_method_id": method.id, "company_id": method.company_id.id,
    "pos_config_id": config.id, "pos_session_id": session.id,
    "order_uuid": order_uuid, "payment_line_uuid": line_uuid,
    "amount": 0.01, "amount_minor": 1,
    "currency_id": session.currency_id.id, "currency_code": session.currency_id.name,
    "environment": "sandbox", "location_id": location, "terminal_id": terminal,
    "fulfilment_type": "eat_in", "secret_reference": method.revolut_secret_reference,
    "credential_id": method._revolut_configuration_credential().id,
    "state": "pending", "provider_state": "pending",
    "revolut_order_id": provider_order, "revolut_payment_intent_id": intent,
    "blocking_order_key": f"{method.company_id.id}:{order_uuid}",
    "blocking_terminal_key": f"{method.company_id.id}:sandbox:{terminal}",
})
env["ir.config_parameter"].set_param("pos_revolut.register_upgrade_fixture", json.dumps({
    "config": config.id, "method": method.id, "manager": manager.id, "session": session.id,
    "operation": operation.id, "order_uuid": order_uuid, "line_uuid": line_uuid,
    "provider_order": provider_order, "intent": intent, "payment": payment,
    "location": location, "terminal": terminal,
}))
env.cr.commit()
print("REGISTER_UPGRADE_SEED_OK: existing register, manager/opener and uncertain payment retained", flush=True)

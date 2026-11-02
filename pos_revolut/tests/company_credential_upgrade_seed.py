"""Seed the pre-database-source Odoo 18 authority and financial history."""

import json
from uuid import uuid4

from odoo import Command


assert "source" not in env["pos.revolut.merchant.credential"]._fields
reference = "ODOO_REVOLUT_SECRET_TEST_TERMINAL"
credential = env["pos.revolut.merchant.credential"].create({
    "company_id": env.company.id, "environment": "sandbox", "secret_reference": reference,
})
method = env["pos.payment.method"].create({
    "name": "Synthetic existing environment Merchant", "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
    "revolut_fulfilment_type": "eat_in", "revolut_secret_reference": reference,
})
config = env["pos.config"].create({
    "name": "Synthetic existing environment register",
    "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True,
    "revolut_user_ids": [Command.link(env.user.id)],
})
session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
operations = env["pos.revolut.payment.operation"]
for state in ("verified", "pending"):
    order_uuid = str(uuid4())
    operations |= operations.create({
        "payment_method_id": method.id, "company_id": method.company_id.id,
        "pos_config_id": config.id, "pos_session_id": session.id,
        "order_uuid": order_uuid, "payment_line_uuid": str(uuid4()),
        "amount": 12.34, "amount_minor": 1234, "currency_id": session.currency_id.id,
        "currency_code": session.currency_id.name, "environment": "sandbox",
        "location_id": method.revolut_location_id, "terminal_id": method.revolut_terminal_id,
        "fulfilment_type": "eat_in", "secret_reference": reference,
        "state": state, "provider_state": "captured" if state == "verified" else "pending",
        "revolut_order_id": str(uuid4()), "revolut_payment_intent_id": str(uuid4()),
        "revolut_payment_id": str(uuid4()) if state == "verified" else False,
        "blocking_order_key": f"{method.company_id.id}:{order_uuid}" if state == "pending" else False,
        "blocking_terminal_key": f"{method.company_id.id}:sandbox:{method.revolut_terminal_id}" if state == "pending" else False,
    })
refund = env["pos.revolut.refund.operation"].create({
    "origin": "external", "original_operation_id": operations[0].id,
    "pos_session_id": session.id, "amount": 3.09, "amount_minor": 309,
    "currency_id": session.currency_id.id, "revolut_order_id": str(uuid4()),
    "state": "pending", "provider_state": "pending",
})
snapshot = []
for records, names in (
    (credential, ["company_id", "environment", "secret_reference"]),
    (method, ["company_id", "revolut_environment", "revolut_secret_reference",
              "revolut_location_id", "revolut_terminal_id"]),
    (operations, ["company_id", "credential_id", "payment_method_id", "pos_session_id",
                  "order_uuid", "payment_line_uuid", "amount_minor", "currency_code",
                  "environment", "location_id", "terminal_id", "secret_reference",
                  "state", "provider_state", "revolut_order_id", "revolut_payment_intent_id",
                  "revolut_payment_id", "blocking_order_key", "blocking_terminal_key"]),
    (refund, ["original_operation_id", "payment_method_id", "company_id", "pos_session_id",
              "origin", "state", "provider_state", "amount_minor", "revolut_order_id"]),
):
    snapshot.append({"model": records._name, "ids": records.ids, "fields": names,
                     "values": records.read(names, load=False)})
env["ir.config_parameter"].set_param(
    "pos_revolut.company_credential_upgrade", json.dumps(snapshot),
)
env.cr.commit()
print("COMPANY_CREDENTIAL_UPGRADE_SEED_OK: environment authority, completed/pending payments and pending refund")

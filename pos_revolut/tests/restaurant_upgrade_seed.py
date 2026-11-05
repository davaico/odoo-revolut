"""Commit disposable data on the combined release before the Restaurant split."""

import json
import os
import runpy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons import pos_revolut


mode = os.environ["ODOO_REVOLUT_TEST_UPGRADE_MODE"]
legacy = os.environ.get("ODOO_REVOLUT_TEST_LEGACY_UPGRADE") == "1"
assert mode in {"retail", "mixed"}
params = env["ir.config_parameter"].sudo()
fixtures = Path(pos_revolut.__file__).parent / "tests"
history = []

if not legacy:
    # Use the original release's public POS preparation and dispatch fixtures.
    # They create two durable attempts with provider HTTP mocked.
    runpy.run_path(str(fixtures / "restart_seed.py"), init_globals={"env": env})
    settled, pending = json.loads(params.get_param("pos_revolut.restart_fixture"))
    params.set_param("pos_revolut.restart_fixture", json.dumps([settled]))
    env.cr.commit()
    runpy.run_path(str(fixtures / "restart_wait.py"), init_globals={"env": env})
    with patch("odoo.addons.pos_revolut.models.payment_observation.observation_now",
               return_value=fields.Datetime.now() + timedelta(seconds=2)):
        runpy.run_path(str(fixtures / "restart_verify.py"), init_globals={"env": env})
    operations = env["pos.revolut.payment.operation"].browse(
        [settled["operation_id"], pending["operation_id"]],
    )
    original = operations[0]
    order = original.pos_order_id
    order.sync_from_ui([{
        "uuid": order.uuid, "session_id": order.session_id.id, "state": "paid",
        "date_order": fields.Datetime.to_string(fields.Datetime.now()), "sequence_number": 1,
        "name": order.name, "amount_total": 12.34, "amount_paid": 12.34,
        "amount_tax": 0, "amount_return": 0, "to_invoice": False,
        "lines": [], "payment_ids": [],
    }])
    assert order.state == "paid" and original.pos_payment_id == order.payment_ids
    assert operations[1].state == "pending" and operations[1].pos_order_id.state == "draft"
    refund = env["pos.revolut.refund.operation"].create({
        "origin": "external", "original_operation_id": original.id,
        "pos_session_id": original.pos_session_id.id, "amount": 3.09,
        "amount_minor": 309, "currency_id": original.currency_id.id,
        "revolut_order_id": str(uuid4()), "state": "verified", "provider_state": "completed",
    })
    registers = operations.pos_config_id
    registers.write({"revolut_user_ids": [Command.link(env.uid)]})
    history.extend([
        (registers, ["name", "payment_method_ids", "revolut_user_ids", "tip_product_id",
                     "auto_validate_terminal_payment", "module_pos_restaurant"]),
        (operations.payment_method_id, ["name", "revolut_environment", "revolut_secret_reference",
                                       "revolut_location_id", "revolut_terminal_id"]),
        (operations.credential_id, ["company_id", "environment", "secret_reference"]),
        (operations.authorization_id, ["pos_order_id", "cart_version", "tender_revision", "tenders"]),
        (operations, ["pos_order_id", "pos_payment_id", "authorization_id", "credential_id",
                      "order_uuid", "payment_line_uuid", "amount_minor", "state",
                      "revolut_order_id", "revolut_payment_id", "revolut_payment_intent_id"]),
        (operations.pos_order_id, ["uuid", "session_id", "state", "amount_total", "amount_paid"]),
        (operations.pos_order_id.payment_ids, ["uuid", "pos_order_id", "amount", "transaction_id",
                                             "revolut_order_id", "revolut_payment_intent_id"]),
        (env["pos.revolut.payment.dispatch"].search([("operation_id", "in", operations.ids)]),
         ["operation_id", "outcome"]),
        (refund, ["original_operation_id", "amount_minor", "state", "revolut_order_id",
                  "native_reconciliation_status"]),
    ])
    params.set_param("pos_revolut.restart_fixture", json.dumps([pending]))

# The historic bridge test also keeps native data, including on older
# releases whose payment/authorization fixtures have different contracts.
register = env["pos.config"].create({
    "name": f"Existing {mode} upgrade register", "module_pos_restaurant": mode == "mixed",
})
values = {"uuid": str(uuid4()), "amount_total": 0, "amount_paid": 0,
          "amount_return": 0, "amount_tax": 0}
order_fields = ["uuid", "session_id", "state"]
register_fields = ["name", "module_pos_restaurant"]
if mode == "mixed":
    floor = env["restaurant.floor"].create({
        "name": "Existing Restaurant upgrade floor", "pos_config_ids": [Command.link(register.id)],
    })
    table = env["restaurant.table"].create({
        "floor_id": floor.id, "table_number": 17, "seats": 3,
    })
    preset = env.ref("pos_restaurant.pos_takein_preset", raise_if_not_found=False) or env.ref(
        "pos_revolut.pos_takein_preset",
    )
    register.write({"available_preset_ids": [Command.link(preset.id)]})
    values.update({"table_id": table.id, "preset_id": preset.id})
    order_fields.extend(["table_id", "preset_id"])
    register_fields.append("available_preset_ids")
    history.extend([
        (floor, ["name", "pos_config_ids"]),
        (table, ["floor_id", "table_number", "seats"]),
        (preset, ["name"]),
    ])
session = env["pos.session"].create({"config_id": register.id, "state": "opened"})
order = env["pos.order"].create(dict(values, session_id=session.id))
history.extend([(register, register_fields), (order, order_fields)])
snapshot = [
    {"model": records._name, "ids": records.ids, "fields": names,
     "values": records.read(names, load=False)}
    for records, names in history
]
params.set_param("pos_revolut_test.restaurant_upgrade", json.dumps(snapshot, default=str))
env.cr.commit()
print(f"RESTAURANT_UPGRADE_SEED_OK: {mode}, legacy={legacy}, {len(snapshot)} record sets", flush=True)

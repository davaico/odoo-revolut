"""Verify durable data and original-attempt recovery after a real module update."""

import json
import os
import runpy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from odoo import fields
from odoo.addons import pos_revolut


params = env["ir.config_parameter"].sudo()
snapshot = json.loads(params.get_param("pos_revolut_test.restaurant_upgrade"))
assert snapshot, "No pre-upgrade data snapshot"
for entry in snapshot:
    records = env[entry["model"]].browse(entry["ids"]).exists()
    assert records.ids == entry["ids"], f"Upgrade removed {entry['model']} records"
    observed = json.loads(json.dumps(records.read(entry["fields"], load=False), default=str))
    for name in entry["fields"]:
        if records._fields[name].type == "many2many":
            for values in observed + entry["values"]:
                values[name] = sorted(values[name])
    assert observed == entry["values"], f"Upgrade changed {entry['model']} history"

if os.environ.get("ODOO_REVOLUT_TEST_LEGACY_UPGRADE") != "1":
    fixture, = json.loads(params.get_param("pos_revolut.restart_fixture"))
    operation = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
    method = operation.payment_method_id
    with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
               side_effect=AssertionError("Payment replay must reuse original dispatch")) as provider:
        replay = method.revolut_start_payment(
            fixture["session_id"], fixture["order_uuid"], fixture["line_uuid"],
            12.34, operation.currency_id.id, False, False, fixture["authorization_id"],
            fixture["cart_version"], fixture["tender_revision"],
        )
        assert replay["operation_id"] == operation.id and replay["state"] == "pending", replay
        provider.assert_not_called()
    if os.environ.get("ODOO_REVOLUT_TEST_UPGRADE_FINAL") == "1":
        # The restart fixtures assert provider finality and exactly two original
        # dispatch ledger entries. Status report creation is the only new POST.
        fixtures = Path(pos_revolut.__file__).parent / "tests"
        runpy.run_path(str(fixtures / "restart_wait.py"), init_globals={"env": env})
        with patch("odoo.addons.pos_revolut.models.payment_observation.observation_now",
                   return_value=fields.Datetime.now() + timedelta(seconds=2)):
            runpy.run_path(str(fixtures / "restart_verify.py"), init_globals={"env": env})
        env.invalidate_all()
        assert operation.state == "verified"
        assert operation.revolut_payment_id == fixture["provider_payment"]

print("RESTAURANT_UPGRADE_VERIFIED: preserved native and Revolut records", flush=True)

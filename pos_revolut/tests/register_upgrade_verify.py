"""Verify upgrade fails closed without preventing trusted late-success recovery."""

import json
from unittest.mock import Mock, patch

from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import call_kw


fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut.register_upgrade_fixture"))
config = env["pos.config"].browse(fixture["config"])
method = env["pos.payment.method"].browse(fixture["method"])
manager = env["res.users"].browse(fixture["manager"])
operation = env["pos.revolut.payment.operation"].browse(fixture["operation"])
assert not env["pos.config"].search([("revolut_user_ids", "!=", False)])
assert operation.state == "pending" and operation.blocking_terminal_key and operation.blocking_order_key
assert operation.revolut_order_id == fixture["provider_order"]
assert operation.revolut_payment_intent_id == fixture["intent"]
assert env.ref("pos_revolut.ir_cron_reconcile_payments").user_id == env.ref("base.user_root")
args = [[method.id], fixture["order_uuid"], fixture["line_uuid"]]
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as request:
    try:
        call_kw(method.with_user(manager), "revolut_find_payment", args, {})
    except AccessError:
        pass
    else:
        raise AssertionError("Upgrade silently granted manager/session opener access")
    request.assert_not_called()

# Root cron reconciles the same immutable operation, with no replacement charge.
def provider(verb, url, **kwargs):
    assert verb == "GET", "Upgrade recovery must never dispatch a replacement charge"
    response = Mock(status_code=200)
    if url.endswith(f"/api/payment-intents/{fixture['intent']}"):
        response.json.return_value = {"id": fixture["intent"], "order_id": fixture["provider_order"],
            "payment_id": fixture["payment"], "state": "completed", "amount": 1,
            "currency": operation.currency_code, "terminal_id": fixture["terminal"]}
    elif url.endswith(f"/api/payments/{fixture['payment']}"):
        response.json.return_value = {"id": fixture["payment"], "order_id": fixture["provider_order"],
            "state": "captured", "amount": 1, "currency": operation.currency_code,
            "location_id": fixture["location"]}
    else:
        raise AssertionError(f"Unexpected mocked request: {verb} {url}")
    return response

with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=provider) as request:
    env["pos.revolut.payment.operation"]._cron_reconcile_payments()
    assert request.call_count == 2
env.cr.commit()
env.invalidate_all()
assert operation.state == "verified" and operation.revolut_payment_id == fixture["payment"]
assert not config.revolut_user_ids
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as request:
    try:
        call_kw(method.with_user(manager), "revolut_find_payment", args, {})
    except AccessError:
        pass
    else:
        raise AssertionError("Late success reauthorized the revoked/ungranted user")
    config.write({"revolut_user_ids": [Command.link(manager.id)]})
    env.cr.commit()
    recovered = call_kw(method.with_user(manager), "revolut_find_payment", args, {})
    assert recovered["operation_id"] == operation.id and recovered["state"] == "verified"
    request.assert_not_called()
created = env["pos.config"].create({"name": "Register upgrade new register"})
copied = config.copy({"name": "Register upgrade copied register"})
assert not created.revolut_user_ids and not copied.revolut_user_ids
assert operation.pos_config_id == config and operation.pos_session_id.id == fixture["session"]
env.cr.commit()
print("REGISTER_UPGRADE_VERIFY_OK: no implicit grants; late success reconciled; original recovered after explicit grant", flush=True)

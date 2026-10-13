"""Verify fail-closed migration and explicit recovery in a new Odoo process."""

import json
from unittest.mock import Mock, patch

from odoo.exceptions import UserError


fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut.credential_upgrade_fixture"))
method = env["pos.payment.method"].browse(fixture["method_id"])
operation = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
assert not env["pos.revolut.merchant.credential"].search([])
assert not operation.credential_id
assert operation.state == "pending"
assert operation.blocking_order_key == fixture["order_lock"]
assert operation.blocking_terminal_key == fixture["terminal_lock"]
assert operation.revolut_order_id == fixture["provider_order"]
assert operation.revolut_payment_intent_id == fixture["intent"]

with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
    with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get") as check:
        try:
            method.action_revolut_check_connection()
        except UserError:
            pass
        else:
            raise AssertionError("Unmapped historical configuration checked a Merchant account")
        try:
            method._revolut_api_request({
                "credential_operation_id": operation.id,
                "environment": operation.environment,
                "secret_reference": operation.secret_reference,
            }, "GET", f"/api/payment-intents/{fixture['intent']}")
        except UserError:
            pass
        else:
            raise AssertionError("Unmapped historical operation contacted Merchant")
        polled = method.revolut_poll_payment(operation.id, fixture["order_uuid"], fixture["line_uuid"])
        assert polled["state"] in {"pending", "unresolved"}, polled
        provider.assert_not_called()
        check.assert_not_called()

env.cr.rollback()
env.invalidate_all()
method = env["pos.payment.method"].browse(fixture["method_id"])
operation = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
assert operation.blocking_order_key == fixture["order_lock"]
assert operation.blocking_terminal_key == fixture["terminal_lock"]

# The system administrator separately verified this fixture's original
# account. In production that verification is an operator decision, never an
# inferred migration from the old method's untrusted reference.
env["pos.revolut.merchant.credential"].create({
    "company_id": fixture["company_id"],
    "environment": operation.environment,
    "secret_reference": fixture["reference"],
})
assert env["pos.revolut.merchant.credential"].search_count([
    ("company_id", "=", fixture["company_id"]),
    ("secret_reference", "=", fixture["reference"]),
]) == 1
assert not operation.credential_id
operation.action_revolut_authorize_legacy_credential()
assert operation.credential_id.company_id.id == fixture["company_id"]

response = Mock(status_code=200)
response.json.return_value = {
    "id": fixture["intent"], "order_id": fixture["provider_order"],
    "state": "pending", "amount": 1, "currency": operation.currency_code,
    "terminal_id": operation.terminal_id,
}
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", return_value=response) as provider:
    observed = method.revolut_poll_payment(operation.id, fixture["order_uuid"], fixture["line_uuid"])
    assert observed["state"] in {"pending", "unresolved"}, observed
    assert provider.call_count == 1
    assert all(call.args[0] == "GET" for call in provider.call_args_list)
env.cr.rollback()
env.invalidate_all()
operation = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
assert operation.blocking_order_key == fixture["order_lock"]
assert operation.blocking_terminal_key == fixture["terminal_lock"]
assert operation.revolut_order_id == fixture["provider_order"]
assert operation.revolut_payment_intent_id == fixture["intent"]
print("CREDENTIAL_UPGRADE_VERIFY_OK: legacy attempt failed closed, admin attested, GET-only recovery", flush=True)

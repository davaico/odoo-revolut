"""Verify the existing source and history in a fresh process after the update."""

import json
from unittest.mock import Mock, patch


snapshot = json.loads(env["ir.config_parameter"].get_param("pos_revolut.company_credential_upgrade"))
for entry in snapshot:
    records = env[entry["model"]].browse(entry["ids"]).exists()
    assert records.ids == entry["ids"], f"Upgrade removed {entry['model']} records"
    assert records.read(entry["fields"], load=False) == entry["values"], f"Upgrade changed {entry['model']} history"
credential = env["pos.revolut.merchant.credential"].browse(snapshot[0]["ids"])
method = env["pos.payment.method"].browse(snapshot[1]["ids"])
operations = env["pos.revolut.payment.operation"].browse(snapshot[2]["ids"])
refund = env["pos.revolut.refund.operation"].browse(snapshot[3]["ids"])
assert credential.source == "environment"
assert not credential.secret_key and not credential.revoked
assert method._revolut_configuration_credential() == credential
assert operations.credential_id == credential
assert refund.original_operation_id.credential_id == credential
assert sorted(operations.mapped("state")) == ["pending", "verified"]

pending = operations.filtered(lambda item: item.state == "pending")
response = Mock(status_code=200)
response.json.return_value = {
    "id": pending.revolut_payment_intent_id, "order_id": pending.revolut_order_id,
    "state": "pending", "amount": pending.amount_minor, "currency": pending.currency_code,
    "terminal_id": pending.terminal_id,
}
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", return_value=response) as provider:
    observed = method.revolut_poll_payment(pending.id, pending.order_uuid, pending.payment_line_uuid)
    assert observed["state"] == "pending", observed
    assert provider.call_count == 1
    assert provider.call_args.args[0] == "GET"
    assert provider.call_args.kwargs["headers"]["Authorization"] == "Bearer test-only-not-a-credential"
response.json.return_value = {
    "id": refund.revolut_order_id, "type": "refund",
    "related_order_id": refund.original_operation_id.revolut_order_id,
    "state": "pending", "amount": refund.amount_minor,
    "currency": refund.currency_id.name,
}
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", return_value=response) as provider:
    observed = method.revolut_poll_refund(refund.id)
    assert observed["state"] == "pending", observed
    assert provider.call_count == 1
    assert provider.call_args.args[0] == "GET"
    assert provider.call_args.kwargs["headers"]["Authorization"] == "Bearer test-only-not-a-credential"
print("COMPANY_CREDENTIAL_UPGRADE_VERIFIED: unchanged environment authority/history and GET-only payment/refund recovery")

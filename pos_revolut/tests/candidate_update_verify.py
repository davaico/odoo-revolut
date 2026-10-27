"""Verify committed configuration and financial identities after addon update."""
import json
import os
from unittest.mock import patch


snapshot = json.loads(env["ir.config_parameter"].sudo().get_param(
    "pos_revolut_test.candidate_update",
))
assert any(entry["model"] == "pos.revolut.payment.operation" for entry in snapshot), "Missing committed payment update evidence"
assert any(entry["model"] == "pos.revolut.refund.operation" for entry in snapshot), "Missing committed refund update evidence"
assert any(entry["model"] == "pos.revolut.cart.authorization" for entry in snapshot), "Missing committed current cart authority update evidence"
for entry in snapshot:
    records = env[entry["model"]].browse(entry["ids"]).exists()
    assert records.ids == entry["ids"], f"Candidate {entry['model']} records were removed"
    observed = json.loads(json.dumps(records.read(entry["fields"], load=False), default=str, sort_keys=True))
    # Membership is stable across processes; native Many2many query order is not.
    for name in entry["fields"]:
        if records._fields[name].type == "many2many":
            for row in observed + entry["values"]:
                row[name] = sorted(row[name])
    assert observed == entry["values"], f"Candidate {entry['model']} records changed: {observed!r}"
credential_id = next(entry["ids"] for entry in snapshot if entry["model"] == "pos.revolut.merchant.credential")
method_id = next(entry["ids"] for entry in snapshot if entry["model"] == "pos.payment.method")
config_id = next(entry["ids"] for entry in snapshot if entry["model"] == "pos.config")
cashier_id = next(entry["ids"] for entry in snapshot if entry["model"] == "res.users")
method = env["pos.payment.method"].browse(method_id)
assert method._revolut_configuration_credential().ids == credential_id
env["pos.config"].browse(config_id).with_user(env["res.users"].browse(cashier_id)).with_context(
    allowed_company_ids=method.company_id.ids,
)._check_revolut_register_access()
configured = env(context={**env.context, "allowed_company_ids": method.company_id.ids})
operation_ids = next(entry["ids"] for entry in snapshot if entry["model"] == "pos.revolut.payment.operation")
operations = configured["pos.revolut.payment.operation"].browse(operation_ids)
authority_ids = next(entry["ids"] for entry in snapshot if entry["model"] == "pos.revolut.cart.authorization")
assert len(authority_ids) == 2 and sorted(operations.authorization_id.ids) == sorted(authority_ids)
for operation in operations:
    authority = operation.authorization_id
    assert authority and authority.pos_order_id == operation.pos_order_id
    assert operation.pos_order_id.revolut_authorization_id == authority
    assert operation.cart_version == authority.cart_version
    assert operation.tender_revision == authority.tender_revision
    assert authority.canonical and authority.native_contents and authority.projected_snapshot and authority.tenders
assert sorted(operations.mapped("state")) == ["unresolved", "verified"]
assert sorted(operations.pos_order_id.mapped("state")) == ["draft", "paid"]
assert operations.filtered(lambda operation: operation.state == "unresolved").deployment_blocking
refund_ids = next(entry["ids"] for entry in snapshot if entry["model"] == "pos.revolut.refund.operation")
refunds = configured["pos.revolut.refund.operation"].browse(refund_ids)
assert sorted(refunds.mapped("state")) == ["pending", "unresolved", "verified"]
assert sum(refunds.mapped("amount_minor")) == 618
assert refunds.filtered(lambda refund: refund.state == "unresolved").deployment_blocking
assert refunds.filtered(lambda refund: refund.origin == "external").native_reconciliation_status == "outstanding"
manager = configured["res.users"].browse(next(
    identifier for identifier in configured["pos.config"].browse(config_id).revolut_user_ids.ids
    if identifier not in cashier_id
))
with patch.dict(os.environ, {method.revolut_secret_reference: "synthetic-update-secret"}), patch(
           "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Update recovery reads must not contact Revolut")) as provider:
    for operation in operations:
        found = method.with_env(configured).with_user(configured["res.users"].browse(cashier_id)).revolut_find_payment(
            operation.order_uuid, operation.payment_line_uuid, operation.pos_session_id.id,
        )
        assert found["operation_id"] == operation.id and found["state"] == operation.state
        assert found["order_id"] == operation.revolut_order_id
        assert found["payment_intent_id"] == operation.revolut_payment_intent_id
        if operation.state == "unresolved":
            authority = operation.authorization_id
            resumed = configured["pos.order"].with_user(manager).revolut_prepare_payment(
                operation.pos_order_id.id, operation.order_uuid, authority.cart_version, [{
                    "uuid": operation.payment_line_uuid, "payment_method_id": method.id, "amount": 12.34,
                }],
            )
            assert resumed["authorization_id"] == authority.id
            assert resumed["cart_version"] == authority.cart_version
            assert resumed["tender_revision"] == authority.tender_revision
            replay = method.with_env(configured).with_user(manager).revolut_start_payment(
                operation.pos_session_id.id, operation.order_uuid, operation.payment_line_uuid,
                12.34, operation.currency_id.id, False, False, authority.id,
                authority.cart_version, authority.tender_revision,
            )
            assert replay["operation_id"] == operation.id and replay["state"] == "unresolved"
    for refund in refunds.filtered(lambda record: record.origin == "odoo"):
        found = method.with_env(configured).with_user(manager).revolut_find_refund(
            refund.order_uuid, refund.payment_line_uuid,
        )
        assert found["operation_id"] == refund.id and found["state"] == refund.state
        assert found["order_id"] == refund.revolut_order_id
    provider.assert_not_called()
print("CANDIDATE_UPDATE_VERIFIED: completed/unresolved native records, original references, claims, reservations, grants and read-only recovery preserved")

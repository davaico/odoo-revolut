"""Verify real reviewed-main history after installing conserved allocations."""
import json
from unittest.mock import patch

from odoo.api import call_kw


fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut.return_rounding_upgrade_fixture"))
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Upgrade verification must not contact Revolut")) as provider:
    for row in fixture["records"]:
        record = env[row["model"]].browse(row["values"]["id"]).exists()
        assert record, row["model"]
        actual = json.loads(json.dumps(record.read(list(row["values"]))[0], default=str))
        assert actual == row["values"], (row["model"], actual, row["values"])
        if record._name == "pos.order":
            assert not record.revolut_return_allocation
        if record._name == "pos.revolut.refund.operation":
            assert not record.return_allocation
    method = env["pos.payment.method"].browse(fixture["method_id"])
    source = env["pos.revolut.payment.operation"].browse(fixture["source_id"])
    uncertain = env["pos.revolut.refund.operation"].browse(fixture["uncertain_id"])
    sources = call_kw(env["pos.payment.method"], "revolut_refund_sources", [
        [method.id], source.pos_session_id.id, source.currency_id.id, fixture["remaining_payload"],
    ], {})
    eligible = next(row for row in sources if row["operation_id"] == source.id)
    assert eligible["remaining_minor"] == 925, eligible
    assert eligible["return_total_minor"] == 925, eligible
    recovered = call_kw(env["pos.payment.method"], "revolut_find_refund", [
        [method.id], uncertain.order_uuid, uncertain.payment_line_uuid,
    ], {})
    assert recovered["operation_id"] == uncertain.id, recovered
    assert recovered["order_id"] == uncertain.revolut_order_id, recovered
    assert recovered["return_total_minor"] == 309, recovered
    replayed = call_kw(env["pos.payment.method"], "revolut_start_refund", [
        [method.id], uncertain.pos_session_id.id, uncertain.order_uuid, uncertain.payment_line_uuid,
        -uncertain.amount, uncertain.currency_id.id, fixture["uncertain_payload"],
        uncertain.original_operation_id.id,
    ], {})
    assert replayed["operation_id"] == uncertain.id, replayed
    assert replayed["order_id"] == uncertain.revolut_order_id, replayed
    assert replayed["state"] == "unresolved", replayed
    provider.assert_not_called()
print("RETURN_ROUNDING_UPGRADE_VERIFY_OK: immutable history unchanged; remaining 925 cents; uncertain replay reuses references without HTTP", flush=True)

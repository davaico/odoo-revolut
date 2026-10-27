"""Exercise manager native completion after a real pre-ticket-41 schema upgrade."""
import json
from unittest.mock import patch
from uuid import uuid4

from odoo.exceptions import UserError, ValidationError
from odoo.api import call_kw


fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut.external_native_upgrade_fixture"))
context = {"allowed_company_ids": [fixture["company_id"]], "generate_pdf": False}
manager = env["res.users"].browse(fixture["manager_id"])
completed = env["pos.revolut.refund.operation"].browse(fixture["completed_id"])
pending = env["pos.revolut.refund.operation"].browse(fixture["pending_id"])
financial_fields = ["origin", "original_operation_id", "pos_session_id", "amount", "amount_minor",
                    "currency_id", "state", "provider_state", "revolut_order_id", "related_order_id",
                    "dispatched_at", "verified_at", "idempotency_key"]


def stored(record, names):
    values = record.read(names)[0]
    return json.loads(json.dumps({
        name: value[0] if record._fields[name].type == "many2one" and value else value
        for name, value in values.items()
    }, default=str))


def rpc(refund, method, *args):
    return call_kw(env["pos.revolut.refund.operation"].with_user(manager), method,
                   [[refund.id], *args], {"context": context})


def rejected(action, expected=(UserError, ValidationError)):
    try:
        with env.cr.savepoint():
            action()
    except expected:
        return
    raise AssertionError("Protected native workflow unexpectedly accepted an invalid action")


with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("History upgrade/native completion must not contact Merchant HTTP")) as provider:
    for row in fixture["records"]:
        record = env[row["model"]].browse(row["values"]["id"]).exists()
        assert record, row["model"]
        actual = stored(record, list(row["values"]))
        assert actual == row["values"], (row["model"], actual, row["values"])
    assert completed.native_reconciliation_status == "reconciled"
    assert completed.native_reconciled_by == manager
    assert str(completed.native_reconciled_at) == fixture["acknowledged_at"]
    assert not completed.pos_order_id and not completed.pos_payment_id
    assert not completed.historical_acknowledged_at and not completed.historical_acknowledged_by
    for refund in (completed, pending):
        assert not refund.provider_initiated_at and not refund.last_provider_observed_at
        assert not refund.order_uuid and not refund.payment_line_uuid and not refund.financial_snapshot
        assert not refund.return_allocation and not refund.allocation_explicit
        assert not refund.financial_correction_move_id
    assert pending.state == "pending" and pending.native_reconciliation_status == "outstanding"
    before_completed = stored(completed, financial_fields)
    before_pending = stored(pending, financial_fields)
    rejected(lambda: rpc(completed, "action_acknowledge_native_reconciliation"))
    rejected(lambda: rpc(pending, "action_acknowledge_native_reconciliation"))

    # A migrated pending external refund still consumes its entire card source
    # before it acquires any native product evidence.
    source = env["pos.revolut.payment.operation"].browse(fixture["pending_source_id"])
    original = source.pos_order_id
    candidate = {
        "uuid": str(uuid4()), "amount_total": -12.34,
        "pricelist_id": original.pricelist_id.id, "fiscal_position_id": False,
        "lines": [{"uuid": str(uuid4()), "product_id": original.lines.product_id.id,
                   "qty": -1, "price_unit": 12.34, "discount": 0, "tax_ids": [],
                   "refunded_orderline_id": original.lines.id}],
    }
    sources = call_kw(env["pos.payment.method"].with_user(manager), "revolut_refund_sources", [
        [fixture["method_id"]], fixture["session_id"], source.currency_id.id, candidate,
    ], {"context": context})
    capacity = next(row for row in sources if row["operation_id"] == source.id)
    assert capacity["remaining_minor"] == 0, capacity

    action = rpc(completed, "action_prepare_native_return", [{
        "original_line_id": fixture["completed_line_id"], "quantity": 1,
    }])
    native = env["pos.order"].browse(action["res_id"])
    assert native.state == "draft" and native.amount_total == -12.34
    assert completed.historical_acknowledged_by == manager
    assert str(completed.historical_acknowledged_at) == fixture["acknowledged_at"]
    assert completed.native_reconciliation_status == "native_draft"
    rpc(completed, "action_validate_native_return")
    assert native.state == "paid" and completed.native_reconciliation_status == "native_completed"
    assert native.lines.refunded_orderline_id.id == fixture["completed_line_id"]
    assert native.payment_ids.revolut_refund_operation_id == completed
    assert native.payment_ids.amount == -12.34
    assert native.payment_ids.transaction_id == completed.revolut_order_id
    assert not native.picking_ids and not native.account_move
    evidence = (native.id, native.payment_ids.ids, native.lines.ids, completed.native_reconciled_at)
    assert rpc(completed, "action_prepare_native_return")["res_id"] == native.id
    rpc(completed, "action_validate_native_return")
    assert (native.id, native.payment_ids.ids, native.lines.ids, completed.native_reconciled_at) == evidence
    assert stored(completed, financial_fields) == before_completed
    assert not completed.provider_initiated_at and not completed.last_provider_observed_at

    pending_action = rpc(pending, "action_prepare_native_return", [{
        "original_line_id": fixture["pending_line_id"], "quantity": 1,
    }])
    draft = env["pos.order"].browse(pending_action["res_id"])
    assert draft.state == "draft" and draft.payment_ids.payment_status == "waiting"
    rejected(lambda: rpc(pending, "action_validate_native_return"))
    rejected(lambda: draft.payment_ids.with_user(manager).write({"payment_status": "done"}))
    rejected(lambda: draft.with_user(manager).write({"state": "paid"}))
    rejected(lambda: draft.with_user(manager).unlink())
    assert rpc(pending, "action_prepare_native_return")["res_id"] == draft.id
    assert draft.state == "draft" and draft.payment_ids.payment_status == "waiting"
    assert stored(pending, financial_fields) == before_pending
    assert pending.pos_session_id.id == fixture["session_id"]
    assert not pending.provider_initiated_at and not pending.last_provider_observed_at
    assert not draft.picking_ids and not draft.account_move
    assert not pending.native_reconciled_at and not pending.historical_acknowledged_at
    for identity in (fixture["verified_source_id"], fixture["pending_source_id"]):
        row = next(item for item in fixture["records"]
                   if item["model"] == "pos.revolut.payment.operation" and item["values"]["id"] == identity)
        protected = set(row["values"]) - {"write_date", "write_uid"}
        assert stored(env["pos.revolut.payment.operation"].browse(identity), list(protected)) == {
            key: value for key, value in row["values"].items() if key in protected
        }
    provider.assert_not_called()
env.cr.commit()
print("EXTERNAL_NATIVE_UPGRADE_VERIFY_OK: exact financial history preserved; old acknowledgement unproven; one native completion; pending capacity protected; zero HTTP", flush=True)

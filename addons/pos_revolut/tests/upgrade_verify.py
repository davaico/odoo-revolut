"""Check real old-runtime history after upgrading in a new guarded process."""
import json
from copy import deepcopy
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.exceptions import UserError


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    return result


history = json.loads(env["ir.config_parameter"].get_param("pos_revolut.upgrade_fixture"))
assert len(history) == 6
assert env["ir.module.module"].search([("name", "=", "pos_revolut")]).installed_version == "19.0.1.10.1"
assert not env["pos.revolut.cart.authorization"].search_count([])
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
    for fixture in history:
        scenario = fixture["scenario"]
        order = env["pos.order"].browse(fixture["order_id"])
        method = env["pos.payment.method"].browse(fixture["method_id"])
        operation = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
        assert not order.revolut_authorization_id, scenario
        if operation:
            assert not operation.credential_id, scenario
            actual = operation.read(list(fixture["operation_values"]))[0]
            assert actual == fixture["operation_values"], (scenario, actual, fixture["operation_values"])
            assert not operation.authorization_id, scenario
            assert not operation.terminal_tip_evidence, scenario
            assert not operation.gross_amount_minor and not operation.terminal_tip_minor, scenario
            assert not operation.report_run_id and not operation.report_run_history, scenario
            recovered = method.revolut_find_payment(operation.order_uuid, operation.payment_line_uuid)
            assert recovered["operation_id"] == operation.id, recovered
            assert recovered["order_id"] == operation.revolut_order_id, recovered
            assert recovered["payment_intent_id"] == operation.revolut_payment_intent_id, recovered
            if scenario.endswith("verified"):
                polled = method.revolut_poll_payment(operation.id, operation.order_uuid, operation.payment_line_uuid)
                assert polled["state"] == "verified", polled
                document = env["pos.revolut.receipt"]._document("payment", operation.id)
                assert document["amount"] == "12.34", document
                assert document["base_amount"] is False and document["tip_amount"] is False, document
                assert not document["terminal_tip_evidence"], document
            if scenario != "safe_failed":
                try:
                    env["pos.order"].revolut_prepare_payment(order.id, order.uuid, 0, [])
                except UserError:
                    pass
                else:
                    raise AssertionError(f"Historical {scenario} gained new cart authority")
                try:
                    method.revolut_start_payment(order.session_id.id, order.uuid, str(uuid4()),
                                                12.34, order.currency_id.id, False,
                                                operation.financial_snapshot)
                except UserError:
                    pass
                else:
                    raise AssertionError(f"Historical {scenario} dispatched without authority")
        if scenario in {"unexposed", "safe_failed"}:
            payment = order.payment_ids
            prepared = env["pos.order"].revolut_prepare_payment(order.id, order.uuid, 0, [{
                "uuid": payment.uuid, "payment_method_id": method.id, "amount": 12.34,
            }])
            assert prepared["status"] == "prepared", (scenario, prepared)
            assert prepared["payable_minor"] == 1234, prepared
            env.cr.rollback()
            env.invalidate_all()
        provider.assert_not_called()

    # This old-runtime fixture has one independently reviewed Merchant account.
    # Authorization is explicit; the upgrade never infers it from old rows.
    original_method = env["pos.payment.method"].browse(history[0]["method_id"])
    env["pos.revolut.merchant.credential"].create({
        "company_id": original_method.company_id.id,
        "environment": original_method.revolut_environment,
        "secret_reference": original_method.revolut_secret_reference,
    })
    for fixture in history:
        if fixture["operation_id"]:
            env["pos.revolut.payment.operation"].browse(
                fixture["operation_id"]
            ).action_revolut_authorize_legacy_credential()
    # The payment entrypoint uses its own cursor, and later assertions roll
    # this one back. Persist the administrator's explicit migration action.
    env.cr.commit()
    env.invalidate_all()

    # A confirmed undispatched failure may retry against fresh canonical
    # authority while keeping its historical operation and references intact.
    fixture = next(item for item in history if item["scenario"] == "safe_failed")
    order = env["pos.order"].browse(fixture["order_id"])
    method = env["pos.payment.method"].browse(fixture["method_id"])
    previous = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
    authority = order.revolut_authorization_id
    provider_order, provider_intent = str(uuid4()), str(uuid4())
    provider.side_effect = [
        response({"terminals": [{"id": method.revolut_terminal_id, "online": True,
                                 "operation_mode": "pos", "location_id": method.revolut_location_id}]}),
        response({"id": provider_order}), response({"id": provider_intent, "state": "pending"}),
    ]
    retried = method.revolut_start_payment(
        order.session_id.id, order.uuid, previous.payment_line_uuid, 12.34, order.currency_id.id,
        previous.id, False, authority.id, authority.cart_version, authority.tender_revision,
    )
    assert retried["state"] == "pending" and retried["operation_id"] != previous.id, retried
    assert sum(call.args[0] == "POST" for call in provider.call_args_list) == 2
    env.cr.rollback()
    env.invalidate_all()
    current = env["pos.revolut.payment.operation"].browse(retried["operation_id"])
    assert current.previous_operation_id == previous and current.authorization_id == authority
    assert previous.read(list(fixture["operation_values"]))[0] == fixture["operation_values"]
    provider.reset_mock(side_effect=True)

    # Legacy completed payments retain the ordinary amount-based refund lane.
    fixture = next(item for item in history if item["scenario"] == "verified")
    order = env["pos.order"].browse(fixture["order_id"])
    method = env["pos.payment.method"].browse(fixture["method_id"])
    operation = env["pos.revolut.payment.operation"].browse(fixture["operation_id"])
    original = order.lines
    returned = deepcopy(fixture["payload"])
    returned.update(uuid=str(uuid4()), state="draft", amount_total=-12.34, amount_paid=0)
    returned.pop("id", None)
    returned["lines"] = [Command.create({
        "uuid": str(uuid4()), "product_id": original.product_id.id, "qty": -1,
        "price_unit": original.price_unit, "discount": original.discount,
        "tax_ids": [Command.set(original.tax_ids.ids)], "refunded_orderline_id": original.id,
        "price_subtotal": -12.34, "price_subtotal_incl": -12.34, "pack_lot_ids": [],
    })]
    return_line = str(uuid4())
    returned["payment_ids"] = [Command.create({
        "uuid": return_line, "payment_method_id": method.id, "amount": -12.34,
        "payment_status": "waiting", "transaction_id": False,
    })]
    sources = method.revolut_refund_sources(order.session_id.id, order.currency_id.id, returned)
    assert len(sources) == 1 and sources[0]["operation_id"] == operation.id, sources
    assert sources[0]["amount_minor"] == sources[0]["remaining_minor"] == 1234, sources
    assert not sources[0]["terminal_tip_evidence"], sources
    provider.assert_not_called()
    refund_id = str(uuid4())
    refund = {"id": refund_id, "related_order_id": operation.revolut_order_id,
              "type": "refund", "amount": 1234, "currency": order.currency_id.name}
    provider.side_effect = [
        response({"id": operation.revolut_order_id, "state": "completed", "amount": 1234,
                  "currency": order.currency_id.name, "refunded_amount": 0}),
        response(dict(refund, state="pending")), response(dict(refund, state="completed")),
    ]
    started = method.revolut_start_refund(order.session_id.id, returned["uuid"], return_line,
                                         -12.34, order.currency_id.id, returned, operation.id)
    observed = method.revolut_poll_refund(started["operation_id"], returned["uuid"], return_line)
    assert observed["state"] == "verified" and not observed["terminal_tip_evidence"], observed
    assert sum(call.args[0] == "POST" for call in provider.call_args_list) == 1
    assert all("report-runs" not in call.args[1] for call in provider.call_args_list)
    # Public refund mutations commit in owned cursors. Start the next native
    # checkout transaction before inspecting or linking their evidence.
    env.cr.rollback()
    env.invalidate_all()
    returned.update(state="paid", amount_paid=-12.34)
    returned["payment_ids"][0][2].update(payment_status="done", transaction_id=refund_id)
    env["pos.order"].sync_from_ui([returned])
    document = env["pos.revolut.receipt"]._document("refund", observed["operation_id"])
    assert document["amount"] == "12.34" and not document["terminal_tip_evidence"], document

env.cr.commit()
print("UPGRADE_VERIFY_OK: preserved six historical states, no invented authority/tip proof; legacy refund verified", flush=True)

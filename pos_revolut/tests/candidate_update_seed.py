"""Commit representative Revolut configuration and financial records before updating this candidate.

This is initial Odoo 18 candidate-update evidence, not imported payment history.
Only synthetic references are stored; Merchant HTTP is mocked at its external boundary.
"""
import json
import os
from datetime import timedelta
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

import requests

from odoo import Command, fields
from odoo.addons.pos_revolut.tests.test_revolut_terminal_tip import TerminalTipFixtures


assert env["ir.module.module"].search([("name", "=", "pos_revolut")]).state == "installed"
native_snapshot = json.loads(env["ir.config_parameter"].sudo().get_param(
    "pos_revolut_test.native_install",
))
company_ids = next(entry["ids"] for entry in native_snapshot if entry["model"] == "res.company")
manager_ids = next(entry["ids"] for entry in native_snapshot if entry["model"] == "res.users")
company = env["res.company"].browse(company_ids)
configured = env(context={**env.context, "allowed_company_ids": company.ids})
cashier = configured["res.users"].create({
    "name": "Candidate update cashier", "login": "candidate-update-cashier",
    "company_id": company.id, "company_ids": [Command.set(company.ids)],
    "groups_id": [Command.set([
        env.ref("base.group_user").id, env.ref("point_of_sale.group_pos_user").id,
    ])],
})
credential = configured["pos.revolut.merchant.credential"].create({
    "company_id": company.id, "environment": "sandbox",
    "secret_reference": "ODOO_REVOLUT_SECRET_UPDATE_FIXTURE",
})
bank_journal = configured["account.journal"].search([("type", "=", "bank")], limit=1)
assert bank_journal, "The populated native company must have a bank journal"
method = configured["pos.payment.method"].create({
    "name": "Candidate update Revolut terminal", "company_id": company.id,
    "journal_id": bank_journal.id, "payment_method_type": "terminal",
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": "18000000-0000-4000-8000-000000000001",
    "revolut_terminal_id": "18000000-0000-4000-8000-000000000002",
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": credential.secret_reference,
})
config = configured["pos.config"].create({
    "name": "Candidate update Revolut register", "company_id": company.id,
    "payment_method_ids": [Command.set(method.ids)],
    "auto_validate_terminal_payment": True,
    "revolut_user_ids": [Command.set(manager_ids + cashier.ids)],
})
assert method._revolut_configuration_credential() == credential
config.with_user(cashier)._check_revolut_register_access()
history = [
    (credential, ["company_id", "environment", "secret_reference"]),
    (method, ["name", "company_id", "journal_id", "payment_method_type",
              "use_payment_terminal", "revolut_environment", "revolut_location_id",
              "revolut_terminal_id", "revolut_fulfilment_type", "revolut_secret_reference"]),
    (config, ["name", "company_id", "payment_method_ids", "revolut_user_ids",
              "auto_validate_terminal_payment", "journal_id", "invoice_journal_id", "tip_product_id"]),
    (cashier, ["login", "company_id", "company_ids", "groups_id"]),
]
# Create current authorized carts through the same public preparation, dispatch
# and finality paths as POS. Only Merchant HTTP is mocked.
manager = configured["res.users"].browse(manager_ids)
tip_product = configured["product.product"].create({
    "name": "Candidate update configured tip", "type": "service", "list_price": 0,
    "taxes_id": [Command.clear()],
})
config.write({"tip_product_id": tip_product.id})
config.with_user(manager).open_ui()
session = config.current_session_id
session.set_opening_control(0, "Candidate update preservation")
product_ids = next(entry["ids"] for entry in native_snapshot if entry["model"] == "product.product")
product = configured["product.product"].browse(product_ids)
partner_ids = next(entry["ids"] for entry in native_snapshot if entry["model"] == "res.partner")
partner = configured["res.partner"].browse(partner_ids)
operations = configured["pos.revolut.payment.operation"]
refunds = configured["pos.revolut.refund.operation"]
orders = configured["pos.order"]
public_method = method.with_user(manager)


def current_sale(label, finish):
    payload = {
        "uuid": str(uuid4()), "name": label, "session_id": session.id,
        "user_id": manager.id, "partner_id": partner.id, "state": "draft", "sequence_number": 1,
        "pricelist_id": config.pricelist_id.id, "fiscal_position_id": False,
        "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
        "date_order": fields.Datetime.to_string(fields.Datetime.now()), "to_invoice": False,
        "lines": [Command.create({
            "uuid": str(uuid4()), "product_id": product.id, "qty": 1, "price_unit": 12.34,
            "discount": 0, "tax_ids": [Command.set([])], "price_subtotal": 12.34,
            "price_subtotal_incl": 12.34, "pack_lot_ids": [],
        })],
        "payment_ids": [Command.create({
            "uuid": str(uuid4()), "payment_method_id": method.id, "amount": 12.34,
            "payment_status": "waiting", "transaction_id": False,
        })],
    }
    configured["pos.order"].sync_from_ui([payload])
    order = configured["pos.order"].search([("uuid", "=", payload["uuid"])])
    fixture = TerminalTipFixtures()
    fixture.method, fixture.order = method, order
    fixture.provider_order_id, fixture.provider_intent_id, fixture.provider_payment_id = [str(uuid4()) for _ in range(3)]
    fixture.base_minor, fixture.gross_minor, fixture.tip_minor = 1234, 1234, 0
    fixture.report_status, fixture.active_run_id = "completed", ""
    fixture.report_post_count, fixture.csv_content, fixture.order_payments = 0, None, None
    payment_uuid = payload["payment_ids"][0][2]["uuid"]
    env.cr.commit()
    prepared = configured["pos.order"].with_user(manager).revolut_prepare_payment(order.id, order.uuid, 0, [{
        "uuid": payment_uuid, "payment_method_id": method.id, "amount": 12.34,
    }])
    assert prepared["status"] == "prepared", prepared
    env.cr.commit()
    configured.invalidate_all()
    with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
               side_effect=fixture.provider_response) as provider:
        started = public_method.revolut_start_payment(session.id, order.uuid, payment_uuid,
            12.34, company.currency_id.id, False, False, prepared["authorization_id"],
            prepared["cart_version"], prepared["tender_revision"])
        assert started["state"] == "pending", started
        env.cr.commit()
        configured.invalidate_all()
        with patch("odoo.addons.pos_revolut.models.payment_observation.observation_now",
                   return_value=fields.Datetime.now() + timedelta(seconds=2)):
            if finish:
                outcome = public_method.revolut_poll_payment(started["operation_id"], order.uuid, payment_uuid)
            else:
                with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                           side_effect=requests.Timeout("Synthetic interrupted status response")):
                    outcome = public_method.revolut_poll_payment(started["operation_id"], order.uuid, payment_uuid)
        assert outcome["state"] == ("verified" if finish else "unresolved"), outcome
        assert sum(call.args[0] == "POST" and not call.args[1].endswith("/report-runs")
                   for call in provider.call_args_list) == 2
    env.cr.commit()
    configured.invalidate_all()
    operation = configured["pos.revolut.payment.operation"].browse(started["operation_id"])
    assert operation.authorization_id == order.revolut_authorization_id
    assert operation.cart_version == operation.authorization_id.cart_version
    assert operation.tender_revision == operation.authorization_id.tender_revision
    if finish:
        configured["pos.order"].sync_from_ui([dict(payload, state="paid", amount_paid=12.34,
                                                  lines=[], payment_ids=[])])
        assert order.state == "paid" and order.amount_total == 12.34
    else:
        assert order.state == "draft" and operation.deployment_blocking and not operation.retry_safe
    return operation, payload


with patch.dict(os.environ, {method.revolut_secret_reference: "synthetic-update-secret"}), patch(
        "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
        side_effect=AssertionError("Unexpected provider request outside mocked candidate flow")) as provider:
    completed, sale = current_sale("Candidate completed authorized sale", True)
    original = completed.pos_order_id
    operations |= completed
    orders |= original
    for state in ("verified", "unresolved"):
        # The second quarter receives 3.08 from the remaining 9.25 / 0.75,
        # preserving the original 12.34 rather than rounding both to 3.09.
        refund_minor = 309 if state == "verified" else 308
        returned = deepcopy(sale)
        returned.update(uuid=str(uuid4()), name=f"Candidate {state} partial return", state="draft",
                        amount_total=-refund_minor / 100, amount_paid=0)
        returned["lines"][0][2].update(uuid=str(uuid4()), qty=-0.25, price_subtotal=-3.085,
            price_subtotal_incl=-3.085, refunded_orderline_id=original.lines.id)
        returned["payment_ids"][0][2].update(uuid=str(uuid4()), amount=-refund_minor / 100,
            payment_status="waiting", transaction_id=False)
        configured["pos.order"].sync_from_ui([returned])
        native_return = configured["pos.order"].search([("uuid", "=", returned["uuid"])])
        reference = str(uuid4())
        response = {
            "id": reference, "type": "refund", "related_order_id": completed.revolut_order_id,
            "amount": refund_minor, "currency": company.currency_id.name, "state": "pending",
        }
        env.cr.commit()
        configured.invalidate_all()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=[
            TerminalTipFixtures().response({"id": completed.revolut_order_id, "state": "completed",
                "amount": 1234, "currency": company.currency_id.name,
                "refunded_amount": 0 if state == "verified" else 309}),
            TerminalTipFixtures().response(response),
        ]) as refund_provider:
            started = public_method.revolut_start_refund(session.id, native_return.uuid,
                native_return.payment_ids.uuid, -refund_minor / 100, company.currency_id.id, returned,
                completed.id, refund_minor, 0)
            assert started["state"] == "pending", started
            assert [call.args[0] for call in refund_provider.call_args_list] == ["GET", "POST"]
        env.cr.commit()
        configured.invalidate_all()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=([TerminalTipFixtures().response(dict(response, state="completed"))]
                                if state == "verified" else requests.Timeout("Synthetic refund status response loss"))):
            observed = public_method.revolut_poll_refund(started["operation_id"], native_return.uuid,
                                                       native_return.payment_ids.uuid)
        assert observed["state"] == state, observed
        env.cr.commit()
        configured.invalidate_all()
        refund = configured["pos.revolut.refund.operation"].browse(started["operation_id"])
        assert refund.return_allocation, "Current refund must retain its frozen native return allocation"
        if state == "verified":
            returned["payment_ids"][0][2].update(payment_status="done", transaction_id=reference)
            configured["pos.order"].sync_from_ui([dict(returned, state="paid", amount_paid=-3.09,
                lines=[], payment_ids=[Command.update(native_return.payment_ids.id,
                    returned["payment_ids"][0][2])])])
            assert refund.pos_order_id == native_return
        assert native_return.state == ("paid" if state == "verified" else "draft")
        assert refund.deployment_blocking == (state == "unresolved")
        refunds |= refund
        orders |= native_return
    unresolved, pending = current_sale("Candidate unresolved authorized sale", False)
    operations |= unresolved
    orders |= unresolved.pos_order_id
    dispatches = configured["pos.revolut.payment.dispatch"].search([("operation_id", "in", operations.ids)])
    assert len(dispatches) == 4 and set(dispatches.mapped("outcome")) == {"succeeded"}
    external = configured["pos.revolut.refund.operation"].create({
        "origin": "external", "original_operation_id": completed.id, "pos_session_id": session.id,
        "amount": 0.01, "amount_minor": 1, "currency_id": company.currency_id.id,
        "revolut_order_id": str(uuid4()), "state": "pending", "provider_state": "pending",
    })
    refunds |= external
    evidence = configured["pos.revolut.external.refund.evidence"].sudo().create({
        "credential_id": credential.id, "original_operation_id": completed.id,
        "provider_order_id": str(uuid4()), "related_order_id": completed.revolut_order_id,
        "amount_minor": 1, "currency_code": company.currency_id.name, "reason": "interrupted",
    })
    assert evidence.deployment_blocking and external.deployment_blocking
    provider.assert_not_called()

# Preserve canonical/projected cart snapshots, tender allocations/revisions and
# their linked native/financial identities across the real module update.
for records in (session, operations.authorization_id, operations, dispatches, refunds, evidence,
                orders, orders.lines, orders.payment_ids):
    names = sorted(name for name, field in records._fields.items()
                   if field.store and field.type not in {"one2many", "many2many", "binary"})
    history.append((records, names))

snapshot = [{"model": records._name, "ids": records.ids, "fields": names,
             "values": records.read(names, load=False)} for records, names in history]
env["ir.config_parameter"].sudo().set_param(
    "pos_revolut_test.candidate_update", json.dumps(snapshot, default=str, sort_keys=True),
)
env.cr.commit()
print("CANDIDATE_UPDATE_SEED_OK: configuration, grants, completed/unresolved native payments/refunds, dispatch and external evidence")

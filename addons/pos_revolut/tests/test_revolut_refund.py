import os
from copy import deepcopy
from unittest.mock import Mock, patch
from unittest import TestCase
from uuid import uuid4

import requests

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests.common import tagged, new_test_user
from odoo.service.model import call_kw
from odoo.exceptions import AccessError, UserError, ValidationError

from .test_revolut_payment import TestRevolutOrderSettlement


@tagged("post_install", "-at_install")
class TestRevolutRefund(CommonPosTest):
    LOCATION_ID = TestRevolutOrderSettlement.LOCATION_ID
    TERMINAL_ID = TestRevolutOrderSettlement.TERMINAL_ID
    PAYMENT_ID = TestRevolutOrderSettlement.PAYMENT_ID
    _operation = TestRevolutOrderSettlement._operation
    _order_payload = TestRevolutOrderSettlement._order_payload

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Revolut refund test", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({"payment_method_ids": [Command.link(cls.revolut_method.id)],
                                 "auto_validate_terminal_payment": True})
        cls.product = cls.env["product.product"].create({
            "name": "Refund product", "available_in_pos": True, "list_price": 12.34,
            "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.enterContext(patch.dict(os.environ, {
            "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST": "test-only",
        }))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        original = self._order_payload(str(uuid4()), str(uuid4()))
        self.source = self._operation(
            original["uuid"], original["payment_ids"][0][2]["uuid"],
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(original),
        )
        original["payment_ids"][0][2]["transaction_id"] = self.source.revolut_payment_id
        self.env["pos.order"].sync_from_ui([original])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        for name in ("amount_paid", "amount_total"):
            self.payload[name] = -12.34
        line = self.payload["lines"][0][2]
        line.update(qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
                    refunded_orderline_id=self.original.lines.id)
        self.payload["payment_ids"][0][2].update(amount=-12.34, transaction_id=False, payment_status="waiting")
        self.refund_id = str(uuid4())
        self.env.flush_all()

    def _start(self):
        return self.revolut_method.revolut_start_refund(
            self.session.id, self.payload["uuid"],
            self.payload["payment_ids"][0][2]["uuid"], self.payload["payment_ids"][0][2]["amount"],
            self.session.currency_id.id, self.payload,
        )

    def _mutation_actor(self, manager=True):
        return new_test_user(
            self.env, login=f"refund_mutation_{uuid4()}",
            groups="base.group_user,point_of_sale.group_pos_manager" if manager else "base.group_user,point_of_sale.group_pos_user",
            company_id=self.company.id, company_ids=[Command.set([self.company.id])],
        )

    def _rpc_refund(self, user, model, method, args):
        return call_kw(self.env[model].with_user(user), method, args, {
            "context": {"allowed_company_ids": [self.company.id]},
        })

    def _rpc_start_refund(self, manager, payload=None):
        payload = payload or self.payload
        payment = payload["payment_ids"][0][2]
        return self._rpc_refund(manager, "pos.payment.method", "revolut_start_refund", [
            [self.revolut_method.id], self.session.id, payload["uuid"],
            payment["uuid"], payment["amount"], self.session.currency_id.id, payload,
        ])

    def _rpc_refund_sources(self, manager, payload=None):
        return self._rpc_refund(manager, "pos.payment.method", "revolut_refund_sources", [
            [self.revolut_method.id], self.session.id, self.session.currency_id.id,
            payload or self.payload,
        ])

    def test_oversized_cash_return_discovers_originals_in_bounded_batches(self):
        class NoWholeTraversal(list):
            def __iter__(self):
                raise AssertionError("Unbounded return relationship traversal")

            def __getitem__(self, key):
                if isinstance(key, slice):
                    assert key.stop - key.start <= 1000, "Unbounded discovery batch"
                return super().__getitem__(key)

        cash_sale = self._order_payload(str(uuid4()), str(uuid4()), payment_method=self.cash_payment_method)
        saved = self.env["pos.order"].sync_from_ui([cash_sale])
        cash_original = self.env["pos.order"].browse(saved["pos.order"][0]["id"])
        for financial_first in (True, False):
            with self.subTest(financial_first=financial_first):
                payload = deepcopy(self.payload)
                payload["uuid"] = str(uuid4())
                payload["payment_ids"][0][2].update(
                    payment_method_id=self.cash_payment_method.id, payment_status="done", transaction_id=False,
                )
                financial = payload["lines"][0]
                cash = deepcopy(financial)
                cash[2]["refunded_orderline_id"] = cash_original.lines.id
                contents = [financial] + [cash] * 1000 if financial_first else [cash] * 1000 + [financial]
                payload["lines"] = NoWholeTraversal(contents)
                with TestCase.assertRaisesRegex(self, UserError, "at most 1,000 lines"):
                    self._rpc_refund(self._mutation_actor(), "pos.order", "sync_from_ui", [[payload]])
                self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", payload["uuid"])]))
                self.assertFalse(self.env["pos.revolut.refund.operation"].sudo().search_count([
                    ("order_uuid", "=", payload["uuid"]),
                ]))
                self.request.assert_not_called()

    def test_public_invalid_refund_snapshot_leaves_no_reservation(self):
        manager = self._mutation_actor()
        valid = deepcopy(self.payload)
        cases = (
            ("qty", "-1e1000"), ("qty", "-1e-1000"),
            ("price_unit", "9" * 65),
            ("price_unit", "0.12345678901234567890123456789"),
            ("discount", "NaN"), ("discount", "12x"),
            ("amount_total", "-1e1000"), ("lines", None),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                payload = deepcopy(valid)
                if field == "lines":
                    # A capped list proves the public routes apply the same
                    # cheap count check before return/source traversal.
                    payload["lines"] = payload["lines"] * 1001
                elif field == "amount_total":
                    payload[field] = value
                else:
                    payload["lines"][0][2][field] = value
                with TestCase.assertRaisesRegex(self, UserError, "Revolut cart"):
                    self._rpc_refund_sources(manager, payload)
                rejected = self._rpc_start_refund(manager, payload)
                self.assertEqual(rejected["start_rejected"], "snapshot_invalid")
                self.assertIs(rejected["dispatched"], False)
                self.assertEqual(rejected["order_uuid"], payload["uuid"])
                self.assertEqual(rejected["payment_line_uuid"], payload["payment_ids"][0][2]["uuid"])
                self.assertFalse(rejected["previous_operation_id"])
                self.assertNotIn("operation_id", rejected)
                self.assertIn("Correct the cart", rejected["message"])
                for model in ("pos.revolut.payment.operation", "pos.revolut.refund.operation",
                              "pos.revolut.order.lock"):
                    self.assertFalse(self.env[model].sudo().search_count([
                        ("company_id", "=", self.company.id), ("order_uuid", "=", payload["uuid"]),
                    ]))
                self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", payload["uuid"])]))
                found = self._rpc_refund(manager, "pos.payment.method", "revolut_find_refund", [
                    [self.revolut_method.id], payload["uuid"], payload["payment_ids"][0][2]["uuid"],
                ])
                self.assertFalse(found)
                self.request.assert_not_called()
        self.assertEqual(self._rpc_refund_sources(manager, valid)[0]["remaining_minor"], 1234)
        self.request.assert_not_called()

    def test_public_refund_snapshot_correction_completes_same_line(self):
        manager = self._mutation_actor()
        self.payload.update(amount_total=-6.17, amount_paid=-6.17)
        line = self.payload["lines"][0][2]
        line.update(qty=-0.5, price_subtotal=-6.17, price_subtotal_incl=-6.17)
        self.payload["payment_ids"][0][2]["amount"] = -6.17
        corrected = deepcopy(self.payload)
        line["qty"] = "-1e1000"
        rejected = self._rpc_start_refund(manager)
        self.assertEqual(rejected["start_rejected"], "snapshot_invalid")
        self.request.assert_not_called()

        self.payload = corrected
        self.assertEqual(self._rpc_refund_sources(manager)[0]["remaining_minor"], 1234)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=617), self._refund_response("completed", amount=617),
        ]
        started = self._rpc_start_refund(manager)
        self.assertEqual(started["state"], "pending")
        verified = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], self.payload["uuid"],
            self.payload["payment_ids"][0][2]["uuid"],
        ])
        self.assertEqual(verified["state"], "verified")
        self.payload.update(user_id=manager.id)
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        saved = self._rpc_refund(manager, "pos.order", "sync_from_ui", [[self.payload]])
        order = self.env["pos.order"].browse(next(
            item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]
        ))
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.lines.qty, -0.5)
        self.assertEqual(refund.pos_order_id, order)
        self.assertEqual(refund.pos_payment_id.revolut_refund_operation_id, refund)
        self.assertEqual(self._rpc_refund_sources(manager)[0]["remaining_minor"], 617)
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET", "POST", "GET"])

    def test_public_invalid_snapshot_preserves_uncertain_refund(self):
        manager = self._mutation_actor()
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            requests.Timeout(),
        ]
        started = self._rpc_start_refund(manager)
        self.assertEqual(started["state"], "unresolved")
        self.assertFalse(started["order_id"])
        refund = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        evidence_fields = ["state", "original_operation_id", "order_uuid", "payment_line_uuid",
                           "financial_snapshot", "idempotency_key", "amount_minor", "return_total_minor",
                           "revolut_order_id", "dispatched_at", "local_outcome"]
        evidence = deepcopy(refund.read(evidence_fields)[0])
        valid = deepcopy(self.payload)
        self.payload["lines"][0][2]["qty"] = "-1e1000"
        self.request.reset_mock()
        with TestCase.assertRaisesRegex(self, UserError, "Revolut cart"):
            self._rpc_start_refund(manager)
        with TestCase.assertRaisesRegex(self, UserError, "Revolut cart"):
            self._rpc_refund_sources(manager)
        refund.invalidate_recordset()
        self.assertEqual(refund.read(evidence_fields)[0], evidence)
        self.assertTrue(refund.deployment_blocking)
        found = self._rpc_refund(manager, "pos.payment.method", "revolut_find_refund", [
            [self.revolut_method.id], valid["uuid"], valid["payment_ids"][0][2]["uuid"],
        ])
        self.assertEqual(found, started)
        self.assertFalse(found["retry_safe"])
        self.assertEqual(self._rpc_start_refund(manager, valid), started)
        self.assertEqual(self._rpc_refund_sources(manager, valid)[0]["remaining_minor"], 0)
        replacement = deepcopy(valid)
        replacement["uuid"] = str(uuid4())
        replacement["payment_ids"][0][2]["uuid"] = str(uuid4())
        with TestCase.assertRaises(self, UserError):
            self._rpc_start_refund(manager, replacement)
        self.assertEqual(self.env["pos.revolut.refund.operation"].search_count([
            ("original_operation_id", "=", self.source.id),
        ]), 1)
        self.request.assert_not_called()

        candidate = self._refund_response("completed").json()
        candidate["merchant_order_data"] = {"reference": evidence["idempotency_key"]}
        self.request.side_effect = [self._response(orders=[candidate]), self._refund_response("completed")]
        verified = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], valid["uuid"],
            valid["payment_ids"][0][2]["uuid"],
        ])
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(verified["order_id"], self.refund_id)
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET", "GET"])
        refund.invalidate_recordset()
        self.assertEqual(refund.financial_snapshot, evidence["financial_snapshot"])
        self.assertEqual(refund.idempotency_key, evidence["idempotency_key"])

    def test_public_invalid_snapshot_cannot_settle_verified_refund(self):
        manager = self._mutation_actor()
        started = self._pending()
        self.request.side_effect = [self._refund_response("completed")]
        self.assertEqual(self._poll(started)["state"], "verified")
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        refund.invalidate_recordset()
        snapshot = deepcopy(refund.financial_snapshot)
        key = refund.idempotency_key
        self.payload.update(user_id=manager.id)
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        self.payload["lines"][0][2]["price_unit"] = "1e-1000"
        self.request.reset_mock()

        with TestCase.assertRaisesRegex(self, UserError, "Revolut cart"):
            self._rpc_refund(manager, "pos.order", "sync_from_ui", [[self.payload]])
        self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", self.payload["uuid"])]))
        refund.invalidate_recordset()
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.revolut_order_id, self.refund_id)
        self.assertEqual(refund.financial_snapshot, snapshot)
        self.assertEqual(refund.idempotency_key, key)
        self.assertFalse(refund.pos_order_id)
        self.assertFalse(refund.pos_payment_id)
        self.request.assert_not_called()

    def test_native_zero_discount_settles_verified_refund(self):
        manager = self._mutation_actor()
        started = self._pending()
        self.request.side_effect = [self._refund_response("completed")]
        self.assertEqual(self._poll(started)["state"], "verified")
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        snapshot = deepcopy(refund.financial_snapshot)
        self.payload.update(user_id=manager.id)
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        self.payload["lines"][0][2]["discount"] = False
        self.request.reset_mock()

        saved = self._rpc_refund(manager, "pos.order", "sync_from_ui", [[self.payload]])
        order = self.env["pos.order"].browse(next(
            item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]
        ))
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.lines.discount, 0)
        self.assertEqual(refund.pos_order_id, order)
        self.assertEqual(order.payment_ids.revolut_refund_operation_id, refund)
        self.assertEqual(refund.financial_snapshot, snapshot)
        self.request.assert_not_called()

    def test_persisted_refund_snapshot_remains_settleable(self):
        manager = self._mutation_actor()
        self.payload.update(amount_total=-6.17, amount_paid=-6.17, user_id=manager.id)
        line = self.payload["lines"][0][2]
        line.update(qty="-5e-1", price_unit="1.234e1", discount="0e1",
                    price_subtotal=-6.17, price_subtotal_incl=-6.17)
        self.payload["payment_ids"][0][2].update(
            amount=-6.17, payment_status="done", transaction_id=self.refund_id,
        )
        # Literal output of the pre-upgrade return normalizer: the assertion
        # must not regenerate its expected evidence with the new helper.
        persisted = {
            "pricelist_id": self.payload["pricelist_id"], "fiscal_position_id": 0,
            "lines": [{
                "uuid": line["uuid"], "product_id": self.product.id,
                "qty": "-0.5", "price_unit": "12.34", "discount": "0", "tax_ids": [],
                "refunded_orderline_id": self.original.lines.id,
            }],
        }
        refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": self.source.id, "pos_session_id": self.session.id,
            "order_uuid": self.payload["uuid"],
            "payment_line_uuid": self.payload["payment_ids"][0][2]["uuid"],
            "amount": 6.17, "amount_minor": 617, "return_total_minor": 617,
            "currency_id": self.session.currency_id.id, "financial_snapshot": persisted,
            "state": "verified", "revolut_order_id": self.refund_id, "provider_state": "completed",
        })
        saved = self._rpc_refund(manager, "pos.order", "sync_from_ui", [[self.payload]])
        order = self.env["pos.order"].browse(next(
            item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]
        ))
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.lines.qty, -0.5)
        self.assertEqual(refund.pos_order_id, order)
        self.assertEqual(order.payment_ids.revolut_refund_operation_id, refund)
        self.assertEqual(refund.financial_snapshot, persisted)
        self.request.assert_not_called()

    def test_public_refund_draft_preparation_remains_allowed(self):
        manager = self._mutation_actor()
        result = self._rpc_refund(manager, "pos.order", "refund", [[self.original.id]])
        order = self.env["pos.order"].browse(result["res_id"])
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.lines.refunded_orderline_id, self.original.lines)
        self.assertEqual(order.amount_total, -12.34)
        self.request.assert_not_called()

    def test_public_unclaimed_return_cancellation_remains_allowed(self):
        manager = self._mutation_actor()
        result = self._rpc_refund(manager, "pos.order", "refund", [[self.original.id]])
        order_id = result["res_id"]
        self._rpc_refund(manager, "pos.order", "remove_from_ui", [[order_id]])
        self.assertFalse(self.env["pos.order"].browse(order_id).exists())
        self.request.assert_not_called()

    def test_public_pending_and_failed_refunds_cannot_be_fabricated_as_done(self):
        manager = self._mutation_actor()
        started = self._pending()
        payload = dict(self.payload, state="draft", user_id=manager.id)
        order_id = self._rpc_refund(manager, "pos.order", "create", [payload])
        order = self.env["pos.order"].browse(order_id)
        for state in ("pending", "failed"):
            with self.subTest(state=state):
                if state == "failed":
                    self.request.side_effect = [self._refund_response("failed")]
                    self.assertEqual(self._poll(started)["state"], "failed")
                for model, method, args in (
                    ("pos.payment", "write", [[order.payment_ids.id], {"payment_status": "done"}]),
                    ("pos.order", "action_pos_order_paid", [[order.id]]),
                ):
                    with TestCase.assertRaises(self, UserError):
                        self._rpc_refund(manager, model, method, args)
                    self.assertEqual(order.state, "draft")
                    self.assertEqual(order.payment_ids.payment_status, "waiting")
        self.assertEqual(self.request.call_count, 3)

    def test_public_verified_refund_rejects_mismatch_and_reuse_atomically(self):
        manager = self._mutation_actor()
        started = self._pending()
        self.request.side_effect = [self._refund_response("completed")]
        self._poll(started)
        self.payload.update(state="draft", user_id=manager.id)
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        for changed in ({"amount": -6.17}, {"transaction_id": str(uuid4())},
                        {"revolut_operation_id": self.source.id}):
            payload = deepcopy(self.payload)
            payload["payment_ids"][0][2].update(changed)
            with TestCase.assertRaises(self, UserError):
                self._rpc_refund(manager, "pos.order", "create", [payload])
            self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
        order_id = self._rpc_refund(manager, "pos.order", "create", [self.payload])
        payload = deepcopy(self.payload)
        payload["uuid"] = str(uuid4())
        payload["lines"][0][2]["uuid"] = str(uuid4())
        payload["payment_ids"][0][2].update(uuid=str(uuid4()), payment_method_id=self.cash_payment_method.id)
        with TestCase.assertRaises(self, UserError):
            self._rpc_refund(manager, "pos.order", "create", [payload])
        self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        self.assertEqual(refund.pos_order_id.id, order_id)
        self.assertEqual(self.request.call_count, 3)

    def test_direct_refund_done_and_cash_substitution_without_evidence_are_rejected(self):
        for manager in (False, True):
            actor = self._mutation_actor(manager)
            payload = dict(self.payload, state="draft", user_id=actor.id)
            payload["payment_ids"][0][2]["payment_status"] = "done"
            with TestCase.assertRaises(self, UserError):
                self._rpc_refund(actor, "pos.order", "create", [payload])
            self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
        self.request.assert_not_called()

    def test_reconfigured_method_cannot_turn_original_revolut_into_manual_refund(self):
        manager = self._mutation_actor()
        # Reconfiguration is permitted once the original session is closed.
        self.session.write({"state": "closed"})
        self._rpc_refund(manager, "pos.payment.method", "write", [
            [self.revolut_method.id], {"payment_method_type": "none"},
        ])
        self.assertFalse(self.revolut_method.use_payment_terminal)
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        payload = deepcopy(self.payload)
        payload.update(state="paid", session_id=self.session.id, user_id=manager.id)
        payload["payment_ids"][0][2]["payment_status"] = "done"
        with TestCase.assertRaisesRegex(self, UserError, "non-Revolut refund exceeds"):
            self._rpc_refund(manager, "pos.order", "create", [payload])
        self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
        self.assertEqual(self.original.payment_ids.revolut_operation_id, self.source)
        self.assertFalse(self.env["pos.revolut.refund.operation"].search([
            ("order_uuid", "=", payload["uuid"]),
        ]))
        self.request.assert_not_called()

    def test_waiting_return_cannot_detach_original_or_settle_as_cash(self):
        cashier = self._mutation_actor(False)
        payload = dict(self.payload, state="draft", amount_paid=0, payment_ids=[], user_id=cashier.id)
        order_id = self._rpc_refund(cashier, "pos.order", "create", [payload])
        order = self.env["pos.order"].browse(order_id)
        with TestCase.assertRaises(self, UserError):
            self._rpc_refund(cashier, "pos.order.line", "write", [[order.lines.id], {"refunded_orderline_id": False}])
        payment = dict(self.payload["payment_ids"][0][2], payment_method_id=self.cash_payment_method.id,
                       payment_status="done", pos_order_id=order.id, transaction_id=False)
        with TestCase.assertRaises(self, UserError):
            self._rpc_refund(cashier, "pos.order", "write", [[order.id], {
                "payment_ids": [Command.create(payment)], "amount_paid": -12.34, "state": "paid",
            }])
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.lines.refunded_orderline_id, self.original.lines)
        self.assertFalse(order.payment_ids)
        self.request.assert_not_called()

    def test_public_manager_verified_partial_refund_is_linked_and_immutable(self):
        manager = self._mutation_actor()
        self.payload.update(amount_total=-6.17, amount_paid=-6.17)
        self.payload["lines"][0][2].update(qty=-0.5, price_subtotal=-6.17, price_subtotal_incl=-6.17)
        self.payload["payment_ids"][0][2]["amount"] = -6.17
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=617), self._refund_response("completed", amount=617),
        ]
        started = self._rpc_refund(manager, "pos.payment.method", "revolut_start_refund", [
            [self.revolut_method.id], self.session.id, self.payload["uuid"],
            self.payload["payment_ids"][0][2]["uuid"], -6.17, self.session.currency_id.id, self.payload,
        ])
        self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], self.payload["uuid"],
            self.payload["payment_ids"][0][2]["uuid"],
        ])
        self.payload.update(state="draft", user_id=manager.id)
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        order_id = self._rpc_refund(manager, "pos.order", "create", [self.payload])
        order = self.env["pos.order"].browse(order_id)
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        self._rpc_refund(manager, "pos.order", "action_pos_order_paid", [[order.id]])
        self.assertEqual(order.state, "paid")
        self.assertEqual(refund.pos_order_id, order)
        self.assertEqual(refund.pos_payment_id.revolut_refund_operation_id, refund)
        for values in ({"revolut_refund_operation_id": False}, {"amount": -12.34},
                       {"payment_method_id": self.cash_payment_method.id}, {"transaction_id": str(uuid4())}):
            with TestCase.assertRaises(self, UserError):
                self._rpc_refund(manager, "pos.payment", "write", [[order.payment_ids.id], values])
            self.assertEqual(order.payment_ids.amount, -6.17)
            self.assertEqual(order.payment_ids.revolut_refund_operation_id, refund)
        self.assertEqual(self.request.call_count, 3)

    def _response(self, **payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _refund_response(self, state="pending", amount=1234, source=None):
        return self._response(id=self.refund_id, type="refund", state=state,
                              related_order_id=(source or self.source).revolut_order_id,
                              amount=amount, currency=self.session.currency_id.name)

    def _split_original(self, second_revolut=False):
        original = self._order_payload(str(uuid4()), str(uuid4()))
        first_payment = original["payment_ids"][0][2]
        first_payment["amount"] = 6.17
        second_payment = dict(first_payment, uuid=str(uuid4()), amount=6.17,
                              payment_method_id=self.revolut_method.id if second_revolut else self.cash_payment_method.id)
        original["payment_ids"].append(Command.create(second_payment))
        financial = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(original)
        first = self._operation(original["uuid"], first_payment["uuid"], amount=6.17,
                                amount_minor=617, financial_snapshot=financial)
        first_payment["transaction_id"] = first.revolut_payment_id
        second = False
        if second_revolut:
            second = self._operation(original["uuid"], second_payment["uuid"], amount=6.17,
                                     amount_minor=617, financial_snapshot=financial,
                                     blocking_order_key=False)
            second_payment["transaction_id"] = second.revolut_payment_id
        else:
            second_payment["transaction_id"] = False
        self.env["pos.order"].sync_from_ui([original])
        self.env.flush_all()
        first.invalidate_recordset()
        if second:
            second.invalidate_recordset()
        self.source = first
        self.original = first.pos_order_id
        self.assertTrue(self.original)
        self.assertEqual(first.pos_payment_id.revolut_operation_id, first)
        self.assertEqual(first.pos_payment_id.transaction_id, first.revolut_payment_id)
        self.payload["lines"][0][2]["refunded_orderline_id"] = self.original.lines.id
        return first, second

    def test_repeated_partial_refunds_can_use_full_remaining_balance(self):
        self.payload["amount_total"] = self.payload["amount_paid"] = -6.17
        self.payload["lines"][0][2].update(qty=-0.5, price_subtotal=-6.17, price_subtotal_incl=-6.17)
        self.payload["payment_ids"][0][2]["amount"] = -6.17
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed",
                           amount=1234, currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=617),
        ]
        first = self._start()
        self.assertEqual(first["state"], "pending")
        self.request.side_effect = [self._refund_response("completed", amount=617)]
        self.assertEqual(self._poll(first)["state"], "verified")
        self.payload["uuid"] = str(uuid4())
        self.payload["payment_ids"][0][2]["uuid"] = str(uuid4())
        self.refund_id = str(uuid4())
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed",
                           amount=1234, currency=self.session.currency_id.name, refunded_amount=617),
            self._refund_response(amount=617),
        ]
        second = self._start()
        self.assertEqual(second["state"], "pending")
        self.assertNotEqual(first["operation_id"], second["operation_id"])
        self.payload["uuid"] = str(uuid4())
        self.payload["payment_ids"][0][2].update(uuid=str(uuid4()), amount=-0.01)
        self.payload["lines"][0][2].update(qty=-0.001, price_subtotal=-0.01, price_subtotal_incl=-0.01)
        self.payload["amount_total"] = self.payload["amount_paid"] = -0.01
        self.request.reset_mock()
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_mixed_tender_return_refunds_only_original_revolut_share(self):
        self._split_original()
        self.payload["payment_ids"][0][2]["amount"] = -6.17
        self.payload["payment_ids"].append(Command.create({
            "uuid": str(uuid4()), "payment_method_id": self.cash_payment_method.id,
            "amount": -6.17, "payment_status": "done", "transaction_id": False,
        }))
        sources = self.revolut_method.revolut_refund_sources(
            self.session.id, self.session.currency_id.id, self.payload,
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["remaining_minor"], 617)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed",
                           amount=617, currency=self.session.currency_id.name),
            self._refund_response(amount=617),
        ]
        started = self._start()
        self.request.side_effect = [self._refund_response("completed", amount=617)]
        self.assertEqual(self._poll(started)["state"], "verified")
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        saved = self.env["pos.order"].sync_from_ui([self.payload])
        order = self.env["pos.order"].browse(next(item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]))
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.payment_ids.filtered(lambda item: item.payment_method_id == self.revolut_method).revolut_refund_operation_id.original_operation_id, self.source)
        self.assertFalse(order.payment_ids.filtered(lambda item: item.payment_method_id == self.cash_payment_method).revolut_refund_operation_id)

    def test_cash_only_partial_return_uses_only_original_cash_balance(self):
        self._split_original()
        self.payload["amount_total"] = self.payload["amount_paid"] = -6.17
        self.payload["lines"][0][2].update(qty=-0.5, price_subtotal=-6.17, price_subtotal_incl=-6.17)
        self.payload["payment_ids"][0][2].update(
            payment_method_id=self.cash_payment_method.id, amount=-6.17,
            payment_status="done", transaction_id=False,
        )
        saved = self.env["pos.order"].sync_from_ui([self.payload])
        order = self.env["pos.order"].browse(next(item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]))
        self.assertEqual(order.state, "paid")
        self.assertFalse(order.payment_ids.revolut_refund_operation_id)
        self.payload["uuid"] = str(uuid4())
        self.payload["payment_ids"][0][2]["uuid"] = str(uuid4())
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])
        self.request.assert_not_called()

    def test_positive_tender_cannot_hide_overallocated_refund(self):
        self._split_original()
        self.payload["amount_total"] = self.payload["amount_paid"] = -6.17
        self.payload["lines"][0][2].update(qty=-0.5, price_subtotal=-6.17, price_subtotal_incl=-6.17)
        self.payload["payment_ids"][0][2]["amount"] = -6.17
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=617,
                           currency=self.session.currency_id.name),
            self._refund_response(amount=617),
        ]
        started = self._start()
        self.request.side_effect = [self._refund_response("completed", amount=617)]
        self.assertEqual(self._poll(started)["state"], "verified")
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        for amount in (-6.17, 6.17):
            self.payload["payment_ids"].append(Command.create({
                "uuid": str(uuid4()), "payment_method_id": self.cash_payment_method.id,
                "amount": amount, "payment_status": "done", "transaction_id": False,
            }))
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])

    def test_completed_return_reserves_original_product_quantity(self):
        original = self._order_payload(str(uuid4()), str(uuid4()))
        original["lines"][0][2].update(price_unit=1.0, price_subtotal=1.0, price_subtotal_incl=1.0)
        expensive = self.env["product.product"].create({
            "name": "Other refund product", "available_in_pos": True,
            "list_price": 11.34, "taxes_id": [Command.clear()],
        })
        original["lines"].append(Command.create({
            "uuid": str(uuid4()), "product_id": expensive.id, "qty": 1,
            "price_unit": 11.34, "price_subtotal": 11.34, "price_subtotal_incl": 11.34,
            "discount": 0, "tax_ids": [[6, False, []]], "pack_lot_ids": [],
        }))
        financial = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(original)
        source = self._operation(
            original["uuid"], original["payment_ids"][0][2]["uuid"],
            financial_snapshot=financial,
        )
        original["payment_ids"][0][2]["transaction_id"] = source.revolut_payment_id
        self.env["pos.order"].sync_from_ui([original])
        self.env.flush_all()
        source.invalidate_recordset()
        self.source = source
        self.original = source.pos_order_id
        cheap_line = self.original.lines.filtered(lambda line: line.product_id == self.product)
        self.payload["lines"][0][2].update(
            price_unit=1.0, price_subtotal=-1.0, price_subtotal_incl=-1.0,
            refunded_orderline_id=cheap_line.id,
        )
        self.payload["amount_total"] = self.payload["amount_paid"] = -1.0
        self.payload["payment_ids"][0][2]["amount"] = -1.0
        self.request.side_effect = [
            self._response(id=source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name),
            self._refund_response(amount=100),
        ]
        started = self._start()
        self.request.side_effect = [self._refund_response("completed", amount=100)]
        self.assertEqual(self._poll(started)["state"], "verified")
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        self.env["pos.order"].sync_from_ui([self.payload])
        self.env.flush_all()
        self.payload["uuid"] = str(uuid4())
        self.payload["payment_ids"][0][2].update(uuid=str(uuid4()), payment_status="waiting", transaction_id=False)
        self.request.reset_mock()
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_two_original_allocations_preserve_success_when_other_fails(self):
        first_source, second_source = self._split_original(second_revolut=True)
        first_line = self.payload["payment_ids"][0][2]
        first_line["amount"] = -6.17
        second_line = dict(first_line, uuid=str(uuid4()))
        self.payload["payment_ids"].append(Command.create(second_line))
        sources = self.revolut_method.revolut_refund_sources(
            self.session.id, self.session.currency_id.id, self.payload,
        )
        self.assertEqual({item["operation_id"] for item in sources}, {first_source.id, second_source.id})
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()
        self.request.side_effect = [
            self._response(id=first_source.revolut_order_id, state="completed", amount=617,
                           currency=self.session.currency_id.name),
            self._refund_response(amount=617),
        ]
        first = self.revolut_method.revolut_start_refund(
            self.session.id, self.payload["uuid"], first_line["uuid"], -6.17,
            self.session.currency_id.id, self.payload, first_source.id,
        )
        self.request.side_effect = [self._refund_response("completed", amount=617)]
        self.assertEqual(self.revolut_method.revolut_poll_refund(first["operation_id"], self.payload["uuid"], first_line["uuid"])["state"], "verified")
        first_line.update(payment_status="done", transaction_id=self.refund_id)
        self.refund_id = str(uuid4())
        self.request.side_effect = [
            self._response(id=second_source.revolut_order_id, state="completed", amount=617,
                           currency=self.session.currency_id.name),
            self._refund_response(amount=617, source=second_source),
        ]
        second = self.revolut_method.revolut_start_refund(
            self.session.id, self.payload["uuid"], second_line["uuid"], -6.17,
            self.session.currency_id.id, self.payload, second_source.id,
        )
        self.request.side_effect = [self._refund_response("failed", amount=617, source=second_source)]
        self.assertEqual(self.revolut_method.revolut_poll_refund(second["operation_id"], self.payload["uuid"], second_line["uuid"])["state"], "failed")
        second_line.update(payment_status="done", transaction_id=self.refund_id)
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])
        self.assertEqual(self.revolut_method.revolut_find_refund(self.payload["uuid"], first_line["uuid"])["state"], "verified")
        self.payload["payment_ids"].pop()
        replacement = dict(second_line, uuid=str(uuid4()), transaction_id=False, payment_status="waiting")
        self.payload["payment_ids"].append(Command.create(replacement))
        self.refund_id = str(uuid4())
        self.request.side_effect = [
            self._response(id=second_source.revolut_order_id, state="completed", amount=617,
                           currency=self.session.currency_id.name),
            self._refund_response(amount=617, source=second_source),
        ]
        retried = self.revolut_method.revolut_start_refund(
            self.session.id, self.payload["uuid"], replacement["uuid"], -6.17,
            self.session.currency_id.id, self.payload, second_source.id,
        )
        self.assertNotEqual(retried["operation_id"], second["operation_id"])
        self.request.side_effect = [self._refund_response("completed", amount=617, source=second_source)]
        self.assertEqual(self.revolut_method.revolut_poll_refund(retried["operation_id"], self.payload["uuid"], replacement["uuid"])["state"], "verified")
        replacement.update(payment_status="done", transaction_id=self.refund_id)
        saved = self.env["pos.order"].sync_from_ui([self.payload])
        order = self.env["pos.order"].browse(next(item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]))
        self.assertEqual(order.state, "paid")
        self.assertEqual(set(order.payment_ids.revolut_refund_operation_id.ids), {first["operation_id"], retried["operation_id"]})

    def test_full_refund_requires_verified_completion(self):
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed",
                           amount=1234, currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(),
        ]
        self.assertEqual(self.original.payment_ids.revolut_operation_id, self.source)
        self.assertEqual(self.original.payment_ids.transaction_id, self.source.revolut_payment_id)
        self.assertEqual(self.source.pos_payment_id, self.original.payment_ids)
        self.assertEqual(self.source.payment_method_id, self.revolut_method)
        started = self._start()
        self.assertEqual(started["state"], "pending")
        self.assertEqual(started["order_id"], self.refund_id)
        self.request.side_effect = [self._refund_response("completed")]
        result = self.revolut_method.revolut_poll_refund(
            started["operation_id"], self.payload["uuid"],
            self.payload["payment_ids"][0][2]["uuid"],
        )
        self.assertEqual(result["state"], "verified")
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        saved = self.env["pos.order"].sync_from_ui([self.payload])
        order = self.env["pos.order"].browse(next(item["id"] for item in saved["pos.order"] if item["uuid"] == self.payload["uuid"]))
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.payment_ids.revolut_refund_operation_id.original_operation_id, self.source)

    def _pending(self):
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed",
                           amount=1234, currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(),
        ]
        return self._start()

    def _poll(self, started):
        return self.revolut_method.revolut_poll_refund(
            started["operation_id"], self.payload["uuid"],
            self.payload["payment_ids"][0][2]["uuid"],
        )

    def test_pending_refund_blocks_deployment_until_verified(self):
        started = self._pending()
        refund = self.env["pos.revolut.refund.operation"].browse(
            started["operation_id"]
        )
        self.assertTrue(refund.deployment_blocking)

        self.request.side_effect = [self._refund_response("completed")]
        self.assertEqual(self._poll(started)["state"], "verified")
        refund.invalidate_recordset()
        self.assertFalse(refund.deployment_blocking)

    def test_duplicate_submit_reuses_refund_and_key(self):
        started = self._pending()
        self.assertEqual(self._start(), started)
        self.assertEqual(self.request.call_count, 2)
        post = self.request.call_args_list[1]
        self.assertTrue(post.kwargs["headers"]["Idempotency-Key"])
        self.assertEqual(post.kwargs["json"]["merchant_order_data"]["reference"],
                         post.kwargs["headers"]["Idempotency-Key"])

    def test_duplicate_submit_rejects_changed_return_total(self):
        self._pending()
        self.request.reset_mock()
        self.payload["amount_total"] = -12.35
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_cashier_cannot_issue_or_reconcile_refund(self):
        cashier = new_test_user(self.env, login="refund_cashier", groups="point_of_sale.group_pos_user")
        with self.assertRaises(AccessError):
            self.revolut_method.with_user(cashier).revolut_start_refund(
                self.session.id, self.payload["uuid"], self.payload["payment_ids"][0][2]["uuid"],
                -12.34, self.session.currency_id.id, self.payload,
            )
        self.request.assert_not_called()
        started = self._pending()
        with self.assertRaises(AccessError):
            self.revolut_method.with_user(cashier).revolut_poll_refund(
                started["operation_id"], self.payload["uuid"], self.payload["payment_ids"][0][2]["uuid"],
            )
        with self.assertRaises(AccessError):
            self.env["pos.revolut.refund.operation"].with_user(cashier).browse(started["operation_id"]).read(["amount"])

    def test_unverified_original_cannot_be_refunded(self):
        self.source.write({"state": "unresolved"})
        self.env.flush_all()
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_missing_return_total_cannot_dispatch_refund(self):
        self.payload.pop("amount_total")
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_unrelated_or_excessive_return_cannot_be_refunded(self):
        self.payload["lines"][0][2]["qty"] = -2
        with self.assertRaises(UserError):
            self._start()
        self.payload["lines"][0][2]["qty"] = -1
        self.payload["lines"][0][2]["refunded_orderline_id"] = 2147483647
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_cross_company_original_cannot_be_refunded(self):
        other = self.env["res.company"].create({"name": "Refund other company"})
        foreign_original = self.env["pos.order"].create({
            "session_id": self.session.id, "company_id": other.id,
            "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                "product_id": self.product.id, "qty": 1, "price_unit": 12.34,
                "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
                "tax_ids": [Command.clear()],
            })],
        })
        self.payload["lines"][0][2]["refunded_orderline_id"] = foreign_original.lines.id
        with self.assertRaises(AccessError):
            self._start()
        self.request.assert_not_called()

    def test_provider_original_must_be_completed_and_unrefunded(self):
        self.request.side_effect = [self._response(
            id=self.source.revolut_order_id, state="authorised", amount=1234,
            currency=self.session.currency_id.name, refunded_amount=0,
        )]
        result = self._start()
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["provider_state"], "original_ineligible")
        self.assertEqual(self.request.call_count, 1)

    def test_failed_refund_cannot_complete_or_silently_use_cash(self):
        started = self._pending()
        self.request.side_effect = [self._refund_response("failed")]
        self.assertEqual(self._poll(started)["state"], "failed")
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])
        self.payload["payment_ids"][0][2]["payment_method_id"] = self.cash_payment_method.id
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])

    def test_pending_refund_and_original_return_cannot_settle_as_cash(self):
        self.payload["payment_ids"][0][2].update(payment_method_id=self.cash_payment_method.id, payment_status="done")
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])
        self.payload["payment_ids"][0][2].update(payment_method_id=self.revolut_method.id, payment_status="waiting")
        self._pending()
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])

    def test_missing_active_refund_allocation_cannot_settle_return(self):
        self._pending()
        self.payload["payment_ids"] = []
        self.payload["state"] = "paid"
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])

    def test_lost_response_recovered_by_reference_without_replay(self):
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            requests.Timeout(),
        ]
        started = self._start()
        self.assertEqual(started["state"], "unresolved")
        self.assertFalse(started["order_id"])
        self.assertEqual(self._start(), started)
        reference = self.request.call_args_list[1].kwargs["headers"]["Idempotency-Key"]
        candidate = self._refund_response("completed").json()
        candidate["merchant_order_data"] = {"reference": reference}
        self.request.side_effect = [self._response(orders=[candidate]), self._refund_response("completed")]
        result = self._poll(started)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["order_id"], self.refund_id)
        self.assertEqual(len([call for call in self.request.call_args_list if call.args[0] == "POST"]), 1)

    def test_missing_refund_search_stays_uncertain_and_reserves_amount(self):
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name), requests.Timeout(),
        ]
        started = self._start()
        self.request.side_effect = [self._response(orders=[])]
        self.assertEqual(self._poll(started)["state"], "unresolved")
        self.payload["uuid"] = str(uuid4())
        self.payload["payment_ids"][0][2]["uuid"] = str(uuid4())
        with self.assertRaises(UserError):
            self._start()

    def test_background_reconciliation_and_reload_observe_late_completion(self):
        started = self._pending()
        self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"]).write({"next_reconcile_at": "2000-01-01"})
        self.env.flush_all()
        self.request.side_effect = [self._refund_response("completed")]
        self.env["pos.revolut.refund.operation"]._cron_reconcile_refunds(1)
        result = self.revolut_method.revolut_find_refund(self.payload["uuid"], self.payload["payment_ids"][0][2]["uuid"])
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["order_id"], self.refund_id)

    def test_mismatched_refund_response_cannot_verify(self):
        started = self._pending()
        wrong = self._refund_response("completed").json()
        wrong["related_order_id"] = str(uuid4())
        self.request.side_effect = [self._response(**wrong)]
        self.assertEqual(self._poll(started)["state"], "unresolved")

    def test_refund_amount_currency_key_and_relationship_are_immutable(self):
        started = self._pending()
        operation = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        for values in ({"amount_minor": 1}, {"currency_id": self.env.ref("base.EUR").id},
                       {"idempotency_key": str(uuid4())}, {"original_operation_id": False}):
            with self.assertRaises(ValidationError):
                operation.write(values)

    def test_malformed_recovery_reference_stays_unresolved(self):
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name), requests.Timeout(),
        ]
        started = self._start()
        candidate = self._refund_response().json()
        candidate["merchant_order_data"] = None
        self.request.side_effect = [self._response(orders=[candidate])]
        self.assertEqual(self._poll(started)["state"], "unresolved")

    def test_return_cannot_dispatch_while_charge_exists_for_same_order(self):
        self._operation(self.payload["uuid"], str(uuid4()), state="pending",
                        financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(self.payload))
        self.env.flush_all()
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_refund_order_cannot_start_a_charge(self):
        self._pending()
        with self.assertRaises(UserError):
            self.revolut_method.revolut_start_payment(
                self.session.id, self.payload["uuid"], str(uuid4()), 12.34,
                self.session.currency_id.id, False, self.payload,
            )
        self.assertEqual(self.request.call_count, 2)

    def test_verified_refund_cannot_settle_another_return(self):
        started = self._pending()
        self.request.side_effect = [self._refund_response("completed")]
        self._poll(started)
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        self.payload["uuid"] = str(uuid4())
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])

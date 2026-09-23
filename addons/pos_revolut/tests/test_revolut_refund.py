import os
from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests.common import tagged, new_test_user
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
            financial_snapshot=self.env["pos.revolut.payment.operation"].normalize_financial_snapshot(original),
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
            self.payload["payment_ids"][0][2]["uuid"], -12.34,
            self.session.currency_id.id, self.payload,
        )

    def _response(self, **payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _refund_response(self, state="pending"):
        return self._response(id=self.refund_id, type="refund", state=state,
                              related_order_id=self.source.revolut_order_id,
                              amount=1234, currency=self.session.currency_id.name)

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

    def test_duplicate_submit_reuses_refund_and_key(self):
        started = self._pending()
        self.assertEqual(self._start(), started)
        self.assertEqual(self.request.call_count, 2)
        post = self.request.call_args_list[1]
        self.assertTrue(post.kwargs["headers"]["Idempotency-Key"])
        self.assertEqual(post.kwargs["json"]["merchant_order_data"]["reference"],
                         post.kwargs["headers"]["Idempotency-Key"])

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

    def test_unrelated_or_partial_return_cannot_be_refunded(self):
        self.payload["lines"][0][2]["qty"] = -0.5
        with self.assertRaises(UserError):
            self._start()
        self.payload["lines"][0][2]["qty"] = -1
        self.payload["lines"][0][2]["refunded_orderline_id"] = 2147483647
        with self.assertRaises(UserError):
            self._start()
        self.request.assert_not_called()

    def test_cross_company_original_cannot_be_refunded(self):
        other = self.env["res.company"].create({"name": "Refund other company"})
        self.original.write({"company_id": other.id})
        self.env.flush_all()
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
                        financial_snapshot=self.env["pos.revolut.payment.operation"].normalize_financial_snapshot(self.payload))
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

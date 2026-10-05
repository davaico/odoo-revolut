"""Server-side discovery of terminal refunds without native return fabrication."""

import os
from copy import deepcopy
from datetime import datetime, timedelta
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, api, fields, SUPERUSER_ID
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError
from odoo.service.model import call_kw
from odoo.tests.common import tagged, TransactionCase, new_test_user

from .test_revolut_refund import TestRevolutRefund
from .test_revolut_refund_concurrency import TestRevolutRefundConcurrency
from .test_revolut_tip_refund import TestRevolutTipRefund


@tagged("post_install", "-at_install")
class TestExternalRefunds(CommonPosTest):
    LOCATION_ID = TestRevolutRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefund.PAYMENT_ID
    _operation = TestRevolutRefund._operation
    _order_payload = TestRevolutRefund._order_payload
    _response = TestRevolutRefund._response
    _refund_response = TestRevolutRefund._refund_response
    _split_original = TestRevolutRefund._split_original
    _save_return_draft = TestRevolutRefund._save_return_draft
    _start = TestRevolutRefund._start
    _mutation_actor = TestRevolutRefund._mutation_actor
    _rpc_refund = TestRevolutRefund._rpc_refund
    _terminal_sale = TestRevolutTipRefund._terminal_sale
    _tip_return = TestRevolutTipRefund._tip_return
    _stream_response = TestRevolutTipRefund._stream_response
    _start_allocated = TestRevolutTipRefund._start_allocated

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "External Revolut refunds", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "External refund goods", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
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
        self.payload.update(amount_paid=-12.34, amount_total=-12.34)
        self.payload["lines"][0][2].update(
            qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
            refunded_orderline_id=self.original.lines.id,
        )
        self.payload["payment_ids"][0][2].update(
            amount=-12.34, transaction_id=False, payment_status="waiting",
        )
        self.refund_id = str(uuid4())
        # Always choose this transactional fixture over older committed
        # concurrency fixtures when the public cron discovers one credential.
        self.source.credential_id.sudo().write({"next_refund_discovery_at": False})
        self.env.flush_all()

    def _external(self, state="processing", amount=1, source=None, **values):
        result = self._refund_response(state, amount, source).json()
        result.update(created_at="2026-10-01T12:00:00Z")
        result.update(values)
        return result

    def _discover(self, orders, details=None):
        details = details or {order["id"]: order for order in orders if isinstance(order, dict)}

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET", "Import must never move money")
            if url.endswith("/api/orders"):
                return self._response(orders=deepcopy(orders))
            identity = url.rsplit("/", 1)[-1]
            self.assertIn(identity, details)
            return self._response(**deepcopy(details[identity]))

        self.source.credential_id.sudo().write({"next_refund_discovery_at": False})
        self.env.flush_all()
        self.request.side_effect = http
        self.env["pos.revolut.refund.operation"]._cron_reconcile_refunds()
        self.env.invalidate_all()
        return self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", self.source.id),
        ])

    def _remaining(self):
        sources = self.revolut_method.revolut_refund_sources(
            self.session.id, self.session.currency_id.id, self.payload,
        )
        return {item["operation_id"]: item["remaining_minor"] for item in sources}

    def test_closed_session_processing_refund_discovered_without_native_return(self):
        before_orders = self.env["pos.order"].search_count([])
        before_lines = self.env["pos.order.line"].search_count([])
        before_payments = self.env["pos.payment"].search_count([])
        self.session.write({"state": "closed"})
        self.env.flush_all()
        refunds = self._discover([self._external()])
        self.assertEqual(len(refunds), 1)
        refund = refunds
        self.assertEqual(refund.original_operation_id, self.source)
        self.assertEqual(refund.original_order_id, self.original)
        self.assertEqual(refund.pos_session_id, self.session)
        self.assertEqual(refund.origin, "external")
        self.assertEqual(refund.native_reconciliation_status, "outstanding")
        self.assertEqual(refund.revolut_order_id, self.refund_id)
        self.assertEqual(refund.amount_minor, 1)
        self.assertEqual(refund.state, "pending")
        self.assertTrue(refund.deployment_blocking)
        for name in ("order_uuid", "payment_line_uuid", "financial_snapshot", "idempotency_key",
                     "pos_order_id", "pos_payment_id"):
            self.assertFalse(refund[name], name)
        self.assertEqual(self.env["pos.order"].search_count([]), before_orders)
        self.assertEqual(self.env["pos.order.line"].search_count([]), before_lines)
        self.assertEqual(self.env["pos.payment"].search_count([]), before_payments)
        self.session.write({"state": "opened"})
        self.assertEqual(self._remaining()[self.source.id], 1233)
        self.assertTrue(any(call.args[1].endswith("/api/orders/" + self.refund_id)
                            for call in self.request.call_args_list))
        for call in self.request.call_args_list:
            if call.args[1].endswith("/api/orders"):
                self.assertLessEqual(call.kwargs["params"]["limit"], 100)
                self.assertIn("from", call.kwargs["params"])
                self.assertIn("to", call.kwargs["params"])

    def test_partial_completion_and_duplicate_reads_reserve_once(self):
        candidate = self._external("completed", amount=617)
        refunds = self._discover([candidate, candidate])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "verified")
        self.assertTrue(refunds.verified_at)
        self.assertFalse(refunds.deployment_blocking)
        self.assertEqual(self._remaining()[self.source.id], 617)
        previous = refunds.id
        refunds = self._discover([candidate])
        self.assertEqual(refunds.ids, [previous])
        self.assertEqual(self._remaining()[self.source.id], 617)

    def test_refund_list_without_parent_uses_authoritative_detail(self):
        detail = self._external("completed", amount=617)
        listed = dict(detail)
        listed.pop("related_order_id")
        refunds = self._discover([listed], {self.refund_id: detail})
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.original_operation_id, self.source)
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(self._remaining()[self.source.id], 617)
        self.assertFalse(self.source.external_refund_review_required)
        self.assertTrue(any(call.args[1].endswith("/api/orders/" + self.refund_id)
                            for call in self.request.call_args_list))

    def test_full_external_refund_consumes_card_capacity_without_returning_products(self):
        original_qty = self.original.lines.qty
        refunds = self._discover([self._external("completed", amount=1234)])
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(self._remaining()[self.source.id], 0)
        self.assertEqual(self.original.lines.qty, original_qty)
        self.assertFalse(self.original.lines.refund_orderline_ids)
        self.assertFalse(refunds.pos_order_id)
        self.assertFalse(refunds.pos_payment_id)

    def test_processing_list_and_completed_original_do_not_verify_refund(self):
        listed = self._external("completed", amount=617)
        detail = self._external("processing", amount=617)
        refunds = self._discover([listed], {self.refund_id: detail})
        self.assertEqual(refunds.state, "pending")
        self.assertEqual(refunds.provider_state, "processing")
        self.assertFalse(refunds.verified_at)
        self.assertEqual(self._remaining()[self.source.id], 617)
        refunds = self._discover([self._external("completed", amount=617)])
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(self._remaining()[self.source.id], 617)

    def test_verified_failure_releases_external_reservation(self):
        candidate = self._external(amount=617)
        refunds = self._discover([candidate])
        identity = refunds.id
        self.assertEqual(self._remaining()[self.source.id], 617)
        refunds = self._discover([self._external("failed", amount=617)])
        self.assertEqual(refunds.ids, [identity])
        self.assertEqual(refunds.state, "failed")
        self.assertFalse(refunds.deployment_blocking)
        self.assertEqual(self._remaining()[self.source.id], 1234)
        self.assertFalse(refunds.pos_order_id)

    def test_unknown_provider_state_stays_unresolved_and_reserves_capacity(self):
        refunds = self._discover([self._external("unknown", amount=617)])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "unresolved")
        self.assertTrue(refunds.deployment_blocking)
        self.assertFalse(refunds.verified_at)
        self.assertLessEqual(self._remaining()[self.source.id], 617)
        self.assertEqual(refunds.amount_minor, 617)

    def test_detail_failure_preserves_amount_and_recovers_without_replay(self):
        import requests

        candidate = self._external(amount=617)

        def interrupted(method, url, **kwargs):
            self.assertEqual(method, "GET")
            if url.endswith("/api/orders"):
                return self._response(orders=[candidate])
            raise requests.Timeout()

        self.request.side_effect = interrupted
        self.env["pos.revolut.refund.operation"]._cron_reconcile_refunds()
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", self.source.id),
        ])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "unresolved")
        self.assertTrue(refunds.deployment_blocking)
        self.assertLessEqual(self._remaining()[self.source.id], 617)
        self.assertEqual(refunds.amount_minor, 617)
        identity = refunds.id
        refunds = self._discover([self._external("completed", amount=617)])
        self.assertEqual(refunds.ids, [identity])
        self.assertEqual(refunds.state, "verified")

    def test_unsafe_provider_evidence_blocks_source_and_does_not_invent_refund(self):
        cases = (
            {"amount": "617"}, {"amount": True}, {"amount": 0}, {"amount": 1235},
            {"currency": "XXX"}, {"id": "truncated-provider-id"},
        )
        for invalid in cases:
            with self.subTest(invalid=invalid):
                self.env["pos.revolut.external.refund.evidence"].sudo().search([
                    ("credential_id", "=", self.source.credential_id.id),
                ]).write({"resolved": True})
                self.env.flush_all()
                refunds = self._discover([self._external(**invalid)])
                self.assertFalse(refunds)
                self.assertTrue(self.source.external_refund_review_required)
                self.assertTrue(self.source.external_refund_review_note)
                self.assertEqual(self._remaining()[self.source.id], 0)

    def test_detail_identity_conflict_preserves_reservation_and_requires_review(self):
        listed = self._external(amount=617)
        detail = self._external("completed", amount=617, related_order_id=str(uuid4()))
        refunds = self._discover([listed], {self.refund_id: detail})
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "unresolved")
        self.assertTrue(self.source.external_refund_review_required)
        self.assertTrue(self.source.external_refund_review_note)
        self.assertFalse(refunds.verified_at)
        self.assertEqual(self._remaining()[self.source.id], 0)

    def test_mixed_tender_external_refund_never_consumes_cash(self):
        source, _ = self._split_original()
        cash = self.original.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.cash_payment_method
        )
        self.assertEqual(cash.amount, 6.17)
        refunds = self._discover([self._external("completed", amount=300)])
        self.assertEqual(refunds.original_operation_id, source)
        self.assertEqual(self._remaining(), {source.id: 317})
        self.assertEqual(cash.amount, 6.17)
        self.assertFalse(cash.revolut_refund_operation_id)
        self.assertFalse(refunds.financial_snapshot)

    def test_multiple_revolut_allocations_match_full_original_identity(self):
        first, second = self._split_original(second_revolut=True)
        first_candidate = self._external(amount=100, source=first)
        second_candidate = self._external("completed", amount=200, source=second, id=str(uuid4()))
        self._discover([first_candidate, second_candidate])
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "in", [first.id, second.id]),
        ])
        self.assertEqual(len(refunds), 2)
        self.assertEqual(self._remaining(), {first.id: 517, second.id: 417})
        self.assertEqual(refunds.mapped("origin"), ["external", "external"])

    def test_odoo_reference_recovers_existing_attempt_without_external_duplicate(self):
        import requests

        self.request.side_effect = [self._response(
            id=self.source.revolut_order_id, state="completed", amount=1234,
            currency=self.session.currency_id.name, refunded_amount=0,
        ), requests.Timeout()]
        started = self._start()
        self.assertEqual(started["state"], "unresolved")
        refund = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        frozen = {name: deepcopy(refund[name]) for name in (
            "financial_snapshot", "order_uuid", "payment_line_uuid", "idempotency_key",
        )}
        candidate = self._external("completed", amount=1234,
                                   merchant_order_data={"reference": refund.idempotency_key})
        self.request.reset_mock()
        refunds = self._discover([candidate])
        self.assertEqual(refunds.ids, [refund.id])
        self.assertEqual(refunds.origin, "odoo")
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(refunds.revolut_order_id, self.refund_id)
        for name, value in frozen.items():
            self.assertEqual(refunds[name], value, name)
        self.assertFalse(refunds.pos_order_id)
        self.assertEqual(self._remaining()[self.source.id], 0)

    def test_legacy_missing_and_invalid_original_refunded_amount_never_dispatch(self):
        marker = object()
        for refunded_amount in (marker, None, False, True, "0", 0.0, -1, 1235):
            with self.subTest(refunded_amount=refunded_amount):
                self.payload["uuid"] = str(uuid4())
                self.payload["payment_ids"][0][2]["uuid"] = str(uuid4())
                original = {
                    "id": self.source.revolut_order_id, "state": "completed",
                    "amount": 1234, "currency": self.session.currency_id.name,
                }
                if refunded_amount is not marker:
                    original["refunded_amount"] = refunded_amount
                self.request.reset_mock()
                self.request.side_effect = [self._response(**original)]
                result = self._start()
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["provider_state"], "original_ineligible")
                self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET"])

    def test_other_company_merchant_cannot_link_own_original_order(self):
        other_company = self.env["res.company"].create({"name": "External refund other merchant"})
        other_method = self.env["pos.payment.method"].sudo().create({
            "name": "Foreign external refund credential", "company_id": other_company.id,
            "payment_method_type": "terminal", "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox", "revolut_location_id": str(uuid4()),
            "revolut_terminal_id": str(uuid4()), "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_EXTERNAL_OTHER_TEST",
        })
        self._operation(
            str(uuid4()), str(uuid4()), payment_method_id=other_method.id,
            company_id=other_company.id, secret_reference=other_method.revolut_secret_reference,
            location_id=other_method.revolut_location_id, terminal_id=other_method.revolut_terminal_id,
        )
        candidate = self._external("completed")

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            token = kwargs["headers"]["Authorization"]
            if url.endswith("/api/orders"):
                return self._response(orders=[candidate] if token == "Bearer other-merchant" else [])
            self.fail("A different company's Merchant evidence must not read or import our order")

        self.env.flush_all()
        with patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_EXTERNAL_OTHER_TEST": "other-merchant"}):
            self.request.side_effect = http
            self.env["pos.revolut.refund.operation"]._cron_discover_external_refunds(batch_size=5)
        self.env.invalidate_all()
        self.assertFalse(self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", self.source.id),
        ]))
        self.assertEqual(self._remaining()[self.source.id], 1234)

    def test_one_interrupted_detail_does_not_starve_later_refund(self):
        import requests

        first = self._external(amount=100)
        later = self._external("completed", amount=200, id=str(uuid4()))

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            if url.endswith("/api/orders"):
                return self._response(orders=[first, later])
            if url.endswith("/" + first["id"]):
                raise requests.Timeout()
            self.assertTrue(url.endswith("/" + later["id"]))
            return self._response(**later)

        self.request.side_effect = http
        self.env["pos.revolut.refund.operation"]._cron_reconcile_refunds()
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", self.source.id),
        ])
        self.assertEqual(len(refunds), 2)
        self.assertEqual(refunds.filtered(lambda refund: refund.revolut_order_id == first["id"]).state, "unresolved")
        self.assertEqual(refunds.filtered(lambda refund: refund.revolut_order_id == later["id"]).state, "verified")
        self.assertLessEqual(self._remaining()[self.source.id], 934)
        self.assertEqual(sum(refunds.mapped("amount_minor")), 300)

    def test_provider_race_rejects_post_without_replay_or_native_settlement(self):
        # Local serialization cannot lock the physical terminal. Simulate a
        # terminal refund after the original GET, with provider enforcement
        # rejecting the now excessive Odoo refund POST.
        import requests

        external = self._external("completed", amount=1, id=str(uuid4()))
        posts = []

        def race(method, url, **kwargs):
            if method == "GET":
                return self._response(
                    id=self.source.revolut_order_id, state="completed", amount=1234,
                    currency=self.session.currency_id.name, refunded_amount=0,
                )
            self.assertEqual(method, "POST")
            posts.append(kwargs["json"])
            self.assertGreater(kwargs["json"]["amount"] + external["amount"], 1234)
            raise requests.HTTPError("Provider refund capacity exceeded")

        self.request.side_effect = race
        result = self._start()
        self.assertEqual(result["state"], "unresolved")
        self.assertEqual(len(posts), 1)
        self.assertEqual(self._start(), result)
        self.assertEqual(len(posts), 1)
        refund = self.env["pos.revolut.refund.operation"].sudo().browse(result["operation_id"])
        self.assertTrue(refund.deployment_blocking)
        self.assertFalse(refund.pos_order_id)
        self.assertFalse(refund.pos_payment_id)
        self.assertEqual(self._remaining()[self.source.id], 0)

    def test_saturated_page_is_subdivided_and_interrupted_window_resumes(self):
        import requests

        first = self._external("completed", amount=100)
        # Other Merchant sales fill this bounded page but are never imported.
        full_page = [dict(id=str(uuid4()), type="payment")] * 99 + [first]
        refunds = self._discover(full_page)
        self.assertEqual(len(refunds), 1)
        credential = self.source.credential_id
        windows = deepcopy(credential.refund_discovery_windows)
        self.assertEqual(len(windows), 2)
        credential.sudo().write({"next_refund_discovery_at": False})
        self.env.flush_all()
        self.request.reset_mock()
        self.request.side_effect = requests.Timeout()
        self.env["pos.revolut.refund.operation"]._cron_reconcile_refunds()
        self.env.invalidate_all()
        self.assertEqual(credential.refund_discovery_windows, windows[1:])
        self.assertIn(windows[0], credential.refund_discovery_retry_windows)
        failed_call = self.request.call_args
        self.assertEqual(failed_call.kwargs["params"]["from"], windows[0][0])
        self.assertEqual(failed_call.kwargs["params"]["to"], windows[0][1])
        later = self._external("completed", amount=200, id=str(uuid4()))
        self._discover([later])
        self.assertFalse(credential.refund_discovery_windows)
        credential.sudo().write({"refund_discovery_steps": 9})
        self._discover([first])
        self.assertFalse(credential.refund_discovery_retry_windows)
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", self.source.id),
        ])
        self.assertEqual(len(refunds), 2)
        self.assertEqual(self._remaining()[self.source.id], 934)

    def test_retired_acknowledgement_cannot_prove_native_work(self):
        manager = self._mutation_actor()
        refund = self._discover([self._external("completed", amount=617)])
        before = {model: self.env[model].search_count([]) for model in (
            "pos.order", "pos.order.line", "pos.payment", "account.move",
        )}
        self.request.reset_mock()
        self.assertEqual(refund.native_reconciliation_status, "outstanding")
        with self.assertRaises(UserError):
            refund.with_user(manager).action_acknowledge_native_reconciliation()
        refund.invalidate_recordset()
        self.assertEqual(refund.native_reconciliation_status, "outstanding")
        self.assertFalse(refund.native_reconciled_by)
        self.assertFalse(refund.native_reconciled_at)
        for model, count in before.items():
            self.assertEqual(self.env[model].search_count([]), count, model)
        self.request.assert_not_called()
        self.assertEqual(self._remaining()[self.source.id], 617)

    def test_pending_external_refund_cannot_be_acknowledged_or_finalize_native_return(self):
        manager = self._mutation_actor()
        refund = self._discover([self._external(amount=617)])
        self.request.reset_mock()
        with self.assertRaises(UserError):
            refund.with_user(manager).action_acknowledge_native_reconciliation()
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([self.payload])
        self.assertFalse(refund.pos_order_id)
        self.assertFalse(refund.pos_payment_id)
        self.assertEqual(refund.native_reconciliation_status, "outstanding")
        self.request.assert_not_called()

    def test_discovery_evidence_is_internal_even_with_full_register_access(self):
        manager = self._mutation_actor()
        self._discover([self._external(currency="XXX")])
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", self.refund_id),
        ])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence.original_operation_id, self.source)
        self.assertEqual(evidence.original_order_id, self.original)
        self.assertTrue(evidence.deployment_blocking)
        unrelated = self.env[evidence._name].sudo().create({
            "credential_id": self.source.credential_id.id,
            "provider_order_id": str(uuid4()), "related_order_id": str(uuid4()),
            "amount_minor": 100, "currency_code": self.source.currency_code,
            "reason": "unrelated_source",
        })
        cashier = new_test_user(self.env, login="evidence_cashier", groups="point_of_sale.group_pos_user")
        administrator = new_test_user(self.env, login="evidence_admin", groups="base.group_system")
        for user in (manager, cashier, administrator):
            user.sudo().write({"group_ids": [Command.link(self.env.ref("base.group_allow_export").id)]})
            model = self.env[evidence._name].with_user(user)
            for record in (evidence, unrelated):
                for method, args in (
                    ("search_read", [[("id", "=", record.id)], ["provider_order_id"]]),
                    ("read", [[record.id], ["provider_order_id", "related_order_id"]]),
                    ("search_count", [[("id", "=", record.id)]]),
                    ("export_data", [[record.id], ["provider_order_id"]]),
                ):
                    with self.subTest(user=user.login, method=method, reason=record.reason):
                        with self.assertRaises(AccessError):
                            call_kw(model, method, args, {})
        # Restricting reads must not clear the financial reservation or evidence.
        self.assertTrue(self.source.external_refund_review_required)
        self.assertEqual(self._remaining()[self.source.id], 0)
        self.assertFalse(evidence.resolved)
        self.assertTrue(evidence.exists())
        self.assertTrue(unrelated.exists())

    def test_discovery_page_and_permissions_are_retired(self):
        for xmlid in (
            "menu_external_refund_evidence", "action_external_refund_evidence",
            "view_external_refund_evidence_list", "view_external_refund_evidence_form",
            "view_external_refund_evidence_search", "access_pos_revolut_external_refund_evidence_manager",
            "rule_revolut_external_refund_evidence_company_manager",
        ):
            self.assertFalse(self.env.ref(f"pos_revolut.{xmlid}", raise_if_not_found=False), xmlid)
        self.assertTrue(self.env.ref("pos_revolut.action_revolut_refunds"))

    def test_cancelled_external_refund_releases_reservation_without_native_work(self):
        refund = self._discover([self._external("cancelled", amount=617)])
        self.assertEqual(refund.state, "failed")
        self.assertEqual(refund.provider_state, "cancelled")
        self.assertEqual(refund.native_reconciliation_status, "not_required")
        self.assertFalse(refund.deployment_blocking)
        self.assertFalse(refund.pos_order_id)
        self.assertEqual(self._remaining()[self.source.id], 1234)

    def test_malformed_page_entry_does_not_starve_valid_external_refund(self):
        # Invalid list entries remain internal evidence without preventing the
        # same bounded read from importing its other complete relationships.
        refund = self._discover([self._external("completed", amount=617), None])
        self.assertEqual(len(refund), 1)
        self.assertEqual(refund.state, "verified")
        self.assertTrue(self.source.external_refund_review_required)
        self.assertEqual(self._remaining()[self.source.id], 0)
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", "malformed-page"),
        ])
        self.assertTrue(evidence)
        self.assertFalse(evidence.original_operation_id)

    def test_external_acknowledgement_requires_manager_and_current_register_grant(self):
        manager = self._mutation_actor()
        cashier = self._mutation_actor(manager=False)
        refund = self._discover([self._external("completed", amount=617)])
        self.request.reset_mock()
        with self.assertRaises(AccessError):
            refund.with_user(cashier).action_acknowledge_native_reconciliation()
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.unlink(manager.id)]})
        with self.assertRaises(AccessError):
            refund.with_user(manager).action_acknowledge_native_reconciliation()
        self.assertEqual(refund.native_reconciliation_status, "outstanding")
        self.assertFalse(refund.native_reconciled_by)
        self.request.assert_not_called()

    def test_documented_unrelated_order_types_do_not_create_investigation_evidence(self):
        orders = [{"id": str(uuid4()), "type": kind} for kind in (
            "payment", "payment_request", "chargeback", "chargeback_reversal",
            "credit_reimbursement",
        )]
        self.assertFalse(self._discover(orders))
        self.assertFalse(self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
        ]))
        self.assertFalse(self.source.external_refund_review_required)
        self.assertEqual(self._remaining()[self.source.id], 1234)
        self.assertTrue(all(call.args[1].endswith("/api/orders") for call in self.request.call_args_list))

    def test_saturated_historical_window_does_not_starve_new_refunds(self):
        before = datetime(2026, 10, 1, 12)
        after = before + timedelta(minutes=6)
        tiny_window = ["2026-10-01T11:59:59.999999Z", "2026-10-01T12:00:00.000000Z"]
        credential = self.source.credential_id
        credential.sudo().write({
            "refund_discovery_windows": [tiny_window],
            "refund_discovery_latest_end": before,
            "next_refund_discovery_at": False,
        })
        self.env.flush_all()
        crowded = [{"id": str(uuid4()), "type": "payment"} for _ in range(100)]
        with patch.object(fields.Datetime, "now", return_value=before):
            self.assertFalse(self._discover(crowded))
        self.assertIn(tiny_window, credential.refund_discovery_retry_windows)
        saturated = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", credential.id), ("reason", "=", "saturated_window"),
        ])
        self.assertTrue(saturated)
        self.assertFalse(saturated.resolved)
        self.request.reset_mock()
        with patch.object(fields.Datetime, "now", return_value=after):
            refund = self._discover([self._external("completed", amount=617)])
        self.assertEqual(refund.state, "verified")
        self.assertIn(tiny_window, credential.refund_discovery_retry_windows)
        self.assertFalse(saturated.resolved)
        lists = [call for call in self.request.call_args_list if call.args[1].endswith("/api/orders")]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].kwargs["params"]["to"], "2026-10-01T12:06:00.000000Z")
        self.assertNotEqual(lists[0].kwargs["params"]["from"], tiny_window[0])

    def test_detail_only_reference_recovers_odoo_lost_response_without_duplicate(self):
        import requests

        self.request.side_effect = [self._response(
            id=self.source.revolut_order_id, state="completed", amount=1234,
            currency=self.session.currency_id.name, refunded_amount=0,
        ), requests.ConnectionError()]
        started = self._start()
        self.assertEqual(started["state"], "unresolved")
        local = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        self.assertFalse(local.revolut_order_id)
        frozen = {name: deepcopy(local[name]) for name in (
            "financial_snapshot", "order_uuid", "payment_line_uuid", "idempotency_key",
        )}
        listed = self._external("completed", amount=1234)
        detail = dict(listed, merchant_order_data={"reference": local.idempotency_key})
        self.request.reset_mock()
        refunds = self._discover([listed], {self.refund_id: detail})
        self.assertEqual(refunds.ids, [local.id])
        self.assertEqual(refunds.origin, "odoo")
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(refunds.revolut_order_id, self.refund_id)
        for name, value in frozen.items():
            self.assertEqual(refunds[name], value, name)
        self.assertEqual(self._remaining()[self.source.id], 0)
        self.assertFalse(refunds.pos_order_id)
        self.assertTrue(all(call.args[0] == "GET" for call in self.request.call_args_list))

    def test_missing_reference_preserves_ambiguous_odoo_attempt_without_second_refund(self):
        import requests

        self.request.side_effect = [self._response(
            id=self.source.revolut_order_id, state="completed", amount=1234,
            currency=self.session.currency_id.name, refunded_amount=0,
        ), requests.ConnectionError()]
        started = self._start()
        self.assertEqual(started["state"], "unresolved")
        local = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        self.assertFalse(local.revolut_order_id)
        candidate = self._external("completed", amount=1234)
        self.request.reset_mock()
        refunds = self._discover([candidate])
        self.assertEqual(refunds.ids, [local.id])
        self.assertEqual(refunds.origin, "odoo")
        self.assertEqual(refunds.state, "unresolved")
        self.assertEqual(refunds.amount_minor, 1234)
        self.assertFalse(refunds.revolut_order_id)
        self.assertTrue(refunds.deployment_blocking)
        self.assertTrue(self.source.external_refund_review_required)
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", self.refund_id),
            ("reason", "=", "ambiguous_odoo_attempt"),
        ])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence.original_operation_id, self.source)
        self.assertFalse(evidence.resolved)
        self.assertEqual(self._remaining()[self.source.id], 0)
        self.assertTrue(all(call.args[0] == "GET" for call in self.request.call_args_list))

    def test_deferred_saturation_does_not_prevent_late_old_refund_visibility(self):
        now = datetime(2026, 10, 1, 12)
        tiny_window = ["2026-10-01T11:59:59.999999Z", "2026-10-01T12:00:00.000000Z"]
        credential = self.source.credential_id
        credential.sudo().write({
            "refund_discovery_windows": [tiny_window],
            "refund_discovery_latest_end": now,
            "refund_discovery_steps": 0,
            "next_refund_discovery_at": False,
        })
        self.env.flush_all()
        crowded = [{"id": str(uuid4()), "type": "payment"} for _ in range(100)]
        with patch.object(fields.Datetime, "now", return_value=now):
            self.assertFalse(self._discover(crowded))
        self.assertFalse(credential.refund_discovery_windows)
        self.assertIn(tiny_window, credential.refund_discovery_retry_windows)
        self.request.reset_mock()
        # This refund becomes visible late with an old creation time outside
        # the saturated interval. Repeating whole history must still find it.
        delayed = self._external("completed", amount=617, created_at="2025-01-01T12:00:00Z")
        with patch.object(fields.Datetime, "now", return_value=now + timedelta(minutes=1)):
            refund = self._discover([delayed])
        self.assertEqual(refund.state, "verified")
        self.assertIn(tiny_window, credential.refund_discovery_retry_windows)
        lists = [call for call in self.request.call_args_list if call.args[1].endswith("/api/orders")]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].kwargs["params"]["from"], "1970-01-01T00:00:00.000000Z")
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", credential.id), ("reason", "=", "saturated_window"),
            ("resolved", "=", False),
        ])
        self.assertTrue(evidence)
        self.assertTrue(self.source.external_refund_review_required)

    def test_failed_history_window_does_not_starve_next_queued_window(self):
        import requests

        first = ["2025-01-01T00:00:00.000000Z", "2025-02-01T00:00:00.000000Z"]
        second = ["2025-02-01T00:00:00.000000Z", "2025-03-01T00:00:00.000000Z"]
        credential = self.source.credential_id
        now = fields.Datetime.now()
        credential.sudo().write({
            "refund_discovery_windows": [first, second],
            "refund_discovery_latest_end": now,
            "refund_discovery_steps": 0,
            "next_refund_discovery_at": False,
        })
        self.env.flush_all()
        self.request.side_effect = requests.Timeout()
        self.env["pos.revolut.refund.operation"]._cron_reconcile_refunds()
        self.env.invalidate_all()
        self.assertEqual(credential.refund_discovery_windows, [second])
        self.assertIn(first, credential.refund_discovery_retry_windows)
        self.request.reset_mock()
        refund = self._discover([self._external("completed", amount=617)])
        self.assertEqual(refund.state, "verified")
        self.assertIn(first, credential.refund_discovery_retry_windows)
        lists = [call for call in self.request.call_args_list if call.args[1].endswith("/api/orders")]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0].kwargs["params"]["from"], second[0])
        self.assertEqual(lists[0].kwargs["params"]["to"], second[1])
        self.assertTrue(self.source.external_refund_review_required)

    def test_authoritative_unrelated_merchant_refund_does_not_block_known_sources(self):
        candidate = self._external(
            "completed", amount=100, related_order_id=str(uuid4()), currency="USD",
        )
        before = {model: self.env[model].search_count([]) for model in (
            "pos.order", "pos.order.line", "pos.payment", "account.move",
        )}
        self.assertFalse(self._discover([candidate]))
        self.assertFalse(self.env["pos.revolut.refund.operation"].sudo().search([
            ("revolut_order_id", "=", self.refund_id),
        ]))
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", self.refund_id),
        ])
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence.reason, "unrelated_source")
        self.assertFalse(evidence.resolved)
        self.assertFalse(evidence.blocks_financial_capacity)
        self.assertFalse(evidence.deployment_blocking)
        self.assertFalse(evidence.original_operation_id)
        self.assertFalse(self.source.external_refund_review_required)
        self.assertEqual(self._remaining()[self.source.id], 1234)
        for model, count in before.items():
            self.assertEqual(self.env[model].search_count([]), count, model)
        self.assertTrue(any(call.args[1].endswith("/api/orders/" + self.refund_id)
                            for call in self.request.call_args_list))

    def test_unrelated_list_parent_survives_omission_from_detail(self):
        listed = self._external("completed", amount=100, related_order_id=str(uuid4()))
        detail = dict(listed)
        detail.pop("related_order_id")
        self.assertFalse(self._discover([listed], {self.refund_id: detail}))
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", self.refund_id),
        ])
        self.assertEqual(evidence.reason, "unrelated_source")
        self.assertFalse(evidence.deployment_blocking)
        self.assertFalse(self.source.external_refund_review_required)

    def test_final_unlinked_foreign_location_keeps_evidence_without_global_block(self):
        candidate = self._external("completed", amount=100, location_id=str(uuid4()))
        candidate.pop("related_order_id")
        before = {model: self.env[model].search_count([]) for model in (
            "pos.order", "pos.payment", "pos.revolut.refund.operation",
        )}
        self.assertFalse(self._discover([candidate]))
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", self.refund_id),
        ])
        self.assertEqual(evidence.reason, "outside_integration_location")
        self.assertFalse(evidence.resolved)
        self.assertFalse(evidence.deployment_blocking)
        self.assertFalse(self.source.external_refund_review_required)
        self.assertEqual(self._remaining()[self.source.id], 1234)
        for model, count in before.items():
            self.assertEqual(self.env[model].search_count([]), count, model)

    def test_discovery_scope_huge_amount_preserves_metadata_without_import(self):
        # Shared Merchant history may contain amounts beyond this integration's
        # integer ledger. Scope proof must not turn them into financial records.
        amount = 4711111114111141111
        evidence_model = self.env["pos.revolut.external.refund.evidence"].sudo()
        models = ("pos.order", "pos.order.line", "pos.payment", "account.move",
                  "pos.revolut.refund.operation")
        before = {model: self.env[model].sudo().search_count([]) for model in models}
        candidate = self._external("completed", amount=amount, currency="EUR",
                                   id=str(uuid4()), location_id=str(uuid4()))
        candidate.pop("related_order_id")
        self.assertFalse(self._discover([candidate]))
        evidence = evidence_model.search([("provider_order_id", "=", candidate["id"])])
        self.assertEqual(evidence.reason, "outside_integration_location")
        self.assertEqual(evidence.amount_minor, 0)
        self.assertFalse(evidence.resolved)
        self.assertFalse(evidence.blocks_financial_capacity)
        self.assertFalse(evidence.deployment_blocking)
        self.assertFalse(evidence.original_operation_id)
        self.assertFalse(self.source.external_refund_review_required)
        for model, count in before.items():
            self.assertEqual(self.env[model].sudo().search_count([]), count, model)

        for location in (None, self.LOCATION_ID, "invalid-location"):
            with self.subTest(location=location):
                candidate = self._external("completed", amount=amount, currency="EUR", id=str(uuid4()))
                candidate.pop("related_order_id")
                if location is not None:
                    candidate["location_id"] = location
                self.assertFalse(self._discover([candidate]))
                evidence = evidence_model.search([("provider_order_id", "=", candidate["id"])])
                self.assertEqual(evidence.amount_minor, 0)
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "outside_integration_location")
                for model, count in before.items():
                    self.assertEqual(self.env[model].sudo().search_count([]), count, model)

        candidate = self._external("completed", amount=amount, id=str(uuid4()), location_id=str(uuid4()))
        self.assertFalse(self._discover([candidate]))
        evidence = evidence_model.search([("provider_order_id", "=", candidate["id"])])
        self.assertEqual(evidence.reason, "amount_or_currency_mismatch")
        self.assertEqual(evidence.amount_minor, 0)
        self.assertTrue(evidence.deployment_blocking)
        for model, count in before.items():
            self.assertEqual(self.env[model].sudo().search_count([]), count, model)

        for state, parent in (("processing", None), ("completed", str(uuid4()))):
            with self.subTest(state=state, parent=parent):
                candidate = self._external(state, amount=amount, currency="EUR", id=str(uuid4()),
                                           location_id=str(uuid4()))
                if parent is None:
                    candidate.pop("related_order_id")
                else:
                    candidate["related_order_id"] = parent
                self.assertFalse(self._discover([candidate]))
                evidence = evidence_model.search([("provider_order_id", "=", candidate["id"])])
                self.assertEqual(evidence.amount_minor, 0)
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "outside_integration_location")
                self.assertNotEqual(evidence.reason, "unrelated_source")
                for model, count in before.items():
                    self.assertEqual(self.env[model].sudo().search_count([]), count, model)

        refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": self.source.id, "pos_session_id": self.session.id,
            "order_uuid": self.payload["uuid"],
            "payment_line_uuid": self.payload["payment_ids"][0][2]["uuid"],
            "financial_snapshot": self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(self.payload),
            "amount": 1, "amount_minor": 100, "currency_id": self.session.currency_id.id,
            "state": "verified", "revolut_order_id": self.refund_id,
        })
        before["pos.revolut.refund.operation"] += 1
        for reference, merchant in (
            (refund.revolut_order_id, {}),
            (str(uuid4()), {"reference": refund.idempotency_key}),
        ):
            with self.subTest(reference=reference):
                candidate = self._external("completed", amount=amount, currency="EUR", id=reference,
                                           location_id=str(uuid4()), merchant_order_data=merchant)
                candidate.pop("related_order_id")
                self._discover([candidate])
                evidence = evidence_model.search([("provider_order_id", "=", reference)])
                self.assertEqual(evidence.amount_minor, 0)
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "outside_integration_location")
                self.assertEqual(refund.state, "verified")
                self.assertEqual(refund.amount_minor, 100)
                for model, count in before.items():
                    self.assertEqual(self.env[model].sudo().search_count([]), count, model)
        self.assertTrue(self.request.call_args_list)
        self.assertTrue(all(call.args[0] == "GET" for call in self.request.call_args_list))

    def test_known_unverified_original_remains_blocking_investigation_evidence(self):
        pending = self._operation(str(uuid4()), str(uuid4()), state="unresolved")
        self.env.flush_all()
        candidate = self._external("completed", amount=100, source=pending)
        self.assertFalse(self._discover([candidate]))
        self.assertFalse(self.env["pos.revolut.refund.operation"].sudo().search([
            ("revolut_order_id", "=", self.refund_id),
        ]))
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", self.source.credential_id.id),
            ("provider_order_id", "=", self.refund_id),
        ])
        self.assertEqual(len(evidence), 1)
        self.assertNotEqual(evidence.reason, "unrelated_source")
        self.assertFalse(evidence.resolved)
        self.assertTrue(evidence.blocks_financial_capacity)
        self.assertTrue(evidence.deployment_blocking)
        self.assertEqual(pending.state, "unresolved")
        self.assertFalse(pending.pos_order_id)

    def test_discovery_scope_missing_same_invalid_location_stays_blocking(self):
        evidence_model = self.env["pos.revolut.external.refund.evidence"].sudo()
        for location in (None, self.LOCATION_ID, "invalid-location", "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"):
            with self.subTest(location=location):
                candidate = self._external("completed", amount=100, id=str(uuid4()))
                candidate.pop("related_order_id")
                if location is not None:
                    candidate["location_id"] = location
                self.assertFalse(self._discover([candidate]))
                evidence = evidence_model.search([("provider_order_id", "=", candidate["id"])])
                self.assertEqual(evidence.reason, "unmatched_source")
                self.assertTrue(evidence.deployment_blocking)
                self.assertTrue(self.source.external_refund_review_required)

    def test_discovery_scope_foreign_location_nonfinal_stays_blocking(self):
        evidence_model = self.env["pos.revolut.external.refund.evidence"].sudo()
        for state in ("pending", "processing", "authorised", "unknown"):
            with self.subTest(state=state):
                candidate = self._external(state, amount=100, id=str(uuid4()), location_id=str(uuid4()))
                candidate.pop("related_order_id")
                self.assertFalse(self._discover([candidate]))
                evidence = evidence_model.search([("provider_order_id", "=", candidate["id"])])
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "outside_integration_location")

    def test_discovery_scope_known_original_overrides_foreign_location(self):
        foreign = str(uuid4())
        candidate = self._external("completed", amount=100, location_id=foreign)
        refunds = self._discover([candidate])
        self.assertEqual(refunds.original_operation_id, self.source)
        self.assertEqual(refunds.state, "verified")

        legacy = self._operation(str(uuid4()), str(uuid4()))
        self.env.flush_all()
        self.cr.execute("UPDATE pos_revolut_payment_operation SET credential_id = NULL WHERE id = %s", [legacy.id])
        legacy.invalidate_recordset()
        candidate = self._external("completed", amount=100, source=legacy, id=str(uuid4()), location_id=foreign)
        self._discover([candidate])
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("provider_order_id", "=", candidate["id"]),
        ])
        self.assertEqual(evidence.reason, "conflicting_original_authority")
        self.assertTrue(evidence.deployment_blocking)
        self.assertFalse(legacy.credential_id)
        self.assertFalse(self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", legacy.id),
        ]))

    def test_discovery_scope_known_refund_id_or_key_stays_blocking(self):
        refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": self.source.id, "pos_session_id": self.session.id,
            "order_uuid": self.payload["uuid"],
            "payment_line_uuid": self.payload["payment_ids"][0][2]["uuid"],
            "financial_snapshot": self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(self.payload),
            "amount": 1, "amount_minor": 100, "currency_id": self.session.currency_id.id,
            "state": "verified", "revolut_order_id": self.refund_id,
        })
        for reference, merchant in (
            (refund.revolut_order_id, {}),
            (str(uuid4()), {"reference": refund.idempotency_key}),
        ):
            with self.subTest(reference=reference):
                candidate = self._external("completed", amount=100, id=reference,
                                           location_id=str(uuid4()), merchant_order_data=merchant)
                candidate.pop("related_order_id")
                self._discover([candidate])
                evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
                    ("provider_order_id", "=", reference),
                ])
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "outside_integration_location")
                self.assertEqual(refund.state, "verified")
        for merchant in (None, {}, {"reference": None}, {"reference": str(uuid4())}):
            with self.subTest(detail_merchant=merchant):
                candidate = self._external("completed", amount=100, id=str(uuid4()),
                                           location_id=str(uuid4()),
                                           merchant_order_data={"reference": refund.idempotency_key})
                candidate.pop("related_order_id")
                detail = dict(candidate)
                if merchant is None:
                    detail.pop("merchant_order_data")
                else:
                    detail["merchant_order_data"] = merchant
                self._discover([candidate], {candidate["id"]: detail})
                evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
                    ("provider_order_id", "=", candidate["id"]),
                ])
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "outside_integration_location")
        for identity in ("provider_id", "merchant_key"):
            for parent_pattern in ("both", "list_only", "detail_only"):
                with self.subTest(identity=identity, parent_pattern=parent_pattern):
                    reference = refund.revolut_order_id if identity == "provider_id" else str(uuid4())
                    merchant = {"reference": refund.idempotency_key} if identity == "merchant_key" else {}
                    candidate = self._external("completed", amount=100, id=reference,
                                               related_order_id=str(uuid4()),
                                               location_id=str(uuid4()), merchant_order_data=merchant)
                    detail = dict(candidate)
                    if parent_pattern == "list_only":
                        detail.pop("related_order_id")
                    elif parent_pattern == "detail_only":
                        candidate.pop("related_order_id")
                    self._discover([candidate], {reference: detail})
                    evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
                        ("provider_order_id", "=", reference),
                    ])
                    self.assertTrue(evidence.deployment_blocking)
                    self.assertNotEqual(evidence.reason, "unrelated_source")
                    self.assertNotEqual(evidence.reason, "outside_integration_location")
                    self.assertEqual(refund.state, "verified")
        self.assertEqual(self.env["pos.revolut.refund.operation"].sudo().search_count([
            ("original_operation_id", "=", self.source.id),
        ]), 1)

    def test_discovery_scope_configured_archived_location_reopens_evidence(self):
        foreign = str(uuid4())
        candidate = self._external("completed", amount=100, location_id=foreign)
        candidate.pop("related_order_id")
        self._discover([candidate])
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("provider_order_id", "=", candidate["id"]),
        ])
        self.assertFalse(evidence.deployment_blocking)
        identity = evidence.id
        self.revolut_method.copy({
            "name": "Archived integration location", "active": False,
            "revolut_location_id": foreign, "revolut_terminal_id": str(uuid4()),
            "revolut_environment": self.revolut_method.revolut_environment,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": self.revolut_method.revolut_secret_reference,
        })
        self._discover([candidate])
        self.assertEqual(evidence.id, identity)
        self.assertEqual(evidence.reason, "unmatched_source")
        self.assertTrue(evidence.deployment_blocking)
        self.assertTrue(self.source.external_refund_review_required)

    def test_discovery_scope_frozen_legacy_location_stays_blocking(self):
        foreign = str(uuid4())
        historical = self._operation(str(uuid4()), str(uuid4()), state="failed", location_id=foreign)
        self.env.flush_all()
        self.cr.execute("UPDATE pos_revolut_payment_operation SET credential_id = NULL WHERE id = %s", [historical.id])
        historical.invalidate_recordset()
        candidate = self._external("completed", amount=100, location_id=foreign)
        candidate.pop("related_order_id")
        self.assertFalse(self._discover([candidate]))
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("provider_order_id", "=", candidate["id"]),
        ])
        self.assertTrue(evidence.deployment_blocking)
        self.assertFalse(historical.credential_id)

    def test_discovery_scope_foreign_evidence_cannot_bypass_public_refund_counter(self):
        candidate = self._external("completed", amount=100, location_id=str(uuid4()))
        candidate.pop("related_order_id")
        self._discover([candidate])
        self.assertFalse(self.source.external_refund_review_required)
        manager = self._mutation_actor()
        for counter in (None, 100):
            with self.subTest(counter=counter):
                claim = deepcopy(self.payload)
                claim["uuid"] = str(uuid4())
                claim["payment_ids"][0][2]["uuid"] = str(uuid4())
                self._save_return_draft(claim, manager)
                original = {"id": self.source.revolut_order_id, "state": "completed",
                            "amount": 1234, "currency": self.session.currency_id.name}
                if counter is not None:
                    original["refunded_amount"] = counter
                self.request.reset_mock()
                self.request.side_effect = [self._response(**original)]
                payment = claim["payment_ids"][0][2]
                result = self._rpc_refund(manager, "pos.payment.method", "revolut_start_refund", [
                    [self.revolut_method.id], self.session.id, claim["uuid"], payment["uuid"],
                    payment["amount"], self.session.currency_id.id, claim,
                ])
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["provider_state"], "original_ineligible")
                self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET"])

    def test_discovery_scope_null_invalid_conflicting_detail_parent_stays_blocking(self):
        for parent in (None, "invalid-parent", str(uuid4())):
            with self.subTest(parent=parent):
                candidate = self._external("completed", amount=100, id=str(uuid4()), related_order_id=str(uuid4()))
                detail = dict(candidate, related_order_id=parent, location_id=str(uuid4()))
                self.assertFalse(self._discover([candidate], {candidate["id"]: detail}))
                evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
                    ("provider_order_id", "=", candidate["id"]),
                ])
                self.assertTrue(evidence.deployment_blocking)
                self.assertNotEqual(evidence.reason, "unrelated_source")
                self.assertNotEqual(evidence.reason, "outside_integration_location")
        candidate = self._external("completed", amount=100, id=str(uuid4()), location_id=str(uuid4()))
        candidate.pop("related_order_id")
        detail = dict(candidate, related_order_id=None)
        self.assertFalse(self._discover([candidate], {candidate["id"]: detail}))
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("provider_order_id", "=", candidate["id"]),
        ])
        self.assertTrue(evidence.deployment_blocking)
        self.assertNotEqual(evidence.reason, "outside_integration_location")

    def test_external_refund_on_terminal_tip_source_does_not_invent_component_authority(self):
        # The original decomposition is real report-verified payment evidence.
        # The external refund has no equivalent base/tip allocation proof.
        self._terminal_sale(tip_minor=200, base_minor=1234)
        self._tip_return(goods_qty=0.5, tip_qty=0, payment_minor=100)
        original_lines = {line.id: line.qty for line in self.original.lines}
        refund = self._discover([self._external("completed", amount=300)])
        self.assertEqual(refund.state, "verified")
        self.assertFalse(refund.allocation_explicit)
        self.assertEqual((refund.base_amount_minor, refund.tip_amount_minor), (0, 0))
        self.assertTrue(self.source.terminal_tip_evidence)
        self.assertEqual((self.source.amount_minor, self.source.terminal_tip_minor), (1234, 200))

        def assert_capacity():
            source = self.revolut_method.revolut_refund_sources(
                self.session.id, self.session.currency_id.id, self.payload,
            )[0]
            self.assertEqual(source["remaining_minor"], 1134)
            self.assertEqual((source["remaining_base_minor"], source["remaining_tip_minor"]), (0, 0))
            self.assertTrue(source["terminal_tip_evidence"])

        self.request.reset_mock()
        assert_capacity()
        with self.assertRaisesRegex(UserError, "external refund has no verified base"):
            self._start_allocated(base_minor=100, tip_minor=0)
        self.assertEqual(self.env["pos.revolut.refund.operation"].sudo().search_count([
            ("original_operation_id", "=", self.source.id),
        ]), 1)
        with self.assertRaises(UserError):
            refund.with_user(self._mutation_actor()).action_acknowledge_native_reconciliation()
        refund.invalidate_recordset()
        self.assertEqual(refund.native_reconciliation_status, "outstanding")
        assert_capacity()
        with self.assertRaisesRegex(UserError, "external refund has no verified base"):
            self._start_allocated(base_minor=100, tip_minor=0)
        self.request.assert_not_called()
        self.assertFalse(refund.allocation_explicit)
        self.assertEqual((refund.base_amount_minor, refund.tip_amount_minor), (0, 0))
        self.assertEqual({line.id: line.qty for line in self.original.lines}, original_lines)
        self.assertFalse(refund.financial_snapshot)
        self.assertFalse(refund.pos_order_id)
        self.assertFalse(refund.pos_payment_id)


@tagged("post_install", "-at_install")
class TestExternalRefundConcurrency(TransactionCase):
    _run_workers = TestRevolutRefundConcurrency._run_workers
    _response = staticmethod(TestRevolutRefundConcurrency._response)

    def setUp(self):
        super().setUp()
        self.registry = self.env.registry
        self.context = {"allowed_company_ids": [self.env.company.id]}
        self.order_uuid, self.line_uuid = str(uuid4()), str(uuid4())
        self.provider_order, self.provider_refund = str(uuid4()), str(uuid4())
        self.secret_reference = "ODOO_REVOLUT_SECRET_EXTERNAL_RACE_" + uuid4().hex.upper()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            method = env["pos.payment.method"].create({
                "name": "Revolut refund concurrency test",
                "payment_method_type": "terminal",
                "use_payment_terminal": "revolut",
                "revolut_environment": "sandbox",
                "revolut_location_id": str(uuid4()),
                "revolut_terminal_id": str(uuid4()),
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": self.secret_reference,
            })
            config = env["pos.config"].create({
                "name": "Revolut refund concurrency test",
                "auto_validate_terminal_payment": True,
                "payment_method_ids": [Command.link(method.id)],
            })
            session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
            product = env["product.product"].create({
                "name": "Refund concurrency product", "list_price": 12.34,
                "available_in_pos": True, "taxes_id": [Command.clear()],
            })
            order_uuid, payment_uuid, payment_reference = str(uuid4()), str(uuid4()), str(uuid4())
            order_values = {
                "name": "Refund concurrency original", "session_id": session.id,
                "uuid": order_uuid, "state": "paid", "amount_total": 12.34,
                "pricelist_id": config.pricelist_id.id,
                "amount_tax": 0, "amount_paid": 12.34, "amount_return": 0,
                "lines": [Command.create({
                    "product_id": product.id, "qty": 1, "price_unit": 12.34,
                    "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
                    "tax_ids": [Command.set([])], "uuid": str(uuid4()),
                })],
                "payment_ids": [Command.create({
                    "payment_method_id": method.id, "amount": 12.34,
                    "uuid": payment_uuid, "payment_status": "done",
                    "transaction_id": payment_reference,
                })],
            }
            operation = env["pos.revolut.payment.operation"].create({
                "payment_method_id": method.id, "company_id": env.company.id,
                "pos_config_id": config.id, "pos_session_id": session.id,
                "order_uuid": order_uuid, "payment_line_uuid": payment_uuid,
                "amount": 12.34, "amount_minor": 1234,
                "currency_id": config.currency_id.id, "currency_code": config.currency_id.name,
                "environment": "sandbox", "location_id": method.revolut_location_id,
                "terminal_id": method.revolut_terminal_id, "fulfilment_type": "eat_in",
                "secret_reference": method.revolut_secret_reference, "state": "verified",
                "revolut_order_id": self.provider_order,
                "revolut_payment_intent_id": str(uuid4()), "revolut_payment_id": payment_reference,
                "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(order_values),
            })
            # The production ORM boundary owns the linkage, even in fixtures.
            order = env["pos.order"].create(order_values)
            self.assertEqual(operation.pos_order_id, order)
            self.method_id, self.session_id = method.id, session.id
            self.source_id, self.credential_id = operation.id, operation.credential_id.id
            operation.credential_id.write({"next_refund_discovery_at": False})
            self.currency_id, self.currency_code = config.currency_id.id, config.currency_id.name
            self.snapshot = {
                "amount_total": -12.34,
                "pricelist_id": order.pricelist_id.id or 0, "fiscal_position_id": False,
                "lines": [{"uuid": str(uuid4()), "product_id": product.id,
                           "qty": -1, "price_unit": 12.34, "discount": 0,
                           "tax_ids": [], "refunded_orderline_id": order.lines.id}],
            }
            cursor.commit()
        self.addCleanup(self._unschedule)
        self.enterContext(patch.dict(os.environ, {
            self.secret_reference: "test-only",
        }))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        self.request.side_effect = self._http

    def _unschedule(self):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.merchant.credential"].browse(self.credential_id).write({
                "next_refund_discovery_at": "2100-01-01",
            })
            env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id),
            ]).write({"next_reconcile_at": False})
            cursor.commit()

    def _candidate(self):
        return {
            "id": self.provider_refund, "type": "refund", "state": "processing",
            "related_order_id": self.provider_order, "amount": 617,
            "currency": self.currency_code, "created_at": "2026-10-01T12:00:00Z",
        }

    def _http(self, method, url, **kwargs):
        self.assertEqual(method, "GET", "Concurrent imports must never move money")
        if url.endswith("/api/orders"):
            return self._response({"orders": [self._candidate()]})
        self.assertTrue(url.endswith("/" + self.provider_refund))
        return self._response(self._candidate())

    def _scan(self):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.refund.operation"]._cron_discover_external_refunds()
            cursor.commit()

    def test_competing_discovery_workers_import_one_provider_refund(self):
        list_started, contender_finished = Event(), Event()

        def http(method, url, **kwargs):
            if url.endswith("/api/orders"):
                list_started.set()
                self.assertTrue(contender_finished.wait(10), "Competing scan blocked on provider I/O")
            return self._http(method, url, **kwargs)

        def contender():
            self.assertTrue(list_started.wait(10), "First scan did not read provider history")
            try:
                self._scan()
            finally:
                contender_finished.set()

        self.request.side_effect = http
        self._run_workers([("first-external-scan", self._scan), ("competing-external-scan", contender)])
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refunds = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id),
            ])
            self.assertEqual(len(refunds), 1)
            self.assertEqual(refunds.revolut_order_id, self.provider_refund)
            self.assertEqual(refunds.amount_minor, 617)
            self.assertEqual(refunds.origin, "external")
            self.assertTrue(refunds.deployment_blocking)
            self.assertFalse(refunds.order_uuid)
            self.assertFalse(refunds.financial_snapshot)
            # A new cursor simulates restart/overlap with the same financial
            # identity; its import must retain the existing reservation.
            identity = refunds.id
            env["pos.revolut.merchant.credential"].browse(self.credential_id).write({
                "next_refund_discovery_at": False,
            })
            cursor.commit()
        self.request.side_effect = self._http
        self._scan()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refunds = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id),
            ])
            self.assertEqual(refunds.ids, [identity])
            self.assertEqual(sum(refunds.mapped("amount_minor")), 617)
        self.assertTrue(all(call.args[0] == "GET" for call in self.request.call_args_list))

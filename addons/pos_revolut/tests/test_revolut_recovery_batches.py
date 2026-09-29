"""Reconciliation entry points with production-owned, committed transactions."""

import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from psycopg2.errors import UniqueViolation

from odoo import SUPERUSER_ID, Command, api, fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestRevolutRecoveryBatches(TransactionCase):
    def setUp(self):
        super().setUp()
        self.registry = self.env.registry
        self.context = {"allowed_company_ids": [self.env.company.id]}
        # Keep other tests' committed attempts out of these cron runs.
        self.now = datetime(1990, 1, 1, 12)
        self.clock = self.enterContext(patch.object(fields.Datetime, "now", return_value=self.now))
        self.enterContext(patch.dict(os.environ, {
            "ODOO_REVOLUT_SECRET_BATCH_TEST": "test-only",
        }))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        self.payments = []
        self.payloads = {}
        self.payment_ids, self.refund_ids = [], []
        self.addCleanup(self._unschedule)
        self.request.side_effect = self._http
        self._create_payments()

    def _create_payments(self):
        self.payments = []
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            for index in range(2):
                method = env["pos.payment.method"].create({
                    "name": "Revolut recovery batch test",
                    "payment_method_type": "terminal", "use_payment_terminal": "revolut",
                    "revolut_environment": "sandbox",
                    "revolut_location_id": str(uuid4()),
                    "revolut_terminal_id": str(uuid4()),
                    "revolut_fulfilment_type": "eat_in",
                    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_BATCH_TEST",
                })
                config = env["pos.config"].create({
                    "name": "Revolut recovery batch test",
                    "auto_validate_terminal_payment": True,
                    "payment_method_ids": [Command.link(method.id)],
                })
                session = env["pos.session"].create({
                    "config_id": config.id, "state": "opened",
                })
                order_uuid, line_uuid = str(uuid4()), str(uuid4())
                order_id, intent_id, payment_id = str(uuid4()), str(uuid4()), str(uuid4())
                operation = env["pos.revolut.payment.operation"].create({
                    "payment_method_id": method.id, "company_id": env.company.id,
                    "pos_config_id": config.id, "pos_session_id": session.id,
                    "order_uuid": order_uuid, "payment_line_uuid": line_uuid,
                    "amount": 12.34, "amount_minor": 1234,
                    "currency_id": config.currency_id.id,
                    "currency_code": config.currency_id.name,
                    "environment": "sandbox", "location_id": method.revolut_location_id,
                    "terminal_id": method.revolut_terminal_id, "fulfilment_type": "eat_in",
                    "secret_reference": method.revolut_secret_reference,
                    "state": "pending", "revolut_order_id": order_id,
                    "revolut_payment_intent_id": intent_id,
                    "blocking_order_key": f"{env.company.id}:{order_uuid}",
                    "blocking_terminal_key": f"sandbox:{method.revolut_terminal_id}",
                    "next_reconcile_at": self.now - timedelta(seconds=2 - index),
                })
                env["pos.revolut.payment.dispatch"].create([
                    {"operation_id": operation.id, "action": action,
                     "outcome": "succeeded", "completed_at": self.now,
                     "provider_reference": reference}
                    for action, reference in (("create_order", order_id),
                                              ("create_intent", intent_id))
                ])
                self.payments.append({
                    "id": operation.id, "method_id": method.id,
                    "session_id": session.id, "order_uuid": order_uuid,
                    "line_uuid": line_uuid, "order_id": order_id,
                    "intent_id": intent_id, "payment_id": payment_id,
                    "currency_id": config.currency_id.id,
                    "currency_code": config.currency_id.name,
                })
                self.payment_ids.append(operation.id)
                self.payloads[f"/api/payment-intents/{intent_id}"] = {
                    "id": intent_id, "order_id": order_id,
                    "state": "completed", "payment_id": payment_id,
                }
                self.payloads[f"/api/payments/{payment_id}"] = {
                    "id": payment_id, "order_id": order_id,
                    "amount": 1234, "currency": config.currency_id.name,
                    "state": "captured",
                }
            cursor.commit()

    def _unschedule(self):
        # Fixtures use real commits, so cleanup must also use a real cursor.
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.payment.operation"].browse(self.payment_ids).write({"next_reconcile_at": False})
            env["pos.revolut.refund.operation"].browse(self.refund_ids).write({"next_reconcile_at": False})
            cursor.commit()

    def _http(self, method, url, **kwargs):
        self.assertEqual(method, "GET", "Reconciliation must never replay a mutation")
        path = url[url.index("/api/"):]
        payload = self.payloads[path]
        if isinstance(payload, Exception):
            raise payload
        response = Mock()
        response.json.return_value = payload
        return response

    def _cron(self, kind="payments", batch_size=None):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            if batch_size is None:
                self.assertIs(env.ref(
                    f"pos_revolut.ir_cron_reconcile_{kind}"
                ).method_direct_trigger(), True)
            else:
                model = "payment" if kind == "payments" else "refund"
                getattr(env[f"pos.revolut.{model}.operation"],
                        f"_cron_reconcile_{kind}")(batch_size)
            cursor.commit()

    def _status(self, payment, kind="payment", user_id=SUPERUSER_ID):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, user_id, self.context)
            result = getattr(env["pos.payment.method"].browse(payment["method_id"]),
                             f"revolut_find_{kind}")(
                payment["order_uuid"], payment["line_uuid"],
            )
            cursor.commit()
            return result

    def _poll(self, payment):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = env["pos.payment.method"].browse(payment["method_id"]).revolut_poll_payment(
                payment["id"], payment["order_uuid"], payment["line_uuid"],
            )
            cursor.commit()
            return result

    def test_documented_processing_states_reach_capture_on_same_attempt(self):
        payment = self.payments[0]
        payload = self.payloads[f"/api/payments/{payment['payment_id']}"]
        for state in (
            "pending", "authentication_challenge", "authentication_verified",
            "authorisation_started", "authorisation_passed", "authorised",
            "capture_started",
        ):
            with self.subTest(state=state):
                payload["state"] = state
                result = self._poll(payment)
                self.assertEqual(result["state"], "pending")
                self.assertEqual(result["provider_state"], state)
                self.assertEqual(result["operation_id"], payment["id"])
                self.assertEqual(result["order_id"], payment["order_id"])
                self.assertEqual(result["payment_intent_id"], payment["intent_id"])
                self.assertEqual(result["payment_id"], payment["payment_id"])
                self.assertFalse(result["retry_safe"])
                self.assertEqual(self._status(payment), result)
        payload["state"] = "captured"
        result = self._poll(payment)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["operation_id"], payment["id"])
        self.assertEqual(result["payment_id"], payment["payment_id"])
        self.assertEqual(self._status(payment), result)

    def test_invalid_intent_cannot_resume_a_known_processing_payment(self):
        invalid_fields = (
            ("id", str(uuid4())), ("order_id", str(uuid4())),
            ("payment_id", str(uuid4())), ("payment_id", False),
            ("state", "unknown_provider_state"), ("state", []),
        )
        for index, (field, value) in enumerate(invalid_fields):
            with self.subTest(field=field, value=value):
                if index:
                    self._create_payments()
                payment = self.payments[0]
                self.payloads[f"/api/payments/{payment['payment_id']}"]["state"] = "pending"
                self.assertEqual(self._poll(payment)["state"], "pending")
                path = f"/api/payment-intents/{payment['intent_id']}"
                original = dict(self.payloads[path])
                self.payloads[path][field] = value
                calls = self.request.call_count

                result = self._poll(payment)

                self.assertEqual(result["state"], "unresolved")
                self.assertFalse(result["retry_safe"])
                self.assertEqual(result["payment_id"], payment["payment_id"])
                self.assertEqual(self.request.call_count, calls + 1)
                self._assert_blocked(payment)
                self.payloads[path] = original
                self.payloads[f"/api/payments/{payment['payment_id']}"]["state"] = "captured"
                self.assertEqual(self._poll(payment)["state"], "verified")

    def test_processing_payment_requires_exact_identity_amount_currency_and_state(self):
        invalid_fields = (
            ("id", str(uuid4())), ("order_id", str(uuid4())),
            ("amount", 1235), ("amount", 1234.0), ("amount", "1234"),
            ("amount", True), ("amount", None),
            ("currency", "ZZZ"), ("currency", None),
            ("state", "processing"), ("state", "unknown_provider_state"),
            ("state", []), ("state", None),
        )
        for index, (field, value) in enumerate(invalid_fields):
            with self.subTest(field=field, value=value):
                if index:
                    self._create_payments()
                payment = self.payments[0]
                path = f"/api/payments/{payment['payment_id']}"
                self.payloads[path]["state"] = "authentication_verified"
                self.payloads[path][field] = value

                result = self._poll(payment)

                self.assertEqual(result["state"], "unresolved")
                self.assertFalse(result["retry_safe"])
                self._assert_blocked(payment)

    def test_processing_observation_rejects_another_order_or_payment_line(self):
        payment = self.payments[0]
        self.payloads[f"/api/payments/{payment['payment_id']}"]["state"] = "pending"
        for field in ("id", "order_uuid", "line_uuid"):
            with self.subTest(field=field):
                wrong = {**payment, field: self.payments[1]["id"] if field == "id" else str(uuid4())}
                with self.assertRaises(AccessError):
                    self._poll(wrong)
        self.request.assert_not_called()
        self.assertEqual(self._poll(payment)["state"], "pending")

    def test_processing_payment_can_reach_each_unsuccessful_final_state(self):
        for index, (intermediate, final) in enumerate((
            ("declining", "declined"), ("failing", "failed"), ("cancelling", "cancelled"),
        )):
            with self.subTest(final=final):
                if index:
                    self._create_payments()
                payment = self.payments[0]
                payload = self.payloads[f"/api/payments/{payment['payment_id']}"]
                for state in ("authorisation_started", intermediate):
                    payload["state"] = state
                    result = self._poll(payment)
                    self.assertEqual(result["state"], "pending")
                    self.assertFalse(result["retry_safe"])
                payload["state"] = final
                result = self._poll(payment)
                self.assertEqual(result["state"], final)
                self.assertTrue(result["retry_safe"])
                self.assertEqual(result["operation_id"], payment["id"])
                self.assertEqual(result["payment_id"], payment["payment_id"])
                self.assertEqual(self._status(payment), result)

    def test_processing_timeout_keeps_claims_and_later_reconciles_capture(self):
        payment = self.payments[0]
        payload = self.payloads[f"/api/payments/{payment['payment_id']}"]
        payload["state"] = "authentication_challenge"
        self.assertEqual(self._poll(payment)["state"], "pending")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = env["pos.payment.method"].browse(payment["method_id"]).revolut_mark_timeout(
                payment["id"], payment["order_uuid"], payment["line_uuid"],
            )
            cursor.commit()
        self.assertEqual(result["state"], "unresolved")
        self.assertEqual(result["local_outcome"], "timed_out")
        self.assertEqual(result["payment_id"], payment["payment_id"])
        self._assert_blocked(payment, delay=30)

        payload["state"] = "completed"
        self.now += timedelta(seconds=30)
        self.clock.return_value = self.now
        self._cron()

        result = self._status(payment)
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["operation_id"], payment["id"])
        self.assertEqual(result["payment_id"], payment["payment_id"])
        self.assertFalse(result["local_outcome"])

    def _assert_blocked(self, payment, delay=300):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.payment.operation"].browse(payment["id"])
            self.assertEqual(operation.state, "unresolved")
            self.assertFalse(operation.retry_safe)
            self.assertFalse(operation.verified_at)
            self.assertTrue(operation.blocking_order_key)
            self.assertTrue(operation.blocking_terminal_key)
            self.assertTrue(operation.deployment_blocking)
            self.assertEqual(operation.revolut_order_id, payment["order_id"])
            self.assertEqual(operation.revolut_payment_intent_id, payment["intent_id"])
            self.assertEqual(operation.next_reconcile_at, self.now + timedelta(seconds=delay))
            self.assertEqual(env["pos.revolut.payment.dispatch"].search_count([
                ("operation_id", "=", operation.id), ("outcome", "=", "succeeded"),
            ]), 2)
            self.assertFalse(operation.pos_order_id)

    def test_malformed_intent_does_not_block_later_payment(self):
        first, healthy = self.payments
        self.payloads[f"/api/payment-intents/{first['intent_id']}"]["state"] = []

        self._cron()

        self._assert_blocked(first)
        self.assertEqual(self._status(healthy)["state"], "verified")
        self.assertEqual(self._status(healthy)["payment_id"], healthy["payment_id"])
        requests_before = self.request.call_count
        self._cron()
        self.assertEqual(self.request.call_count, requests_before)

    def _make_refunds(self):
        refunds = []
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            for payment in self.payments:
                original = env["pos.revolut.payment.operation"].browse(payment["id"])
                original.write({
                    "state": "verified", "revolut_payment_id": payment["payment_id"],
                    "blocking_order_key": False, "blocking_terminal_key": False,
                    "next_reconcile_at": False,
                })
                reference = str(uuid4())
                operation = env["pos.revolut.refund.operation"].create({
                    "original_operation_id": original.id,
                    "pos_session_id": payment["session_id"],
                    "order_uuid": str(uuid4()), "payment_line_uuid": str(uuid4()),
                    "amount": 12.34, "amount_minor": 1234,
                    "currency_id": payment["currency_id"],
                    "financial_snapshot": {"lines": []},
                    "state": "pending", "revolut_order_id": reference,
                    "next_reconcile_at": self.now - timedelta(seconds=2 - len(refunds)),
                })
                refunds.append({
                    **payment, "id": operation.id,
                    "original_id": original.id, "refund_id": reference,
                    "order_uuid": operation.order_uuid,
                    "line_uuid": operation.payment_line_uuid,
                    "idempotency_key": operation.idempotency_key,
                    "dispatched_at": operation.dispatched_at,
                })
                self.refund_ids.append(operation.id)
                self.payloads[f"/api/orders/{reference}"] = {
                    "id": reference, "type": "refund", "related_order_id": payment["order_id"],
                    "amount": 1234, "currency": payment["currency_code"],
                    "state": "completed",
                }
            cursor.commit()
        return refunds

    def _assert_refund_reserved(self, refund, delay=300):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.refund.operation"].browse(refund["id"])
            self.assertEqual(operation.state, "unresolved")
            self.assertFalse(operation.verified_at)
            self.assertTrue(operation.deployment_blocking)
            self.assertEqual(operation.revolut_order_id, refund["refund_id"])
            self.assertEqual(operation.idempotency_key, refund["idempotency_key"])
            self.assertEqual(operation.dispatched_at, refund["dispatched_at"])
            self.assertEqual(operation.next_reconcile_at, self.now + timedelta(seconds=delay))
            reservations = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", refund["original_id"]),
                ("state", "!=", "failed"),
            ])
            self.assertEqual(reservations.ids, [refund["id"]])
            self.assertEqual(sum(reservations.mapped("amount_minor")), 1234)
            self.assertFalse(operation.pos_order_id)

    def test_malformed_refund_does_not_block_later_refund(self):
        first, healthy = self._make_refunds()
        self.payloads[f"/api/orders/{first['refund_id']}"]["state"] = {}

        self._cron("refunds")

        self._assert_refund_reserved(first)
        self.assertEqual(self._status(healthy, "refund")["state"], "verified")
        requests_before = self.request.call_count
        self._cron("refunds")
        self.assertEqual(self.request.call_count, requests_before)

    def test_exhausted_payment_conflicts_reschedule_and_continue(self):
        first, healthy = self.payments
        model = type(self.env["pos.revolut.payment.operation"])
        apply = model._apply_payment_observation
        failures = []

        def conflicting(operation, kind, evidence=None):
            if operation.id == first["id"] and kind == "payment":
                failures.append(operation.env.cr)
                # A real database error aborts this owned transaction.
                operation.env.cr.execute(
                    "DO $$ BEGIN RAISE EXCEPTION USING ERRCODE = '40001', "
                    "MESSAGE = 'test evidence conflict'; END $$"
                )
            return apply(operation, kind, evidence)

        with patch.object(model, "_apply_payment_observation", conflicting), mute_logger("odoo.sql_db"):
            self._cron()

        self._assert_blocked(first, delay=60)
        self.assertEqual(self._status(first)["payment_id"], first["payment_id"])
        self.assertEqual(len(failures), 3)
        self.assertTrue(all(cursor.closed for cursor in failures))
        self.assertEqual(self._status(healthy)["state"], "verified")
        # The fresh intent observation was committed before the conflict;
        # recovery must read the same payment, without redispatching.
        self.now += timedelta(seconds=60)
        self.clock.return_value = self.now
        self._cron()
        self.assertEqual(self._status(first)["state"], "verified")

    def _check_payment_shapes(self, stage):
        for index, state in enumerate(([], {}, None, "unknown_provider_state", False, 7)):
            with self.subTest(stage=stage, state=state):
                if index:
                    self._create_payments()
                first, healthy = self.payments
                path = (f"/api/payment-intents/{first['intent_id']}" if stage == "intent"
                        else f"/api/payments/{first['payment_id']}")
                original = dict(self.payloads[path])
                if state is None:
                    self.payloads[path].pop("state")
                else:
                    self.payloads[path]["state"] = state
                self._cron()
                self._assert_blocked(first)
                self.assertEqual(self._status(healthy)["state"], "verified")
                if stage == "payment":
                    self.assertEqual(self._status(first)["payment_id"], first["payment_id"])
                calls = self.request.call_count
                self._cron(batch_size=1)
                self.assertEqual(self.request.call_count, calls)
                self.now += timedelta(seconds=300)
                self.clock.return_value = self.now
                self._cron(batch_size=1)
                self._assert_blocked(first)
                self.payloads[path] = original
                self.now += timedelta(seconds=300)
                self.clock.return_value = self.now
                self._cron()
                result = self._status(first)
                self.assertEqual(result["state"], "verified")
                self.assertEqual(result["operation_id"], first["id"])
                self.assertEqual(result["payment_id"], first["payment_id"])

    def test_intent_shapes_back_off_and_recover_without_dispatch(self):
        self._check_payment_shapes("intent")

    def test_underlying_payment_shapes_back_off_and_recover_without_dispatch(self):
        self._check_payment_shapes("payment")

    def test_refund_shapes_back_off_and_recover_without_dispatch(self):
        for index, state in enumerate(([], {}, None, "unknown_provider_state", False, 7)):
            with self.subTest(state=state):
                if index:
                    self._create_payments()
                first, healthy = self._make_refunds()
                path = f"/api/orders/{first['refund_id']}"
                original = dict(self.payloads[path])
                if state is None:
                    self.payloads[path].pop("state")
                else:
                    self.payloads[path]["state"] = state
                self._cron("refunds")
                self._assert_refund_reserved(first)
                self.assertEqual(self._status(healthy, "refund")["state"], "verified")
                calls = self.request.call_count
                self._cron("refunds", batch_size=1)
                self.assertEqual(self.request.call_count, calls)
                self.now += timedelta(seconds=300)
                self.clock.return_value = self.now
                self._cron("refunds", batch_size=1)
                self._assert_refund_reserved(first)
                self.payloads[path] = original
                self.now += timedelta(seconds=300)
                self.clock.return_value = self.now
                self._cron("refunds")
                result = self._status(first, "refund")
                self.assertEqual(result["state"], "verified")
                self.assertEqual(result["operation_id"], first["id"])
                self.assertEqual(result["payment_id"], first["refund_id"])

    def test_payment_parser_failure_rolls_back_only_current_observation(self):
        first, healthy = self.payments
        model = type(self.env["pos.revolut.payment.operation"])
        apply = model._apply_payment_observation
        failed_cursors = []

        def malformed(operation, kind, evidence=None):
            if operation.id == first["id"] and kind == "payment":
                failed_cursors.append(operation.env.cr)
                operation.env.cr.execute(
                    "UPDATE pos_revolut_payment_operation SET provider_state = 'rollback_marker' WHERE id = %s",
                    [operation.id],
                )
                raise ValueError("test-only sensitive provider payload")
            return apply(operation, kind, evidence)

        with patch.object(model, "_apply_payment_observation", malformed):
            self._cron()
        self._assert_blocked(first)
        self.assertTrue(all(cursor.closed for cursor in failed_cursors))
        result = self._status(first)
        self.assertEqual(result["payment_id"], first["payment_id"])
        self.assertEqual(result["provider_state"], "completed")
        self.assertEqual(self._status(healthy)["state"], "verified")

    def test_refund_parser_failure_rolls_back_only_current_observation(self):
        first, healthy = self._make_refunds()
        model = type(self.env["pos.revolut.refund.operation"])
        snapshot = model._snapshot
        failed_cursors = []

        def malformed(operation):
            if operation.id == first["id"] and operation.state == "verified":
                failed_cursors.append(operation.env.cr)
                operation.env.cr.execute(
                    "UPDATE pos_revolut_refund_operation SET provider_state = 'rollback_marker' WHERE id = %s",
                    [operation.id],
                )
                raise ValueError("test-only sensitive provider payload")
            return snapshot(operation)

        with patch.object(model, "_snapshot", malformed):
            self._cron("refunds")
        self._assert_refund_reserved(first)
        self.assertTrue(all(cursor.closed for cursor in failed_cursors))
        self.assertFalse(self._status(first, "refund")["provider_state"])
        self.assertEqual(self._status(healthy, "refund")["state"], "verified")

    def test_exhausted_refund_deadlocks_reschedule_and_continue(self):
        first, healthy = self._make_refunds()
        model = type(self.env["pos.revolut.refund.operation"])
        snapshot = model._snapshot
        failures = []

        def conflicting(operation):
            if operation.id == first["id"] and operation.state == "verified":
                failures.append(operation.env.cr)
                operation.env.cr.execute(
                    "DO $$ BEGIN RAISE EXCEPTION USING ERRCODE = '40P01', "
                    "MESSAGE = 'test evidence conflict'; END $$"
                )
            return snapshot(operation)

        with patch.object(model, "_snapshot", conflicting), mute_logger("odoo.sql_db"):
            self._cron("refunds")
        self._assert_refund_reserved(first, delay=60)
        self.assertEqual(len(failures), 3)
        self.assertTrue(all(cursor.closed for cursor in failures))
        self.assertEqual(self._status(healthy, "refund")["state"], "verified")
        self.now += timedelta(seconds=60)
        self.clock.return_value = self.now
        self._cron("refunds")
        self.assertEqual(self._status(first, "refund")["state"], "verified")

    def test_unexpected_database_failure_is_not_suppressed(self):
        first, healthy = self.payments
        model = type(self.env["pos.revolut.payment.operation"])
        apply = model._apply_payment_observation

        def broken(operation, kind, evidence=None):
            if operation.id == first["id"] and kind == "payment":
                operation.env.cr.execute(
                    "DO $$ BEGIN RAISE EXCEPTION USING ERRCODE = '23505', "
                    "MESSAGE = 'test unexpected constraint failure'; END $$"
                )
            return apply(operation, kind, evidence)

        with patch.object(model, "_apply_payment_observation", broken), mute_logger("odoo.sql_db"):
            with self.assertRaises(UniqueViolation):
                self._cron(batch_size=2)
        self.assertEqual(self._status(first)["payment_id"], first["payment_id"])
        self.assertEqual(self._status(healthy)["state"], "pending")

    def test_underlying_network_failures_back_off_to_thirty_minutes(self):
        first, healthy = self.payments
        path = f"/api/payments/{first['payment_id']}"
        original = self.payloads[path]
        self.payloads[path] = requests.ConnectionError("test-only sensitive transport detail")
        for delay in (60, 120, 240, 480, 960, 1800, 1800):
            self._cron()
            self._assert_blocked(first, delay=delay)
            self.assertEqual(self._status(healthy)["state"], "verified")
            self.now += timedelta(seconds=delay)
            self.clock.return_value = self.now
        self.payloads[path] = original
        self._cron()
        self.assertEqual(self._status(first)["state"], "verified")

    def test_refund_network_failures_back_off_to_thirty_minutes(self):
        first, healthy = self._make_refunds()
        path = f"/api/orders/{first['refund_id']}"
        original = self.payloads[path]
        self.payloads[path] = requests.ConnectionError("test-only sensitive transport detail")
        for delay in (60, 120, 240, 480, 960, 1800, 1800):
            self._cron("refunds")
            self._assert_refund_reserved(first, delay=delay)
            self.assertEqual(self._status(healthy, "refund")["state"], "verified")
            self.now += timedelta(seconds=delay)
            self.clock.return_value = self.now
        self.payloads[path] = original
        self._cron("refunds")
        self.assertEqual(self._status(first, "refund")["state"], "verified")

    def test_cashier_and_manager_checks_keep_malformed_payment_unresolved(self):
        first = self.payments[0]
        self.payloads[f"/api/payment-intents/{first['intent_id']}"]["state"] = {
            "secret": "test-only sensitive provider payload",
        }
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            cashier = new_test_user(
                env, login=f"batch_cashier_{uuid4()}",
                groups="base.group_user,point_of_sale.group_pos_user",
                company_id=env.company.id, company_ids=[Command.set(env.companies.ids)],
            )
            manager = new_test_user(
                env, login=f"batch_manager_{uuid4()}",
                groups="base.group_user,point_of_sale.group_pos_manager",
                company_id=env.company.id, company_ids=[Command.set(env.companies.ids)],
            )
            cashier_id, manager_id = cashier.id, manager.id
            cursor.commit()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, cashier_id, self.context)
            result = env["pos.payment.method"].browse(first["method_id"]).revolut_poll_payment(
                first["id"], first["order_uuid"], first["line_uuid"],
            )
            cursor.commit()
        self.assertEqual(result["state"], "unresolved")
        self.assertNotIn("sensitive", repr(result))
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, manager_id, self.context)
            env["pos.revolut.payment.operation"].browse(first["id"]).action_revolut_reconcile()
            cursor.commit()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, manager_id, self.context)
            operation = env["pos.revolut.payment.operation"].browse(first["id"])
            self.assertEqual(operation.audit_ids.actor_id.id, manager_id)
            self.assertEqual(operation.audit_ids.resulting_state, "unresolved")
            self.assertTrue(operation.sanitized_error)
            self.assertIn("Keep the order blocked", operation.support_explanation)
            self.assertNotIn("sensitive", operation.sanitized_error + operation.support_explanation)
        self._assert_blocked(first)

    def test_malformed_intent_payment_references_never_unlock_retry(self):
        for index, reference in enumerate(([], {}, False, 7)):
            with self.subTest(reference=reference):
                if index:
                    self._create_payments()
                first, healthy = self.payments
                path = f"/api/payment-intents/{first['intent_id']}"
                original = dict(self.payloads[path])
                self.payloads[path].update(state="cancelled", payment_id=reference)
                self._cron()
                self._assert_blocked(first)
                self.assertEqual(self._status(healthy)["state"], "verified")
                self.payloads[path] = original
                self.now += timedelta(seconds=300)
                self.clock.return_value = self.now
                self._cron()
                self.assertEqual(self._status(first)["state"], "verified")

    def test_manager_refund_check_reports_sanitized_unresolved_status(self):
        first, healthy = self._make_refunds()
        self.payloads[f"/api/orders/{first['refund_id']}"]["state"] = {
            "secret": "test-only sensitive provider payload",
        }
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            manager = new_test_user(
                env, login=f"refund_batch_manager_{uuid4()}",
                groups="base.group_user,point_of_sale.group_pos_manager",
                company_id=env.company.id, company_ids=[Command.set(env.companies.ids)],
            )
            manager_id = manager.id
            cursor.commit()
        with self.assertLogs("odoo.addons.pos_revolut.models", level="WARNING") as logs:
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, manager_id, self.context)
                result = env["pos.revolut.refund.operation"].browse(first["id"]).action_check_status()
                cursor.commit()
        self.assertEqual(result["tag"], "reload")
        self.assertNotIn("sensitive", " ".join(logs.output))
        self.assertNotIn("test-only", " ".join(logs.output))
        self.assertEqual(self._status(first, "refund", user_id=manager_id)["state"], "unresolved")
        self._assert_refund_reserved(first)
        self._cron("refunds")
        self.assertEqual(self._status(healthy, "refund")["state"], "verified")

    def test_payment_cron_respects_batch_limit(self):
        first, later = self.payments
        self._cron(batch_size=1)
        self.assertEqual(self._status(first)["state"], "verified")
        self.assertEqual(self._status(later)["state"], "pending")
        self._cron()
        self.assertEqual(self._status(later)["state"], "verified")

    def test_refund_cron_respects_batch_limit(self):
        first, later = self._make_refunds()
        self._cron("refunds", batch_size=1)
        self.assertEqual(self._status(first, "refund")["state"], "verified")
        self.assertEqual(self._status(later, "refund")["state"], "pending")
        self._cron("refunds")
        self.assertEqual(self._status(later, "refund")["state"], "verified")

    def test_malformed_payment_after_transport_failure_waits_five_minutes(self):
        first, healthy = self.payments
        path = f"/api/payments/{first['payment_id']}"
        original = self.payloads[path]
        self.payloads[path] = requests.ConnectionError("test-only sensitive transport detail")
        self._cron()
        self._assert_blocked(first, delay=60)
        self.assertEqual(self._status(healthy)["state"], "verified")

        self.now += timedelta(seconds=60)
        self.clock.return_value = self.now
        self.payloads[path] = {**original, "state": {}}
        self._cron()
        self._assert_blocked(first, delay=300)

        self.now += timedelta(seconds=300)
        self.clock.return_value = self.now
        self.payloads[path] = original
        self._cron()
        self.assertEqual(self._status(first)["state"], "verified")

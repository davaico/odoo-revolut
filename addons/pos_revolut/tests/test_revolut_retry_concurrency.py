"""Exercise public RPCs with real, independently committed transactions."""

import os
from threading import Barrier, Event, RLock, Thread, current_thread
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import SUPERUSER_ID, Command, api
from odoo.exceptions import UserError
from odoo.orm.registry import Registry
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestRevolutRetryConcurrency(TransactionCase):
    def setUp(self):
        super().setUp()
        self.registry = self.env.registry
        self.context = {"allowed_company_ids": [self.env.company.id]}
        self.order_uuid, self.line_uuid = str(uuid4()), str(uuid4())
        self.location_id, self.terminal_id = str(uuid4()), str(uuid4())
        self.provider_order, self.provider_intent = str(uuid4()), str(uuid4())
        self.provider_payment = str(uuid4())
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            method = env["pos.payment.method"].create({
                "name": "Revolut retry concurrency test",
                "payment_method_type": "terminal",
                "use_payment_terminal": "revolut",
                "revolut_environment": "sandbox",
                "revolut_location_id": self.location_id,
                "revolut_terminal_id": self.terminal_id,
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_RETRY_RACE_TEST",
            })
            config = env["pos.config"].create({
                "name": "Revolut retry concurrency test",
                "payment_method_ids": [Command.link(method.id)],
                "auto_validate_terminal_payment": True,
            })
            session = env["pos.session"].create({
                "config_id": config.id, "state": "opened",
            })
            self.method_id, self.session_id = method.id, session.id
            self.currency_id, self.currency_code = config.currency_id.id, config.currency_id.name
            cursor.commit()
        self.enterContext(patch.dict(os.environ, {
            "ODOO_REVOLUT_SECRET_RETRY_RACE_TEST": "test-only",
        }))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))

    def _rpc(self, name, *args):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = getattr(env["pos.payment.method"].browse(self.method_id), name)(*args)
            cursor.commit()
            return result

    def _start(self, previous_operation_id=None):
        snapshot = {
            "pricelist_id": 0,
            "fiscal_position_id": False,
            "lines": [{
                "uuid": self.order_uuid, "product_id": 1,
                "qty": 1, "price_unit": 12.34, "discount": 0,
                "tax_ids": [],
            }],
        }
        return self._rpc(
            "revolut_start_payment", self.session_id, self.order_uuid,
            self.line_uuid, 12.34, self.currency_id,
            previous_operation_id or False, snapshot,
        )

    @staticmethod
    def _response(payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _start_http(self, method, url, **kwargs):
        if method == "GET" and url.endswith("/api/terminals"):
            return self._response({"terminals": [{
                "id": self.terminal_id, "online": True,
                "operation_mode": "pos", "location_id": self.location_id,
            }]})
        if method == "POST" and url.endswith("/api/orders"):
            return self._response({"id": self.provider_order})
        if method == "POST" and url.endswith("/payment-intents"):
            return self._response({"id": self.provider_intent, "state": "pending"})
        raise AssertionError(f"Unexpected HTTP request: {method} {url}")

    def _intent(self, state, **extra):
        return self._response({"id": self.provider_intent,
                               "order_id": self.provider_order,
                               "state": state, **extra})

    def _run_workers(self, tasks):
        errors, results = [], []

        def run(task):
            try:
                results.append(task())
            except Exception as error:  # Propagate failures from worker threads.
                errors.append(error)

        workers = [Thread(target=run, args=(task,), name=name, daemon=True)
                   for name, task in tasks]
        # The test server holds Registry._lock throughout preload, including
        # post-install tests. Let worker Environments find the already-loaded
        # registry without replacing real database cursors with TestCursors.
        with patch.object(Registry, "_lock", RLock()), mute_logger("odoo.sql_db"):
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=20)
        self.assertFalse(any(worker.is_alive() for worker in workers), "RPC worker deadlocked")
        self.assertFalse(errors, repr(errors))
        return results

    def test_scheduled_stale_poll_cannot_regress_foreground_success(self):
        self.request.side_effect = self._start_http
        started = self._start()
        # The upgrade run can retain older committed attempts. Make this one
        # the oldest due item and exercise a single-item scheduled batch.
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.payment.operation"].browse(
                started["operation_id"]
            ).write({"next_reconcile_at": "2000-01-01 00:00:00"})
            cursor.commit()
        background_read, foreground_verified = Event(), Event()

        def http(method, url, **kwargs):
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                if current_thread().name == "background":
                    background_read.set()
                    self.assertTrue(foreground_verified.wait(10))
                    return self._intent("pending")
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code,
                    "state": "captured",
                })
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        def background():
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                env["pos.revolut.payment.operation"]._cron_reconcile_payments(1)
                cursor.commit()

        def foreground():
            self.assertTrue(background_read.wait(10))
            try:
                result = self._rpc(
                    "revolut_poll_payment", started["operation_id"],
                    self.order_uuid, self.line_uuid,
                )
                self.assertEqual(result["state"], "verified")
            finally:
                foreground_verified.set()

        self.request.reset_mock()
        self.request.side_effect = http
        self._run_workers([("background", background), ("foreground", foreground)])
        recovered = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], self.provider_payment)
        self.assertFalse([call for call in self.request.call_args_list
                          if call.args[0] == "POST"])

    def test_simultaneous_safe_retries_create_one_replacement(self):
        self.request.side_effect = self._start_http
        first = self._start()
        self.request.side_effect = lambda *args, **kwargs: self._intent("cancelled")
        failed = self._rpc("revolut_poll_payment", first["operation_id"],
                           self.order_uuid, self.line_uuid)
        self.assertTrue(failed["retry_safe"])
        self.provider_order, self.provider_intent = str(uuid4()), str(uuid4())
        self.request.reset_mock()
        barrier, replay_finished = Barrier(2), Event()

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                self.assertTrue(replay_finished.wait(10), "Competing retry did not return")
            return self._start_http(method, url, **kwargs)

        def retry():
            barrier.wait(timeout=10)
            try:
                return self._start(first["operation_id"])
            finally:
                replay_finished.set()

        self.request.side_effect = http
        results = self._run_workers([("retry-one", retry), ("retry-two", retry)])
        self.assertEqual(len({result["operation_id"] for result in results}), 1)
        self.assertNotEqual(results[0]["operation_id"], first["operation_id"])
        posts = [call for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(len(posts), 2, "Only one order and one intent may be dispatched")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            attempts = env["pos.revolut.payment.operation"].search([
                ("payment_method_id", "=", self.method_id),
                ("order_uuid", "=", self.order_uuid),
                ("payment_line_uuid", "=", self.line_uuid),
            ])
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts.browse(first["operation_id"]).state, "cancelled")

    def test_stale_cancel_reconciliation_cannot_downgrade_success(self):
        self.request.side_effect = self._start_http
        started = self._start()
        args = (started["operation_id"], self.order_uuid, self.line_uuid)
        cancellation_sent, stale_read_started, verified = Event(), Event(), Event()
        self.request.reset_mock()

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith("/cancel"):
                cancellation_sent.set()
                return self._response({})
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                if current_thread().name == "cancel":
                    if not cancellation_sent.is_set():
                        return self._intent("pending")
                    stale_read_started.set()
                    self.assertTrue(verified.wait(10), "Concurrent success was not persisted")
                    return self._intent("cancelled")
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code, "state": "completed",
                })
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        def poll():
            self.assertTrue(stale_read_started.wait(10), "Cancellation did not reach reconciliation")
            try:
                result = self._rpc("revolut_poll_payment", *args)
                self.assertEqual(result["state"], "verified")
                return result
            finally:
                verified.set()

        self.request.side_effect = http
        results = self._run_workers([
            ("cancel", lambda: self._rpc("revolut_cancel_payment", *args)),
            ("poll", poll),
        ])
        self.assertEqual([result["state"] for result in results], ["verified", "verified"])
        repeated = self._rpc("revolut_cancel_payment", *args)
        self.assertEqual(repeated["state"], "verified")
        self.assertFalse(repeated["retry_safe"])
        posts = [call for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(len(posts), 1)

    def test_cancel_cannot_release_attempt_while_payment_verification_is_pending(self):
        self.request.side_effect = self._start_http
        started = self._start()
        args = (started["operation_id"], self.order_uuid, self.line_uuid)
        cancellation_sent = Event()
        cancel_reconciliation_started = Event()
        payment_verification_started = Event()
        cancellation_reconciled = Event()
        self.request.reset_mock()

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith("/cancel"):
                cancellation_sent.set()
                return self._response({})
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                if current_thread().name == "cancel":
                    if not cancellation_sent.is_set():
                        return self._intent("pending")
                    cancel_reconciliation_started.set()
                    self.assertTrue(payment_verification_started.wait(10))
                    # This stale response omits a payment reference already
                    # persisted by the other request before its payment GET.
                    return self._intent("cancelled")
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                payment_verification_started.set()
                self.assertTrue(cancellation_reconciled.wait(10))
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code, "state": "completed",
                })
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        def cancel():
            try:
                result = self._rpc("revolut_cancel_payment", *args)
                self.assertFalse(result["retry_safe"], "Payment verification still pending")
                with self.assertRaises(UserError):
                    self._start(started["operation_id"])
                return result
            finally:
                cancellation_reconciled.set()

        def poll():
            self.assertTrue(cancel_reconciliation_started.wait(10))
            result = self._rpc("revolut_poll_payment", *args)
            self.assertEqual(result["state"], "verified")
            return result

        self.request.side_effect = http
        self._run_workers([("cancel", cancel), ("poll", poll)])
        final = self._rpc("revolut_poll_payment", *args)
        self.assertEqual(final["state"], "verified")
        self.assertFalse(final["retry_safe"])
        posts = [call for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(len(posts), 1, "Unsafe retry must dispatch no new payment")

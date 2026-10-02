"""Exercise public RPCs with real, independently committed transactions."""

import json
import os
from datetime import datetime, timedelta
from threading import Barrier, Event, RLock, Thread, current_thread
from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from odoo import SUPERUSER_ID, Command, api
from odoo.exceptions import UserError
from odoo.orm.registry import Registry
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

from .authorization_fixtures import financial_posts, install_zero_reports, native_products, prepare_fixture


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
            self.product_id = native_products(env, config).id
            session = env["pos.session"].create({
                "config_id": config.id, "state": "opened",
            })
            self.method_id, self.session_id = method.id, session.id
            self.currency_id, self.currency_code = config.currency_id.id, config.currency_id.name
            cursor.commit()
        self.enterContext(patch.dict(os.environ, {
            "ODOO_REVOLUT_SECRET_RETRY_RACE_TEST": "test-only",
        }))
        self._retry_observation_time = datetime(2026, 10, 2, 12)
        self.enterContext(patch(
            "odoo.addons.pos_revolut.models.payment_observation.observation_now",
            side_effect=lambda: self._retry_observation_time,
        ))
        self.authorities = {}
        self._prepare(self.order_uuid, self.line_uuid)
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))

    def _advance_observation(self, seconds):
        self._retry_observation_time += timedelta(seconds=seconds)

    def _rpc(self, name, *args, user_id=SUPERUSER_ID):
        # New cadence-specific tests reuse this fixture without opting into
        # the legacy class's one-second separation of sequential observations.
        if hasattr(self, "_retry_observation_time") and name in {
            "revolut_poll_payment", "revolut_cancel_payment",
        }:
            self._retry_observation_time += timedelta(seconds=1)
        install_zero_reports(self.env, self.request)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, user_id, self.context)
            result = getattr(env["pos.payment.method"].browse(self.method_id), name)(*args)
            cursor.commit()
            return result

    def _manager_rpc(self, operation_id, name, *args):
        if hasattr(self, "_retry_observation_time"):
            self._retry_observation_time += timedelta(seconds=1)
        install_zero_reports(self.env, self.request)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = getattr(
                env["pos.revolut.payment.operation"].browse(operation_id), name
            )(*args)
            cursor.commit()
            return result

    def _manager_order(self):
        return self._response({
            "id": self.provider_order, "amount": 1234,
            "currency": self.currency_code, "location_id": self.location_id,
            "metadata": {"pos_order_uuid": self.order_uuid,
                         "pos_payment_line_uuid": self.line_uuid},
        })

    def _manager_intent(self):
        return self._response({
            "id": self.provider_intent, "order_id": self.provider_order,
            "amount": 1234, "currency": self.currency_code,
            "terminal_id": self.terminal_id, "state": "pending",
        })

    def _prepare(self, order_uuid, line_uuid):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            self.authorities[(order_uuid, line_uuid)] = prepare_fixture(
                env["pos.payment.method"].browse(self.method_id), self.session_id,
                order_uuid, line_uuid, 12.34, {
                    "pricelist_id": 0, "fiscal_position_id": False,
                    "lines": [{"uuid": order_uuid, "product_id": self.product_id,
                               "qty": 1, "price_unit": 12.34, "discount": 0, "tax_ids": []}],
                }, commit_draft=True,
            )
            cursor.commit()

    def _start(self, previous_operation_id=None, user_id=SUPERUSER_ID,
               *, order_uuid=None, line_uuid=None):
        order_uuid, line_uuid = order_uuid or self.order_uuid, line_uuid or self.line_uuid
        authority = self.authorities[(order_uuid, line_uuid)]
        install_zero_reports(self.env, self.request)
        return self._rpc(
            "revolut_start_payment", self.session_id, order_uuid, line_uuid,
            12.34, self.currency_id, previous_operation_id or False, False,
            authority["authorization_id"], authority["cart_version"], authority["tender_revision"],
            user_id=user_id,
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

    def _bounded_status_reads(self, outcome, *, overlap=False):
        """Characterize three callers, never an exhaustion or live HTTP test."""
        self.request.side_effect = self._start_http
        started = self._start()
        args = (started["operation_id"], self.order_uuid, self.line_uuid)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            cashier = new_test_user(
                env, login=f"poll_cashier_{uuid4().hex}",
                groups="point_of_sale.group_pos_user", company_id=env.company.id,
            )
            cashier_id = cashier.id
            env["pos.session"].browse(self.session_id).config_id.write({
                "revolut_user_ids": [Command.link(cashier.id)],
            })
            env["pos.revolut.payment.operation"].browse(args[0]).write({
                "next_reconcile_at": "2000-01-01 00:00:00",
            })
            cursor.commit()

        held, release, count_lock = Event(), Event(), RLock()
        finished = [Event(), Event()]
        counts = {"active": 0, "intent_reads": 0, "peak": 0, "blocked_callers": 0}

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith(f"/api/payment-intents/{self.provider_intent}"))
            with count_lock:
                counts["intent_reads"] += 1
                counts["active"] += 1
                counts["peak"] = max(counts["peak"], counts["active"])
            held.set()
            try:
                self.assertTrue(release.wait(10), "Provider fixture was not released")
                if outcome == "timeout":
                    raise requests.Timeout()
                if outcome == "http_error":
                    raise requests.HTTPError(response=Mock(status_code=503))
                if outcome == "malformed":
                    return self._response({"id": self.provider_intent, "state": "unexpected"})
                return self._intent("pending")
            finally:
                with count_lock:
                    counts["active"] -= 1

        def cron():
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                env["pos.revolut.payment.operation"]._cron_reconcile_payments(1)
                cursor.commit()

        def duplicate(index):
            self.assertTrue(held.wait(10), "Winner did not enter the provider")
            try:
                if overlap and index == 1:
                    cron()
                    return
                result = self._rpc(
                    "revolut_cancel_payment" if overlap else "revolut_poll_payment",
                    *args, user_id=cashier_id,
                )
                self.assertTrue(result["observation_in_progress"])
                self.assertFalse(result["observation_fresh"])
                self.assertFalse(result["retry_safe"])
                self.assertGreater(result["next_check_seconds"], 0)
                self.assertLessEqual(result["next_check_seconds"], 60)
                return result
            finally:
                finished[index].set()

        def observer():
            try:
                self.assertTrue(held.wait(10))
                # Neither a second browser, cancellation precheck nor cron
                # waits for the provider or sends another external request.
                for event in finished:
                    self.assertTrue(event.wait(2), "Duplicate caller did not return promptly")
                with count_lock:
                    self.assertEqual(counts["intent_reads"], 1)
                    self.assertEqual(counts["active"], 1)
                    counts["blocked_callers"] = counts["active"]
                self.assertFalse(financial_posts(self.request))
            finally:
                release.set()

        self.request.reset_mock()
        self.request.side_effect = http
        install_zero_reports(self.env, self.request)
        self._run_workers([
            ("foreground", lambda: self._rpc("revolut_poll_payment", *args, user_id=cashier_id)),
            ("cancel-precheck" if overlap else "check-status", lambda: duplicate(0)),
            ("cron" if overlap else "shared-browser", lambda: duplicate(1)),
            ("observer", observer),
        ])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid,
                          user_id=cashier_id)
        self.assertEqual(counts["intent_reads"], 1)
        self.assertEqual(counts["peak"], 1)
        self.assertEqual(counts["active"], 0)
        self.assertFalse(financial_posts(self.request))
        self.assertEqual(final["state"], "pending" if outcome == "pending" else "unresolved")
        self.assertFalse(final["retry_safe"])
        print("TICKET38_POLL_EVIDENCE " + json.dumps({
            "outcome": outcome, "cron_cancel_overlap": overlap, **counts,
            "total_provider_reads": sum(call.args[0] == "GET" for call in self.request.call_args_list),
            "total_provider_calls": self.request.call_count,
            "final_state": final["state"], "retry_safe": final["retry_safe"],
        }, sort_keys=True))
        return args, cashier_id

    def test_bounded_status_reads_from_three_shared_cashier_browsers(self):
        self._bounded_status_reads("pending")

    def test_bounded_status_reads_overlap_cron_and_cancellation_precheck(self):
        self._bounded_status_reads("pending", overlap=True)

    def test_bounded_status_reads_preserve_malformed_uncertainty(self):
        self._bounded_status_reads("malformed")

    def test_bounded_status_reads_preserve_timeout_uncertainty(self):
        self._bounded_status_reads("timeout")

    def test_bounded_status_reads_preserve_http_error_uncertainty(self):
        self._bounded_status_reads("http_error")

    def test_bounded_status_reads_recover_late_success_after_local_timeout(self):
        args, cashier_id = self._bounded_status_reads("timeout")
        timed_out = self._rpc("revolut_mark_timeout", *args, user_id=cashier_id)
        self.assertEqual(timed_out["local_outcome"], "timed_out")
        self.assertFalse(timed_out["retry_safe"])

        def success(method, url, **kwargs):
            self.assertEqual(method, "GET")
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code, "state": "captured",
                })
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.reset_mock()
        self.request.side_effect = success
        verified = self._rpc("revolut_poll_payment", *args, user_id=cashier_id)
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(verified["payment_id"], self.provider_payment)
        self.assertFalse(verified["retry_safe"])
        # Native authorized payments need authenticated report evidence, even
        # for zero tips. Intent completion alone cannot verify this control.
        self.assertFalse(verified["awaiting_tip_details"])
        self.assertFalse(financial_posts(self.request))
        calls_to_verify = self.request.call_count
        results = self._run_workers([
            (f"verified-browser-{index}", lambda: self._rpc(
                "revolut_poll_payment", *args, user_id=cashier_id,
            )) for index in range(3)
        ])
        self.assertEqual([result["state"] for result in results], ["verified"] * 3)
        self.assertEqual(self.request.call_count, calls_to_verify)
        print("TICKET29_POLL_EVIDENCE " + json.dumps({
            "outcome": "late_success_after_local_timeout",
            "total_provider_reads": sum(call.args[0] == "GET" for call in self.request.call_args_list),
            "total_provider_calls": calls_to_verify,
            "additional_reads_from_three_verified_browsers": 0,
            "final_state": verified["state"], "retry_safe": verified["retry_safe"],
        }, sort_keys=True))

    def test_busy_starts_recover_only_after_cancellation_and_explicit_start(self):
        self.request.side_effect = self._start_http
        blocker = self._start()
        other_order_uuid, other_line_uuid = str(uuid4()), str(uuid4())
        self._prepare(other_order_uuid, other_line_uuid)
        self.request.reset_mock()
        busy_barrier = Barrier(3)

        def busy_start():
            busy_barrier.wait(timeout=10)
            return self._start(order_uuid=other_order_uuid, line_uuid=other_line_uuid)

        rejected = self._run_workers([
            (f"busy-{index}", busy_start) for index in range(3)
        ])
        self.assertEqual(rejected, [{
            "start_rejected": "terminal_busy",
            "dispatched": False,
            "order_uuid": other_order_uuid,
            "payment_line_uuid": other_line_uuid,
            "previous_operation_id": False,
        }] * 3)
        for _lookup in range(2):
            self.assertFalse(self._rpc(
                "revolut_find_payment", other_order_uuid, other_line_uuid
            ))
        self.request.assert_not_called()
        self.assertEqual(self._rpc(
            "revolut_find_payment", self.order_uuid, self.line_uuid
        ), blocker)

        cancellation_sent = Event()

        def cancel_http(method, url, **kwargs):
            if method == "POST" and url.endswith("/cancel"):
                cancellation_sent.set()
                return self._response({})
            if method == "GET" and url.endswith(
                f"/api/payment-intents/{self.provider_intent}"
            ):
                return self._intent("cancelled" if cancellation_sent.is_set() else "pending")
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.side_effect = cancel_http
        cancelled = self._rpc(
            "revolut_cancel_payment", blocker["operation_id"],
            self.order_uuid, self.line_uuid,
        )
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertTrue(cancelled["retry_safe"])
        self.assertEqual(len(financial_posts(self.request)), 1)
        self.request.reset_mock()
        self.assertFalse(self._rpc(
            "revolut_find_payment", other_order_uuid, other_line_uuid
        ))
        self.request.assert_not_called()

        self.provider_order, self.provider_intent = str(uuid4()), str(uuid4())
        start_barrier, replay_finished = Barrier(2), Event()

        def start_http(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                self.assertTrue(replay_finished.wait(10), "Repeated start did not coalesce")
            return self._start_http(method, url, **kwargs)

        def start_after_release():
            start_barrier.wait(timeout=10)
            try:
                return self._start(order_uuid=other_order_uuid, line_uuid=other_line_uuid)
            finally:
                replay_finished.set()

        self.request.side_effect = start_http
        started = self._run_workers([
            ("start-one", start_after_release), ("start-two", start_after_release),
        ])
        recovered = self._rpc("revolut_find_payment", other_order_uuid, other_line_uuid)
        self.assertEqual(recovered["state"], "pending")
        self.assertEqual({item["operation_id"] for item in started},
                         {recovered["operation_id"]})
        self.assertNotEqual(recovered["operation_id"], blocker["operation_id"])
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 2, "Only one order and one intent may be dispatched")
        self.assertEqual(posts[0].kwargs["json"]["metadata"]["pos_order_uuid"], other_order_uuid)
        self.assertEqual(posts[0].kwargs["json"]["metadata"]["pos_payment_line_uuid"], other_line_uuid)

    def test_busy_replacement_retains_predecessor_and_reuses_existing_attempts(self):
        self.request.side_effect = self._start_http
        first = self._start()
        self.request.side_effect = lambda *args, **kwargs: self._intent("cancelled")
        cancelled = self._rpc(
            "revolut_poll_payment", first["operation_id"], self.order_uuid, self.line_uuid
        )
        self.assertTrue(cancelled["retry_safe"])
        other_order_uuid, other_line_uuid = str(uuid4()), str(uuid4())
        self._prepare(other_order_uuid, other_line_uuid)
        self.provider_order, self.provider_intent = str(uuid4()), str(uuid4())
        self.request.side_effect = self._start_http
        blocker = self._start(order_uuid=other_order_uuid, line_uuid=other_line_uuid)
        self.request.reset_mock()

        rejected = self._start(first["operation_id"])
        self.assertEqual(rejected, {
            "start_rejected": "terminal_busy",
            "dispatched": False,
            "order_uuid": self.order_uuid,
            "payment_line_uuid": self.line_uuid,
            "previous_operation_id": first["operation_id"],
        })
        self.assertEqual(self._start(first["operation_id"]), rejected)
        self.assertTrue(cancelled["observation_fresh"])
        cached_cancelled = {**cancelled, "observation_fresh": False}
        self.assertEqual(self._start(), cached_cancelled)
        self.assertEqual(self._rpc(
            "revolut_find_payment", self.order_uuid, self.line_uuid
        ), cached_cancelled)
        self.request.assert_not_called()

        self.request.side_effect = lambda *args, **kwargs: self._intent("cancelled")
        released = self._rpc(
            "revolut_poll_payment", blocker["operation_id"], other_order_uuid, other_line_uuid
        )
        self.assertTrue(released["retry_safe"])
        self.provider_order, self.provider_intent = str(uuid4()), str(uuid4())
        self.request.reset_mock()
        self.request.side_effect = self._start_http
        replacement = self._start(first["operation_id"])
        self.assertNotEqual(replacement["operation_id"], first["operation_id"])
        self.assertEqual(self._start(first["operation_id"]), replacement)
        self.assertEqual(self._start(), replacement)
        self.assertEqual(self._rpc(
            "revolut_find_payment", self.order_uuid, self.line_uuid
        ), replacement)
        self.assertEqual(len(financial_posts(self.request)), 2)

    def _assert_creation_crash_keeps_dispatch(self, action, after_response):
        def http(method, url, **kwargs):
            if not after_response and method == "POST" and (
                (action == "create_order" and url.endswith("/api/orders"))
                or (action == "create_intent" and url.endswith("/payment-intents"))
            ):
                raise RuntimeError("simulated crash before provider request")
            return self._start_http(method, url, **kwargs)

        self.request.side_effect = http
        original_complete = type(
            self.env["pos.payment.method"]
        )._apply_revolut_observation_owned

        def crash_after_result(method, operation_id, kind, *args):
            if kind == f"dispatch_{action}":
                raise RuntimeError("simulated crash after provider response")
            return original_complete(method, operation_id, kind, *args)

        with patch.object(
            type(self.env["pos.payment.method"]),
            "_apply_revolut_observation_owned",
            autospec=True,
            side_effect=crash_after_result if after_response else original_complete,
        ), self.assertRaises(RuntimeError):
            self._start()

        recovered = self._rpc(
            "revolut_find_payment", self.order_uuid, self.line_uuid
        )
        self.assertTrue(recovered, "The committed claim vanished after the crash")
        replay = self._start()
        self.assertEqual(replay, recovered)
        self.assertEqual(recovered["state"], "unresolved")
        self.assertFalse(recovered["retry_safe"])
        self.assertEqual(
            bool(recovered["order_id"]), action == "create_intent"
        )
        self.assertFalse(recovered["payment_intent_id"])
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            dispatch = env["pos.revolut.payment.dispatch"].search([
                ("operation_id", "=", recovered["operation_id"]),
                ("action", "=", action),
            ])
            self.assertEqual(len(dispatch), 1)
            self.assertFalse(dispatch.completed_at)
        self.assertEqual(
            len(financial_posts(self.request)),
            2 if action == "create_intent" else 1,
        )

    def test_crash_before_order_request_blocks_replay(self):
        self._assert_creation_crash_keeps_dispatch("create_order", False)

    def test_crash_before_intent_request_blocks_replay(self):
        self._assert_creation_crash_keeps_dispatch("create_intent", False)

    def test_crash_after_intent_response_blocks_replay(self):
        self._assert_creation_crash_keeps_dispatch("create_intent", True)

    def test_crash_after_payment_result_recovers_verified_reference(self):
        self.request.side_effect = self._start_http
        started = self._start()

        def http(method, url, **kwargs):
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code,
                    "state": "captured",
                })
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.reset_mock()
        self.request.side_effect = http
        original_update = type(
            self.env["pos.payment.method"]
        )._apply_revolut_observation_owned

        def crash_before_verified_commit(method, operation_id, kind, *args, **kwargs):
            if kind == "payment":
                raise RuntimeError("simulated crash after payment result")
            return original_update(method, operation_id, kind, *args, **kwargs)

        with patch.object(
            type(self.env["pos.payment.method"]),
            "_apply_revolut_observation_owned", autospec=True,
            side_effect=crash_before_verified_commit,
        ), self.assertRaises(RuntimeError):
            self._rpc(
                "revolut_poll_payment", started["operation_id"],
                self.order_uuid, self.line_uuid,
            )

        # The crashed holder retains its fixed claim until expiry.
        self._advance_observation(61)
        recovered = self._rpc(
            "revolut_poll_payment", started["operation_id"],
            self.order_uuid, self.line_uuid,
        )
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], self.provider_payment)
        self.assertFalse(financial_posts(self.request))

    def test_crash_after_cancel_response_never_replays_cancel(self):
        self.request.side_effect = self._start_http
        started = self._start()
        reads = 0

        def http(method, url, **kwargs):
            nonlocal reads
            if method == "GET" and url.endswith(
                f"/api/payment-intents/{self.provider_intent}"
            ):
                reads += 1
                return self._intent("pending" if reads == 1 else "cancelled")
            if method == "POST" and url.endswith("/cancel"):
                return self._response({})
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.reset_mock()
        self.request.side_effect = http
        original_complete = type(
            self.env["pos.payment.method"]
        )._apply_revolut_observation_owned

        def crash_after_cancel(method, operation_id, kind, *args):
            if kind == "dispatch_cancel_intent":
                raise RuntimeError("simulated crash after cancel response")
            return original_complete(method, operation_id, kind, *args)

        with patch.object(
            type(self.env["pos.payment.method"]),
            "_apply_revolut_observation_owned", autospec=True,
            side_effect=crash_after_cancel,
        ), self.assertRaises(RuntimeError):
            self._rpc(
                "revolut_cancel_payment", started["operation_id"],
                self.order_uuid, self.line_uuid,
            )

        self._advance_observation(61)
        recovered = self._rpc(
            "revolut_cancel_payment", started["operation_id"],
            self.order_uuid, self.line_uuid,
        )
        self.assertEqual(recovered["state"], "cancelled")
        self.assertTrue(recovered["retry_safe"])
        self.assertEqual(len(financial_posts(self.request)), 1)

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
            # An expired physical read may overlap its successor; only the
            # successor owns the right to apply evidence.
            self._advance_observation(61)
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
        self.assertFalse(financial_posts(self.request))

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
        with self.registry.cursor() as cursor:
            setup_env = api.Environment(cursor, SUPERUSER_ID, self.context)
            cashier_ids = [new_test_user(
                setup_env,
                login=f"revolut_concurrent_cashier_{index}_{uuid4().hex}",
                groups="base.group_user,point_of_sale.group_pos_user",
                company_id=setup_env.company.id,
            ).id for index in range(2)]
            setup_env["pos.session"].browse(self.session_id).config_id.write({
                "revolut_user_ids": [Command.set(cashier_ids)],
            })
            cursor.commit()
        # Administrator provisioning changes the configuration pricing stamp.
        # The cancelled attempt has no exposure; refresh normal cart authority
        # before the two granted colleagues race to retry it.
        self._prepare(self.order_uuid, self.line_uuid)

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                self.assertTrue(replay_finished.wait(10), "Competing retry did not return")
            return self._start_http(method, url, **kwargs)

        def retry(user_id):
            barrier.wait(timeout=10)
            try:
                return self._start(first["operation_id"], user_id=user_id)
            finally:
                replay_finished.set()

        self.request.side_effect = http
        results = self._run_workers([
            ("retry-one", lambda: retry(cashier_ids[0])),
            ("retry-two", lambda: retry(cashier_ids[1])),
        ])
        # The competing retry returns the committed replacement while its
        # original caller is still dispatching. That provisional snapshot is
        # unresolved until the original request acknowledges the intent.
        self.assertTrue(all(result["state"] in {"pending", "unresolved"}
                            for result in results), repr(results))
        self.assertEqual(len({result["operation_id"] for result in results}), 1)
        self.assertNotEqual(results[0]["operation_id"], first["operation_id"])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "pending")
        self.assertEqual(final["operation_id"], results[0]["operation_id"])
        posts = financial_posts(self.request)
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
            self._advance_observation(61)
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
        posts = financial_posts(self.request)
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
            self._advance_observation(61)
            result = self._rpc("revolut_poll_payment", *args)
            self.assertEqual(result["state"], "verified")
            return result

        self.request.side_effect = http
        self._run_workers([("cancel", cancel), ("poll", poll)])
        final = self._rpc("revolut_poll_payment", *args)
        self.assertEqual(final["state"], "verified")
        self.assertFalse(final["retry_safe"])
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 1, "Unsafe retry must dispatch no new payment")

    def test_association_audit_failure_rolls_back_references(self):
        def interrupted_order(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                raise requests.Timeout()
            return self._start_http(method, url, **kwargs)

        self.request.side_effect = interrupted_order
        started = self._start()
        self.assertEqual(started["state"], "unresolved")

        def evidence(method, url, **kwargs):
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                return self._manager_intent()
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.side_effect = evidence
        audit_model = type(self.env["pos.revolut.reconciliation.audit"])
        with patch.object(audit_model, "create", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                self._manager_rpc(
                    started["operation_id"], "action_revolut_associate",
                    self.provider_order, self.provider_intent,
                )
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.payment.operation"].browse(started["operation_id"])
            self.assertFalse(operation.revolut_order_id)
            self.assertFalse(operation.revolut_payment_intent_id)
            self.assertFalse(operation.audit_ids)
            self.assertTrue(operation.blocking_order_key)

    def test_reconciliation_audit_failure_keeps_committed_payment(self):
        def interrupted_order(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                raise requests.Timeout()
            return self._start_http(method, url, **kwargs)

        self.request.side_effect = interrupted_order
        started = self._start()

        def association_evidence(method, url, **kwargs):
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                return self._manager_intent()
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.side_effect = association_evidence
        self._manager_rpc(
            started["operation_id"], "action_revolut_associate",
            self.provider_order, self.provider_intent,
        )

        def payment_evidence(method, url, **kwargs):
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code,
                    "state": "captured",
                })
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.side_effect = payment_evidence
        audit_model = type(self.env["pos.revolut.reconciliation.audit"])
        with patch.object(audit_model, "create", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesRegex(RuntimeError, "audit failed"):
                self._manager_rpc(started["operation_id"], "action_revolut_reconcile")
        recovered = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], self.provider_payment)
        self.assertFalse(recovered["retry_safe"])
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.payment.operation"].browse(started["operation_id"])
            self.assertFalse(operation.blocking_order_key)
            self.assertFalse(operation.blocking_terminal_key)
            self.assertEqual(operation.audit_ids.mapped("action"), ["associate"])

    def test_delayed_order_acknowledgement_preserves_manager_verified_result(self):
        order_sent, reconciled = Event(), Event()
        intent_reads = 0

        def http(method, url, **kwargs):
            nonlocal intent_reads
            if method == "POST" and url.endswith("/api/orders"):
                order_sent.set()
                self.assertTrue(reconciled.wait(10))
                return self._response({"id": self.provider_order})
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                intent_reads += 1
                if intent_reads == 1:
                    return self._manager_intent()
                return self._intent("completed", payment_id=self.provider_payment)
            if url.endswith(f"/api/payments/{self.provider_payment}"):
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code,
                    "state": "completed",
                })
            return self._start_http(method, url, **kwargs)

        def recovery():
            self.assertTrue(order_sent.wait(10))
            try:
                pending = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
                self._manager_rpc(
                    pending["operation_id"], "action_revolut_associate",
                    self.provider_order, self.provider_intent,
                )
                self._manager_rpc(pending["operation_id"], "action_revolut_reconcile")
                verified = self._rpc(
                    "revolut_find_payment", self.order_uuid, self.line_uuid
                )
                self.assertEqual(verified["state"], "verified")
            finally:
                reconciled.set()

        self.request.side_effect = http
        self._run_workers([("start", self._start), ("recovery", recovery)])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "verified")
        self.assertEqual(final["order_id"], self.provider_order)
        self.assertEqual(final["payment_intent_id"], self.provider_intent)
        self.assertEqual(final["payment_id"], self.provider_payment)
        self.assertFalse(final["retry_safe"])
        self.assertEqual(self._start(), final)
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 1, "Recovery must not dispatch another intent")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            dispatches = env["pos.revolut.payment.dispatch"].search([
                ("operation_id", "=", final["operation_id"]),
            ])
            operation = env["pos.revolut.payment.operation"].browse(
                final["operation_id"]
            )
            self.assertFalse(operation.blocking_order_key)
            self.assertFalse(operation.blocking_terminal_key)
            self.assertEqual(dispatches.mapped("action"), ["create_order"])
            self.assertEqual(dispatches.outcome, "succeeded")
            self.assertEqual(dispatches.provider_reference, self.provider_order)

    def test_order_only_association_during_ack_allows_first_intent_dispatch(self):
        order_sent, associated = Event(), Event()

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                order_sent.set()
                self.assertTrue(associated.wait(10))
                return self._response({"id": self.provider_order})
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            return self._start_http(method, url, **kwargs)

        def associate():
            self.assertTrue(order_sent.wait(10))
            try:
                pending = self._rpc(
                    "revolut_find_payment", self.order_uuid, self.line_uuid
                )
                self._manager_rpc(
                    pending["operation_id"], "action_revolut_associate",
                    self.provider_order,
                )
            finally:
                associated.set()

        self.request.side_effect = http
        self._run_workers([("start", self._start), ("associate", associate)])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "pending")
        self.assertEqual(final["order_id"], self.provider_order)
        self.assertEqual(final["payment_intent_id"], self.provider_intent)
        self.assertFalse(final["retry_safe"])
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 2, "Only the original order and one intent may dispatch")

    def test_order_only_association_before_intent_claim_allows_first_dispatch(self):
        claim_started, associated = Event(), Event()
        method_type = type(self.env["pos.payment.method"])
        original_claim = method_type._claim_revolut_dispatch_owned

        def paused_claim(method, operation_id, action):
            if action == "create_intent":
                claim_started.set()
                self.assertTrue(associated.wait(10))
            return original_claim(method, operation_id, action)

        def associate():
            self.assertTrue(claim_started.wait(10))
            try:
                current = self._rpc(
                    "revolut_find_payment", self.order_uuid, self.line_uuid
                )
                self._manager_rpc(
                    current["operation_id"], "action_revolut_associate",
                    self.provider_order,
                )
            finally:
                associated.set()

        def http(method, url, **kwargs):
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            return self._start_http(method, url, **kwargs)

        self.request.side_effect = http
        with patch.object(method_type, "_claim_revolut_dispatch_owned",
                          autospec=True, side_effect=paused_claim):
            self._run_workers([("start", self._start), ("associate", associate)])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "pending")
        self.assertEqual(final["payment_intent_id"], self.provider_intent)
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 2)

    def test_order_only_association_during_intent_dispatch_keeps_ack(self):
        intent_sent, associated = Event(), Event()

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith("/payment-intents"):
                intent_sent.set()
                self.assertTrue(associated.wait(10))
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            return self._start_http(method, url, **kwargs)

        def associate():
            self.assertTrue(intent_sent.wait(10))
            try:
                current = self._rpc(
                    "revolut_find_payment", self.order_uuid, self.line_uuid
                )
                self._manager_rpc(
                    current["operation_id"], "action_revolut_associate",
                    self.provider_order,
                )
            finally:
                associated.set()

        self.request.side_effect = http
        self._run_workers([("start", self._start), ("associate", associate)])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "pending")
        self.assertEqual(final["payment_intent_id"], self.provider_intent)
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 2)

    def _assert_observation_during_creation_dispatch(self, action, observation):
        dispatch_started, observation_finished = Event(), Event()

        def http(method, url, **kwargs):
            is_target = (
                method == "POST" and (
                    (action == "create_order" and url.endswith("/api/orders"))
                    or (action == "create_intent" and url.endswith("/payment-intents"))
                )
            )
            if is_target:
                dispatch_started.set()
                self.assertTrue(observation_finished.wait(10))
            return self._start_http(method, url, **kwargs)

        def observe():
            self.assertTrue(dispatch_started.wait(10))
            try:
                current = self._rpc(
                    "revolut_find_payment", self.order_uuid, self.line_uuid
                )
                result = self._rpc(
                    observation, current["operation_id"],
                    self.order_uuid, self.line_uuid,
                )
                self.assertEqual(result["state"], "unresolved")
            finally:
                observation_finished.set()

        self.request.side_effect = http
        self._run_workers([("start", self._start), ("observe", observe)])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "pending")
        self.assertEqual(final["order_id"], self.provider_order)
        self.assertEqual(final["payment_intent_id"], self.provider_intent)
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 2)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.payment.operation"].browse(
                final["operation_id"]
            )
            self.assertTrue(operation.next_reconcile_at)

    def test_poll_during_order_dispatch_does_not_strand_valid_acknowledgement(self):
        self._assert_observation_during_creation_dispatch(
            "create_order", "revolut_poll_payment"
        )

    def test_poll_during_intent_dispatch_does_not_strand_valid_acknowledgement(self):
        self._assert_observation_during_creation_dispatch(
            "create_intent", "revolut_poll_payment"
        )

    def test_timeout_during_order_dispatch_resumes_valid_acknowledgement(self):
        self._assert_observation_during_creation_dispatch(
            "create_order", "revolut_mark_timeout"
        )

    def test_timeout_during_intent_dispatch_schedules_reconciliation(self):
        self._assert_observation_during_creation_dispatch(
            "create_intent", "revolut_mark_timeout"
        )

    def _assert_timeout_before_creation_claim(self, action):
        claim_started, timed_out = Event(), Event()
        method_type = type(self.env["pos.payment.method"])
        original_claim = method_type._claim_revolut_dispatch_owned

        def paused_claim(method, operation_id, claimed_action):
            if claimed_action == action:
                claim_started.set()
                self.assertTrue(timed_out.wait(10))
            return original_claim(method, operation_id, claimed_action)

        def timeout():
            self.assertTrue(claim_started.wait(10))
            try:
                current = self._rpc(
                    "revolut_find_payment", self.order_uuid, self.line_uuid
                )
                result = self._rpc(
                    "revolut_mark_timeout", current["operation_id"],
                    self.order_uuid, self.line_uuid,
                )
                self.assertEqual(result["state"], "unresolved")
                self.assertEqual(result["local_outcome"], "timed_out")
            finally:
                timed_out.set()

        self.request.side_effect = self._start_http
        with patch.object(method_type, "_claim_revolut_dispatch_owned",
                          autospec=True, side_effect=paused_claim):
            self._run_workers([("start", self._start), ("timeout", timeout)])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "pending")
        self.assertEqual(final["order_id"], self.provider_order)
        self.assertEqual(final["payment_intent_id"], self.provider_intent)
        posts = financial_posts(self.request)
        self.assertEqual(len(posts), 2)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.payment.operation"].browse(
                final["operation_id"]
            )
            self.assertTrue(operation.next_reconcile_at)

    def test_timeout_before_order_claim_keeps_first_dispatch_claimable(self):
        self._assert_timeout_before_creation_claim("create_order")

    def test_timeout_before_intent_claim_keeps_first_dispatch_claimable(self):
        self._assert_timeout_before_creation_claim("create_intent")

    def test_stale_missing_reference_poll_reads_newly_associated_evidence(self):
        def interrupted_order(method, url, **kwargs):
            if method == "POST" and url.endswith("/api/orders"):
                raise requests.Timeout()
            return self._start_http(method, url, **kwargs)

        self.request.side_effect = interrupted_order
        started = self._start()
        read_finished, associated = Event(), Event()
        scheduled = []
        polled = []

        def evidence(method, url, **kwargs):
            if url.endswith(f"/api/orders/{self.provider_order}"):
                return self._manager_order()
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                return self._manager_intent()
            raise AssertionError(f"Unexpected HTTP request: {method} {url}")

        self.request.reset_mock()
        self.request.side_effect = evidence
        method_type = type(self.env["pos.payment.method"])
        original_read = method_type._read_revolut_operation_owned

        def paused_read(method, operation_id, *args, **kwargs):
            result = original_read(method, operation_id, *args, **kwargs)
            if current_thread().name == "poll" and not result["order_id"]:
                read_finished.set()
                self.assertTrue(associated.wait(10))
            return result

        def associate():
            self.assertTrue(read_finished.wait(10))
            try:
                self._manager_rpc(
                    started["operation_id"], "action_revolut_associate",
                    self.provider_order, self.provider_intent,
                )
                with self.registry.cursor() as cursor:
                    env = api.Environment(cursor, SUPERUSER_ID, self.context)
                    operation = env["pos.revolut.payment.operation"].browse(
                        started["operation_id"]
                    )
                    scheduled.append(operation.next_reconcile_at)
            finally:
                associated.set()

        def poll():
            polled.append(self._rpc(
                "revolut_poll_payment", started["operation_id"],
                self.order_uuid, self.line_uuid,
            ))

        # Association schedules immediate recovery. This caller's stale
        # preliminary access read predates its observation claim: the winner
        # reads the now-associated references and receives fresh evidence.
        due_time = datetime(2026, 10, 2, 12)
        with patch("odoo.fields.Datetime.now", return_value=due_time), patch.object(
            method_type, "_read_revolut_operation_owned",
            autospec=True, side_effect=paused_read,
        ):
            self._run_workers([
                ("poll", poll),
                ("associate", associate),
            ])
        self.assertEqual(scheduled, [due_time])
        self.assertEqual(len(polled), 1)
        self.assertEqual(polled[0]["state"], "pending")
        self.assertTrue(polled[0]["observation_fresh"])
        self.assertFalse(polled[0]["retry_safe"])
        calls = self.request.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(call.args[0] == "GET" for call in calls))
        self.assertEqual(sum(call.args[1].endswith(f"/api/orders/{self.provider_order}")
                             for call in calls), 1)
        self.assertEqual(sum(call.args[1].endswith(f"/api/payment-intents/{self.provider_intent}")
                             for call in calls), 2)
        self.assertFalse(financial_posts(self.request))
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            operation = env["pos.revolut.payment.operation"].browse(
                started["operation_id"]
            )
            self.assertEqual(operation.next_reconcile_at, due_time + timedelta(seconds=30))
            self.assertEqual(operation.revolut_order_id, self.provider_order)
            self.assertEqual(operation.revolut_payment_intent_id, self.provider_intent)

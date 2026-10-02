"""Exercise persisted provider observations through authorized public RPCs."""

from datetime import datetime, timedelta
from threading import Event, current_thread
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, Command, api
from odoo.tools import mute_logger
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .authorization_fixtures import financial_posts, install_zero_reports, native_products, zero_report_response
from .test_revolut_retry_concurrency import TestRevolutRetryConcurrency


@tagged("post_install", "-at_install")
class TestRevolutPaymentObservation(TransactionCase):
    # Share only fixture helpers; inheriting the class repeats its old tests.
    _rpc = TestRevolutRetryConcurrency._rpc
    _manager_rpc = TestRevolutRetryConcurrency._manager_rpc
    _prepare = TestRevolutRetryConcurrency._prepare
    _start = TestRevolutRetryConcurrency._start
    _response = staticmethod(TestRevolutRetryConcurrency._response)
    _start_http = TestRevolutRetryConcurrency._start_http
    _intent = TestRevolutRetryConcurrency._intent
    _run_workers = TestRevolutRetryConcurrency._run_workers

    def setUp(self):
        super().setUp()
        TestRevolutRetryConcurrency._set_up_payment_fixture(self)

    def _controlled_clock(self):
        self.observation_time = datetime(2026, 10, 2, 12, 0, 0)
        self.enterContext(patch(
            "odoo.addons.pos_revolut.models.payment_observation.observation_now",
            side_effect=lambda: self.observation_time,
        ))

    def _advance(self, seconds):
        self.observation_time += timedelta(seconds=seconds)

    def _success_http(self, method, url, **kwargs):
        self.assertEqual(method, "GET")
        if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
            return self._intent("completed", payment_id=self.provider_payment)
        if url.endswith(f"/api/payments/{self.provider_payment}"):
            return self._response({
                "id": self.provider_payment, "order_id": self.provider_order,
                "amount": 1234, "currency": self.currency_code, "state": "captured",
            })
        raise AssertionError(f"Unexpected HTTP request: {method} {url}")

    def _provider_reads(self, resource):
        return [call for call in self.request.call_args_list
                if call.args[0] == "GET" and resource in call.args[1]]

    def _pending(self):
        self.request.side_effect = self._start_http
        result = self._start()
        self.request.reset_mock()
        return result

    def _poll(self, started, *, user_id=SUPERUSER_ID):
        return self._rpc("revolut_poll_payment", started["operation_id"],
                         self.order_uuid, self.line_uuid, user_id=user_id)

    def _operation_values(self, operation_id, names):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            return env["pos.revolut.payment.operation"].browse(operation_id).read(names)[0]

    def _cron(self):
        install_zero_reports(self.env, self.request)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.payment.operation"]._cron_reconcile_payments(1)
            cursor.commit()

    def test_four_cashier_tabs_cron_and_cancel_share_held_observation(self):
        started = self._pending()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            cashiers = [new_test_user(
                env, login=f"observe_cashier_{uuid4().hex}",
                groups="point_of_sale.group_pos_user", company_id=env.company.id,
            ) for _index in range(2)]
            user_ids = [cashier.id for cashier in cashiers]
            env["pos.session"].browse(self.session_id).config_id.write({
                "revolut_user_ids": [Command.link(user_id) for user_id in user_ids],
            })
            env["pos.revolut.payment.operation"].browse(started["operation_id"]).write({
                "next_reconcile_at": "2000-01-01 00:00:00",
            })
            cursor.commit()

        entered, release, losers_finished = Event(), Event(), Event()
        reads = []
        snapshots = []

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith(f"/api/payment-intents/{self.provider_intent}"))
            reads.append(url)
            entered.set()
            self.assertTrue(release.wait(10), "Winner did not release provider fixture")
            return self._intent("pending")

        def losers():
            self.assertTrue(entered.wait(10))
            try:
                before = self._operation_values(started["operation_id"], [
                    "observation_token", "observation_expires_at", "next_reconcile_at",
                ])
                # The other tab of cashier one and both tabs of cashier two
                # must return while the winner remains inside mocked HTTP.
                for user_id in (user_ids[0], user_ids[1], user_ids[1]):
                    snapshots.append(self._poll(started, user_id=user_id))
                snapshots.append(self._rpc(
                    "revolut_cancel_payment", started["operation_id"],
                    self.order_uuid, self.line_uuid, user_id=user_ids[1],
                ))
                self._manager_rpc(started["operation_id"], "action_revolut_reconcile")
                self._cron()
                after = self._operation_values(started["operation_id"], [
                    "observation_token", "observation_expires_at", "next_reconcile_at",
                ])
                self.assertEqual(after, before, "Losing callers renewed or postponed recovery")
                self.assertFalse(release.is_set())
                losers_finished.set()
            finally:
                release.set()

        self.request.side_effect = http
        install_zero_reports(self.env, self.request)
        self._run_workers([
            ("winning-tab", lambda: self._poll(started, user_id=user_ids[0])),
            ("other-tabs-cron-cancel", losers),
        ])
        self.assertTrue(losers_finished.is_set(), "Losers must return before provider release")
        self.assertEqual(len(reads), 1)
        self.assertEqual(financial_posts(self.request), [])
        for snapshot in snapshots:
            self.assertEqual(snapshot["state"], "pending")
            self.assertTrue(snapshot["observation_in_progress"])
            self.assertFalse(snapshot["observation_fresh"])
            self.assertFalse(snapshot["retry_safe"])
            self.assertGreater(snapshot["next_check_seconds"], 0)
            self.assertLessEqual(snapshot["next_check_seconds"], 60)

    def test_cadence_boundary_stale_cancel_and_final_cache(self):
        started = self._pending()
        self._controlled_clock()
        self.request.side_effect = lambda method, url, **kwargs: self._intent("pending")
        first = self._poll(started)
        self.assertTrue(first["observation_fresh"])
        self.assertFalse(first["observation_in_progress"])
        self.assertTrue(first["observation_finished_at"])
        self._advance(0.999999)
        cached = self._poll(started)
        cancelled = self._rpc("revolut_cancel_payment", started["operation_id"],
                              self.order_uuid, self.line_uuid)
        for snapshot in (cached, cancelled):
            self.assertEqual(snapshot["state"], "pending")
            self.assertFalse(snapshot["observation_fresh"])
            self.assertFalse(snapshot["retry_safe"])
            self.assertEqual(snapshot["next_check_seconds"], 1)
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 1)
        self.assertEqual(financial_posts(self.request), [])
        self._advance(0.000001)
        self.request.side_effect = self._success_http
        verified = self._poll(started)
        self.assertEqual(verified["state"], "verified")
        self.assertTrue(verified["observation_fresh"])
        self.assertFalse(verified["awaiting_tip_details"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(len(self._provider_reads("/api/payments/")), 1)
        calls = self.request.call_count
        final = self._poll(started)
        self.assertEqual(final["state"], "verified")
        self.assertFalse(final["observation_fresh"])
        self.assertFalse(final["observation_in_progress"])
        self.assertEqual(final["next_check_seconds"], 0)
        self.assertEqual(self.request.call_count, calls)

    def test_retry_after_defers_without_http_and_recovers_late_capture(self):
        started = self._pending()
        self._controlled_clock()
        self.request.side_effect = requests.HTTPError(response=Mock(
            status_code=429, headers={"Retry-After": " 120 "},
        ))
        interrupted = self._poll(started)
        self.assertEqual(interrupted["state"], "unresolved")
        self.assertFalse(interrupted["observation_fresh"])
        self.assertFalse(interrupted["retry_safe"])
        self.assertEqual(interrupted["next_check_seconds"], 60)
        values = self._operation_values(started["operation_id"], [
            "observation_not_before", "next_reconcile_at",
        ])
        self.assertEqual(values["observation_not_before"], self.observation_time + timedelta(seconds=120))
        self.assertGreaterEqual(values["next_reconcile_at"], values["observation_not_before"])
        self._advance(119)
        cached = self._poll(started)
        self._cron()
        self.assertEqual(cached["state"], "unresolved")
        self.assertEqual(cached["next_check_seconds"], 1)
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 1)
        self.assertEqual(self._operation_values(started["operation_id"], [
            "observation_not_before", "next_reconcile_at",
        ]), values)
        self._advance(1)
        self.request.side_effect = self._success_http
        recovered = self._poll(started)
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], self.provider_payment)
        self.assertFalse(recovered["awaiting_tip_details"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(len(self._provider_reads("/api/payments/")), 1)
        self.assertEqual(financial_posts(self.request), [])

    def test_invalid_retry_after_keeps_uncertainty_without_provider_deferral(self):
        started = self._pending()
        self._controlled_clock()
        headers = (None, "", "-1", "1.5", "tomorrow", "Wed, 21 Oct 2026 07:28:00 GMT",
                   "99999999999999999999")
        for value in headers:
            with self.subTest(retry_after=value):
                self.request.side_effect = requests.HTTPError(response=Mock(
                    status_code=429, headers={} if value is None else {"Retry-After": value},
                ))
                observed = self._poll(started)
                self.assertEqual(observed["state"], "unresolved")
                self.assertFalse(observed["observation_fresh"])
                self.assertFalse(observed["retry_safe"])
                self.assertEqual(observed["next_check_seconds"], 1)
                self.assertFalse(self._operation_values(started["operation_id"], [
                    "observation_not_before",
                ])["observation_not_before"])
                self._advance(1)
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), len(headers))
        self.assertEqual(financial_posts(self.request), [])

    def test_timeout_503_and_malformed_evidence_remain_unresolved(self):
        started = self._pending()
        self._controlled_clock()
        outcomes = (
            requests.Timeout(),
            requests.HTTPError(response=Mock(status_code=503, headers={})),
            lambda method, url, **kwargs: self._intent("unexpected"),
        )
        for outcome in outcomes:
            self.request.side_effect = outcome
            observed = self._poll(started)
            self.assertEqual(observed["state"], "unresolved")
            self.assertFalse(observed["retry_safe"])
            self.assertFalse(observed["observation_fresh"])
            self._advance(1)
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 3)
        self.assertEqual(financial_posts(self.request), [])
        self.request.side_effect = self._success_http
        self.assertEqual(self._poll(started)["state"], "verified")

    def test_expired_holder_cannot_overwrite_successor_capture(self):
        started = self._pending()
        self._controlled_clock()
        entered, release = Event(), Event()
        old_results, new_results = [], []

        def http(method, url, **kwargs):
            if current_thread().name == "expired-holder":
                self.assertEqual(method, "GET")
                self.assertTrue(url.endswith(f"/api/payment-intents/{self.provider_intent}"))
                entered.set()
                self.assertTrue(release.wait(10))
                return self._intent("pending")
            return self._success_http(method, url, **kwargs)

        def successor():
            self.assertTrue(entered.wait(10))
            try:
                self._advance(60)
                new_results.append(self._poll(started))
                self.assertEqual(new_results[0]["state"], "verified")
            finally:
                release.set()

        self.request.side_effect = http
        install_zero_reports(self.env, self.request)
        self._run_workers([
            ("expired-holder", lambda: old_results.append(self._poll(started))),
            ("successor", successor),
        ])
        self.assertEqual(old_results[0]["state"], "verified")
        self.assertFalse(old_results[0]["observation_fresh"])
        self.assertTrue(new_results[0]["observation_fresh"])
        final = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        self.assertEqual(final["state"], "verified")
        self.assertEqual(final["payment_id"], self.provider_payment)
        self.assertFalse(final["observation_in_progress"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(len(self._provider_reads("/api/payments/")), 1)
        self.assertEqual(financial_posts(self.request), [])

    def _crashed_observation_recovers_after_fixed_expiry(self, *, after_response, cron):
        started = self._pending()
        self._controlled_clock()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.payment.operation"].browse(started["operation_id"]).write({
                "next_reconcile_at": "2000-01-01 00:00:00",
            })
            cursor.commit()
        self.request.side_effect = lambda method, url, **kwargs: self._intent("pending")
        if after_response:
            method_type = type(self.env["pos.payment.method"])
            original = method_type._apply_revolut_observation_owned

            def crash(method, operation_id, kind, *args, **kwargs):
                if kind == "intent":
                    raise SystemExit("simulated worker death after provider response")
                return original(method, operation_id, kind, *args, **kwargs)

            with patch.object(method_type, "_apply_revolut_observation_owned",
                              autospec=True, side_effect=crash), self.assertRaises(SystemExit):
                self._poll(started)
        else:
            self.request.side_effect = SystemExit("simulated worker death before provider response")
            with self.assertRaises(SystemExit):
                self._poll(started)
        before = self._operation_values(started["operation_id"], [
            "observation_token", "observation_expires_at", "observation_started_at",
            "next_reconcile_at",
        ])
        self.assertTrue(before["observation_token"])
        self.assertEqual(before["observation_expires_at"], self.observation_time + timedelta(seconds=60))
        self._advance(59.999999)
        cached = self._poll(started)
        self.assertTrue(cached["observation_in_progress"])
        self.assertFalse(cached["observation_fresh"])
        self.assertFalse(cached["retry_safe"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 1)
        self.assertEqual(self._operation_values(started["operation_id"], [
            "observation_token", "observation_expires_at", "observation_started_at",
            "next_reconcile_at",
        ]), before)
        self._advance(0.000001)
        self.request.side_effect = self._success_http
        if cron:
            self._cron()
            recovered = self._rpc("revolut_find_payment", self.order_uuid, self.line_uuid)
        else:
            recovered = self._poll(started)
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], self.provider_payment)
        self.assertFalse(recovered["observation_in_progress"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(len(self._provider_reads("/api/payments/")), 1)
        self.assertEqual(financial_posts(self.request), [])

    def test_worker_crash_before_response_recovers_in_foreground(self):
        self._crashed_observation_recovers_after_fixed_expiry(after_response=False, cron=False)

    def test_worker_crash_after_http_recovers_through_cron(self):
        self._crashed_observation_recovers_after_fixed_expiry(after_response=True, cron=True)

    def _direct_rpc(self, name, *args):
        """Use the same public seam with explicit authenticated report mocks."""
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = getattr(env["pos.payment.method"].browse(self.method_id), name)(*args)
            cursor.commit()
            return result

    def test_held_authenticated_report_is_shared_and_late_file_is_fenced(self):
        started = self._pending()
        self._controlled_clock()
        entered, release = Event(), Event()
        old_results, new_results = [], []
        args = (started["operation_id"], self.order_uuid, self.line_uuid)

        def http(method, url, **kwargs):
            if "/api/payment-intents/" in url:
                return self._intent("completed", payment_id=self.provider_payment,
                                    amount=1234, currency=self.currency_code,
                                    terminal_id=self.terminal_id)
            if "/api/payments/" in url:
                return self._response({
                    "id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code, "state": "captured",
                    "created_at": "2026-10-01T08:00:00Z",
                })
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                response = zero_report_response(env, method, url)
            self.assertIsNotNone(response, f"Unexpected provider request: {method} {url}")
            if url.endswith("/file") and current_thread().name == "old-report":
                chunks = response.iter_content.return_value

                def held_content(**_kwargs):
                    entered.set()
                    self.assertTrue(release.wait(10))
                    yield from chunks

                response.iter_content.side_effect = held_content
            return response

        def successor():
            self.assertTrue(entered.wait(10), "Report stream did not begin")
            try:
                for name in ("revolut_poll_payment", "revolut_cancel_payment"):
                    cached = self._direct_rpc(name, *args)
                    self.assertEqual(cached["state"], "pending")
                    self.assertTrue(cached["awaiting_tip_details"])
                    self.assertTrue(cached["observation_in_progress"])
                    self.assertFalse(cached["observation_fresh"])
                    self.assertFalse(cached["retry_safe"])
                # The provider socket can physically outlive the fixed lease.
                # A new observation may finish, but the old report cannot apply.
                self._advance(60)
                new_results.append(self._direct_rpc("revolut_poll_payment", *args))
                self.assertEqual(new_results[0]["state"], "verified")
                self.assertFalse(new_results[0]["awaiting_tip_details"])
            finally:
                release.set()

        self.request.side_effect = http
        self._run_workers([
            ("old-report", lambda: old_results.append(self._direct_rpc("revolut_poll_payment", *args))),
            ("report-successor", successor),
        ])
        self.assertEqual(old_results[0]["state"], "verified")
        self.assertFalse(old_results[0]["observation_fresh"])
        self.assertTrue(new_results[0]["observation_fresh"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(len(self._provider_reads("/api/payments/")), 2)
        report_posts = [call for call in self.request.call_args_list
                        if call.args[0] == "POST" and "/api/report-runs" in call.args[1]]
        self.assertEqual(len(report_posts), 1, "Observation expiry must not duplicate report creation")
        self.assertEqual(sum(call.args[1].endswith("/file") for call in self.request.call_args_list), 2)
        self.assertEqual(len(self._provider_reads("/api/orders/")), 1,
                         "Expired report holder must not continue to order reconciliation")
        self.assertEqual(financial_posts(self.request), [])

    def _independent_pending(self):
        names = ("method_id", "session_id", "order_uuid", "line_uuid", "terminal_id",
                 "provider_order", "provider_intent", "provider_payment", "product_id")
        saved = {name: getattr(self, name) for name in names}
        try:
            self.terminal_id = str(uuid4())
            self.order_uuid, self.line_uuid = str(uuid4()), str(uuid4())
            self.provider_order, self.provider_intent, self.provider_payment = (
                str(uuid4()), str(uuid4()), str(uuid4()),
            )
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                method = env["pos.payment.method"].browse(saved["method_id"]).copy({
                    "name": "Independent Revolut observation",
                    "revolut_terminal_id": self.terminal_id,
                    "revolut_location_id": self.location_id,
                    "revolut_fulfilment_type": "eat_in",
                    "revolut_environment": "sandbox",
                    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_RETRY_RACE_TEST",
                })
                config = env["pos.config"].create({
                    "name": "Independent Revolut observation",
                    "payment_method_ids": [Command.link(method.id)],
                    "auto_validate_terminal_payment": True,
                })
                self.product_id = native_products(env, config).id
                session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
                self.method_id, self.session_id = method.id, session.id
                cursor.commit()
            self._prepare(self.order_uuid, self.line_uuid)
            result = self._pending()
            return {**{name: getattr(self, name) for name in names}, "started": result}
        finally:
            for name, value in saved.items():
                setattr(self, name, value)

    def test_distinct_operation_observes_while_first_provider_read_is_held(self):
        started = self._pending()
        other = self._independent_pending()
        self._controlled_clock()
        entered, release, independently_finished = Event(), Event(), Event()
        results = []

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            if url.endswith(f"/api/payment-intents/{self.provider_intent}"):
                entered.set()
                self.assertTrue(release.wait(10))
                return self._intent("pending")
            self.assertTrue(url.endswith(f"/api/payment-intents/{other['provider_intent']}"))
            return self._response({
                "id": other["provider_intent"], "order_id": other["provider_order"],
                "amount": 1234, "currency": self.currency_code,
                "terminal_id": other["terminal_id"], "state": "pending",
            })

        def observe_other():
            self.assertTrue(entered.wait(10))
            try:
                before = self._operation_values(started["operation_id"], [
                    "observation_token", "observation_expires_at",
                ])
                with self.registry.cursor() as cursor:
                    env = api.Environment(cursor, SUPERUSER_ID, self.context)
                    result = env["pos.payment.method"].browse(other["method_id"]).revolut_poll_payment(
                        other["started"]["operation_id"], other["order_uuid"], other["line_uuid"],
                    )
                    cursor.commit()
                results.append(result)
                self.assertEqual(result["state"], "pending")
                self.assertTrue(result["observation_fresh"])
                self.assertEqual(self._operation_values(started["operation_id"], [
                    "observation_token", "observation_expires_at",
                ]), before)
                self.assertFalse(release.is_set())
                independently_finished.set()
            finally:
                release.set()

        self.request.side_effect = http
        install_zero_reports(self.env, self.request)
        self._run_workers([
            ("first-operation", lambda: self._poll(started)),
            ("independent-operation", observe_other),
        ])
        self.assertTrue(independently_finished.is_set())
        self.assertEqual(len(results), 1)
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(financial_posts(self.request), [])

    def test_payment_phase_budget_rejects_late_capture_before_report(self):
        started = self._pending()
        self._controlled_clock()
        elapsed = [0.0]

        def slow_payment(method, url, **kwargs):
            response = self._success_http(method, url, **kwargs)
            if "/api/payment-intents/" in url:
                elapsed[0] = 15.0
            elif "/api/payments/" in url:
                self.assertEqual(kwargs["timeout"], 5.0)
                elapsed[0] = 20.0
            return response

        self.request.side_effect = slow_payment
        with patch("odoo.addons.pos_revolut.models.payment_observation.time.monotonic",
                   side_effect=lambda: elapsed[0]):
            result = self._poll(started)
        self.assertEqual(result["state"], "unresolved")
        self.assertFalse(result["retry_safe"])
        self.assertFalse(result["observation_fresh"])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 1)
        self.assertEqual(len(self._provider_reads("/api/payments/")), 1)
        self.assertEqual(len(self.request.call_args_list), 2, "Late capture cannot start a report")
        self.assertEqual(financial_posts(self.request), [])
        self._advance(1)
        self.request.side_effect = self._success_http
        recovered = self._poll(started)
        self.assertEqual(recovered["state"], "verified")
        self.assertTrue(recovered["observation_fresh"])

    def test_report_phase_budget_rejects_late_stream_before_order_read(self):
        started = self._pending()
        self._controlled_clock()
        elapsed = [0.0]

        def slow_report(method, url, **kwargs):
            if "/api/payment-intents/" in url:
                return self._intent("completed", payment_id=self.provider_payment,
                                    amount=1234, currency=self.currency_code,
                                    terminal_id=self.terminal_id)
            if "/api/payments/" in url:
                return self._response({"id": self.provider_payment, "order_id": self.provider_order,
                    "amount": 1234, "currency": self.currency_code, "state": "captured",
                    "created_at": "2026-10-01T08:00:00Z"})
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                response = zero_report_response(env, method, url)
            self.assertIsNotNone(response)
            if url.endswith("/file"):
                elapsed[0] = 30.0
            return response

        self.request.side_effect = slow_report
        with patch("odoo.addons.pos_revolut.models.payment_observation.time.monotonic",
                   side_effect=lambda: elapsed[0]):
            result = self._direct_rpc("revolut_poll_payment", started["operation_id"],
                                      self.order_uuid, self.line_uuid)
        self.assertEqual(result["state"], "unresolved")
        self.assertTrue(result["awaiting_tip_details"])
        self.assertFalse(result["retry_safe"])
        self.assertFalse(result["observation_fresh"])
        self.assertEqual(len(self._provider_reads("/api/orders/")), 0)
        self.assertEqual(len(self.request.call_args_list), 4)
        self.assertEqual(financial_posts(self.request), [])

    def test_cancel_rate_limit_defers_recovery_without_replaying_post(self):
        started = self._pending()
        self._controlled_clock()
        limited = Mock(status_code=429, headers={"Retry-After": "2"})

        def cancellation_limit(method, url, **kwargs):
            if method == "POST":
                self.assertTrue(url.endswith("/cancel"))
                raise requests.HTTPError(response=limited)
            return self._intent("pending")

        self.request.side_effect = cancellation_limit
        args = (started["operation_id"], self.order_uuid, self.line_uuid)
        result = self._rpc("revolut_cancel_payment", *args)
        self.assertEqual(result["state"], "unresolved")
        self.assertFalse(result["retry_safe"])
        self.assertEqual(len(self.request.call_args_list), 2,
                         "Retry-After must defer the immediate recovery GET")
        self.assertEqual(len(financial_posts(self.request)), 1)
        self._advance(1)
        self._rpc("revolut_cancel_payment", *args)
        self.assertEqual(len(self.request.call_args_list), 2)
        self._advance(1)
        self.request.side_effect = self._success_http
        recovered = self._rpc("revolut_cancel_payment", *args)
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(len(financial_posts(self.request)), 1)

    def test_expired_holder_cannot_release_active_successor_lease(self):
        started = self._pending()
        self._controlled_clock()
        old_entered, new_entered = Event(), Event()
        release_old, release_new, old_finished = Event(), Event(), Event()
        results = []

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith(f"/api/payment-intents/{self.provider_intent}"))
            if current_thread().name == "old-holder":
                old_entered.set()
                self.assertTrue(release_old.wait(10))
            else:
                new_entered.set()
                self.assertTrue(release_new.wait(10))
            return self._intent("pending")

        def old_holder():
            try:
                results.append(self._poll(started))
            finally:
                old_finished.set()

        def new_holder():
            self.assertTrue(old_entered.wait(10))
            self._advance(60)
            return self._poll(started)

        def verify_fence():
            try:
                self.assertTrue(new_entered.wait(10))
                before = self._operation_values(started["operation_id"], [
                    "observation_token", "observation_expires_at", "observation_finished_at",
                ])
                release_old.set()
                self.assertTrue(old_finished.wait(10))
                after = self._operation_values(started["operation_id"], list(before.keys() - {"id"}))
                self.assertEqual(after, before, "An expired release must preserve its successor")
                self.assertTrue(results[0]["observation_in_progress"])
                self.assertFalse(results[0]["observation_fresh"])
            finally:
                release_old.set()
                release_new.set()

        self.request.side_effect = http
        install_zero_reports(self.env, self.request)
        self._run_workers([
            ("old-holder", old_holder), ("new-holder", new_holder), ("fence-check", verify_fence),
        ])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(financial_posts(self.request), [])

    def test_exhausted_cron_conflicts_cannot_reschedule_successor(self):
        started = self._pending()
        self._controlled_clock()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.payment.operation"].browse(started["operation_id"]).write({
                "next_reconcile_at": "2000-01-01 00:00:00",
            })
            cursor.commit()
        operation_type = type(self.env["pos.revolut.payment.operation"])
        method_type = type(self.env["pos.payment.method"])
        apply = operation_type._apply_payment_observation
        apply_owned = method_type._apply_revolut_observation_owned
        failed_cursors, successor_values = [], []
        names = ["state", "provider_state", "reconcile_failures", "next_reconcile_at",
                 "observation_token", "observation_expires_at", "observation_finished_at"]

        def conflicting(operation, kind, evidence=None):
            if kind == "intent" and current_thread().name != "conflict-successor":
                failed_cursors.append(operation.env.cr)
                operation.env.cr.execute(
                    "DO $$ BEGIN RAISE EXCEPTION USING ERRCODE = '40001', "
                    "MESSAGE = 'test observation conflict'; END $$"
                )
            return apply(operation, kind, evidence)

        def successor_after_exhaustion(method, operation_id, kind, evidence=None):
            try:
                return apply_owned(method, operation_id, kind, evidence)
            except SerializationFailure:
                # All failed cursors have rolled back before a new worker
                # takes the expired lease and commits newer pending evidence.
                self._advance(60)
                self._run_workers([("conflict-successor", lambda: self._poll(started))])
                successor_values.append(self._operation_values(operation_id, names))
                raise

        self.request.side_effect = lambda method, url, **kwargs: self._intent("processing")
        with patch.object(operation_type, "_apply_payment_observation", conflicting), \
                patch.object(method_type, "_apply_revolut_observation_owned", successor_after_exhaustion), \
                mute_logger("odoo.sql_db"):
            self._cron()
        self.assertEqual(len(failed_cursors), 3)
        self.assertTrue(all(cursor.closed for cursor in failed_cursors))
        self.assertEqual(successor_values[0]["state"], "pending")
        self.assertEqual(successor_values[0]["provider_state"], "processing")
        self.assertEqual(self._operation_values(started["operation_id"], names), successor_values[0])
        self.assertEqual(len(self._provider_reads("/api/payment-intents/")), 2)
        self.assertEqual(financial_posts(self.request), [])

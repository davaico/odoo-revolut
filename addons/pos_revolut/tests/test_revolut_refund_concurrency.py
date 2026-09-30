"""Refund RPC safety across real, independently committed transactions."""

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
class TestRevolutRefundConcurrency(TransactionCase):
    def setUp(self):
        super().setUp()
        self.registry = self.env.registry
        self.context = {"allowed_company_ids": [self.env.company.id]}
        self.order_uuid, self.line_uuid = str(uuid4()), str(uuid4())
        self.provider_order, self.provider_refund = str(uuid4()), str(uuid4())
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
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_REFUND_RACE_TEST",
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
            self.currency_id, self.currency_code = config.currency_id.id, config.currency_id.name
            self.snapshot = {
                "amount_total": -12.34,
                "pricelist_id": order.pricelist_id.id or 0, "fiscal_position_id": False,
                "lines": [{"uuid": str(uuid4()), "product_id": product.id,
                           "qty": -1, "price_unit": 12.34, "discount": 0,
                           "tax_ids": [], "refunded_orderline_id": order.lines.id}],
            }
            cursor.commit()
        self.enterContext(patch.dict(os.environ, {
            "ODOO_REVOLUT_SECRET_REFUND_RACE_TEST": "test-only",
        }))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        self.request.side_effect = self._http

    def _rpc(self, name, *args):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = getattr(env["pos.payment.method"].browse(self.method_id), name)(*args)
            cursor.commit()
            return result

    def _start(self, order_uuid=None, line_uuid=None):
        return self._rpc(
            "revolut_start_refund", self.session_id, order_uuid or self.order_uuid,
            line_uuid or self.line_uuid, -12.34, self.currency_id, self.snapshot,
        )

    @staticmethod
    def _response(payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _refund(self, state):
        return self._response({
            "id": self.provider_refund, "type": "refund",
            "related_order_id": self.provider_order, "amount": 1234,
            "currency": self.currency_code, "state": state,
        })

    def _http(self, method, url, **kwargs):
        if method == "GET" and url.endswith(f"/api/orders/{self.provider_order}"):
            return self._response({
                "id": self.provider_order, "type": "payment", "state": "completed",
                "amount": 1234, "currency": self.currency_code,
            })
        if method == "POST" and url.endswith(f"/api/orders/{self.provider_order}/refund"):
            self.assertTrue(kwargs["headers"].get("Idempotency-Key"))
            return self._refund("pending")
        if method == "GET" and url.endswith(f"/api/orders/{self.provider_refund}"):
            return self._refund("pending")
        raise AssertionError(f"Unexpected HTTP request: {method} {url}")

    def _run_workers(self, tasks):
        errors, results = [], []

        def run(task):
            try:
                results.append(task())
            except Exception as error:
                errors.append(error)

        workers = [Thread(target=run, args=(task,), name=name, daemon=True)
                   for name, task in tasks]
        # Odoo preload holds this lock while executing post-install tests.
        with patch.object(Registry, "_lock", RLock()), mute_logger("odoo.sql_db"):
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=20)
        self.assertFalse(any(worker.is_alive() for worker in workers), "RPC worker deadlocked")
        self.assertFalse(errors, repr(errors))
        return results

    def _posts(self):
        return [call for call in self.request.call_args_list if call.args[0] == "POST"]

    def test_simultaneous_same_return_dispatches_one_refund(self):
        barrier, replay_finished = Barrier(2), Event()

        def http(method, url, **kwargs):
            if method == "POST":
                self.assertTrue(replay_finished.wait(10), "Replay did not return during dispatch")
            return self._http(method, url, **kwargs)

        def start():
            barrier.wait(timeout=10)
            try:
                return self._start()
            finally:
                replay_finished.set()

        self.request.side_effect = http
        results = self._run_workers([("first", start), ("replay", start)])
        self.assertEqual(len({result["operation_id"] for result in results}), 1)
        self.assertEqual(len(self._posts()), 1)

    def test_competing_returns_reserve_original_payment_once(self):
        barrier, competitor_finished = Barrier(2), Event()

        def http(method, url, **kwargs):
            if method == "POST":
                self.assertTrue(competitor_finished.wait(10), "Competing return was not rejected")
            return self._http(method, url, **kwargs)

        def start():
            barrier.wait(timeout=10)
            try:
                return self._start(str(uuid4()), str(uuid4()))
            except UserError:
                return "rejected"
            finally:
                competitor_finished.set()

        self.request.side_effect = http
        results = self._run_workers([("first-return", start), ("second-return", start)])
        self.assertEqual(results.count("rejected"), 1)
        self.assertEqual(len(self._posts()), 1)

    def test_concurrent_partial_allocations_cannot_exceed_original_balance(self):
        barrier = Barrier(2)

        def http(method, url, **kwargs):
            if method == "POST" and url.endswith(f"/api/orders/{self.provider_order}/refund"):
                return self._response({
                    "id": self.provider_refund, "type": "refund", "state": "pending",
                    "related_order_id": self.provider_order,
                    "amount": kwargs["json"]["amount"], "currency": self.currency_code,
                })
            return self._http(method, url, **kwargs)

        def start(qty, amount):
            snapshot = {
                **self.snapshot, "amount_total": amount,
                "lines": [{**self.snapshot["lines"][0], "qty": qty, "uuid": str(uuid4())}],
            }
            barrier.wait(timeout=10)
            try:
                return self._rpc(
                    "revolut_start_refund", self.session_id, str(uuid4()), str(uuid4()),
                    amount, self.currency_id, snapshot,
                )
            except UserError:
                return "rejected"

        self.request.side_effect = http
        results = self._run_workers([
            ("partial-a", lambda: start(-0.5, -6.17)),
            ("partial-b", lambda: start(-0.501, -6.18)),
        ])
        self.assertEqual(results.count("rejected"), 1)
        self.assertEqual(len(self._posts()), 1)

    def test_stale_poll_cannot_regress_verified_refund(self):
        started = self._start()
        args = (started["operation_id"], self.order_uuid, self.line_uuid)
        stale_read, verified = Event(), Event()

        def http(method, url, **kwargs):
            if method == "GET" and url.endswith(f"/api/orders/{self.provider_refund}"):
                if current_thread().name == "stale":
                    stale_read.set()
                    self.assertTrue(verified.wait(10))
                    return self._refund("pending")
                return self._refund("completed")
            return self._http(method, url, **kwargs)

        def current():
            self.assertTrue(stale_read.wait(10))
            try:
                result = self._rpc("revolut_poll_refund", *args)
                self.assertEqual(result["state"], "verified")
                return result
            finally:
                verified.set()

        self.request.reset_mock()
        self.request.side_effect = http
        self._run_workers([
            ("stale", lambda: self._rpc("revolut_poll_refund", *args)),
            ("current", current),
        ])
        recovered = self._rpc("revolut_find_refund", self.order_uuid, self.line_uuid)
        self.assertEqual(recovered["state"], "verified")
        self.assertFalse(recovered["retry_safe"])
        self.assertFalse(self._posts())

    def test_process_failure_during_refund_dispatch_blocks_replay(self):
        def http(method, url, **kwargs):
            if method == "POST":
                raise RuntimeError("simulated process failure after refund dispatch")
            return self._http(method, url, **kwargs)

        self.request.side_effect = http
        with self.assertRaises(RuntimeError):
            self._start()
        recovered = self._rpc("revolut_find_refund", self.order_uuid, self.line_uuid)
        self.assertTrue(recovered, "Refund claim must survive a rolled-back caller")
        self.assertEqual(recovered["state"], "unresolved")
        self.assertFalse(recovered["retry_safe"])
        replay = self._start()
        self.assertEqual(replay["operation_id"], recovered["operation_id"])
        self.assertEqual(len(self._posts()), 1)

"""Refund RPC safety across real, independently committed transactions."""

import os
from copy import deepcopy
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
        self.secret_reference = "ODOO_REVOLUT_SECRET_REFUND_RACE_" + uuid4().hex.upper()
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
            operation.credential_id.write({"next_refund_discovery_at": "2100-01-01"})
            self.currency_id, self.currency_code = config.currency_id.id, config.currency_id.name
            self.snapshot = {
                "amount_total": -12.34,
                "pricelist_id": order.pricelist_id.id or 0, "fiscal_position_id": False,
                "lines": [{"uuid": str(uuid4()), "product_id": product.id,
                           "qty": -1, "price_unit": 12.34, "discount": 0,
                           "tax_ids": [], "refunded_orderline_id": order.lines.id}],
            }
            env["pos.order"].sync_from_ui([self._draft_values(self.order_uuid, self.line_uuid, self.snapshot)])
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
        # Independently committed fixtures must not be reconciled by another
        # test's Merchant mocks, including the subsequent upgrade pass.
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.merchant.credential"].browse(self.credential_id).write({
                "next_refund_discovery_at": "2100-01-01",
            })
            env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id),
            ]).write({"next_reconcile_at": False})
            cursor.commit()

    def _rpc(self, name, *args):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            result = getattr(env["pos.payment.method"].browse(self.method_id), name)(*args)
            cursor.commit()
            return result

    def _draft_values(self, order_uuid, line_uuid, snapshot, amount=-12.34):
        values = deepcopy(snapshot)
        values.update(
            name=f"Refund concurrency return {order_uuid}", uuid=order_uuid,
            session_id=self.session_id, state="draft", amount_paid=0,
            amount_tax=0, amount_return=0,
            payment_ids=[Command.create({
                "uuid": line_uuid, "payment_method_id": self.method_id,
                "amount": amount, "payment_status": "waiting", "transaction_id": False,
            })],
        )
        values["lines"] = [Command.create(dict(line,
            price_subtotal=float(line["qty"]) * float(line["price_unit"]),
            price_subtotal_incl=float(line["qty"]) * float(line["price_unit"]),
            tax_ids=[Command.set(line["tax_ids"])],
        )) for line in snapshot["lines"]]
        return values

    def _save_native_return(self, order_uuid, line_uuid, snapshot, amount=-12.34):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            existing = env["pos.order"].search([("uuid", "=", order_uuid)])
            if not existing:
                env["pos.order"].sync_from_ui([self._draft_values(order_uuid, line_uuid, snapshot, amount)])
                existing = env["pos.order"].search([("uuid", "=", order_uuid)])
            saved = {
                **env["pos.revolut.payment.operation"]._normalize_financial_snapshot(
                    existing._revolut_order_values(), native_order=True,
                ),
                "amount_total": existing.amount_total,
            }
            cursor.commit()
            return saved

    def _start(self, order_uuid=None, line_uuid=None):
        order_uuid, line_uuid = order_uuid or self.order_uuid, line_uuid or self.line_uuid
        snapshot = self.snapshot
        if order_uuid != self.order_uuid:
            snapshot = deepcopy(self.snapshot)
            snapshot["lines"][0]["uuid"] = str(uuid4())
            snapshot = self._save_native_return(order_uuid, line_uuid, snapshot)
        return self._rpc(
            "revolut_start_refund", self.session_id, order_uuid,
            line_uuid, -12.34, self.currency_id, snapshot,
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
                "amount": 1234, "currency": self.currency_code, "refunded_amount": 0,
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

        identities = [(str(uuid4()), str(uuid4())) for _ in range(2)]
        for order_uuid, line_uuid in identities:
            snapshot = deepcopy(self.snapshot)
            snapshot["lines"][0]["uuid"] = str(uuid4())
            self._save_native_return(order_uuid, line_uuid, snapshot)

        def start(order_uuid, line_uuid):
            barrier.wait(timeout=10)
            try:
                return self._start(order_uuid, line_uuid)
            except UserError:
                return "rejected"
            finally:
                competitor_finished.set()

        self.request.side_effect = http
        results = self._run_workers([
            ("first-return", lambda: start(*identities[0])),
            ("second-return", lambda: start(*identities[1])),
        ])
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

        prepared = []
        # Both requests must survive native quantity precision unchanged. A
        # .501 quantity rounds to .50 in Odoo's two-decimal quantity field and
        # rejects on stale submitted evidence before competing for entitlement.
        for qty, amount in ((-0.5, -6.17), (-0.51, -6.29)):
            snapshot = {
                **self.snapshot, "amount_total": amount,
                "lines": [{**self.snapshot["lines"][0], "qty": qty, "uuid": str(uuid4())}],
            }
            order_uuid, line_uuid = str(uuid4()), str(uuid4())
            saved = self._save_native_return(order_uuid, line_uuid, snapshot, amount)
            self.assertEqual(float(saved["lines"][0]["qty"]), qty)
            self.assertEqual(saved["amount_total"], amount)
            prepared.append((order_uuid, line_uuid, snapshot, amount))

        def start(order_uuid, line_uuid, snapshot, amount):
            barrier.wait(timeout=10)
            try:
                return self._rpc(
                    "revolut_start_refund", self.session_id, order_uuid, line_uuid,
                    amount, self.currency_id, snapshot,
                )
            except UserError:
                return "rejected"

        self.request.side_effect = http
        results = self._run_workers([
            ("partial-a", lambda: start(*prepared[0])),
            ("partial-b", lambda: start(*prepared[1])),
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

    def test_concurrent_odd_partitions_reject_stale_cent_then_exhaust_balance(self):
        barrier = Barrier(2)
        prepared = []
        for quantity, minor in ((0.25, 309), (0.75, 926)):
            snapshot = {
                **self.snapshot, "amount_total": -minor / 100,
                "lines": [{**self.snapshot["lines"][0], "qty": -quantity, "uuid": str(uuid4())}],
            }
            order_uuid, line_uuid = str(uuid4()), str(uuid4())
            self._save_native_return(order_uuid, line_uuid, snapshot, -minor / 100)
            prepared.append((order_uuid, line_uuid, snapshot, minor))

        def http(method, url, **kwargs):
            if method == "POST":
                return self._response({
                    "id": str(uuid4()), "type": "refund", "state": "pending",
                    "related_order_id": self.provider_order,
                    "amount": kwargs["json"]["amount"], "currency": self.currency_code,
                })
            return self._http(method, url, **kwargs)

        def start(candidate):
            order_uuid, line_uuid, snapshot, minor = candidate
            barrier.wait(timeout=10)
            try:
                self._rpc("revolut_start_refund", self.session_id, order_uuid,
                          line_uuid, -minor / 100, self.currency_id, snapshot)
                return (order_uuid, "accepted")
            except UserError:
                return (order_uuid, "rejected")

        self.request.side_effect = http
        results = self._run_workers([(f"odd-partition-{index}", lambda row=row: start(row))
                                     for index, row in enumerate(prepared)])
        self.assertEqual([status for _uuid, status in results].count("rejected"), 1)
        self.assertEqual(len(self._posts()), 1)
        rejected_uuid = next(uuid for uuid, status in results if status == "rejected")
        order_uuid, line_uuid, snapshot, stale_minor = next(row for row in prepared if row[0] == rejected_uuid)
        sources = self._rpc("revolut_refund_sources", self.session_id, self.currency_id, snapshot)
        corrected_minor = sources[0]["return_total_minor"]
        self.assertEqual(corrected_minor, stale_minor - 1)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].search([("uuid", "=", order_uuid)])
            order.payment_ids.write({"amount": -corrected_minor / 100})
            cursor.commit()
        snapshot["amount_total"] = -corrected_minor / 100
        self._rpc("revolut_start_refund", self.session_id, order_uuid,
                  line_uuid, -corrected_minor / 100, self.currency_id, snapshot)
        self.assertEqual(sum(call.kwargs["json"]["amount"] for call in self._posts()), 1234)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            claims = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id), ("state", "!=", "failed"),
            ])
            self.assertEqual(sum(claims.mapped("return_total_minor")), 1234)

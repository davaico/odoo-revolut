"""Manager native-completion RPCs race in independent committed transactions."""
import os
from threading import Barrier, Event
from time import monotonic
from unittest.mock import Mock, patch
from uuid import uuid4

from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import Command, SUPERUSER_ID, api, fields
from odoo.exceptions import UserError
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .test_revolut_refund_concurrency import TestRevolutRefundConcurrency


@tagged("post_install", "-at_install")
class TestExternalNativeConcurrency(TransactionCase):
    _run_workers = TestRevolutRefundConcurrency._run_workers

    def setUp(self):
        super().setUp()
        self.registry = self.env.registry
        self.context = {"allowed_company_ids": [self.env.company.id], "generate_pdf": False}
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            managers = [new_test_user(
                env, login=f"external_native_race_{uuid4()}",
                groups="base.group_user,point_of_sale.group_pos_manager",
                company_id=env.company.id, company_ids=[Command.set([env.company.id])],
            ) for _index in range(2)]
            method = env["pos.payment.method"].create({
                "name": "Native external refund race", "payment_method_type": "terminal",
                "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
                "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_NATIVE_RACE_" + uuid4().hex.upper(),
            })
            config = env["pos.config"].create({
                "name": "Native external refund race", "auto_validate_terminal_payment": True,
                "payment_method_ids": [Command.link(method.id)],
                "revolut_user_ids": [Command.set([manager.id for manager in managers])],
            })
            session = env["pos.session"].create({
                "config_id": config.id, "state": "opened", "update_stock_at_closing": False,
            })
            product = env["product.product"].create({
                "name": "Native external race inventory", "type": "consu", "is_storable": True,
                "available_in_pos": True, "list_price": 12.34, "taxes_id": [Command.clear()],
            })
            original_uuid, payment_uuid, provider_payment = (str(uuid4()) for _index in range(3))
            values = {
                "name": "Native external race original", "session_id": session.id,
                "uuid": original_uuid, "state": "paid", "amount_total": 12.34,
                "pricelist_id": config.pricelist_id.id, "amount_tax": 0,
                "amount_paid": 12.34, "amount_return": 0,
                "lines": [Command.create({
                    "product_id": product.id, "qty": 1, "price_unit": 12.34,
                    "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
                    "tax_ids": [Command.set([])], "uuid": str(uuid4()),
                })],
                "payment_ids": [Command.create({
                    "payment_method_id": method.id, "amount": 12.34,
                    "uuid": payment_uuid, "payment_status": "done", "transaction_id": provider_payment,
                })],
            }
            source = env["pos.revolut.payment.operation"].create({
                "payment_method_id": method.id, "company_id": env.company.id,
                "pos_config_id": config.id, "pos_session_id": session.id,
                "order_uuid": original_uuid, "payment_line_uuid": payment_uuid,
                "amount": 12.34, "amount_minor": 1234,
                "currency_id": config.currency_id.id, "currency_code": config.currency_id.name,
                "environment": "sandbox", "location_id": method.revolut_location_id,
                "terminal_id": method.revolut_terminal_id, "fulfilment_type": "eat_in",
                "secret_reference": method.revolut_secret_reference, "state": "verified",
                "revolut_order_id": str(uuid4()), "revolut_payment_intent_id": str(uuid4()),
                "revolut_payment_id": provider_payment,
                "financial_snapshot": env["pos.revolut.payment.operation"]._normalize_financial_snapshot(values),
            })
            original = env["pos.order"].create(values)
            original._create_order_picking()
            self.assertEqual(set(original.picking_ids.mapped("state")), {"done"})
            self.assertEqual(source.pos_order_id, original)
            self.source_id, self.credential_id = source.id, source.credential_id.id
            self.original_id, self.original_line_id = original.id, original.lines.id
            self.session_id, self.method_id = session.id, method.id
            self.currency_id = source.currency_id.id
            self.secret_reference = source.secret_reference
            self.manager_ids = [manager.id for manager in managers]
            source.credential_id.write({"next_refund_discovery_at": "2100-01-01"})
            cursor.commit()
        self.addCleanup(self._unschedule)
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Native manager completion must never contact Merchant HTTP"),
        ))

    def _unschedule(self):
        # Committed fixture history cannot participate in later tests' provider
        # mocks or the subsequent addon upgrade phase.
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.revolut.merchant.credential"].browse(self.credential_id).write({
                "next_refund_discovery_at": "2100-01-01",
            })
            env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id),
            ]).write({"next_reconcile_at": False})
            cursor.commit()

    def _external_refund(self, minor=1234, state="verified"):
        # Financial evidence is the pre-agreed mocked seam. These races begin
        # after the provider refund has already completed and been imported.
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            source = env["pos.revolut.payment.operation"].browse(self.source_id)
            refund = env["pos.revolut.refund.operation"].create({
                "origin": "external", "original_operation_id": source.id,
                "pos_session_id": source.pos_session_id.id,
                "amount": minor / 100, "amount_minor": minor, "currency_id": source.currency_id.id,
                "state": state, "provider_state": "completed" if state == "verified" else state,
                "verified_at": fields.Datetime.now() if state == "verified" else False,
                "revolut_order_id": str(uuid4()), "next_reconcile_at": False,
            })
            identity = refund.id
            cursor.commit()
            return identity

    def _rpc(self, manager_id, refund_id, method, *args):
        return self._model_rpc(manager_id, "pos.revolut.refund.operation", method, [[refund_id], *args])

    def _model_rpc(self, manager_id, model, method, args):
        # The browser/server transaction may encounter PostgreSQL's stale
        # snapshot guard. Retry the public call in a fresh transaction, exactly
        # as reconnecting and reopening the recorded workflow would do.
        for attempt in range(3):
            try:
                with self.registry.cursor() as cursor:
                    env = api.Environment(cursor, manager_id, self.context)
                    result = call_kw(env[model], method, args, {
                        "context": self.context,
                    })
                    cursor.commit()
                    return result
            except (SerializationFailure, DeadlockDetected):
                if attempt == 2:
                    raise

    def _prepare(self, manager_id, refund_id, quantity=1):
        return self._rpc(manager_id, refund_id, "action_prepare_native_return", [{
            "original_line_id": self.original_line_id, "quantity": quantity,
        }])

    def _native_draft(self, quantity, minor):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            original = env["pos.order"].browse(self.original_id)
            order_uuid, payment_uuid = str(uuid4()), str(uuid4())
            values = {
                "name": "Competing native refund", "uuid": order_uuid,
                "session_id": self.session_id, "state": "draft",
                "amount_total": -original.currency_id.round(12.34 * quantity),
                "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
                "pricelist_id": original.pricelist_id.id,
                "lines": [Command.create({
                    "product_id": original.lines.product_id.id, "qty": -quantity,
                    "price_unit": 12.34, "price_subtotal": -12.34 * quantity,
                    "price_subtotal_incl": -12.34 * quantity,
                    "tax_ids": [Command.set([])], "uuid": str(uuid4()),
                    "refunded_orderline_id": self.original_line_id,
                })],
                "payment_ids": [Command.create({
                    "payment_method_id": self.method_id, "amount": -minor / 100,
                    "uuid": payment_uuid, "payment_status": "waiting",
                })],
            }
            saved = env["pos.order"].sync_from_ui([values])
            order = env["pos.order"].browse(next(row["id"] for row in saved["pos.order"]
                                               if row["uuid"] == order_uuid))
            snapshot = env["pos.revolut.payment.operation"]._normalize_financial_snapshot(
                order._revolut_order_values(), native_order=True,
            )
            snapshot["amount_total"] = order.amount_total
            cursor.commit()
            return order_uuid, payment_uuid, snapshot

    @staticmethod
    def _response(payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _wait_for_session_mutations(self, cursor, count=2):
        deadline = monotonic() + 10
        waiting = 0
        while monotonic() < deadline:
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute("""
                SELECT COUNT(*) FROM pg_stat_activity activity
                WHERE activity.datname = current_database()
                  AND activity.wait_event_type = 'Lock'
                  AND EXISTS (
                      SELECT 1 FROM pg_locks locks
                      WHERE locks.pid = activity.pid
                        AND locks.relation = 'pos_session'::regclass
                        AND locks.mode = 'RowExclusiveLock'
                  )
            """)
            waiting = cursor.fetchone()[0]
            if waiting >= count:
                return
            Event().wait(0.05)
        self.assertGreaterEqual(waiting, count, "Public mutations did not share session locking")

    def test_two_managers_prepare_one_external_refund_draft_and_payment(self):
        refund_id = self._external_refund()
        barrier = Barrier(2)

        def prepare(manager_id):
            barrier.wait(timeout=10)
            return self._prepare(manager_id, refund_id)

        results = self._run_workers([
            (f"native-preparer-{index}", lambda manager=manager: prepare(manager))
            for index, manager in enumerate(self.manager_ids)
        ])
        order_id = results[0]["res_id"]
        self.assertEqual({result["res_id"] for result in results}, {order_id})
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            orders = env["pos.order"].search([
                ("lines.refunded_orderline_id", "=", self.original_line_id),
            ])
            self.assertEqual(orders.ids, [order_id])
            self.assertEqual(len(orders.payment_ids), 1)
            self.assertEqual(refund.pos_payment_id, orders.payment_ids)
            self.assertEqual(orders.lines.qty, -1)
            self.assertFalse(orders.picking_ids)
            self.assertEqual(refund.origin, "external")
            self.assertEqual(refund.amount_minor, 1234)
        self.request.assert_not_called()

    def test_distinct_external_refunds_cannot_reserve_overlapping_original_quantities(self):
        refunds = [self._external_refund(617) for _index in range(2)]
        barrier = Barrier(2)

        def prepare(manager_id, refund_id):
            barrier.wait(timeout=10)
            try:
                return self._prepare(manager_id, refund_id, 0.75)
            except UserError:
                return "rejected"

        results = self._run_workers([
            (f"quantity-preparer-{index}", lambda manager=manager, refund=refund: prepare(manager, refund))
            for index, (manager, refund) in enumerate(zip(self.manager_ids, refunds))
        ])
        self.assertEqual(results.count("rejected"), 1)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            records = env["pos.revolut.refund.operation"].browse(refunds)
            self.assertEqual(len(records.pos_order_id), 1)
            self.assertEqual(len(records.pos_payment_id), 1)
            self.assertEqual(sum(records.pos_order_id.lines.mapped("qty")), -0.75)
            self.assertEqual(sum(records.mapped("amount_minor")), 1234)
            self.assertEqual(set(records.mapped("state")), {"verified"})
            orders = env["pos.order"].search([
                ("lines.refunded_orderline_id", "=", self.original_line_id),
            ])
            self.assertEqual(orders, records.pos_order_id)
        self.request.assert_not_called()

    def test_two_managers_validate_one_native_stock_return_once(self):
        refund_id = self._external_refund()
        order_id = self._prepare(self.manager_ids[0], refund_id)["res_id"]
        barrier = Barrier(2)

        def validate(manager_id):
            barrier.wait(timeout=10)
            return self._rpc(manager_id, refund_id, "action_validate_native_return")

        results = self._run_workers([
            (f"native-validator-{index}", lambda manager=manager: validate(manager))
            for index, manager in enumerate(self.manager_ids)
        ])
        self.assertEqual({result["res_id"] for result in results}, {order_id})
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            order = env["pos.order"].browse(order_id)
            self.assertEqual(order.state, "paid")
            self.assertEqual(refund.native_reconciliation_status, "native_completed")
            self.assertEqual(len(order.payment_ids), 1)
            self.assertEqual(order.payment_ids.amount, -12.34)
            self.assertEqual(order.payment_ids.revolut_refund_operation_id, refund)
            self.assertEqual(len(order.picking_ids), 1)
            self.assertEqual(order.picking_ids.state, "done")
            self.assertEqual(sum(order.picking_ids.move_ids.mapped("quantity")), 1)
            self.assertEqual(order.picking_ids.move_ids.origin_returned_move_id,
                             env["pos.order"].browse(self.original_id).picking_ids.move_ids)
            evidence = (order.picking_ids.ids, order.picking_ids.move_ids.ids,
                        order.payment_ids.ids, refund.native_reconciled_at)
        self._rpc(self.manager_ids[1], refund_id, "action_validate_native_return")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(order_id)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            self.assertEqual((order.picking_ids.ids, order.picking_ids.move_ids.ids,
                              order.payment_ids.ids, refund.native_reconciled_at), evidence)
        self.request.assert_not_called()

    def test_native_reservation_and_external_association_conserve_last_quantities(self):
        refund_id = self._external_refund(617)
        order_uuid, payment_uuid, snapshot = self._native_draft(0.75, 617)
        barrier = Barrier(2)
        self.enterContext(patch.dict(os.environ, {self.secret_reference: "test-only"}))
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            source = env["pos.revolut.payment.operation"].browse(self.source_id)
            provider_order, currency = source.revolut_order_id, source.currency_id.name
        provider_refund = str(uuid4())

        def http(method, url, **kwargs):
            if method == "GET" and url.endswith(f"/api/orders/{provider_order}"):
                return self._response({"id": provider_order, "type": "payment", "state": "completed",
                                       "amount": 1234, "currency": currency, "refunded_amount": 617})
            if method == "POST" and url.endswith(f"/api/orders/{provider_order}/refund"):
                self.assertEqual(kwargs["json"]["amount"], 617)
                return self._response({"id": provider_refund, "type": "refund", "state": "pending",
                                       "related_order_id": provider_order, "amount": 617, "currency": currency})
            raise AssertionError(f"Unexpected Merchant request: {method} {url}")

        def reserve():
            barrier.wait(timeout=10)
            try:
                return self._model_rpc(self.manager_ids[0], "pos.payment.method", "revolut_start_refund", [
                    [self.method_id], self.session_id, order_uuid, payment_uuid, -6.17,
                    self.currency_id, snapshot,
                ])
            except UserError:
                return "rejected"

        def associate():
            barrier.wait(timeout=10)
            try:
                return self._prepare(self.manager_ids[1], refund_id, 0.75)
            except UserError:
                return "rejected"

        self.request.side_effect = http
        results = self._run_workers([("native-reservation", reserve), ("external-association", associate)])
        self.assertEqual(results.count("rejected"), 1)
        posts = [call for call in self.request.call_args_list if call.args[0] == "POST"]
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refunds = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id), ("state", "!=", "failed"),
            ])
            self.assertLessEqual(sum(refunds.mapped("amount_minor")), 1234)
            allocated = refunds.filtered("order_uuid")
            self.assertEqual(len(allocated), 1)
            self.assertEqual(sum(float(line["qty"]) for line in allocated.financial_snapshot["lines"]), -0.75)
            self.assertEqual(len(posts), int(allocated.origin == "odoo"))
            self.assertEqual(env["pos.revolut.refund.operation"].browse(refund_id).state, "verified")
            self.assertFalse(refunds.pos_order_id.picking_ids)
            self.assertFalse(refunds.pos_order_id.account_move)

    def test_historical_recovery_and_closure_keep_verified_refund_recoverable(self):
        order_uuid, payment_uuid, snapshot = self._native_draft(1, 1234)
        snapshot.pop("amount_total")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            env["pos.order"].search([("uuid", "=", order_uuid)]).unlink()
            source = env["pos.revolut.payment.operation"].browse(self.source_id)
            refund = env["pos.revolut.refund.operation"].create({
                "original_operation_id": source.id, "pos_session_id": self.session_id,
                "order_uuid": order_uuid, "payment_line_uuid": payment_uuid,
                "amount": 12.34, "amount_minor": 1234, "currency_id": source.currency_id.id,
                "state": "verified", "provider_state": "completed", "verified_at": fields.Datetime.now(),
                "revolut_order_id": str(uuid4()), "financial_snapshot": snapshot,
                "return_total_minor": 1234, "next_reconcile_at": False,
            })
            # A historical orphan represents a deployment predating closure
            # protection; public closure cannot create this fixture today.
            env.flush_all()
            cursor.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session_id])
            env["pos.session"].browse(self.session_id).invalidate_recordset()
            session = env["pos.session"].create({"config_id": source.pos_config_id.id, "state": "opened"})
            refund_id, current_session_id = refund.id, session.id
            cursor.commit()
        barrier = Barrier(2)

        def recover():
            barrier.wait(timeout=10)
            try:
                return self._rpc(self.manager_ids[0], refund_id, "action_recover_return")
            except UserError:
                return "rejected"

        def close():
            barrier.wait(timeout=10)
            try:
                self._model_rpc(self.manager_ids[1], "pos.session", "write", [
                    [current_session_id], {"state": "closing_control"},
                ])
                return "closed"
            except UserError:
                return "rejected"

        results = self._run_workers([("native-recovery", recover), ("session-closure", close)])
        self.assertEqual(results.count("rejected"), 1)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            session = env["pos.session"].browse(current_session_id)
            self.assertEqual(refund.state, "verified")
            self.assertEqual(refund.pos_session_id.id, self.session_id)
            if refund.pos_order_id:
                self.assertEqual(session.state, "opened")
                self.assertEqual(refund.pos_order_id.session_id, session)
            else:
                self.assertEqual(session.state, "closing_control")
                session.write({"state": "opened"})
                cursor.commit()
        action = self._rpc(self.manager_ids[0], refund_id, "action_recover_return")
        self.assertEqual(self._rpc(self.manager_ids[1], refund_id, "action_recover_return"), action)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            orders = env["pos.order"].search([("uuid", "=", order_uuid)])
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            self.assertEqual(len(orders), 1)
            self.assertEqual(orders.state, "draft")
            self.assertEqual(orders.lines.qty, -1)
            self.assertEqual(refund.pos_payment_id, orders.payment_ids)
            self.assertEqual(orders.payment_ids.amount, -12.34)
            self.assertFalse(orders.picking_ids)
            self.assertFalse(orders.account_move)
        self.request.assert_not_called()

    def test_discovery_during_reservation_releases_stale_claim_and_dispatches_only_remaining_cents(self):
        order_uuid, payment_uuid, snapshot = self._native_draft(1, 1234)
        original_read, discovery_finished = Event(), Event()
        self.enterContext(patch.dict(os.environ, {self.secret_reference: "test-only"}))
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            source = env["pos.revolut.payment.operation"].browse(self.source_id)
            provider_order, currency = source.revolut_order_id, source.currency_id.name
            source.credential_id.write({"next_refund_discovery_at": False})
            cron_id = env.ref("pos_revolut.ir_cron_reconcile_refunds").id
            cursor.commit()
        external_reference, native_reference = str(uuid4()), str(uuid4())
        candidate = {
            "id": external_reference, "type": "refund", "state": "completed",
            "related_order_id": provider_order, "amount": 617, "currency": currency,
            "created_at": "2026-10-01T12:00:00Z",
        }

        def http(method, url, **kwargs):
            if method == "GET" and url.endswith("/api/orders"):
                # The native claim is durable and its GET preflight is still
                # in flight. Imported money invalidates it before dispatch.
                return self._response({"orders": [candidate]})
            if method == "GET" and url.endswith(f"/api/orders/{external_reference}"):
                return self._response(candidate)
            if method == "GET" and url.endswith(f"/api/orders/{provider_order}"):
                original_read.set()
                self.assertTrue(discovery_finished.wait(10), "External discovery did not finish")
                return self._response({"id": provider_order, "type": "payment", "state": "completed",
                                       "amount": 1234, "currency": currency, "refunded_amount": 617})
            if method == "POST" and url.endswith(f"/api/orders/{provider_order}/refund"):
                self.assertEqual(kwargs["json"]["amount"], 617)
                self.assertTrue(kwargs["headers"].get("Idempotency-Key"))
                return self._response({"id": native_reference, "type": "refund", "state": "pending",
                                       "related_order_id": provider_order, "amount": 617, "currency": currency})
            raise AssertionError(f"Unexpected Merchant request: {method} {url}")

        def start(identity, minor):
            selected_order, selected_payment, selected_snapshot = identity
            return self._model_rpc(self.manager_ids[0], "pos.payment.method", "revolut_start_refund", [
                [self.method_id], self.session_id, selected_order, selected_payment,
                -minor / 100, self.currency_id, selected_snapshot,
            ])

        def discover():
            try:
                self.assertTrue(original_read.wait(10), "Native reservation did not reach provider preflight")
                return self._model_rpc(SUPERUSER_ID, "ir.cron", "method_direct_trigger", [[cron_id]])
            finally:
                discovery_finished.set()

        self.request.side_effect = http
        results = self._run_workers([
            ("native-stale-reservation", lambda: start((order_uuid, payment_uuid, snapshot), 1234)),
            ("external-provider-discovery", discover),
        ])
        stale = next(result for result in results if isinstance(result, dict) and "operation_id" in result)
        self.assertEqual(stale["state"], "failed")
        self.assertFalse([call for call in self.request.call_args_list if call.args[0] == "POST"])
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            imported = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id), ("origin", "=", "external"),
            ])
            self.assertEqual(len(imported), 1, (results, self.request.call_args_list))
            self.assertEqual(imported.revolut_order_id, external_reference)
            self.assertEqual(imported.amount_minor, 617)
            self.assertEqual(imported.state, "verified")
            self.assertFalse(imported.pos_order_id)
            self.assertFalse(imported.financial_snapshot)
        remaining = self._native_draft(0.5, 617)
        started = start(remaining, 617)
        self.assertEqual(started["state"], "pending")
        self.assertEqual(start(remaining, 617)["operation_id"], started["operation_id"])
        posts = [call for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].kwargs["json"]["amount"], 617)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            protected = env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", self.source_id), ("state", "!=", "failed"),
            ])
            self.assertEqual(sum(protected.mapped("amount_minor")), 1234)
            self.assertEqual(set(protected.mapped("origin")), {"external", "odoo"})
            self.assertFalse(protected.pos_order_id.picking_ids)
            self.assertFalse(protected.pos_order_id.account_move)
        exhausted = self._native_draft(0.5, 617)
        with self.assertRaisesRegex(UserError, "balance"):
            start(exhausted, 617)
        self.assertEqual(len([call for call in self.request.call_args_list if call.args[0] == "POST"]), 1)

    def test_pending_status_completion_and_finalization_create_native_effects_once(self):
        refund_id = self._external_refund(state="pending")
        order_id = self._prepare(self.manager_ids[0], refund_id)["res_id"]
        provider_read, validation_finished = Event(), Event()
        self.enterContext(patch.dict(os.environ, {self.secret_reference: "test-only"}))
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            reference, parent, currency = refund.revolut_order_id, refund.original_operation_id.revolut_order_id, refund.currency_id.name

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith(f"/api/orders/{reference}"))
            provider_read.set()
            self.assertTrue(validation_finished.wait(10), "Pending native validation did not return")
            return self._response({"id": reference, "type": "refund", "state": "completed",
                                   "related_order_id": parent, "amount": 1234, "currency": currency})

        def finalize():
            self.assertTrue(provider_read.wait(10))
            try:
                with self.assertRaises(UserError):
                    self._rpc(self.manager_ids[1], refund_id, "action_validate_native_return")
                with self.registry.cursor() as cursor:
                    env = api.Environment(cursor, SUPERUSER_ID, self.context)
                    order = env["pos.order"].browse(order_id)
                    self.assertEqual(order.state, "draft")
                    self.assertFalse(order.picking_ids)
                    self.assertEqual(order.payment_ids.payment_status, "waiting")
            finally:
                validation_finished.set()

        self.request.side_effect = http
        self._run_workers([
            ("provider-completion", lambda: self._rpc(self.manager_ids[0], refund_id, "action_check_status")),
            ("pending-finalization", finalize),
        ])
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Resuming issued money must never contact Merchant HTTP")
        self._rpc(self.manager_ids[0], refund_id, "action_prepare_native_return")
        self._rpc(self.manager_ids[1], refund_id, "action_validate_native_return")
        self._rpc(self.manager_ids[0], refund_id, "action_validate_native_return")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            order = env["pos.order"].browse(order_id)
            self.assertEqual(refund.state, "verified")
            self.assertEqual(refund.native_reconciliation_status, "native_completed")
            self.assertEqual(order.state, "paid")
            self.assertEqual(len(order.payment_ids), 1)
            self.assertEqual(order.payment_ids.transaction_id, reference)
            self.assertEqual(len(order.picking_ids), 1)
            self.assertEqual(order.picking_ids.state, "done")
            self.assertEqual(sum(order.picking_ids.move_ids.mapped("quantity")), 1)
        self.request.assert_not_called()

    def test_status_application_and_finalization_contend_on_session_before_native_effects(self):
        refund_id = self._external_refund(state="pending")
        order_id = self._prepare(self.manager_ids[0], refund_id)["res_id"]
        session_locked, provider_read = Event(), Event()
        self.enterContext(patch.dict(os.environ, {self.secret_reference: "test-only"}))
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            reference = refund.revolut_order_id
            parent, currency = refund.original_operation_id.revolut_order_id, refund.currency_id.name

        def http(method, url, **kwargs):
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith(f"/api/orders/{reference}"))
            provider_read.set()
            return self._response({"id": reference, "type": "refund", "state": "completed",
                                   "related_order_id": parent, "amount": 1234, "currency": currency})

        def hold_session():
            with self.registry.cursor() as cursor:
                cursor.execute("SELECT id FROM pos_session WHERE id = %s FOR UPDATE", [self.session_id])
                session_locked.set()
                # Observe real PostgreSQL waiters, not a substituted module
                # helper. Both public actions must reach the same session
                # boundary before either can apply status/native effects.
                self._wait_for_session_mutations(cursor)
                cursor.commit()
            return "released"

        def status():
            self.assertTrue(session_locked.wait(10))
            return self._rpc(self.manager_ids[0], refund_id, "action_check_status")

        def finalize():
            self.assertTrue(session_locked.wait(10))
            self.assertTrue(provider_read.wait(10))
            try:
                return self._rpc(self.manager_ids[1], refund_id, "action_validate_native_return")
            except UserError:
                return "pending"

        self.request.side_effect = http
        self._run_workers([
            ("session-lock-holder", hold_session), ("authoritative-status-application", status),
            ("contending-native-finalization", finalize),
        ])
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Native resume must never contact Merchant HTTP")
        self._rpc(self.manager_ids[0], refund_id, "action_prepare_native_return")
        self._rpc(self.manager_ids[1], refund_id, "action_validate_native_return")
        self._rpc(self.manager_ids[0], refund_id, "action_validate_native_return")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            refund = env["pos.revolut.refund.operation"].browse(refund_id)
            order = env["pos.order"].browse(order_id)
            self.assertEqual(refund.state, "verified")
            self.assertEqual(refund.native_reconciliation_status, "native_completed")
            self.assertEqual(order.state, "paid")
            self.assertEqual(len(order.payment_ids), 1)
            self.assertEqual(order.payment_ids.transaction_id, reference)
            self.assertEqual(len(order.picking_ids), 1)
            self.assertEqual(order.picking_ids.state, "done")
            self.assertEqual(sum(order.picking_ids.move_ids.mapped("quantity")), 1)
        self.request.assert_not_called()

    def test_parent_commands_transfer_lines_and_payments_across_sessions_without_deadlock(self):
        for field, model, owner_field, ordinary_payment in (
            ("lines", "pos.order.line", "order_id", False),
            ("payment_ids", "pos.payment", "pos_order_id", False),
            ("payment_ids", "pos.payment", "pos_order_id", True),
        ):
            for kind in ("link", "set"):
                with self.subTest(field=field, command=kind, ordinary_payment=ordinary_payment):
                    with self.registry.cursor() as cursor:
                        env = api.Environment(cursor, SUPERUSER_ID, self.context)
                        original = env["pos.order"].browse(self.original_id)
                        method_id, first_session_id = self.method_id, self.session_id
                        if ordinary_payment:
                            ordinary_method = env['pos.payment.method'].create({'name': 'Ordinary parent transfer'})
                            first_config = env['pos.config'].create({
                                'name': f'Ordinary owner transfer {kind}',
                                'payment_method_ids': [Command.link(ordinary_method.id)],
                                'revolut_user_ids': [Command.set(self.manager_ids)],
                            })
                            first_session = env['pos.session'].create({'config_id': first_config.id, 'state': 'opened'})
                            method_id, first_session_id = ordinary_method.id, first_session.id
                        config = original.config_id if field == "lines" and kind == "set" else env["pos.config"].create({
                            "name": f"Opposite owner transfer {field} {kind}",
                            "auto_validate_terminal_payment": True,
                            "payment_method_ids": [Command.link(method_id)],
                            "revolut_user_ids": [Command.set(self.manager_ids)],
                        })
                        # Pinned native line.write reads config fields on its
                        # entire recordset during SET. Use historical and
                        # current sessions of the same register for that shape.
                        second_session = env["pos.session"].create({
                            "config_id": config.id,
                            "state": "closed" if field == "lines" and kind == "set" else "opened",
                        })
                        session_ids = [first_session_id, second_session.id]
                        orders = env["pos.order"]
                        for session_id in session_ids:
                            session = env["pos.session"].browse(session_id)
                            orders |= env["pos.order"].create({
                                "name": f"Ordinary transfer draft {uuid4()}", "uuid": str(uuid4()),
                                "session_id": session.id, "state": "draft", "amount_total": 12.34,
                                "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
                                "pricelist_id": session.config_id.pricelist_id.id,
                                "lines": [Command.create({
                                    "product_id": original.lines.product_id.id, "qty": 1,
                                    "price_unit": 12.34, "price_subtotal": 12.34,
                                    "price_subtotal_incl": 12.34, "tax_ids": [Command.set([])],
                                    "uuid": str(uuid4()),
                                })],
                                "payment_ids": [Command.create({
                                    "payment_method_id": method_id, "amount": 12.34,
                                    "payment_status": False if ordinary_payment else "waiting", "uuid": str(uuid4()),
                                })],
                            })
                        order_ids = orders.ids
                        child_ids = [order[field].id for order in orders]
                        line_ids, payment_ids = orders.lines.ids, orders.payment_ids.ids
                        cursor.commit()
                    session_locked = Event()

                    def hold_sessions():
                        with self.registry.cursor() as cursor:
                            cursor.execute("SELECT id FROM pos_session WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
                                           [session_ids])
                            session_locked.set()
                            self._wait_for_session_mutations(cursor)
                            cursor.commit()

                    def transfer(index):
                        self.assertTrue(session_locked.wait(10))
                        commands = [Command.link(child_ids[1 - index])] if kind == "link" else [Command.set(child_ids)]
                        # Repeatable-read conflicts retry with fresh evidence.
                        # A real acquisition inversion must remain visible as
                        # DeadlockDetected rather than being swallowed here.
                        for attempt in range(3):
                            try:
                                with self.registry.cursor() as cursor:
                                    env = api.Environment(cursor, self.manager_ids[index], self.context)
                                    result = call_kw(env["pos.order"], "write", [[order_ids[index]], {field: commands}],
                                                     {"context": self.context})
                                    cursor.commit()
                                    return result
                            except SerializationFailure:
                                if attempt == 2:
                                    raise
                            except UserError as error:
                                if field != 'payment_ids' or ordinary_payment:
                                    raise
                                self.assertEqual(str(error), 'Keep the original saved Revolut tender identity.')
                                return 'protected'

                    results = self._run_workers([
                        ("owner-session-holder", hold_sessions),
                        ("first-parent-transfer", lambda: transfer(0)),
                        ("opposite-parent-transfer", lambda: transfer(1)),
                    ])
                    protected_payment = field == 'payment_ids' and not ordinary_payment
                    self.assertEqual(results.count('protected'), 2 if protected_payment else 0)
                    with self.registry.cursor() as cursor:
                        env = api.Environment(cursor, SUPERUSER_ID, self.context)
                        orders = env["pos.order"].browse(order_ids)
                        records = env[model].browse(child_ids).exists()
                        self.assertEqual(set(records.ids), set(child_ids))
                        self.assertEqual(set(orders.lines.ids), set(line_ids))
                        self.assertEqual(set(orders.payment_ids.ids), set(payment_ids))
                        self.assertEqual(sum(orders.lines.mapped("qty")), 2)
                        self.assertEqual(sum(orders.payment_ids.mapped("amount")), 24.68)
                        self.assertTrue(all(record[owner_field] in orders for record in records))
                        if protected_payment:
                            # Persisted waiting tenders now carry protected
                            # identity even before their first operation. Both
                            # opposing transfers roll back without deadlocking.
                            for child_id, order_id in zip(child_ids, order_ids):
                                self.assertEqual(env[model].browse(child_id)[owner_field].id, order_id)
                        self.assertEqual(set(orders.mapped("state")), {"draft"})
                        self.assertFalse(orders.picking_ids)
                        self.assertFalse(orders.account_move)
        self.request.assert_not_called()

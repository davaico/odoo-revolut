"""Manager native-completion RPCs race in independent committed transactions."""
from threading import Barrier
from unittest.mock import patch
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
                    "tax_ids": [Command.clear()], "uuid": str(uuid4()),
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

    def _external_refund(self, minor=1234):
        # Financial evidence is the pre-agreed mocked seam. These races begin
        # after the provider refund has already completed and been imported.
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            source = env["pos.revolut.payment.operation"].browse(self.source_id)
            refund = env["pos.revolut.refund.operation"].create({
                "origin": "external", "original_operation_id": source.id,
                "pos_session_id": source.pos_session_id.id,
                "amount": minor / 100, "amount_minor": minor, "currency_id": source.currency_id.id,
                "state": "verified", "provider_state": "completed", "verified_at": fields.Datetime.now(),
                "revolut_order_id": str(uuid4()), "next_reconcile_at": False,
            })
            identity = refund.id
            cursor.commit()
            return identity

    def _rpc(self, manager_id, refund_id, method, *args):
        # The browser/server transaction may encounter PostgreSQL's stale
        # snapshot guard. Retry the public call in a fresh transaction, exactly
        # as reconnecting and reopening the recorded workflow would do.
        for attempt in range(3):
            try:
                with self.registry.cursor() as cursor:
                    env = api.Environment(cursor, manager_id, self.context)
                    result = call_kw(env["pos.revolut.refund.operation"], method, [[refund_id], *args], {
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

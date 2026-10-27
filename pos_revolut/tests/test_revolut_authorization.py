import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user

from .authorization_fixtures import authorized_start, financial_posts, native_products


class TestRevolutAuthorization(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({
            "name": "Revolut authorization other company",
        })
        cls.manager = new_test_user(
            cls.env, login="revolut_authorization_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.other_manager = new_test_user(
            cls.env, login="revolut_authorization_other_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=cls.other_company.id,
            company_ids=[Command.set([cls.other_company.id])],
        )
        cls.multi_company_manager = new_test_user(
            cls.env, login="revolut_authorization_multi_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id, cls.other_company.id])],
        )
        cls.cashier = new_test_user(
            cls.env, login="revolut_authorization_cashier",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.method = cls.env["pos.payment.method"].create({
            "name": "Revolut authorization test",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()),
            "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_AUTHORIZATION_TEST",
        })
        cls.config = cls.env["pos.config"].create({
            "name": "Revolut authorization test",
            "payment_method_ids": [Command.link(cls.method.id)],
            "auto_validate_terminal_payment": True,
            "revolut_user_ids": [Command.set((cls.manager | cls.multi_company_manager | cls.cashier).ids)],
        })
        cls.product = native_products(cls.env, cls.config)
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id, "state": "opened",
        })
        cls.operation_values = {
            "payment_method_id": cls.method.id,
            "company_id": cls.company.id,
            "pos_config_id": cls.config.id,
            "pos_session_id": cls.session.id,
            "order_uuid": str(uuid4()),
            "payment_line_uuid": str(uuid4()),
            "amount": 12.34,
            "amount_minor": 1234,
            "currency_id": cls.session.currency_id.id,
            "currency_code": cls.session.currency_id.name,
            "environment": "sandbox",
            "location_id": cls.method.revolut_location_id,
            "terminal_id": cls.method.revolut_terminal_id,
            "fulfilment_type": "eat_in",
            "secret_reference": "ODOO_REVOLUT_SECRET_AUTHORIZATION_TEST",
            "state": "unresolved",
        }
        cls.operation = cls.env["pos.revolut.payment.operation"].sudo().create(
            cls.operation_values
        )
        # The creator's company must not override the operation's ownership.
        cls.dispatch = cls.env["pos.revolut.payment.dispatch"].with_user(
            cls.other_manager
        ).sudo().create({
            "operation_id": cls.operation.id,
            "action": "create_order",
            "outcome": "succeeded",
            "provider_reference": str(uuid4()),
        })
        cls.order_lock = cls.env["pos.revolut.order.lock"].sudo().create({
            "company_id": cls.company.id,
            "order_uuid": cls.operation.order_uuid,
        })

    def test_foreign_dispatch_scalar_reads_are_denied(self):
        operation = self.operation.with_user(self.other_manager).with_context(
            allowed_company_ids=[self.other_company.id]
        )
        self.assertFalse(operation.search([("id", "=", operation.id)]))
        with self.assertRaises(AccessError):
            operation.read(["order_uuid"])

        dispatch = self.dispatch.with_user(self.other_manager).with_context(
            allowed_company_ids=[self.other_company.id]
        )
        scalar_fields = ["provider_reference", "action", "outcome"]
        with self.assertRaises(AccessError):
            dispatch.read(scalar_fields)
        self.assertFalse(dispatch.search([("id", "=", dispatch.id)]))
        self.assertEqual(
            dispatch.search_read([("id", "=", dispatch.id)], scalar_fields), []
        )
        allowed = self.dispatch.with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id]
        )
        self.assertEqual(allowed.read(scalar_fields), [{
            "id": self.dispatch.id,
            "provider_reference": self.dispatch.provider_reference,
            "action": "create_order",
            "outcome": "succeeded",
        }])

    def test_foreign_order_lock_scalar_reads_are_denied(self):
        order_lock = self.order_lock.with_user(self.other_manager).with_context(
            allowed_company_ids=[self.other_company.id]
        )
        with self.assertRaises(AccessError):
            order_lock.read(["order_uuid"])
        self.assertFalse(order_lock.search([("id", "=", order_lock.id)]))
        self.assertEqual(
            order_lock.search_read([("id", "=", order_lock.id)], ["order_uuid"]),
            [],
        )

        allowed = self.order_lock.with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id]
        )
        self.assertEqual(allowed.read(["order_uuid"]), [{
            "id": self.order_lock.id,
            "order_uuid": self.operation.order_uuid,
        }])

    def test_multi_company_manager_is_limited_to_active_companies(self):
        for records, scalar_fields in (
            (self.operation, ["order_uuid"]),
            (self.dispatch, ["provider_reference", "action", "outcome"]),
            (self.order_lock, ["order_uuid"]),
        ):
            with self.subTest(model=records._name):
                manager_records = records.with_user(self.multi_company_manager)
                self.assertFalse(manager_records.env.su)
                domain = [("id", "=", records.id)]
                for companies in (
                    [self.company.id],
                    [self.company.id, self.other_company.id],
                ):
                    allowed = manager_records.with_context(allowed_company_ids=companies)
                    self.assertEqual(allowed.search(domain).ids, records.ids)
                    self.assertEqual(len(allowed.read(scalar_fields)), 1)

                restricted = manager_records.with_context(
                    allowed_company_ids=[self.other_company.id]
                )
                self.assertFalse(restricted.search(domain))
                self.assertEqual(restricted.search_read(domain, scalar_fields), [])
                with self.assertRaises(AccessError):
                    restricted.read(scalar_fields)

    def test_cashier_cannot_inspect_financial_internals_directly(self):
        for records, scalar_fields in (
            (self.operation, ["order_uuid"]),
            (self.dispatch, ["provider_reference", "action", "outcome"]),
            (self.order_lock, ["order_uuid"]),
        ):
            with self.subTest(model=records._name):
                restricted = records.with_user(self.cashier).with_context(
                    allowed_company_ids=[self.company.id]
                )
                with self.assertRaises(AccessError):
                    restricted.read(scalar_fields)
                with self.assertRaises(AccessError):
                    restricted.search([("id", "=", records.id)])

    def test_manager_and_cashier_cannot_mutate_financial_internals_directly(self):
        for user in (self.manager, self.cashier):
            for records, create_values, write_values in (
                (self.operation, {
                    **self.operation_values,
                    "order_uuid": str(uuid4()),
                    "payment_line_uuid": str(uuid4()),
                }, {"state": "verified"}),
                (self.dispatch, {
                    "operation_id": self.operation.id,
                    "action": "cancel_intent",
                }, {"provider_reference": str(uuid4())}),
                (self.order_lock, {
                    "company_id": self.company.id,
                    "order_uuid": str(uuid4()),
                }, {"order_uuid": str(uuid4())}),
            ):
                with self.subTest(user=user.login, model=records._name):
                    restricted = records.with_user(user).with_context(
                        allowed_company_ids=[self.company.id]
                    )
                    with self.assertRaises(AccessError):
                        restricted.create(create_values)
                    with self.assertRaises(AccessError):
                        restricted.write(write_values)
                    with self.assertRaises(AccessError):
                        restricted.unlink()

        self.assertEqual(self.operation.state, "unresolved")
        self.assertEqual(self.dispatch.outcome, "succeeded")
        self.assertEqual(self.order_lock.order_uuid, self.operation.order_uuid)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_AUTHORIZATION_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_cashier_dispatch_and_manager_reconciliation_preserve_evidence(self, request):
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)

        def response(payload):
            result = Mock()
            result.json.return_value = payload
            return result

        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        order_reference, intent_reference, payment_reference = (
            str(uuid4()), str(uuid4()), str(uuid4())
        )
        request.side_effect = [
            response({"terminals": [{
                "id": self.method.revolut_terminal_id,
                "online": True,
                "operation_mode": "pos",
                "location_id": self.method.revolut_location_id,
            }]}),
            response({"id": order_reference}),
            response({"id": intent_reference, "state": "pending"}),
            response({
                "id": intent_reference, "order_id": order_reference,
                "state": "completed", "payment_id": payment_reference,
            }),
            response({
                "id": payment_reference, "order_id": order_reference,
                "amount": 1234, "currency": self.session.currency_id.name,
                "state": "captured",
            }),
        ]
        cashier_method = self.method.with_user(self.cashier).with_context(
            allowed_company_ids=[self.company.id]
        )
        started = authorized_start(cashier_method,
            self.session.id, order_uuid, line_uuid, 12.34,
            self.session.currency_id.id, False, {
                "pricelist_id": self.config.pricelist_id.id,
                "fiscal_position_id": False,
                "lines": [{
                    "uuid": order_uuid, "product_id": self.product.id, "qty": 1,
                    "price_unit": 12.34, "discount": 0, "tax_ids": [],
                }],
            },
        )
        self.assertEqual(started["state"], "pending")
        operation = self.env["pos.revolut.payment.operation"].with_user(
            self.manager
        ).with_context(allowed_company_ids=[self.company.id]).browse(
            started["operation_id"]
        )
        self.assertFalse(operation.env.su)
        self.assertTrue(operation.blocking_order_key)
        self.assertTrue(operation.blocking_terminal_key)
        dispatches = self.env["pos.revolut.payment.dispatch"].with_user(
            self.manager
        ).with_context(allowed_company_ids=[self.company.id]).search([
            ("operation_id", "=", operation.id),
        ])
        self.assertEqual(len(dispatches), 2)
        self.assertEqual(set(dispatches.mapped("provider_reference")), {
            order_reference, intent_reference,
        })
        self.assertEqual(dispatches.mapped("outcome"), ["succeeded", "succeeded"])
        self.assertTrue(all(dispatches.mapped("completed_at")))
        order_locks = self.env["pos.revolut.order.lock"].with_user(
            self.manager
        ).with_context(allowed_company_ids=[self.company.id]).search([
            ("order_uuid", "=", order_uuid),
        ])
        self.assertEqual(len(order_locks), 1)

        operation.action_revolut_reconcile()
        operation.invalidate_recordset()
        recovered = cashier_method.revolut_find_payment(order_uuid, line_uuid)
        self.assertEqual(recovered["operation_id"], started["operation_id"])
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], payment_reference)
        self.assertEqual(operation.audit_ids.mapped("actor_id"), self.manager)
        self.assertEqual(operation.audit_ids.mapped("action"), ["reconcile"])
        self.assertEqual(operation.audit_ids.mapped("resulting_state"), ["verified"])
        self.assertIn(payment_reference, operation.audit_ids.evidence_reference)
        self.assertFalse(operation.blocking_terminal_key)
        self.assertFalse(operation.blocking_order_key)
        self.assertFalse(operation.retry_safe)
        self.assertEqual(dispatches.search_count([("operation_id", "=", operation.id)]), 2)
        self.assertEqual([call.args[0] for call in request.call_args_list], [
            "GET", "POST", "POST", "GET", "GET", "POST", "GET", "GET",
        ])
        self.assertEqual(len(financial_posts(request)), 2)

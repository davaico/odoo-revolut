"""Native manager worklists retain register boundaries and audit actions."""

from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .authorization_fixtures import native_products, prepare_fixture


@tagged("post_install", "-at_install")
class TestRevolutRegisterManagerUi(TestPointOfSaleHttpCommon):
    ORDER_UUID = "860724e8-c507-40b4-bcbe-970bd3b60055"
    HIDDEN_UUID = "18a1fc19-8c42-4cd9-b715-f83087f90055"
    ORDER_ID = "8da7c170-e212-46e6-bfc9-a0bd2c4f0055"
    INTENT_ID = "ac55159c-b656-4ac9-989a-0f46d36e0055"
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"

    def test_manager_reconciles_permitted_work_then_revocation_hides_it(self):
        method = self.env["pos.payment.method"].create({
            "name": "Revolut manager worklist", "journal_id": self.bank_journal.id,
            "payment_method_type": "terminal", "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox", "revolut_location_id": self.LOCATION_ID,
            "revolut_terminal_id": self.TERMINAL_ID, "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        config = self.main_pos_config
        config.write({
            "payment_method_ids": [Command.link(method.id)],
            "auto_validate_terminal_payment": True,
            "revolut_user_ids": [Command.set((self.env.user | self.pos_user | self.pos_admin).ids)],
        })
        product = native_products(self.env, config)
        config.with_user(self.pos_user).open_ui()
        session = config.current_session_id
        session.set_opening_control(0, "")
        line_uuid = str(uuid4())
        snapshot = {
            "pricelist_id": config.pricelist_id.id, "fiscal_position_id": False,
            "lines": [{"uuid": str(uuid4()), "product_id": product.id,
                       "qty": 1, "price_unit": 12.34, "discount": 0, "tax_ids": []}],
        }
        authority = prepare_fixture(
            method.with_user(self.pos_user), session.id, self.ORDER_UUID,
            line_uuid, 12.34, snapshot,
        )
        calls = []

        def response(payload):
            result = Mock(status_code=200)
            result.json.return_value = payload
            return result

        def provider(verb, url, **kwargs):
            calls.append((verb, url))
            if verb == "GET" and url.endswith("/api/terminals"):
                return response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if verb == "POST" and url.endswith("/api/orders"):
                return response({"id": self.ORDER_ID})
            if verb == "POST" and url.endswith(f"/api/orders/{self.ORDER_ID}/payment-intents"):
                raise requests.ConnectionError("Simulated lost intent response")
            if verb == "GET" and url.endswith(f"/api/orders/{self.ORDER_ID}"):
                return response({
                    "id": self.ORDER_ID, "amount": 1234,
                    "currency": config.currency_id.name, "location_id": self.LOCATION_ID,
                    "metadata": {"pos_order_uuid": self.ORDER_UUID,
                                 "pos_payment_line_uuid": line_uuid},
                })
            if verb == "GET" and url.endswith(f"/api/payment-intents/{self.INTENT_ID}"):
                return response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID, "amount": 1234,
                    "currency": config.currency_id.name, "terminal_id": self.TERMINAL_ID,
                    "state": "pending",
                })
            self.fail(f"Unexpected manager worklist provider call: {verb} {url}")

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=provider):
            started = method.with_user(self.pos_user).revolut_start_payment(
                session.id, self.ORDER_UUID, line_uuid, 12.34, config.currency_id.id,
                False, False, authority["authorization_id"], authority["cart_version"],
                authority["tender_revision"],
            )
            self.assertEqual(started["state"], "unresolved")
            operation = self.env["pos.revolut.payment.operation"].browse(started["operation_id"])
            hidden_config = config.copy({
                "name": "Other manager register",
                "revolut_user_ids": [Command.set(self.env.user.ids)],
            })
            hidden_session = self.env["pos.session"].create({
                "config_id": hidden_config.id, "state": "opened",
            })
            # Seed the inaccessible server-owned record; all visibility and
            # action assertions below run as the actual manager/cashier.
            hidden = self.env["pos.revolut.payment.operation"].sudo().create({
                "payment_method_id": method.id, "company_id": self.env.company.id,
                "pos_config_id": hidden_config.id, "pos_session_id": hidden_session.id,
                "order_uuid": self.HIDDEN_UUID, "payment_line_uuid": str(uuid4()),
                "amount": 12.34, "amount_minor": 1234,
                "currency_id": config.currency_id.id, "currency_code": config.currency_id.name,
                "environment": "sandbox", "location_id": self.LOCATION_ID,
                "terminal_id": self.TERMINAL_ID, "fulfilment_type": "eat_in",
                "secret_reference": method.revolut_secret_reference, "state": "unresolved",
            })
            manager_operations = self.env["pos.revolut.payment.operation"].with_user(self.pos_admin)
            self.assertEqual(manager_operations.search([("id", "in", (operation | hidden).ids)]),
                             operation.with_user(self.pos_admin))
            action = self.env.ref("pos_revolut.action_revolut_reconciliation")
            url = f"/odoo/action-{action.id}?debug=tests"
            self.start_tour(url, "pos_revolut_manager_reconciles_register", login="pos_admin")
            self.env.invalidate_all()
            operation = operation.with_user(self.pos_admin)
            self.assertEqual(operation.state, "pending")
            self.assertEqual(operation.revolut_order_id, self.ORDER_ID)
            self.assertEqual(operation.revolut_payment_intent_id, self.INTENT_ID)
            self.assertEqual(operation.order_uuid, self.ORDER_UUID)
            self.assertEqual(operation.payment_line_uuid, line_uuid)
            self.assertEqual(operation.pos_order_id.state, "draft")
            self.assertTrue(operation.blocking_terminal_key)
            self.assertEqual(operation.audit_ids.mapped("action"), ["associate", "reconcile"])
            self.assertEqual(operation.audit_ids.actor_id, self.pos_admin)
            self.assertEqual(sum(verb == "POST" for verb, _url in calls), 2)
            observed_calls = list(calls)
            config.write({"revolut_user_ids": [Command.unlink(self.pos_admin.id)]})
            self.env.invalidate_all()
            self.start_tour(url, "pos_revolut_manager_revoked_worklist", login="pos_admin")
            self.assertFalse(manager_operations.search([("id", "in", (operation | hidden).ids)]))
            with self.assertRaises(AccessError):
                operation.read(["state"])
            self.assertEqual(calls, observed_calls)
            # Check retained exposure as the originally granted cashier.
            retained = method.with_user(self.pos_user).revolut_find_payment(
                self.ORDER_UUID, line_uuid,
            )
            self.assertEqual(retained["operation_id"], operation.id)
            self.assertEqual(retained["state"], "pending")
            self.assertFalse(retained["retry_safe"])
            self.assertEqual(calls, observed_calls)

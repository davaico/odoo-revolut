"""Checkout on a database with Restaurant but without the Revolut companion."""
import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.tests.common import TransactionCase, tagged

from .authorization_fixtures import authorized_start, financial_posts, native_products


@tagged("post_install", "-at_install", "-standard", "revolut_restaurant_without_companion")
class TestRestaurantWithoutCompanion(TransactionCase):
    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_TEST_TERMINAL": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_restaurant_rejects_new_sales_and_recovers_existing_payment(self, provider):
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.assertIn("restaurant.table", self.env)
        self.assertFalse(self.env["ir.module.module"].search_count([
            ("name", "=", "pos_revolut_restaurant_integration"), ("state", "=", "installed"),
        ]))
        method = self.env["pos.payment.method"].create({
            "name": "Revolut companion boundary", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        dine_in = self.env.ref("pos_restaurant.pos_takein_preset")
        restaurant, retail = self.env["pos.config"].create([
            {"name": "Restaurant", "module_pos_restaurant": True, "use_presets": True,
             "default_preset_id": dine_in.id, "available_preset_ids": [Command.link(dine_in.id)],
             "payment_method_ids": [Command.link(method.id)], "auto_validate_terminal_payment": True},
            {"name": "Retail", "payment_method_ids": [Command.link(method.id)],
             "auto_validate_terminal_payment": True},
        ])

        products = {config.id: native_products(self.env, config) for config in (restaurant, retail)}
        sessions = {
            config.id: self.env["pos.session"].create({"config_id": config.id, "state": "opened"})
            for config in (restaurant, retail)
        }

        def start(config, context=False):
            session = sessions[config.id]
            order_uuid, line_uuid = str(uuid4()), str(uuid4())
            result = authorized_start(method, session.id, order_uuid, line_uuid, 12.34,
                                      config.currency_id.id, False, {
                "pricelist_id": config.pricelist_id.id,
                "restaurant": context,
                "lines": [{"uuid": str(uuid4()), "product_id": products[config.id].id, "qty": 1,
                           "price_unit": 12.34, "discount": 0, "tax_ids": []}],
            })
            return result, order_uuid, line_uuid

        def response(payload):
            result = Mock(status_code=200)
            result.json.return_value = payload
            return result

        def start_responses(order_id, intent_id):
            return [
                response({"terminals": [{"id": method.revolut_terminal_id, "online": True,
                                         "location_id": method.revolut_location_id, "operation_mode": "pos"}]}),
                response({"id": order_id}),
                response({"id": intent_id, "state": "pending"}),
            ]

        context = {"preset_id": dine_in.id, "table_id": False}
        provider.side_effect = start_responses(str(uuid4()), str(uuid4()))
        rejected, order_uuid, line_uuid = start(restaurant, context)
        self.assertEqual(rejected.get("start_rejected"), "snapshot_invalid")
        self.assertFalse(rejected["dispatched"])
        self.assertIn("POS Revolut Restaurant Integration", rejected["message"])
        self.assertFalse(method.revolut_find_payment(order_uuid, line_uuid))
        provider.assert_not_called()

        order_id, intent_id, payment_id = (str(uuid4()) for _ in range(3))
        provider.side_effect = [
            *start_responses(order_id, intent_id),
            response({"id": intent_id, "order_id": order_id, "state": "completed", "payment_id": payment_id}),
            response({"id": payment_id, "order_id": order_id, "state": "captured", "amount": 1234,
                      "currency": restaurant.currency_id.name}),
        ]
        # Seed the operation that the combined release could already have dispatched.
        with patch.object(type(method), "_revolut_payment_fulfilment", return_value="eat_in"):
            pending, order_uuid, line_uuid = start(restaurant, context)
        self.assertEqual(pending["state"], "pending")
        provider.reset_mock()
        recovered = method.revolut_poll_payment(pending["operation_id"], order_uuid, line_uuid)
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], payment_id)
        self.assertFalse(financial_posts(provider))

        provider.reset_mock()
        provider.side_effect = start_responses(str(uuid4()), str(uuid4()))
        started, order_uuid, line_uuid = start(retail)
        self.assertEqual(started["state"], "pending")
        self.assertEqual(method.revolut_find_payment(order_uuid, line_uuid)["operation_id"], started["operation_id"])
        self.assertEqual(provider.call_count, 3)

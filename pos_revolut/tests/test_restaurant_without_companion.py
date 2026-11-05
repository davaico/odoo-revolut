"""Checkout on a database with Restaurant but without the Revolut companion."""
import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.tests.common import TransactionCase, tagged

from .authorization_fixtures import authorized_start, native_products


@tagged("post_install", "-at_install", "-standard", "revolut_restaurant_without_companion")
class TestRestaurantWithoutCompanion(TransactionCase):
    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_TEST_TERMINAL": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_new_restaurant_sale_is_blocked_and_retail_can_dispatch(self, provider):
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.assertIn("restaurant.table", self.env)
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

        def start(config, context=False):
            product = native_products(self.env, config)
            session = self.env["pos.session"].create({"config_id": config.id, "state": "opened"})
            order_uuid, line_uuid = str(uuid4()), str(uuid4())
            result = authorized_start(method, session.id, order_uuid, line_uuid, 12.34,
                                      config.currency_id.id, False, {
                "pricelist_id": config.pricelist_id.id,
                "restaurant": context,
                "lines": [{"uuid": str(uuid4()), "product_id": product.id, "qty": 1,
                           "price_unit": 12.34, "discount": 0, "tax_ids": []}],
            })
            return result, method.revolut_find_payment(order_uuid, line_uuid)

        def response(payload):
            result = Mock(status_code=200)
            result.json.return_value = payload
            return result

        provider.side_effect = [
            response({"terminals": [{"id": method.revolut_terminal_id, "online": True,
                                     "location_id": method.revolut_location_id, "operation_mode": "pos"}]}),
            response({"id": str(uuid4())}),
            response({"id": str(uuid4()), "state": "pending"}),
        ]
        rejected, found = start(restaurant, {"preset_id": dine_in.id, "table_id": False})
        self.assertEqual(rejected.get("start_rejected"), "snapshot_invalid")
        self.assertFalse(rejected["dispatched"])
        self.assertIn("POS Revolut Restaurant Integration", rejected["message"])
        self.assertFalse(found)
        provider.assert_not_called()

        started, found = start(retail)
        self.assertEqual(started["state"], "pending")
        self.assertEqual(found["operation_id"], started["operation_id"])
        self.assertEqual(provider.call_count, 3)

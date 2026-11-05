"""Native Restaurant browser startup, checkout and table guards."""
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from odoo.addons.pos_revolut.tests import test_ui
from odoo.addons.pos_revolut.tests.authorization_fixtures import install_zero_reports


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantPosStarts(TestPointOfSaleHttpCommon):
    def test_restaurant_table_checkout_verifies_revolut_payment(self):
        method = self.env["pos.payment.method"].create({
            "name": "Revolut",
            "journal_id": self.bank_journal.id,
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": test_ui.TestRevolutManagerUi.LOCATION_ID,
            "revolut_terminal_id": test_ui.TestRevolutManagerUi.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        self.main_pos_config.sudo().write({
            "revolut_user_ids": [Command.set((self.env.user | self.pos_user).ids)],
        })
        self.main_pos_config.write({
            "module_pos_restaurant": True,
            "payment_method_ids": [Command.link(method.id)],
            "auto_validate_terminal_payment": True,
            "tip_product_id": self.env["product.product"].create({
                "name": "Verified terminal tip", "list_price": 0,
                "taxes_id": [Command.clear()],
            }).id,
            "use_presets": True,
            "default_preset_id": self.env.ref(
                "pos_restaurant.pos_takein_preset"
            ).id,
            "available_preset_ids": [Command.link(self.env.ref(
                "pos_restaurant.pos_takein_preset"
            ).id)],
        })
        floor = self.env["restaurant.floor"].create({
            "name": "Checkout Floor",
            "pos_config_ids": [Command.link(self.main_pos_config.id)],
        })
        self.env["restaurant.table"].create({
            "table_number": 1, "floor_id": floor.id, "seats": 2,
        })
        self.desk_pad.write({"list_price": 12.34, "taxes_id": [Command.clear()]})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        provider_order_id = "d40466e0-2188-41d0-bebb-aa3a930663a8"
        provider_intent_id = "4ca74d24-7b42-451a-91fb-8aca308e2630"
        provider_payment_id = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"
        calls = []

        def response(payload):
            result = Mock()
            result.json.return_value = payload
            return result

        def request(http_method, url, **kwargs):
            calls.append((http_method, url, kwargs))
            if http_method == "GET" and url.endswith("/api/terminals"):
                return response({"terminals": [{
                    "id": test_ui.TestRevolutManagerUi.TERMINAL_ID,
                    "online": True, "operation_mode": "pos",
                    "location_id": test_ui.TestRevolutManagerUi.LOCATION_ID,
                }]})
            if http_method == "POST" and url.endswith("/api/orders"):
                return response({"id": provider_order_id})
            if http_method == "POST" and url.endswith("/payment-intents"):
                return response({"id": provider_intent_id, "state": "pending"})
            if http_method == "GET" and "/api/payment-intents/" in url:
                return response({
                    "id": provider_intent_id, "order_id": provider_order_id,
                    "state": "completed", "payment_id": provider_payment_id,
                })
            if http_method == "GET" and "/api/payments/" in url:
                return response({
                    "id": provider_payment_id, "order_id": provider_order_id,
                    "state": "captured", "amount": 1234,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {http_method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_restaurant_checkout")

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", method.id),
        ])
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(operation.pos_order_id.table_id.table_number, 1)
        posts = [call for call in calls if call[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0][2]["json"]["fulfilment_type"], "eat_in")

    def test_restaurant_merge_and_transfer_preserve_revolut_order(self):
        method = self.env["pos.payment.method"].create({
            "name": "Revolut",
            "journal_id": self.bank_journal.id,
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": test_ui.TestRevolutManagerUi.LOCATION_ID,
            "revolut_terminal_id": test_ui.TestRevolutManagerUi.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        self.main_pos_config.sudo().write({
            "revolut_user_ids": [Command.set((self.env.user | self.pos_user).ids)],
        })
        self.main_pos_config.write({
            "module_pos_restaurant": True,
            "payment_method_ids": [Command.link(method.id)],
        })
        floor = self.env["restaurant.floor"].create({
            "name": "Guard Floor",
            "pos_config_ids": [Command.link(self.main_pos_config.id)],
        })
        self.env["restaurant.table"].create({
            "table_number": 1, "floor_id": floor.id, "seats": 2,
        })
        self.env["restaurant.table"].create({
            "table_number": 2, "floor_id": floor.id, "seats": 2,
        })
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        self.start_pos_tour("pos_revolut_restaurant_guards")

    def test_restaurant_pos_starts_with_addon_installed(self):

        self.main_pos_config.write({"module_pos_restaurant": True})
        floor = self.env["restaurant.floor"].create(
            {
                "name": "Acceptance Floor",
                "pos_config_ids": [Command.link(self.main_pos_config.id)],
            }
        )
        self.env["restaurant.table"].create(
            {
                "table_number": 1,
                "floor_id": floor.id,
                "seats": 2,
            }
        )
        self.main_pos_config.with_user(self.pos_user).open_ui()

        self.start_pos_tour("pos_revolut_restaurant_starts")

from unittest.mock import Mock, patch

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import (
    TestPointOfSaleHttpCommon,
)
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestRevolutManagerUi(HttpCase):
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"

    def test_manager_configures_and_checks_terminal_in_browser(self):
        payment_method = self.env["pos.payment.method"].create(
            {"name": "Browser Revolut"}
        )
        response = Mock()
        response.json.return_value = {
            "terminals": [
                {
                    "id": self.TERMINAL_ID,
                    "name": "Counter 1",
                    "online": True,
                }
            ]
        }
        action = self.env.ref("point_of_sale.action_pos_payment_method_form")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
            return_value=response,
        ) as request_get:
            self.start_tour(
                f"/odoo/action-{action.id}/{payment_method.id}?debug=tests",
                "pos_revolut_manager_configuration",
                login="admin",
            )

        payment_method.invalidate_recordset()
        self.assertRecordValues(
            payment_method,
            [
                {
                    "payment_method_type": "terminal",
                    "use_payment_terminal": "revolut",
                    "revolut_environment": "sandbox",
                    "revolut_location_id": self.LOCATION_ID,
                    "revolut_terminal_id": self.TERMINAL_ID,
                    "revolut_fulfilment_type": "eat_in",
                    "revolut_secret_reference": (
                        "ODOO_REVOLUT_SECRET_TEST_TERMINAL"
                    ),
                }
            ],
        )
        request_get.assert_called_once()
        response.raise_for_status.assert_called_once_with()


@tagged("post_install", "-at_install")
class TestRevolutRetailPosStarts(TestPointOfSaleHttpCommon):
    def test_retail_pos_starts_with_addon_installed(self):
        self.main_pos_config.with_user(self.pos_user).open_ui()

        self.start_pos_tour("pos_revolut_retail_starts")


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantPosStarts(TestPointOfSaleHttpCommon):
    def test_restaurant_pos_starts_with_addon_installed(self):
        restaurant_module = self.env["ir.module.module"].search(
            [("name", "=", "pos_restaurant")], limit=1
        )
        if restaurant_module.state != "installed":
            self.skipTest("pos_restaurant is not installed in this test phase")

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


@tagged("post_install", "-at_install")
class TestRevolutVerifiedCheckout(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutManagerUi.LOCATION_ID
    ORDER_ID = "d40466e0-2188-41d0-bebb-aa3a930663a8"
    INTENT_ID = "4ca74d24-7b42-451a-91fb-8aca308e2630"
    PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"
    TERMINAL_ID = TestRevolutManagerUi.TERMINAL_ID

    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def test_successful_payment_is_verified_before_automatic_checkout(self):
        revolut_method = self.env["pos.payment.method"].create(
            {
                "name": "Revolut",
                "journal_id": self.bank_journal.id,
                "payment_method_type": "terminal",
                "use_payment_terminal": "revolut",
                "revolut_environment": "sandbox",
                "revolut_location_id": self.LOCATION_ID,
                "revolut_terminal_id": self.TERMINAL_ID,
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
            }
        )
        self.main_pos_config.write(
            {
                "payment_method_ids": [Command.link(revolut_method.id)],
                "auto_validate_terminal_payment": True,
            }
        )
        self.desk_pad.write({"list_price": 12.34, "taxes_id": [Command.clear()]})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        calls = []
        intent_polls = 0

        def request(method, url, **kwargs):
            nonlocal intent_polls
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response(
                    {
                        "terminals": [
                            {
                                "id": self.TERMINAL_ID,
                                "online": True,
                                "operation_mode": "pos",
                                "location_id": self.LOCATION_ID,
                            }
                        ]
                    }
                )
            if method == "POST" and url.endswith("/api/orders"):
                return self._response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                intent_polls += 1
                if intent_polls < 3:
                    return self._response(
                        {
                            "id": self.INTENT_ID,
                            "order_id": self.ORDER_ID,
                            "state": "processing",
                        }
                    )
                return self._response(
                    {
                        "id": self.INTENT_ID,
                        "order_id": self.ORDER_ID,
                        "state": "completed",
                        "payment_id": self.PAYMENT_ID,
                    }
                )
            if method == "GET" and "/api/payments/" in url:
                return self._response(
                    {
                        "id": self.PAYMENT_ID,
                        "order_id": self.ORDER_ID,
                        "state": "captured",
                        "amount": 1234,
                        "currency": self.main_pos_config.currency_id.name,
                    }
                )
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ):
            self.start_pos_tour("pos_revolut_verified_checkout")

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search(
            [("payment_method_id", "=", revolut_method.id)]
        )
        order = operation.pos_order_id
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.revolut_order_id, self.ORDER_ID)
        self.assertEqual(operation.revolut_payment_intent_id, self.INTENT_ID)
        self.assertEqual(operation.revolut_payment_id, self.PAYMENT_ID)
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.payment_ids.transaction_id, self.PAYMENT_ID)
        mutating_calls = [call for call in calls if call[0] == "POST"]
        self.assertEqual(len(mutating_calls), 2)

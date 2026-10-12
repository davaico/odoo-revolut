"""Timed Takeout uses native slots and checkout with mocked provider traffic."""
from datetime import datetime
from unittest.mock import Mock, patch

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .authorization_fixtures import install_zero_reports


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutTakeoutReadinessUi(TestPointOfSaleHttpCommon):
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"
    ORDER_ID = "d40466e0-2188-41d0-bebb-aa3a930663a8"
    INTENT_ID = "4ca74d24-7b42-451a-91fb-8aca308e2630"
    PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"

    def setUp(self):
        super().setUp()
        self.method = self.env["pos.payment.method"].create({
            "name": "Revolut", "journal_id": self.bank_journal.id,
            "payment_method_type": "terminal", "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": self.LOCATION_ID,
            "revolut_terminal_id": self.TERMINAL_ID,
            "revolut_fulfilment_type": "take_away",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        calendar = self.env["resource.calendar"].create({
            "name": "Takeout closed today, open tomorrow", "tz": "UTC",
            "attendance_ids": [Command.clear(), Command.create({
                "name": "Next available pickup day",
                "dayofweek": str((datetime.now().weekday() + 1) % 7),
                "hour_from": 10, "hour_to": 18, "day_period": "morning",
            })],
        })
        self.takeout = self.env.ref("pos_restaurant.pos_takeout_preset")
        self.takeout.write({
            "use_timing": True, "identification": "none",
            "resource_calendar_id": calendar.id,
        })
        dine_in = self.env.ref("pos_restaurant.pos_takein_preset")
        self.main_pos_config.sudo().write({
            "revolut_user_ids": [Command.set((self.env.user | self.pos_user).ids)],
        })
        self.main_pos_config.write({
            "module_pos_restaurant": True,
            "payment_method_ids": [Command.link(self.method.id)],
            "auto_validate_terminal_payment": True,
            "tip_product_id": self.env["product.product"].create({
                "name": "Takeout terminal tip", "list_price": 0,
                "taxes_id": [Command.clear()],
            }).id,
            "use_presets": True, "default_preset_id": dine_in.id,
            "available_preset_ids": [Command.set((dine_in | self.takeout).ids)],
        })
        floor = self.env["restaurant.floor"].create({
            "name": "Takeout readiness floor",
            "pos_config_ids": [Command.link(self.main_pos_config.id)],
        })
        self.env["restaurant.table"].create({
            "table_number": 1, "floor_id": floor.id, "seats": 2,
        })
        self.desk_pad.write({"list_price": 12.34, "taxes_id": [Command.clear()]})
        self.pos_user.tz = "UTC"
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")

    def _run_checkout(self, tour):
        calls = []

        def response(payload):
            result = Mock()
            result.json.return_value = payload
            return result

        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                return response({"terminals": [{
                    "id": self.method.revolut_terminal_id, "online": True,
                    "operation_mode": "pos", "location_id": self.method.revolut_location_id,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                return response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                return response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                return response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if method == "GET" and "/api/payments/" in url:
                return response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "state": "captured", "amount": 1234,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour(tour)
        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", self.method.id),
        ])
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(operation.pos_order_id.preset_id, self.takeout)
        self.assertTrue(operation.pos_order_id.preset_time)
        self.assertEqual(operation.pos_payment_id.payment_status, "done")
        self.assertEqual(operation.pos_payment_id.transaction_id, self.PAYMENT_ID)
        self.assertEqual(operation.pos_payment_id.revolut_operation_id, operation)
        posts = [call for call in calls if call[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0][2]["json"]["fulfilment_type"], "take_away")

    def test_missing_slot_blocks_new_financial_preparation_and_provider_dispatch(self):
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Missing pickup slot must not contact Revolut"),
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_takeout_missing_slot_blocked")
            provider.assert_not_called()
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", self.method.id),
        ]))

    def test_valid_native_slot_automatically_completes_same_order(self):
        self._run_checkout("pos_revolut_takeout_valid_slot_automatic_checkout")

    def test_captured_tender_finishes_after_native_scheduling_correction(self):
        self._run_checkout("pos_revolut_takeout_captured_scheduling_recovery")

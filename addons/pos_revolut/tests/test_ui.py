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

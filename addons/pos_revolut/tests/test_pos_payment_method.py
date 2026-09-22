from unittest.mock import Mock, patch

from lxml import etree
from requests import RequestException

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user


class TestRevolutPaymentMethod(TransactionCase):
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    SECRET_VALUE = "test-only-not-a-credential"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"

    def _create_revolut_payment_method(self, **overrides):
        values = {
            "name": "Revolut",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": self.LOCATION_ID,
            "revolut_terminal_id": self.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        }
        values.update(overrides)
        return self.env["pos.payment.method"].create(values)

    def test_revolut_is_available_as_payment_terminal(self):
        selection = dict(
            self.env["pos.payment.method"]._get_payment_terminal_selection()
        )

        self.assertEqual(selection["revolut"], "Revolut")

    def test_manager_can_configure_one_terminal(self):
        payment_method = self._create_revolut_payment_method()

        self.assertEqual(payment_method.company_id, self.env.company)
        self.assertEqual(payment_method.revolut_terminal_id, self.TERMINAL_ID)

    def test_revolut_configuration_rejects_unrelated_secret_reference(self):
        with self.assertRaises(ValidationError):
            self._create_revolut_payment_method(
                revolut_secret_reference="DATABASE_PASSWORD"
            )

    def test_revolut_configuration_requires_uuid_identifiers(self):
        invalid_identifiers = (
            (False, self.TERMINAL_ID),
            ("not-a-location", self.TERMINAL_ID),
            (self.LOCATION_ID, False),
            (self.LOCATION_ID, "not-a-terminal"),
        )
        for location_id, terminal_id in invalid_identifiers:
            with self.subTest(location_id=location_id, terminal_id=terminal_id):
                with self.assertRaises(ValidationError):
                    self._create_revolut_payment_method(
                        revolut_location_id=location_id,
                        revolut_terminal_id=terminal_id,
                    )

    def test_revolut_configuration_requires_supported_fulfilment(self):
        with self.assertRaises(ValidationError):
            self._create_revolut_payment_method(revolut_fulfilment_type=False)

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_manager_can_check_an_online_terminal_without_a_payment(self, request_get):
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
        request_get.return_value = response
        payment_method = self._create_revolut_payment_method()

        result = payment_method.action_revolut_check_connection()

        request_get.assert_called_once_with(
            "https://sandbox-merchant.revolut.com/api/terminals",
            headers={
                "Authorization": f"Bearer {self.SECRET_VALUE}",
                "Revolut-Api-Version": "2026-08-17",
            },
            params={"operation_mode": "pos", "location_id": self.LOCATION_ID},
            timeout=10,
        )
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(result["tag"], "display_notification")
        self.assertNotIn(self.SECRET_VALUE, repr(result))

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_pos_user_cannot_check_a_terminal(self, request_get):
        cashier = new_test_user(
            self.env,
            login="revolut_cashier",
            groups="point_of_sale.group_pos_user",
            company_id=self.env.company.id,
        )
        payment_method = self._create_revolut_payment_method()

        with self.assertRaises(AccessError):
            payment_method.with_user(cashier).action_revolut_check_connection()

        request_get.assert_not_called()

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_manager_cannot_check_another_company_terminal(self, request_get):
        manager = new_test_user(
            self.env,
            login="revolut_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=self.env.company.id,
            company_ids=[Command.set([self.env.company.id])],
        )
        other_company = self.env["res.company"].create({"name": "Other Company"})
        payment_method = self._create_revolut_payment_method(
            company_id=other_company.id
        )

        with self.assertRaises(AccessError):
            payment_method.with_user(manager).with_context(
                allowed_company_ids=[self.env.company.id]
            ).action_revolut_check_connection()

        request_get.assert_not_called()

    def test_pos_data_exports_no_revolut_credentials(self):
        browser_fields = self.env[
            "pos.payment.method"
        ]._load_pos_data_fields(self.env["pos.config"])

        self.assertFalse(
            {
                "revolut_environment",
                "revolut_location_id",
                "revolut_terminal_id",
                "revolut_secret_reference",
            }.intersection(browser_fields)
        )

    def test_terminal_check_is_available_only_in_the_manager_form(self):
        cashier = new_test_user(
            self.env,
            login="form_revolut_cashier",
            groups="point_of_sale.group_pos_user",
            company_id=self.env.company.id,
        )
        form_view = self.env.ref("point_of_sale.pos_payment_method_view_form")

        manager_arch = etree.fromstring(
            self.env["pos.payment.method"].get_view(
                view_id=form_view.id, view_type="form"
            )["arch"]
        )
        cashier_arch = etree.fromstring(
            self.env["pos.payment.method"].with_user(cashier).get_view(
                view_id=form_view.id, view_type="form"
            )["arch"]
        )

        button_path = "//button[@name='action_revolut_check_connection']"
        self.assertTrue(manager_arch.xpath(button_path))
        self.assertFalse(cashier_arch.xpath(button_path))

    def test_pos_user_cannot_read_server_configuration(self):
        cashier = new_test_user(
            self.env,
            login="restricted_revolut_cashier",
            groups="point_of_sale.group_pos_user",
            company_id=self.env.company.id,
        )
        payment_method = self._create_revolut_payment_method()

        with self.assertRaises(AccessError):
            payment_method.with_user(cashier).read(
                [
                    "revolut_environment",
                    "revolut_location_id",
                    "revolut_terminal_id",
                    "revolut_secret_reference",
                ]
            )

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_terminal_check_rejects_missing_or_offline_terminal(self, request_get):
        response = Mock()
        request_get.return_value = response
        payment_method = self._create_revolut_payment_method()
        invalid_terminal_lists = (
            [],
            [{"id": self.TERMINAL_ID, "name": "Counter 1", "online": False}],
        )

        for terminals in invalid_terminal_lists:
            with self.subTest(terminals=terminals):
                response.json.return_value = {"terminals": terminals}
                with self.assertRaises(UserError):
                    payment_method.action_revolut_check_connection()

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_production_check_uses_the_fixed_production_host(self, request_get):
        response = Mock()
        response.json.return_value = {
            "terminals": [{"id": self.TERMINAL_ID, "online": True}]
        }
        request_get.return_value = response
        payment_method = self._create_revolut_payment_method(
            revolut_environment="production"
        )

        payment_method.action_revolut_check_connection()

        self.assertEqual(
            request_get.call_args.args[0],
            "https://merchant.revolut.com/api/terminals",
        )

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_terminal_check_does_not_expose_secrets_in_errors(self, request_get):
        request_get.side_effect = RequestException(self.SECRET_VALUE)
        payment_method = self._create_revolut_payment_method()

        with self.assertRaises(UserError) as error:
            payment_method.action_revolut_check_connection()

        self.assertNotIn(self.SECRET_VALUE, str(error.exception))

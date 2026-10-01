"""Company credential boundaries use mocked Merchant HTTP only."""

import os
from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user


class TestRevolutCredentialAuthority(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "Other Merchant"})
        cls.manager = new_test_user(
            cls.env, login="merchant_authority_manager",
            groups="point_of_sale.group_pos_manager", company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.broad_manager = new_test_user(
            cls.env, login="merchant_authority_broad_manager",
            groups="point_of_sale.group_pos_manager", company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id, cls.other_company.id])],
        )
        cls.cashier = new_test_user(
            cls.env, login="merchant_authority_cashier",
            groups="point_of_sale.group_pos_user", company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.own_reference = "ODOO_REVOLUT_SECRET_COMPANY_A_TEST"
        cls.other_reference = "ODOO_REVOLUT_SECRET_COMPANY_B_TEST"
        cls.own_method = cls._method(cls.company, cls.own_reference)
        cls.other_method = cls._method(cls.other_company, cls.other_reference)
        cls.config = cls.env["pos.config"].create({
            "name": "Merchant authority POS",
            "payment_method_ids": [Command.link(cls.own_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id, "state": "opened",
        })

    @classmethod
    def _method(cls, company, reference):
        return cls.env["pos.payment.method"].create({
            "name": f"Merchant authority {company.id}",
            "company_id": company.id,
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()),
            "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": reference,
        })

    def _operation(self, method):
        return self.env["pos.revolut.payment.operation"].sudo().create({
            "payment_method_id": method.id,
            "company_id": method.company_id.id,
            "pos_config_id": self.config.id,
            "pos_session_id": self.session.id,
            "order_uuid": str(uuid4()),
            "payment_line_uuid": str(uuid4()),
            "amount": 0.01,
            "amount_minor": 1,
            "currency_id": self.session.currency_id.id,
            "currency_code": self.session.currency_id.name,
            "environment": method.revolut_environment,
            "location_id": method.revolut_location_id,
            "terminal_id": method.revolut_terminal_id,
            "fulfilment_type": method.revolut_fulfilment_type,
            "secret_reference": method.revolut_secret_reference,
            "state": "unresolved",
        })

    def test_restricted_manager_cannot_select_known_foreign_reference(self):
        foreign = self.other_reference
        method = self.own_method.with_user(self.manager)
        authority_count = self.env["pos.revolut.merchant.credential"].sudo().search_count([])
        # Exercise credential authorization after Odoo's open-session guard.
        self.cr.execute(
            "UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id]
        )
        self.session.invalidate_recordset()
        message = "credential authority is not configured for this company"
        with self.assertRaisesRegex(UserError, message), self.cr.savepoint():
            method.write({"revolut_secret_reference": foreign})
        with self.assertRaisesRegex(UserError, message), self.cr.savepoint():
            method.copy(default={
                "revolut_environment": "sandbox",
                "revolut_location_id": self.other_method.revolut_location_id,
                "revolut_terminal_id": self.other_method.revolut_terminal_id,
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": foreign,
            })
        with self.assertRaisesRegex(UserError, message), self.cr.savepoint():
            self.env["pos.payment.method"].with_user(self.manager).create({
                "name": "Forbidden import equivalent", "company_id": self.company.id,
                "payment_method_type": "terminal", "use_payment_terminal": "revolut",
                "revolut_environment": "sandbox",
                "revolut_location_id": self.other_method.revolut_location_id,
                "revolut_terminal_id": self.other_method.revolut_terminal_id,
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": foreign,
            })
        self.assertEqual(self.own_method.revolut_secret_reference, self.own_reference)
        self.assertEqual(
            self.env["pos.revolut.merchant.credential"].sudo().search_count([]), authority_count,
        )

    @patch.dict(os.environ, {
        "ODOO_REVOLUT_SECRET_COMPANY_A_TEST": "private-a",
        "ODOO_REVOLUT_SECRET_COMPANY_B_TEST": "private-b",
    })
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    def test_connection_check_uses_only_authorized_company_credential(self, request_get):
        response = Mock()
        response.json.return_value = {"terminals": [{
            "id": self.own_method.revolut_terminal_id, "online": True,
        }]}
        request_get.return_value = response
        result = self.own_method.with_user(self.manager).action_revolut_check_connection()
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(request_get.call_args.kwargs["headers"]["Authorization"], "Bearer private-a")
        self.assertNotIn("private-a", repr(result))

        # Context can widen a manager's record visibility, not company authority.
        with self.assertRaises(AccessError):
            self.other_method.with_user(self.manager).with_context(
                allowed_company_ids=[self.company.id]
            ).action_revolut_check_connection()
        self.assertEqual(request_get.call_count, 1)

    @patch.dict(os.environ, {
        "ODOO_REVOLUT_SECRET_COMPANY_A_TEST": "private-a",
        "ODOO_REVOLUT_SECRET_COMPANY_B_TEST": "private-b",
    })
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_unmapped_config_and_historical_attempt_never_reach_provider(self, request, request_get):
        operation = self._operation(self.own_method)
        self.assertTrue(operation.credential_id)
        self.cr.execute(
            "UPDATE pos_revolut_payment_operation SET credential_id = NULL WHERE id = %s",
            [operation.id],
        )
        operation.invalidate_recordset()
        provider_operation = {
            "credential_operation_id": operation.id,
            "environment": operation.environment,
            "secret_reference": operation.secret_reference,
        }
        with self.assertRaises(UserError):
            self.own_method._revolut_api_request(provider_operation, "GET", "/api/orders")
        with self.assertRaises(UserError):
            self.own_method._revolut_report_request(provider_operation, "GET", "/api/report-runs")
        with self.assertRaises(ValidationError):
            operation.with_user(self.manager).action_revolut_authorize_legacy_credential()
        request.assert_not_called()

        # Simulate an upgraded, untrusted method row; the payment entrypoint
        # rejects it before creating an operation or sending a terminal GET.
        self.cr.execute(
            "UPDATE pos_payment_method SET revolut_secret_reference = %s WHERE id = %s",
            [self.other_reference, self.own_method.id],
        )
        self.own_method.invalidate_recordset()
        with self.assertRaises(UserError):
            self.own_method.with_user(self.cashier).revolut_start_payment(
                self.session.id, str(uuid4()), str(uuid4()), 0.01,
                self.session.currency_id.id,
            )
        with self.assertRaises(UserError):
            self.own_method.with_user(self.manager).action_revolut_check_connection()
        request.assert_not_called()
        request_get.assert_not_called()

        # Restore the method; only an administrator can attest the old attempt.
        self.cr.execute(
            "UPDATE pos_payment_method SET revolut_secret_reference = %s WHERE id = %s",
            [self.own_reference, self.own_method.id],
        )
        self.own_method.invalidate_recordset()
        operation.with_user(self.env.ref("base.user_admin")).action_revolut_authorize_legacy_credential()
        self.assertEqual(operation.credential_id.company_id, self.company)
        response = Mock()
        response.json.return_value = {"orders": []}
        request.return_value = response
        self.own_method._revolut_api_request(provider_operation, "GET", "/api/orders")
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer private-a")

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_direct_foreign_operation_id_cannot_choose_a_merchant(self, request):
        # The source operation, method and frozen company must all agree.
        foreign = self._operation(self.other_method)
        with self.assertRaises(UserError):
            self.own_method._revolut_api_request({
                "credential_operation_id": foreign.id,
                "environment": foreign.environment,
                "secret_reference": foreign.secret_reference,
            }, "GET", "/api/orders")
        request.assert_not_called()

    def test_method_with_historical_attempt_cannot_move_to_another_company(self):
        self._operation(self.own_method)
        with self.assertRaisesRegex(ValidationError, "cannot change company"):
            self.own_method.write({
                "company_id": self.other_company.id,
                "revolut_secret_reference": self.other_reference,
            })

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_system_administrator_without_pos_role_can_attest_history(self, request):
        administrator = new_test_user(
            self.env, login="merchant_authority_system_only",
            groups="base.group_system", company_id=self.company.id,
            company_ids=[Command.set([self.company.id])],
        )
        self.assertFalse(administrator.has_group("point_of_sale.group_pos_manager"))
        operation = self._operation(self.own_method)
        self.cr.execute(
            "UPDATE pos_revolut_payment_operation SET credential_id = NULL WHERE id = %s",
            [operation.id],
        )
        operation.invalidate_recordset()

        operation.with_user(administrator).action_revolut_authorize_legacy_credential()

        self.assertEqual(operation.credential_id.company_id, self.company)
        self.assertEqual(operation.state, "unresolved")
        request.assert_not_called()

    @patch.dict(os.environ, {
        "ODOO_REVOLUT_SECRET_COMPANY_A_TEST": "private-a",
        "ODOO_REVOLUT_SECRET_COMPANY_A_ROTATED": "rotated-a",
    })
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_same_company_rotation_keeps_historical_attempt_on_original_account(self, request):
        old = self._operation(self.own_method)
        old.write({"state": "verified"})
        # This authority fixture has no full native checkout. Mark its prior
        # register closed so Odoo allows a post-sale method rotation.
        self.cr.execute(
            "UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id]
        )
        self.session.invalidate_recordset()
        self.env["pos.revolut.merchant.credential"].create({
            "company_id": self.company.id, "environment": "sandbox",
            "secret_reference": "ODOO_REVOLUT_SECRET_COMPANY_A_ROTATED",
        })
        self.own_method.with_user(self.manager).write({
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_COMPANY_A_ROTATED"
        })
        response = Mock()
        response.json.return_value = {"orders": []}
        request.return_value = response
        self.own_method._revolut_api_request({
            "credential_operation_id": old.id,
            "environment": old.environment,
            "secret_reference": old.secret_reference,
        }, "GET", "/api/orders")
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer private-a")
        self.assertEqual(self.own_method.revolut_secret_reference,
                         "ODOO_REVOLUT_SECRET_COMPANY_A_ROTATED")

    def test_authority_records_and_reference_inventory_are_admin_only(self):
        for user in (self.manager, self.broad_manager, self.cashier):
            restricted = self.env["pos.revolut.merchant.credential"].with_user(user)
            with self.assertRaises(AccessError):
                restricted.search([])
            with self.assertRaises(AccessError):
                restricted.create({
                    "company_id": self.company.id, "environment": "sandbox",
                    "secret_reference": "ODOO_REVOLUT_SECRET_UNAUTHORIZED",
                })
        browser_fields = self.env["pos.payment.method"]._load_pos_data_fields(
            self.env["pos.config"]
        )
        self.assertNotIn("revolut_secret_reference", browser_fields)
        self.assertNotIn("credential_id", browser_fields)

    def test_saving_unchanged_legacy_method_does_not_authorize_its_reference(self):
        authority = self.env["pos.revolut.merchant.credential"]._for_snapshot(
            self.company.id, "sandbox", self.own_reference,
        )
        authority.unlink()
        administrator_method = self.own_method.with_user(self.env.ref("base.user_admin"))
        self.cr.execute(
            "UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id]
        )
        self.session.invalidate_recordset()

        with self.assertRaisesRegex(UserError, "credential authority is not configured"), self.cr.savepoint():
            administrator_method.write({"revolut_secret_reference": self.own_reference})

        self.assertFalse(self.env["pos.revolut.merchant.credential"].search([
            ("secret_reference", "=", self.own_reference),
        ]))

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_COMPANY_A_TEST": "private-a"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get")
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_redirects_cannot_change_the_authorized_provider_origin(self, request, request_get):
        operation = self._operation(self.own_method)
        method = self.own_method.with_user(self.manager)
        for status in (302, 307, 308):
            with self.subTest(status=status):
                response = requests.Response()
                response.status_code = status
                response.headers["Location"] = "https://foreign.invalid/merchant"
                # Even plausible JSON must not make a redirect acceptable.
                response._content = b'{"terminals": [], "orders": []}'
                request_get.return_value = response
                request.return_value = response

                with self.assertRaisesRegex(UserError, "terminal check could not be completed"):
                    method.action_revolut_check_connection()
                self.assertIs(request_get.call_args.kwargs.get("allow_redirects"), False)

                with self.assertRaisesRegex(UserError, "evidence could not be retrieved"):
                    operation.with_user(self.manager).action_revolut_associate(
                        order_reference=str(uuid4()),
                    )
                self.assertIs(request.call_args.kwargs.get("allow_redirects"), False)
                self.assertEqual(operation.state, "unresolved")
                self.assertFalse(operation.revolut_order_id)

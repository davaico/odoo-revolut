import csv
import io
import json
from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import (
    TestPointOfSaleHttpCommon,
)
from odoo.tests import tagged

from .authorization_fixtures import install_zero_reports
from .test_revolut_terminal_tip import TerminalTipFixtures


@tagged("post_install", "-at_install")
class TestRevolutManagerUi(TestPointOfSaleHttpCommon):
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"

    def test_manager_configures_and_checks_terminal_in_browser(self):
        # The manager converts an existing method in the tour; that update
        # requires an independently provisioned administrator authority.
        self.env["pos.revolut.merchant.credential"].create({
            "company_id": self.env.company.id,
            "environment": "sandbox",
            "secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        payment_method = self.env["pos.payment.method"].create(
            {
                "name": "Browser Revolut",
                "journal_id": self.bank_journal.id,
                "outstanding_account_id": (
                    self.inbound_payment_method_line.payment_account_id.id
                ),
            }
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
        real_get = requests.get
        merchant_requests = []

        def request_get(url, **kwargs):
            if url == "https://sandbox-merchant.revolut.com/api/terminals":
                merchant_requests.append((url, kwargs))
                return response
            return real_get(url, **kwargs)

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
            side_effect=request_get,
        ):
            self.start_tour(
                f"/odoo/action-{action.id}/{payment_method.id}?debug=tests",
                "pos_revolut_manager_configuration",
                login="pos_admin",
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
        self.assertEqual(len(merchant_requests), 1)
        response.raise_for_status.assert_called_once_with()


@tagged("post_install", "-at_install")
class TestRevolutRetailPosStarts(TestPointOfSaleHttpCommon):
    def test_retail_pos_starts_with_addon_installed(self):
        self.main_pos_config.with_user(self.pos_user).open_ui()

        self.start_pos_tour("pos_revolut_retail_starts")


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantPosStarts(TestPointOfSaleHttpCommon):
    def test_restaurant_table_checkout_verifies_revolut_payment(self):
        restaurant_module = self.env["ir.module.module"].search(
            [("name", "=", "pos_restaurant")], limit=1
        )
        if restaurant_module.state != "installed":
            self.skipTest("pos_restaurant is not installed in this test phase")
        method = self.env["pos.payment.method"].create({
            "name": "Revolut",
            "journal_id": self.bank_journal.id,
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": TestRevolutManagerUi.LOCATION_ID,
            "revolut_terminal_id": TestRevolutManagerUi.TERMINAL_ID,
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
                    "id": TestRevolutManagerUi.TERMINAL_ID,
                    "online": True, "operation_mode": "pos",
                    "location_id": TestRevolutManagerUi.LOCATION_ID,
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
        restaurant_module = self.env["ir.module.module"].search(
            [("name", "=", "pos_restaurant")], limit=1
        )
        if restaurant_module.state != "installed":
            self.skipTest("pos_restaurant is not installed in this test phase")
        method = self.env["pos.payment.method"].create({
            "name": "Revolut",
            "journal_id": self.bank_journal.id,
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": TestRevolutManagerUi.LOCATION_ID,
            "revolut_terminal_id": TestRevolutManagerUi.TERMINAL_ID,
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

    def _configure_revolut_checkout(self, include_bank=False):
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
        self.main_pos_config.sudo().write({
            "revolut_user_ids": [Command.set((self.env.user | self.pos_user | self.pos_admin).ids)],
        })
        self.main_pos_config.write(
            {
                "payment_method_ids": [
                    Command.link(revolut_method.id),
                    *([Command.link(self.bank_payment_method.id)] if include_bank else []),
                ],
                "auto_validate_terminal_payment": True,
                "tip_product_id": self.env["product.product"].create({
                    "name": "Verified terminal tip", "list_price": 0,
                    "taxes_id": [Command.clear()],
                }).id,
            }
        )
        self.desk_pad.write({"list_price": 12.34, "taxes_id": [Command.clear()]})
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        return revolut_method

    def test_stale_draft_sync_preserves_payment_recovery(self):
        self._configure_revolut_checkout()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_sync_recovery_payment")
            provider.assert_not_called()

    def test_stale_draft_sync_preserves_refund_recovery(self):
        self._configure_revolut_checkout()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_sync_recovery_refund")
            provider.assert_not_called()

    def test_successful_payment_is_verified_before_automatic_checkout(self):
        revolut_method = self._configure_revolut_checkout()
        calls = []
        intent_polls = 0
        payment_states = []
        processing_states = [
            "pending", "authentication_challenge", "authentication_verified",
            "authorisation_started", "authorisation_passed", "authorised", "capture_started",
        ]

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
                state = processing_states[len(payment_states)] if len(payment_states) < len(processing_states) else "captured"
                payment_states.append(state)
                return self._response(
                    {
                        "id": self.PAYMENT_ID,
                        "order_id": self.ORDER_ID,
                        "state": state,
                        "amount": 1234,
                        "currency": self.main_pos_config.currency_id.name,
                        "cardholder_name": "CARDHOLDER_CANARY_TICKET_11",
                        "card": {"pan": "PAN_CANARY_TICKET_11"},
                    }
                )
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
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
        self.assertEqual(payment_states, [*processing_states, "captured"])
        self.assertNotIn("CARDHOLDER_CANARY_TICKET_11", repr(operation.read()[0]))
        self.assertNotIn("PAN_CANARY_TICKET_11", repr(operation.read()[0]))
        mutating_calls = [call for call in calls if call[0] == "POST"]
        self.assertEqual(len(mutating_calls), 2)

    def test_terminal_tip_waits_for_report_and_recovers_after_reload(self):
        self._run_terminal_tip_checkout()

    def test_tipped_processing_payment_completes_without_manual_status(self):
        self._run_terminal_tip_checkout(processing=True)

    def test_unsaved_global_rounded_return_refunds_base_and_tip_exactly(self):
        self._run_terminal_tip_checkout(refund=True)

    def _run_terminal_tip_checkout(self, *, refund=False, processing=False):
        revolut_method = self._configure_revolut_checkout()
        base_minor, tip_minor, gross_minor = (1000, 3, 1003) if refund else (1234, 200, 1434)
        gross, tip = gross_minor / 100, tip_minor / 100
        if refund:
            self.desk_pad.list_price = 10.02
            self.main_pos_config.write({
                "cash_rounding": True, "only_round_cash_method": False,
                "rounding_method": self.env["account.cash.rounding"].create({
                    "name": "Native terminal return rounding", "rounding": 0.05,
                    "rounding_method": "HALF-UP", "strategy": "add_invoice_line",
                }).id,
            })
        run_id = str(uuid4())
        currency = self.main_pos_config.currency_id.name
        created = TerminalTipFixtures.created_at
        report_polls = 0
        payment_polls = 0
        calls = []
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=TerminalTipFixtures.columns)
        writer.writeheader()
        writer.writerow({
            "payment_id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
            "currency": currency, "location_id": self.LOCATION_ID,
            "type": "PAYMENT", "state": "CAPTURED", "amount": f"{gross:.2f}",
            "tip_amount": f"{tip:.2f}", "surcharge_amount": "", "refunded_amount": "0.00",
            "created_date": created + "[UTC]", "captured_date": "2026-10-01T10:00:10Z[UTC]",
        })
        report_csv = output.getvalue().encode()

        def response(payload):
            content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            result = Mock(status_code=200)
            result.json.return_value = payload
            result.iter_content.return_value = [content]
            return result

        def request(method, url, **kwargs):
            nonlocal report_polls, payment_polls
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                return response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True, "operation_mode": "pos",
                    "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                self.assertEqual(kwargs["json"]["amount"], base_minor)
                return response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                self.assertEqual(kwargs["json"]["amount"], base_minor)
                return response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and url.endswith(f"/api/payment-intents/{self.INTENT_ID}"):
                return response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "amount": base_minor, "currency": currency, "terminal_id": self.TERMINAL_ID,
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if method == "GET" and url.endswith(f"/api/payments/{self.PAYMENT_ID}"):
                payment_polls += 1
                state = ("authorised", "capture_started", "captured")[min(payment_polls - 1, 2)] if processing else "captured"
                return response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "amount": gross_minor, "currency": currency,
                    "state": state, "created_at": created,
                })
            if method == "POST" and url.endswith("/api/report-runs"):
                return response({"report_run_id": run_id, "status": "completed" if refund or processing else "processing"})
            if method == "GET" and url.endswith(f"/api/report-runs/{run_id}"):
                report_polls += 1
                if processing:
                    return response({"report_run_id": run_id, "status": "completed"})
                if report_polls == 3:
                    # Lose report transport after two processing observations;
                    # the native POS must retain the captured operation on reload.
                    raise requests.ConnectionError("Mocked report transport interruption")
                return response({"report_run_id": run_id,
                                 "status": "processing" if report_polls < 3 else "completed"})
            if method == "GET" and url.endswith(f"/api/report-runs/{run_id}/file"):
                return response(report_csv)
            if method == "GET" and url.endswith(f"/api/orders/{self.ORDER_ID}"):
                return response({
                    "id": self.ORDER_ID, "currency": currency, "location_id": self.LOCATION_ID,
                    "type": "payment", "state": "completed", "amount": gross_minor,
                    "refunded_amount": 0,
                    "payments": [{"id": self.PAYMENT_ID, "state": "captured", "amount": gross_minor}],
                })
            if refund and method == "POST" and url.endswith("/refund"):
                self.assertEqual(kwargs["json"]["amount"], 1003)
                return response({"id": self.REFUND_ID, "state": "pending", "type": "refund",
                                 "amount": 1003, "currency": currency, "related_order_id": self.ORDER_ID})
            if refund and method == "GET" and url.endswith(f"/api/orders/{self.REFUND_ID}"):
                return response({"id": self.REFUND_ID, "state": "completed", "type": "refund",
                                 "amount": 1003, "currency": currency, "related_order_id": self.ORDER_ID})
            raise AssertionError(f"Unexpected mocked Revolut request: {method} {url}")

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=request):
            self.start_pos_tour("pos_revolut_global_rounded_tip_return" if refund
                                else "pos_revolut_tipped_processing_checkout" if processing
                                else "pos_revolut_terminal_tip_report_reload",
                                login="pos_admin" if refund else "pos_user")

        self.env.invalidate_all()
        if processing:
            self.assertEqual(payment_polls, 3)
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", revolut_method.id),
        ])
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.amount_minor, base_minor)
        self.assertEqual(operation.gross_amount_minor, gross_minor)
        self.assertEqual(operation.terminal_tip_minor, tip_minor)
        self.assertEqual(operation.report_run_id, run_id)
        order = operation.pos_order_id
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.amount_total, gross)
        self.assertEqual(order.amount_paid, gross)
        tips = order.lines.filtered(lambda line: line.product_id == order.config_id.tip_product_id)
        self.assertEqual(len(tips), 1)
        self.assertEqual(tips.price_subtotal_incl, tip)
        self.assertEqual(operation.pos_payment_id.amount, gross)
        self.assertEqual(operation.authorization_id.projection_revision, 1)
        if not refund and not processing:
            self.assertGreaterEqual(report_polls, 4)
        financial_posts = [call for call in calls if call[0] == "POST" and "/api/report-runs" not in call[1]]
        self.assertEqual(len(financial_posts), 3 if refund else 2)
        self.assertEqual(len([call for call in calls if call[0] == "POST" and call[1].endswith("/api/report-runs")]), 1)
        self.assertEqual(operation.pos_payment_id.transaction_id, operation.revolut_payment_id)
        self.assertEqual(operation.pos_payment_id.payment_ref_no, operation.revolut_order_id)
        self.assertEqual(operation.pos_payment_id.ticket.count(operation.revolut_payment_id), 1)
        self.assertTrue(operation.verified_at)
        if refund:
            returned = self.env["pos.revolut.refund.operation"].search([
                ("original_operation_id", "=", operation.id),
            ])
            self.assertEqual(len(returned), 1)
            self.assertEqual(returned.state, "verified")
            self.assertEqual((returned.base_amount_minor, returned.tip_amount_minor, returned.amount_minor),
                             (1000, 3, 1003))
            self.assertEqual(returned.pos_order_id.state, "paid")
            self.assertEqual(returned.pos_order_id.amount_total, -10.03)
            self.assertEqual(returned.pos_payment_id.amount, -10.03)
            self.assertEqual(len(returned.pos_order_id.lines), 2)

    def test_cash_and_bank_still_checkout_without_revolut_dispatch(self):
        self._configure_revolut_checkout(include_bank=True)
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ) as request:
            self.start_pos_tour("pos_revolut_other_tenders_checkout")

        self.env.invalidate_all()
        orders = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id),
            ("state", "=", "paid"),
        ])
        self.assertEqual(len(orders), 2)
        self.assertEqual(
            {order.payment_ids.payment_method_id.name for order in orders},
            {"Cash", "Bank"},
        )
        request.assert_not_called()

    def test_split_cash_and_revolut_checkout_uses_remaining_line_amount(self):
        revolut_method = self._configure_revolut_checkout()
        calls = []
        payment_polls = 0

        def request(method, url, **kwargs):
            nonlocal payment_polls
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                return self._response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                return self._response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if method == "GET" and "/api/payments/" in url:
                payment_polls += 1
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "state": "pending" if payment_polls == 1 else "captured", "amount": 434,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_split_cash_checkout")

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search(
            [("payment_method_id", "=", revolut_method.id)]
        )
        order = operation.pos_order_id
        self.assertEqual(order.state, "paid")
        self.assertEqual(operation.amount_minor, 434)
        self.assertEqual(len(order.payment_ids), 2)
        self.assertEqual(operation.pos_payment_id.amount, 4.34)
        posts = [call for call in calls if call[0] == "POST"]
        self.assertEqual(posts[0][2]["json"]["amount"], 434)
        self.assertEqual(posts[1][2]["json"]["amount"], 434)
        self.assertEqual(payment_polls, 2)

    def test_processing_multiple_card_lines_preserve_partial_due_and_complete_automatically(self):
        revolut_method = self._configure_revolut_checkout()
        attempts = {}
        calls = []

        def request(method, url, **kwargs):
            calls.append((method, url))
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                order_id = str(uuid4())
                attempts[order_id] = {
                    "order_id": order_id, "intent_id": str(uuid4()), "payment_id": str(uuid4()),
                    "amount": kwargs["json"]["amount"], "polls": 0,
                }
                return self._response({"id": order_id})
            if method == "POST" and url.endswith("/payment-intents"):
                order_id = url.split("/api/orders/")[1].split("/")[0]
                attempt = attempts[order_id]
                self.assertEqual(kwargs["json"]["amount"], attempt["amount"])
                return self._response({"id": attempt["intent_id"], "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                attempt = next(item for item in attempts.values() if url.endswith(item["intent_id"]))
                return self._response({
                    "id": attempt["intent_id"], "order_id": attempt["order_id"],
                    "state": "completed", "payment_id": attempt["payment_id"],
                })
            if method == "GET" and "/api/payments/" in url:
                attempt = next(item for item in attempts.values() if url.endswith(item["payment_id"]))
                states = ["pending", "authorisation_started", "capture_started", "captured"]
                state = states[min(attempt["polls"], 3)]
                attempt["polls"] += 1
                return self._response({
                    "id": attempt["payment_id"], "order_id": attempt["order_id"],
                    "state": state, "amount": attempt["amount"],
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_processing_multiple_cards")

        self.env.invalidate_all()
        operations = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", revolut_method.id),
        ], order="id")
        self.assertEqual(len(operations), 2)
        self.assertEqual(operations.mapped("state"), ["verified", "verified"])
        self.assertEqual(operations.mapped("amount_minor"), [1233, 1])
        self.assertEqual(len(operations.mapped("payment_line_uuid")), 2)
        self.assertEqual(len(set(operations.mapped("payment_line_uuid"))), 2)
        self.assertEqual(len(operations.pos_order_id), 1)
        self.assertEqual(operations.pos_order_id.state, "paid")
        self.assertEqual(operations.pos_payment_id.mapped("amount"), [12.33, 0.01])
        self.assertEqual(set(operations.pos_payment_id.mapped("transaction_id")),
                         {item["payment_id"] for item in attempts.values()})
        self.assertEqual([item["polls"] for item in attempts.values()], [4, 4])
        self.assertEqual(len([call for call in calls if call[0] == "POST"]), 4)

    def test_reload_recovers_late_success_without_new_charge(self):
        revolut_method = self._configure_revolut_checkout()
        calls = []
        intent_polls = 0

        def request(method, url, **kwargs):
            nonlocal intent_polls
            calls.append((method, url))
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                return self._response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                intent_polls += 1
                if intent_polls == 1:
                    raise requests.ConnectionError("test interruption")
                return self._response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if method == "GET" and "/api/payments/" in url:
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "amount": 1234, "currency": self.main_pos_config.currency_id.name,
                    "state": "captured",
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_reload_late_success")

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", revolut_method.id),
        ])
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(operation.revolut_payment_id, self.PAYMENT_ID)
        self.assertEqual(len([call for call in calls if call[0] == "POST"]), 2)

    def test_pending_cancellation_preserves_unpaid_order(self):
        revolut_method = self._configure_revolut_checkout()
        cancelled = False
        cancel_calls = 0

        def request(method, url, **kwargs):
            nonlocal cancelled, cancel_calls
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response(
                    {"terminals": [{
                        "id": self.TERMINAL_ID,
                        "online": True,
                        "operation_mode": "pos",
                        "location_id": self.LOCATION_ID,
                    }]}
                )
            if method == "POST" and url.endswith("/api/orders"):
                return self._response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "POST" and url.endswith("/cancel"):
                cancel_calls += 1
                cancelled = True
                return self._response({"id": self.INTENT_ID, "state": "cancelled"})
            if method == "GET" and "/api/payment-intents/" in url:
                return self._response(
                    {
                        "id": self.INTENT_ID,
                        "order_id": self.ORDER_ID,
                        "state": "cancelled" if cancelled else "pending",
                    }
                )
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_pending_cancel")

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search(
            [("payment_method_id", "=", revolut_method.id)]
        )
        self.assertEqual(operation.state, "cancelled")
        self.assertNotEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(cancel_calls, 1)

    def _run_unclaimed_worker_recovery(self, stage):
        revolut_method = self._configure_revolut_checkout()
        session = self.main_pos_config.current_session_id
        stopped = False
        calls = []
        provider_orders = []
        payment_model = type(revolut_method)
        original_claim = payment_model._claim_revolut_dispatch_owned
        original_start = payment_model.revolut_start_payment

        class StoppedWorker(RuntimeError):
            pass

        def start(method, *args, **kwargs):
            try:
                return original_start(method, *args, **kwargs)
            except StoppedWorker:
                # HttpCase shares a rollback cursor across HTTP requests. Its
                # exception dispatcher would erase the committed reservation,
                # unlike a real stopped process. Lose the response at this
                # test RPC boundary after the original worker has terminated.
                return False

        def claim(method, operation_id, action):
            nonlocal stopped
            if stage == "intent" and action == "create_intent" and not stopped:
                stopped = True
                # The original request ends here permanently; no later worker
                # resume is used to make recovery appear successful.
                raise StoppedWorker("Simulated worker stop before intent claim")
            return original_claim(method, operation_id, action)

        def request(method, url, **kwargs):
            nonlocal stopped
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                if stage == "order" and not stopped:
                    stopped = True
                    raise StoppedWorker("Simulated worker stop before order claim")
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                order_id = str(uuid4())
                provider_orders.append(order_id)
                return self._response({"id": order_id})
            if method == "POST" and url.endswith("/payment-intents"):
                self.assertTrue(url.endswith(f"/{provider_orders[-1]}/payment-intents"))
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                return self._response({
                    "id": self.INTENT_ID, "order_id": provider_orders[-1],
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if method == "GET" and "/api/payments/" in url:
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": provider_orders[-1],
                    "state": "captured", "amount": 1234,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch.object(payment_model, "revolut_start_payment", start), patch.object(
            payment_model, "_claim_revolut_dispatch_owned", claim
        ), patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_unclaimed_worker_recovery")

        self.env.invalidate_all()
        self.assertTrue(stopped)
        operations = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", revolut_method.id),
        ], order="id")
        self.assertEqual(len(operations), 2)
        original, replacement = operations
        self.assertEqual(original.state, "cancelled")
        self.assertTrue(original.retry_safe)
        self.assertFalse(original.blocking_order_key)
        self.assertFalse(original.blocking_terminal_key)
        self.assertFalse(original.revolut_payment_intent_id)
        self.assertFalse(original.revolut_payment_id)
        self.assertTrue(original.authorization_id.exists())
        claims = self.env["pos.revolut.payment.dispatch"].search([
            ("operation_id", "=", original.id),
        ])
        if stage == "intent":
            self.assertEqual(claims.action, "create_order")
            self.assertEqual(claims.outcome, "succeeded")
            self.assertEqual(claims.provider_reference, original.revolut_order_id)
            self.assertNotEqual(original.revolut_order_id, replacement.revolut_order_id)
        else:
            self.assertFalse(claims)
            self.assertFalse(original.revolut_order_id)
        self.assertEqual(replacement.state, "verified")
        self.assertEqual(original.pos_order_id, replacement.pos_order_id)
        self.assertEqual(original.order_uuid, replacement.order_uuid)
        self.assertNotEqual(original.payment_line_uuid, replacement.payment_line_uuid)
        self.assertEqual(original.financial_snapshot, replacement.financial_snapshot)
        # Retiring the old native UUID fences its admission. The unchanged
        # basket receives fresh authority for the explicit replacement tender.
        self.assertGreater(replacement.cart_version, original.cart_version)
        self.assertEqual(original.authorization_id.state, "revoked")
        self.assertNotEqual(original.authorization_id, replacement.authorization_id)
        self.assertEqual(operations.mapped("amount_minor"), [1234, 1234])
        self.assertEqual(operations.mapped("currency_code"), [session.currency_id.name] * 2)
        self.assertEqual(replacement.revolut_order_id, provider_orders[-1])
        self.assertEqual(replacement.revolut_payment_intent_id, self.INTENT_ID)
        self.assertEqual(replacement.revolut_payment_id, self.PAYMENT_ID)
        order = replacement.pos_order_id
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.amount_total, 12.34)
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.lines.product_id, self.desk_pad.product_variant_id)
        self.assertEqual(order.lines.qty, 1)
        self.assertEqual(len(order.payment_ids), 1)
        self.assertEqual(order.payment_ids.amount, 12.34)
        self.assertEqual(order.payment_ids.transaction_id, self.PAYMENT_ID)
        self.assertEqual(order.payment_ids.payment_ref_no, provider_orders[-1])
        financial_posts = [call for call in calls if call[0] == "POST" and "/api/report-runs" not in call[1]]
        self.assertEqual(len(financial_posts), 3 if stage == "intent" else 2)
        self.assertEqual(len(provider_orders), 2 if stage == "intent" else 1)
        self.assertTrue(all(call[2]["json"]["amount"] == 1234 for call in financial_posts))
        # Replacement checkout proves the original terminal reservation was
        # released; the native close API also proves the session is unblocked.
        result = session.with_user(self.pos_admin).close_session_from_ui()
        self.assertEqual(session.state, "closed", result)

    def test_cashier_recovers_worker_stopped_before_order_claim(self):
        self._run_unclaimed_worker_recovery("order")

    def test_cashier_recovers_worker_stopped_before_intent_claim(self):
        self._run_unclaimed_worker_recovery("intent")

    def _run_unsuccessful_checkout(self, outcome, tour, retry=False):
        revolut_method = self._configure_revolut_checkout()
        calls = []
        attempt = 0
        cancelled = False
        payment_polls = 0

        def request(method, url, **kwargs):
            nonlocal attempt, cancelled, payment_polls
            calls.append((method, url))
            order_id = (
                self.ORDER_ID if attempt <= 1
                else "d40466e0-2188-41d0-bebb-aa3a930663a9"
            )
            intent_id = (
                self.INTENT_ID if attempt <= 1
                else "4ca74d24-7b42-451a-91fb-8aca308e2631"
            )
            payment_id = (
                self.PAYMENT_ID if attempt <= 1
                else "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfc0"
            )
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response(
                    {"terminals": [{
                        "id": self.TERMINAL_ID,
                        "online": True,
                        "operation_mode": "pos",
                        "location_id": self.LOCATION_ID,
                    }]}
                )
            if method == "POST" and url.endswith("/api/orders"):
                attempt += 1
                return self._response({
                    "id": self.ORDER_ID if attempt == 1
                    else "d40466e0-2188-41d0-bebb-aa3a930663a9",
                })
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": intent_id, "state": "pending"})
            if method == "POST" and url.endswith("/cancel"):
                if outcome not in {"cancelled", "cancel_race"}:
                    raise AssertionError("Only pending intents may be cancelled")
                cancelled = True
                return self._response({"id": intent_id, "state": "cancelled"})
            if method == "GET" and "/api/payment-intents/" in url:
                state = "completed"
                if outcome == "interrupted":
                    raise requests.ConnectionError("Simulated transport interruption")
                if outcome == "processing":
                    state = "processing"
                if outcome == "cancel_race" and not cancelled:
                    state = "pending"
                if outcome == "cancelled":
                    state = "cancelled" if cancelled else "pending"
                payload = {"id": intent_id, "order_id": order_id, "state": state}
                if state == "completed":
                    payload["payment_id"] = payment_id
                return self._response(payload)
            if method == "GET" and "/api/payments/" in url:
                payment_polls += 1
                state = (
                    "captured" if attempt > 1 or outcome == "cancel_race"
                    else outcome
                )
                if outcome in {"timed_out", "malformed_payment"}:
                    state = "authentication_challenge"
                elif attempt == 1 and payment_polls == 1 and outcome in {"declined", "failed"}:
                    state = "authorisation_started"
                return self._response(
                    {
                        "id": payment_id,
                        "order_id": order_id,
                        "state": state,
                        "amount": 1234.0 if outcome == "malformed_payment" else 1234,
                        "currency": self.main_pos_config.currency_id.name,
                    }
                )
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour(tour)

        self.env.invalidate_all()
        operations = self.env["pos.revolut.payment.operation"].search(
            [("payment_method_id", "=", revolut_method.id)], order="id"
        )
        self.assertEqual(len(operations), 2 if retry else 1)
        self.assertEqual(attempt, 2 if retry else 1)
        charge_dispatches = [
            call for call in calls
            if call[0] == "POST" and not call[1].endswith("/cancel")
        ]
        self.assertEqual(len(charge_dispatches), 4 if retry else 2)
        if retry:
            self.assertEqual(operations[0].state, outcome)
            self.assertEqual(operations[1].state, "verified")
            self.assertNotEqual(
                operations[0].revolut_order_id, operations[1].revolut_order_id
            )
            self.assertEqual(
                operations[0].payment_line_uuid, operations[1].payment_line_uuid
            )
            self.assertEqual(operations[1].pos_order_id.state, "paid")
        elif outcome in {"cancel_race", "captured"}:
            self.assertEqual(operations.state, "verified")
            self.assertEqual(operations.pos_order_id.state, "paid")
            self.assertEqual(
                operations.pos_order_id.payment_ids.transaction_id, self.PAYMENT_ID
            )
        else:
            self.assertNotEqual(operations.pos_order_id.state, "paid")
            self.assertEqual(operations.amount_minor, 1234)
            expected_state = {
                "declined": "declined",
                "failed": "failed",
                "cancelled": "cancelled",
                "processing": "pending",
            }.get(outcome, "unresolved")
            if outcome == "timed_out":
                # The browser deliberately does not wait for the timeout-marking
                # RPC; either server state remains financially unresolved.
                self.assertIn(operations.state, {"pending", "unresolved"})
                self.assertFalse(operations.retry_safe)
            else:
                self.assertEqual(operations.state, expected_state)
        return operations, calls

    def test_declined_payment_can_retry_once_without_duplicate_charge(self):
        self._run_unsuccessful_checkout(
            "declined", "pos_revolut_declined_retry", retry=True
        )

    def test_failed_payment_is_distinct_and_unpaid(self):
        self._run_unsuccessful_checkout("failed", "pos_revolut_failed")

    def test_interrupted_payment_stays_locked_and_check_does_not_dispatch(self):
        self._run_unsuccessful_checkout("interrupted", "pos_revolut_interrupted")

    def test_foreground_timeout_preserves_line_and_blocks_new_charge(self):
        operation, calls = self._run_unsuccessful_checkout("timed_out", "pos_revolut_timed_out")
        self.assertEqual(operation.revolut_payment_id, self.PAYMENT_ID)
        self.assertTrue(any(method == "GET" and "/api/payments/" in url for method, url in calls))

    def test_malformed_processing_amount_stays_guarded_and_check_is_read_only(self):
        operation, _calls = self._run_unsuccessful_checkout(
            "malformed_payment", "pos_revolut_malformed_processing",
        )
        self.assertEqual(operation.revolut_payment_id, self.PAYMENT_ID)
        self.assertFalse(operation.retry_safe)

    def test_processing_cannot_be_cancelled_and_amount_stays_locked(self):
        _operations, calls = self._run_unsuccessful_checkout(
            "processing", "pos_revolut_processing"
        )
        self.assertFalse(any(url.endswith("/cancel") for method, url in calls))

    def test_cancel_racing_with_capture_preserves_successful_payment(self):
        self._run_unsuccessful_checkout("cancel_race", "pos_revolut_cancel_race")

    def test_payment_discovery_failure_recovers_after_reload_with_one_start(self):
        self._run_unsuccessful_checkout("captured", "pos_revolut_payment_discovery_recovery")

    def _assert_restored_checkout(self, operation, amount, transaction_id, receipt_reference):
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.state, "verified")
        order = operation.pos_order_id
        payment = operation.pos_payment_id
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.uuid, operation.order_uuid)
        self.assertEqual(order.amount_total, amount)
        self.assertEqual(order.currency_id, self.main_pos_config.currency_id)
        self.assertEqual(order.payment_ids, payment)
        self.assertEqual(payment.uuid, operation.payment_line_uuid)
        self.assertEqual(payment.amount, amount)
        self.assertEqual(payment.transaction_id, transaction_id)
        self.assertEqual(payment.payment_ref_no, receipt_reference)
        self.assertEqual(self.env["pos.order"].search_count([
            ("uuid", "=", operation.order_uuid),
        ]), 1)

    def test_verified_payment_checkout_rejection_recovers_after_reload(self):
        operation, calls = self._run_unsuccessful_checkout(
            "captured", "pos_revolut_payment_checkout_reject",
        )
        self._assert_restored_checkout(operation, 12.34, self.PAYMENT_ID, self.ORDER_ID)
        self.assertEqual(sum(method == "POST" for method, _url in calls), 2)

    def test_verified_payment_checkout_timeout_recovers_without_second_charge(self):
        operation, calls = self._run_unsuccessful_checkout(
            "captured", "pos_revolut_payment_checkout_timeout",
        )
        self._assert_restored_checkout(operation, 12.34, self.PAYMENT_ID, self.ORDER_ID)
        self.assertEqual(sum(method == "POST" for method, _url in calls), 2)

    def test_verified_payment_checkout_offline_loader_recovers_without_second_charge(self):
        operation, calls = self._run_unsuccessful_checkout(
            "captured", "pos_revolut_payment_checkout_offline",
        )
        self._assert_restored_checkout(operation, 12.34, self.PAYMENT_ID, self.ORDER_ID)
        self.assertEqual(sum(method == "POST" for method, _url in calls), 2)

    def _run_cancelled_payment_preparation(self, stage):
        self._configure_revolut_checkout()
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Cancelled preparation must not contact Revolut"),
        ) as request:
            self.start_pos_tour(f"pos_revolut_cancel_preparation_{stage}")
        request.assert_not_called()
        self.env.invalidate_all()
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([]))
        orders = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id),
        ])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.state, "paid")
        self.assertEqual(orders.amount_total, 12.34)
        self.assertEqual(orders.payment_ids.payment_method_id.name, "Cash")

    def test_cancel_payment_while_draft_persistence_is_pending(self):
        self._run_cancelled_payment_preparation("draft")

    def test_cancel_payment_while_authorization_is_pending(self):
        self._run_cancelled_payment_preparation("authorization")

    def test_cancel_payment_while_canonical_refresh_is_pending(self):
        self._run_cancelled_payment_preparation("refresh")

    def _run_unstarted_tender_reload(self, *, resume, offline=False, lost_removal=False):
        revolut_method = self._configure_revolut_checkout()
        session = self.main_pos_config.current_session_id
        tip = self.main_pos_config.tip_product_id
        self.main_pos_config.tip_product_id = False
        calls = []

        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if not resume:
                raise AssertionError("Removing the unstarted tender must not contact Revolut")
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                self.assertEqual(kwargs["json"]["amount"], 1234)
                return self._response({"id": self.ORDER_ID})
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                return self._response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if method == "GET" and "/api/payments/" in url:
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "state": "captured", "amount": 1234,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            # The first browser saves the actual native draft before rejected
            # server preparation. A new browser cannot inherit its uiState.
            self.start_pos_tour("pos_revolut_unstarted_prepare_failure")
            provider.assert_not_called()
            self.env.invalidate_all()
            orders = self.env["pos.order"].search([
                ("session_id", "=", session.id), ("state", "=", "draft"),
            ])
            self.assertEqual(len(orders), 1)
            order = orders
            tender = order.payment_ids.filtered(lambda line: line.payment_method_id == revolut_method)
            self.assertEqual(len(tender), 1)
            original_identity = (order.id, order.uuid, tender.id, tender.uuid)
            self.assertEqual(order.amount_total, 12.34)
            self.assertEqual(tender.amount, 12.34)
            self.assertEqual(tender.payment_status, "waiting")
            self.assertFalse(tender.transaction_id)
            self.assertFalse(tender.payment_ref_no)
            self.assertFalse(order.revolut_authorization_id)
            self.assertFalse(self.env["pos.revolut.payment.operation"].search([
                ("order_uuid", "=", order.uuid),
            ]))
            # Repair the disposable configuration through Python, independently
            # of the cashier browser. Leave the original saved tender intact.
            self.main_pos_config.tip_product_id = tip
            if resume:
                install_zero_reports(self.env, provider)
            tour = "pos_revolut_unstarted_cash_removal"
            if resume:
                tour = "pos_revolut_unstarted_offline_resume" if offline else "pos_revolut_unstarted_resume"
            elif lost_removal:
                tour = "pos_revolut_unstarted_lost_removal_cash"
            self.start_pos_tour(tour)
            if not resume:
                provider.assert_not_called()

        self.env.invalidate_all()
        order = self.env["pos.order"].browse(original_identity[0]).exists()
        self.assertEqual(order.uuid, original_identity[1])
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.amount_total, 12.34)
        self.assertEqual(len(order.payment_ids), 1)
        self.assertEqual(order.lines.product_id, self.desk_pad.product_variant_id)
        self.assertEqual(order.lines.qty, 1)
        operations = self.env["pos.revolut.payment.operation"].search([
            ("order_uuid", "=", order.uuid),
        ])
        if resume:
            self.assertEqual(len(operations), 1)
            self.assertEqual(operations.state, "verified")
            self.assertEqual(operations.pos_order_id, order)
            self.assertEqual(operations.pos_payment_id.id, original_identity[2])
            self.assertEqual(operations.payment_line_uuid, original_identity[3])
            self.assertTrue(operations.authorization_id)
            self.assertEqual(order.payment_ids.transaction_id, self.PAYMENT_ID)
            financial_posts = [call for call in calls if call[0] == "POST" and "/api/report-runs" not in call[1]]
            self.assertEqual(len(financial_posts), 2)
        else:
            self.assertFalse(operations)
            self.assertFalse(self.env["pos.payment"].browse(original_identity[2]).exists())
            self.assertEqual(order.payment_ids.payment_method_id.name, "Cash")
            self.assertFalse(calls)

    def test_missing_tip_preparation_reload_resumes_original_tender_once(self):
        self._run_unstarted_tender_reload(resume=True)

    def test_missing_tip_preparation_reload_removes_original_tender_for_cash(self):
        self._run_unstarted_tender_reload(resume=False)

    def test_missing_tip_preparation_reload_recovers_after_offline_lookup(self):
        self._run_unstarted_tender_reload(resume=True, offline=True)

    def test_missing_tip_preparation_reload_recovers_after_lost_removal_response(self):
        self._run_unstarted_tender_reload(resume=False, lost_removal=True)

    def test_delayed_native_preparation_cannot_start_after_same_tender_recovery(self):
        operation, calls = self._run_unsuccessful_checkout(
            "captured", "pos_revolut_stale_preparation_recovery")
        self._assert_restored_checkout(operation, 12.34, self.PAYMENT_ID, self.ORDER_ID)
        self.assertEqual(sum(method == "POST" for method, _url in calls), 2)

    def test_payment_discovery_failure_allows_cash_without_dispatch(self):
        self._configure_revolut_checkout()
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Undispatched payment must not contact Revolut"),
        ):
            self.start_pos_tour("pos_revolut_payment_discovery_alternative")
        self.env.invalidate_all()
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([]))

    def test_invalid_payment_snapshot_recovers_after_correction_and_reload(self):
        operations, _calls = self._run_unsuccessful_checkout(
            "captured", "pos_revolut_payment_snapshot_recovery"
        )
        self.assertEqual(operations.financial_snapshot["lines"][0]["qty"], "1")
        self.assertEqual(
            operations.financial_snapshot["lines"][0]["price_unit"], "12.34"
        )
        self.assertEqual(operations.pos_order_id.uuid, operations.order_uuid)
        self.assertEqual(
            operations.pos_payment_id.uuid, operations.payment_line_uuid
        )
        self.assertEqual(operations.pos_payment_id.payment_ref_no, self.ORDER_ID)
        self.assertFalse(self.env["pos.revolut.refund.operation"].search([]))

    def test_invalid_payment_snapshot_line_can_be_removed_for_cash_without_dispatch(self):
        self._configure_revolut_checkout()
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Invalid snapshot must not contact Revolut"),
        ) as request:
            self.start_pos_tour("pos_revolut_payment_snapshot_cash_alternative")
        request.assert_not_called()

        self.env.invalidate_all()
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([]))
        self.assertFalse(self.env["pos.revolut.refund.operation"].search([]))
        orders = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id),
            ("state", "=", "paid"),
        ])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.amount_total, 12.34)
        self.assertEqual(orders.lines.qty, 1)
        self.assertEqual(orders.payment_ids.payment_method_id.name, "Cash")

    def _run_terminal_busy_checkout(self, tour, resume):
        revolut_method = self._configure_revolut_checkout()
        blocker_uuid = "d40466e0-2188-41d0-bebb-aa3a93066000"
        blocker_line_uuid = "4ca74d24-7b42-451a-91fb-8aca308e2600"
        blocker = self.env["pos.order"].with_user(self.pos_user).create({
            "name": "Independent terminal blocker", "uuid": blocker_uuid,
            "session_id": self.main_pos_config.current_session_id.id,
            "user_id": self.pos_user.id, "state": "draft",
            "pricelist_id": self.main_pos_config.pricelist_id.id,
            "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                "uuid": str(uuid4()), "product_id": self.desk_pad.id, "qty": 1,
                "price_unit": 12.34, "discount": 0, "tax_ids": [Command.clear()],
                "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
            })],
            "payment_ids": [Command.create({
                "uuid": blocker_line_uuid, "payment_method_id": revolut_method.id,
                "amount": 12.34, "payment_status": "waiting",
            })],
        })
        recovered_order_id = "d40466e0-2188-41d0-bebb-aa3a930663a9"
        recovered_intent_id = "4ca74d24-7b42-451a-91fb-8aca308e2631"
        recovered_payment_id = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfc0"
        calls = []
        order_posts = []
        cancelled = False

        def request(method, url, **kwargs):
            nonlocal cancelled
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                order_posts.append(kwargs["json"])
                if len(order_posts) > (2 if resume else 1):
                    raise AssertionError("Busy or read-only checks dispatched another order")
                return self._response({
                    "id": self.ORDER_ID if len(order_posts) == 1 else recovered_order_id,
                })
            if method == "POST" and url.endswith(f"/orders/{self.ORDER_ID}/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if method == "POST" and url.endswith(f"/orders/{recovered_order_id}/payment-intents"):
                return self._response({"id": recovered_intent_id, "state": "pending"})
            if method == "POST" and url.endswith(f"/payment-intents/{self.INTENT_ID}/cancel"):
                cancelled = True
                return self._response({"id": self.INTENT_ID, "state": "cancelled"})
            if method == "GET" and url.endswith(f"/payment-intents/{self.INTENT_ID}"):
                return self._response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "state": "cancelled" if cancelled else "pending",
                })
            if method == "GET" and url.endswith(f"/payment-intents/{recovered_intent_id}"):
                return self._response({
                    "id": recovered_intent_id, "order_id": recovered_order_id,
                    "state": "completed", "payment_id": recovered_payment_id,
                })
            if method == "GET" and url.endswith(f"/payments/{recovered_payment_id}"):
                return self._response({
                    "id": recovered_payment_id, "order_id": recovered_order_id,
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
        operations = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", revolut_method.id),
        ], order="id")
        self.assertEqual(len(operations), 2 if resume else 1)
        self.assertEqual(operations[0].pos_order_id, blocker)
        self.assertEqual(operations[0].order_uuid, blocker_uuid)
        self.assertEqual(operations[0].payment_line_uuid, blocker_line_uuid)
        self.assertTrue(operations[0].authorization_id)
        self.assertEqual(operations[0].state, "cancelled" if resume else "pending")
        self.assertNotEqual(operations[0].pos_order_id.state, "paid")
        posts = [call for call in calls if call[0] == "POST"]
        financial_posts = [call for call in posts if not call[1].endswith("/cancel")]
        self.assertEqual(len(financial_posts), 4 if resume else 2)
        self.assertEqual(len(posts) - len(financial_posts), 1 if resume else 0)
        if resume:
            recovered = operations[1]
            self.assertEqual(recovered.state, "verified")
            self.assertEqual(recovered.pos_order_id.state, "paid")
            self.assertEqual(recovered.revolut_payment_id, recovered_payment_id)
            self.assertEqual(recovered.pos_order_id.uuid, recovered.order_uuid)
            self.assertEqual(recovered.pos_payment_id.uuid, recovered.payment_line_uuid)
            self.assertNotEqual(recovered.order_uuid, operations[0].order_uuid)
            self.assertNotEqual(recovered.payment_line_uuid, operations[0].payment_line_uuid)
            self.assertEqual(order_posts[1]["metadata"]["pos_order_uuid"], recovered.order_uuid)
            self.assertEqual(
                order_posts[1]["metadata"]["pos_payment_line_uuid"], recovered.payment_line_uuid,
            )
        else:
            paid_order = self.env["pos.order"].search([
                ("session_id", "=", self.main_pos_config.current_session_id.id),
                ("state", "=", "paid"),
            ])
            self.assertEqual(len(paid_order), 1)
            self.assertEqual(paid_order.payment_ids.payment_method_id.name, "Cash")
            self.assertNotEqual(paid_order.uuid, operations[0].order_uuid)

    def test_terminal_busy_recovers_after_release_and_reload_without_duplicate_charge(self):
        self._run_terminal_busy_checkout("pos_revolut_busy_recovery", resume=True)

    def test_terminal_busy_line_can_be_removed_for_cash_without_second_dispatch(self):
        self._run_terminal_busy_checkout("pos_revolut_busy_cash_alternative", resume=False)

    REFUND_ID = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"

    def _run_full_refund(self, tour, outcome="completed", *, amount_minor=1234, next_sale=False):
        self._configure_revolut_checkout()
        calls = []
        refund_polls = 0
        refund_posts = []
        sale_count = 0
        sale_order_id = self.ORDER_ID
        sale_intent_id = self.INTENT_ID
        sale_payment_id = self.PAYMENT_ID
        sale_amount = amount_minor

        def request(method, url, **kwargs):
            nonlocal refund_polls, sale_count, sale_order_id, sale_intent_id, sale_payment_id, sale_amount
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if method == "POST" and url.endswith("/api/orders"):
                sale_count += 1
                if next_sale and sale_count == 2:
                    sale_amount = 1
                    sale_order_id = "d40466e0-2188-41d0-bebb-aa3a930663a9"
                    sale_intent_id = "4ca74d24-7b42-451a-91fb-8aca308e2631"
                    sale_payment_id = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfb0"
                self.assertEqual(kwargs["json"]["amount"], sale_amount)
                return self._response({"id": sale_order_id})
            if method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": sale_intent_id, "state": "pending"})
            if method == "GET" and "/api/payment-intents/" in url:
                return self._response({
                    "id": sale_intent_id, "order_id": sale_order_id,
                    "state": "completed", "payment_id": sale_payment_id,
                })
            if method == "GET" and "/api/payments/" in url:
                return self._response({
                    "id": sale_payment_id, "order_id": sale_order_id,
                    "state": "captured", "amount": sale_amount,
                    "currency": self.main_pos_config.currency_id.name,
                })
            if method == "POST" and url.endswith("/refund"):
                refund_posts.append(kwargs)
                if outcome == "lost_response":
                    raise requests.ConnectionError("Refund accepted but response lost")
                return self._response({
                    "id": self.REFUND_ID, "state": "pending", "type": "refund",
                    "amount": amount_minor, "currency": self.main_pos_config.currency_id.name,
                    "related_order_id": self.ORDER_ID,
                })
            if method == "GET" and url.endswith(f"/orders/{self.ORDER_ID}"):
                return self._response({
                    "id": self.ORDER_ID, "state": "completed", "type": "payment",
                    "amount": amount_minor, "currency": self.main_pos_config.currency_id.name,
                    "payments": [{"id": self.PAYMENT_ID, "state": "captured"}],
                })
            if method == "GET" and url.endswith("/api/orders"):
                return self._response({"orders": [{
                    "id": self.REFUND_ID, "type": "refund", "state": "pending",
                    "amount": amount_minor, "currency": self.main_pos_config.currency_id.name,
                    "related_order_id": self.ORDER_ID,
                    "merchant_order_data": refund_posts[0]["json"]["merchant_order_data"],
                }]})
            if method == "GET" and url.endswith(f"/orders/{self.REFUND_ID}"):
                refund_polls += 1
                return self._response({
                    "id": self.REFUND_ID, "type": "refund",
                    "state": "pending" if refund_polls < 3 else ("failed" if outcome == "failed" else "completed"),
                    "amount": amount_minor, "currency": self.main_pos_config.currency_id.name,
                    "related_order_id": self.ORDER_ID,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour(tour, login="pos_admin")
        self.assertEqual(len(refund_posts), 0 if outcome == "undispatched" else 1)
        self.assertEqual(sale_count, 2 if next_sale else 1)
        return calls

    def test_pending_refund_allows_next_sale_without_refresh(self):
        self.desk_pad.copy({"name": "One cent item", "list_price": 0.01,
                            "taxes_id": [Command.clear()]})
        self._run_full_refund("pos_revolut_refund_terminal_idle", next_sale=True)
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].search([])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "verified")
        returned = self.env["pos.order"].search([("uuid", "=", refunds.order_uuid)])
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned.state, "draft")
        sales = self.env["pos.revolut.payment.operation"].search([])
        self.assertEqual(len(sales), 2)
        self.assertEqual(set(sales.mapped("state")), {"verified"})
        self.assertEqual(set(sales.mapped("pos_order_id.state")), {"paid"})

    def test_manager_returns_full_revolut_sale_in_normal_pos_flow(self):
        self._run_full_refund("pos_revolut_full_refund")

    def _run_refund_checkout_recovery(self, kind):
        calls = self._run_full_refund(f"pos_revolut_refund_checkout_{kind}")
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self._assert_restored_checkout(refund, -12.34, self.REFUND_ID, self.REFUND_ID)
        self.assertEqual(refund.original_operation_id.state, "verified")
        self.assertEqual(refund.original_operation_id.revolut_order_id, self.ORDER_ID)
        self.assertEqual(refund.pos_order_id.lines.refunded_orderline_id,
                         refund.original_operation_id.pos_order_id.lines)
        self.assertEqual(sum(method == "POST" for method, _url, _kwargs in calls), 3)

    def test_verified_saved_refund_checkout_rejection_recovers_without_second_refund(self):
        self._run_refund_checkout_recovery("reject")

    def test_verified_saved_refund_checkout_timeout_recovers_without_second_refund(self):
        self._run_refund_checkout_recovery("timeout")

    def test_verified_saved_refund_checkout_offline_loader_recovers_without_second_refund(self):
        self._run_refund_checkout_recovery("offline")

    def test_refund_discovery_failure_recovers_after_reload_with_one_start(self):
        self._run_full_refund("pos_revolut_refund_discovery_recovery")
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refund), 1)
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.original_operation_id.revolut_order_id, self.ORDER_ID)
        self.assertEqual(refund.pos_order_id.state, "paid")
        self.assertEqual(refund.pos_order_id.uuid, refund.order_uuid)
        self.assertEqual(refund.pos_payment_id.uuid, refund.payment_line_uuid)
        self.assertEqual(refund.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refund.pos_payment_id.payment_ref_no, self.REFUND_ID)

    def test_refund_discovery_failure_allows_cash_without_refund_dispatch(self):
        self._run_full_refund("pos_revolut_refund_discovery_alternative", "undispatched")
        self.env.invalidate_all()
        self.assertFalse(self.env["pos.revolut.refund.operation"].search([]))

    def test_invalid_refund_snapshot_recovers_after_correction_and_reload(self):
        calls = self._run_full_refund("pos_revolut_refund_snapshot_recovery")
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].search([])
        payments = self.env["pos.revolut.payment.operation"].search([])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(len(payments), 1)
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(refunds.financial_snapshot["lines"][0]["qty"], "-1")
        self.assertEqual(
            refunds.financial_snapshot["lines"][0]["refunded_orderline_id"],
            payments.pos_order_id.lines.id,
        )
        self.assertEqual(refunds.original_operation_id, payments)
        self.assertEqual(refunds.original_operation_id.state, "verified")
        self.assertEqual(refunds.revolut_order_id, self.REFUND_ID)
        self.assertEqual(refunds.pos_order_id.state, "paid")
        self.assertEqual(refunds.pos_order_id.uuid, refunds.order_uuid)
        self.assertEqual(refunds.pos_payment_id.uuid, refunds.payment_line_uuid)
        self.assertEqual(refunds.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refunds.pos_payment_id.payment_ref_no, self.REFUND_ID)
        self.assertEqual(sum(method == "POST" for method, _url, _kwargs in calls), 3)

    def test_lost_refund_response_recovers_after_reload_without_second_refund(self):
        self._run_full_refund("pos_revolut_refund_reload", "lost_response")
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(refunds.original_operation_id.revolut_order_id, self.ORDER_ID)
        self.assertEqual(refunds.pos_order_id.state, "paid")
        self.assertEqual(refunds.pos_order_id.uuid, refunds.order_uuid)
        self.assertEqual(refunds.pos_payment_id.uuid, refunds.payment_line_uuid)
        self.assertEqual(refunds.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refunds.pos_payment_id.payment_ref_no, self.REFUND_ID)

    def test_completed_refund_recovers_from_saved_return_without_browser_state(self):
        self._run_full_refund("pos_revolut_refund_server_recovery")
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(refunds.pos_order_id.state, "paid")
        self.assertEqual(refunds.pos_order_id.uuid, refunds.order_uuid)
        self.assertEqual(refunds.pos_payment_id.uuid, refunds.payment_line_uuid)
        self.assertEqual(refunds.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refunds.pos_payment_id.payment_ref_no, self.REFUND_ID)

    def test_pending_refund_recovers_from_saved_return_without_browser_state(self):
        calls = self._run_full_refund("pos_revolut_pending_refund_server_recovery")
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.state, "verified")
        self.assertEqual(refunds.original_operation_id.revolut_order_id, self.ORDER_ID)
        self.assertEqual(refunds.pos_order_id.state, "paid")
        self.assertEqual(refunds.pos_order_id.uuid, refunds.order_uuid)
        self.assertEqual(refunds.pos_payment_id.uuid, refunds.payment_line_uuid)
        self.assertEqual(refunds.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refunds.pos_payment_id.payment_ref_no, self.REFUND_ID)
        self.assertEqual(sum(
            method == "POST" and url.endswith("/refund")
            for method, url, _kwargs in calls
        ), 1)
        self.assertEqual(sum(
            method == "GET" and url.endswith(f"/orders/{self.REFUND_ID}")
            for method, url, _kwargs in calls
        ), 3)

    def test_failed_refund_stays_unpaid_and_cannot_be_substituted(self):
        self._run_full_refund("pos_revolut_refund_failed", "failed")

from unittest.mock import Mock, patch

import requests

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import (
    TestPointOfSaleHttpCommon,
)
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestRevolutManagerUi(TestPointOfSaleHttpCommon):
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"

    def test_manager_configures_and_checks_terminal_in_browser(self):
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

    def _configure_revolut_checkout(self):
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
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        return revolut_method

    def test_successful_payment_is_verified_before_automatic_checkout(self):
        revolut_method = self._configure_revolut_checkout()
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

    def test_split_cash_and_revolut_checkout_uses_remaining_line_amount(self):
        revolut_method = self._configure_revolut_checkout()
        calls = []

        def request(method, url, **kwargs):
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
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "state": "captured", "amount": 434,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ):
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
        ):
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
        ):
            self.start_pos_tour("pos_revolut_pending_cancel")

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search(
            [("payment_method_id", "=", revolut_method.id)]
        )
        self.assertEqual(operation.state, "cancelled")
        self.assertNotEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(cancel_calls, 1)

    def _run_unsuccessful_checkout(self, outcome, tour, retry=False):
        revolut_method = self._configure_revolut_checkout()
        calls = []
        attempt = 0
        cancelled = False

        def request(method, url, **kwargs):
            nonlocal attempt, cancelled
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
                if outcome in {"processing", "timed_out"}:
                    state = "processing" if outcome == "processing" else "pending"
                if outcome == "cancel_race" and not cancelled:
                    state = "pending"
                if outcome == "cancelled":
                    state = "cancelled" if cancelled else "pending"
                payload = {"id": intent_id, "order_id": order_id, "state": state}
                if state == "completed":
                    payload["payment_id"] = payment_id
                return self._response(payload)
            if method == "GET" and "/api/payments/" in url:
                state = (
                    "captured" if attempt > 1 or outcome == "cancel_race"
                    else outcome
                )
                return self._response(
                    {
                        "id": payment_id,
                        "order_id": order_id,
                        "state": state,
                        "amount": 1234,
                        "currency": self.main_pos_config.currency_id.name,
                    }
                )
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ):
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
        elif outcome == "cancel_race":
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
        self._run_unsuccessful_checkout("timed_out", "pos_revolut_timed_out")

    def test_processing_cannot_be_cancelled_and_amount_stays_locked(self):
        _operations, calls = self._run_unsuccessful_checkout(
            "processing", "pos_revolut_processing"
        )
        self.assertFalse(any(url.endswith("/cancel") for method, url in calls))

    def test_cancel_racing_with_capture_preserves_successful_payment(self):
        self._run_unsuccessful_checkout("cancel_race", "pos_revolut_cancel_race")

    REFUND_ID = "6c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"

    def _run_full_refund(self, tour, outcome="completed"):
        self._configure_revolut_checkout()
        refund_polls = 0
        refund_posts = []

        def request(method, url, **kwargs):
            nonlocal refund_polls
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
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "state": "captured", "amount": 1234,
                    "currency": self.main_pos_config.currency_id.name,
                })
            if method == "POST" and url.endswith("/refund"):
                refund_posts.append(kwargs)
                if outcome == "lost_response":
                    raise requests.ConnectionError("Refund accepted but response lost")
                return self._response({
                    "id": self.REFUND_ID, "state": "pending", "type": "refund",
                    "amount": 1234, "currency": self.main_pos_config.currency_id.name,
                    "related_order_id": self.ORDER_ID,
                })
            if method == "GET" and url.endswith(f"/orders/{self.ORDER_ID}"):
                return self._response({
                    "id": self.ORDER_ID, "state": "completed", "type": "payment",
                    "amount": 1234, "currency": self.main_pos_config.currency_id.name,
                    "payments": [{"id": self.PAYMENT_ID, "state": "captured"}],
                })
            if method == "GET" and url.endswith("/api/orders"):
                return self._response({"orders": [{
                    "id": self.REFUND_ID, "type": "refund", "state": "pending",
                    "amount": 1234, "currency": self.main_pos_config.currency_id.name,
                    "related_order_id": self.ORDER_ID,
                    "merchant_order_data": refund_posts[0]["json"]["merchant_order_data"],
                }]})
            if method == "GET" and url.endswith(f"/orders/{self.REFUND_ID}"):
                refund_polls += 1
                return self._response({
                    "id": self.REFUND_ID, "type": "refund",
                    "state": "pending" if refund_polls < 3 else ("failed" if outcome == "failed" else "completed"),
                    "amount": 1234, "currency": self.main_pos_config.currency_id.name,
                    "related_order_id": self.ORDER_ID,
                })
            raise AssertionError(f"Unexpected Revolut request: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ):
            self.start_pos_tour(tour, login="pos_admin")
        self.assertEqual(len(refund_posts), 1)

    def test_manager_returns_full_revolut_sale_in_normal_pos_flow(self):
        self._run_full_refund("pos_revolut_full_refund")

    def test_lost_refund_response_recovers_after_reload_without_second_refund(self):
        self._run_full_refund("pos_revolut_refund_reload", "lost_response")

    def test_failed_refund_stays_unpaid_and_cannot_be_substituted(self):
        self._run_full_refund("pos_revolut_refund_failed", "failed")

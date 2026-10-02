"""Public polling/reconciliation tests using the documented payments CSV schema."""
import csv
import io
import json
import os
from datetime import timedelta
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests.common import tagged


class TerminalTipFixtures:
    """Provider fixtures shared with integrated refund/receipt tests.

    CSV columns and values follow Report-Run-Csv-Payments and Res-Payments-Report
    in the official 2026-08-17 OpenAPI, including blank surcharge and explicit
    decimal zero tip. Nonzero examples exercise the selected design inference;
    they are not physical-terminal acceptance evidence.
    """
    created_at = "2026-10-01T10:00:00Z"
    columns = (
        "payment_id", "type", "order_id", "state", "amount", "currency",
        "surcharge_amount", "tip_amount", "refunded_amount", "created_date",
        "captured_date", "location_id",
    )

    def response(self, payload, status=200):
        content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        response = Mock(status_code=status)
        response.json.return_value = payload
        response.iter_content.return_value = [content]
        return response

    def report_row(self, **overrides):
        return dict({
            "payment_id": self.provider_payment_id, "type": "PAYMENT",
            "order_id": self.provider_order_id, "state": "COMPLETED",
            "amount": f"{self.gross_minor / 100:.2f}", "currency": self.order.currency_id.name,
            "surcharge_amount": "", "tip_amount": f"{self.tip_minor / 100:.2f}",
            "refunded_amount": "0.00", "created_date": self.created_at,
            "captured_date": "2026-10-01T10:00:10Z", "location_id": self.method.revolut_location_id,
        }, **overrides)

    def report_csv(self, rows=None):
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=self.columns)
        writer.writeheader()
        writer.writerows(rows if rows is not None else [self.report_row()])
        return output.getvalue().encode()

    def provider_response(self, method, url, **kwargs):
        path = urlsplit(url).path
        if path == "/api/terminals" and method == "GET":
            return self.response({"terminals": [{"id": self.method.revolut_terminal_id,
                "online": True, "operation_mode": "pos", "location_id": self.method.revolut_location_id}]})
        if path == "/api/orders" and method == "POST":
            return self.response({"id": self.provider_order_id})
        if path == f"/api/orders/{self.provider_order_id}/payment-intents" and method == "POST":
            return self.response({"id": self.provider_intent_id, "state": "pending"})
        if path == f"/api/payment-intents/{self.provider_intent_id}" and method == "GET":
            return self.response({"id": self.provider_intent_id, "order_id": self.provider_order_id,
                "state": "completed", "payment_id": self.provider_payment_id,
                "amount": getattr(self, "base_minor", 10000), "currency": self.order.currency_id.name,
                "terminal_id": self.method.revolut_terminal_id})
        if path == f"/api/payments/{self.provider_payment_id}" and method == "GET":
            return self.response({"id": self.provider_payment_id, "order_id": self.provider_order_id,
                "amount": self.gross_minor, "currency": self.order.currency_id.name,
                "state": "captured", "created_at": self.created_at})
        if path == "/api/report-runs" and method == "POST":
            self.report_post_count += 1
            self.active_run_id = str(uuid4())
            return self.response({"report_run_id": self.active_run_id, "status": self.report_status,
                                  "file_url": "https://untrusted.invalid/stolen-report"})
        if path == f"/api/report-runs/{self.active_run_id}" and method == "GET":
            return self.response({"report_run_id": self.active_run_id, "status": self.report_status})
        if path == f"/api/report-runs/{self.active_run_id}/file" and method == "GET":
            return self.response(self.csv_content if self.csv_content is not None else self.report_csv())
        if path == f"/api/orders/{self.provider_order_id}" and method == "GET":
            return self.response({"id": self.provider_order_id, "currency": self.order.currency_id.name,
                "location_id": self.method.revolut_location_id,
                "payments": self.order_payments if self.order_payments is not None else [
                    {"id": self.provider_payment_id, "state": "captured", "amount": self.gross_minor}]})
        raise AssertionError(f"Unexpected mocked provider call: {method} {path}")


@tagged("post_install", "-at_install")
class TestRevolutTerminalTip(TerminalTipFixtures, CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.method = cls.bank_payment_method.copy({
            "name": "Revolut report evidence", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TIP_TEST",
            "revolut_fulfilment_type": "eat_in",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Terminal-tip base cart", "available_in_pos": True,
            "list_price": 100, "taxes_id": [Command.clear()],
        })
        cls.tip_product = cls.env["product.product"].create({
            "name": "Reported terminal tip", "list_price": 0, "taxes_id": [Command.clear()],
        })
        cls.tip_pricelist = cls.env["product.pricelist"].create({
            "name": "Terminal tip report prices", "currency_id": cls.pos_config_usd.currency_id.id,
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.method.id)],
            "auto_validate_terminal_payment": True, "tip_product_id": cls.tip_product.id,
            "use_pricelist": True,
            "pricelist_id": cls.tip_pricelist.id,
            "available_pricelist_ids": [Command.link(cls.tip_pricelist.id)],
        })

    def setUp(self):
        super().setUp()
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        self.order = self.env["pos.order"].create({
            "session_id": self.session.id, "uuid": str(uuid4()),
            "amount_total": 100, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "pricelist_id": self.pos_config_usd.pricelist_id.id,
            "lines": [Command.create({"product_id": self.product.id, "qty": 1,
                "price_unit": 100, "price_subtotal": 100, "price_subtotal_incl": 100,
                "tax_ids": [Command.clear()]})],
        })
        self.line_uuid = str(uuid4())
        self.provider_order_id, self.provider_intent_id, self.provider_payment_id = [str(uuid4()) for _ in range(3)]
        self.gross_minor, self.tip_minor = 10300, 300
        self.report_status = "processing"
        self.active_run_id = ""
        self.report_post_count = 0
        self.csv_content = None
        self.order_payments = None
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_TIP_TEST": "test-only"}))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=self.provider_response))

    def start_payment(self):
        prepared = self.env["pos.order"].revolut_prepare_payment(
            self.order.id, self.order.uuid, 0,
            [{"uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 100}],
        )
        started = self.method.revolut_start_payment(
            self.session.id, self.order.uuid, self.line_uuid, 100, self.order.currency_id.id,
            False, False, prepared["authorization_id"], prepared["cart_version"], prepared["tender_revision"],
        )
        self.assertIn("operation_id", started, started)
        self.operation_id = started["operation_id"]
        return started

    def poll_payment(self):
        return self.method.revolut_poll_payment(self.operation_id, self.order.uuid, self.line_uuid)

    def financial_post_count(self):
        return sum(call.args[0] == "POST" and urlsplit(call.args[1]).path != "/api/report-runs"
                   for call in self.request.call_args_list)

    def test_capture_waits_for_report_then_projects_tip_once(self):
        self.start_payment()
        waiting = self.poll_payment()
        self.assertEqual(waiting["state"], "pending")
        self.assertTrue(waiting["awaiting_tip_details"])
        self.assertFalse(waiting["retry_safe"])
        self.assertEqual(waiting["captured_amount_minor"], 10300)
        self.assertEqual(self.financial_post_count(), 2)
        self.report_status = "completed"
        verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(verified["gross_amount_minor"], 10300)
        self.assertEqual(verified["terminal_tip_minor"], 300)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.amount_total, 103)
        self.assertEqual(len(self.order.lines.filtered(lambda line: line.product_id == self.tip_product)), 1)
        self.assertEqual(self.poll_payment(), verified)
        self.assertEqual(self.financial_post_count(), 2)
        self.assertEqual(self.report_post_count, 1)

    def test_tip_product_reconfiguration_during_report_keeps_original_projection(self):
        self.start_payment()
        self.assertTrue(self.poll_payment()["awaiting_tip_details"])
        replacement = self.env["product.product"].create({"name": "Replacement terminal tip",
            "list_price": 0, "taxes_id": [Command.clear()]})
        self.pos_config_usd.tip_product_id = replacement
        self.env.flush_all()
        self.env.invalidate_all()
        self.report_status = "completed"
        verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.env.invalidate_all()
        tip = self.order.lines.filtered(lambda line: line.product_id == self.tip_product)
        self.assertEqual(len(tip), 1)
        self.assertFalse(self.order.lines.filtered(lambda line: line.product_id == replacement))
        self.assertEqual(tip.price_subtotal_incl, 3)
        self.assertEqual(self.order.amount_total, 103)
        self.assertEqual(self.order.payment_ids.amount, 103)
        self.assertEqual(self.financial_post_count(), 2)
        self.env["pos.order"].sync_from_ui([{
            "uuid": self.order.uuid, "session_id": self.session.id, "state": "paid",
            "date_order": fields.Datetime.to_string(fields.Datetime.now()), "sequence_number": 1,
            "name": f"Order {self.order.uuid}", "amount_total": 103, "amount_paid": 103,
            "amount_tax": 0, "amount_return": 0, "to_invoice": False,
            "lines": [], "payment_ids": [],
        }])
        self.env.invalidate_all()
        returned = {"uuid": str(uuid4()), "session_id": self.session.id, "state": "draft",
            "currency_id": self.order.currency_id.id, "pricelist_id": self.order.pricelist_id.id,
            "fiscal_position_id": self.order.fiscal_position_id.id,
            "amount_total": -103, "amount_paid": -103, "amount_tax": 0, "amount_return": 0,
            "lines": [Command.create({"uuid": str(uuid4()), "product_id": line.product_id.id,
                "qty": -line.qty, "price_unit": line.price_unit, "discount": 0,
                "price_subtotal": -line.price_subtotal, "price_subtotal_incl": -line.price_subtotal_incl,
                "tax_ids": [Command.set(line.tax_ids.ids)], "refunded_orderline_id": line.id})
                for line in self.order.lines],
            "payment_ids": [Command.create({"uuid": str(uuid4()), "payment_method_id": self.method.id,
                "amount": -103, "payment_status": "waiting"})]}
        sources = self.method.revolut_refund_sources(self.session.id, self.order.currency_id.id, returned)
        self.assertEqual(len(sources), 1)
        self.assertEqual((sources[0]["base_amount_minor"], sources[0]["tip_amount_minor"]), (10000, 300))
        self.assertEqual((sources[0]["return_base_minor"], sources[0]["return_tip_minor"]), (10000, 300))
        self.assertEqual(self.financial_post_count(), 2)

    def test_sequential_tips_keep_one_original_product_after_configuration_change(self):
        second_uuid = str(uuid4())
        plan = [{"uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 40},
                {"uuid": second_uuid, "payment_method_id": self.method.id, "amount": 60}]
        prepared = self.env["pos.order"].revolut_prepare_payment(self.order.id, self.order.uuid, 0, plan)
        self.base_minor, self.gross_minor, self.tip_minor = 4000, 4300, 300
        self.report_status = "completed"
        first = self.method.revolut_start_payment(self.session.id, self.order.uuid, self.line_uuid,
            40, self.order.currency_id.id, False, False, prepared["authorization_id"],
            prepared["cart_version"], prepared["tender_revision"])
        self.operation_id = first["operation_id"]
        self.assertEqual(self.poll_payment()["state"], "verified")
        replacement = self.env["product.product"].create({"name": "New terminal tip configuration",
            "list_price": 0, "taxes_id": [Command.clear()]})
        self.pos_config_usd.tip_product_id = replacement
        self.env.flush_all()
        self.env.invalidate_all()
        self.provider_order_id, self.provider_intent_id, self.provider_payment_id = [str(uuid4()) for _ in range(3)]
        self.line_uuid = second_uuid
        self.base_minor, self.gross_minor, self.tip_minor = 6000, 6200, 200
        second = self.method.revolut_start_payment(self.session.id, self.order.uuid, second_uuid,
            60, self.order.currency_id.id, False, False, prepared["authorization_id"],
            prepared["cart_version"], prepared["tender_revision"])
        self.operation_id = second["operation_id"]
        self.assertEqual(self.poll_payment()["state"], "verified")
        self.env.invalidate_all()
        tips = self.order.lines.filtered(lambda line: line.product_id == self.tip_product)
        self.assertEqual(len(tips), 1)
        self.assertEqual(tips.price_subtotal_incl, 5)
        self.assertFalse(self.order.lines.filtered(lambda line: line.product_id == replacement))
        self.assertEqual(self.order.amount_total, 105)
        self.assertEqual(sum(self.order.payment_ids.mapped("amount")), 105)
        self.assertEqual(self.financial_post_count(), 4)

    def test_changed_tip_tax_policy_keeps_capture_reserved_until_restored(self):
        tax = self.env["account.tax"].create({"name": "Frozen terminal tip tax", "amount": 20,
            "amount_type": "percent", "company_id": self.order.company_id.id})
        self.tip_product.taxes_id = tax
        self.env.ref("product.decimal_price").digits = 3
        self.env.flush_all()
        self.env.registry.clear_cache()
        self.start_payment()
        self.assertTrue(self.poll_payment()["awaiting_tip_details"])
        tax.amount = 25
        self.env.flush_all()
        self.env.invalidate_all()
        self.report_status = "completed"
        unresolved = self.poll_payment()
        self.assertEqual(unresolved["state"], "unresolved")
        self.assertFalse(unresolved["retry_safe"])
        self.env.invalidate_all()
        self.assertFalse(self.order.payment_ids)
        self.assertFalse(self.order.lines.filtered(lambda line: line.product_id == self.tip_product))
        tax.amount = 20
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(self.poll_payment()["state"], "verified")
        self.assertEqual(self.financial_post_count(), 2)

    def test_changed_tip_tax_policy_blocks_later_base_dispatch_without_provider_post(self):
        tax = self.env["account.tax"].create({"name": "Later allocation frozen tip tax", "amount": 20,
            "amount_type": "percent", "company_id": self.order.company_id.id})
        self.tip_product.taxes_id = tax
        self.env.ref("product.decimal_price").digits = 3
        self.env.flush_all()
        self.env.registry.clear_cache()
        second_uuid = str(uuid4())
        plan = [{"uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 40},
                {"uuid": second_uuid, "payment_method_id": self.method.id, "amount": 60}]
        prepared = self.env["pos.order"].revolut_prepare_payment(self.order.id, self.order.uuid, 0, plan)
        self.base_minor, self.gross_minor, self.tip_minor = 4000, 4300, 300
        self.report_status = "completed"
        first = self.method.revolut_start_payment(self.session.id, self.order.uuid, self.line_uuid,
            40, self.order.currency_id.id, False, False, prepared["authorization_id"],
            prepared["cart_version"], prepared["tender_revision"])
        self.operation_id = first["operation_id"]
        self.assertEqual(self.poll_payment()["state"], "verified")
        self.env.ref("product.decimal_price").digits = 2
        self.env.flush_all()
        self.env.registry.clear_cache()
        self.env.invalidate_all()
        prior_calls = self.request.call_count
        with self.assertRaisesRegex(UserError, "original terminal tip tax or precision policy changed"):
            self.method.revolut_start_payment(self.session.id, self.order.uuid, second_uuid,
                60, self.order.currency_id.id, False, False, prepared["authorization_id"],
                prepared["cart_version"], prepared["tender_revision"])
        self.assertEqual(self.request.call_count, prior_calls)
        self.assertEqual(self.financial_post_count(), 2)
        self.assertEqual(self.env["pos.revolut.payment.operation"].sudo().search_count([
            ("order_uuid", "=", self.order.uuid)]), 1)

    def test_reduced_tip_price_precision_keeps_capture_reserved_until_restored(self):
        precision = self.env.ref("product.decimal_price")
        original = precision.digits
        self.start_payment()
        self.assertTrue(self.poll_payment()["awaiting_tip_details"])
        precision.digits = original - 1
        self.env.flush_all()
        self.env.registry.clear_cache()
        self.report_status = "completed"
        unresolved = self.poll_payment()
        self.assertEqual(unresolved["state"], "unresolved")
        self.assertFalse(unresolved["retry_safe"])
        self.env.invalidate_all()
        self.assertFalse(self.order.payment_ids)
        self.assertFalse(self.order.lines.filtered(lambda line: line.product_id == self.tip_product))
        precision.digits = original
        self.env.flush_all()
        self.env.registry.clear_cache()
        self.assertEqual(self.poll_payment()["state"], "verified")
        self.assertEqual(self.financial_post_count(), 2)

    def test_equal_gross_and_base_still_requires_explicit_report_zero(self):
        self.gross_minor, self.tip_minor = 10000, 0
        self.start_payment()
        self.assertEqual(self.poll_payment()["state"], "pending")
        self.report_status = "completed"
        verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(verified["gross_amount_minor"], 10000)
        self.assertEqual(verified["terminal_tip_minor"], 0)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.amount_total, 100)
        self.assertFalse(self.order.lines.filtered(lambda line: line.product_id == self.tip_product))
        self.assertEqual(self.financial_post_count(), 2)

    def test_invalid_report_never_verifies_or_releases_captured_reservation(self):
        self.start_payment()
        self.report_status = "completed"
        cases = [
            {"tip_amount": ""}, {"tip_amount": "-3.00"}, {"tip_amount": "3e0"},
            {"tip_amount": "3.001"}, {"amount": "10300"}, {"currency": "EUR"},
            {"order_id": str(uuid4())}, {"location_id": str(uuid4())},
            {"type": "REFUND"}, {"state": "PROCESSING"},
            {"surcharge_amount": "0.01"}, {"refunded_amount": "0.01"},
            {"created_date": "2026-10-01T11:00:00Z"},
            {"captured_date": "2026-10-01T09:59:00Z"},
            {"amount": "0" * 25},
        ]
        for wrong in cases:
            with self.subTest(wrong=wrong):
                self.csv_content = self.report_csv([self.report_row(**wrong)])
                result = self.poll_payment()
                self.assertEqual(result["state"], "unresolved")
                self.assertEqual(result["captured_amount_minor"], 10300)
                self.assertTrue(result["awaiting_tip_details"])
                self.assertFalse(result["retry_safe"])
                self.assertEqual(result["gross_amount_minor"], 0)
                self.order.invalidate_recordset()
                self.assertEqual(self.order.amount_total, 100)
                self.assertEqual(self.financial_post_count(), 2)

    def test_duplicate_or_second_successful_report_rows_stay_unresolved(self):
        self.start_payment()
        self.report_status = "completed"
        for rows in ([self.report_row(), self.report_row()],
                     [self.report_row(), self.report_row(payment_id=str(uuid4()), amount="3.00")]):
            with self.subTest(rows=rows):
                self.csv_content = self.report_csv(rows)
                result = self.poll_payment()
                self.assertEqual(result["state"], "unresolved")
                self.assertFalse(result["retry_safe"])
                self.assertEqual(self.financial_post_count(), 2)

    def test_unexpected_successful_or_unfinished_order_payment_blocks_report(self):
        self.start_payment()
        self.report_status = "completed"
        for state in ("captured", "pending", "authorised"):
            with self.subTest(state=state):
                self.order_payments = [
                    {"id": self.provider_payment_id, "state": "captured", "amount": 10300},
                    {"id": str(uuid4()), "state": state, "amount": 300},
                ]
                self.assertEqual(self.poll_payment()["state"], "unresolved")
                self.assertEqual(self.financial_post_count(), 2)

    def test_expired_report_can_regenerate_without_replaying_payment(self):
        self.start_payment()
        self.assertEqual(self.poll_payment()["state"], "pending")
        original_run = self.active_run_id
        self.report_status = "expired"
        expired = self.poll_payment()
        self.assertTrue(expired["awaiting_tip_details"])
        self.assertFalse(expired["retry_safe"])
        self.report_status = "completed"
        verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.assertNotEqual(self.active_run_id, original_run)
        self.assertEqual(self.report_post_count, 2)
        self.assertEqual(self.financial_post_count(), 2)
        operation = self.env["pos.revolut.payment.operation"].sudo().browse(self.operation_id)
        operation.invalidate_recordset()
        self.assertEqual(operation.report_run_history[0]["report_run_id"], original_run)
        self.assertEqual(operation.revolut_payment_id, self.provider_payment_id)
        self.assertEqual(operation.amount_minor, 10000)

    def test_late_report_row_recovers_through_public_poll(self):
        self.start_payment()
        self.report_status = "completed"
        self.csv_content = self.report_csv([])
        waiting = self.poll_payment()
        self.assertTrue(waiting["awaiting_tip_details"])
        self.assertFalse(waiting["retry_safe"])
        self.csv_content = None
        verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(self.report_post_count, 2)
        self.assertEqual(self.financial_post_count(), 2)

    def test_report_download_and_rows_are_bounded(self):
        self.start_payment()
        self.report_status = "completed"
        for content in (b"x" * 262145,
                        self.report_csv([self.report_row()] * 1001),
                        self.report_csv([self.report_row(location_id="x" * 129)])):
            with self.subTest(size=len(content)):
                self.csv_content = content
                result = self.poll_payment()
                self.assertEqual(result["state"], "unresolved")
                self.assertFalse(result["retry_safe"])
                self.assertEqual(self.financial_post_count(), 2)

    def test_report_uses_bounded_columns_time_and_authenticated_fixed_paths(self):
        self.start_payment()
        self.poll_payment()
        report_call = next(call for call in self.request.call_args_list
                           if call.args[0] == "POST" and urlsplit(call.args[1]).path == "/api/report-runs")
        body = report_call.kwargs["json"]
        self.assertEqual(body["type"], "payments_report")
        self.assertEqual(body["filter"], {"from": "2026-10-01T09:59:00Z", "to": "2026-10-01T10:01:00Z"})
        self.assertEqual(set(body["options"]["columns"]), set(self.columns))
        self.assertFalse(report_call.kwargs["allow_redirects"])
        self.assertEqual(report_call.kwargs["headers"]["Authorization"], "Bearer test-only")
        self.report_status = "completed"
        self.poll_payment()
        file_call = next(call for call in self.request.call_args_list if urlsplit(call.args[1]).path.endswith("/file"))
        self.assertEqual(urlsplit(file_call.args[1]).path, f"/api/report-runs/{self.active_run_id}/file")
        self.assertFalse(file_call.kwargs["allow_redirects"])

    def test_lost_report_creation_response_never_replays_financial_dispatch(self):
        self.start_payment()
        provider = self.provider_response
        failed = [False]

        def lose_report_response(method, url, **kwargs):
            if method == "POST" and urlsplit(url).path == "/api/report-runs" and not failed[0]:
                failed[0] = True
                raise requests.Timeout("simulated report response loss")
            return provider(method, url, **kwargs)

        self.request.side_effect = lose_report_response
        waiting = self.poll_payment()
        self.assertEqual(waiting["state"], "unresolved")
        self.assertTrue(waiting["awaiting_tip_details"])
        self.assertFalse(waiting["retry_safe"])
        self.report_status = "completed"
        later = fields.Datetime.now() + timedelta(seconds=61)
        with patch("odoo.fields.Datetime.now", return_value=later):
            verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(self.financial_post_count(), 2)
        self.assertEqual(verified["payment_id"], self.provider_payment_id)

    def test_scheduled_reconciliation_finishes_tip_without_browser(self):
        self.start_payment()
        self.poll_payment()
        self.report_status = "completed"
        later = fields.Datetime.now() + timedelta(seconds=31)
        with patch("odoo.fields.Datetime.now", return_value=later):
            self.env.ref("pos_revolut.ir_cron_reconcile_payments").method_direct_trigger()
        verified = self.method.revolut_find_payment(self.order.uuid, self.line_uuid)
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(verified["gross_amount_minor"], 10300)
        self.assertEqual(verified["terminal_tip_minor"], 300)
        self.assertEqual(self.financial_post_count(), 2)

    def test_taxed_tip_projection_preserves_exact_collected_gross(self):
        tax = self.env["account.tax"].create({
            "name": "Reported terminal tip 20 percent", "amount": 20,
            "amount_type": "percent", "company_id": self.order.company_id.id,
        })
        self.tip_product.taxes_id = tax
        self.env.ref("product.decimal_price").digits = 3
        self.env.flush_all()
        self.env.registry.clear_cache()
        self.assertEqual(self.env["decimal.precision"].precision_get("Product Price"), 3)
        self.order.company_id.tax_calculation_rounding_method = "round_globally"
        self.gross_minor, self.tip_minor = 10003, 3
        self.report_status = "completed"
        self.start_payment()
        result = self.poll_payment()
        self.assertEqual(result["state"], "verified")
        self.assertEqual(result["gross_amount_minor"], 10003)
        self.assertEqual(result["terminal_tip_minor"], 3)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.amount_total, 100.03)
        tip = self.order.lines.filtered(lambda line: line.product_id == self.tip_product)
        self.assertEqual(tip.tax_ids, tax)
        self.assertEqual(self.order.payment_ids.amount, 100.03)
        self.assertEqual(self.financial_post_count(), 2)

    def test_global_rounded_base_adds_tip_without_rounding_it_again(self):
        self.product.list_price = 100.02
        self.pos_config_usd.write({
            "cash_rounding": True, "only_round_cash_method": False,
            "rounding_method": self.account_cash_rounding_half.id,
        })
        self.order.write({
            "amount_total": 100.02,
            "lines": [Command.update(self.order.lines.id, {"price_unit": 100.02,
                "price_subtotal": 100.02, "price_subtotal_incl": 100.02})],
        })
        self.gross_minor, self.tip_minor = 10003, 3
        self.report_status = "completed"
        self.start_payment()
        result = self.poll_payment()
        self.assertEqual(result["state"], "verified")
        self.order.invalidate_recordset()
        self.assertEqual(self.order.amount_total, 100.03)
        self.assertEqual(self.order.payment_ids.amount, 100.03)
        # Polling commits in an owned cursor. Invalidate this fixture's cache
        # before exercising the public checkout with the persisted evidence.
        self.env.invalidate_all()
        self.env["pos.order"].sync_from_ui([{
            "uuid": self.order.uuid, "session_id": self.session.id, "state": "paid",
            "date_order": fields.Datetime.to_string(fields.Datetime.now()), "sequence_number": 1,
            "name": f"Order {self.order.uuid}", "amount_total": 100.03, "amount_paid": 100.03,
            "amount_tax": 0, "amount_return": 0, "to_invoice": False,
            "lines": [], "payment_ids": [],
        }])
        self.env.invalidate_all()
        self.assertEqual(self.order.state, "paid")
        self.assertEqual(self.order.amount_total, 100.03)
        self.assertEqual(self.order.amount_paid, 100.03)
        self.assertEqual(self.order._get_rounded_amount(self.order.amount_total), 100.03)
        self.assertEqual(self.financial_post_count(), 2)

    def _check_currency_tip(self, currency_xmlid, exponent, gross_minor, tip_minor, decimal_gross, decimal_tip):
        currency = self.env.ref(currency_xmlid)
        currency.active = True
        self.env["res.currency.rate"].create({"currency_id": currency.id,
            "company_id": self.order.company_id.id, "name": fields.Date.today(), "rate": 1})
        self.method.journal_id.currency_id = currency
        self.pos_config_usd.journal_id.currency_id = currency
        self.tip_pricelist.currency_id = currency
        self.env.flush_all()
        self.env.invalidate_all()
        self.order.invalidate_recordset()
        self.assertEqual(self.order.currency_id, currency)
        self.assertEqual(currency.decimal_places, exponent)
        self.base_minor = 100 * (10 ** exponent)
        self.gross_minor, self.tip_minor = gross_minor, tip_minor
        self.csv_content = self.report_csv([self.report_row(
            amount=decimal_gross, tip_amount=decimal_tip, refunded_amount="0")])
        self.report_status = "completed"
        plan = [{"uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 100}]
        prepared = self.env["pos.order"].revolut_prepare_payment(self.order.id, self.order.uuid, 0, plan)
        if prepared["status"] == "review_required":
            prepared = self.env["pos.order"].revolut_prepare_payment(
                self.order.id, self.order.uuid, prepared["cart_version"], plan)
        self.assertEqual(prepared["status"], "prepared", prepared)
        started = self.method.revolut_start_payment(self.session.id, self.order.uuid,
            self.line_uuid, 100, currency.id, False, False, prepared["authorization_id"],
            prepared["cart_version"], prepared["tender_revision"])
        self.assertIn("operation_id", started, started)
        self.operation_id = started["operation_id"]
        verified = self.poll_payment()
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(verified["gross_amount_minor"], gross_minor)
        self.assertEqual(verified["terminal_tip_minor"], tip_minor)
        self.order.invalidate_recordset()
        self.assertEqual(self.order.amount_total, gross_minor / (10 ** exponent))
        self.assertEqual(self.order.payment_ids.amount, gross_minor / (10 ** exponent))
        self.assertEqual(self.financial_post_count(), 2)

    def test_zero_decimal_currency_report_projects_exact_minor_tip(self):
        self._check_currency_tip("base.JPY", 0, 103, 3, "103", "3")

    def test_three_decimal_currency_report_projects_exact_minor_tip(self):
        self.env.ref("product.decimal_price").digits = 3
        self.env.flush_all()
        self.env.registry.clear_cache()
        self._check_currency_tip("base.TND", 3, 100003, 3, "100.003", "0.003")

    def test_conflicting_fresh_payment_cannot_be_overridden_by_old_capture(self):
        self.start_payment()
        self.assertTrue(self.poll_payment()["awaiting_tip_details"])
        self.report_status = "completed"
        original_provider = self.provider_response

        def contradictory_payment(method, url, **kwargs):
            if urlsplit(url).path == f"/api/payments/{self.provider_payment_id}":
                return self.response({"id": self.provider_payment_id, "order_id": self.provider_order_id,
                    "amount": 10300, "currency": self.order.currency_id.name,
                    "state": "failed", "created_at": self.created_at})
            return original_provider(method, url, **kwargs)

        self.request.side_effect = contradictory_payment
        result = self.poll_payment()
        self.assertEqual(result["state"], "unresolved")
        self.assertFalse(result["retry_safe"])
        self.assertTrue(result["awaiting_tip_details"])
        self.assertEqual(result["captured_amount_minor"], 10300)
        self.assertEqual(result["gross_amount_minor"], 0)
        self.assertEqual(self.financial_post_count(), 2)

    def test_invented_synchronous_tip_field_is_never_report_evidence(self):
        self.start_payment()
        self.report_status = "completed"
        self.csv_content = self.report_csv([self.report_row(tip_amount="")])
        original_provider = self.provider_response

        def invented_tip(method, url, **kwargs):
            response = original_provider(method, url, **kwargs)
            if urlsplit(url).path == f"/api/payments/{self.provider_payment_id}":
                response.json.return_value["tip_amount"] = 300
            return response

        self.request.side_effect = invented_tip
        result = self.poll_payment()
        self.assertEqual(result["state"], "unresolved")
        self.assertFalse(result["retry_safe"])
        self.assertEqual(result["gross_amount_minor"], 0)

    def test_expired_download_recreates_report_without_new_charge(self):
        self.start_payment()
        self.report_status = "completed"
        original_provider = self.provider_response
        unavailable = [True]

        def expired_file(method, url, **kwargs):
            if urlsplit(url).path.endswith("/file") and unavailable[0]:
                unavailable[0] = False
                response = self.response({}, status=404)
                response.raise_for_status.side_effect = requests.HTTPError("expired report", response=response)
                return response
            return original_provider(method, url, **kwargs)

        self.request.side_effect = expired_file
        waiting = self.poll_payment()
        self.assertTrue(waiting["awaiting_tip_details"])
        self.assertFalse(waiting["retry_safe"])
        original_run = self.active_run_id
        self.assertEqual(self.poll_payment()["state"], "verified")
        self.assertNotEqual(self.active_run_id, original_run)
        self.assertEqual(self.financial_post_count(), 2)
        self.assertEqual(self.report_post_count, 2)

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .test_revolut_payment import TestRevolutOrderSettlement
from .test_revolut_receipt import TestRevolutReceipt
from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestRevolutReceiptUi(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    ORDER_ID = TestRevolutVerifiedCheckout.ORDER_ID
    INTENT_ID = TestRevolutVerifiedCheckout.INTENT_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout
    _response = TestRevolutVerifiedCheckout._response
    def _pos_fixture(self, helper, *args, **kwargs):
        http_session = self.session
        self.session = self.receipt_session
        try:
            return helper(self, *args, **kwargs)
        finally:
            self.session = http_session

    def _operation(self, *args, **kwargs):
        return self._pos_fixture(TestRevolutOrderSettlement._operation, *args, **kwargs)

    def _order_payload(self, *args, **kwargs):
        return self._pos_fixture(TestRevolutOrderSettlement._order_payload, *args, **kwargs)

    def _refund(self, *args, **kwargs):
        return self._pos_fixture(TestRevolutReceipt._refund, *args, **kwargs)

    def _receipt_sale(self, split=False):
        self.revolut_method = self._configure_revolut_checkout()
        self.pos_config_usd = self.main_pos_config
        self.company = self.main_pos_config.company_id
        self.product = self.desk_pad.product_variant_id
        self.receipt_session = self.main_pos_config.current_session_id
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        payload["pos_reference"] = "Historical Revolut receipt sale"
        payment = payload["payment_ids"][0][2]
        if split:
            payment["amount"] = 4.34
            cash = self.main_pos_config.payment_method_ids.filtered("is_cash_count")[:1]
            payload["payment_ids"].append(Command.create({
                "amount": 8.0, "name": fields.Datetime.now(),
                "payment_method_id": cash.id, "uuid": str(uuid4()),
            }))
        historical_date = self.event_time = fields.Datetime.now() - timedelta(days=8)
        payload["date_order"] = fields.Datetime.to_string(historical_date)
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
        operation = self._operation(
            payload["uuid"], payment["uuid"], amount=payment["amount"],
            amount_minor=434 if split else 1234, financial_snapshot=snapshot,
            provider_state="captured", verified_at=historical_date,
        )
        payment["transaction_id"] = operation.revolut_payment_id
        self.env["pos.order"].sync_from_ui([payload])
        operation.invalidate_recordset()
        self.assertEqual(operation.pos_order_id.pos_reference, "Historical Revolut receipt sale")
        return operation

    def _sale_refunds(self, full=False):
        self.source = self._receipt_sale()
        self.original = self.source.pos_order_id
        refunds = [self._refund()] if full else [self._refund(6.17), self._refund(6.17)]
        self.receipt_session.post_closing_cash_details(0)
        self.receipt_session.close_session_from_ui()
        self.assertEqual(self.receipt_session.state, "closed")
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        return refunds

    def test_cashier_downloads_week_old_split_payment_after_closed_session_and_fresh_load(self):
        operation = self._receipt_sale(split=True)
        self.env.cr.execute(
            "UPDATE pos_revolut_payment_operation SET receipt_merchant_snapshot = NULL WHERE id = %s",
            [operation.id],
        )
        operation.invalidate_recordset()
        original = operation.pos_order_id
        self.receipt_session.post_closing_cash_details(8.0)
        self.receipt_session.close_session_from_ui()
        self.assertEqual(self.receipt_session.state, "closed")
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        before = (operation.state, original.state, operation.pos_payment_id.amount)
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt downloads must not contact Merchant API"),
        ) as merchant:
            self.start_pos_tour("pos_revolut_historical_receipt_download")
        self.env.invalidate_all()
        self.assertEqual((operation.state, original.state, operation.pos_payment_id.amount), before)
        self.assertEqual(self.receipt_session.state, "closed")
        self.assertEqual(original.amount_total, 12.34)
        self.assertEqual(operation.amount_minor, 434)
        merchant.assert_not_called()

    def test_cashier_history_does_not_offer_a_nonfinal_payment_receipt(self):
        operation = self._receipt_sale()
        # Historical browser evidence must not override the server outcome.
        operation.write({"state": "pending"})
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt discovery must not contact Merchant API"),
        ) as merchant:
            self.start_pos_tour("pos_revolut_nonfinal_receipt_unavailable")
        self.env.invalidate_all()
        self.assertEqual(operation.state, "pending")
        merchant.assert_not_called()

    def test_current_receipt_download_retries_report_failure_without_another_charge(self):
        method = self._configure_revolut_checkout()
        calls = []

        def request(http_method, url, **kwargs):
            calls.append((http_method, url))
            if http_method == "GET" and url.endswith("/api/terminals"):
                return self._response({"terminals": [{
                    "id": self.TERMINAL_ID, "online": True,
                    "operation_mode": "pos", "location_id": self.LOCATION_ID,
                }]})
            if http_method == "POST" and url.endswith("/api/orders"):
                return self._response({"id": self.ORDER_ID})
            if http_method == "POST" and url.endswith("/payment-intents"):
                return self._response({"id": self.INTENT_ID, "state": "pending"})
            if http_method == "GET" and "/api/payment-intents/" in url:
                return self._response({
                    "id": self.INTENT_ID, "order_id": self.ORDER_ID,
                    "state": "completed", "payment_id": self.PAYMENT_ID,
                })
            if http_method == "GET" and "/api/payments/" in url:
                return self._response({
                    "id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                    "state": "captured", "amount": 1234,
                    "currency": self.main_pos_config.currency_id.name,
                })
            raise AssertionError(f"Unexpected Merchant request: {http_method} {url}")

        report_model = type(self.env["ir.actions.report"])
        original_render = report_model._render_qweb_pdf
        calls_at_download = []

        def render(report, report_ref, *args, **kwargs):
            if report_ref == "pos_revolut.action_report_revolut_payment_receipt":
                calls_at_download.append(len(calls))
                if len(calls_at_download) == 1:
                    raise RuntimeError("Test-only receipt renderer failure")
            return original_render(report, report_ref, *args, **kwargs)

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ), patch.object(report_model, "_render_qweb_pdf", render):
            self.start_pos_tour("pos_revolut_current_receipt_retry")
        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", method.id),
        ])
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(len(calls_at_download), 3)
        self.assertEqual(len(set(calls_at_download)), 1)
        self.assertEqual(len(calls), calls_at_download[0])
        self.assertEqual(sum(call[0] == "POST" for call in calls), 2)

    def test_cashier_selects_each_partial_refund_and_original_payment_after_reload(self):
        refunds = self._sale_refunds()
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt downloads must not contact Merchant API"),
        ) as merchant:
            self.start_pos_tour("pos_revolut_partial_refund_receipts")
        self.env.invalidate_all()
        self.assertEqual([refund.state for refund in refunds], ["verified", "verified"])
        self.assertEqual([refund.amount for refund in refunds], [6.17, 6.17])
        self.assertEqual(self.source.state, "verified")
        self.assertEqual(self.receipt_session.state, "closed")
        merchant.assert_not_called()

    def test_cashier_downloads_full_refund_and_keeps_original_payment_receipt(self):
        refunds = self._sale_refunds(full=True)
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt downloads must not contact Merchant API"),
        ) as merchant:
            self.start_pos_tour("pos_revolut_full_refund_receipts")
        self.env.invalidate_all()
        self.assertEqual(refunds[0].state, "verified")
        self.assertEqual(refunds[0].amount, 12.34)
        self.assertEqual(self.source.state, "verified")
        self.assertEqual(self.receipt_session.state, "closed")
        merchant.assert_not_called()

    def test_admin_order_receipt_links_download_payment_and_partial_refunds(self):
        self._sale_refunds()
        action = self.env.ref("point_of_sale.action_pos_pos_form")
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt downloads must not contact Merchant API"),
        ) as merchant:
            self.start_tour(
                f"/odoo/action-{action.id}/{self.original.id}?debug=tests",
                "pos_revolut_admin_receipt_links", login="pos_admin",
            )
        merchant.assert_not_called()

    def test_admin_order_receipt_links_download_full_refund_and_original_payment(self):
        self._sale_refunds(full=True)
        action = self.env.ref("point_of_sale.action_pos_pos_form")
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt downloads must not contact Merchant API"),
        ) as merchant:
            self.start_tour(
                f"/odoo/action-{action.id}/{self.original.id}?debug=tests",
                "pos_revolut_admin_full_refund_receipt_links", login="pos_admin",
            )
        merchant.assert_not_called()

    def test_receipt_download_and_standard_report_routes_enforce_access_and_outcomes(self):
        operation = self._receipt_sale()
        pending = self._operation(
            str(uuid4()), str(uuid4()), state="pending", pos_order_id=operation.pos_order_id.id,
        )
        urls = (
            f"/pos_revolut/receipt/payment/{operation.id}",
            f"/report/pdf/pos_revolut.report_revolut_payment_receipt/{operation.id}"
            '?context={"force_report_rendering":true}',
        )
        outsider_company = self.env["res.company"].create({"name": "Receipt outsider"})
        non_pos = new_test_user(
            self.env, login="receipt_no_pos", password="receipt_no_pos", groups="base.group_user",
        )
        cross_company = new_test_user(
            self.env, login="receipt_other_company", password="receipt_other_company",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=outsider_company.id, company_ids=[Command.set([outsider_company.id])],
        )
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Receipt access must not contact Merchant API"),
        ) as merchant:
            for login in (None, non_pos.login, cross_company.login):
                self.authenticate(login, login)
                for url in urls:
                    result = self.url_open(url, allow_redirects=False)
                    self.assertFalse(result.content.startswith(b"%PDF-"), (login, url))
                    self.assertNotEqual(result.headers.get("Content-Type"), "application/pdf")
            self.authenticate("pos_user", "pos_user")
            for url in (
                f"/pos_revolut/receipt/payment/{pending.id}",
                f"/report/pdf/pos_revolut.report_revolut_payment_receipt/{pending.id}",
                "/pos_revolut/receipt/payment/2147483647",
                "/report/pdf/pos_revolut.report_revolut_payment_receipt/2147483647",
                f"/pos_revolut/receipt/refund/{operation.id}",
            ):
                result = self.url_open(url)
                self.assertFalse(result.content.startswith(b"%PDF-"), url)
            for url in urls:
                result = self.url_open(url)
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.content.startswith(b"%PDF-"), url)
        self.env.invalidate_all()
        self.assertEqual(operation.state, "verified")
        self.assertEqual(pending.state, "pending")
        merchant.assert_not_called()

from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import new_test_user, tagged
from odoo.tools.pdf import PdfFileReader

from .test_revolut_payment import TestRevolutOrderSettlement
from .test_revolut_refund import TestRevolutRefund


@tagged("post_install", "-at_install")
class TestRevolutReceipt(CommonPosTest):
    LOCATION_ID = TestRevolutOrderSettlement.LOCATION_ID
    TERMINAL_ID = TestRevolutOrderSettlement.TERMINAL_ID
    PAYMENT_ID = TestRevolutOrderSettlement.PAYMENT_ID
    _operation = TestRevolutOrderSettlement._operation
    _order_payload = TestRevolutOrderSettlement._order_payload
    _split_original = TestRevolutRefund._split_original

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Revolut receipt test", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Receipt product", "available_in_pos": True, "list_price": 12.34,
            "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("A receipt must not call the Merchant API"),
        ))
        self.event_time = fields.Datetime.now() - timedelta(days=8)
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        payload["date_order"] = fields.Datetime.to_string(self.event_time)
        self.source = self._operation(
            payload["uuid"], payload["payment_ids"][0][2]["uuid"],
            provider_state="captured", verified_at=self.event_time,
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        )
        payload["payment_ids"][0][2]["transaction_id"] = self.source.revolut_payment_id
        self.env["pos.order"].sync_from_ui([payload])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id

    def _pdf(self, kind, operation, user=None, companies=None):
        report = self.env["ir.actions.report"].with_context(force_report_rendering=True)
        if user:
            report = report.with_user(user)
        if companies:
            report = report.with_context(allowed_company_ids=companies)
        pdf, extension = report._render_qweb_pdf(
            f"pos_revolut.action_report_revolut_{kind}_receipt", [operation.id],
        )
        self.assertEqual(extension, "pdf")
        self.assertTrue(pdf.startswith(b"%PDF-"))
        reader = PdfFileReader(BytesIO(pdf))
        return " ".join(" ".join(page.extractText() for page in reader.pages).split())

    def _refund(self, amount=12.34, state="verified"):
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        payload.update(amount_total=-amount, amount_paid=-amount)
        line = payload["lines"][0][2]
        line.update(qty=-amount / 12.34, price_subtotal=-amount,
                    price_subtotal_incl=-amount, refunded_orderline_id=self.original.lines.id)
        reference = str(uuid4())
        payload["payment_ids"][0][2].update(amount=-amount, transaction_id=reference)
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
        snapshot["lines"][0]["refunded_orderline_id"] = self.original.lines.id
        refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": self.source.id, "pos_session_id": self.session.id,
            "order_uuid": payload["uuid"], "payment_line_uuid": payload["payment_ids"][0][2]["uuid"],
            "amount": amount, "amount_minor": round(amount * 100),
            "return_total_minor": round(amount * 100), "currency_id": self.session.currency_id.id,
            "financial_snapshot": snapshot, "state": state, "revolut_order_id": reference,
            "provider_state": "completed" if state == "verified" else "pending",
            "verified_at": self.event_time + timedelta(days=1) if state == "verified" else False,
        })
        if state == "verified":
            self.env["pos.order"].sync_from_ui([payload])
            refund.invalidate_recordset()
        return refund

    def _actor(self, groups="point_of_sale.group_pos_user", companies=None):
        companies = companies or self.company
        return new_test_user(
            self.env, login=f"receipt_{uuid4()}", groups=f"base.group_user,{groups}",
            company_id=companies[0].id, company_ids=[Command.set(companies.ids)],
        )

    def _financial_evidence(self):
        models = ("pos.revolut.payment.operation", "pos.revolut.refund.operation",
                  "pos.revolut.payment.dispatch", "pos.revolut.reconciliation.audit", "pos.payment", "pos.order",
                  "account.move", "ir.attachment")
        return {
            "counts": {
                name: self.env[name].sudo().search_count(
                    [("mimetype", "=", "application/pdf")] if name == "ir.attachment" else []
                ) for name in models
            },
            "payment": self.source.read(["state", "verified_at", "revolut_payment_id", "write_date"]),
            "order": self.original.read(["state", "account_move", "write_date"]),
            "session": self.session.read(["state", "write_date"]),
        }

    def test_week_old_closed_session_payment_has_actual_receipt_pdf(self):
        self.session.write({"state": "closed"})
        self.assertFalse(self.original.partner_id)
        self.assertFalse(self.original.account_move)
        options = self.original.revolut_receipt_options()
        self.assertEqual([(item["kind"], item["operation_id"]) for item in options],
                         [("payment", self.source.id)])
        self.assertEqual(options[0]["url"], f"/pos_revolut/receipt/payment/{self.source.id}")
        text = self._pdf("payment", self.source)
        for value in ("Odoo-generated", "payment receipt", self.company.name,
                      self.original.name, "12.34", self.session.currency_id.name,
                      self.source.revolut_order_id, self.source.revolut_payment_id,
                      "Verified in Odoo at", self.event_time.strftime("%Y-%m-%d")):
            self.assertIn(value, text)
        self.assertEqual(self.session.state, "closed")
        self.assertEqual(self.original.state, "paid")
        self.request.assert_not_called()

    def test_legacy_optional_metadata_uses_truthful_time_and_current_merchant(self):
        # Simulate an upgraded row created before merchant display snapshots existed.
        self.env.cr.execute(
            "UPDATE pos_revolut_payment_operation SET receipt_merchant_snapshot = NULL WHERE id = %s",
            [self.source.id],
        )
        self.source.invalidate_recordset()
        self.company.write({"name": "Current merchant after upgrade"})
        text = self._pdf("payment", self.source)
        for expected in ("Current merchant identity", "Current merchant after upgrade", "Verified in Odoo at"):
            self.assertIn(expected, text)
        self.assertIn("local Odoo timestamp", text)
        for absent in ("Visa", "Mastercard", "Authorization code",
                       "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST"):
            self.assertNotIn(absent, text)
        self.assertFalse(self.source.receipt_merchant_snapshot)
        self.request.assert_not_called()

    def test_future_receipt_preserves_merchant_at_verification(self):
        original_name = self.company.name
        self.assertTrue(self.source.receipt_merchant_snapshot)
        self.company.write({"name": "Different merchant name today"})
        text = self._pdf("payment", self.source)
        self.assertIn(original_name, text)
        self.assertNotIn("Different merchant name today", text)
        self.assertNotIn("Current merchant identity", text)
        with self.assertRaises(ValidationError):
            self.source.write({"receipt_merchant_snapshot": {"name": "Forged merchant"}})
        with self.assertRaises(ValidationError):
            self.source.write({"verified_at": fields.Datetime.now()})
        self.request.assert_not_called()

    def test_legacy_missing_verification_time_does_not_invent_event_timestamp(self):
        self.env.cr.execute(
            "UPDATE pos_revolut_payment_operation SET verified_at = NULL WHERE id = %s", [self.source.id],
        )
        self.source.invalidate_recordset()
        text = self._pdf("payment", self.source)
        self.assertIn("Verification time was not retained", text)
        self.assertIn("PDF generated at", text)
        self.assertNotIn("Verified in Odoo at", text)
        self.assertFalse(self.source.verified_at)
        self.request.assert_not_called()

    def test_verified_full_refund_has_distinct_pdf_and_preserves_original(self):
        refund = self._refund()
        self.session.write({"state": "closed"})
        text = self._pdf("refund", refund)
        for value in ("Odoo-generated", "refund receipt", "12.34", refund.revolut_order_id,
                      self.source.revolut_order_id, self.source.revolut_payment_id, self.original.name,
                      (self.event_time + timedelta(days=1)).strftime("%Y-%m-%d")):
            self.assertIn(value, text)
        self.assertIn(self.source.revolut_payment_id, self._pdf("payment", self.source))
        expected = {("payment", self.source.id), ("refund", refund.id)}
        self.assertEqual({(item["kind"], item["operation_id"]) for item in self.original.revolut_receipt_options()}, expected)
        self.assertEqual([(item["kind"], item["operation_id"]) for item in refund.pos_order_id.revolut_receipt_options()],
                         [("refund", refund.id)])
        self.request.assert_not_called()

    def test_multiple_partial_refunds_are_individually_identifiable(self):
        first, second = self._refund(6.17), self._refund(6.17)
        for selected, other in ((first, second), (second, first)):
            text = self._pdf("refund", selected)
            self.assertIn("6.17", text)
            self.assertIn(selected.revolut_order_id, text)
            self.assertNotIn(other.revolut_order_id, text)
            self.assertIn(self.source.revolut_payment_id, text)
        self.assertIn("12.34", self._pdf("payment", self.source))
        self.assertEqual({item["operation_id"] for item in self.original.revolut_receipt_options()},
                         {self.source.id, first.id, second.id})
        self.request.assert_not_called()

    def test_split_tender_receipt_contains_only_selected_verified_amount(self):
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        self._split_original()
        self.source.write({"provider_state": "captured"})
        text = self._pdf("payment", self.source)
        self.assertIn("6.17", text)
        self.assertNotIn("12.34", text)
        self.assertIn("does not certify that the entire Odoo sale is fully paid", text)
        self.assertEqual(len(self.original.revolut_receipt_options()), 1)
        self.request.assert_not_called()

    def test_every_nonfinal_payment_outcome_denies_direct_report(self):
        for state in ("created", "dispatching_order", "order_created", "dispatching_intent",
                      "pending", "failed", "declined", "cancelled", "unresolved"):
            with self.subTest(state=state):
                self.source.write({"state": state})
                self.assertEqual(self.original.revolut_receipt_options(), [])
                with self.assertRaises(UserError):
                    self._pdf("payment", self.source)
        self.request.assert_not_called()

    def test_nonfinal_refund_denies_completed_document(self):
        refund = self._refund(state="pending")
        for state in ("dispatching", "pending", "failed", "unresolved"):
            with self.subTest(state=state):
                refund.write({"state": state})
                self.assertEqual([(item["kind"], item["operation_id"]) for item in self.original.revolut_receipt_options()],
                                 [("payment", self.source.id)])
                with self.assertRaises(UserError):
                    self._pdf("refund", refund)
        self.request.assert_not_called()

    def test_inconsistent_verified_evidence_denies_receipt_without_repair(self):
        self.env.cr.execute(
            "UPDATE pos_revolut_payment_operation SET amount_minor = 1 WHERE id = %s", [self.source.id],
        )
        self.source.invalidate_recordset()
        with self.assertRaises(UserError):
            self._pdf("payment", self.source)
        self.assertEqual(self.source.state, "verified")
        self.assertEqual(self.source.amount_minor, 1)
        self.request.assert_not_called()

    def test_inconsistent_saved_tender_reference_denies_verified_document(self):
        self.env.cr.execute(
            "UPDATE pos_payment SET transaction_id = %s WHERE id = %s",
            ["wrong-persisted-payment-reference", self.source.pos_payment_id.id],
        )
        self.source.pos_payment_id.invalidate_recordset()
        with self.assertRaises(UserError):
            self._pdf("payment", self.source)
        self.assertEqual(self.source.state, "verified")
        self.assertEqual(self.original.state, "paid")
        self.request.assert_not_called()

    def test_cashier_and_manager_use_sale_access_without_financial_mutation_rights(self):
        for groups in ("point_of_sale.group_pos_user", "point_of_sale.group_pos_manager"):
            actor = self._actor(groups)
            order = self.original.with_user(actor).with_context(allowed_company_ids=self.company.ids)
            self.assertEqual(order.revolut_receipt_options()[0]["operation_id"], self.source.id)
            self.assertIn(self.source.revolut_payment_id, self._pdf("payment", self.source, actor, self.company.ids))
            with self.assertRaises(AccessError):
                self.source.with_user(actor).write({"state": "failed"})
        self.request.assert_not_called()

    def test_direct_report_denies_non_pos_and_inactive_company_users(self):
        other = self.env["res.company"].create({"name": "Receipt forbidden company"})
        ordinary = self._actor("base.group_user")
        foreign = self._actor("point_of_sale.group_pos_manager", other)
        multi = self._actor("point_of_sale.group_pos_manager", self.company | other)
        for user, companies in ((ordinary, self.company.ids), (foreign, other.ids), (multi, other.ids)):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.original.with_user(user).with_context(allowed_company_ids=companies).revolut_receipt_options()
                with self.assertRaises(AccessError):
                    self._pdf("payment", self.source, user, companies)
        self.request.assert_not_called()

    def test_repeated_downloads_and_failed_render_leave_financial_evidence_unchanged(self):
        self.session.write({"state": "closed"})
        self.env.flush_all()
        before = self._financial_evidence()
        self._pdf("payment", self.source)
        self.original.revolut_receipt_options()
        with patch.object(type(self.env["ir.actions.report"]), "_run_wkhtmltopdf",
                          side_effect=UserError("PDF printer unavailable; retry the download")):
            with self.assertRaisesRegex(UserError, "retry the download"):
                self._pdf("payment", self.source)
        self._pdf("payment", self.source)
        self.assertEqual(self._financial_evidence(), before)
        self.request.assert_not_called()

from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import new_test_user, tagged

from .test_revolut_payment import TestRevolutOrderSettlement
from .test_revolut_refund import TestRevolutRefund


@tagged("post_install", "-at_install")
class TestRevolutNativeDocuments(CommonPosTest):
    LOCATION_ID = TestRevolutOrderSettlement.LOCATION_ID
    TERMINAL_ID = TestRevolutOrderSettlement.TERMINAL_ID
    PAYMENT_ID = TestRevolutOrderSettlement.PAYMENT_ID
    _operation = TestRevolutOrderSettlement._operation
    _order_payload = TestRevolutOrderSettlement._order_payload
    _split_original = TestRevolutRefund._split_original

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Revolut native documents test", "payment_method_type": "terminal",
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
            "name": "Native document product", "available_in_pos": True, "list_price": 12.34,
            "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Native document reads must not call the Merchant API"),
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
            self.env, login=f"native_documents_{uuid4()}", groups=f"base.group_user,{groups}",
            company_id=companies[0].id, company_ids=[Command.set(companies.ids)],
        )

    def _financial_evidence(self):
        refunds = self.env["pos.revolut.refund.operation"].search([
            ("original_operation_id", "=", self.source.id),
        ], order="id")
        models = ("pos.revolut.payment.operation", "pos.revolut.refund.operation",
                  "pos.revolut.payment.dispatch", "pos.revolut.reconciliation.audit", "pos.payment", "pos.order",
                  "account.move", "ir.attachment")
        return {
            "counts": {
                name: self.env[name].sudo().search_count(
                    [("mimetype", "=", "application/pdf")] if name == "ir.attachment" else []
                ) for name in models
            },
            "payment": self.source.read([
                "state", "provider_state", "verified_at", "amount", "amount_minor",
                "currency_id", "revolut_order_id", "revolut_payment_id",
                "financial_snapshot", "receipt_merchant_snapshot", "write_date",
            ]),
            "refunds": refunds.read([
                "original_operation_id", "state", "provider_state", "verified_at",
                "amount", "amount_minor", "currency_id", "revolut_order_id",
                "financial_snapshot", "receipt_merchant_snapshot", "write_date",
            ]),
            "orders": (self.original | refunds.pos_order_id).read([
                "state", "account_move", "write_date",
            ]),
            "session": self.session.read(["state", "write_date"]),
        }

    def test_custom_document_interfaces_are_retired(self):
        for name in ("pos.revolut.receipt",
                     "report.pos_revolut.report_revolut_payment_receipt",
                     "report.pos_revolut.report_revolut_refund_receipt"):
            self.assertNotIn(name, self.env.registry.models)
        self.assertNotIn("revolut_receipt_links", self.original._fields)
        self.assertFalse(hasattr(self.original, "revolut_receipt_options"))
        for identifier in ("action_report_revolut_payment_receipt",
                           "action_report_revolut_refund_receipt",
                           "report_revolut_payment_receipt", "report_revolut_refund_receipt",
                           "report_revolut_receipt_layout", "view_pos_order_revolut_receipts"):
            self.assertFalse(self.env.ref(f"pos_revolut.{identifier}", raise_if_not_found=False))
        self.request.assert_not_called()

    def test_week_old_closed_session_native_read_preserves_uninvoiced_sale(self):
        self.session.write({"state": "closed"})
        self.assertFalse(self.original.account_move)
        self.env.flush_all()
        before = self._financial_evidence()
        for _read in range(2):
            data = self.env["pos.order"].read_pos_data_uuid(self.original.uuid)
            self.assertEqual(data["pos.order"][0]["id"], self.original.id)
            tender = next(item for item in data["pos.payment"] if item["id"] == self.source.pos_payment_id.id)
            self.assertEqual(tender["transaction_id"], self.source.revolut_payment_id)
            self.assertEqual(self._financial_evidence(), before)
        self.assertEqual(self.session.state, "closed")
        self.assertEqual(self.original.state, "paid")
        self.request.assert_not_called()

    def _check_native_refund_reads(self, amounts):
        refunds = [self._refund(amount) for amount in amounts]
        self.env.flush_all()
        before = self._financial_evidence()
        for _read in range(2):
            for refund in refunds:
                data = self.env["pos.order"].read_pos_data_uuid(refund.pos_order_id.uuid)
                tender = next(item for item in data["pos.payment"] if item["id"] == refund.pos_payment_id.id)
                self.assertEqual(tender["transaction_id"], refund.revolut_order_id)
                self.assertEqual(tender["amount"], -refund.amount)
            self.assertEqual(self._financial_evidence(), before)
        self.request.assert_not_called()

    def test_native_full_refund_reads_preserve_evidence(self):
        self._check_native_refund_reads((12.34,))

    def test_native_partial_refund_reads_preserve_evidence(self):
        self._check_native_refund_reads((6.17, 6.17))

    def test_native_split_tender_keeps_verified_reference_once(self):
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        self._split_original()
        self.env.flush_all()
        before = self._financial_evidence()
        data = self.env["pos.order"].read_pos_data_uuid(self.original.uuid)
        tenders = [item for item in data["pos.payment"] if item["pos_order_id"] == self.original.id]
        self.assertEqual(sorted(item["amount"] for item in tenders), [6.17, 6.17])
        self.assertEqual(sum(item["transaction_id"] == self.source.revolut_payment_id for item in tenders), 1)
        self.assertEqual(self._financial_evidence(), before)
        self.request.assert_not_called()

    def test_new_operations_reject_legacy_merchant_metadata(self):
        with self.assertRaisesRegex(ValidationError, "Legacy merchant evidence"):
            self._operation(str(uuid4()), str(uuid4()),
                            receipt_merchant_snapshot={"name": "Injected metadata"})
        refund = self._refund()
        with self.assertRaisesRegex(ValidationError, "Legacy merchant evidence"):
            refund.copy({"receipt_merchant_snapshot": {"name": "Injected metadata"}})
        self.request.assert_not_called()

    def test_verification_time_and_legacy_metadata_stay_immutable(self):
        refund = self._refund()
        for operation in (self.source, refund):
            with self.subTest(model=operation._name):
                self.assertFalse(operation.receipt_merchant_snapshot)
                operation.write({"verified_at": operation.verified_at})
                with self.assertRaises(ValidationError):
                    operation.write({"verified_at": fields.Datetime.now()})
                with self.assertRaises(ValidationError):
                    operation.write({"receipt_merchant_snapshot": {"name": "Forged merchant"}})
                self.env.cr.execute(
                    f"UPDATE {operation._table} SET receipt_merchant_snapshot = %s WHERE id = %s",
                    ['{"name": "Historical merchant"}', operation.id],
                )
                operation.invalidate_recordset()
                operation.write({"provider_state": operation.provider_state})
                self.assertEqual(operation.receipt_merchant_snapshot, {"name": "Historical merchant"})
        self.request.assert_not_called()

    def test_payment_and_refund_verification_no_longer_capture_merchant(self):
        refund = self._refund(state="pending")
        self.source.write({"state": "pending"})
        self.source.write({"state": "verified", "verified_at": self.event_time})
        refund.write({"state": "verified", "verified_at": self.event_time})
        self.assertFalse(self.source.receipt_merchant_snapshot)
        self.assertFalse(refund.receipt_merchant_snapshot)
        self.request.assert_not_called()

    def test_financial_deployment_guards_survive_receipt_retirement(self):
        refund = self._refund(state="pending")
        for state in ("created", "dispatching_order", "order_created", "dispatching_intent",
                      "pending", "unresolved", "verified", "failed", "declined", "cancelled"):
            self.source.write({"state": state})
            self.assertEqual(self.source.deployment_blocking,
                             state not in {"verified", "failed", "declined", "cancelled"})
        for state in ("dispatching", "pending", "unresolved", "verified", "failed"):
            refund.write({"state": state})
            self.assertEqual(refund.deployment_blocking, state not in {"verified", "failed"})
        self.request.assert_not_called()

    def test_native_tender_rollover_preserves_original_session_access(self):
        refund = self._refund()
        actor = self._actor()
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(actor.id)]})
        self.session.write({"state": "closed"})
        later = self.env["pos.session"].create({"config_id": self.pos_config_usd.id, "state": "opened"})
        orders = self.original | refund.pos_order_id
        self.env.cr.execute("UPDATE pos_order SET session_id = %s WHERE id IN %s",
                            [later.id, tuple(orders.ids)])
        orders.invalidate_recordset()
        rule = self.env["ir.rule"].sudo().create({
            "name": "Original financial session denial",
            "model_id": self.env["ir.model"]._get_id("pos.session"),
            "domain_force": f"[('id', '!=', {self.session.id})] if user.id == {actor.id} else []",
        })
        for operation in (self.source, refund):
            tender = operation.pos_payment_id.with_user(actor)
            self.assertFalse(tender.search([("id", "=", tender.id)]))
            with self.assertRaises(AccessError):
                tender.read(["payment_status", "transaction_id"])
        rule.unlink()
        self.assertEqual(self.source.pos_payment_id.with_user(actor).transaction_id, self.source.revolut_payment_id)
        self.assertEqual(refund.pos_payment_id.with_user(actor).transaction_id, refund.revolut_order_id)
        self.request.assert_not_called()

    def test_unassociated_refund_preserves_matching_return_draft_access(self):
        refund = self._refund()
        saved_return = refund.pos_order_id
        actor = self._actor("point_of_sale.group_pos_manager")
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(actor.id)]})
        self.env.cr.execute(
            "UPDATE pos_revolut_refund_operation SET pos_order_id = NULL, pos_payment_id = NULL WHERE id = %s",
            [refund.id],
        )
        refund.invalidate_recordset()
        rule = self.env["ir.rule"].sudo().create({
            "name": "Unassociated refund return denial",
            "model_id": self.env["ir.model"]._get_id("pos.order"),
            "domain_force": f"[('id', '!=', {saved_return.id})] if user.id == {actor.id} else []",
        })
        with self.assertRaises(AccessError):
            refund.with_user(actor)._check_revolut_register_access()
        rule.unlink()
        refund.with_user(actor)._check_revolut_register_access()
        self.request.assert_not_called()

    def test_native_later_invoice_creation_and_report_html_preserve_financial_evidence(self):
        self.assertFalse(self.original.account_move)
        self.original.write({"partner_id": self.partner_mobt.id})
        action = self.original.with_context(generate_pdf=False).action_pos_order_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(self.original.account_move, invoice)
        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.amount_total, 12.34)
        self.assertEqual(invoice.move_type, "out_invoice")
        self.session.write({"state": "closed"})
        self.env.flush_all()
        before = self._financial_evidence()
        invoice_before = invoice.read(["state", "amount_total", "name", "write_date"])
        # Exercise the native report template in this transaction. Actual
        # wkhtmltopdf needs a committed invoice on a normally running server
        # so its asset requests can use independent database cursors.
        for _read in range(2):
            html, extension = self.env["ir.actions.report"]._render_qweb_html(
                "account.account_invoices", [invoice.id],
            )
            self.assertEqual(extension, "html")
            text = html.decode()
            self.assertIn(invoice.name, text)
            self.assertIn(self.product.name, text)
            self.assertIn("12.34", text)
            self.assertEqual(self.original.action_pos_order_invoice()["res_id"], invoice.id)
            self.assertEqual(invoice.read(["state", "amount_total", "name", "write_date"]), invoice_before)
            self.assertEqual(self._financial_evidence(), before)
        self.request.assert_not_called()

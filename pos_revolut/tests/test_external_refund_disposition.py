from unittest.mock import patch
from uuid import uuid4

from lxml import etree

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import new_test_user, tagged

from .test_revolut_refund import TestRevolutRefund


@tagged("post_install", "-at_install")
class TestExternalRefundDisposition(CommonPosTest):
    LOCATION_ID = TestRevolutRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefund.PAYMENT_ID
    _operation = TestRevolutRefund._operation
    _order_payload = TestRevolutRefund._order_payload

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        outstanding = cls.env["account.account"].create({
            "name": "Revolut refund settlement", "code": "991041",
            "account_type": "asset_current", "reconcile": True,
            "company_ids": [Command.set(cls.company.ids)],
        })
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Financial-only Revolut", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
            "outstanding_account_id": outstanding.id,
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Financial-only original goods", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Financial-only native work must never request money"),
        ))
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        self.source = self._operation(
            payload["uuid"], payload["payment_ids"][0][2]["uuid"],
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        )
        payload["payment_ids"][0][2]["transaction_id"] = self.source.revolut_payment_id
        self.env["pos.order"].sync_from_ui([payload])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id
        self.refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "origin": "external", "original_operation_id": self.source.id,
            "pos_session_id": self.session.id, "currency_id": self.session.currency_id.id,
            "amount": 6.17, "amount_minor": 617, "state": "verified",
            "provider_state": "completed", "verified_at": fields.Datetime.now(),
            "revolut_order_id": str(uuid4()),
        })

    def _posted_adjustment(self, amount=6.17):
        action = self.refund.action_prepare_financial_correction()
        move = self.env["account.move"].browse(action["res_id"])
        outstanding = self.revolut_method.outstanding_account_id
        expense = self.env["account.account"].search([
            ("company_ids", "in", self.company.ids), ("account_type", "=", "expense"),
        ], limit=1)
        move.write({"line_ids": [
            Command.create({"name": "Goodwill refund", "account_id": expense.id,
                            "debit": amount, "currency_id": self.session.currency_id.id,
                            "amount_currency": amount}),
            Command.create({"name": "Verified card reimbursement", "account_id": outstanding.id,
                            "credit": amount, "currency_id": self.session.currency_id.id,
                            "amount_currency": -amount}),
        ]})
        move.action_post()
        return move

    def test_native_posted_adjustment_completes_without_products_or_http(self):
        before = {model: self.env[model].search_count([]) for model in (
            "pos.order", "pos.order.line", "pos.payment", "stock.move",
        )}
        move = self._posted_adjustment()
        original_evidence = self.refund.read(["state", "amount_minor", "revolut_order_id", "origin"])
        self.refund.action_record_financial_only("Customer goodwill; goods retained", move.id)
        audit = self.refund.read(["native_reconciled_at", "native_reconciled_by"])
        self.refund.action_record_financial_only("Customer goodwill; goods retained", move.id)
        self.assertEqual(self.refund.native_reconciliation_status, "financial_only")
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.revolut_original_order_id, self.original)
        self.assertEqual(self.refund.read(["state", "amount_minor", "revolut_order_id", "origin"]), original_evidence)
        self.assertEqual(self.refund.read(["native_reconciled_at", "native_reconciled_by"]), audit)
        for model, count in before.items():
            self.assertEqual(self.env[model].search_count([]), count, model)
        self.request.assert_not_called()

    def test_pending_missing_unposted_wrong_amount_and_reason_rejected(self):
        with self.assertRaises(UserError):
            self.refund.action_record_financial_only("Goods retained")
        self.refund.action_prepare_financial_correction()
        with self.assertRaises(UserError):
            self.refund.action_record_financial_only("Goods retained")
        move = self._posted_adjustment(amount=6)
        with self.assertRaises(UserError):
            self.refund.action_record_financial_only("Goods retained", move.id)
        with self.assertRaises(UserError):
            self.refund.action_record_financial_only(" ", move.id)
        self.refund.write({"state": "pending"})
        with self.assertRaises(UserError):
            self.refund.action_prepare_financial_correction()
        self.request.assert_not_called()

    def test_completed_native_correction_cannot_be_cancelled_or_edited(self):
        move = self._posted_adjustment()
        self.refund.action_record_financial_only("Goods retained", move.id)
        with self.assertRaises(UserError):
            move.button_draft()
        with self.assertRaises(UserError):
            move._reverse_moves(cancel=False)
        with self.assertRaises(UserError):
            move.line_ids[0].write({"debit": 7})
        with self.assertRaises(ValidationError):
            move.write({"revolut_external_refund_id": False})
        with self.assertRaises(UserError):
            self.refund.action_record_financial_only("Different reason", move.id)

    def test_invoiced_sale_requires_exact_posted_native_credit_note(self):
        self.original.write({"partner_id": self.partner_mobt.id})
        invoice_action = self.original.with_context(generate_pdf=False).action_pos_order_invoice()
        invoice = self.env["account.move"].browse(invoice_action["res_id"])
        action = self.refund.action_prepare_financial_correction()
        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(credit.reversed_entry_id, invoice)
        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(credit.state, "draft")
        credit.invoice_line_ids.write({"quantity": 0.5})
        credit.action_post()
        self.refund.action_record_financial_only("Partial price concession; goods retained", credit.id)
        self.assertEqual(self.refund.native_reconciliation_status, "financial_only")
        self.assertFalse(self.refund.pos_order_id)
        self.assertFalse(self.original.picking_ids.filtered(lambda picking: picking.location_dest_id.usage != "customer"))
        self.request.assert_not_called()

    def test_existing_exact_invoice_credit_note_can_be_associated_once(self):
        self.original.write({"partner_id": self.partner_mobt.id})
        self.original.with_context(generate_pdf=False).action_pos_order_invoice()
        credit = self.original.account_move._reverse_moves(cancel=False)
        credit.invoice_line_ids.write({"quantity": 0.5})
        credit.action_post()
        count = self.env["account.move"].search_count([])
        self.refund.action_record_financial_only("Separately posted concession", credit.id)
        self.assertEqual(self.refund.financial_correction_move_id, credit)
        self.assertEqual(self.env["account.move"].search_count([]), count)
        another = self.env["pos.revolut.refund.operation"].sudo().create({
            "origin": "external", "original_operation_id": self.source.id,
            "pos_session_id": self.session.id, "currency_id": self.session.currency_id.id,
            "amount": 6.17, "amount_minor": 617, "state": "verified",
            "provider_state": "completed", "verified_at": fields.Datetime.now(),
            "revolut_order_id": str(uuid4()),
        })
        with self.assertRaises(UserError):
            another.action_record_financial_only("Same correction cannot pay twice", credit.id)
        self.request.assert_not_called()

    def test_invoice_display_total_cannot_replace_native_accounting_evidence(self):
        self.original.write({"partner_id": self.partner_mobt.id})
        self.original.with_context(generate_pdf=False).action_pos_order_invoice()
        action = self.refund.action_prepare_financial_correction()
        credit = self.env["account.move"].browse(action["res_id"])
        credit.action_post()
        # A writable computed display field is not proof of the journal's
        # underlying reimbursement. The actual full-credit receivable remains.
        credit.write({"amount_total": self.refund.amount})
        with self.assertRaises(UserError):
            self.refund.action_record_financial_only("Partial concession", credit.id)
        self.assertEqual(self.refund.native_reconciliation_status, "outstanding")
        self.request.assert_not_called()

    def test_correction_editor_requires_existing_accounting_access(self):
        manager = new_test_user(
            self.env, login=f"correction_pos_manager_{uuid4()}",
            groups="point_of_sale.group_pos_manager",
        )
        accountant = new_test_user(
            self.env, login=f"correction_accountant_{uuid4()}",
            groups="account.group_account_user",
        )
        for user, has_editor in ((manager, False), (accountant, True)):
            view = self.env["account.move"].with_user(user).get_view(view_type="form")
            arch = etree.fromstring(view["arch"])
            self.assertEqual(bool(arch.xpath("//page[@id='aml_tab']")), has_editor)
            self.assertIn("Ask an accountant", view["arch"])

    def test_accountant_can_review_draft_but_cannot_complete_manager_disposition(self):
        accountant = new_test_user(
            self.env, login=f"refund_accountant_{uuid4()}",
            groups="base.group_user,account.group_account_user",
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        action = self.refund.action_prepare_financial_correction()
        move = self.env["account.move"].browse(action["res_id"]).with_user(accountant)
        move.write({"date": fields.Date.context_today(move)})
        with self.assertRaises(AccessError):
            self.refund.with_user(accountant).action_record_financial_only("Goods retained", move.id)
        self.assertEqual(self.refund.native_reconciliation_status, "outstanding")

import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from .test_revolut_payment import TestRevolutOrderSettlement
from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestRevolutNativePrinting(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout

    def _pos_fixture(self, helper, *args, **kwargs):
        http_session = self.session
        self.session = self.sale_session
        try:
            return helper(self, *args, **kwargs)
        finally:
            self.session = http_session

    def _historical_sale(self, customer=False, invoiced=False):
        self.revolut_method = self._configure_revolut_checkout()
        self.pos_config_usd = self.main_pos_config
        self.company = self.main_pos_config.company_id
        self.product = self.desk_pad.product_variant_id
        self.sale_session = self.main_pos_config.current_session_id
        payload = self._pos_fixture(
            TestRevolutOrderSettlement._order_payload, str(uuid4()), str(uuid4()),
        )
        payload["pos_reference"] = "Historical native Revolut sale"
        historical_date = fields.Datetime.now() - timedelta(days=8)
        payload["date_order"] = fields.Datetime.to_string(historical_date)
        if customer or invoiced:
            self.invoice_customer = self.env["res.partner"].create({
                "name": "Historical native invoice customer", "email": "native@example.test",
            })
            payload["partner_id"] = self.invoice_customer.id
        payment = payload["payment_ids"][0][2]
        operation = self._pos_fixture(
            TestRevolutOrderSettlement._operation, payload["uuid"], payment["uuid"],
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
            provider_state="captured", verified_at=historical_date,
        )
        payment.update(
            transaction_id=operation.revolut_payment_id,
            payment_ref_no=operation.revolut_order_id,
            ticket=f"Revolut payment: {operation.revolut_payment_id}",
        )
        self.env["pos.order"].sync_from_ui([payload])
        operation.invalidate_recordset()
        self.original = operation.pos_order_id
        self.assertEqual(self.original.state, "paid")
        self.assertLessEqual(self.original.date_order, fields.Datetime.now() - timedelta(days=7))
        if invoiced:
            self.original.with_context(generate_pdf=False).action_pos_order_invoice()
            self.assertEqual(self.original.account_move.state, "posted")
        else:
            self.assertFalse(self.original.account_move)
        self.sale_session.post_closing_cash_details(0)
        self.sale_session.close_session_from_ui()
        self.assertEqual(self.sale_session.state, "closed")
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        return operation

    def _financial_evidence(self, operation, invoice_creation=False):
        # Explicit native invoicing relinks existing payment/accounting records
        # and updates technical write timestamps. Reprinting/retrieval must
        # preserve those timestamps too; both flows preserve all payment proof.
        return {
            "operation": operation.read([
                "state", "provider_state", "verified_at", "amount", "amount_minor",
                "gross_amount_minor", "terminal_tip_minor", "financial_snapshot",
                "revolut_order_id", "revolut_payment_intent_id", "revolut_payment_id",
                *([] if invoice_creation else ["write_date"]),
            ]),
            "payments": self.original.payment_ids.read([
                "amount", "transaction_id", "payment_ref_no", "ticket",
                *([] if invoice_creation else ["write_date"]),
            ]),
            "session": self.sale_session.read(["state", "write_date"]),
            "counts": {
                model: self.env[model].sudo().search_count([])
                for model in ("pos.revolut.payment.operation", "pos.revolut.refund.operation",
                              "pos.revolut.payment.dispatch", "pos.revolut.reconciliation.audit")
            },
        }

    def _native_tour(self, tour, operation, invoice_creation=False, login="pos_user"):
        before = self._financial_evidence(operation, invoice_creation=invoice_creation)
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Native printing must not contact Merchant API"),
        ) as merchant:
            # Each HttpCase starts a fresh browser, after the original session
            # has closed. History must therefore load the saved sale via RPC.
            self.start_pos_tour(tour, login=login)
        self.env.invalidate_all()
        self.assertEqual(self._financial_evidence(operation, invoice_creation=invoice_creation), before)
        self.assertEqual(self.sale_session.state, "closed")
        merchant.assert_not_called()

    def test_week_old_noninvoiced_sale_reprints_through_native_history_after_fresh_load(self):
        operation = self._historical_sale()
        self.assertFalse(self.original.partner_id)
        state = self.original.state
        moves = self.env["account.move"].search_count([])
        self._native_tour("pos_revolut_native_historical_receipt", operation)
        self.assertEqual(self.original.state, state)
        self.assertFalse(self.original.account_move)
        self.assertEqual(self.env["account.move"].search_count([]), moves)
        self.assertEqual(self.original.nb_print, 2)

    def test_conserved_remaining_refund_renders_native_rounding_receipt_after_fresh_load(self):
        source = self._historical_sale()
        current_session = self.main_pos_config.current_session_id
        refunds = self.env["pos.revolut.refund.operation"].sudo()
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Native rounding receipt fixtures must not contact Merchant API"),
        ) as merchant:
            for quantity, minor, label in ((0.25, 309, "Historical quarter return"),
                                            (0.75, 925, "Historical conserved remaining return")):
                payload = self._pos_fixture(
                    TestRevolutOrderSettlement._order_payload, str(uuid4()), str(uuid4()),
                )
                payload.update(session_id=current_session.id, state="paid",
                               amount_total=-minor / 100, amount_paid=-minor / 100, pos_reference=label)
                line = payload["lines"][0][2]
                line.update(qty=-quantity, price_subtotal=-12.34 * quantity,
                            price_subtotal_incl=-12.34 * quantity,
                            refunded_orderline_id=self.original.lines.id)
                reference = str(uuid4())
                payment = payload["payment_ids"][0][2]
                payment.update(amount=-minor / 100, transaction_id=reference, payment_ref_no=reference,
                               ticket=f"Revolut refund: {reference}")
                refund = self.env["pos.revolut.refund.operation"].sudo().create({
                    "original_operation_id": source.id, "pos_session_id": current_session.id,
                    "order_uuid": payload["uuid"], "payment_line_uuid": payment["uuid"],
                    "amount": minor / 100, "amount_minor": minor, "return_total_minor": minor,
                    "currency_id": current_session.currency_id.id, "state": "verified",
                    "provider_state": "completed", "verified_at": fields.Datetime.now(),
                    "revolut_order_id": reference,
                    "financial_snapshot": self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
                })
                self.env["pos.order"].sync_from_ui([payload])
                refund.invalidate_recordset()
                self.assertTrue(refund.pos_order_id.revolut_return_allocation)
                self.assertEqual(refund.pos_order_id.amount_total, -minor / 100)
                refunds |= refund
            merchant.assert_not_called()
        returned = refunds[-1].pos_order_id
        before = returned.read(["amount_total", "amount_tax", "revolut_return_allocation"])
        line_before = returned.lines.read(["qty", "price_unit", "discount", "tax_ids", "write_date"])
        refund_before = refunds.read(["amount_minor", "return_total_minor", "revolut_order_id", "financial_snapshot", "write_date"])
        self._native_tour("pos_revolut_native_conserved_refund_receipt", source)
        self.assertEqual(returned.read(["amount_total", "amount_tax", "revolut_return_allocation"]), before)
        self.assertEqual(returned.lines.read(["qty", "price_unit", "discount", "tax_ids", "write_date"]), line_before)
        self.assertEqual(refunds.read(["amount_minor", "return_total_minor", "revolut_order_id", "financial_snapshot", "write_date"]), refund_before)
        self.assertEqual(returned.lines.qty, -0.75)
        self.assertEqual(returned.lines.price_unit, 12.34)
        self.assertEqual(returned.nb_print, 1)

    def test_native_invoice_retrieval_preserves_existing_accounting_document(self):
        # Native download content uses Odoo's HTML fallback in shared-cursor
        # test mode; actual PDF rendering runs in a normal disposable server.
        operation = self._historical_sale(invoiced=True)
        invoice = self.original.account_move
        before = invoice.read(["state", "name", "amount_total", "line_ids"])
        moves = self.env["account.move"].search_count([])
        self._native_tour("pos_revolut_native_invoice_retrieval", operation)
        self.assertEqual(self.original.account_move, invoice)
        self.assertEqual(invoice.read(["state", "name", "amount_total", "line_ids"]), before)
        self.assertEqual(self.env["account.move"].search_count([]), moves)

    def test_native_later_invoice_is_created_only_by_explicit_invoice_action(self):
        operation = self._historical_sale(customer=True)
        # Native later invoicing creates payment journal entries. Grant the
        # fixture manager Odoo's existing accounting role; cashier access and
        # production permissions are unchanged by the addon removal.
        self.pos_admin.group_ids = [Command.link(self.env.ref("account.group_account_invoice").id)]
        self._native_tour(
            "pos_revolut_native_later_invoice", operation, invoice_creation=True, login="pos_admin",
        )
        self.assertEqual(self.original.state, "done")
        self.assertEqual(self.original.invoice_status, "invoiced")
        self.assertEqual(self.original.account_move.state, "posted")
        self.assertEqual(self.original.account_move.partner_id, self.invoice_customer)
        self.assertEqual(self.original.account_move.amount_total, 12.34)

    def test_native_later_invoice_keeps_cashier_accounting_restriction(self):
        operation = self._historical_sale(customer=True)
        self.assertFalse(self.pos_user.has_group("account.group_account_invoice"))
        before = self._financial_evidence(operation)
        order_before = self.original.read(["state", "account_move", "to_invoice", "write_date"])
        moves = self.env["account.move"].search_count([])
        self.authenticate("pos_user", "pos_user")
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Denied native invoicing must not contact Merchant API"),
        ) as merchant:
            result = self.url_open(
                "/web/dataset/call_kw/pos.order/action_pos_order_invoice",
                data=json.dumps({
                    "jsonrpc": "2.0", "method": "call", "id": 1,
                    "params": {
                        "model": "pos.order", "method": "action_pos_order_invoice",
                        "args": [[self.original.id]], "kwargs": {},
                    },
                }),
                headers={"Content-Type": "application/json"},
            )
        self.assertEqual(result.json()["error"]["data"]["name"], "odoo.exceptions.AccessError")
        self.env.invalidate_all()
        self.assertEqual(self._financial_evidence(operation), before)
        self.assertEqual(self.original.read(["state", "account_move", "to_invoice", "write_date"]), order_before)
        self.assertEqual(self.env["account.move"].search_count([]), moves)
        merchant.assert_not_called()

    def test_retired_download_and_standard_report_urls_never_produce_pdfs(self):
        operation = self._historical_sale()
        outsider_company = self.env["res.company"].create({"name": "Native document outsider"})
        non_pos = new_test_user(
            self.env, login="native_no_pos", password="native_no_pos", groups="base.group_user",
        )
        cross_company = new_test_user(
            self.env, login="native_other_company", password="native_other_company",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=outsider_company.id, company_ids=[Command.set([outsider_company.id])],
        )
        before = self._financial_evidence(operation)
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Retired document routes must not contact Merchant API"),
        ) as merchant:
            for login in (None, non_pos.login, cross_company.login, "pos_user", "pos_admin"):
                self.authenticate(login, login)
                for kind in ("payment", "refund"):
                    for url in (
                        f"/pos_revolut/receipt/{kind}/{operation.id}",
                        f"/report/pdf/pos_revolut.report_revolut_{kind}_receipt/{operation.id}"
                        '?context={"force_report_rendering":true}',
                    ):
                        result = self.url_open(url, allow_redirects=False)
                        self.assertFalse(result.content.startswith(b"%PDF-"), (login, url))
                        self.assertNotEqual(result.headers.get("Content-Type"), "application/pdf")
        self.env.invalidate_all()
        self.assertEqual(self._financial_evidence(operation), before)
        merchant.assert_not_called()

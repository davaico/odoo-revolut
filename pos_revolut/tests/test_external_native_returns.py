"""Already-issued card money completes manager-selected native returns."""
from ast import literal_eval
from copy import deepcopy
from uuid import uuid4

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .test_external_refunds import TestExternalRefunds


@tagged("post_install", "-at_install")
class TestExternalNativeReturns(TestExternalRefunds):
    def test_return_link_uses_draft_pos_reference_then_final_order_name(self):
        refund = self._discover([self._external("completed", amount=1234)])
        native = self._prepare(refund)
        native.write({"name": "/"})
        displayed = native.with_context(revolut_return_display=True)
        self.assertEqual(native.name, "/")
        self.assertTrue(native.pos_reference)
        self.assertEqual(displayed.display_name, native.pos_reference)
        self.assertEqual(native.display_name, "/")
        manager_refund = refund.with_user(self._mutation_actor())
        view = manager_refund.get_view(view_type="form")
        link = etree.fromstring(view["arch"]).xpath("//field[@name='display_return_id']")[0]
        row = manager_refund.web_read({"display_return_id": {
            "fields": {"display_name": {}}, "context": literal_eval(link.get("context")),
        }})[0]
        self.assertEqual(row["display_return_id"], {
            "id": native.id, "display_name": native.pos_reference,
        })
        refund.with_user(self._mutation_actor()).action_validate_native_return()
        self.assertEqual(displayed.display_name, native.name)

    def test_manager_selects_and_finalizes_native_return_without_moving_money(self):
        refund = self._discover([self._external("completed", amount=1234)])
        manager = self._mutation_actor()
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Native completion must never move money")
        action = refund.with_user(manager).action_prepare_native_return([
            {"original_line_id": self.original.lines.id, "quantity": 1},
        ])
        native = self.env["pos.order"].browse(action["res_id"])
        self.assertEqual(native.state, "draft")
        self.assertEqual(native.amount_total, -12.34)
        self.assertFalse(native.picking_ids)
        refund.with_user(manager).action_validate_native_return()
        self.assertIn(native.state, ("paid", "done", "invoiced"))
        self.assertEqual(native.lines.refunded_orderline_id, self.original.lines)
        self.assertEqual(refund.pos_payment_id.amount, -12.34)
        self.assertEqual(refund.pos_payment_id.transaction_id, refund.revolut_order_id)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.assertEqual(refund.origin, "external")
        self.assertEqual(refund.pos_session_id, self.source.pos_session_id)
        refund.with_user(manager).action_validate_native_return()
        self.assertEqual(len(native.payment_ids), 1)
        self.request.assert_not_called()

    def _prepare(self, refund, quantity=1, **kwargs):
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Native work must never contact Revolut")
        action = refund.with_user(self._mutation_actor()).action_prepare_native_return([
            {"original_line_id": self.original.lines.id, "quantity": quantity},
        ], **kwargs)
        return self.env["pos.order"].browse(action["res_id"])

    def test_pending_association_resumes_after_authoritative_completion(self):
        refund = self._discover([self._external(amount=1234)])
        native = self._prepare(refund)
        self.assertEqual(native.payment_ids.payment_status, "waiting")
        manager = self._mutation_actor()
        with self.assertRaises(UserError):
            refund.with_user(manager).action_validate_native_return()
        self.assertEqual(native.state, "draft")
        self._discover([self._external("completed", amount=1234)])
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Native work must never contact Revolut")
        refund.with_user(manager).action_prepare_native_return()
        refund.with_user(manager).action_validate_native_return()
        self.assertEqual(native.payment_ids.payment_status, "done")
        self.assertEqual(native.payment_ids.transaction_id, self.refund_id)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.assertEqual(len(native.payment_ids), 1)
        self.request.assert_not_called()

    def test_failed_refund_cannot_become_a_negative_card_tender(self):
        refund = self._discover([self._external(amount=1234)])
        native = self._prepare(refund)
        self._discover([self._external("failed", amount=1234)])
        with self.assertRaises(UserError):
            refund.with_user(self._mutation_actor()).action_validate_native_return()
        self.assertEqual(native.state, "draft")
        self.assertEqual(native.payment_ids.payment_status, "waiting")
        self.assertFalse(native.payment_ids.revolut_refund_operation_id)

    def test_existing_draft_uses_selected_payment_and_rejects_unrelated_reference(self):
        refund = self._discover([self._external("completed", amount=1234)])
        payload = deepcopy(self.payload)
        payload["state"] = "draft"
        saved = self.env["pos.order"].sync_from_ui([payload])
        native = self.env["pos.order"].browse(next(row["id"] for row in saved["pos.order"] if row["uuid"] == payload["uuid"]))
        payment = native.payment_ids
        manager = self._mutation_actor()
        self.request.reset_mock()
        with self.assertRaises(UserError):
            refund.with_user(manager).action_prepare_native_return(return_order_id=native.id)
        # Roll back the injected unrelated reference with its rejection;
        # existing financial evidence cannot be erased as test cleanup.
        with self.assertRaises(UserError), self.env.cr.savepoint():
            payment.write({"transaction_id": str(uuid4())})
            refund.with_user(manager).action_prepare_native_return(return_order_id=native.id, payment_id=payment.id)
        action = refund.with_user(manager).action_prepare_native_return(return_order_id=native.id, payment_id=payment.id)
        self.assertEqual(action["res_id"], native.id)
        refund.with_user(manager).action_validate_native_return()
        self.assertEqual(native.payment_ids, payment)
        self.assertEqual(refund.pos_order_id, native)
        self.request.assert_not_called()

    def test_two_external_refunds_pay_one_return_exactly_once(self):
        first = self._external("completed", amount=617)
        second = self._external("completed", amount=617, id=str(uuid4()))
        refunds = self._discover([first, second]).sorted("id")
        native = self._prepare(refunds[0])
        manager = self._mutation_actor()
        with self.assertRaises(UserError):
            refunds[0].with_user(manager).action_validate_native_return()
        refunds[1].with_user(manager).action_prepare_native_return(return_order_id=native.id)
        refunds[0].with_user(manager).action_validate_native_return()
        self.assertEqual(len(native.payment_ids), 2)
        self.assertEqual(native.amount_paid, -12.34)
        self.assertEqual(set(refunds.mapped("native_reconciliation_status")), {"native_completed"})
        self.assertEqual(sum(refunds.mapped("amount_minor")), 1234)
        self.request.assert_not_called()

    def test_mixed_tender_keeps_external_refund_on_card_and_cash_separate(self):
        self._split_original()
        refund = self._discover([self._external("completed", amount=617)])
        native = self._prepare(refund)
        self.assertEqual(native.payment_ids.payment_method_id, self.revolut_method)
        manager = self._mutation_actor()
        self.assertTrue(native.with_user(manager).action_continue_external_native_return()["url"].endswith(f"/payment/{native.uuid}"))
        with self.assertRaises(UserError):
            refund.with_user(manager).action_validate_native_return()
        self.env["pos.payment"].with_user(manager).create({
            "pos_order_id": native.id, "uuid": str(uuid4()), "amount": -6.17,
            "payment_method_id": self.cash_payment_method.id, "name": fields.Datetime.now(),
        })
        refund.with_user(manager).action_validate_native_return()
        self.assertEqual(sorted(native.payment_ids.mapped("amount")), [-6.17, -6.17])
        self.assertEqual(refund.pos_payment_id.payment_method_id, self.revolut_method)
        self.request.assert_not_called()

    def test_multiple_original_card_tenders_keep_exact_sources(self):
        first, second = self._split_original(second_revolut=True)
        self._discover([
            self._external("completed", amount=617, source=first),
            self._external("completed", amount=617, source=second, id=str(uuid4())),
        ])
        refunds = self.env["pos.revolut.refund.operation"].search([( "original_operation_id", "in", [first.id, second.id])]).sorted("id")
        native = self._prepare(refunds[0])
        manager = self._mutation_actor()
        refunds[1].with_user(manager).action_prepare_native_return(return_order_id=native.id)
        refunds[0].with_user(manager).action_validate_native_return()
        self.assertEqual(set(refunds.mapped("original_operation_id").ids), {first.id, second.id})
        self.assertEqual(len(native.payment_ids), 2)
        self.request.assert_not_called()

    def test_historical_acknowledgement_preserved_and_never_proves_documents(self):
        refund = self._discover([self._external("completed", amount=1234)])
        manager = self._mutation_actor()
        historical = fields.Datetime.now()
        self.env.cr.execute("UPDATE pos_revolut_refund_operation SET native_reconciliation_status = 'reconciled', native_reconciled_by = %s, native_reconciled_at = %s WHERE id = %s", [manager.id, historical, refund.id])
        refund.invalidate_recordset()
        self.assertFalse(refund.pos_order_id)
        native = self._prepare(refund)
        self.assertEqual(refund.native_reconciliation_status, "native_draft")
        self.assertEqual(refund.historical_acknowledged_by, manager)
        self.assertEqual(refund.historical_acknowledged_at, historical)
        refund.with_user(manager).action_validate_native_return()
        self.assertEqual(refund.pos_order_id, native)
        self.assertEqual(refund.historical_acknowledged_at, historical)
        self.request.assert_not_called()

    def test_manager_register_authority_and_confirmed_selection_cannot_be_forged(self):
        refund = self._discover([self._external("completed", amount=1234)])
        selection = [{"original_line_id": self.original.lines.id, "quantity": 1}]
        cashier = self._mutation_actor(manager=False)
        manager = self._mutation_actor()
        with self.assertRaises(AccessError):
            refund.with_user(cashier).action_prepare_native_return(selection)
        native = self._prepare(refund)
        with self.assertRaises(UserError):
            refund.with_user(manager).action_prepare_native_return([{**selection[0], "quantity": 0.5}])
        with self.assertRaises(ValidationError):
            refund.sudo().write({"allocation_explicit": True})
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.unlink(manager.id)]})
        with self.assertRaises(AccessError):
            refund.with_user(manager).action_validate_native_return()
        self.assertEqual(native.state, "draft")
        self.request.assert_not_called()

    def test_provider_time_is_distinct_and_missing_time_remains_unavailable(self):
        refund = self._discover([self._external("completed", amount=617)])
        self.assertEqual(str(refund.provider_initiated_at), "2026-10-01 12:00:00")
        self.assertNotEqual(refund.provider_initiated_at, refund.create_date)
        self.assertEqual(refund.original_purchase_at, self.original.date_order)
        candidate = self._external("completed", amount=617, id=str(uuid4()))
        candidate.pop("created_at")
        second = self._discover([candidate]).filtered(lambda row: row.revolut_order_id == candidate["id"])
        self.assertFalse(second.provider_initiated_at)

    def test_manager_wizard_requires_product_confirmation_and_validates_native_order(self):
        refund = self._discover([self._external("completed", amount=1234)])
        manager = self._mutation_actor()
        self.request.reset_mock()
        action = refund.with_user(manager).action_open_native_completion()
        wizard = self.env["pos.revolut.external.refund.wizard"].with_user(manager).browse(action["res_id"])
        self.assertEqual(wizard.original_order_id, self.original)
        self.assertEqual(wizard.line_ids.product_id, self.product)
        self.assertEqual(wizard.line_ids.quantity, 0)
        with self.assertRaises(UserError):
            wizard.action_prepare()
        wizard.line_ids.write({"quantity": 1})
        native_action = wizard.action_prepare()
        native = self.env["pos.order"].with_user(manager).browse(native_action["res_id"])
        native.action_validate_external_native_return()
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.request.assert_not_called()

    def test_bound_pending_external_return_prevents_session_closure(self):
        refund = self._discover([self._external(amount=1234)])
        self._prepare(refund)
        with self.assertRaisesRegex(UserError, "Reconcile or settle"):
            self.session.write({"state": "closed"})
        self.assertEqual(self.session.state, "opened")

    def test_native_completion_reuses_quarter_then_residual_rounding(self):
        first = self._discover([self._external("completed", amount=309)])
        native = self._prepare(first, 0.25)
        first.with_user(self._mutation_actor()).action_validate_native_return()
        self.assertEqual(native.amount_total, -3.09)
        self.refund_id = str(uuid4())
        refunds = self._discover([self._external("completed", amount=925)])
        second = refunds.filtered(lambda row: row.revolut_order_id == self.refund_id)
        residual = self._prepare(second, 0.75)
        second.with_user(self._mutation_actor()).action_validate_native_return()
        self.assertEqual(residual.amount_total, -9.25)
        self.assertEqual(self.original.lines.refunded_qty, 1)
        self.assertEqual(first.amount_minor + second.amount_minor, 1234)
        self.request.assert_not_called()

    def test_explicit_external_terminal_tip_allocation_enables_remaining_base_refund(self):
        self._terminal_sale(tip_minor=200)
        refund = self._discover([self._external("completed", amount=200)])
        selection = [{"original_line_id": self.original.lines.filtered(lambda line: line.product_id == self.tip_product).id,
                      "quantity": 1}]
        manager = self._mutation_actor()
        self.request.reset_mock()
        with self.assertRaisesRegex(UserError, "Specify the base"):
            refund.with_user(manager).action_prepare_native_return(selection)
        action = refund.with_user(manager).action_prepare_native_return(selection, base_amount_minor=0, tip_amount_minor=200)
        native = self.env["pos.order"].browse(action["res_id"])
        refund.with_user(manager).action_validate_native_return()
        self.assertEqual(native.amount_total, -2)
        self.assertEqual((refund.base_amount_minor, refund.tip_amount_minor), (0, 200))
        self._tip_return(goods_qty=1, tip_qty=0, payment_minor=1234)
        sources = self.revolut_method.revolut_refund_sources(self.session.id, self.session.currency_id.id, self.payload)
        remaining = next(row for row in sources if row["operation_id"] == self.source.id)
        self.assertEqual((remaining["remaining_base_minor"], remaining["remaining_tip_minor"]), (1234, 0))
        self.request.assert_not_called()

    def test_completed_historical_native_return_association_does_not_duplicate_native_work(self):
        refund = self._discover([self._external("completed", amount=1234)])
        payload = deepcopy(self.payload)
        payload["state"] = "draft"
        saved = self.env["pos.order"].sync_from_ui([payload])
        native = self.env["pos.order"].browse(next(row["id"] for row in saved["pos.order"] if row["uuid"] == payload["uuid"]))
        payment = native.payment_ids
        # Model an existing native return from before this addon established
        # its server evidence; public completion must prove its reimbursement.
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_order SET state = 'paid' WHERE id = %s", [native.id])
        self.env.cr.execute("UPDATE pos_payment SET payment_status = 'done', transaction_id = %s, payment_ref_no = %s WHERE id = %s", [refund.revolut_order_id, refund.revolut_order_id, payment.id])
        native.invalidate_recordset()
        payment.invalidate_recordset()
        before = {model: self.env[model].search_count([]) for model in ("pos.order", "pos.payment", "stock.move", "account.move")}
        self.request.reset_mock()
        refund.with_user(self._mutation_actor()).action_prepare_native_return(return_order_id=native.id, payment_id=payment.id)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.assertEqual(refund.pos_order_id, native)
        for model, count in before.items():
            self.assertEqual(self.env[model].search_count([]), count, model)
        self.request.assert_not_called()

    def test_native_return_reload_and_receipt_read_preserve_financial_evidence(self):
        refund = self._discover([self._external("completed", amount=1234)])
        native = self._prepare(refund)
        manager = self._mutation_actor()
        refund.with_user(manager).action_validate_native_return()
        before = refund.read(["state", "amount_minor", "origin", "revolut_order_id", "native_reconciled_at"])
        for _read in range(2):
            data = self.env["pos.order"].with_user(manager).read_pos_data_uuid(native.uuid)
            tender = next(row for row in data["pos.payment"] if row["id"] == refund.pos_payment_id.id)
            self.assertEqual(tender["amount"], -12.34)
            self.assertEqual(tender["transaction_id"], refund.revolut_order_id)
            self.assertEqual(refund.read(["state", "amount_minor", "origin", "revolut_order_id", "native_reconciled_at"]), before)
        self.request.assert_not_called()

    def test_unknown_sibling_tip_components_protect_native_association(self):
        self._terminal_sale(tip_minor=200)
        selected = self._external("completed", amount=200)
        unknown = self._external(amount=200, id=str(uuid4()))
        refunds = self._discover([selected, unknown])
        refund = refunds.filtered(lambda row: row.revolut_order_id == selected["id"])
        selection = [{"original_line_id": self.original.lines.filtered(
            lambda line: line.product_id == self.tip_product).id, "quantity": 1}]
        before = self.env["pos.order"].search_count([])
        self.request.reset_mock()
        with self.assertRaisesRegex(UserError, "components"):
            refund.with_user(self._mutation_actor()).action_prepare_native_return(
                selection, base_amount_minor=0, tip_amount_minor=200)
        self.assertFalse(refunds.pos_order_id)
        self.assertEqual(self.env["pos.order"].search_count([]), before)
        self.request.assert_not_called()

"""Exercise actual native inventory/accounting for already-issued card refunds."""
import os
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_external_refunds import TestExternalRefunds


@tagged("post_install", "-at_install")
class TestExternalNativeStock(CommonPosTest):
    LOCATION_ID = TestExternalRefunds.LOCATION_ID
    TERMINAL_ID = TestExternalRefunds.TERMINAL_ID
    PAYMENT_ID = TestExternalRefunds.PAYMENT_ID
    _operation = TestExternalRefunds._operation
    _order_payload = TestExternalRefunds._order_payload
    _response = TestExternalRefunds._response
    _refund_response = TestExternalRefunds._refund_response
    _mutation_actor = TestExternalRefunds._mutation_actor
    _external = TestExternalRefunds._external
    _discover = TestExternalRefunds._discover

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Native external refund stock", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened", "update_stock_at_closing": False})
        picking_type = self.pos_config_usd.picking_type_id
        picking_type.write({"use_existing_lots": True, "use_create_lots": True})
        if picking_type.return_picking_type_id:
            picking_type.return_picking_type_id.write({"use_existing_lots": True, "use_create_lots": True})
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_SETTLEMENT_TEST": "test-only"}))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        self.manager = self._mutation_actor()

    def _sale(self, *, kind="consu", tracking="none", quantity=1, lots=(), invoiced=False):
        self.product = self.env["product.product"].create({
            "name": f"Native return {kind} {tracking}", "type": kind,
            "is_storable": kind == "consu", "tracking": tracking,
            "available_in_pos": True, "list_price": 12.34 / quantity,
            "taxes_id": [Command.clear()],
        })
        location = self.pos_config_usd.picking_type_id.default_location_src_id
        self.lots = self.env["stock.lot"]
        for name in lots:
            lot = self.env["stock.lot"].create({
                "name": name, "product_id": self.product.id, "company_id": self.company.id,
            })
            self.lots |= lot
            self.env["stock.quant"]._update_available_quantity(
                self.product, location, 1 if tracking == "serial" else quantity, lot_id=lot,
            )
        if kind == "consu" and not lots:
            self.env["stock.quant"]._update_available_quantity(self.product, location, quantity)
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        payload["lines"][0][2].update(
            qty=quantity, price_unit=12.34 / quantity,
            pack_lot_ids=[Command.create({"lot_name": name}) for name in lots],
        )
        if invoiced:
            payload["partner_id"] = self.partner_mobt.id
        payment = payload["payment_ids"][0][2]
        self.source = self._operation(
            payload["uuid"], payment["uuid"],
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        )
        payment["transaction_id"] = self.source.revolut_payment_id
        self.env["pos.order"].sync_from_ui([payload])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id
        if invoiced:
            self.original.with_context(generate_pdf=False).action_pos_order_invoice()
            self.assertEqual(self.original.account_move.state, "posted")
        if kind == "consu":
            self.assertTrue(self.original.picking_ids)
            self.assertEqual(set(self.original.picking_ids.mapped("state")), {"done"})
        self.source.credential_id.sudo().write({"next_refund_discovery_at": False})
        self.env.flush_all()

    def _verified_refund(self, amount=1234):
        self.refund_id = str(uuid4())
        records = self._discover([self._external("completed", amount=amount)])
        refund = records.filtered(lambda row: row.revolut_order_id == self.refund_id)
        self.assertEqual(len(refund), 1)
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Native completion must not request financial operations")
        return refund.with_user(self.manager).with_context(generate_pdf=False)

    def _prepare(self, refund, quantity=1, lots=()):
        action = refund.action_prepare_native_return([{
            "original_line_id": self.original.lines.id, "quantity": quantity,
            "lot_names": list(lots),
        }])
        native = self.env["pos.order"].browse(action["res_id"])
        self.assertEqual(native.state, "draft")
        self.assertFalse(native.picking_ids, "Manager preparation must not move stock")
        return native

    def _assert_return_move(self, native, quantity, lots=()):
        self.assertEqual(set(native.picking_ids.mapped("state")), {"done"})
        moves = native.picking_ids.move_ids.filtered(lambda move: move.product_id == self.product)
        self.assertEqual(sum(moves.mapped("quantity")), quantity)
        self.assertEqual(moves.origin_returned_move_id, self.original.picking_ids.move_ids)
        self.assertEqual(set(moves.move_line_ids.lot_id.mapped("name")), set(lots))
        self.assertEqual(set(moves.mapped("location_id.usage")), {"customer"})
        self.assertEqual(set(moves.mapped("location_dest_id.usage")), {"internal"})

    def test_partial_native_stock_return_and_repeated_validation_move_once(self):
        self._sale()
        refund = self._verified_refund(617)
        native = self._prepare(refund, 0.5)
        location = self.pos_config_usd.picking_type_id.default_location_src_id
        before = self.env["stock.quant"]._get_available_quantity(self.product, location)
        refund.action_validate_native_return()
        self._assert_return_move(native, 0.5)
        self.assertEqual(self.env["stock.quant"]._get_available_quantity(self.product, location), before + 0.5)
        evidence = (native.picking_ids.ids, native.picking_ids.move_ids.ids, native.payment_ids.ids)
        refund.action_prepare_native_return()
        refund.action_validate_native_return()
        self.assertEqual((native.picking_ids.ids, native.picking_ids.move_ids.ids, native.payment_ids.ids), evidence)
        self.assertEqual(self.env["stock.quant"]._get_available_quantity(self.product, location), before + 0.5)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.request.assert_not_called()

    def test_service_native_return_creates_no_inventory_movement(self):
        self._sale(kind="service")
        refund = self._verified_refund()
        before = self.env["stock.move"].search_count([])
        native = self._prepare(refund)
        refund.action_validate_native_return()
        self.assertFalse(native.picking_ids)
        self.assertEqual(self.env["stock.move"].search_count([]), before)
        self.assertEqual(native.payment_ids.amount, -12.34)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.request.assert_not_called()

    def test_serial_return_requires_original_selected_serial_and_prevents_reuse(self):
        self._sale(tracking="serial", quantity=2, lots=("RETURN-SERIAL-A", "RETURN-SERIAL-B"))
        refund = self._verified_refund(617)
        before = self.env["pos.order"].search_count([])
        for names in ((), ("FOREIGN-SERIAL",), ("RETURN-SERIAL-A", "RETURN-SERIAL-B")):
            with self.assertRaises(UserError):
                self._prepare(refund, 1, names)
            self.assertEqual(self.env["pos.order"].search_count([]), before)
            self.assertFalse(refund.pos_order_id)
        native = self._prepare(refund, 1, ("RETURN-SERIAL-A",))
        refund.action_validate_native_return()
        self._assert_return_move(native, 1, ("RETURN-SERIAL-A",))
        self.request.assert_not_called()
        second = self._verified_refund(617)
        with self.assertRaisesRegex(UserError, "already returned or reserved"):
            self._prepare(second, 1, ("RETURN-SERIAL-A",))
        remaining = self._prepare(second, 1, ("RETURN-SERIAL-B",))
        second.action_validate_native_return()
        self._assert_return_move(remaining, 1, ("RETURN-SERIAL-B",))
        self.assertEqual(self.original.lines.refunded_qty, 2)
        self.request.assert_not_called()

    def test_lot_return_moves_only_selected_quantity_and_rejects_ambiguous_lots(self):
        self._sale(tracking="lot", quantity=2, lots=("RETURN-LOT-A",))
        refund = self._verified_refund(617)
        with self.assertRaises(UserError):
            self._prepare(refund, 1, ("RETURN-LOT-A", "FOREIGN-LOT"))
        native = self._prepare(refund, 1, ("RETURN-LOT-A",))
        refund.action_validate_native_return()
        self._assert_return_move(native, 1, ("RETURN-LOT-A",))
        self.assertEqual(native.lines.pack_lot_ids.lot_name, "RETURN-LOT-A")
        self.request.assert_not_called()

    def test_existing_return_association_rechecks_original_tracking_evidence(self):
        self._sale(tracking="serial", lots=("RETURN-SERIAL-A",))
        native = self.original._refund()
        native.lines.write({"pack_lot_ids": [
            Command.clear(), Command.create({"lot_name": "FOREIGN-SERIAL"}),
        ]})
        refund = self._verified_refund()
        with self.assertRaises(UserError):
            refund.action_prepare_native_return(return_order_id=native.id)
        self.assertFalse(refund.pos_order_id)
        self.assertFalse(native.picking_ids)
        self.assertFalse(native.payment_ids)
        native.lines.write({"pack_lot_ids": [
            Command.clear(), Command.create({"lot_name": "RETURN-SERIAL-A"}),
        ]})
        action = refund.action_prepare_native_return(return_order_id=native.id)
        self.assertEqual(action["res_id"], native.id)
        refund.action_validate_native_return()
        self._assert_return_move(native, 1, ("RETURN-SERIAL-A",))
        self.request.assert_not_called()

    def test_invoiced_original_posts_exact_native_credit_note_linked_to_invoice(self):
        self._sale(invoiced=True)
        refund = self._verified_refund(617)
        original_invoice = self.original.account_move
        native = self._prepare(refund, 0.5)
        self.assertTrue(native.to_invoice)
        refund.action_validate_native_return()
        self._assert_return_move(native, 0.5)
        credit = native.account_move
        self.assertEqual(credit.state, "posted")
        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(credit.reversed_entry_id, original_invoice)
        self.assertEqual(credit.pos_refunded_invoice_ids, original_invoice)
        self.assertEqual(credit.amount_total, 6.17)
        self.assertEqual(credit.currency_id, self.original.currency_id)
        self.assertAlmostEqual(sum(credit.line_ids.mapped("balance")), 0)
        self.assertEqual(refund.pos_payment_id.account_move_id.state, "posted")
        entries = self.env["account.move"].search_count([])
        refund.action_validate_native_return()
        self.assertEqual(self.env["account.move"].search_count([]), entries)
        self.assertEqual(native.account_move, credit)
        self.request.assert_not_called()

    def test_closed_original_session_completes_in_current_same_register_session(self):
        self._sale()
        source_session = self.session
        source_session.post_closing_cash_details(0)
        source_session.close_session_from_ui()
        self.assertEqual(source_session.state, "closed")
        self.pos_config_usd.open_ui()
        current = self.pos_config_usd.current_session_id
        current.write({"state": "opened", "update_stock_at_closing": False})
        refund = self._verified_refund()
        action = refund.action_prepare_native_return([{
            "original_line_id": self.original.lines.id, "quantity": 1,
        }], session_id=current.id)
        native = self.env["pos.order"].browse(action["res_id"])
        self.assertEqual(native.session_id, current)
        self.assertEqual(refund.pos_session_id, source_session)
        refund.action_validate_native_return()
        self._assert_return_move(native, 1)
        self.assertEqual(refund.pos_payment_id.session_id, current)
        self.assertEqual(refund.original_operation_id.pos_session_id, source_session)
        self.request.assert_not_called()

    def test_failed_stock_finalization_keeps_draft_and_recovers_without_duplicate_move(self):
        self._sale()
        refund = self._verified_refund()
        native = self._prepare(refund)
        payment = native.payment_ids
        before = self.env["stock.move"].search_count([])
        with patch.object(type(self.env["stock.picking"]), "_action_done", side_effect=UserError("Stock validation interrupted")):
            with self.assertRaises(UserError):
                refund.action_validate_native_return()
        native.invalidate_recordset()
        self.assertEqual(native.state, "draft")
        self.assertEqual(native.payment_ids, payment)
        self.assertFalse(native.picking_ids)
        self.assertEqual(self.env["stock.move"].search_count([]), before)
        refund.action_prepare_native_return()
        refund.action_validate_native_return()
        self._assert_return_move(native, 1)
        self.assertEqual(native.payment_ids, payment)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.request.assert_not_called()

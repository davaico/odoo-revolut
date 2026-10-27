"""Exercise actual native inventory/accounting for already-issued card refunds."""
import os
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_external_refunds import TestExternalRefunds


@tagged("post_install", "-at_install")
class TestExternalNativeStock(TestPointOfSaleCommon):
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
        cls.pos_config.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Native external refund stock", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })

    def setUp(self):
        super().setUp()
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened", "update_stock_at_closing": False})
        picking_type = self.pos_config.picking_type_id
        picking_type.write({"use_existing_lots": True, "use_create_lots": True})
        if picking_type.return_picking_type_id:
            picking_type.return_picking_type_id.write({"use_existing_lots": True, "use_create_lots": True})
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_SETTLEMENT_TEST": "test-only"}))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        self.manager = self._mutation_actor()

    def _sale(self, *, kind="consu", tracking="none", quantity=1, lots=(), invoiced=False, deferred=False, valuation_cost=None):
        self.product = self.env["product.product"].create({
            "name": f"Native return {kind} {tracking}", "type": kind,
            "is_storable": kind == "consu", "tracking": tracking,
            "available_in_pos": True, "list_price": 12.34 / quantity,
            "taxes_id": [Command.clear()],
        })
        if valuation_cost is not None:
            self.product.write({"categ_id": self.stock_account_product_categ.id, "standard_price": valuation_cost})
        location = self.pos_config.picking_type_id.default_location_src_id
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
        if deferred:
            self.session.write({"update_stock_at_closing": True})
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        payload["lines"][0][2].update(
            qty=quantity, price_unit=12.34 / quantity,
            pack_lot_ids=[Command.create({"lot_name": name}) for name in lots],
        )
        if invoiced:
            payload["partner_id"] = self.partner1.id
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
        if kind == "consu" and not deferred:
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

    def _assert_return_move(self, native, quantity, lots=(), original_moves=None):
        self.assertEqual(set(native.picking_ids.mapped("state")), {"done"})
        moves = native.picking_ids.move_ids.filtered(lambda move: move.product_id == self.product)
        self.assertEqual(sum(moves.mapped("quantity")), quantity)
        self.assertEqual(moves.origin_returned_move_id, self.original.picking_ids.move_ids if original_moves is None else original_moves)
        self.assertEqual(set(moves.move_line_ids.lot_id.mapped("name")), set(lots))
        self.assertEqual(set(moves.mapped("location_id.usage")), {"customer"})
        self.assertEqual(set(moves.mapped("location_dest_id.usage")), {"internal"})

    def test_partial_native_stock_return_and_repeated_validation_move_once(self):
        self._sale()
        refund = self._verified_refund(617)
        native = self._prepare(refund, 0.5)
        location = self.pos_config.picking_type_id.default_location_src_id
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
        self.pos_config.open_ui()
        current = self.pos_config.current_session_id
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

    def test_historical_stock_and_credit_note_association_preserves_native_history(self):
        self._sale(invoiced=True)
        refund = self._verified_refund()
        native = self._prepare(refund)
        refund.action_validate_native_return()
        self._assert_return_move(native, 1)
        credit = native.account_move
        self.assertEqual(credit.state, "posted")
        self.assertEqual(credit.reversed_entry_id, self.original.account_move)
        payment = native.payment_ids
        history = (native.picking_ids.ids, native.picking_ids.move_ids.ids,
                   credit.ids, credit.line_ids.ids, payment.ids)
        counts = {model: self.env[model].search_count([]) for model in
                  ("pos.order", "pos.payment", "stock.move", "account.move", "account.move.line")}
        # Preserve genuine native stock/accounting work, representing a release
        # before the addon stored association and per-line allocation evidence.
        # SQL changes only the absent historical addon metadata, never effects.
        self.env.flush_all()
        self.env.cr.execute("""
            UPDATE pos_revolut_refund_operation
               SET pos_order_id = NULL, pos_payment_id = NULL, order_uuid = NULL,
                   payment_line_uuid = NULL, financial_snapshot = NULL,
                   return_allocation = NULL, return_total_minor = 0,
                   allocation_explicit = FALSE, base_amount_minor = 0, tip_amount_minor = 0,
                   native_lot_snapshot = NULL, native_reconciliation_status = 'pending',
                   native_reconciled_by = NULL, native_reconciled_at = NULL
             WHERE id = %s
        """, [refund.id])
        self.env.cr.execute("UPDATE pos_payment SET revolut_refund_operation_id = NULL WHERE id = %s", [payment.id])
        self.env.cr.execute("UPDATE pos_order SET revolut_return_allocation = NULL WHERE id = %s", [native.id])
        refund.invalidate_recordset()
        payment.invalidate_recordset()
        native.invalidate_recordset()
        self.request.reset_mock()
        for _repeat in range(2):
            action = refund.action_associate_native_return(native.id, [{
                "refund_id": refund.id, "payment_id": payment.id,
            }])
            self.assertEqual(action["res_id"], native.id)
            self.assertEqual(refund.native_reconciliation_status, "native_completed")
            self.assertEqual(refund.pos_payment_id, payment)
            self.assertEqual((native.picking_ids.ids, native.picking_ids.move_ids.ids,
                              native.account_move.ids, native.account_move.line_ids.ids,
                              native.payment_ids.ids), history)
            self._assert_return_move(native, 1)
            self.assertEqual(native.account_move.state, "posted")
            self.assertEqual(native.account_move.amount_total, 12.34)
            self.assertEqual({model: self.env[model].search_count([]) for model in counts}, counts)
        self.request.assert_not_called()

    def test_deferred_stock_closing_links_same_session_sale_and_external_return(self):
        self._sale(deferred=True)
        self.assertFalse(self.original.picking_ids)
        refund = self._verified_refund(617)
        native = self._prepare(refund, 0.5)
        refund.action_validate_native_return()
        self.assertEqual(native.state, "paid")
        self.assertFalse(native.picking_ids)
        self.assertEqual(refund.native_reconciliation_status, "native_draft")
        self.session.post_closing_cash_details(0)
        self.session.close_session_from_ui()
        self.assertEqual(self.session.state, "closed")
        self.assertEqual(set(self.original.picking_ids.mapped("state")), {"done"})
        self._assert_return_move(native, 0.5)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.request.assert_not_called()

    def test_native_return_links_original_move_into_configured_return_location(self):
        self._sale()
        returned_goods = self.env["stock.location"].create({
            "name": "External returned goods", "usage": "internal",
            "location_id": self.pos_config.picking_type_id.default_location_src_id.id,
        })
        return_type = self.pos_config.picking_type_id.return_picking_type_id
        if not return_type:
            return_type = self.pos_config.picking_type_id.copy({"name": "External returns", "code": "incoming"})
            self.pos_config.picking_type_id.return_picking_type_id = return_type
        return_type.default_location_dest_id = returned_goods
        refund = self._verified_refund()
        native = self._prepare(refund)
        refund.action_validate_native_return()
        self._assert_return_move(native, 1)
        self.assertEqual(native.picking_ids.location_dest_id, returned_goods)
        self.assertEqual(self.env["stock.quant"]._get_available_quantity(self.product, returned_goods), 1)
        self.request.assert_not_called()

    def test_return_of_delivered_scheduled_sale_does_not_schedule_new_procurement(self):
        self._sale()
        self.original.shipping_date = fields.Date.today()
        original_pickings = self.original.picking_ids
        refund = self._verified_refund()
        native = self._prepare(refund)
        self.assertFalse(native.shipping_date)
        refund.action_validate_native_return()
        self._assert_return_move(native, 1)
        self.assertEqual(self.original.picking_ids, original_pickings)
        self.request.assert_not_called()

    def test_closed_deferred_source_uses_native_session_history_without_rewriting_it(self):
        self._sale(deferred=True)
        source_session = self.session
        source_session.post_closing_cash_details(0)
        source_session.close_session_from_ui()
        self.assertEqual(source_session.state, "closed")
        self.assertFalse(self.original.picking_ids)
        source_moves = source_session.picking_ids.move_ids.filtered(lambda move: move.product_id == self.product)
        self.assertEqual(set(source_moves.mapped("state")), {"done"})
        history = (source_moves.ids, source_moves.move_line_ids.ids, source_moves.stock_valuation_layer_ids.ids)
        self.pos_config.open_ui()
        current = self.pos_config.current_session_id
        current.write({"state": "opened", "update_stock_at_closing": False})
        refund = self._verified_refund(617)
        native = self._prepare(refund, 0.5)
        self.assertEqual(native.session_id, current)
        refund.action_validate_native_return()
        self._assert_return_move(native, 0.5, original_moves=source_moves)
        self.assertFalse(self.original.picking_ids)
        self.assertEqual((source_moves.ids, source_moves.move_line_ids.ids, source_moves.stock_valuation_layer_ids.ids), history)
        self.assertEqual(refund.native_reconciliation_status, "native_completed")
        self.request.assert_not_called()

    def test_native_return_values_goods_at_original_cost_before_posting_stock_entries(self):
        self._sale(valuation_cost=7)
        original_layers = self.original.picking_ids.move_ids.stock_valuation_layer_ids
        self.assertEqual(sum(original_layers.mapped("quantity")), -1)
        self.assertEqual(sum(original_layers.mapped("value")), -7)
        self.product.standard_price = 11
        refund = self._verified_refund(617)
        native = self._prepare(refund, 0.5)
        refund.action_validate_native_return()
        layers = native.picking_ids.move_ids.stock_valuation_layer_ids
        self.assertEqual(sum(layers.mapped("quantity")), 0.5)
        self.assertEqual(sum(layers.mapped("value")), 3.5)
        self.assertEqual(set(layers.account_move_id.mapped("state")), {"posted"})
        self._assert_return_move(native, 0.5)
        evidence = (layers.ids, layers.account_move_id.ids)
        refund.action_validate_native_return()
        self.assertEqual((native.picking_ids.move_ids.stock_valuation_layer_ids.ids,
                          native.picking_ids.move_ids.stock_valuation_layer_ids.account_move_id.ids), evidence)
        self.request.assert_not_called()

    def test_historical_pooled_native_return_association_preserves_completed_stock_and_accounts(self):
        self._sale(tracking="lot", quantity=2, lots=("HISTORICAL-RETURN-LOT",),
                   deferred=True, valuation_cost=7)
        native = self.original._refund()
        native.lines.write({"qty": -1})
        native.lines._onchange_amount_line_all()
        native._compute_prices()
        self.refund_id = str(uuid4())
        payment = self.env["pos.payment"].create({
            "pos_order_id": native.id, "payment_method_id": self.revolut_method.id,
            "amount": -6.17, "payment_status": "waiting", "uuid": str(uuid4()),
        })
        # Represent financial metadata recorded before today's addon checkout
        # guards existed. Inventory and accounting below use real native close;
        # no external association or addon-created order picking exists yet.
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_order SET state = 'paid' WHERE id = %s", [native.id])
        self.env.cr.execute("""
            UPDATE pos_payment SET payment_status = 'done', transaction_id = %s, payment_ref_no = %s
             WHERE id = %s
        """, [self.refund_id, self.refund_id, payment.id])
        native.invalidate_recordset()
        payment.invalidate_recordset()
        # Only bypass the newer addon's evidence requirement while building
        # this pre-addon history. Native stock/accounting APIs remain intact.
        with patch.object(type(native), "_check_revolut_order", return_value=None):
            self.session.post_closing_cash_details(0)
            self.session.close_session_from_ui()
        self.assertEqual(self.session.state, "closed")
        self.assertFalse(native.picking_ids)
        pooled = self.session.picking_ids
        incoming = pooled.move_ids.filtered(lambda move: move.location_id.usage == "customer")
        self.assertEqual(sum(incoming.mapped("quantity")), 1)
        self.assertEqual(incoming.move_line_ids.lot_id, self.lots)
        self.assertEqual(set(pooled.mapped("state")), {"done"})
        self.assertEqual(self.session.move_id.state, "posted")
        history = (pooled.ids, pooled.move_ids.ids, pooled.move_line_ids.ids,
                   pooled.move_ids.stock_valuation_layer_ids.ids, self.session.move_id.ids,
                   self.session.move_id.line_ids.ids, payment.ids)
        counts = {model: self.env[model].search_count([]) for model in
                  ("stock.picking", "stock.move", "stock.move.line", "stock.valuation.layer",
                   "account.move", "account.move.line", "pos.payment")}
        refund = self._discover([self._external("completed", amount=617)]).with_user(self.manager)
        self.assertEqual(len(refund), 1)
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Historical association must not contact Merchant HTTP")
        for _repeat in range(2):
            refund.action_associate_native_return(native.id, [{"refund_id": refund.id, "payment_id": payment.id}])
            self.assertEqual(refund.native_reconciliation_status, "native_completed")
            self.assertFalse(native.picking_ids, "Keep native pooled history unchanged")
            self.assertEqual((pooled.ids, pooled.move_ids.ids, pooled.move_line_ids.ids,
                              pooled.move_ids.stock_valuation_layer_ids.ids, self.session.move_id.ids,
                              self.session.move_id.line_ids.ids, payment.ids), history)
            self.assertEqual({model: self.env[model].search_count([]) for model in counts}, counts)
        self.request.assert_not_called()

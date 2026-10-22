"""Managers resume already-issued refunds through the actual Odoo 18 register."""
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import fields
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_external_refunds import TestExternalRefunds
from .test_revolut_payment import TestRevolutOrderSettlement
from .test_revolut_refund_history_ui import TestRevolutRefundHistory
from .test_revolut_native_printing import TestRevolutNativePrinting


@tagged("post_install", "-at_install")
class TestExternalRefundManagerUi(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutRefundHistory.LOCATION_ID
    TERMINAL_ID = TestRevolutRefundHistory.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefundHistory.PAYMENT_ID
    _configure_revolut_checkout = TestRevolutRefundHistory._configure_revolut_checkout
    _pos_fixture = TestRevolutRefundHistory._pos_fixture
    _discover = TestExternalRefunds._discover

    @staticmethod
    def _response(payload=None, **values):
        result = Mock(status_code=200)
        result.json.return_value = payload if payload is not None else values
        return result

    def _run_resume(self, *, external=True, split=False):
        self.source = TestRevolutNativePrinting._historical_sale(self, split=split)
        session = self.main_pos_config.current_session_id
        session.write({"update_stock_at_closing": False})
        reference = str(uuid4())
        minor = 617 if split else 1234
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.request = provider
            if external:
                refund = self._discover([{
                    "id": reference, "state": "completed", "type": "refund",
                    "amount": minor, "currency": session.currency_id.name,
                    "related_order_id": self.source.revolut_order_id,
                    "created_at": "2026-10-01T12:00:00Z",
                }])
                self.assertEqual(len(refund), 1)
                self.assertFalse(refund.pos_order_id)
            else:
                payload = self._pos_fixture(
                    TestRevolutOrderSettlement._order_payload, str(uuid4()), str(uuid4()),
                )
                payload.update(session_id=session.id, amount_total=-12.34, amount_paid=-12.34)
                payload["lines"][0][2].update(qty=-1, refunded_orderline_id=self.original.lines.id)
                refund = self.env["pos.revolut.refund.operation"].sudo().create({
                    "original_operation_id": self.source.id, "pos_session_id": session.id,
                    "order_uuid": payload["uuid"], "payment_line_uuid": payload["payment_ids"][0][2]["uuid"],
                    "amount": 12.34, "amount_minor": 1234, "return_total_minor": 1234,
                    "currency_id": session.currency_id.id, "state": "verified",
                    "provider_state": "completed", "verified_at": fields.Datetime.now(),
                    "revolut_order_id": reference,
                    "financial_snapshot": self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
                })
            provider.reset_mock()
            provider.side_effect = AssertionError("Resuming an existing reimbursement must not contact Revolut")
            action = self.env.ref("pos_revolut.action_revolut_refunds")
            tour = ("pos_revolut_external_resume_mixed" if split else "pos_revolut_external_resume") if external else "pos_revolut_manager_restore_return"
            self.start_tour(f"/odoo/action-{action.id}/{refund.id}?debug=tests", tour, login="pos_admin")
            provider.assert_not_called()
        self.env.invalidate_all()
        native = refund.pos_order_id
        self.assertEqual(native.state, "paid")
        self.assertEqual(native.session_id, session)
        self.assertEqual(native.amount_total, -12.34)
        self.assertEqual(native.amount_paid, -12.34)
        self.assertEqual(native.lines.refunded_orderline_id, self.original.lines)
        self.assertEqual(self.original.lines.refunded_qty, 1)
        self.assertEqual(refund.pos_payment_id.amount, -minor / 100)
        self.assertEqual(refund.pos_payment_id.transaction_id, reference)
        self.assertEqual(len(native.payment_ids), 2 if split else 1)
        self.assertEqual(len(native.picking_ids), 1)
        self.assertEqual(native.picking_ids.state, "done")
        if external:
            self.assertEqual(refund.native_reconciliation_status, "native_completed")
            self.assertEqual(native.picking_ids.move_ids.origin_returned_move_id, (self.original.picking_ids or self.source.pos_session_id.picking_ids).move_ids.filtered(
                lambda move: move.product_id == self.product))
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.revolut_order_id, reference)
        self.assertEqual(self.env["pos.revolut.refund.operation"].search_count([
            ("original_operation_id", "=", self.source.id),
        ]), 1)

    def test_manager_completes_discovered_refund_after_native_register_reload(self):
        self._run_resume()

    def test_manager_completes_cash_share_without_second_external_card_refund(self):
        self._run_resume(split=True)

    def test_manager_restores_missing_odoo_return_in_native_register(self):
        self._run_resume(external=False)

    def test_external_return_reprints_from_closed_session_without_financial_dispatch(self):
        self._run_resume()
        refund = self.env["pos.revolut.refund.operation"].search([
            ("original_operation_id", "=", self.source.id),
        ])
        native = refund.pos_order_id
        native.write({"pos_reference": "Historical external return"})
        session = native.session_id
        session.post_closing_cash_details(0)
        session.close_session_from_ui()
        self.assertEqual(session.state, "closed")
        self.main_pos_config.with_user(self.pos_user).open_ui()
        self.main_pos_config.current_session_id.set_opening_control(0, "")
        # Reprints may increment nb_print; all financial and stock history stays exact.
        before = {
            "refund": refund.read(["state", "amount_minor", "revolut_order_id", "write_date"]),
            "order": native.read(["state", "amount_total", "amount_tax", "account_move", "payment_ids", "picking_ids"]),
            "payments": native.payment_ids.read(["amount", "transaction_id", "payment_ref_no", "write_date"]),
            "session": session.read(["state", "move_id", "write_date"]),
            "counts": {model: self.env[model].sudo().search_count([]) for model in (
                "pos.order", "pos.payment", "stock.picking", "stock.move", "account.move", "account.payment",
                "pos.revolut.refund.operation", "pos.revolut.payment.operation", "pos.revolut.payment.dispatch",
            )},
        }
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=AssertionError("Historical external receipt must not contact Revolut")) as provider:
            self.start_pos_tour("pos_revolut_external_historical_reprint", login="pos_user")
            provider.assert_not_called()
        self.env.invalidate_all()
        self.assertEqual(refund.read(["state", "amount_minor", "revolut_order_id", "write_date"]), before["refund"])
        self.assertEqual(native.read(["state", "amount_total", "amount_tax", "account_move", "payment_ids", "picking_ids"]), before["order"])
        self.assertEqual(native.payment_ids.read(["amount", "transaction_id", "payment_ref_no", "write_date"]), before["payments"])
        self.assertEqual(session.read(["state", "move_id", "write_date"]), before["session"])
        for model, count in before["counts"].items():
            self.assertEqual(self.env[model].sudo().search_count([]), count, model)
        self.assertEqual(native.nb_print, 2)

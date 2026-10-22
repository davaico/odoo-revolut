"""Closed-session originals survive native history, draft loading, and returns."""
from unittest.mock import patch

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .authorization_fixtures import install_zero_reports
from .test_revolut_native_printing import TestRevolutNativePrinting
from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestRevolutRefundHistory(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    REFUND_ID = TestRevolutVerifiedCheckout.REFUND_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout
    _response = TestRevolutVerifiedCheckout._response

    _pos_fixture = TestRevolutNativePrinting._pos_fixture
    _historical_sale = TestRevolutNativePrinting._historical_sale

    def _run_history_refund(self, tour):
        # Use the same native closed-session fixture as historical receipt
        # acceptance. Neither an in-browser sale nor its cached original exists.
        source = self._historical_sale()
        old_session = self.sale_session
        current_session = self.main_pos_config.current_session_id
        current_session.write({"update_stock_at_closing": False})
        original_move = old_session.move_id
        self.assertEqual(original_move.state, "posted")
        original_accounting = original_move.read(["state", "line_ids", "amount_total", "write_date"])
        original_pickings = self.original.picking_ids
        calls = []

        def request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if method == "GET" and url.endswith(f"/orders/{source.revolut_order_id}"):
                return self._response({
                    "id": source.revolut_order_id, "state": "completed", "type": "payment",
                    "amount": 1234, "refunded_amount": 0,
                    "currency": current_session.currency_id.name,
                    "payments": [{"id": source.revolut_payment_id, "state": "captured"}],
                })
            if method == "POST" and url.endswith(f"/orders/{source.revolut_order_id}/refund"):
                self.assertEqual(kwargs["json"]["amount"], 1234)
                return self._response({
                    "id": self.REFUND_ID, "state": "pending", "type": "refund",
                    "amount": 1234, "currency": current_session.currency_id.name,
                    "related_order_id": source.revolut_order_id,
                })
            if method == "GET" and url.endswith(f"/orders/{self.REFUND_ID}"):
                return self._response({
                    "id": self.REFUND_ID, "state": "completed", "type": "refund",
                    "amount": 1234, "currency": current_session.currency_id.name,
                    "related_order_id": source.revolut_order_id,
                })
            raise AssertionError(f"Unexpected Merchant API request during historical refund: {method} {url}")

        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=request,
        ) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour(tour, login="pos_admin")
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].search([
            ("original_operation_id", "=", source.id),
        ])
        self.assertEqual(len(refund), 1)
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.original_order_id, self.original)
        self.assertEqual(source.pos_session_id, old_session)
        self.assertEqual(refund.pos_session_id, current_session)
        returned = refund.pos_order_id
        self.assertEqual(returned.state, "paid")
        self.assertEqual(returned.session_id, current_session)
        self.assertEqual(returned.amount_total, -12.34)
        self.assertEqual(returned.amount_paid, -12.34)
        self.assertEqual(returned.lines.refunded_orderline_id, self.original.lines)
        self.assertEqual(returned.lines.qty, -1)
        self.assertEqual(self.original.lines.refunded_qty, 1)
        self.assertEqual(refund.pos_payment_id.uuid, refund.payment_line_uuid)
        self.assertEqual(refund.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refund.pos_payment_id.payment_ref_no, self.REFUND_ID)
        posts = [kwargs for method, _url, kwargs in calls if method == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["headers"]["Idempotency-Key"], refund.idempotency_key)
        self.assertEqual(posts[0]["json"]["merchant_order_data"]["reference"], refund.idempotency_key)
        self.assertEqual(old_session.state, "closed")
        self.assertEqual(old_session.move_id, original_move)
        self.assertEqual(original_move.read(["state", "line_ids", "amount_total", "write_date"]), original_accounting)
        self.assertEqual(self.original.picking_ids, original_pickings)
        self.assertEqual(len(returned.picking_ids), 1)
        self.assertEqual(returned.picking_ids.state, "done")
        moves = returned.picking_ids.move_ids.filtered(lambda move: move.product_id == self.product)
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.quantity, 1)
        self.assertEqual(moves.location_id.usage, "customer")
        self.assertEqual(moves.location_dest_id.usage, "internal")
        # Replaying native completion must retain the one stock return and
        # tender rather than generating a second movement or provider refund.
        pickings, payments = returned.picking_ids, returned.payment_ids
        returned._process_saved_order(False)
        self.assertEqual(returned.picking_ids, pickings)
        self.assertEqual(returned.payment_ids, payments)
        self.assertEqual(sum(method == "POST" for method, _url, _kwargs in calls), 1)

    def test_closed_original_loads_from_native_history_and_refunds_in_new_session(self):
        self._run_history_refund("pos_revolut_closed_original_refund")

    def test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund(self):
        self._run_history_refund("pos_revolut_unavailable_original_refund")

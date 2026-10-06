"""Native browser selection and completion of negative-quantity adjustments."""
from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestNativeAdjustmentBrowser(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    ORDER_ID = TestRevolutVerifiedCheckout.ORDER_ID
    INTENT_ID = TestRevolutVerifiedCheckout.INTENT_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    REFUND_ID = TestRevolutVerifiedCheckout.REFUND_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout
    _response = TestRevolutVerifiedCheckout._response
    _run_full_refund = TestRevolutVerifiedCheckout._run_full_refund

    def _adjustment_product(self):
        return self.env["product.product"].create({
            "name": "Return adjustment", "available_in_pos": True,
            "list_price": 1, "taxes_id": [Command.clear()],
        })

    def test_browser_selects_and_completes_negative_quantity_adjustment(self):
        adjustment = self._adjustment_product()
        calls = self._run_full_refund("pos_revolut_negative_quantity_adjustment", amount_minor=1134)
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refund), 1)
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.amount_minor, 1134)
        self.assertEqual(refund.original_order_id.amount_total, 11.34)
        self.assertEqual(refund.pos_order_id.state, "paid")
        self.assertEqual(refund.pos_order_id.amount_total, -11.34)
        self.assertEqual(refund.pos_payment_id.amount, -11.34)
        self.assertEqual(refund.pos_payment_id.transaction_id, self.REFUND_ID)
        returned = refund.pos_order_id.lines.filtered(lambda line: line.product_id == adjustment)
        self.assertEqual(returned.qty, 1)
        self.assertEqual(returned.refunded_orderline_id.qty, -1)
        self.assertEqual(returned.price_unit, 1)
        self.assertEqual(returned.discount, returned.refunded_orderline_id.discount)
        self.assertEqual(returned.tax_ids, returned.refunded_orderline_id.tax_ids)
        self.assertEqual(returned.refunded_orderline_id.refunded_qty, -1)
        self.assertEqual(len([call for call in calls if call[0] == "POST" and call[1].endswith("/refund")]), 1)

    def test_browser_completes_remaining_adjustment_without_another_refund(self):
        adjustment = self._adjustment_product()
        calls = self._run_full_refund("pos_revolut_remaining_adjustment_zero_return", amount_minor=1134)
        self.env.invalidate_all()
        refunds = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds.amount_minor, 1134)
        original = refunds.original_order_id
        returned = self.env["pos.order.line"].search([
            ("refunded_orderline_id.order_id", "=", original.id), ("product_id", "=", adjustment.id),
        ])
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned.qty, 1)
        self.assertEqual(returned.price_unit, 1)
        self.assertEqual(returned.order_id.state, "paid")
        self.assertEqual(returned.order_id.amount_total, 0)
        self.assertFalse(returned.order_id.payment_ids)
        self.assertFalse(original.has_refundable_lines)
        self.assertEqual(returned.refunded_orderline_id.refunded_qty, -1)
        self.assertEqual(len([call for call in calls if call[0] == "POST" and call[1].endswith("/refund")]), 1)

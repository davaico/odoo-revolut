"""Native partial and mixed-funding returns preserve their original funding."""
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestNativeRefundCheckout(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    ORDER_ID = TestRevolutVerifiedCheckout.ORDER_ID
    INTENT_ID = TestRevolutVerifiedCheckout.INTENT_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    REFUND_ID = TestRevolutVerifiedCheckout.REFUND_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout
    _response = TestRevolutVerifiedCheckout._response
    _run_full_refund = TestRevolutVerifiedCheckout._run_full_refund

    def _verified_return(self):
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].search([
            ("revolut_order_id", "=", self.REFUND_ID),
        ])
        self.assertEqual(len(refund), 1)
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.pos_order_id.state, "paid")
        self.assertEqual(refund.pos_payment_id.uuid, refund.payment_line_uuid)
        self.assertEqual(refund.pos_payment_id.transaction_id, self.REFUND_ID)
        self.assertEqual(refund.original_operation_id.revolut_payment_id, self.PAYMENT_ID)
        return refund

    def test_native_partial_return_keeps_unreturned_quantity_and_amount(self):
        self._run_full_refund("pos_revolut_partial_refund", refund_minor=617)
        refund = self._verified_return()
        self.assertEqual(refund.amount_minor, 617)
        self.assertEqual(refund.original_operation_id.amount_minor, 1234)
        self.assertEqual(refund.pos_order_id.amount_total, -6.17)
        self.assertEqual(refund.pos_payment_id.amount, -6.17)
        self.assertEqual(refund.pos_order_id.lines.qty, -0.5)
        self.assertEqual(refund.original_order_id.lines.refunded_qty, 0.5)
        self.assertTrue(refund.original_order_id.has_refundable_lines)

    def test_native_mixed_return_restores_cash_and_card_to_original_sources(self):
        self._run_full_refund("pos_revolut_mixed_funding_refund", charge_minor=800, refund_minor=800)
        refund = self._verified_return()
        self.assertEqual(refund.amount_minor, 800)
        self.assertEqual(refund.original_operation_id.amount_minor, 800)
        self.assertEqual(refund.original_order_id.amount_total, 12.34)
        self.assertEqual(refund.pos_order_id.amount_total, -12.34)
        self.assertEqual(refund.pos_order_id.amount_paid, -12.34)
        self.assertEqual(refund.pos_payment_id.amount, -8)
        cash = refund.pos_order_id.payment_ids - refund.pos_payment_id
        self.assertEqual(len(cash), 1)
        self.assertTrue(cash.payment_method_id.is_cash_count)
        self.assertEqual(cash.amount, -4.34)
        self.assertEqual(refund.original_order_id.lines.refunded_qty, 1)

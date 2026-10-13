"""Native cashier-tip rejection feedback and safe undispatched tender removal."""
from unittest.mock import patch

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestOdooTipBrowser(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout

    def test_native_odoo_tip_feedback_preserves_safe_tender_removal(self):
        self._configure_revolut_checkout()
        tip = self.env.ref("point_of_sale.product_product_tip")
        self.assertTrue(tip.active)
        self.assertFalse(tip.available_in_pos)
        self.main_pos_config.write({"iface_tipproduct": True, "tip_product_id": tip.id})
        with patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Rejected Odoo tip must not contact Revolut"),
        ) as provider:
            self.start_pos_tour("pos_revolut_odoo_tip_rejection")
        provider.assert_not_called()
        self.env.invalidate_all()
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([]))
        self.assertFalse(self.env["pos.revolut.refund.operation"].search([]))
        orders = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id),
        ])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.state, "paid")
        self.assertEqual(orders.amount_total, 13.34)
        self.assertEqual(orders.tip_amount, 1)
        self.assertEqual(orders.payment_ids.payment_method_id.name, "Cash")

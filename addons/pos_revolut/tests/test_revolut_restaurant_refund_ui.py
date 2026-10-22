"""Native Restaurant returns retain the original sale's pricing and taxes."""
from unittest.mock import patch

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRestaurantRefundCheckout(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    ORDER_ID = TestRevolutVerifiedCheckout.ORDER_ID
    INTENT_ID = TestRevolutVerifiedCheckout.INTENT_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    REFUND_ID = TestRevolutVerifiedCheckout.REFUND_ID
    _response = TestRevolutVerifiedCheckout._response
    _run_full_refund = TestRevolutVerifiedCheckout._run_full_refund

    def _configure_revolut_checkout(self, include_bank=False):
        company = self.main_pos_config.company_id
        self.default_pricelist, self.original_pricelist = self.env["product.pricelist"].create([
            {"name": name, "currency_id": self.main_pos_config.currency_id.id, "company_id": company.id}
            for name in ("Restaurant default prices A", "Restaurant original prices B")
        ])
        self.default_fiscal, self.original_fiscal = self.env["account.fiscal.position"].create([
            {"name": name, "company_id": company.id}
            for name in ("Restaurant default taxes A", "Restaurant original taxes B")
        ])
        takeout = self.env.ref("pos_revolut.pos_takeout_preset")
        dine_in = self.env.ref("pos_revolut.pos_takein_preset")
        takeout.write({"pricelist_id": self.default_pricelist.id,
                       "fiscal_position_id": self.default_fiscal.id,
                       "use_timing": False, "identification": "none"})
        dine_in.write({"pricelist_id": self.original_pricelist.id,
                       "fiscal_position_id": self.original_fiscal.id,
                       "use_timing": False, "identification": "none"})
        self.customer = self.env["res.partner"].with_company(company).create({
            "name": "Restaurant original policy customer",
            "property_product_pricelist": self.original_pricelist.id,
            "property_account_position_id": self.original_fiscal.id,
        })
        self.main_pos_config.write({
            "module_pos_restaurant": True, "use_presets": True,
            "default_preset_id": takeout.id, "available_preset_ids": [Command.set((takeout | dine_in).ids)],
            "use_pricelist": True, "pricelist_id": self.default_pricelist.id,
            "available_pricelist_ids": [Command.set((self.default_pricelist | self.original_pricelist).ids)],
            "tax_regime_selection": True,
            "fiscal_position_ids": [Command.set((self.default_fiscal | self.original_fiscal).ids)],
        })
        floor = self.env["restaurant.floor"].create({
            "name": "Restaurant refund floor", "pos_config_ids": [Command.link(self.main_pos_config.id)],
        })
        self.env["restaurant.table"].create({"floor_id": floor.id, "table_number": 1, "seats": 2})
        return TestRevolutVerifiedCheckout._configure_revolut_checkout(self, include_bank=True)

    def _assert_original_return_policy(self, with_customer=True):
        self.env.invalidate_all()
        orders = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(orders), 2)
        original = orders.filtered(lambda order: order.amount_total > 0)
        returned = orders.filtered(lambda order: order.amount_total < 0)
        self.assertEqual((original.amount_total, returned.amount_total), (12.34, -12.34))
        if with_customer:
            self.assertEqual(orders.partner_id, self.customer)
        else:
            self.assertFalse(orders.partner_id)
        self.assertEqual(orders.pricelist_id, self.original_pricelist)
        self.assertEqual(orders.fiscal_position_id, self.original_fiscal)
        self.assertEqual(returned.lines.refunded_orderline_id, original.lines)
        self.assertEqual(returned.lines.qty, -1)
        self.assertEqual(original.lines.refunded_qty, 1)
        self.assertEqual(returned.amount_paid, -12.34)
        self.assertNotEqual(returned.pricelist_id, self.main_pos_config.default_preset_id.pricelist_id)
        self.assertNotEqual(returned.fiscal_position_id, self.main_pos_config.default_preset_id.fiscal_position_id)
        return original, returned

    def test_native_bank_return_preserves_original_policy_against_default_sale_preset(self):
        self._configure_revolut_checkout()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_restaurant_bank_return_policy", login="pos_admin")
            provider.assert_not_called()
        original, returned = self._assert_original_return_policy(with_customer=False)
        self.assertEqual((original | returned).payment_ids.payment_method_id, self.bank_payment_method)
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([
            ("pos_session_id", "=", self.main_pos_config.current_session_id.id),
        ]))

    def test_native_revolut_return_preserves_original_policy_and_payment_references(self):
        calls = self._run_full_refund("pos_revolut_restaurant_revolut_return_policy")
        original, returned = self._assert_original_return_policy()
        refund = self.env["pos.revolut.refund.operation"].search([("pos_order_id", "=", returned.id)])
        self.assertEqual(len(refund), 1)
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.original_order_id, original)
        self.assertEqual(refund.original_operation_id.revolut_payment_id, self.PAYMENT_ID)
        self.assertEqual(refund.revolut_order_id, self.REFUND_ID)
        self.assertEqual(refund.pos_payment_id, returned.payment_ids)
        self.assertEqual(returned.payment_ids.transaction_id, self.REFUND_ID)
        self.assertEqual(len([call for call in calls if call[0] == "POST" and (
            call[1].endswith("/api/orders") or call[1].endswith("/payment-intents")
        )]), 2)
        self.assertEqual(len([call for call in calls if call[0] == "POST" and call[1].endswith("/refund")]), 1)

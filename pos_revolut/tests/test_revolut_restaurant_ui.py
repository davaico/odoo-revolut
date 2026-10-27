"""Restaurant cashier workflows through native Community 18 controls."""
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .authorization_fixtures import install_zero_reports
from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantWorkflows(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    ORDER_ID = TestRevolutVerifiedCheckout.ORDER_ID
    INTENT_ID = TestRevolutVerifiedCheckout.INTENT_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID

    def _configure_restaurant(self, include_bank=False):
        self.dine_in = self.env.ref("pos_revolut.pos_takein_preset")
        self.takeout = self.env.ref("pos_revolut.pos_takeout_preset")
        self.fiscal = self.env["account.fiscal.position"].create({
            "name": "Restaurant context fiscal policy", "company_id": self.env.company.id,
        })
        self.dine_in.fiscal_position_id = self.fiscal
        self.main_pos_config.write({
            "module_pos_restaurant": True, "iface_splitbill": True,
            "use_presets": True, "default_preset_id": self.dine_in.id,
            "available_preset_ids": [Command.set((self.dine_in | self.takeout).ids)],
        })
        floor = self.env["restaurant.floor"].create({
            "name": "Restaurant parity", "pos_config_ids": [Command.link(self.main_pos_config.id)],
        })
        self.tables = self.env["restaurant.table"].create([
            {"table_number": number, "floor_id": floor.id, "seats": 2,
             "position_h": 100 + 180 * (number - 1), "position_v": 100,
             "width": 100, "height": 100}
            for number in (1, 2, 3)
        ])
        return TestRevolutVerifiedCheckout._configure_revolut_checkout(self, include_bank=include_bank)

    @staticmethod
    def _response(payload):
        result = Mock(status_code=200)
        result.json.return_value = payload
        return result

    def _provider(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if method == "GET" and url.endswith("/api/terminals"):
            return self._response({"terminals": [{
                "id": self.TERMINAL_ID, "online": True, "operation_mode": "pos",
                "location_id": self.LOCATION_ID,
            }]})
        if method == "POST" and url.endswith("/api/orders"):
            return self._response({"id": self.ORDER_ID})
        if method == "POST" and url.endswith("/payment-intents"):
            return self._response({"id": self.INTENT_ID, "state": "pending"})
        if method == "GET" and "/api/payment-intents/" in url:
            if getattr(self, "pending", False):
                return self._response({"id": self.INTENT_ID, "order_id": self.ORDER_ID,
                                       "state": "pending"})
            return self._response({"id": self.INTENT_ID, "order_id": self.ORDER_ID,
                                   "state": "completed", "payment_id": self.PAYMENT_ID})
        if method == "GET" and "/api/payments/" in url:
            return self._response({"id": self.PAYMENT_ID, "order_id": self.ORDER_ID,
                                   "state": "captured", "amount": 1234,
                                   "currency": self.main_pos_config.currency_id.name})
        raise AssertionError(f"Unexpected Merchant request: {method} {url}")

    def test_cashier_selects_dine_in_context_before_verified_checkout(self):
        method = self._configure_restaurant()
        self.main_pos_config.default_preset_id = self.takeout
        self.calls = []
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=self._provider) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_restaurant_context_checkout")
        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", method.id),
        ])
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.pos_order_id.state, "paid")
        self.assertEqual(operation.pos_order_id.preset_id, self.dine_in)
        self.assertEqual(operation.pos_order_id.fiscal_position_id, self.fiscal)
        self.assertEqual(operation.pos_order_id.table_id.table_number, 1)
        self.assertEqual(operation.pos_order_id.amount_total, 12.34)
        self.assertEqual(operation.pos_payment_id.amount, 12.34)
        self.assertEqual(operation.pos_order_id.tip_amount, 0)
        self.assertEqual(len(operation.pos_order_id.lines), 1)
        posts = [call for call in self.calls if call[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0][2]["json"]["fulfilment_type"], "eat_in")

    def test_unexposed_native_split_merge_and_manual_tenders_keep_sale_context(self):
        self._configure_restaurant(include_bank=True)
        self.main_pos_config.default_preset_id = self.takeout
        self._saved_table_order(self.tables[0], 2)
        destination = self._saved_table_order(self.tables[1], 1)
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_restaurant_unexposed_controls")
            provider.assert_not_called()
        self.env.invalidate_all()
        paid = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(paid), 2)
        self.assertAlmostEqual(sum(paid.mapped("amount_total")), 37.02, places=2)
        self.assertEqual(paid.preset_id, self.dine_in)
        self.assertEqual(paid.fiscal_position_id, self.fiscal)
        self.assertEqual(destination.table_id, self.tables[1])
        self.assertEqual(destination.lines.qty, 2)
        self.assertEqual(destination.amount_total, 24.68)
        self.assertEqual(set(paid.payment_ids.payment_method_id.mapped("type")), {"cash", "bank"})
        self.assertFalse(self.env["pos.revolut.payment.operation"].search([
            ("pos_session_id", "=", self.main_pos_config.current_session_id.id),
        ]))

    def test_native_customer_correction_satisfies_address_preset(self):
        self._configure_restaurant(include_bank=True)
        self.dine_in.identification = "address"
        customer = self.env["res.partner"].create({
            "name": "Restaurant addressed guest", "street2": "Restaurant entrance",
        })
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_restaurant_customer_requirement")
            provider.assert_not_called()
        self.env.invalidate_all()
        paid = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(paid), 1)
        self.assertEqual(paid.partner_id, customer)
        self.assertEqual(paid.preset_id, self.dine_in)
        self.assertEqual(paid.fiscal_position_id, self.fiscal)
        self.assertEqual(paid.amount_total, 12.34)

    def _saved_table_order(self, table, quantity):
        amount = quantity * 12.34
        reference = str(uuid4())
        return self.env["pos.order"].create({
            "uuid": reference, "pos_reference": reference,
            "session_id": self.main_pos_config.current_session_id.id,
            "table_id": table.id, "preset_id": self.dine_in.id,
            "fiscal_position_id": self.fiscal.id,
            "pricelist_id": self.main_pos_config.pricelist_id.id,
            "amount_total": amount, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                "uuid": str(uuid4()), "product_id": self.desk_pad.id, "qty": quantity,
                "price_unit": 12.34, "price_subtotal": amount, "price_subtotal_incl": amount,
                "tax_ids": [Command.clear()],
            })],
        })

    def test_native_split_and_merge_controls_protect_both_exposed_orders(self):
        method = self._configure_restaurant()
        source = self._saved_table_order(self.tables[0], 2)
        destination = self._saved_table_order(self.tables[1], 1)
        self.pending, self.calls = True, []
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=self._provider) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour("pos_revolut_restaurant_native_guards", login="pos_admin")
        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", method.id),
        ])
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.state, "pending")
        self.assertEqual(operation.pos_order_id, source)
        self.assertEqual(source.state, "draft")
        self.assertEqual(source.table_id, self.tables[2])
        self.assertEqual(source.preset_id, self.dine_in)
        self.assertEqual(source.fiscal_position_id, self.fiscal)
        self.assertEqual(source.lines.qty, 2)
        self.assertEqual(source.amount_total, 24.68)
        self.assertEqual(destination.state, "draft")
        self.assertEqual(destination.table_id, self.tables[1])
        self.assertEqual(destination.lines.qty, 1)
        self.assertEqual(destination.amount_total, 12.34)
        self.assertFalse(self.tables.parent_id)
        self.assertEqual(source.payment_ids.uuid, operation.payment_line_uuid)
        self.assertEqual(len([call for call in self.calls if call[0] == "POST"]), 2)

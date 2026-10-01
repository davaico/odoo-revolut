"""Native Restaurant table changes preserve exposed financial ownership."""
import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests.common import tagged


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantAuthority(CommonPosTest):
    def setUp(self):
        super().setUp()
        if self.env["ir.module.module"].search([("name", "=", "pos_restaurant")]).state != "installed":
            self.skipTest("Restaurant table ownership needs pos_restaurant installed")
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.method = self.bank_payment_method.copy({
            "name": "Restaurant authority terminal", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
        })
        self.product = self.env["product.product"].create({
            "name": "Restaurant authorized goods", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })
        tip = self.env["product.product"].create({
            "name": "Restaurant configured terminal tip", "list_price": 0,
            "taxes_id": [Command.clear()],
        })
        preset = self.env.ref("pos_restaurant.pos_takein_preset")
        self.pos_config_usd.write({
            "module_pos_restaurant": True, "payment_method_ids": [Command.link(self.method.id)],
            "auto_validate_terminal_payment": True, "tip_product_id": tip.id,
            "use_presets": True, "default_preset_id": preset.id,
            "available_preset_ids": [Command.link(preset.id)],
        })
        own_floor = self.env["restaurant.floor"].create({
            "name": "Original floor", "pos_config_ids": [Command.link(self.pos_config_usd.id)],
        })
        self.table_a, self.table_b = self.env["restaurant.table"].create([
            {"table_number": 1, "floor_id": own_floor.id, "seats": 2},
            {"table_number": 2, "floor_id": own_floor.id, "seats": 2},
        ])
        foreign_config = self.env["pos.config"].create({"name": "Other Restaurant configuration"})
        foreign_floor = self.env["restaurant.floor"].create({
            "name": "Foreign floor", "pos_config_ids": [Command.link(foreign_config.id)],
        })
        self.table_c = self.env["restaurant.table"].create({
            "table_number": 3, "floor_id": foreign_floor.id, "seats": 2,
        })
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        self.line_uuid = str(uuid4())
        self.order = self.env["pos.order"].create({
            "session_id": self.session.id, "uuid": str(uuid4()), "table_id": self.table_a.id,
            "preset_id": preset.id, "amount_total": 12.34, "amount_tax": 0,
            "amount_paid": 0, "amount_return": 0, "pricelist_id": self.pos_config_usd.pricelist_id.id,
            "lines": [Command.create({
                "product_id": self.product.id, "qty": 1, "price_unit": 12.34,
                "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
                "tax_ids": [Command.clear()],
            })],
            "payment_ids": [Command.create({
                "uuid": self.line_uuid, "payment_method_id": self.method.id,
                "amount": 12.34, "payment_status": "waiting",
            })],
        })
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_TEST_TERMINAL": "test-only"}))

    def test_exposed_direct_table_moves_preserve_original_config_and_operation(self):
        prepared = self.env["pos.order"].revolut_prepare_payment(self.order.id, self.order.uuid, 0, [{
            "uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 12.34,
        }])
        provider_order, provider_intent = str(uuid4()), str(uuid4())

        def response(payload):
            result = Mock(status_code=200)
            result.json.return_value = payload
            return result

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=[
            response({"terminals": [{"id": self.method.revolut_terminal_id, "online": True,
                                     "operation_mode": "pos", "location_id": self.method.revolut_location_id}]}),
            response({"id": provider_order}), response({"id": provider_intent, "state": "pending"}),
        ]) as provider:
            started = self.method.revolut_start_payment(
                self.session.id, self.order.uuid, self.line_uuid, 12.34, self.order.currency_id.id,
                False, False, prepared["authorization_id"], prepared["cart_version"], prepared["tender_revision"],
            )
            self.assertEqual(started["state"], "pending")
            self.assertEqual(sum(call.args[0] == "POST" for call in provider.call_args_list), 2)
            provider.reset_mock(side_effect=True)
            provider.side_effect = AssertionError("Table-only changes must never contact Revolut")
            self.env.invalidate_all()
            operation = self.env["pos.revolut.payment.operation"].browse(started["operation_id"])
            original = (self.order.uuid, self.order.session_id.id, self.order.config_id.id,
                        operation.authorization_id.id, operation.revolut_order_id,
                        operation.revolut_payment_intent_id, operation.financial_snapshot)
            self.order.write({"table_id": self.table_b.id})
            self.assertEqual(self.order.table_id, self.table_b)
            with self.assertRaisesRegex(UserError, "original POS configuration"), self.env.cr.savepoint():
                self.order.write({"table_id": self.table_c.id})
            self.order.invalidate_recordset()
            operation.invalidate_recordset()
            self.assertEqual(self.order.table_id, self.table_b)
            self.assertEqual((self.order.uuid, self.order.session_id.id, self.order.config_id.id,
                              operation.authorization_id.id, operation.revolut_order_id,
                              operation.revolut_payment_intent_id, operation.financial_snapshot), original)
            self.assertEqual(operation.state, "pending")
            provider.assert_not_called()

"""Native Restaurant table changes preserve exposed financial ownership."""
import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_revolut_terminal_tip import TerminalTipFixtures


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantAuthority(TerminalTipFixtures, CommonPosTest):
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
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(self.env.uid)]})
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

    def _select_timed_takeout(self, preset_time=False):
        preset = self.env.ref("pos_restaurant.pos_takeout_preset")
        calendar = self.env["resource.calendar"].create({
            "name": "Restaurant pickup test hours",
            "attendance_ids": [Command.create({
                "name": "Pickup", "dayofweek": str(day), "hour_from": 0,
                "hour_to": 24, "day_period": "morning",
            }) for day in range(7)],
        })
        preset.write({"use_timing": True, "resource_calendar_id": calendar.id})
        self.pos_config_usd.write({"available_preset_ids": [Command.link(preset.id)]})
        self.order.write({"preset_id": preset.id, "table_id": False, "preset_time": preset_time})

    def _prepare(self):
        # RPC-owned cursors see the persisted draft, as after native POS sync.
        self.env.flush_all()
        return self.env["pos.order"].revolut_prepare_payment(self.order.id, self.order.uuid, 0, [{
            "uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 12.34,
        }])

    def _start(self, prepared):
        self.env.flush_all()
        return self.method.revolut_start_payment(
            self.session.id, self.order.uuid, self.line_uuid, 12.34, self.order.currency_id.id,
            False, False, prepared["authorization_id"], prepared["cart_version"], prepared["tender_revision"],
        )

    def test_timed_takeout_requires_pickup_before_preparation(self):
        self._select_timed_takeout()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "select.*time slot"):
                self._prepare()
            provider.assert_not_called()
        checkout = self.env["pos.order"].revolut_checkout_state(self.order.id, self.order.uuid)
        self.assertFalse(checkout["authority"])
        self.assertFalse(self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id))

    def test_timed_takeout_missing_pickup_after_preparation_cannot_dispatch(self):
        self._select_timed_takeout(fields.Datetime.now())
        prepared = self._prepare()
        self.order.write({"preset_time": False})
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=AssertionError("Missing pickup must not contact Revolut")) as provider:
            rejected = self._start(prepared)
            self.assertFalse(rejected["dispatched"])
            self.assertRegex(rejected["message"], "select.*time slot")
            provider.assert_not_called()
        self.assertFalse(self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id))
        self.order.write({"preset_time": fields.Datetime.now()})
        corrected = self._prepare()
        self.assertEqual(corrected["authorization_id"], prepared["authorization_id"])
        self.assertEqual(corrected["cart_version"], prepared["cart_version"])

    def test_captured_takeout_keeps_original_recovery_when_pickup_needs_correction(self):
        self._select_timed_takeout(fields.Datetime.now())
        prepared = self._prepare()
        self.base_minor = self.gross_minor = 1234
        self.tip_minor = 0
        self.provider_order_id, self.provider_intent_id, self.provider_payment_id = (
            str(uuid4()) for _ in range(3)
        )
        self.report_status, self.report_post_count = "completed", 0
        self.csv_content, self.order_payments = None, None
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=self.provider_response) as provider:
            started = self._start(prepared)
            captured = self.method.revolut_poll_payment(
                started["operation_id"], self.order.uuid, self.line_uuid,
            )
            self.assertEqual(captured["state"], "verified")
            self.assertEqual(captured["captured_amount_minor"], 1234)
            capture_fields = ("operation_id", "state", "order_id", "payment_intent_id", "payment_id",
                              "authorization_id", "cart_version", "tender_revision",
                              "captured_amount_minor", "gross_amount_minor")
            original_capture = {name: captured[name] for name in capture_fields}
            self.assertEqual(len([call for call in provider.call_args_list
                                  if call.args[0] == "POST" and "/api/report-runs" not in call.args[1]]), 2)
            # Polling commits capture in an owned cursor. Native edits and reads
            # must reload that committed state, as a subsequent RPC would.
            self.env.invalidate_all()

            # A captured order may lose scheduling during synchronization or
            # need a new pickup time. Its original payment remains recoverable.
            self.order.write({"preset_time": False})
            self.env.flush_all()
            provider.reset_mock()
            found = self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id)
            self.assertEqual({name: found[name] for name in capture_fields}, original_capture)
            missing_slot = self._prepare()
            same_start = self._start(prepared)
            self.assertEqual({name: same_start[name] for name in capture_fields}, original_capture)
            provider.assert_not_called()

            self.order.write({"preset_time": fields.Datetime.now()})
            corrected = self._prepare()
            for result in (missing_slot, corrected):
                for name in ("authorization_id", "cart_version", "tender_revision", "canonical", "tenders"):
                    self.assertEqual(result[name], prepared[name])
            same_start = self._start(corrected)
            self.assertEqual({name: same_start[name] for name in capture_fields}, original_capture)
            found = self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id)
            self.assertEqual({name: found[name] for name in capture_fields}, original_capture)
            provider.assert_not_called()

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

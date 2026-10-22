"""Native Restaurant table changes preserve exposed financial ownership."""
import os
from datetime import timedelta
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_revolut_terminal_tip import TerminalTipFixtures


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantAuthority(TerminalTipFixtures, TestPointOfSaleCommon):
    def setUp(self):
        super().setUp()
        if self.env["ir.module.module"].search([("name", "=", "pos_restaurant")]).state != "installed":
            self.skipTest("Restaurant table ownership needs pos_restaurant installed")
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
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
        preset = self.env.ref("pos_revolut.pos_takein_preset")
        self.pos_config.sudo().write({"revolut_user_ids": [Command.link(self.env.uid)]})
        self.pos_config.write({
            "module_pos_restaurant": True, "payment_method_ids": [Command.link(self.method.id)],
            "auto_validate_terminal_payment": True, "tip_product_id": tip.id,
            "use_presets": True, "default_preset_id": preset.id,
            "available_preset_ids": [Command.link(preset.id)],
        })
        self.shared_config = self.pos_config.copy({"name": "Shared floor second register"})
        own_floor = self.env["restaurant.floor"].create({
            "name": "Original floor", "pos_config_ids": [
                Command.link(self.pos_config.id), Command.link(self.shared_config.id),
            ],
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
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened"})
        self.line_uuid = str(uuid4())
        self.order = self.env["pos.order"].create({
            "session_id": self.session.id, "uuid": str(uuid4()), "table_id": self.table_a.id,
            "preset_id": preset.id, "amount_total": 12.34, "amount_tax": 0,
            "amount_paid": 0, "amount_return": 0, "pricelist_id": self.pos_config.pricelist_id.id,
            "lines": [Command.create({
                "uuid": str(uuid4()),
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
        preset = self.env.ref("pos_revolut.pos_takeout_preset")
        calendar = self.env["resource.calendar"].create({
            "name": "Restaurant pickup test hours",
            "attendance_ids": [Command.create({
                "name": "Pickup", "dayofweek": str(day), "hour_from": 0,
                "hour_to": 24, "day_period": "morning",
            }) for day in range(7)],
        })
        preset.write({"use_timing": True, "resource_calendar_id": calendar.id})
        self.pos_config.write({"available_preset_ids": [Command.link(preset.id)]})
        self.order.write({"preset_id": preset.id, "table_id": False, "preset_time": False})
        if preset_time:
            availability = preset.get_available_slots(self.pos_config.id, self.order.id)
            self.pickup_time = fields.Datetime.to_datetime(next(
                slot["time"] for day in availability["days"] for slot in day["slots"]
            ))
            self.order.write({"preset_time": self.pickup_time})

    def _prepare(self):
        # RPC-owned cursors see the persisted draft, as after native POS sync.
        self.env.flush_all()
        return self.env["pos.order"].revolut_prepare_payment(self.order.id, self.order.uuid, 0, [{
            "uuid": self.line_uuid, "payment_method_id": self.method.id, "amount": 12.34,
        }])

    def test_selected_preset_loads_its_pricelist_and_fiscal_position(self):
        pricelist = self.env["product.pricelist"].create({
            "name": "Dine In preset pricing", "currency_id": self.order.currency_id.id,
        })
        fiscal = self.env["account.fiscal.position"].create({
            "name": "Dine In preset taxes", "company_id": self.order.company_id.id,
        })
        self.order.preset_id.write({
            "pricelist_id": pricelist.id, "fiscal_position_id": fiscal.id,
        })
        self.order.write({"pricelist_id": pricelist.id, "fiscal_position_id": fiscal.id})
        loaded = self.session.load_data([])
        self.assertIn(pricelist.id, [row["id"] for row in loaded["product.pricelist"]["data"]])
        self.assertIn(fiscal.id, [row["id"] for row in loaded["account.fiscal.position"]["data"]])
        self.assertEqual(self._prepare()["canonical"]["total_minor"], 1234)

    def test_unconfigured_fiscal_position_cannot_authorize_restaurant_sale(self):
        fiscal = self.env["account.fiscal.position"].create({
            "name": "Unconfigured Restaurant taxes", "company_id": self.order.company_id.id,
        })
        self.order.fiscal_position_id = fiscal
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "authorized fiscal position"):
                self._prepare()
            provider.assert_not_called()

    def test_disabled_presets_cannot_authorize_restaurant_sale(self):
        self.pos_config.use_presets = False
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "available sale preset"):
                self._prepare()
            provider.assert_not_called()

    def test_name_preset_requires_partner_or_floating_order_name(self):
        self.order.preset_id.identification = "name"
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "customer.*order name"):
                self._prepare()
            self.order.floating_order_name = "Restaurant guest"
            self.assertEqual(self._prepare()["canonical"]["total_minor"], 1234)
            provider.assert_not_called()

    def test_name_preset_accepts_customer_without_address(self):
        self.order.preset_id.identification = "name"
        self.order.partner_id = self.env["res.partner"].create({"name": "Restaurant guest"})
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.assertEqual(self._prepare()["canonical"]["total_minor"], 1234)
            provider.assert_not_called()

    def test_address_preset_requires_customer_with_street_or_street2(self):
        self.order.preset_id.identification = "address"
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "customer.*address"):
                self._prepare()
            self.order.partner_id = self.env["res.partner"].create({"name": "Restaurant guest"})
            with self.assertRaisesRegex(UserError, "customer.*address"):
                self._prepare()
            self.order.partner_id.street2 = "Delivery entrance"
            self.assertEqual(self._prepare()["canonical"]["total_minor"], 1234)
            provider.assert_not_called()

    def test_missing_name_after_preparation_cannot_dispatch(self):
        self.order.preset_id.identification = "name"
        self.order.floating_order_name = "Restaurant guest"
        prepared = self._prepare()
        self.order.floating_order_name = False
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            rejected = self._start(prepared)
            self.assertFalse(rejected["dispatched"])
            self.assertRegex(rejected["message"], "customer.*order name")
            provider.assert_not_called()
        self.assertFalse(self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id))

    def test_missing_address_after_preparation_cannot_dispatch(self):
        self.order.preset_id.identification = "address"
        self.order.partner_id = self.env["res.partner"].create({
            "name": "Restaurant guest", "street": "Restaurant street",
        })
        prepared = self._prepare()
        self.order.partner_id.street = False
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            rejected = self._start(prepared)
            self.assertFalse(rejected["dispatched"])
            self.assertRegex(rejected["message"], "customer.*address")
            provider.assert_not_called()
        self.assertFalse(self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id))

    def test_ordinary_paid_sale_enforces_name_preset(self):
        order = self._unexposed_table_order(self.table_b)
        order.preset_id = self.order.preset_id
        order.preset_id.identification = "name"
        order.write({"amount_paid": 12.34, "payment_ids": [Command.create({
            "uuid": str(uuid4()), "payment_method_id": self.bank_payment_method.id, "amount": 12.34,
        })]})
        with self.assertRaisesRegex(UserError, "customer.*order name"), self.env.cr.savepoint():
            order.action_pos_order_paid()
        order.floating_order_name = "Restaurant guest"
        order.action_pos_order_paid()
        self.assertEqual(order.state, "paid")

    def test_ordinary_paid_sale_enforces_address_preset(self):
        order = self._unexposed_table_order(self.table_b)
        order.preset_id = self.order.preset_id
        order.preset_id.identification = "address"
        order.partner_id = self.env["res.partner"].create({"name": "Restaurant guest"})
        order.write({"amount_paid": 12.34, "payment_ids": [Command.create({
            "uuid": str(uuid4()), "payment_method_id": self.bank_payment_method.id, "amount": 12.34,
        })]})
        with self.assertRaisesRegex(UserError, "customer.*address"), self.env.cr.savepoint():
            order.action_pos_order_paid()
        order.partner_id.street = "Restaurant street"
        order.action_pos_order_paid()
        self.assertEqual(order.state, "paid")

    def test_disabled_presets_keep_ordinary_payment_without_identification(self):
        self.pos_config.use_presets = False
        order = self._unexposed_table_order(self.table_b)
        order.preset_id = self.order.preset_id
        order.preset_id.identification = "address"
        order.write({"amount_paid": 12.34, "payment_ids": [Command.create({
            "uuid": str(uuid4()), "payment_method_id": self.bank_payment_method.id, "amount": 12.34,
        })]})
        order.action_pos_order_paid()
        self.assertEqual(order.state, "paid")

    def _start(self, prepared):
        self.env.flush_all()
        return self.method.revolut_start_payment(
            self.session.id, self.order.uuid, self.line_uuid, 12.34, self.order.currency_id.id,
            False, False, prepared["authorization_id"], prepared["cart_version"], prepared["tender_revision"],
        )

    def _unexposed_table_order(self, table, session=None):
        session = session or self.session
        return self.env["pos.order"].create({
            "session_id": session.id, "uuid": str(uuid4()), "table_id": table.id,
            "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "lines": [Command.create({
                "uuid": str(uuid4()), "product_id": self.product.id, "qty": 1,
                "price_unit": 12.34, "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
                "tax_ids": [Command.clear()],
            })],
        })

    def _pending_restaurant_payment(self):
        prepared = self._prepare()

        def response(payload):
            result = Mock(status_code=200)
            result.json.return_value = payload
            return result

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=[
            response({"terminals": [{"id": self.method.revolut_terminal_id, "online": True,
                                     "operation_mode": "pos", "location_id": self.method.revolut_location_id}]}),
            response({"id": str(uuid4())}), response({"id": str(uuid4()), "state": "pending"}),
        ]):
            started = self._start(prepared)
        self.assertEqual(started["state"], "pending")
        self.env.invalidate_all()
        return started

    def _assert_occupied_move_rejected(self, exposed_source, other_session=None):
        other = self._unexposed_table_order(self.table_b, session=other_session)
        started = self._pending_restaurant_payment()
        source, destination = (self.order, other) if exposed_source else (other, self.order)
        orders = source | destination
        before = orders.read(["uuid", "table_id", "session_id", "lines", "payment_ids", "amount_total"])
        values = {"table_id": destination.table_id.id}
        if other_session:
            # Native sync can submit table placement and line commands together.
            values["lines"] = [Command.update(source.lines.id, {"qty": 1})]
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "occupied table"), self.env.cr.savepoint():
                source.write(values)
            self.env.invalidate_all()
            self.assertEqual(orders.read(["uuid", "table_id", "session_id", "lines", "payment_ids", "amount_total"]), before)
            recovered = self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id)
            self.assertEqual(recovered["operation_id"], started["operation_id"])
            self.assertEqual(recovered["state"], "pending")
            provider.assert_not_called()

    def test_exposed_source_cannot_move_into_occupied_table(self):
        self._assert_occupied_move_rejected(exposed_source=True)

    def test_unexposed_source_cannot_move_into_exposed_occupied_table(self):
        self._assert_occupied_move_rejected(exposed_source=False)

    def test_transfer_from_another_session_cannot_merge_into_exposed_table(self):
        session = self.env["pos.session"].create({"config_id": self.shared_config.id})
        session.state = "opened"
        self._assert_occupied_move_rejected(exposed_source=False, other_session=session)

    def test_native_sync_from_another_session_cannot_move_into_exposed_table(self):
        session = self.env["pos.session"].create({"config_id": self.shared_config.id, "state": "opened"})
        source = self._unexposed_table_order(self.table_b, session=session)
        source.date_order = "2099-01-01 12:00:00"
        started = self._pending_restaurant_payment()
        orders = source | self.order
        names = ["uuid", "table_id", "session_id", "lines", "payment_ids", "amount_total"]
        before = orders.read(names)
        payload = {
            "uuid": source.uuid, "session_id": session.id, "state": "draft",
            "table_id": self.table_a.id, "name": source.pos_reference,
            "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [], "payment_ids": [],
        }
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "occupied table"), self.env.cr.savepoint():
                self.env["pos.order"].sync_from_ui([payload])
            self.env.invalidate_all()
            self.assertEqual(orders.read(names), before)
            recovered = self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id)
            self.assertEqual(recovered["operation_id"], started["operation_id"])
            self.assertEqual(recovered["state"], "pending")
            provider.assert_not_called()

    def test_unexposed_orders_retain_native_occupied_table_moves(self):
        other = self._unexposed_table_order(self.table_b)
        before = (self.order.uuid, self.order.lines.ids, self.order.amount_total)
        self.order.write({"table_id": other.table_id.id})
        self.assertEqual(self.order.table_id, self.table_b)
        self.assertEqual((self.order.uuid, self.order.lines.ids, self.order.amount_total), before)

    def _assert_exposed_table_link_rejected(self, child, target):
        started = self._pending_restaurant_payment()
        names = ["uuid", "table_id", "session_id", "lines", "payment_ids", "amount_total"]
        tables = child | target | self.table_a | self.table_b
        orders = self.env["pos.order"].search([("table_id", "in", tables.ids), ("state", "=", "draft")])
        before = orders.read(names)
        links = tables.read(["parent_id"])
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "linking tables"), self.env.cr.savepoint():
                child.write({"parent_id": target.id})
            self.env.invalidate_all()
            self.assertEqual(tables.read(["parent_id"]), links)
            self.assertEqual(orders.read(names), before)
            recovered = self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id)
            self.assertEqual(recovered["operation_id"], started["operation_id"])
            self.assertEqual(recovered["state"], "pending")
            provider.assert_not_called()

    def test_linking_exposed_source_table_is_rejected(self):
        self._unexposed_table_order(self.table_b)
        self._assert_exposed_table_link_rejected(self.table_a, self.table_b)

    def test_linking_into_exposed_destination_table_is_rejected(self):
        self._unexposed_table_order(self.table_b)
        self._assert_exposed_table_link_rejected(self.table_b, self.table_a)

    def test_linking_into_exposed_destination_ancestor_is_rejected(self):
        self.table_b.parent_id = self.table_a
        child = self.env["restaurant.table"].create({
            "table_number": 4, "floor_id": self.table_a.floor_id.id,
        })
        self._unexposed_table_order(child)
        self._assert_exposed_table_link_rejected(child, self.table_b)

    def test_relinking_child_of_exposed_source_ancestor_is_rejected(self):
        self.table_b.parent_id = self.table_a
        target = self.env["restaurant.table"].create({
            "table_number": 4, "floor_id": self.table_a.floor_id.id,
        })
        self._assert_exposed_table_link_rejected(self.table_b, target)

    def test_unexposed_table_links_and_recovery_unlink_remain_allowed(self):
        other = self._unexposed_table_order(self.table_b)
        before = (self.order.uuid, self.order.table_id.id, other.uuid, other.table_id.id)
        self.table_b.write({"parent_id": self.table_a.id})
        self.assertEqual(self.table_b.parent_id, self.table_a)
        self._pending_restaurant_payment()
        self.table_b.write({"parent_id": False})
        self.assertFalse(self.table_b.parent_id)
        self.assertEqual((self.order.uuid, self.order.table_id.id, other.uuid, other.table_id.id), before)

    def test_timed_takeout_requires_pickup_before_preparation(self):
        self._select_timed_takeout()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "select.*time slot"):
                self._prepare()
            provider.assert_not_called()
        checkout = self.env["pos.order"].revolut_checkout_state(self.order.id, self.order.uuid)
        self.assertFalse(checkout["authority"])
        self.assertFalse(self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id))

    def test_unavailable_pickup_cannot_prepare_or_dispatch(self):
        self._select_timed_takeout(fields.Datetime.now())
        for invalid in (self.pickup_time + timedelta(minutes=1),
                        self.pickup_time - timedelta(days=8)):
            self.order.write({"preset_time": invalid})
            with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
                with self.assertRaisesRegex(UserError, "available pickup time slot"):
                    self._prepare()
                provider.assert_not_called()
        self.order.write({"preset_time": self.pickup_time})
        prepared = self._prepare()
        self.order.write({"preset_time": self.pickup_time + timedelta(minutes=1)})
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            rejected = self._start(prepared)
            self.assertFalse(rejected["dispatched"])
            self.assertIn("available pickup time slot", rejected["message"])
            provider.assert_not_called()

    def test_full_pickup_cannot_prepare_or_dispatch(self):
        self._select_timed_takeout(fields.Datetime.now())
        prepared = self._prepare()
        self.env["pos.order"].create([{
            "session_id": self.session.id, "preset_id": self.order.preset_id.id,
            "preset_time": self.pickup_time, "amount_total": 0, "amount_tax": 0,
            "amount_paid": 0, "amount_return": 0,
        } for _ in range(self.order.preset_id.slots_per_interval)])
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            with self.assertRaisesRegex(UserError, "available pickup time slot"):
                self._prepare()
            rejected = self._start(prepared)
            self.assertFalse(rejected["dispatched"])
            self.assertIn("available pickup time slot", rejected["message"])
            provider.assert_not_called()

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
        self.order.write({"preset_time": self.pickup_time})
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

            self.order.write({"preset_time": self.pickup_time})
            corrected = self._prepare()
            for result in (missing_slot, corrected):
                for name in ("authorization_id", "cart_version", "tender_revision", "canonical", "tenders"):
                    self.assertEqual(result[name], prepared[name])
            same_start = self._start(corrected)
            self.assertEqual({name: same_start[name] for name in capture_fields}, original_capture)
            found = self.method.revolut_find_payment(self.order.uuid, self.line_uuid, self.session.id)
            self.assertEqual({name: found[name] for name in capture_fields}, original_capture)
            provider.assert_not_called()

            # Scheduling correction never permits financial changes, and an
            # already captured slot may elapse before the cashier settles it.
            with self.assertRaises(UserError), self.cr.savepoint():
                self.order.lines[0].write({"price_unit": 99})
            self.assertEqual(self.order.state, "draft")
            payment = self.order.payment_ids.filtered(lambda item: item.uuid == self.line_uuid)
            self.assertEqual(payment.payment_status, "done")
            self.assertEqual(payment.transaction_id, self.provider_payment_id)
            with patch("odoo.fields.Datetime.now", return_value=self.pickup_time + timedelta(minutes=1)):
                self.order.action_pos_order_paid()
            self.assertEqual(self.order.state, "paid")
            self.assertEqual(self.order.preset_time, self.pickup_time)
            self.assertEqual(payment.revolut_operation_id.id, started["operation_id"])
            self.assertEqual(payment.revolut_operation_id.pos_order_id, self.order)
            self.assertEqual(payment.revolut_operation_id.pos_payment_id, payment)
            self.assertEqual(payment.transaction_id, self.provider_payment_id)
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

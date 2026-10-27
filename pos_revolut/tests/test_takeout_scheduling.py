"""Calendar slots are operational context, checked before payment admission."""
from datetime import datetime
from unittest.mock import patch

from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import new_test_user, tagged


@tagged("post_install", "-at_install", "pos_revolut_takeout")
class TestTakeoutScheduling(TestPointOfSaleCommon):
    def setUp(self):
        super().setUp()
        self.calendar = self.env["resource.calendar"].create({
            "name": "Pickup calendar", "tz": "Europe/Paris",
            "attendance_ids": [Command.clear(), Command.create({
                "name": "Thursday pickup", "dayofweek": "3", "hour_from": 10,
                "hour_to": 11, "day_period": "morning",
                "date_from": "2026-10-22", "date_to": "2026-10-22",
            })],
        })
        self.preset = self.env["pos.preset"].create({
            "name": "Timed Takeout", "use_timing": True,
            "resource_calendar_id": self.calendar.id, "slots_per_interval": 1,
            "interval_time": 20,
        })
        self.pos_config.write({"use_presets": True, "default_preset_id": self.preset.id,
                               "available_preset_ids": [Command.link(self.preset.id)]})
        self.enterContext(patch("odoo.fields.Datetime.now", return_value=datetime(2026, 10, 21, 12)))

    def _slots(self, order_id=False):
        return self.preset.get_available_slots(self.pos_config.id, order_id)

    def _order(self, **values):
        if not self.pos_config.current_session_id:
            self.pos_config.open_ui()
        return self.env["pos.order"].create({
            "session_id": self.pos_config.current_session_id.id,
            "preset_id": self.preset.id, "amount_total": 0, "amount_tax": 0,
            "amount_paid": 0, "amount_return": 0, **values,
        })

    def test_later_day_uses_calendar_timezone_and_utc_storage(self):
        result = self._slots()
        self.assertEqual(result["timezone"], "Europe/Paris")
        self.assertEqual(len(result["days"]), 7)
        self.assertEqual(result["days"][0], {"date": "2026-10-21", "slots": []})
        self.assertEqual(result["days"][1]["slots"], [
            {"time": "2026-10-22 08:00:00", "label": "10:00"},
            {"time": "2026-10-22 08:20:00", "label": "10:20"},
            {"time": "2026-10-22 08:40:00", "label": "10:40"},
            {"time": "2026-10-22 09:00:00", "label": "11:00"},
        ])
        self.assertTrue(all(not day["slots"] for day in result["days"][2:]))

    def test_capacity_excludes_only_authorized_own_order(self):
        order = self._order(preset_time="2026-10-22 08:00:00")
        self.assertEqual(len(self._slots()["days"][1]["slots"]), 3)
        self.assertEqual(len(self._slots(order.id)["days"][1]["slots"]), 4)
        foreign = self.pos_config.copy({"name": "Other checkout"})
        with self.assertRaises(AccessError):
            self.preset.get_available_slots(foreign.id, order.id)
        order.state = "cancel"
        self.assertEqual(len(self._slots()["days"][1]["slots"]), 4)

    def test_unavailable_or_disabled_preset_is_rejected(self):
        self.pos_config.use_presets = False
        with self.assertRaises(AccessError):
            self._slots()

    def test_non_pos_staff_and_foreign_company_preset_cannot_read_slots(self):
        outsider = new_test_user(self.env, login="pickup_outsider", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.preset.with_user(outsider).get_available_slots(self.pos_config.id)
        foreign_company = self.env["res.company"].create({"name": "Foreign pickup company"})
        self.preset.company_id = foreign_company
        with self.assertRaises(AccessError):
            self._slots()

    def test_two_week_calendar_honours_the_attendance_week(self):
        self.calendar.two_weeks_calendar = True
        week = self.env["resource.calendar.attendance"].get_week_type(datetime(2026, 10, 22))
        self.calendar.attendance_ids.week_type = str(1 - week)
        self.assertTrue(all(not day["slots"] for day in self._slots()["days"]))
        self.calendar.attendance_ids.week_type = str(week)
        self.assertEqual(len(self._slots()["days"][1]["slots"]), 4)

    def test_invalid_configuration_is_rejected(self):
        for values in ({"interval_time": 0}, {"slots_per_interval": 0},
                       {"resource_calendar_id": False}):
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.preset.write(values)

    def test_native_settlement_requires_valid_slot_and_drafts_keep_correction(self):
        order = self._order()
        for instant in (False, "2026-10-22 08:01:00", "2026-10-20 08:00:00"):
            # Saving operational context must stay possible for recovery even
            # when it is not ready for native settlement yet.
            order.preset_time = instant
            self.assertEqual(order.state, "draft")
            with self.assertRaisesRegex(UserError, "available pickup time slot"), self.cr.savepoint():
                order.action_pos_order_paid()
        order.preset_time = "2026-10-22 08:00:00"
        order.action_pos_order_paid()
        self.assertEqual(order.state, "paid")

    def test_native_settlement_rechecks_capacity_without_losing_draft(self):
        order = self._order(preset_time="2026-10-22 08:00:00")
        other = self._order(preset_time="2026-10-22 08:00:00")
        with self.assertRaisesRegex(UserError, "available pickup time slot"), self.cr.savepoint():
            order.action_pos_order_paid()
        self.assertEqual(order.state, "draft")
        other.state = "cancel"
        order.action_pos_order_paid()
        self.assertEqual(order.state, "paid")

    def test_settled_order_can_close_after_pickup_and_calendar_changes(self):
        order = self._order(preset_time="2026-10-22 08:00:00")
        order.action_pos_order_paid()
        self.calendar.attendance_ids.unlink()
        with patch("odoo.fields.Datetime.now", return_value=datetime(2026, 10, 23, 12)):
            order.write({"state": "done"})
        self.assertEqual(order.state, "done")

    def test_dst_slots_are_real_instants_with_calendar_labels(self):
        self.calendar.attendance_ids.unlink()
        self.calendar.write({"attendance_ids": [Command.create({
            "name": "Clock change", "dayofweek": "6", "hour_from": 1,
            "hour_to": 4, "day_period": "morning",
        })]})
        self.preset.interval_time = 60
        slots = self._slots()["days"][4]["slots"]
        self.assertEqual([slot["time"] for slot in slots], [
            "2026-10-24 23:00:00", "2026-10-25 00:00:00",
            "2026-10-25 01:00:00", "2026-10-25 02:00:00", "2026-10-25 03:00:00",
        ])
        self.assertEqual([slot["label"] for slot in slots], ["01:00", "02:00", "02:00", "03:00", "04:00"])
        with patch("odoo.fields.Datetime.now", return_value=datetime(2026, 3, 28, 12)):
            spring_slots = self._slots()["days"][1]["slots"]
        self.assertEqual(spring_slots, [
            {"time": "2026-03-29 00:00:00", "label": "01:00"},
            {"time": "2026-03-29 01:00:00", "label": "03:00"},
            {"time": "2026-03-29 02:00:00", "label": "04:00"},
        ])

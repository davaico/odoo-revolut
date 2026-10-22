"""Configured sale context for Community 18's native Restaurant orders."""
from collections import Counter
from datetime import datetime, time, timedelta

from pytz import UTC, timezone

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression


class PosPreset(models.Model):
    _name = "pos.preset"
    _inherit = ["pos.load.mixin"]
    _description = "Point of Sale Checkout Preset"

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one("res.company", index=True)
    pricelist_id = fields.Many2one("product.pricelist")
    fiscal_position_id = fields.Many2one("account.fiscal.position")
    identification = fields.Selection(
        [("none", "Not required"), ("address", "Address"), ("name", "Name")],
        required=True, default="none",
    )
    is_return = fields.Boolean(default=False)
    use_timing = fields.Boolean(default=False)
    resource_calendar_id = fields.Many2one("resource.calendar", string="Opening Hours")
    calendar_tz = fields.Selection(related="resource_calendar_id.tz", readonly=True)
    revolut_fulfilment = fields.Selection(
        [("eat_in", "Dine In"), ("take_away", "Takeout")],
        compute="_compute_revolut_fulfilment", readonly=True,
    )
    attendance_ids = fields.One2many(
        related="resource_calendar_id.attendance_ids", readonly=False,
    )
    slots_per_interval = fields.Integer(string="Slot Capacity", default=5)
    interval_time = fields.Integer(string="Slot Interval (minutes)", default=20)

    def _compute_revolut_fulfilment(self):
        takein = self.env.ref("pos_revolut.pos_takein_preset", raise_if_not_found=False)
        takeout = self.env.ref("pos_revolut.pos_takeout_preset", raise_if_not_found=False)
        for preset in self:
            preset.revolut_fulfilment = "take_away" if preset == takeout else "eat_in" if preset == takein else False

    @api.constrains("use_timing", "resource_calendar_id", "slots_per_interval", "interval_time")
    def _check_pickup_configuration(self):
        for preset in self:
            if preset.interval_time <= 0 or preset.slots_per_interval <= 0:
                raise ValidationError(_("Pickup slot interval and capacity must be positive."))
            if preset.use_timing and not preset.resource_calendar_id:
                raise ValidationError(_("Select opening hours for a timed checkout preset."))

    def _check_pickup_access(self, config_id, order_id=False):
        self.ensure_one()
        if type(config_id) is not int or not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only POS staff can select pickup slots for a configured register."))
        self.check_access("read")
        config = self.env["pos.config"].browse(config_id).exists()
        config.check_access("read")
        if (not config or config.company_id not in self.env.companies or not config.use_presets
            or self not in (config.available_preset_ids | config.default_preset_id)
            or (self.company_id and self.company_id != config.company_id)
            or not self.use_timing or not self.resource_calendar_id):
            raise AccessError(_("Select an available timed checkout preset for this register."))
        if config.payment_method_ids.filtered(lambda method: method.use_payment_terminal == "revolut"):
            config._check_revolut_register_access()
        order = self.env["pos.order"]
        if order_id:
            if type(order_id) is not int:
                raise AccessError(_("Select the original pickup order."))
            order = order.browse(order_id).exists()
            order.check_access("read")
            if not order or order.config_id != config or order.company_id != config.company_id:
                raise AccessError(_("Select the original pickup order for this register."))
        return config, order

    def _pickup_slots(self, start_date, days=7):
        """Use native attendance intervals, including dated and alternating weeks.

        Iterate real UTC instants so clock changes never create nonexistent local
        times. The calendar timezone owns both opening hours and display labels.
        """
        self.ensure_one()
        zone = timezone(self.calendar_tz)
        start = zone.localize(datetime.combine(start_date, time.min))
        end = zone.localize(datetime.combine(start_date + timedelta(days=days), time.min))
        intervals = self.resource_calendar_id.sudo()._attendance_intervals_batch(start, end)[False]
        step = timedelta(minutes=self.interval_time)
        result = {}
        for opening, closing, _attendance in intervals:
            slot = opening.astimezone(UTC)
            closing = closing.astimezone(UTC)
            # Native preset slots are pickup instants and include closing.
            while slot <= closing:
                local = slot.astimezone(zone)
                if start_date <= local.date() < start_date + timedelta(days=days):
                    result[slot.replace(tzinfo=None)] = (local.date(), local.strftime("%H:%M"))
                slot += step
        return result

    def _pickup_occupancy(self, config, order, start, end):
        # Aggregate counts after access checks: never expose customer/order data
        # or let a caller exclude another register's reservation from capacity.
        domain = [("preset_id", "=", self.id), ("company_id", "=", config.company_id.id),
                  ("state", "!=", "cancel"), ("is_refund", "=", False),
                  ("preset_time", ">=", start), ("preset_time", "<=", end)]
        if order:
            domain.append(("id", "!=", order.id))
        # Odoo 18 groups datetime fields at hour granularity or coarser. Keep
        # the exact instant so several intervals within an hour stay distinct.
        return Counter(self.env["pos.order"].sudo().search(domain).mapped("preset_time"))

    def get_available_slots(self, config_id, order_id=False):
        """Return seven local days of future pickup slots for an authorized POS."""
        config, order = self._check_pickup_access(config_id, order_id)
        now = fields.Datetime.now()
        today = UTC.localize(now).astimezone(timezone(self.calendar_tz)).date()
        slots = self._pickup_slots(today)
        occupied = self._pickup_occupancy(config, order, min(slots), max(slots)) if slots else {}
        days = [{"date": (today + timedelta(days=index)).isoformat(), "slots": []} for index in range(7)]
        for instant, (date, label) in sorted(slots.items()):
            if instant > now and occupied.get(instant, 0) < self.slots_per_interval:
                days[(date - today).days]["slots"].append({"time": fields.Datetime.to_string(instant), "label": label})
        return {"timezone": self.calendar_tz, "days": days}

    def _check_pickup_time(self, order, allow_past=False):
        config, _own_order = self._check_pickup_access(order.config_id.id, order.id)
        instant = order.preset_time
        now = fields.Datetime.now()
        zone = timezone(self.calendar_tz)
        today = UTC.localize(now).astimezone(zone).date()
        date = UTC.localize(instant).astimezone(zone).date()
        if ((instant <= now and not allow_past) or date >= today + timedelta(days=7)
            or instant not in self._pickup_slots(date, days=1)
            or self._pickup_occupancy(config, order, instant, instant).get(instant, 0) >= self.slots_per_interval):
            raise UserError(_("Please select an available pickup time slot; the selected time is unavailable."))

    @api.model
    def _load_pos_data_domain(self, data):
        config = self.env["pos.config"].browse(data["pos.config"]["data"][0]["id"])
        return [("id", "in", (config.available_preset_ids | config.default_preset_id).ids)]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ["name", "company_id", "pricelist_id", "fiscal_position_id",
                "identification", "is_return", "use_timing", "calendar_tz", "revolut_fulfilment", "write_date"]


class PosConfig(models.Model):
    _inherit = "pos.config"

    def _get_available_pricelists(self):
        pricelists = super()._get_available_pricelists()
        if self.use_presets:
            pricelists |= (self.available_preset_ids | self.default_preset_id).pricelist_id
        return pricelists


class AccountFiscalPosition(models.Model):
    _inherit = "account.fiscal.position"

    @api.model
    def _load_pos_data_domain(self, data):
        config = self.env["pos.config"].browse(data["pos.config"]["data"][0]["id"])
        # Native 18 loads only explicitly listed fiscal positions. A configured
        # preset also authorizes its own mapping, as cart preparation checks.
        domain = super()._load_pos_data_domain(data)
        ids = config.default_fiscal_position_id
        if config.use_presets:
            ids |= (config.available_preset_ids | config.default_preset_id).fiscal_position_id
        return expression.OR([domain, [("id", "in", ids.ids)]]) if ids else domain


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def _load_pos_data_fields(self, config_id):
        # Address presets accept either street line, as on the Odoo 19 lane.
        return list(dict.fromkeys(super()._load_pos_data_fields(config_id) + ["street2"]))


class PosSession(models.Model):
    _inherit = "pos.session"

    def _load_pos_data_models(self, config_id):
        return super()._load_pos_data_models(config_id) + ["pos.preset"]


class PosOrder(models.Model):
    _inherit = "pos.order"

    preset_id = fields.Many2one("pos.preset", ondelete="restrict")
    preset_time = fields.Datetime()

    def _revolut_check_preset_identification(self):
        self.ensure_one()
        if not self.config_id.use_presets:
            return
        if self.preset_id.identification == "name" and not (self.partner_id or self.floating_order_name):
            raise UserError(_("Select a customer or an order name before completing this checkout."))
        if self.preset_id.identification == "address" and (
            not self.partner_id or not (self.partner_id.street or self.partner_id.street2)
        ):
            raise UserError(_("Select a customer with an address before completing this checkout."))

    def _revolut_check_preset_timing(self, settling=False):
        self.ensure_one()
        if not self.config_id.use_presets or not self.preset_id.use_timing:
            return
        if not self.preset_time:
            raise UserError(_("Please select an available pickup time slot before starting Revolut payment."))
        # A verified payment remains recoverable even after its pickup time has
        # passed. Native settlement still requires a real, non-overbooked slot.
        captured = settling and self._locked_revolut_operations_for_order(self.company_id.id, self.uuid).filtered(
            lambda operation: operation.state == "verified" and operation.pos_order_id == self)
        self.preset_id._check_pickup_time(self, allow_past=bool(captured))

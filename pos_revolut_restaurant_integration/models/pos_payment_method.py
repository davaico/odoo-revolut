from odoo import _, models
from odoo.exceptions import UserError


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _revolut_payment_fulfilment(self, order):
        if not order.config_id.module_pos_restaurant:
            return super()._revolut_payment_fulfilment(order)
        preset = order.preset_id
        if preset == self.env.ref("pos_restaurant.pos_delivery_preset", raise_if_not_found=False):
            raise UserError(_("Delivery orders are not supported by the Revolut terminal contract."))
        if preset == self.env.ref("pos_restaurant.pos_takeout_preset", raise_if_not_found=False):
            if order.table_id:
                raise UserError(_("A takeaway payment cannot be attached to a table."))
            return "take_away"
        if preset == self.env.ref("pos_restaurant.pos_takein_preset", raise_if_not_found=False):
            return "eat_in"
        raise UserError(_("Select a Dine In or Takeout preset before starting a Revolut payment."))

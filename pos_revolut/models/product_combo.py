"""Explicit quantity options for the maintained Odoo 18 combo contract."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


class ProductCombo(models.Model):
    _inherit = "product.combo"

    qty_free = fields.Integer(string="Included quantity", default=1)
    qty_max = fields.Integer(string="Maximum quantity", default=1)

    @api.constrains("qty_free", "qty_max")
    def _check_revolut_combo_quantities(self):
        for combo in self:
            if combo.qty_max < 1 or combo.qty_free < 0 or combo.qty_free > combo.qty_max:
                raise ValidationError(_("Combo quantities require a positive maximum and an included quantity between zero and that maximum."))

    @api.model
    def _load_pos_data_fields(self, config_id):
        return list(dict.fromkeys(super()._load_pos_data_fields(config_id)
                                  + ["qty_free", "qty_max", "currency_id"]))


class ProductComboItem(models.Model):
    _inherit = "product.combo.item"

    @api.model
    def _load_pos_data_fields(self, config_id):
        return list(dict.fromkeys(super()._load_pos_data_fields(config_id) + ["currency_id"]))


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data):
        # Shared products use the main company's currency. Native loading only
        # includes the POS company/config currencies, which can both differ.
        source_currency_ids = {
            row["currency_id"]
            for model in ("product.combo", "product.combo.item")
            for row in data.get(model, {}).get("data", [])
            if row["currency_id"]
        }
        return expression.OR([
            super()._load_pos_data_domain(data),
            [("id", "in", list(source_currency_ids))],
        ])

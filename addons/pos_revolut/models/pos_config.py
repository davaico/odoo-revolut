from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class PosConfig(models.Model):
    _inherit = "pos.config"

    revolut_user_ids = fields.Many2many(
        "res.users", "pos_revolut_register_user_rel", "config_id", "user_id",
        string="Revolut backend users", groups="base.group_system", copy=False,
        domain="[('share', '=', False)]",
        help="Administrators explicitly grant each backend till user and supervisor access to this register. Employee switching does not change this access.",
    )

    def _check_revolut_grant_management(self, values):
        if "revolut_user_ids" in values and not (
            self.env.su or self.env.user.has_group("base.group_system")
        ):
            raise AccessError(_("Only administrators can grant or revoke Revolut register access."))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_revolut_grant_management(values)
        if "default_revolut_user_ids" in self.env.context:
            self._check_revolut_grant_management({"revolut_user_ids": self.env.context["default_revolut_user_ids"]})
        return super().create(vals_list)

    def write(self, values):
        self._check_revolut_grant_management(values)
        return super().write(values)

    def _check_revolut_register_access(self, session=None, order=None):
        """Check interactive access without imposing session-opener ownership."""
        self.ensure_one()
        if self.env.su:
            return
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale staff can use Revolut registers."))
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(_("The Revolut register company must be active and accessible."))
        if self.env.uid not in self.sudo().revolut_user_ids.ids:
            raise AccessError(_("Ask an administrator to grant your backend user Revolut access to this register."))
        if session is not None:
            session = session.with_env(self.env)
            session.check_access("read")
            if not session or session.config_id != self or session.company_id != self.company_id:
                raise AccessError(_("Recover the original Revolut register and session."))
        if order is not None and order:
            order = order.with_env(self.env)
            order.check_access("read")
            if order.config_id != self or order.company_id != self.company_id:
                raise AccessError(_("The Revolut order belongs to another register."))

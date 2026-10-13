"""Administrator-owned company authority for server-side Merchant credentials."""

import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


REFERENCE_PATTERN = re.compile(r"ODOO_REVOLUT_SECRET_[A-Z0-9_]+\Z")


class PosRevolutMerchantCredential(models.Model):
    _name = "pos.revolut.merchant.credential"
    _description = "Revolut Merchant Credential Authority"

    company_id = fields.Many2one("res.company", required=True, ondelete="restrict", index=True)
    environment = fields.Selection(
        [("sandbox", "Sandbox"), ("production", "Production")], required=True
    )
    secret_reference = fields.Char(required=True, copy=False)

    _unique_reference = models.Constraint(
        "UNIQUE(secret_reference)",
        "A Revolut Merchant credential can be assigned to only one company.",
    )

    @api.constrains("secret_reference")
    def _check_reference(self):
        for credential in self:
            if not REFERENCE_PATTERN.fullmatch(credential.secret_reference or ""):
                raise ValidationError(_("The Revolut credential reference is invalid."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
        return super().create(vals_list)

    def write(self, values):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
        if {"company_id", "environment", "secret_reference"}.intersection(values):
            raise ValidationError(_("Revolut credential authority is immutable. Create a new authority for rotation."))
        return super().write(values)

    def unlink(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
        return super().unlink()

    @api.model
    def _for_snapshot(self, company_id, environment, secret_reference):
        """Resolve only the exact administrator-owned authority, never context."""
        credential = self.sudo().search([
            ("company_id", "=", company_id),
            ("environment", "=", environment),
            ("secret_reference", "=", secret_reference),
        ], limit=1)
        if not credential:
            raise UserError(_(
                "Revolut credential authority is not configured for this company. "
                "Ask a system administrator to verify and authorize the Merchant account."
            ))
        return credential

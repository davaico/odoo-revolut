"""Administrator-owned company authority for server-side Merchant credentials."""

import os
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
    source = fields.Selection(
        [("environment", "Environment variable"), ("database", "Database")],
        required=True, default="environment", copy=False,
    )
    secret_key = fields.Char(copy=False, groups="base.group_system")
    revoked = fields.Boolean(default=False, copy=False)

    _sql_constraints = [
        ("unique_reference",
            "UNIQUE(secret_reference)",
            "A Revolut Merchant credential can be assigned to only one company.",
        ),
    ]

    @api.constrains("secret_reference")
    def _check_reference(self):
        for credential in self:
            if not REFERENCE_PATTERN.fullmatch(credential.secret_reference or ""):
                raise ValidationError(_("The Revolut credential reference is invalid."))

    @api.constrains("source", "secret_key")
    def _check_secret_source(self):
        for credential in self:
            key = credential.secret_key
            if credential.source == "database":
                if not key or not key.strip() or "\r" in key or "\n" in key:
                    raise ValidationError(_("Enter a valid Revolut Merchant key for the database source."))
            elif key:
                raise ValidationError(_("An environment authority cannot store a database key."))

    def _resolve_secret(self):
        """Private server boundary; never expose this method through RPC."""
        self.ensure_one()
        credential = self.sudo()
        if credential.revoked:
            raise UserError(_(
                "The original Revolut credential has been revoked. "
                "Ask a system administrator to reconcile this Merchant account."
            ))
        secret = (credential.secret_key if credential.source == "database"
                  else os.environ.get(credential.secret_reference))
        if not secret:
            raise UserError(_("The Revolut credential is not available on the Odoo server."))
        return secret

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
        return super().create(vals_list)

    def write(self, values):
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
        if {"company_id", "environment", "secret_reference", "source", "secret_key"}.intersection(values):
            raise ValidationError(_("Revolut credential authority is immutable. Create a new authority for rotation."))
        return super().write(values)

    def action_rotate(self):
        self.ensure_one()
        if not self.env.user.has_group("base.group_system"):
            raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
        self.check_access("read")
        return {
            "type": "ir.actions.act_window",
            "name": _("Rotate Revolut Merchant Credential"),
            "res_model": self._name,
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_company_id": self.company_id.id,
                "default_environment": self.environment,
                "default_source": self.source,
            },
        }

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

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosRevolutFinancialOperationMixin(models.AbstractModel):
    _name = "pos.revolut.financial.operation.mixin"
    _description = "Revolut Financial Operation Deployment Guard"

    deployment_blocking = fields.Boolean(
        compute="_compute_deployment_blocking",
        store=True,
        index=True,
        help=(
            "Prevents addon deployment while this financial operation is active or "
            "has an uncertain provider outcome."
        ),
    )
    # Preserve historical stored metadata without capturing new receipt data.
    receipt_merchant_snapshot = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any("receipt_merchant_snapshot" in values for values in vals_list):
            raise ValidationError(_("Legacy merchant evidence cannot be supplied."))
        return super().create(vals_list)

    def write(self, values):
        if "receipt_merchant_snapshot" in values:
            raise ValidationError(_("Legacy merchant evidence is immutable."))
        for operation in self:
            if operation.state == "verified" and "verified_at" in values and (
                fields.Datetime.to_datetime(values["verified_at"]) != operation.verified_at
            ):
                raise ValidationError(_("Financial verification time is immutable."))
        return super().write(values)

    def _revolut_deployment_terminal_states(self):
        """Return states that cannot change the provider's financial position."""
        return set()

    @api.depends("state")
    def _compute_deployment_blocking(self):
        terminal_states = self._revolut_deployment_terminal_states()
        for operation in self:
            operation.deployment_blocking = operation.state not in terminal_states

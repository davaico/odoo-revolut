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
    receipt_merchant_snapshot = fields.Json(readonly=True, copy=False)

    def _receipt_merchant_identity(self):
        self.ensure_one()
        company = self.company_id
        return {
            "name": company.name,
            "vat": company.vat or "",
            "address": ", ".join(filter(None, [company.street, company.street2,
                company.zip, company.city, company.state_id.name, company.country_id.name])),
        }

    @api.model_create_multi
    def create(self, vals_list):
        if any("receipt_merchant_snapshot" in values for values in vals_list):
            raise ValidationError(_("Receipt merchant evidence is captured by the server."))
        records = super().create(vals_list)
        for operation in records.filtered(lambda record: record.state == "verified"):
            super(PosRevolutFinancialOperationMixin, operation).write({
                "receipt_merchant_snapshot": operation._receipt_merchant_identity(),
            })
        return records

    def write(self, values):
        if "receipt_merchant_snapshot" in values:
            raise ValidationError(_("Receipt merchant evidence is immutable."))
        for operation in self:
            if operation.state == "verified" and "verified_at" in values and (
                fields.Datetime.to_datetime(values["verified_at"]) != operation.verified_at
            ):
                raise ValidationError(_("Receipt verification time is immutable."))
        if values.get("state") == "verified":
            for operation in self:
                operation_values = dict(values)
                if operation.state != "verified" and not operation.receipt_merchant_snapshot:
                    operation_values["receipt_merchant_snapshot"] = operation._receipt_merchant_identity()
                super(PosRevolutFinancialOperationMixin, operation).write(operation_values)
            return True
        return super().write(values)

    def _revolut_deployment_terminal_states(self):
        """Return states that cannot change the provider's financial position."""
        return set()

    @api.depends("state")
    def _compute_deployment_blocking(self):
        terminal_states = self._revolut_deployment_terminal_states()
        for operation in self:
            operation.deployment_blocking = operation.state not in terminal_states

from odoo import api, fields, models


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

    def _revolut_deployment_terminal_states(self):
        """Return states that cannot change the provider's financial position."""
        return set()

    @api.depends("state")
    def _compute_deployment_blocking(self):
        terminal_states = self._revolut_deployment_terminal_states()
        for operation in self:
            operation.deployment_blocking = operation.state not in terminal_states

"""Read-only manager evidence for refunds that cannot be safely associated."""

import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL


_REASON_CODE = re.compile(r"[a-z][a-z0-9_]{0,79}\Z")


class PosRevolutExternalRefundEvidence(models.Model):
    _name = "pos.revolut.external.refund.evidence"
    _inherit = ["pos.revolut.register.worklist.mixin"]
    _description = "Revolut External Refund Discovery Evidence"
    _rec_name = "provider_order_id"
    _order = "resolved, id desc"

    credential_id = fields.Many2one(
        "pos.revolut.merchant.credential", required=True, readonly=True,
        ondelete="restrict", index=True,
    )
    company_id = fields.Many2one(related="credential_id.company_id", store=True)
    original_operation_id = fields.Many2one(
        "pos.revolut.payment.operation", readonly=True, ondelete="restrict", index=True,
    )
    original_order_id = fields.Many2one(
        string="Original Sale", related="original_operation_id.pos_order_id",
    )
    provider_order_id = fields.Char(string="Provider Refund / Scan Reference", required=True, readonly=True, index=True)
    related_order_id = fields.Char(string="Reported Original Revolut Order", readonly=True)
    amount_minor = fields.Integer(string="Reported Amount (Minor Units)", readonly=True)
    currency_code = fields.Char(string="Reported Currency", readonly=True)
    reason = fields.Char(string="Investigation Reason", readonly=True)
    resolved = fields.Boolean(readonly=True, default=False, index=True)
    blocks_financial_capacity = fields.Boolean(
        compute="_compute_deployment_blocking", store=True,
        help="Verified unrelated sources and final observations outside integration locations do not block integration capacity.",
    )
    deployment_blocking = fields.Boolean(
        compute="_compute_deployment_blocking", store=True, index=True,
        help="Unresolved evidence that could concern integration payments prevents deployment.",
    )

    _unique_provider_scope = models.Constraint(
        "UNIQUE(credential_id, provider_order_id)",
        "External refund evidence can only be recorded once per Merchant credential.",
    )

    @api.depends("resolved", "reason")
    def _compute_deployment_blocking(self):
        for evidence in self:
            evidence.blocks_financial_capacity = evidence.reason not in {"unrelated_source", "outside_integration_location"}
            evidence.deployment_blocking = not evidence.resolved and evidence.blocks_financial_capacity

    @api.constrains("credential_id", "original_operation_id")
    def _check_original_scope(self):
        for evidence in self:
            source = evidence.original_operation_id
            credential = evidence.credential_id
            if source and (
                source.credential_id != credential
                or source.company_id != credential.company_id
                or source.environment != credential.environment
                or source.secret_reference != credential.secret_reference
            ):
                raise ValidationError(_("External refund evidence must use the original Merchant credential authority."))

    @api.model
    def _sanitized_values(self, values):
        values = dict(values)
        if "reason" in values:
            reason = values["reason"]
            values["reason"] = reason if isinstance(reason, str) and _REASON_CODE.fullmatch(reason) else "invalid_evidence"
        return values

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("External refund evidence is recorded by server reconciliation only."))
        return super().create([self._sanitized_values(values) for values in vals_list])

    def write(self, values):
        if not self.env.su:
            raise AccessError(_("External refund evidence is updated by server reconciliation only."))
        if set(values) - {"reason", "resolved"}:
            raise ValidationError(_("External refund evidence identity and financial details are immutable."))
        return super().write(self._sanitized_values(values))

    def unlink(self):
        raise ValidationError(_("External refund discovery evidence must be preserved."))

    def _revolut_native_visibility_domain(self):
        sources = self.env["pos.revolut.payment.operation"].with_context(active_test=False)
        readable = sources._search([])
        hidden_credentials = sources.sudo()._search(
            Domain("credential_id", "!=", False) & Domain("id", "not in", readable)
        ).subselect(SQL.identifier("pos_revolut_payment_operation", "credential_id"))
        # An unidentified refund may concern any register using this credential.
        # Show it only when all those original financial records are readable.
        return (
            Domain("original_operation_id", "in", readable)
            | (Domain("original_operation_id", "=", False)
               & Domain("credential_id", "not in", hidden_credentials))
        )

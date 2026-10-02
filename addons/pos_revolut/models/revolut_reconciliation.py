from uuid import UUID

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PosRevolutPaymentOperation(models.Model):
    _inherit = "pos.revolut.payment.operation"

    audit_ids = fields.One2many(
        "pos.revolut.reconciliation.audit", "operation_id", readonly=True
    )
    age_minutes = fields.Integer(compute="_compute_age_minutes")
    support_explanation = fields.Char(compute="_compute_support_explanation")
    sanitized_error = fields.Char(compute="_compute_sanitized_error")

    def _compute_age_minutes(self):
        now = fields.Datetime.now()
        for operation in self:
            operation.age_minutes = max(
                0, int((now - (operation.create_date or now)).total_seconds() // 60)
            )

    def _compute_support_explanation(self):
        for operation in self:
            if not operation._has_revolut_credential_authority():
                explanation = _(
                    "The original Merchant credential authority is unverified. "
                    "Keep this attempt blocked and ask a system administrator to "
                    "verify and authorize its original Merchant account."
                )
            elif not operation.revolut_order_id:
                explanation = _(
                    "Revolut order reference missing. Locate the original order "
                    "and its payment intent in the same Merchant account; the "
                    "payment remains blocked until both are verified."
                )
            elif not operation.revolut_payment_intent_id:
                explanation = _(
                    "Payment intent reference missing. Locate the intent for this "
                    "Revolut order; the payment remains blocked."
                )
            elif operation.state == "verified":
                explanation = _("The payment was verified by Revolut.")
            elif operation.retry_safe:
                explanation = _("Revolut confirmed a final unsuccessful outcome.")
            else:
                explanation = _(
                    "The outcome is not established. Keep the order blocked and "
                    "reconcile again after checking Revolut; contact support "
                    "with the references shown here if it remains uncertain."
                )
            operation.support_explanation = explanation

    @api.depends(
        "state", "provider_state", "local_outcome",
        "revolut_order_id", "revolut_payment_intent_id", "credential_id",
    )
    def _compute_sanitized_error(self):
        provider_messages = {
            "terminal_unavailable": _("Configured terminal was unavailable."),
            "terminal_check_failed": _("Terminal eligibility check failed."),
            "declined": _("Revolut reported a declined payment."),
            "failed": _("Revolut reported a failed payment."),
            "cancelled": _("Revolut reported a cancelled payment."),
        }
        for operation in self:
            if not operation._has_revolut_credential_authority():
                message = _("Original Merchant credential authority is unverified.")
            elif operation.local_outcome == "interrupted":
                message = _("Provider communication interrupted.")
            elif operation.local_outcome == "timed_out":
                message = _("POS waiting limit expired.")
            elif operation.provider_state in provider_messages:
                message = provider_messages[operation.provider_state]
            elif not operation.revolut_order_id:
                message = _("Revolut order reference is missing.")
            elif not operation.revolut_payment_intent_id:
                message = _("Revolut payment intent reference is missing.")
            elif operation.state not in {"verified", "declined", "failed", "cancelled"}:
                message = _("Provider outcome not established.")
            else:
                message = False
            operation.sanitized_error = message

    def _has_revolut_credential_authority(self):
        self.ensure_one()
        credential = self.credential_id.sudo()
        return bool(
            credential
            and credential.company_id == self.company_id
            and credential.environment == self.environment
            and credential.secret_reference == self.secret_reference
            and self.payment_method_id.company_id == self.company_id
        )

    def _check_manager_reconciliation_access(self):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(_("Only Point of Sale managers can reconcile payments."))
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(_("This payment belongs to another company."))
        self._check_revolut_register_access()

    def _record_reconciliation_audit(self, action, evidence_reference):
        self.ensure_one()
        self.env["pos.revolut.reconciliation.audit"].sudo().create({
            "operation_id": self.id,
            "company_id": self.company_id.id,
            "actor_id": self.env.uid,
            "action": action,
            "evidence_reference": evidence_reference,
            "resulting_state": self.state,
        })

    def action_revolut_open_association(self):
        self._check_manager_reconciliation_access()
        return {
            "type": "ir.actions.act_window",
            "name": _("Associate Revolut references"),
            "res_model": "pos.revolut.association.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_operation_id": self.id,
                "default_order_reference": self.revolut_order_id,
                "default_intent_reference": self.revolut_payment_intent_id,
            },
        }

    def action_revolut_associate(self, order_reference=False, intent_reference=False):
        self._check_manager_reconciliation_access()
        if self.payment_method_id.company_id != self.company_id:
            raise AccessError(_("The payment method company does not match this attempt."))

        try:
            order_reference = str(UUID(order_reference or self.revolut_order_id))
            intent_reference = (
                str(UUID(intent_reference)) if intent_reference else False
            )
        except (TypeError, ValueError, AttributeError):
            raise UserError(_("Enter valid Revolut UUID references.")) from None
        # The operation's original credential selects the Merchant account.
        # No browser input can select a credential or a company.
        provider_operation = {
            "credential_operation_id": self.id,
            "secret_reference": self.secret_reference,
            "environment": self.environment,
        }
        payment_method = self.payment_method_id.sudo().with_company(self.company_id)
        try:
            order = payment_method._revolut_api_request(
                provider_operation, "GET", f"/api/orders/{order_reference}"
            )
            if intent_reference:
                intent = payment_method._revolut_api_request(
                    provider_operation,
                    "GET",
                    f"/api/payment-intents/{intent_reference}",
                )
        except (requests.RequestException, ValueError):
            raise UserError(_(
                "Revolut evidence could not be retrieved. The attempt remains blocked."
            )) from None

        self._apply_payment_observation("association", {
            "order_reference": order_reference,
            "intent_reference": intent_reference,
            "order": order,
            "intent": intent if intent_reference else None,
        })
        self._record_reconciliation_audit(
            "associate", ", ".join(filter(None, [order_reference, intent_reference]))
        )
        return {"type": "ir.actions.client", "tag": "reload"}

    def action_revolut_reconcile(self):
        self._check_manager_reconciliation_access()
        self.invalidate_recordset()
        polled = False
        if self.state != "verified" and not self.retry_safe:
            if self.revolut_order_id and self.revolut_payment_intent_id:
                self.payment_method_id.revolut_poll_payment(
                    self.id, self.order_uuid, self.payment_line_uuid
                )
                polled = True
            self.invalidate_recordset()
        if polled:
            # Polling commits independently. The request's repeatable-read
            # snapshot predates that update, so use a fresh transaction for
            # the audit and its foreign-key check against the operation.
            with self.env.registry.cursor() as cursor:
                owned_env = api.Environment(
                    cursor, self.env.uid, dict(self.env.context)
                )
                operation = owned_env["pos.revolut.payment.operation"].browse(self.id)
                operation._record_reconciliation_audit("reconcile", ", ".join(
                    filter(None, [operation.revolut_order_id,
                                  operation.revolut_payment_intent_id,
                                  operation.revolut_payment_id])
                ))
                cursor.commit()
        else:
            evidence = ", ".join(filter(None, [
                self.revolut_order_id, self.revolut_payment_intent_id,
                self.revolut_payment_id,
            ]))
            self._record_reconciliation_audit("reconcile", evidence)
        return {"type": "ir.actions.client", "tag": "reload"}


class PosRevolutReconciliationAudit(models.Model):
    _name = "pos.revolut.reconciliation.audit"
    _description = "Revolut Manager Reconciliation Audit"
    _order = "id"

    operation_id = fields.Many2one(
        "pos.revolut.payment.operation", required=True, readonly=True,
        ondelete="restrict", index=True,
    )
    company_id = fields.Many2one("res.company", required=True, readonly=True)
    actor_id = fields.Many2one("res.users", required=True, readonly=True)
    action = fields.Selection(
        [("associate", "Associate reference"), ("reconcile", "Reconcile")],
        required=True, readonly=True,
    )
    evidence_reference = fields.Char(readonly=True)
    resulting_state = fields.Char(required=True, readonly=True)

    def write(self, values):
        raise AccessError(_("Revolut reconciliation audits are immutable."))

    def unlink(self):
        raise AccessError(_("Revolut reconciliation audits cannot be deleted."))


class PosRevolutAssociationWizard(models.TransientModel):
    _name = "pos.revolut.association.wizard"
    _description = "Associate Revolut References"

    operation_id = fields.Many2one(
        "pos.revolut.payment.operation", required=True, readonly=True
    )
    order_reference = fields.Char(string="Revolut Order ID", required=True)
    intent_reference = fields.Char(string="Revolut Payment Intent ID")

    def action_associate(self):
        self.ensure_one()
        self.operation_id.action_revolut_associate(
            self.order_reference, self.intent_reference
        )
        return {"type": "ir.actions.act_window_close"}

"""Separate native accounting for refunds without returned products."""

from contextvars import ContextVar

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_correction_cursor = ContextVar("revolut_financial_correction_cursor", default=None)


class ExternalRefundDisposition(models.Model):
    _inherit = "pos.revolut.refund.operation"

    financial_only_reason = fields.Text(readonly=True)
    financial_correction_move_id = fields.Many2one(
        "account.move", string="Financial Correction", readonly=True,
        ondelete="restrict", copy=False,
    )

    _unique_financial_correction = models.Constraint(
        "UNIQUE(financial_correction_move_id)",
        "A native financial correction can only complete one external refund.",
    )

    def _check_financial_only_source(self):
        self.ensure_one()
        if (self.origin != "external" or self.state != "verified"
                or self.provider_state != "completed" or not self.verified_at
                or not self.revolut_order_id):
            raise UserError(_("Verify the completed external refund before recording its financial correction."))
        if self.pos_order_id or self.pos_payment_id:
            raise UserError(_("This refund already belongs to a product return."))
        if not self.original_order_id:
            raise UserError(_("Match the refund to its original sale first."))

    def action_prepare_financial_correction(self):
        """Open a recoverable native draft; an accountant chooses its correction."""
        self.ensure_one()
        with self.env.cr.savepoint():
            self._lock_native_completion()
            self._check_financial_only_source()
            move = self.financial_correction_move_id
            if not move:
                token = _correction_cursor.set(self.env.cr)
                try:
                    invoice = self.original_order_id.account_move
                    if invoice:
                        if invoice.state != "posted" or invoice.move_type != "out_invoice":
                            raise UserError(_("Post the original customer invoice before preparing its correction."))
                        move = invoice._reverse_moves([{
                            "revolut_external_refund_id": self.id,
                            "date": fields.Date.context_today(self),
                        }], cancel=False)
                    else:
                        move = self.env["account.move"].create({
                            "move_type": "entry", "company_id": self.company_id.id,
                            "journal_id": self.original_order_id.config_id.journal_id.id,
                            "currency_id": self.currency_id.id,
                            "partner_id": self.original_order_id.partner_id.id,
                            "ref": _("External refund %(refund)s for %(sale)s",
                                     refund=self.revolut_order_id,
                                     sale=self.original_order_id.pos_reference),
                            "revolut_external_refund_id": self.id,
                        })
                finally:
                    _correction_cursor.reset(token)
                self._write_native_completion({"financial_correction_move_id": move.id})
            move.check_access("read")
            return {"type": "ir.actions.act_window", "res_model": "account.move",
                    "res_id": move.id, "view_mode": "form", "target": "current"}

    def _check_financial_correction(self, move, *, allow_unlinked=False):
        self.ensure_one()
        move.check_access("read")
        if (move.state != "posted" or move.company_id != self.company_id
                or move.currency_id != self.currency_id
                or move.partner_id != self.original_order_id.partner_id
                or (move.revolut_external_refund_id != self
                    and not (allow_unlinked and not move.revolut_external_refund_id))
                or move.pos_order_ids or move.pos_session_ids
                or move.pos_payment_ids):
            raise UserError(_("Use the posted correction linked to this refund, original sale, company, customer and currency."))
        invoice = self.original_order_id.account_move
        if invoice:
            receivable = move.line_ids.filtered(lambda line: line.account_id.account_type == "asset_receivable")
            if (invoice.state != "posted" or move.move_type != "out_refund" or move.reversed_entry_id != invoice
                    or self.currency_id.compare_amounts(move.amount_total, self.amount)
                    or not receivable
                    or any(line.amount_currency > 0 or line.currency_id != self.currency_id for line in receivable)
                    or self.currency_id.compare_amounts(-sum(receivable.mapped("amount_currency")), self.amount)):
                raise UserError(_("The posted credit note must reverse the original invoice for exactly this refund amount."))
            return
        if move.move_type != "entry" or move.reversed_entry_id:
            raise UserError(_("An uninvoiced sale requires its separate native journal adjustment."))
        outstanding = self.payment_method_id.outstanding_account_id
        settlement = move.line_ids.filtered(lambda line: line.account_id == outstanding)
        other = move.line_ids - settlement
        if not outstanding or not settlement or not other:
            raise UserError(_("Credit the original Revolut payment method's outstanding account in the native adjustment."))
        # Company-currency bookkeeping and original-tender currency must both
        # prove an outgoing reimbursement. A balanced unrelated entry is not
        # sufficient, and a cash account cannot stand in for card settlement.
        company_amount = self.currency_id._convert(
            self.amount, self.company_id.currency_id, self.company_id, move.date,
        )
        if (any(line.balance >= 0 or line.currency_id != self.currency_id for line in settlement)
                or any(line.balance <= 0 or line.currency_id != self.currency_id for line in other)
                or self.company_id.currency_id.compare_amounts(-sum(settlement.mapped("balance")), company_amount)
                or self.currency_id.compare_amounts(-sum(settlement.mapped("amount_currency")), self.amount)
                or self.currency_id.compare_amounts(sum(other.mapped("amount_currency")), self.amount)):
            raise UserError(_("The native adjustment must record exactly this card refund in its original currency."))

    def action_record_financial_only(self, reason, correction_move_id=None):
        self.ensure_one()
        if not isinstance(reason, str) or not reason.strip():
            raise UserError(_("Explain why no products were returned."))
        with self.env.cr.savepoint():
            self._lock_native_completion()
            self._check_financial_only_source()
            move = self.env["account.move"].browse(
                correction_move_id or self.financial_correction_move_id.id,
            ).exists()
            if not move or (self.financial_correction_move_id and move != self.financial_correction_move_id):
                raise UserError(_("Prepare and post this refund's native correction first."))
            move.check_access("read")
            self.env.cr.execute("SELECT id FROM account_move WHERE id = %s FOR UPDATE", [move.id])
            move.invalidate_recordset()
            if not self.financial_correction_move_id:
                # Native invoice reversal establishes the original sale even
                # when an accountant prepared the separate credit note first.
                # Consolidated session entries cannot prove that relationship.
                if not self.original_order_id.account_move:
                    raise UserError(_("Prepare the original-sale-linked adjustment from this refund first."))
                self._check_financial_correction(move, allow_unlinked=True)
                token = _correction_cursor.set(self.env.cr)
                try:
                    move.write({"revolut_external_refund_id": self.id})
                finally:
                    _correction_cursor.reset(token)
                self._write_native_completion({"financial_correction_move_id": move.id})
            self._check_financial_correction(move)
            if self.native_reconciliation_status == "financial_only":
                if self.financial_only_reason != reason.strip():
                    raise UserError(_("This completed financial-only disposition is immutable."))
                return {"type": "ir.actions.client", "tag": "reload"}
            self._write_native_completion({
                "native_reconciliation_status": "financial_only",
                "financial_only_reason": reason.strip(),
                "financial_correction_move_id": move.id,
                "native_reconciled_by": self.env.uid,
                "native_reconciled_at": fields.Datetime.now(),
            })
        return {"type": "ir.actions.client", "tag": "reload"}


class FinancialCorrectionMove(models.Model):
    _inherit = "account.move"

    revolut_external_refund_id = fields.Many2one(
        "pos.revolut.refund.operation", readonly=True, ondelete="restrict", copy=False,
    )
    revolut_original_order_id = fields.Many2one(
        "pos.order", related="revolut_external_refund_id.original_order_id",
        string="Original POS Sale",
    )

    def _check_completed_revolut_correction(self):
        # Accountants may edit the native draft with accounting permissions
        # without gaining access to the private POS financial worklist.
        refunds = self.sudo().revolut_external_refund_id
        if refunds:
            self.env.cr.execute(
                "UPDATE pos_revolut_refund_operation SET write_date = write_date WHERE id = ANY(%s)",
                [sorted(refunds.ids)],
            )
            refunds.invalidate_recordset()
        if any(refund.native_reconciliation_status == "financial_only" for refund in refunds):
            raise UserError(_("A completed external refund's native correction cannot be altered or cancelled."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get("revolut_external_refund_id") for values in vals_list) and _correction_cursor.get() is not self.env.cr:
            raise ValidationError(_("Prepare the native correction from its external refund."))
        self.browse([
            values["reversed_entry_id"] for values in vals_list if values.get("reversed_entry_id")
        ])._check_completed_revolut_correction()
        return super().create(vals_list)

    def write(self, values):
        if "revolut_external_refund_id" in values:
            if _correction_cursor.get() is not self.env.cr or self.revolut_external_refund_id:
                raise ValidationError(_("The native correction's refund relationship is immutable."))
        if {"state", "line_ids", "currency_id", "partner_id", "move_type",
                "reversed_entry_id", "journal_id", "company_id", "date",
                "amount_total", "amount_untaxed", "amount_tax", "amount_total_signed",
                "amount_untaxed_signed", "amount_tax_signed"}.intersection(values):
            self._check_completed_revolut_correction()
        return super().write(values)

    def unlink(self):
        if self.revolut_external_refund_id:
            raise UserError(_("Keep the native correction linked to its external refund for review."))
        return super().unlink()

    def _reverse_moves(self, default_values_list=None, cancel=False):
        self._check_completed_revolut_correction()
        return super()._reverse_moves(default_values_list=default_values_list, cancel=cancel)


class FinancialCorrectionLine(models.Model):
    _inherit = "account.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        self.env["account.move"].browse([values.get("move_id") for values in vals_list if values.get("move_id")])._check_completed_revolut_correction()
        return super().create(vals_list)

    def write(self, values):
        if {"move_id", "account_id", "debit", "credit", "balance", "amount_currency",
                "currency_id", "partner_id", "tax_ids", "tax_line_id", "display_type",
                "price_unit", "quantity", "discount"}.intersection(values):
            self.move_id._check_completed_revolut_correction()
            if values.get("move_id"):
                self.env["account.move"].browse(values["move_id"])._check_completed_revolut_correction()
        return super().write(values)

    def unlink(self):
        self.move_id._check_completed_revolut_correction()
        return super().unlink()

"""Product confirmation and separate accounting from the shared refund list."""
from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class ExternalRefundWizard(models.TransientModel):
    _name = "pos.revolut.external.refund.wizard"
    _description = "Complete an external Revolut refund"

    refund_id = fields.Many2one("pos.revolut.refund.operation", required=True, readonly=True)
    original_order_id = fields.Many2one(related="refund_id.original_order_id")
    currency_id = fields.Many2one(related="refund_id.currency_id")
    amount = fields.Monetary(related="refund_id.amount")
    disposition = fields.Selection([
        ("products", "Select returned products"),
        ("existing", "Associate an existing native return"),
        ("financial", "No products returned"),
    ], default="products", required=True)
    line_ids = fields.One2many("pos.revolut.external.refund.line", "wizard_id")
    association_line_ids = fields.One2many("pos.revolut.external.refund.association.line", "wizard_id")
    return_order_id = fields.Many2one("pos.order", string="Existing native return")
    payment_id = fields.Many2one("pos.payment", string="Existing card reimbursement")
    base_amount = fields.Monetary(string="Product/base reimbursement")
    tip_amount = fields.Monetary(string="Terminal tip reimbursement")
    requires_components = fields.Boolean(readonly=True)
    reason = fields.Text(string="Reason no products were returned")
    correction_move_id = fields.Many2one("account.move", string="Posted native correction")

    def action_prepare(self):
        self.ensure_one()
        refund = self.refund_id
        if self.disposition == "financial":
            if not self.reason or not self.reason.strip():
                raise UserError(_("Explain why no products were returned."))
            if self.correction_move_id:
                return refund.action_record_financial_only(self.reason, self.correction_move_id.id)
            return refund.action_prepare_financial_correction()
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        components = {
            "base_amount_minor": normalize(self.currency_id, self.base_amount)[1],
            "tip_amount_minor": normalize(self.currency_id, self.tip_amount)[1],
        } if self.requires_components else {}
        if self.disposition == "existing":
            if not self.return_order_id:
                raise UserError(_("Select the existing native return and its card reimbursement."))
            lines = self.association_line_ids
            if not lines or refund not in lines.refund_id:
                raise UserError(_("Include this refund and every external reimbursement belonging to the existing return."))
            if any(not line.refund_id or not line.payment_id for line in lines):
                raise UserError(_("Select each external refund and its exact existing card reimbursement."))
            if len(lines.refund_id) != len(lines) or len(lines.payment_id) != len(lines):
                raise UserError(_("Select each refund and reimbursement payment only once."))
            return lines.refund_id.action_associate_native_return(self.return_order_id.id, [
                {"refund_id": line.refund_id.id, "payment_id": line.payment_id.id, **({
                    "base_amount_minor": normalize(line.currency_id, line.base_amount)[1],
                    "tip_amount_minor": normalize(line.currency_id, line.tip_amount)[1],
                } if line.requires_components else {})}
                for line in lines
            ])
        return refund.action_prepare_native_return([
            {"original_line_id": line.original_line_id.id, "quantity": line.quantity,
             "lot_names": [name.strip() for name in (line.lot_names or "").splitlines() if name.strip()]}
            for line in self.line_ids if line.quantity
        ], **components)


class ExternalRefundLine(models.TransientModel):
    _name = "pos.revolut.external.refund.line"
    _description = "Confirm returned original products"

    wizard_id = fields.Many2one("pos.revolut.external.refund.wizard", required=True, ondelete="cascade")
    original_line_id = fields.Many2one("pos.order.line", required=True, readonly=True)
    product_id = fields.Many2one(related="original_line_id.product_id")
    purchased_quantity = fields.Float(related="original_line_id.qty")
    returned_quantity = fields.Float(related="original_line_id.refunded_qty")
    currency_id = fields.Many2one(related="original_line_id.currency_id")
    original_amount = fields.Monetary(related="original_line_id.price_subtotal_incl")
    quantity = fields.Float(string="Quantity returned now", digits="Product Unit")
    lot_names = fields.Text(string="Original lot / serial names (one per line)")


class ExternalRefundAssociationLine(models.TransientModel):
    _name = "pos.revolut.external.refund.association.line"
    _description = "Associate an external refund with its existing card reimbursement"

    wizard_id = fields.Many2one("pos.revolut.external.refund.wizard", required=True, ondelete="cascade")
    refund_id = fields.Many2one("pos.revolut.refund.operation", required=True, string="External refund")
    payment_id = fields.Many2one("pos.payment", string="Existing card reimbursement")
    payment_method_id = fields.Many2one(related="refund_id.payment_method_id")
    currency_id = fields.Many2one(related="refund_id.currency_id")
    amount = fields.Monetary(related="refund_id.amount")
    requires_components = fields.Boolean(compute="_compute_requires_components")
    base_amount = fields.Monetary(string="Product/base reimbursement")
    tip_amount = fields.Monetary(string="Terminal tip reimbursement")

    @api.depends("refund_id.original_operation_id.terminal_tip_minor")
    def _compute_requires_components(self):
        for line in self:
            line.requires_components = bool(line.refund_id.original_operation_id.terminal_tip_minor)


class ExternalRefundActions(models.Model):
    _inherit = "pos.revolut.refund.operation"

    def action_open_native_completion(self):
        self.ensure_one()
        self.payment_method_id._check_refund_authority()
        self._check_revolut_register_access()
        if self.origin != "external" or self.state == "failed":
            raise UserError(_("Select a matched external refund requiring native completion."))
        if self.pos_order_id:
            return self.action_prepare_native_return()
        wizard = self.env["pos.revolut.external.refund.wizard"].create({
            "refund_id": self.id,
            "requires_components": bool(self.original_operation_id.terminal_tip_minor),
            "correction_move_id": self.financial_correction_move_id.id or False,
            "disposition": "financial" if self.financial_correction_move_id else "products",
            "association_line_ids": [Command.create({"refund_id": self.id})],
            "line_ids": [Command.create({"original_line_id": line.id})
                         for line in self.original_order_id.lines if line.qty],
        })
        return {"type": "ir.actions.act_window", "res_model": wizard._name,
                "res_id": wizard.id, "view_mode": "form", "target": "new"}

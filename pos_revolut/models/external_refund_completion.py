"""Manager-confirmed native evidence for money already issued by Revolut."""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from uuid import uuid4

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .pos_order import _revolut_mutation
from .return_allocation import ReturnAllocation
from .revolut_refund import PosRevolutRefundOperation as RefundRecord


_NATIVE_FIELDS = {
    "order_uuid", "payment_line_uuid", "financial_snapshot", "return_total_minor",
    "return_allocation", "allocation_explicit", "base_amount_minor", "tip_amount_minor",
    "pos_order_id", "pos_payment_id", "native_reconciliation_status",
    "native_reconciled_by", "native_reconciled_at", "historical_acknowledged_by",
    "historical_acknowledged_at", "financial_only_reason", "financial_correction_move_id",
    "native_lot_snapshot",
}


class ExternalRefundCompletion(models.Model):
    _inherit = "pos.revolut.refund.operation"

    original_purchase_at = fields.Datetime(related="original_order_id.date_order", string="Purchase date")
    provider_initiated_at = fields.Datetime(readonly=True, string="Provider refund initiated at")
    last_provider_observed_at = fields.Datetime(readonly=True, string="Last authoritative reconciliation")
    historical_acknowledged_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    historical_acknowledged_at = fields.Datetime(readonly=True)
    native_lot_snapshot = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        protected = _NATIVE_FIELDS - {
            "order_uuid", "payment_line_uuid", "financial_snapshot", "return_total_minor",
            "return_allocation", "allocation_explicit", "base_amount_minor", "tip_amount_minor",
            "pos_order_id", "pos_payment_id", "native_reconciliation_status",
            "native_reconciled_by", "native_reconciled_at",
        }
        if any(any(values.get(name) for name in protected | {"provider_initiated_at", "last_provider_observed_at"}) for values in vals_list):
            raise ValidationError(_("Native completion evidence is recorded through manager actions."))
        if any(values.get("origin") == "external" and any(values.get(name) for name in (
            "order_uuid", "payment_line_uuid", "financial_snapshot", "pos_order_id", "pos_payment_id",
            "return_allocation", "allocation_explicit", "return_total_minor",
        )) for values in vals_list):
            raise ValidationError(_("External native associations require manager confirmation."))
        return super().create(vals_list)

    def write(self, values):
        if {"historical_acknowledged_by", "historical_acknowledged_at",
            "financial_only_reason", "financial_correction_move_id", "provider_initiated_at", "last_provider_observed_at", "native_lot_snapshot"}.intersection(values):
            raise ValidationError(_("Native completion evidence is recorded through manager actions."))
        return super().write(values)

    def _write_native_completion(self, values):
        self.ensure_one()
        if set(values) - _NATIVE_FIELDS:
            raise ValidationError(_("Only native completion evidence can be recorded here."))
        if self.native_reconciliation_status == "reconciled" and not self.historical_acknowledged_at:
            values = {"historical_acknowledged_by": self.native_reconciled_by.id,
                      "historical_acknowledged_at": self.native_reconciled_at, **values}
        return super(RefundRecord, self.sudo()).write(values)

    def _check_external_native_authority(self):
        self.ensure_one()
        self.payment_method_id._check_refund_authority()
        self._check_revolut_register_access()
        if self.origin != "external" or not self.original_order_id:
            raise UserError(_("Select an external refund matched to an original sale."))

    def _native_action(self):
        return {"type": "ir.actions.act_window", "res_model": "pos.order",
                "res_id": self.pos_order_id.id, "view_mode": "form", "target": "current"}

    def _record_provider_refund_time(self, detail):
        """Store only an authenticated refund detail's explicit, zoned time."""
        if self.origin != "external":
            return
        super(RefundRecord, self.sudo()).write({"last_provider_observed_at": fields.Datetime.now()})
        if self.provider_initiated_at:
            return
        value = detail.get("created_at")
        if not isinstance(value, str) or len(value) > 80:
            return
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return
        except ValueError:
            return
        super(RefundRecord, self.sudo()).write({"provider_initiated_at": parsed.astimezone(timezone.utc).replace(tzinfo=None)})

    def _check_selected_lots(self, original_line, quantity, lot_names, return_order=None):
        tracking = original_line.product_id.tracking
        if tracking == "none":
            if lot_names:
                raise UserError(_("Untracked products do not require lot details."))
            return
        if (not isinstance(lot_names, list) or not lot_names
                or any(not isinstance(name, str) for name in lot_names)
                or len(set(lot_names)) != len(lot_names)
                or not set(lot_names).issubset(set(original_line.pack_lot_ids.mapped("lot_name")))):
            raise UserError(_("Select valid original lot or serial details for every tracked product."))
        if tracking == "serial" and (quantity != quantity.to_integral_value() or len(lot_names) != quantity):
            raise UserError(_("Select one original serial number per returned unit."))
        if tracking == "lot" and len(lot_names) != 1:
            raise UserError(_("Select one original lot for this return line."))
        if tracking == "serial":
            previous = original_line.refund_orderline_ids.filtered(lambda line: line.order_id.state != "cancel" and line.order_id != return_order)
            if set(lot_names).intersection(previous.pack_lot_ids.mapped("lot_name")):
                raise UserError(_("An original serial number is already returned or reserved."))

    def _prepare_native_products(self, selection, session, order_uuid):
        """Use native product/lot helpers only after allocation acquired locks."""
        original = self.original_order_id
        if not isinstance(selection, list) or not selection or len(selection) > 100:
            raise UserError(_("Confirm original products and quantities; the refund amount cannot identify goods."))
        values = original._prepare_refund_values(session)
        values.update(uuid=order_uuid, user_id=self.env.uid, to_invoice=bool(original.account_move),
                      payment_ids=[Command.clear()], lines=[Command.clear()])
        order = original.copy(values)
        selected_ids = set()
        for row in selection:
            try:
                line_id = row["original_line_id"]
                quantity = Decimal(str(row["quantity"]))
                if type(line_id) is not int or not quantity.is_finite() or quantity <= 0 or line_id in selected_ids:
                    raise ValueError()
            except (KeyError, TypeError, ValueError, InvalidOperation):
                raise UserError(_("Select each original product line once with a positive quantity.")) from None
            selected_ids.add(line_id)
            line = original.lines.filtered(lambda item: item.id == line_id)
            if not line:
                raise UserError(_("Selected products must belong to the original sale."))
            names = row.get("lot_names", [])
            self._check_selected_lots(line, quantity, names)
            copied = line._prepare_refund_data(order, [Command.create({"lot_name": name}) for name in names])
            copied.update(qty=float(quantity) * (-1 if line.qty > 0 else 1), uuid=str(uuid4()))
            line.copy(copied)._onchange_amount_line_all()
        order._compute_prices()
        return order

    def action_prepare_native_return(self, selection=None, session_id=None, return_order_id=None,
                                     payment_id=None, base_amount_minor=None, tip_amount_minor=None):
        """Manager projection of one already-issued reimbursement."""
        self.ensure_one()
        with self.env.cr.savepoint(), _revolut_mutation(self.env):
            ReturnAllocation(self.env).associate(self, [{
                "refund_id": self.id, "payment_id": payment_id,
                "base_amount_minor": base_amount_minor, "tip_amount_minor": tip_amount_minor,
            }], return_order_id=return_order_id, selection=selection, session_id=session_id)
            return self._native_action()

    def action_associate_native_return(self, return_order_id, allocations):
        """Bind the complete selected batch in the caller's savepoint."""
        with self.env.cr.savepoint(), _revolut_mutation(self.env):
            ReturnAllocation(self.env).associate(self, allocations, return_order_id=return_order_id,
                                                exact_payments=True)
            return self[0]._native_action()

    def _resume_native_payment(self):
        if self.state == "verified" and self.pos_order_id.state == "draft":
            if self.provider_state != "completed" or not self.verified_at or not self.revolut_order_id:
                raise UserError(_("Authoritative successful refund evidence is required for a negative card tender."))
            self.pos_payment_id.write({"payment_status": "done", "transaction_id": self.revolut_order_id,
                                       "payment_ref_no": self.revolut_order_id})

    def _complete_native_return(self):
        order = self.pos_order_id
        if not order or order.state not in {"paid", "done", "invoiced"}:
            raise UserError(_("Validate the native return before completing its reconciliation."))
        order._check_revolut_order()
        if order.to_invoice and (not order.account_move or order.account_move.state != "posted"):
            raise UserError(_("The native return requires a posted accounting credit note."))
        if order.picking_ids.filtered(lambda picking: picking.state != "done"):
            raise UserError(_("Finish the native stock transfer before marking this return complete."))
        if self.native_reconciliation_status == "native_completed":
            return
        self._write_native_completion({"native_reconciliation_status": "native_completed",
            "native_reconciled_by": self.env.uid, "native_reconciled_at": fields.Datetime.now()})

    def action_validate_native_return(self):
        with self.env.cr.savepoint(), _revolut_mutation(self.env):
            self._check_external_native_authority()
            ReturnAllocation(self.env).acquire_refund_status(self)
            if not self.pos_order_id or self.state != "verified":
                raise UserError(_("Only a verified external refund with a native return can be validated."))
            order = self.pos_order_id
            order.check_access("write")
            if order.state == "draft":
                if order.session_id.state != "opened":
                    raise UserError(_("Open the return's session before validation."))
                self._resume_native_payment()
                order._check_revolut_order()
                order._process_saved_order(False)
            refunds = self.search([( "pos_order_id", "=", order.id), ("origin", "=", "external")])
            for refund in refunds:
                refund._complete_native_return()
            return self._native_action()


class NativeExternalReturn(models.Model):
    _inherit = "pos.order"

    revolut_external_refund_ids = fields.One2many("pos.revolut.refund.operation", "pos_order_id",
        domain=[("origin", "=", "external")], readonly=True, groups="point_of_sale.group_pos_manager")

    @api.depends("name", "pos_reference", "state")
    @api.depends_context("revolut_return_display")
    def _compute_display_name(self):
        super()._compute_display_name()
        if self.env.context.get("revolut_return_display"):
            for order in self:
                if order.state == "draft" and order.name == "/" and order.pos_reference:
                    order.display_name = order.pos_reference

    @api.model
    def _load_pos_data_fields(self, config):
        # Native POS requests an explicit field list, including new addon
        # fields. Manager worklist relations belong only in the backend form.
        names = super()._load_pos_data_fields(config) or list(self._fields)
        return [name for name in names if name != "revolut_external_refund_ids"]

    def _check_revolut_order(self):
        result = super()._check_revolut_order()
        for order in self:
            for refund in order.sudo().revolut_external_refund_ids:
                if (refund.native_lot_snapshot != {str(line.refunded_orderline_id.id): sorted(line.pack_lot_ids.mapped("lot_name")) for line in order.lines}
                        or refund.original_order_id.account_move and not order.to_invoice):
                    raise UserError(_("The native return's confirmed lot details or required invoice correction changed."))
        return result

    def _process_saved_order(self, draft):
        result = super()._process_saved_order(draft)
        if not draft:
            for refund in self.sudo().revolut_external_refund_ids.with_env(self.env):
                refund._complete_native_return()
        return result

    def action_validate_external_native_return(self):
        self.ensure_one()
        refunds = self.revolut_external_refund_ids
        if not refunds:
            raise UserError(_("This order has no associated external refund."))
        return refunds[0].action_validate_native_return()

    def action_continue_external_native_return(self):
        self.ensure_one()
        refunds = self.revolut_external_refund_ids
        if not refunds or self.state != "draft" or self.session_id.state != "opened":
            raise UserError(_("Select an external-refund draft in its open register."))
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            refund._check_revolut_register_access()
        return {"type": "ir.actions.act_url", "target": "self",
                "url": f"/pos/ui/{self.config_id.id}/payment/{self.uuid}"}

    def write(self, values):
        if "to_invoice" not in values:
            return super().write(values)
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self)
            return super().write(values)


class NativeReturnLot(models.Model):
    _inherit = "pos.pack.operation.lot"

    @api.model_create_multi
    def create(self, vals_list):
        with _revolut_mutation(self.env) as mutation:
            lines = self.env["pos.order.line"].browse([
                values["pos_order_line_id"] for values in vals_list if values.get("pos_order_line_id")
            ])
            mutation.watch(lines.order_id)
            records = super().create(vals_list)
            mutation.watch(records.pos_order_line_id.order_id)
            return records

    def write(self, values):
        with _revolut_mutation(self.env) as mutation:
            target = self.env["pos.order.line"].browse(values.get("pos_order_line_id"))
            mutation.watch((self.pos_order_line_id | target).order_id)
            result = super().write(values)
            mutation.watch(self.pos_order_line_id.order_id)
            return result

    def unlink(self):
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_line_id.order_id)
            return super().unlink()

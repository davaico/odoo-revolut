"""Manager-confirmed native evidence for money already issued by Revolut."""
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from contextvars import ContextVar
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
_association_batch = ContextVar("revolut_native_association_batch", default=None)


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

    def _lock_native_completion(self):
        self.ensure_one()
        self.payment_method_id._check_refund_authority()
        self._check_revolut_register_access()
        if self.origin != "external" or not self.original_order_id:
            raise UserError(_("Select an external refund matched to an original sale."))
        # Match native reservation/checkout: session, return identity, original
        # sale, source payment, refund. Updates force stale snapshots to retry.
        session = self.pos_order_id.session_id or self.original_order_id.config_id.current_session_id
        if session:
            self.env.cr.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [session.id])
        if self.order_uuid:
            self.env["pos.revolut.payment.operation"].sudo()._lock_order(self.company_id.id, self.order_uuid)
        self.env.cr.execute("UPDATE pos_order SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [self.original_order_id.id])
        self.env.cr.execute("UPDATE pos_revolut_payment_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [self.original_operation_id.id])
        self.env.cr.execute("UPDATE pos_revolut_refund_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [self.id])
        self.invalidate_recordset()
        return self

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

    def action_prepare_native_return(self, selection=None, session_id=None, return_order_id=None,
                                     payment_id=None, base_amount_minor=None, tip_amount_minor=None):
        """Persist a selected return and bind existing reimbursement, never dispatch."""
        with self.env.cr.savepoint(), _revolut_mutation(self.env):
            self._lock_native_completion()
            if self.state == "failed" or self.native_reconciliation_status == "financial_only" or self.financial_correction_move_id:
                raise UserError(_("This refund cannot be allocated to a product return."))
            if self.pos_order_id:
                if return_order_id and return_order_id != self.pos_order_id.id:
                    raise UserError(_("This refund already belongs to another native return."))
                if payment_id and payment_id != self.pos_payment_id.id:
                    raise UserError(_("This refund already belongs to another native payment."))
                if base_amount_minor is not None and base_amount_minor != self.base_amount_minor or tip_amount_minor is not None and tip_amount_minor != self.tip_amount_minor:
                    raise UserError(_("The confirmed base and terminal tip allocation cannot change."))
                if selection is not None:
                    selected = {row["original_line_id"]: Decimal(str(row["quantity"])) for row in selection}
                    saved = {line.refunded_orderline_id.id: -Decimal(str(line.qty)) for line in self.pos_order_id.lines}
                    if len(selected) != len(selection) or selected != saved:
                        raise UserError(_("Resume the existing return without changing confirmed products or quantities."))
                self._resume_native_payment()
                return self._native_action()
            original = self.original_order_id
            order = self.env["pos.order"].browse(return_order_id).exists() if return_order_id else self.env["pos.order"]
            if return_order_id and not order:
                raise UserError(_("Select an existing native return."))
            session = order.session_id if order else self.env["pos.session"].browse(session_id).exists() if session_id else original.config_id.current_session_id
            if not session or (not order or order.state == "draft") and session.state != "opened":
                raise UserError(_("Open the original register before preparing a native return."))
            session.config_id._check_revolut_register_access(session=session, order=order)
            allocation = ReturnAllocation(self.env)
            if order:
                order.check_access("write" if order.state == "draft" else "read")
                if order.state not in {"draft", "paid", "done", "invoiced"}:
                    raise UserError(_("Select a draft or completed native return."))
                self.env["pos.revolut.payment.operation"].sudo()._lock_order(order.company_id.id, order.uuid)
            else:
                if not isinstance(selection, list) or not selection or len(selection) > 100:
                    raise UserError(_("Confirm original products and quantities; the refund amount cannot identify goods."))
                values = original._prepare_refund_values(session)
                values.update(uuid=str(uuid4()), user_id=self.env.uid, to_invoice=bool(original.account_move),
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
                    copied.update(qty=-float(quantity), uuid=str(uuid4()))
                    line.copy(copied)._onchange_amount_line_all()
                order._compute_prices()
            snapshot = allocation._normalize_return(order._revolut_order_values(), native_order=True)
            for line in order.lines:
                self._check_selected_lots(line.refunded_orderline_id, -Decimal(str(line.qty)), line.pack_lot_ids.mapped("lot_name"), order)
            if allocation._return_original(snapshot, session) != original:
                raise UserError(_("The native return belongs to a different original sale."))
            allocation._lock_original_return(snapshot, original, order.uuid)
            source = allocation._validate_original(snapshot, self.payment_method_id, session, self.amount_minor, self.original_operation_id.id)
            source_base, source_tip, _evidence = allocation._source_components(source)
            if not source_tip and base_amount_minor is None and tip_amount_minor is None:
                base_amount_minor, tip_amount_minor = self.amount_minor, 0
            base, tip, _explicit = allocation._allocation(source, self.amount_minor, base_amount_minor, tip_amount_minor, self.amount_minor)
            related = self.sudo().search([( "original_operation_id", "=", source.id), ("state", "!=", "failed"), ("id", "!=", self.id)])
            if sum(related.mapped("amount_minor")) + self.amount_minor > source._revolut_paid_minor():
                raise UserError(_("Existing financial refunds exceed the original card payment; reconcile their evidence first."))
            known = related.filtered(lambda item: item.origin != "external" or item.allocation_explicit)
            components = [allocation._refund_components(item) for item in known]
            if sum(item[0] for item in components) + base > source_base or sum(item[1] for item in components) + tip > source_tip:
                raise UserError(_("Confirmed refunds exceed the original base or terminal tip capacity."))
            rows = allocation._return_allocation(snapshot, original, self.currency_id, order.uuid)
            total = sum(row["base_minor"] + row["tip_minor"] for row in rows)
            peers = self.sudo().search([( "order_uuid", "=", order.uuid), ("company_id", "=", self.company_id.id), ("state", "!=", "failed")])
            if (sum(peers.mapped("amount_minor")) + self.amount_minor > total
                    or sum(allocation._refund_components(peer)[0] for peer in peers) + base > sum(row["base_minor"] for row in rows)
                    or sum(allocation._refund_components(peer)[1] for peer in peers) + tip > sum(row["tip_minor"] for row in rows)):
                raise UserError(_("External refund allocations exceed the selected native return."))
            payment = order.payment_ids.filtered(lambda item: item.id == payment_id) if payment_id else self.env["pos.payment"]
            if payment_id and not payment:
                raise UserError(_("Select a payment on this native return."))
            if not payment and order.state != "draft":
                raise UserError(_("A completed return requires its exact existing Revolut reimbursement payment."))
            if not payment and order.payment_ids.filtered(lambda item: item.payment_method_id == self.payment_method_id and not item.revolut_refund_operation_id):
                raise UserError(_("Select the existing card reimbursement explicitly; do not duplicate its payment line."))
            if payment:
                if (payment.payment_method_id != self.payment_method_id
                        or self.env["pos.revolut.payment.operation"].normalize_amount(self.currency_id, payment.amount)[1] != -self.amount_minor
                        or payment.revolut_refund_operation_id or payment.revolut_operation_id
                        or payment.transaction_id not in (False, self.revolut_order_id)
                        or payment.payment_ref_no not in (False, self.revolut_order_id)
                        or order.state != "draft" and (self.state != "verified" or payment.transaction_id != self.revolut_order_id)):
                    raise UserError(_("The native payment is unrelated, ambiguous, or already used by another refund."))
            else:
                payment = self.env["pos.payment"].create({"pos_order_id": order.id, "uuid": str(uuid4()),
                    "payment_method_id": self.payment_method_id.id, "amount": -self.amount,
                    "payment_status": "waiting", "name": fields.Datetime.now()})
            if order.state != "draft" and (not order.revolut_return_allocation or order.revolut_return_allocation != rows):
                # Historical native work is acceptable only when its exact
                # saved totals establish the same unambiguous allocation.
                if self.env["pos.revolut.payment.operation"].normalize_amount(self.currency_id, order.amount_total)[1] != -total:
                    raise UserError(_("The completed native return has incompatible monetary evidence."))
            self._write_native_completion({"order_uuid": order.uuid, "payment_line_uuid": payment.uuid,
                "pos_order_id": order.id, "pos_payment_id": payment.id, "financial_snapshot": snapshot,
                "return_allocation": rows, "return_total_minor": total, "allocation_explicit": True,
                "base_amount_minor": base, "tip_amount_minor": tip, "native_reconciliation_status": "native_draft",
                "native_lot_snapshot": {str(line.refunded_orderline_id.id): sorted(line.pack_lot_ids.mapped("lot_name")) for line in order.lines}})
            if order.state == "draft":
                order._revolut_freeze_return_allocation(rows)
            self._resume_native_payment()
            if _association_batch.get() != (self.env.cr, order.id):
                order._check_revolut_order()
                if order.state != "draft":
                    self._complete_native_return()
            return self._native_action()

    def action_associate_native_return(self, return_order_id, allocations):
        """Associate all already-issued reimbursements atomically, including legacy returns."""
        if (not self or len(self) > 100 or not isinstance(allocations, list)
                or len(allocations) != len(self) or not all(isinstance(row, dict) for row in allocations)
                or {row.get("refund_id") for row in allocations} != set(self.ids)
                or len({row.get("payment_id") for row in allocations}) != len(allocations)
                or any(type(row.get("refund_id")) is not int or type(row.get("payment_id")) is not int for row in allocations)):
            raise UserError(_("Select each external refund and its exact native reimbursement payment once."))
        with self.env.cr.savepoint(), _revolut_mutation(self.env) as mutation:
            for refund in self:
                refund.payment_method_id._check_refund_authority()
                refund._check_revolut_register_access()
            order = self.env["pos.order"].browse(return_order_id).exists()
            if not order:
                raise UserError(_("Select the existing native return."))
            order.check_access("read")
            order.config_id._check_revolut_register_access(session=order.session_id, order=order)
            self.env.cr.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [order.session_id.id])
            self.env["pos.revolut.payment.operation"].sudo()._lock_order(order.company_id.id, order.uuid)
            # No mutation is admitted as a proven association until every
            # selected refund has passed the same single-allocation checks.
            token = _association_batch.set((self.env.cr, order.id))
            try:
                by_id = {row["refund_id"]: row for row in allocations}
                for refund in self.sorted("id"):
                    row = by_id[refund.id]
                    refund.action_prepare_native_return(return_order_id=order.id,
                        payment_id=row["payment_id"], base_amount_minor=row.get("base_amount_minor"),
                        tip_amount_minor=row.get("tip_amount_minor"))
            finally:
                _association_batch.reset(token)
            mutation.watch(order)
            order._check_revolut_order()
            if order.state != "draft":
                for refund in self:
                    refund._complete_native_return()
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
            self._lock_native_completion()
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
            records = super().create(vals_list)
            mutation.watch(records.pos_order_line_id.order_id)
            return records

    def write(self, values):
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_line_id.order_id)
            result = super().write(values)
            mutation.watch(self.pos_order_line_id.order_id)
            return result

    def unlink(self):
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_line_id.order_id)
            return super().unlink()

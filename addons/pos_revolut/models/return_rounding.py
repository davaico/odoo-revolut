"""Project conserved return cents through Odoo's native tax/accounting engine."""
import json
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, ROUND_HALF_UP

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

from .return_allocation import ReturnAllocation


_projection_cursor = ContextVar("revolut_return_projection_cursor", default=None)
_conserved_aml_rounding = ContextVar("revolut_conserved_aml_rounding", default=None)


@contextmanager
def _return_projection(env):
    token = _projection_cursor.set(env.cr)
    try:
        yield
    finally:
        _projection_cursor.reset(token)


def _internal(env):
    return _projection_cursor.get() is env.cr


class PosOrder(models.Model):
    _inherit = "pos.order"

    revolut_return_allocation = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if not _internal(self.env) and any("revolut_return_allocation" in vals for vals in vals_list):
            raise AccessError(_("Return allocation is server-owned."))
        return super().create(vals_list)

    def write(self, values):
        if "revolut_return_allocation" in values and not _internal(self.env):
            raise AccessError(_("Return allocation is server-owned."))
        return super().write(values)

    def _process_order(self, order, existing_order):
        # Native POS serializes loaded readonly fields, including an empty
        # allocation on ordinary sales. Accept an unchanged echo at this
        # transport boundary; create/write still require private authority.
        order = dict(order)
        allocation = order.pop("revolut_return_allocation", None)
        # Odoo 18's related model serializer JSON-encodes object fields.
        # Decode only for comparison; the browser never writes this authority.
        if isinstance(allocation, str):
            try:
                allocation = json.loads(allocation)
            except ValueError as error:
                raise AccessError(_("Return allocation is server-owned.")) from error
        if allocation and (not existing_order or allocation != existing_order.revolut_return_allocation):
            raise AccessError(_("Return allocation is server-owned."))
        return super()._process_order(order, existing_order)

    def _revolut_freeze_return_allocation(self, allocation):
        self.ensure_one()
        if self.revolut_return_allocation and self.revolut_return_allocation != allocation:
            active = self.env["pos.revolut.refund.operation"].sudo().search_count([
                ("company_id", "=", self.company_id.id), ("order_uuid", "=", self.uuid),
                ("order_uuid", "!=", False), ("state", "!=", "failed"),
                ("return_allocation", "!=", False),
            ])
            if self.state in {"paid", "done", "invoiced"} or active:
                raise UserError(_("The accepted return allocation cannot change."))
        from .pos_order import _revolut_mutation
        with _return_projection(self.env), _revolut_mutation(self.env) as mutation:
            # Acquire/read native evidence before clearing its fractional cache.
            mutation.watch(self)
            # Pinned Monetary._filter_not_equal treats a raw browser subtotal
            # as unchanged when its rounded value matches. Clear that cached
            # fraction so an explicit write persists the accepted cents.
            target = -sum(row["base_minor"] + row["tip_minor"] for row in allocation)
            self.invalidate_recordset(["amount_total"])
            self.write({"revolut_return_allocation": allocation,
                        "amount_total": target / (10 ** self.currency_id.decimal_places)})
        self.invalidate_recordset(["revolut_payable_target", "revolut_has_authority_exposure"])
        self.amount_difference = self.amount_paid - self.amount_total

    def _process_saved_order(self, draft):
        # Native synchronization stores browser floating subtotals verbatim.
        # Freeze the locked server allocation and persist its currency total
        # before native finalization, including returns settled only in cash.
        ReturnAllocation(self.env).freeze_native_return(self)
        if self.revolut_return_allocation:
            # Tax projection belongs to native Odoo, after authority is fixed.
            # Its advisory target lookup cannot freeze or recurse into locking.
            self._compute_prices()
        return super()._process_saved_order(draft)

    def _refund(self):
        # Native Odoo selects refundable lines with refunded_qty < qty. Its
        # signed quantities correctly reverse negative sale adjustments once
        # selected, but that comparison omits them from the backend action.
        from .pos_order import _revolut_mutation
        returns = self.env["pos.order"]
        with _revolut_mutation(self.env):
            for original in self:
                order = super(PosOrder, original)._refund()
                if original.payment_ids.filtered(lambda payment:
                        payment.payment_method_id.use_payment_terminal == "revolut"
                        or payment.revolut_operation_id):
                    for line in original.lines.filtered(lambda line:
                            line.qty < 0 and abs(line.refunded_qty) < abs(line.qty)):
                        lots = self.env["pos.pack.operation.lot"]
                        for lot in line.pack_lot_ids:
                            lots |= lot.copy()
                        returned = line.copy(line._prepare_refund_data(order, lots))
                        returned._onchange_amount_line_all()
                    order._compute_prices()
                    order.config_id.notify_synchronisation(order.session_id.id, 0)
                returns |= order
        return returns

    @api.depends("lines.refunded_qty", "lines.qty", "state", "amount_total",
                 "payment_ids.payment_method_id.use_payment_terminal", "payment_ids.revolut_operation_id")
    def _compute_has_refundable_lines(self):
        super()._compute_has_refundable_lines()
        digits = self.env["decimal.precision"].precision_get("Product Unit")
        for original in self.filtered(lambda order: order.state in {"paid", "done", "invoiced"} and order.amount_total > 0):
            if original.payment_ids.filtered(lambda payment:
                    payment.payment_method_id.use_payment_terminal == "revolut" or payment.revolut_operation_id):
                original.has_refundable_lines = original.has_refundable_lines or any(
                    not line.refunded_orderline_id and line.qty < 0
                    and float_compare(abs(line.qty), abs(line.refunded_qty), precision_digits=digits) > 0
                    for line in original.lines)

    def _prepare_tax_base_line_values(self):
        base_lines = super()._prepare_tax_base_line_values()
        for order in self.filtered("revolut_return_allocation"):
            selected = [base for base in base_lines if base["record"].order_id == order]
            if not selected:
                continue
            taxes = self.env["account.tax"]
            taxes._add_tax_details_in_base_lines(selected, order.company_id)
            taxes._round_base_lines_tax_details(selected, order.company_id)
            factor = 10 ** order.currency_id.decimal_places
            for row in order.revolut_return_allocation:
                matching = sorted((base for base in selected
                                   if base["record"].refunded_orderline_id.id == row["original_line_id"]),
                                  key=lambda base: base["record"].uuid)
                quantity = sum((abs(Decimal(str(base["record"].qty))) for base in matching), Decimal(0))
                if quantity != Decimal(row["quantity"]) or not matching:
                    raise UserError(_("The return contents differ from their accepted allocation."))
                gross_minor = row["base_minor"] + row["tip_minor"]
                cumulative = Decimal(0)
                allocated = 0
                for base in matching:
                    cumulative += abs(Decimal(str(base["record"].qty)))
                    cumulative_minor = int((Decimal(gross_minor) * cumulative / quantity).quantize(
                        Decimal(1), rounding=ROUND_HALF_UP))
                    gross = (cumulative_minor - allocated) / factor
                    allocated = cumulative_minor
                    details = base["tax_details"]
                    # Preserve the native tax amounts and their bases. Only
                    # the rounded accounting base absorbs the allocation cent.
                    base["manual_tax_amounts"] = {
                        str(tax["tax"].id): {
                            "tax_amount_currency": tax["tax_amount_currency"]
                            * (-1 if tax["is_reverse_charge"] else 1),
                            "base_amount_currency": tax["base_amount_currency"],
                        } for tax in details["taxes_data"]
                    }
                    tax_amount = sum(tax["tax_amount_currency"] for tax in details["taxes_data"])
                    base["manual_total_excluded_currency"] = order.currency_id.round(gross - tax_amount)
        return base_lines

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_line):
        values = super()._get_invoice_lines_values(line_values, pos_line)
        if pos_line.order_id.revolut_return_allocation and values.get("display_type") != "line_section":
            values["revolut_return_line_id"] = pos_line.id
        elif pos_line._revolut_verified_terminal_tip_minor() and values.get("display_type") != "line_section":
            values["revolut_terminal_tip_line_id"] = pos_line.id
        return values

    def _generate_pos_order_invoice(self):
        with _return_projection(self.env):
            return super()._generate_pos_order_invoice()

    def _prepare_invoice_vals(self):
        values = super()._prepare_invoice_vals()
        allocated = self.filtered("revolut_return_allocation")
        if allocated:
            if allocated != self:
                raise UserError(_("Invoice conserved Revolut returns separately from other orders."))
            # The original collected cash rounding already belongs to the
            # frozen entitlement; an invoice must not round that refund again.
            values["invoice_cash_rounding_id"] = False
            # Native 18 infers the document type from amount_total alone.
            # A zero-value linked return still produces a credit note.
            if self.is_refund and self.currency_id.is_zero(self.amount_total):
                values["move_type"] = "out_refund"
        return values

    def _prepare_aml_values_list_per_nature(self):
        self.ensure_one()
        rounding = self.config_id.rounding_method
        if not (self.revolut_return_allocation and self.config_id.cash_rounding and rounding):
            return super()._prepare_aml_values_list_per_nature()
        # Late invoicing reverses the already posted session sale through this
        # native helper. Its tax bases already contain the accepted cents;
        # rounding them again would unbalance the reversal against payments.
        # Scope this exception to this cursor, currency and rounding record,
        # without changing shared POS configuration or ordinary invoices.
        token = _conserved_aml_rounding.set((self.env.cr, rounding.id, self.currency_id.id))
        try:
            return super()._prepare_aml_values_list_per_nature()
        finally:
            _conserved_aml_rounding.reset(token)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    revolut_return_line_id = fields.Many2one("pos.order.line", readonly=True, copy=False, ondelete="restrict")
    revolut_terminal_tip_line_id = fields.Many2one("pos.order.line", readonly=True, copy=False, ondelete="restrict")

    @api.depends("quantity", "discount", "price_unit", "tax_ids", "currency_id",
                 "revolut_return_line_id", "revolut_terminal_tip_line_id")
    def _compute_totals(self):
        super()._compute_totals()
        for line in self.filtered(lambda item: item.display_type == "product" and (
                item.revolut_return_line_id or item.revolut_terminal_tip_line_id)):
            # Native 18 displays raw tax details here. Manual conserved bases
            # become effective only after native tax rounding, as in posting.
            bases = [line.move_id._prepare_product_base_line_for_taxes_computation(line)]
            taxes = self.env["account.tax"]
            taxes._add_tax_details_in_base_lines(bases, line.company_id)
            taxes._round_base_lines_tax_details(bases, line.company_id)
            line.price_subtotal = bases[0]["tax_details"]["total_excluded_currency"]
            line.price_total = bases[0]["tax_details"]["total_included_currency"]

    @api.model_create_multi
    def create(self, vals_list):
        if not _internal(self.env) and any(
                {"revolut_return_line_id", "revolut_terminal_tip_line_id"}.intersection(vals)
                for vals in vals_list):
            raise AccessError(_("POS accounting authority is server-owned."))
        return super().create(vals_list)

    def write(self, values):
        if {"revolut_return_line_id", "revolut_terminal_tip_line_id"}.intersection(values) and not _internal(self.env):
            raise AccessError(_("POS accounting authority is server-owned."))
        return super().write(values)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        base = super()._prepare_product_base_line_for_taxes_computation(product_line)
        source = product_line.revolut_return_line_id or product_line.revolut_terminal_tip_line_id
        if source:
            # Native 18 copies prices and taxes to invoice lines but omits
            # the conserved manual bases. Restore them from the server-owned
            # POS line for returns and authenticated terminal-selected tips.
            bases = (source.order_id._prepare_tax_base_line_values() if product_line.revolut_return_line_id
                     else source.order_id.lines._prepare_tax_base_line_values())
            authority = next(item for item in bases if item["record"] == source)
            if (product_line.product_id != source.product_id
                    or product_line.price_unit != source.price_unit
                    or product_line.discount != source.discount
                    or abs(product_line.quantity) != abs(source.qty)
                    or product_line.tax_ids != source.tax_ids_after_fiscal_position):
                raise UserError(_("The invoice contents differ from their accepted POS allocation."))
            base["manual_total_excluded_currency"] = authority["manual_total_excluded_currency"]
            base["manual_tax_amounts"] = authority["manual_tax_amounts"]
        return base


class AccountCashRounding(models.Model):
    _inherit = "account.cash.rounding"

    def compute_difference(self, currency, amount):
        scope = _conserved_aml_rounding.get()
        if (scope is not None and scope[0] is self.env.cr
                and scope[1] == self.id and scope[2] == currency.id):
            return 0.0
        return super().compute_difference(currency, amount)

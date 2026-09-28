from contextlib import contextmanager
from contextvars import ContextVar

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .return_allocation import ReturnAllocation


# Odoo applies one2many commands in several nested ORM calls. Validate their
# complete result once, inside the outer savepoint. This scope is held only in
# Python and tied to the cursor; RPC context values cannot enable or forge it.
_active_mutation = ContextVar("revolut_order_mutation", default=None)
_PAYMENT_PROOF_FIELDS = {
    "uuid", "pos_order_id", "company_id", "session_id", "amount", "payment_method_id", "payment_status",
    "transaction_id", "payment_ref_no", "revolut_order_id",
    "revolut_payment_intent_id", "revolut_operation_id", "revolut_refund_operation_id",
}


def _payment_proof(payment):
    return {
        name: payment[name].id if payment._fields[name].type == "many2one" else payment[name]
        for name in _PAYMENT_PROOF_FIELDS
    }


def _order_identity(order):
    return (order.uuid, order.session_id.id, order.config_id.id,
            order.company_id.id, order.currency_id.id, order.currency_rate, order.is_refund)


def _line_contents(line):
    values = {}
    for name in line._REVOLUT_MUTATION_FIELDS:
        field = line._fields[name]
        value = line[name]
        values[name] = value.id if field.type == "many2one" else sorted(value.ids) if field.type == "many2many" else value
    return values


class _RevolutMutation:
    def __init__(self, env):
        self.env = env
        self.order_ids = set()
        self.payment_proofs = {}
        self.identities = {}
        self.settled_returns = {}
        self.return_sources = set()
        self.line_contents = {}
        self.validating = False

    def watch(self, orders):
        if self.validating:
            return
        for order in orders:
            if order.id in self.order_ids:
                continue
            self.order_ids.add(order.id)
            if order._revolut_return_source():
                self.return_sources.add(order.id)
            if order._revolut_has_exposure():
                self.identities[order.id] = _order_identity(order)
            if order.state in {"paid", "done"} and order._revolut_return_source():
                self.identities[order.id] = _order_identity(order)
                self.settled_returns[order.id] = order._revolut_order_values()["lines"]
            self.watch_payments(order.payment_ids)

    def validate(self):
        self.validating = True
        for order in self.env["pos.order"].browse(sorted(self.return_sources)).exists():
            if not order._revolut_return_source():
                raise UserError(_("A Revolut-linked return cannot detach its original sale."))
        for order_id, identity in self.identities.items():
            order = self.env["pos.order"].browse(order_id).exists()
            if not order or _order_identity(order) != identity:
                raise UserError(_("An exposed Revolut order cannot be deleted or reassigned."))
            if order_id in self.settled_returns and (
                order._revolut_order_values()["lines"] != self.settled_returns[order_id]
            ):
                raise UserError(_("Completed Revolut return contents cannot be changed."))
        for payment_id, proof in self.payment_proofs.items():
            payment = self.env["pos.payment"].browse(payment_id).exists()
            if not payment or _payment_proof(payment) != proof:
                raise UserError(_("Verified Revolut payment evidence cannot be changed or detached."))
        for line_id, contents in self.line_contents.items():
            line = self.env["pos.order.line"].browse(line_id).exists()
            if not line or _line_contents(line) != contents:
                raise UserError(_("Exposed Revolut order contents cannot be changed."))
        self.env["pos.order"].browse(sorted(self.order_ids)).exists()._check_revolut_order()

    def watch_payments(self, payments):
        if self.validating:
            return
        for payment in payments:
            if payment.id not in self.payment_proofs and (
                payment.revolut_operation_id or payment.revolut_refund_operation_id
            ):
                self.payment_proofs[payment.id] = _payment_proof(payment)

    def watch_lines(self, lines):
        if not self.validating:
            for line in lines:
                if line.order_id.id in self.identities and line.id not in self.line_contents:
                    self.line_contents[line.id] = _line_contents(line)


@contextmanager
def _revolut_mutation(env):
    current = _active_mutation.get()
    if current is not None and current.env.cr is env.cr:
        yield current
        return
    with env.cr.savepoint():
        mutation = _RevolutMutation(env)
        token = _active_mutation.set(mutation)
        try:
            yield mutation
            mutation.validate()
        finally:
            _active_mutation.reset(token)


class PosPayment(models.Model):
    _inherit = "pos.payment"

    revolut_refund_operation_id = fields.Many2one(
        "pos.revolut.refund.operation", readonly=True, ondelete="restrict", index=True
    )
    revolut_order_id = fields.Char(readonly=True, index=True)
    revolut_payment_intent_id = fields.Char(readonly=True, index=True)
    revolut_operation_id = fields.Many2one(
        "pos.revolut.payment.operation", readonly=True, ondelete="restrict", index=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        with _revolut_mutation(self.env) as mutation:
            payments = super().create(vals_list)
            mutation.watch(payments.pos_order_id)
            return payments

    def write(self, values):
        if not _PAYMENT_PROOF_FIELDS.intersection(values):
            return super().write(values)
        self.check_access("write")
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_id)
            mutation.watch_payments(self)
            result = super().write(values)
            mutation.watch(self.pos_order_id)
            return result

    def unlink(self):
        self.check_access("unlink")
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.pos_order_id)
            if self.filtered(lambda payment: payment.revolut_operation_id or payment.revolut_refund_operation_id):
                raise UserError(_("Verified Revolut payment evidence cannot be deleted."))
            return super().unlink()


class PosOrder(models.Model):
    _inherit = "pos.order"

    _REVOLUT_MUTATION_FIELDS = {
        "uuid", "session_id", "config_id", "company_id", "currency_id", "currency_rate", "date_order",
        "state", "pricelist_id", "fiscal_position_id", "lines", "payment_ids",
        "amount_total", "amount_tax", "amount_paid", "amount_return", "is_refund",
    }

    def _revolut_return_source(self):
        return self.sudo().lines.refunded_orderline_id.order_id.payment_ids.filtered(
            lambda payment: payment.payment_method_id.use_payment_terminal == "revolut"
            or payment.revolut_operation_id
        )

    def _revolut_has_exposure(self):
        self.ensure_one()
        operations = self._locked_revolut_operations_for_order(self.company_id.id, self.uuid)
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", self.company_id.id), ("order_uuid", "=", self.uuid),
            ("state", "!=", "failed"),
        ])
        return bool(operations.filtered(lambda operation: not operation.retry_safe or operation.state == "verified") or refunds)

    def _revolut_order_values(self):
        """Feed the same domain validators from persisted ORM records."""
        self.ensure_one()
        return {
            "uuid": self.uuid, "session_id": self.session_id.id,
            "state": self.state, "amount_total": self.amount_total,
            "is_refund": self.is_refund,
            "pricelist_id": self.pricelist_id.id,
            "fiscal_position_id": self.fiscal_position_id.id,
            "lines": [{
                "uuid": line.uuid, "product_id": line.product_id.id,
                "qty": line.qty, "price_unit": line.price_unit,
                "discount": line.discount, "tax_ids": line.tax_ids.ids,
                "refunded_orderline_id": line.refunded_orderline_id.id,
            } for line in self.lines],
        }

    def _check_revolut_order(self):
        for order in self:
            exposed = order._revolut_has_exposure()
            return_source = order._revolut_return_source()
            has_revolut_payment = any(payment.payment_method_id.use_payment_terminal == "revolut"
                                     for payment in order.payment_ids)
            if (exposed or has_revolut_payment or return_source) and (
                order.company_id != order.session_id.company_id
                or order.config_id != order.session_id.config_id
                or order.currency_id != order.session_id.currency_id
                or order.company_id not in self.env.companies
                or any(line.company_id != order.company_id for line in order.lines)
                or any(payment.company_id != order.company_id or payment.session_id != order.session_id
                       for payment in order.payment_ids)
            ):
                raise UserError(_("The Revolut order company, currency, or POS ownership is invalid."))
            if exposed and order.state == "cancel":
                raise UserError(_("Reconcile the exposed Revolut operation before cancelling this order."))
            if exposed or (
                order.state not in {"draft", "cancel"} and return_source
            ):
                for line in order.lines:
                    if any(order.currency_id.compare_amounts(line[name], amount)
                           for name, amount in line._compute_amount_line_all().items()):
                        raise UserError(_("The Revolut order line totals do not match its financial contents."))
                # Use Odoo's tax engine, including its rounding rules, rather
                # than trusting client totals or duplicating tax arithmetic.
                totals = (order.amount_total, order.amount_tax)
                order._compute_prices()
                if any(order.currency_id.compare_amounts(before, after) for before, after in
                       zip(totals, (order.amount_total, order.amount_tax))):
                    raise UserError(_("The Revolut order totals do not match its financial contents."))
            values = order._revolut_order_values()
            refunds = ReturnAllocation(self.env).validate_settlement(
                values, order, self._revolut_payment_values(values, order)
            )
            operations = order._validate_revolut_settlement(values, order) if refunds is None else self.env["pos.revolut.payment.operation"].browse()
            if operations and order.state in {"paid", "done"} and not order._is_pos_order_paid():
                raise UserError(_("The Revolut order is not fully paid."))
            order._validate_revolut_payment_references(self._revolut_payment_values(values, order))
            order._link_revolut_settlement(operations, refunds)

    def _validate_revolut_payment_references(self, payments):
        """Client-supplied evidence must agree with server-owned operations."""
        self.ensure_one()
        domain = [("company_id", "=", self.company_id.id), ("order_uuid", "=", self.uuid)]
        charges = self.env["pos.revolut.payment.operation"].sudo().search(domain, order="id")
        refunds = self.env["pos.revolut.refund.operation"].sudo().search(domain, order="id")
        by_line = {operation.payment_line_uuid: operation for operation in charges}
        by_line.update({refund.payment_line_uuid: refund for refund in refunds})
        for payment in payments.values():
            operation = by_line.get(payment["uuid"])
            is_refund = operation and operation._name == "pos.revolut.refund.operation"
            expected = {
                "revolut_operation_id": operation.id if operation and not is_refund and operation.state == "verified" else False,
                "revolut_refund_operation_id": operation.id if operation and is_refund and operation.state == "verified" else False,
                "revolut_order_id": operation.revolut_order_id if operation else False,
                "revolut_payment_intent_id": operation.revolut_payment_intent_id if operation and not is_refund else False,
            }
            if operation:
                expected["payment_ref_no"] = operation.revolut_order_id
                expected["transaction_id"] = operation.revolut_order_id if is_refund else operation.revolut_payment_id
                if operation.pos_payment_id and operation.pos_payment_id.id != payment["id"]:
                    raise UserError(_("A Revolut operation already settled another payment record."))
            if any(payment.get(name) and payment[name] != value for name, value in expected.items()):
                raise UserError(_("The POS payment references do not match Revolut verification."))

    @api.model_create_multi
    def create(self, vals_list):
        with _revolut_mutation(self.env) as mutation:
            orders = super().create(vals_list)
            mutation.watch(orders)
            return orders

    def write(self, values):
        if not self._REVOLUT_MUTATION_FIELDS.intersection(values):
            return super().write(values)
        self.check_access("write")
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self)
            return super().write(values)

    def unlink(self):
        self.check_access("unlink")
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self)
            if any(order._revolut_has_exposure() for order in self):
                raise UserError(_("An exposed Revolut order cannot be deleted."))
            return super().unlink()

    def _revolut_payment_values(self, order, existing_order):
        payments = {}
        if existing_order:
            for payment in existing_order.payment_ids:
                if payment.uuid in payments:
                    raise UserError(_("POS payment line identifiers must be unique."))
                payments[payment.uuid] = {
                    **_payment_proof(payment), "id": payment.id,
                }
        incoming_uuids = set()
        for command in order.get("payment_ids", []):
            if command[0] == 5:
                payments.clear()
            elif command[0] in (2, 3) and existing_order:
                payment = existing_order.payment_ids.filtered(lambda item: item.id == command[1])
                if payment:
                    payments.pop(payment.uuid, None)
            elif len(command) >= 3 and isinstance(command[2], dict):
                values = command[2]
                payment_uuid = values.get("uuid")
                if not payment_uuid and command[0] == 1 and existing_order:
                    payment = existing_order.payment_ids.filtered(lambda item: item.id == command[1])
                    payment_uuid = payment.uuid if payment else False
                if not payment_uuid or payment_uuid in incoming_uuids:
                    raise UserError(_("POS payment line identifiers must be unique."))
                if payment_uuid in payments and not existing_order:
                    raise UserError(_("POS payment line identifiers must be unique."))
                incoming_uuids.add(payment_uuid)
                payments[payment_uuid] = {
                    **payments.get(payment_uuid, {}), **values, "uuid": payment_uuid,
                }
        return payments

    def _locked_revolut_operations_for_order(self, company_id, order_uuid):
        self.env["pos.revolut.payment.operation"].sudo()._lock_order(
            company_id, order_uuid
        )
        operations = self.env["pos.revolut.payment.operation"].sudo().search(
            [("company_id", "=", company_id), ("order_uuid", "=", order_uuid)],
            order="id",
        )
        if operations:
            self.env.cr.execute(
                "SELECT id FROM pos_revolut_payment_operation WHERE id = ANY(%s) "
                "ORDER BY id FOR UPDATE",
                [operations.ids],
            )
            operations.invalidate_recordset()
        return operations

    def _validate_revolut_settlement(self, order, existing_order):
        session = self.env["pos.session"].browse(order["session_id"]).exists()
        if not session:
            raise UserError(_("The Point of Sale session does not exist."))
        order_uuid = order.get("uuid") or (existing_order and existing_order.uuid)
        operations = self._locked_revolut_operations_for_order(
            session.company_id.id, order_uuid
        )
        payments = self._revolut_payment_values(order, existing_order)
        payment_methods = self.env["pos.payment.method"].browse([
            value["payment_method_id"]
            for value in payments.values()
            if value.get("payment_method_id")
        ])
        has_revolut_line = any(
            method.use_payment_terminal == "revolut" for method in payment_methods
        )
        operation_model = self.env["pos.revolut.payment.operation"].sudo()
        # A copied payment line or reference must never settle a different order,
        # including when the destination uses a non-Revolut payment method.
        references = [value.get("transaction_id") for value in payments.values()
                      if value.get("transaction_id")]
        matching_operations = operation_model.search([
            "|",
            ("payment_line_uuid", "in", list(payments)),
            ("revolut_payment_id", "in", references),
        ]) if payments else operation_model.browse()
        if any(item.order_uuid != order_uuid or item.company_id != session.company_id
               for item in matching_operations):
            raise UserError(_("A Revolut payment belongs to another POS order."))
        if any(
            value.get("transaction_id") == item.revolut_payment_id
            and value.get("uuid") != item.payment_line_uuid
            for item in matching_operations if item.revolut_payment_id
            for value in payments.values()
        ):
            raise UserError(_("A Revolut payment reference belongs to another payment line."))
        if not operations:
            if has_revolut_line and (
                order.get("state") not in {"draft", "cancel"}
                or any(value.get("payment_status") == "done" for value in payments.values()
                       if self.env["pos.payment.method"].browse(value.get("payment_method_id")).use_payment_terminal == "revolut")
            ):
                raise UserError(_("The Revolut payment has not been verified."))
            return operation_model.browse()

        latest_by_line = {}
        for operation in operations:
            latest_by_line[operation.payment_line_uuid] = operation
        latest = operation_model.browse([item.id for item in latest_by_line.values()])
        if order.get("is_refund") and latest.filtered(
            lambda operation: not operation.retry_safe or operation.state == "verified"
        ):
            raise UserError(_("A Revolut charge cannot settle a refund document."))
        verified = operation_model.browse()
        current_snapshot = operation_model.normalize_financial_snapshot(order)
        for operation in latest:
            if operation.retry_safe and operation.state != "verified":
                continue
            if operation.pos_order_id and operation.pos_order_id != existing_order:
                raise UserError(_("This Revolut payment already belongs to another POS order."))
            if not operation.financial_snapshot:
                raise UserError(_(
                    "The original Revolut order contents are unavailable. "
                    "Reconcile this payment before completing the sale."
                ))
            if current_snapshot != operation.financial_snapshot:
                raise UserError(_(
                    "The order changed while Revolut payment was pending. "
                    "Reconcile it before completing the sale."
                ))
            if operation.state != "verified" and order.get("state") != "draft":
                raise UserError(_(
                    "This order has an unresolved Revolut payment and cannot be completed."
                ))
            payment = payments.get(operation.payment_line_uuid)
            if not payment:
                raise UserError(_("The Revolut payment line is missing."))
            _normalized, payment_minor = operation_model.normalize_amount(
                session.currency_id, payment.get("amount")
            )
            if (
                payment.get("payment_method_id") != operation.payment_method_id.id
                or operation.currency_id != session.currency_id
                or operation.pos_session_id != session
                or operation.pos_config_id != session.config_id
                or operation.payment_method_id.company_id != session.company_id
                or payment_minor != operation.amount_minor
            ):
                raise UserError(_("The Revolut amount, currency, or POS ownership is invalid."))
            if operation.state != "verified":
                if payment.get("payment_status") == "done":
                    raise UserError(_("The Revolut payment has not been verified."))
                continue
            if (
                payment.get("payment_status") != "done"
                or payment.get("transaction_id") != operation.revolut_payment_id
            ):
                raise UserError(_("The Revolut payment details do not match verification."))
            verified |= operation

        verified_uuids = set(verified.mapped("payment_line_uuid"))
        for payment in payments.values():
            method = self.env["pos.payment.method"].browse(payment.get("payment_method_id"))
            if method.use_payment_terminal == "revolut" and (
                order.get("state") not in {"draft", "cancel"} or payment.get("payment_status") == "done"
            ) and payment["uuid"] not in verified_uuids:
                raise UserError(_("The Revolut payment has not been verified."))
        return verified

    def _link_revolut_settlement(self, operations, refunds):
        self.ensure_one()
        ReturnAllocation(self.env).link_settled_refunds(
            refunds or self.env["pos.revolut.refund.operation"].browse(), self
        )
        for operation in operations:
            payment = self.payment_ids.filtered(
                lambda item: item.uuid == operation.payment_line_uuid
            )
            if len(payment) != 1:
                raise UserError(_("The verified Revolut payment was not saved on the order."))
            payment.write({
                "transaction_id": operation.revolut_payment_id,
                "payment_ref_no": operation.revolut_order_id,
                "revolut_order_id": operation.revolut_order_id,
                "revolut_payment_intent_id": operation.revolut_payment_intent_id,
                "revolut_operation_id": operation.id,
            })
            operation.write({
                "pos_order_id": self.id,
                "pos_payment_id": payment.id,
                "blocking_order_key": False,
            })

    def _process_order(self, order, existing_order):
        with _revolut_mutation(self.env) as mutation:
            refunds = ReturnAllocation(self.env).validate_settlement(
                order, existing_order, self._revolut_payment_values(order, existing_order)
            )
            if refunds is None:
                self._validate_revolut_settlement(order, existing_order)
            order_id = super()._process_order(order, existing_order)
            mutation.watch(self.browse(order_id))
            return order_id


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    _REVOLUT_MUTATION_FIELDS = {
        "uuid", "order_id", "company_id", "product_id", "qty", "price_unit", "discount",
        "tax_ids", "price_subtotal", "price_subtotal_incl", "refunded_orderline_id",
        "extra_tax_data", "combo_parent_id", "combo_item_id",
    }

    @api.model_create_multi
    def create(self, vals_list):
        with _revolut_mutation(self.env) as mutation:
            lines = super().create(vals_list)
            mutation.watch(lines.order_id)
            return lines

    def write(self, values):
        if not self._REVOLUT_MUTATION_FIELDS.intersection(values):
            return super().write(values)
        self.check_access("write")
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.order_id)
            mutation.watch_lines(self)
            result = super().write(values)
            mutation.watch(self.order_id)
            return result

    def unlink(self):
        self.check_access("unlink")
        with _revolut_mutation(self.env) as mutation:
            mutation.watch(self.order_id)
            if any(order._revolut_has_exposure() for order in self.order_id):
                raise UserError(_("An exposed Revolut order line cannot be deleted."))
            return super().unlink()

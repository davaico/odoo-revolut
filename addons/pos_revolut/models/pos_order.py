from odoo import _, fields, models
from odoo.exceptions import UserError

from .return_allocation import ReturnAllocation


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


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _revolut_payment_values(self, order, existing_order):
        payments = {}
        if existing_order:
            for payment in existing_order.payment_ids:
                if payment.uuid in payments:
                    raise UserError(_("POS payment line identifiers must be unique."))
                payments[payment.uuid] = {
                    "uuid": payment.uuid,
                    "payment_method_id": payment.payment_method_id.id,
                    "payment_status": payment.payment_status,
                    "transaction_id": payment.transaction_id,
                    "amount": payment.amount,
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
        self.env["pos.revolut.payment.operation"].sudo().lock_order(
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
            if has_revolut_line and order.get("state") != "draft":
                raise UserError(_("The Revolut payment has not been verified."))
            return operation_model.browse()

        latest_by_line = {}
        for operation in operations:
            latest_by_line[operation.payment_line_uuid] = operation
        latest = operation_model.browse([item.id for item in latest_by_line.values()])
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
                order.get("state") != "draft" or payment.get("payment_status") == "done"
            ) and payment["uuid"] not in verified_uuids:
                raise UserError(_("The Revolut payment has not been verified."))
        return verified

    def _process_order(self, order, existing_order):
        refunds = ReturnAllocation(self.env).validate_settlement(
            order, existing_order, self._revolut_payment_values(order, existing_order)
        )
        operations = self._validate_revolut_settlement(order, existing_order) if refunds is None else self.env["pos.revolut.payment.operation"].browse()
        order_id = super()._process_order(order, existing_order)
        pos_order = self.browse(order_id)
        ReturnAllocation(self.env).link_settled_refunds(
            refunds or self.env["pos.revolut.refund.operation"].browse(), pos_order
        )
        if not operations:
            return order_id
        for operation in operations:
            payment = pos_order.payment_ids.filtered(
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
                "pos_order_id": pos_order.id,
                "pos_payment_id": payment.id,
                "blocking_order_key": False,
            })
        return order_id

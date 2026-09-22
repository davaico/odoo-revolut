from odoo import _, fields, models
from odoo.exceptions import UserError


class PosPayment(models.Model):
    _inherit = "pos.payment"

    revolut_order_id = fields.Char(readonly=True, index=True)
    revolut_payment_intent_id = fields.Char(readonly=True, index=True)
    revolut_operation_id = fields.Many2one(
        "pos.revolut.payment.operation", readonly=True, ondelete="restrict", index=True
    )


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _revolut_payment_values(self, order):
        values = []
        for command in order.get("payment_ids", []):
            if len(command) >= 3 and isinstance(command[2], dict):
                values.append(command[2])
        return values

    def _locked_revolut_operation_for_order(self, company_id, order_uuid):
        operation_model = self.env["pos.revolut.payment.operation"].sudo()
        operation = operation_model.search(
            [("company_id", "=", company_id), ("order_uuid", "=", order_uuid)],
            limit=1,
        )
        if operation:
            self.env.cr.execute(
                "SELECT id FROM pos_revolut_payment_operation WHERE id = %s FOR UPDATE",
                [operation.id],
            )
            operation.invalidate_recordset()
        return operation

    def _validate_revolut_settlement(self, order, existing_order):
        if order.get("state") == "draft":
            return False
        session = self.env["pos.session"].browse(order["session_id"]).exists()
        if not session:
            raise UserError(_("The Point of Sale session does not exist."))
        order_uuid = order.get("uuid") or (existing_order and existing_order.uuid)
        operation = self._locked_revolut_operation_for_order(
            session.company_id.id, order_uuid
        )
        payments = self._revolut_payment_values(order)
        payment_methods = self.env["pos.payment.method"].browse(
            [
                value["payment_method_id"]
                for value in payments
                if value.get("payment_method_id")
            ]
        )
        has_revolut_line = any(
            method.use_payment_terminal == "revolut" for method in payment_methods
        )
        if not operation:
            if has_revolut_line:
                raise UserError(_("The Revolut payment has not been verified."))
            return False
        if operation.state != "verified":
            raise UserError(
                _("This order has an unresolved Revolut payment and cannot be completed.")
            )
        if operation.pos_order_id and operation.pos_order_id != existing_order:
            raise UserError(_("This Revolut payment already settled another POS order."))
        matches = [
            value
            for value in payments
            if value.get("uuid") == operation.payment_line_uuid
        ]
        if len(matches) != 1:
            if (
                not payments
                and existing_order == operation.pos_order_id
                and operation.pos_payment_id
            ):
                return operation
            raise UserError(_("The verified Revolut payment line is missing."))
        payment = matches[0]
        if (
            payment.get("payment_method_id") != operation.payment_method_id.id
            or payment.get("payment_status") != "done"
            or payment.get("transaction_id") != operation.revolut_payment_id
        ):
            raise UserError(_("The Revolut payment details do not match verification."))
        operation_model = self.env["pos.revolut.payment.operation"]
        _normalized, payment_minor = operation_model.normalize_amount(
            session.currency_id, payment.get("amount")
        )
        _normalized, total_minor = operation_model.normalize_amount(
            session.currency_id, order.get("amount_total")
        )
        if (
            operation.currency_id != session.currency_id
            or operation.pos_session_id != session
            or operation.pos_config_id != session.config_id
            or operation.payment_method_id.company_id != session.company_id
            or payment_minor != operation.amount_minor
            or total_minor != operation.amount_minor
        ):
            raise UserError(_("The Revolut amount, currency, or POS ownership is invalid."))
        return operation

    def _process_order(self, order, existing_order):
        operation = self._validate_revolut_settlement(order, existing_order)
        order_id = super()._process_order(order, existing_order)
        if not operation:
            return order_id
        pos_order = self.browse(order_id)
        payment = pos_order.payment_ids.filtered(
            lambda item: item.uuid == operation.payment_line_uuid
        )
        if len(payment) != 1:
            raise UserError(_("The verified Revolut payment was not saved on the order."))
        payment.write(
            {
                "transaction_id": operation.revolut_payment_id,
                "payment_ref_no": operation.revolut_order_id,
                "revolut_order_id": operation.revolut_order_id,
                "revolut_payment_intent_id": operation.revolut_payment_intent_id,
                "revolut_operation_id": operation.id,
            }
        )
        operation.write(
            {
                "pos_order_id": pos_order.id,
                "pos_payment_id": payment.id,
                "blocking_order_key": False,
            }
        )
        return order_id

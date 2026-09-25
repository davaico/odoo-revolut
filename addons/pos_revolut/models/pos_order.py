from odoo import _, fields, models
from odoo.exceptions import UserError


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

    def _validate_revolut_refund_settlement(self, order, existing_order):
        session = self.env["pos.session"].browse(order["session_id"]).exists()
        if not session:
            raise UserError(_("The Point of Sale session does not exist."))
        order_uuid = order.get("uuid") or (existing_order and existing_order.uuid)
        self.env["pos.revolut.payment.operation"].sudo().lock_order(session.company_id.id, order_uuid)
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", session.company_id.id), ("order_uuid", "=", order_uuid),
        ])
        payments = self._revolut_payment_values(order, existing_order)
        # Find original return relationships even before a Revolut operation
        # exists, so selecting cash cannot bypass the verified-refund boundary.
        original_ids = []
        for raw in order.get("lines", []):
            line = raw[2] if isinstance(raw, (tuple, list)) and len(raw) > 2 else raw
            if isinstance(line, dict) and line.get("refunded_orderline_id"):
                original_ids.append(line["refunded_orderline_id"])
        if existing_order:
            original_ids += existing_order.lines.refunded_orderline_id.ids
        original_lines = self.env["pos.order.line"].sudo().browse(original_ids).exists()
        source_revolut = original_lines.order_id.payment_ids.filtered(
            lambda payment: payment.payment_method_id.use_payment_terminal == "revolut" or payment.revolut_operation_id
        )
        references = [value.get("transaction_id") for value in payments.values() if value.get("transaction_id")]
        copied = self.env["pos.revolut.refund.operation"].sudo().search([
            "|", ("payment_line_uuid", "in", list(payments)), ("revolut_order_id", "in", references),
        ]) if payments else refunds.browse()
        if any(item not in refunds for item in copied):
            raise UserError(_("A Revolut refund belongs to another return."))
        if any(value.get("transaction_id") == item.revolut_order_id and value["uuid"] != item.payment_line_uuid
               for item in copied if item.revolut_order_id for value in payments.values()):
            raise UserError(_("A Revolut refund reference belongs to another return payment line."))
        negative_revolut = any(
            value.get("amount", 0) < 0 and self.env["pos.payment.method"].browse(value.get("payment_method_id")).use_payment_terminal == "revolut"
            for value in payments.values()
        )
        if not refunds and not source_revolut and not negative_revolut:
            return None
        if refunds:
            self.env.cr.execute("SELECT id FROM pos_revolut_refund_operation WHERE id = ANY(%s) ORDER BY id FOR UPDATE", [refunds.ids])
            refunds.invalidate_recordset()
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        total_minor = normalize(session.currency_id, order.get("amount_total"))[1]
        if total_minor >= 0:
            raise UserError(_("A Revolut-linked return must have a negative total."))
        snapshot = self.env["pos.revolut.refund.operation"]._normalize_return(order)
        original = self.env["pos.revolut.refund.operation"]._return_original(snapshot, session)
        # Serialize tender-balance checks across returns, including cash-only
        # returns of an original mixed-tender sale.
        self.env.cr.execute("UPDATE pos_order SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [original.id])
        self.env["pos.revolut.refund.operation"]._validate_return_quantities(snapshot, original, order_uuid)
        if -total_minor != self.env["pos.revolut.refund.operation"]._return_total_minor(snapshot, original, session.currency_id):
            raise UserError(_("The return total does not match its original sale lines."))
        active = refunds.filtered(lambda item: item.state != "failed")
        verified = refunds.browse()
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            payment = payments.get(refund.payment_line_uuid)
            if refund.state == "failed":
                if payment and payment.get("payment_status") == "done":
                    raise UserError(_("A failed Revolut refund cannot complete a return payment."))
                continue
            if (not payment or snapshot != refund.financial_snapshot
                    or refund.original_order_id != original
                    or refund.pos_session_id != session or refund.currency_id != session.currency_id
                    or (refund.return_total_minor and refund.return_total_minor != -total_minor)
                    or (refund.pos_order_id and refund.pos_order_id != existing_order)
                    or payment.get("payment_method_id") != refund.payment_method_id.id
                    or normalize(session.currency_id, payment.get("amount"))[1] != -refund.amount_minor):
                raise UserError(_("The return changed after a Revolut refund allocation was reserved."))
            if refund.state != "verified":
                if order.get("state") != "draft" or payment.get("payment_status") == "done":
                    raise UserError(_("Only completed Revolut refunds can complete this return."))
                continue
            if payment.get("payment_status") != "done" or payment.get("transaction_id") != refund.revolut_order_id:
                raise UserError(_("The refund payment details do not match Revolut verification."))
            verified |= refund
        if sum(active.mapped("amount_minor")) > -total_minor:
            raise UserError(_("Revolut allocations exceed the return total."))
        for payment in payments.values():
            method = self.env["pos.payment.method"].browse(payment.get("payment_method_id"))
            payment_minor = normalize(session.currency_id, payment.get("amount"))[1]
            if payment_minor > 0:
                raise UserError(_("Return payment allocations must not contain a positive tender."))
            if (method.use_payment_terminal == "revolut" and payment_minor < 0
                    and payment["uuid"] not in active.mapped("payment_line_uuid")
                    and (order.get("state") != "draft" or payment.get("payment_status") == "done")):
                raise UserError(_("A Revolut refund payment has no verified allocation."))
        # Non-Revolut tender remains limited to its original payment method,
        # including cash-only partial returns of a mixed-tender sale.
        original_nonrevolut = {}
        for original_payment in original.payment_ids.sudo().filtered(lambda item: item.payment_method_id.use_payment_terminal != "revolut"):
            method_id = original_payment.payment_method_id.id
            original_nonrevolut[method_id] = original_nonrevolut.get(method_id, 0) + normalize(session.currency_id, original_payment.amount)[1]
        current_nonrevolut = {}
        for item in payments.values():
            method_id = item.get("payment_method_id")
            method = self.env["pos.payment.method"].browse(method_id)
            amount_minor = normalize(session.currency_id, item.get("amount"))[1]
            if method.use_payment_terminal != "revolut" and amount_minor < 0:
                current_nonrevolut[method_id] = current_nonrevolut.get(method_id, 0) - amount_minor
        for method_id, current_minor in current_nonrevolut.items():
            original_minor = original_nonrevolut.get(method_id, 0)
            prior = self.env["pos.payment"].sudo().search([
                ("pos_order_id.lines.refunded_orderline_id", "in", original.lines.ids),
                ("pos_order_id.state", "in", ["paid", "done", "invoiced"]),
                ("payment_method_id", "=", method_id), ("amount", "<", 0),
            ])
            prior_minor = -sum(normalize(session.currency_id, item.amount)[1] for item in prior if not existing_order or item.pos_order_id != existing_order)
            if prior_minor + current_minor > original_minor:
                raise UserError(_("The non-Revolut refund exceeds its original tender."))
        if order.get("state") != "draft":
            if len(verified) != len(active):
                raise UserError(_("Reconcile every Revolut allocation before completing the return."))
            if sum(normalize(session.currency_id, item.get("amount"))[1] for item in payments.values()) != total_minor:
                raise UserError(_("Return allocations do not match the requested return total."))
        return verified

    def _process_order(self, order, existing_order):
        refunds = self._validate_revolut_refund_settlement(order, existing_order)
        operations = self._validate_revolut_settlement(order, existing_order) if refunds is None else self.env["pos.revolut.payment.operation"].browse()
        order_id = super()._process_order(order, existing_order)
        pos_order = self.browse(order_id)
        for refund in refunds or self.env["pos.revolut.refund.operation"].browse():
            payment = pos_order.payment_ids.filtered(lambda item: item.uuid == refund.payment_line_uuid)
            if len(payment) != 1:
                raise UserError(_("The verified Revolut refund payment was not saved."))
            payment.write({"revolut_refund_operation_id": refund.id,
                           "transaction_id": refund.revolut_order_id,
                           "revolut_order_id": refund.revolut_order_id,
                           "payment_ref_no": refund.revolut_order_id})
            refund.write({"pos_order_id": pos_order.id, "pos_payment_id": payment.id})
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

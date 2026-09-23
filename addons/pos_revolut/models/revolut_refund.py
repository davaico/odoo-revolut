from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class PosRevolutRefundOperation(models.Model):
    _name = "pos.revolut.refund.operation"
    _inherit = ["pos.revolut.financial.operation.mixin"]
    _description = "Revolut POS Refund"
    _order = "id desc"

    original_operation_id = fields.Many2one("pos.revolut.payment.operation", required=True, readonly=True, ondelete="restrict", index=True)
    payment_method_id = fields.Many2one(related="original_operation_id.payment_method_id", store=True)
    company_id = fields.Many2one(related="original_operation_id.company_id", store=True)
    original_order_id = fields.Many2one(string="Original Sale", related="original_operation_id.pos_order_id")
    pos_session_id = fields.Many2one("pos.session", required=True, readonly=True, ondelete="restrict")
    pos_order_id = fields.Many2one("pos.order", readonly=True, ondelete="restrict")
    pos_payment_id = fields.Many2one("pos.payment", readonly=True, ondelete="restrict")
    order_uuid = fields.Char(required=True, readonly=True, index=True)
    payment_line_uuid = fields.Char(required=True, readonly=True, index=True)
    amount = fields.Monetary(required=True, readonly=True)
    amount_minor = fields.Integer(required=True, readonly=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True, ondelete="restrict")
    financial_snapshot = fields.Json(required=True, readonly=True)
    idempotency_key = fields.Char(required=True, readonly=True, default=lambda self: str(uuid4()))
    state = fields.Selection([
        ("dispatching", "Dispatching"), ("pending", "Pending"),
        ("unresolved", "Unresolved"), ("verified", "Completed"), ("failed", "Failed"),
    ], required=True, readonly=True, default="dispatching", index=True)
    revolut_order_id = fields.Char(readonly=True, index=True)
    related_order_id = fields.Char(string="Original Revolut Order", related="original_operation_id.revolut_order_id")
    provider_state = fields.Char(readonly=True)
    local_outcome = fields.Char(readonly=True)
    dispatched_at = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now)
    verified_at = fields.Datetime(readonly=True)
    next_reconcile_at = fields.Datetime(readonly=True, default=fields.Datetime.now, index=True)

    _unique_return = models.Constraint("UNIQUE(company_id, order_uuid)", "A return can only have one full Revolut refund.")
    _unique_key = models.Constraint("UNIQUE(idempotency_key)", "Refund idempotency keys must be unique.")
    _unique_provider = models.Constraint("UNIQUE(revolut_order_id)", "A Revolut refund can only be linked once.")
    _unique_payment = models.Constraint("UNIQUE(pos_payment_id)", "A refund can only settle one payment.")
    _positive_amount = models.Constraint("CHECK(amount_minor > 0)", "Refund amounts must be positive.")

    def write(self, values):
        immutable = {"original_operation_id", "pos_session_id", "order_uuid", "payment_line_uuid",
                     "amount", "amount_minor", "currency_id", "financial_snapshot", "idempotency_key", "dispatched_at"}
        if immutable.intersection(values):
            raise ValidationError(_("Refund operation details are immutable."))
        for operation in self:
            for name in {"revolut_order_id", "pos_order_id", "pos_payment_id"}.intersection(values):
                old = operation[name]
                if self._fields[name].type == "many2one":
                    old = old.id
                if old and values[name] != old:
                    raise ValidationError(_("Refund references are immutable."))
        return super().write(values)

    def _revolut_deployment_terminal_states(self):
        return {"verified", "failed"}

    def _snapshot(self):
        self.ensure_one()
        return {
            "operation_id": self.id, "kind": "refund",
            "state": "unresolved" if self.state == "dispatching" else self.state,
            "order_id": self.revolut_order_id or False,
            "payment_id": self.revolut_order_id or False,
            "original_order_id": self.related_order_id,
            "provider_state": self.provider_state or False,
            "local_outcome": self.local_outcome or False, "retry_safe": False,
        }

    @api.model
    def _normalize_return(self, data):
        snapshot = self.env["pos.revolut.payment.operation"].normalize_financial_snapshot(data)
        try:
            originals = {}
            for raw in data["lines"]:
                line = raw[2] if isinstance(raw, (tuple, list)) else raw
                originals[line["uuid"]] = int(line["refunded_orderline_id"])
            for line in snapshot["lines"]:
                line["refunded_orderline_id"] = originals[line["uuid"]]
                if not line["refunded_orderline_id"] or Decimal(line["qty"]) >= 0:
                    raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise UserError(_("Use the normal POS return flow for the complete original sale.")) from None
        return snapshot

    @api.model
    def _validate_original(self, snapshot, method, session, amount_minor):
        ids = [line["refunded_orderline_id"] for line in snapshot["lines"]]
        originals = self.env["pos.order.line"].browse(ids).exists()
        originals.check_access("read")
        orders = originals.order_id
        if len(originals) != len(ids) or len(set(ids)) != len(ids) or len(orders) != 1:
            raise UserError(_("Return lines must belong to one original sale."))
        original = orders
        if original.company_id != session.company_id or original.currency_id != session.currency_id:
            raise AccessError(_("The original sale belongs to another company or currency."))
        if original.state not in {"paid", "done", "invoiced"} or set(original.lines.ids) != set(ids):
            raise UserError(_("Only a full return of a completed sale is supported."))
        payments = original.payment_ids
        source = payments.sudo().revolut_operation_id
        if len(payments) != 1 or len(source) != 1 or source.state != "verified":
            raise UserError(_("The original must have one verified Revolut payment for the full amount."))
        if source.pos_order_id != original or source.pos_payment_id != payments:
            raise UserError(_("The original Revolut payment is not linked to this sale."))
        if (source.payment_method_id != method or source.company_id != session.company_id
                or source.currency_id != session.currency_id or source.amount_minor != amount_minor):
            raise UserError(_("The original Revolut method, company, currency or amount does not match."))
        if (payments.transaction_id != source.revolut_payment_id
                or not source.revolut_order_id or not source.revolut_payment_id):
            raise UserError(_("The original Revolut references are not verified."))
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        if normalize(session.currency_id, original.amount_total)[1] != amount_minor or normalize(session.currency_id, payments.amount)[1] != amount_minor:
            raise UserError(_("The original Revolut amount does not match the sale."))
        by_id = {line.id: line for line in originals}
        for line in snapshot["lines"]:
            old = by_id[line["refunded_orderline_id"]]
            if (Decimal(line["qty"]) != -Decimal(str(old.qty))
                    or old.qty <= 0 or line["product_id"] != old.product_id.id
                    or Decimal(line["price_unit"]) != Decimal(str(old.price_unit))
                    or Decimal(line["discount"]) != Decimal(str(old.discount))
                    or line["tax_ids"] != sorted(old.tax_ids.ids)):
                raise UserError(_("Return the original quantities, prices, discounts and taxes unchanged."))
        if (snapshot["pricelist_id"] != original.pricelist_id.id
                or snapshot["fiscal_position_id"] != (original.fiscal_position_id.id or 0)):
            raise UserError(_("The return's price list or fiscal position changed."))
        return source

    @api.model
    def _cron_reconcile_refunds(self, batch_size=50):
        operations = self.sudo().search([
            ("state", "in", ["dispatching", "pending", "unresolved"]),
            ("next_reconcile_at", "<=", fields.Datetime.now()),
        ], order="next_reconcile_at, id", limit=max(1, min(int(batch_size), 50)))
        for operation in operations:
            operation.payment_method_id.sudo().with_company(operation.company_id).revolut_poll_refund(
                operation.id, operation.order_uuid, operation.payment_line_uuid
            )

    def action_check_status(self):
        for operation in self:
            operation.payment_method_id.revolut_poll_refund(operation.id, operation.order_uuid, operation.payment_line_uuid)
        return {"type": "ir.actions.client", "tag": "reload"}


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _check_refund_authority(self):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(_("Only Point of Sale managers can issue or reconcile Revolut refunds."))
        self.check_access("read")
        if self.company_id not in self.env.companies or self.use_payment_terminal != "revolut":
            raise AccessError(_("This Revolut payment method is not accessible."))

    def revolut_start_refund(self, session_id, order_uuid, payment_line_uuid, amount, currency_id, financial_snapshot):
        self._check_refund_authority()
        try:
            amount = Decimal(str(amount))
            if not amount.is_finite() or amount >= 0:
                raise ValueError()
        except (ValueError, ArithmeticError):
            raise UserError(_("The Revolut return amount must be negative.")) from None
        session, currency, normalized, minor, order_uuid, payment_line_uuid = self._validate_revolut_pos_request(
            session_id, order_uuid, payment_line_uuid, -amount, currency_id
        )
        snapshot = self.env["pos.revolut.refund.operation"]._normalize_return(financial_snapshot)
        # Reservation and dispatch claim are committed together, before any HTTP.
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    refunds = env["pos.revolut.refund.operation"].sudo()
                    env["pos.revolut.payment.operation"].sudo().lock_order(self.company_id.id, order_uuid)
                    if env["pos.revolut.payment.operation"].sudo().search_count([
                        ("company_id", "=", self.company_id.id), ("order_uuid", "=", order_uuid),
                    ]):
                        raise UserError(_("A Revolut charge already exists for this return. Reconcile it first."))
                    existing = refunds.search([("company_id", "=", self.company_id.id), ("order_uuid", "=", order_uuid)], limit=1)
                    if existing:
                        if (existing.payment_line_uuid != payment_line_uuid or existing.payment_method_id.id != self.id
                                or existing.amount_minor != minor or existing.currency_id.id != currency.id
                                or existing.pos_session_id.id != session.id or existing.financial_snapshot != snapshot):
                            raise UserError(_("The existing refund has different return details."))
                        return existing._snapshot()
                    source = env["pos.revolut.refund.operation"]._validate_original(
                        snapshot, env["pos.payment.method"].browse(self.id), env["pos.session"].browse(session.id), minor
                    )
                    # Updating the source makes stale repeatable-read contenders
                    # retry, so each reservation sees all committed reservations.
                    cursor.execute("UPDATE pos_revolut_payment_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [source.id])
                    reserved = sum(refunds.search([("original_operation_id", "=", source.id), ("state", "!=", "failed")]).mapped("amount_minor"))
                    other_returns = env["pos.order.line"].sudo().search_count([
                        ("refunded_orderline_id", "in", source.pos_order_id.lines.ids),
                        ("order_id.state", "in", ["paid", "done", "invoiced"]),
                    ])
                    if reserved + minor > source.amount_minor or other_returns:
                        raise UserError(_("The original payment is already refunded or reserved by another refund."))
                    if env["pos.order"].sudo().search_count([("uuid", "=", order_uuid), ("state", "!=", "draft")]):
                        raise UserError(_("This return has already been completed."))
                    refund = refunds.create({
                        "original_operation_id": source.id, "pos_session_id": session.id,
                        "order_uuid": order_uuid, "payment_line_uuid": payment_line_uuid,
                        "amount": float(normalized), "amount_minor": minor,
                        "currency_id": currency.id, "financial_snapshot": snapshot,
                    })
                    operation_id = refund.id
                    cursor.commit()
                break
            except (IntegrityError, SerializationFailure):
                if attempt == 2:
                    raise UserError(_("Another refund request is in progress. Check status.")) from None
        operation = self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        try:
            original = self._revolut_api_request(operation, "GET", f"/api/orders/{operation['original_order_id']}")
            if (original.get("id") != operation["original_order_id"] or original.get("state") != "completed"
                    or original.get("amount") != minor or original.get("currency") != operation["currency_code"]
                    or original.get("refunded_amount", 0) != 0):
                return self._update_refund_owned(operation_id, {"state": "failed", "provider_state": "original_ineligible"})
            result = self._revolut_api_request(
                operation, "POST", f"/api/orders/{operation['original_order_id']}/refund",
                idempotency_key=operation["idempotency_key"],
                json={"amount": minor, "currency": operation["currency_code"],
                      "merchant_order_data": {"reference": operation["idempotency_key"]}},
            )
            self._validate_refund_response(operation, result)
            # Even a completed POST response needs an authoritative read.
            return self._update_refund_owned(operation_id, {"revolut_order_id": result["id"], "state": "pending", "provider_state": result.get("state")})
        except (requests.RequestException, UserError, ValueError):
            return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "interrupted"})

    def _read_refund_owned(self, operation_id=None, order_uuid=None, payment_line_uuid=None):
        self._check_refund_authority()
        with self.env.registry.cursor() as cursor:
            env = api.Environment(cursor, self.env.uid, dict(self.env.context))
            domain = [("payment_method_id", "=", self.id), ("company_id", "in", self.env.companies.ids)]
            if operation_id:
                domain.append(("id", "=", operation_id))
            if order_uuid is not None:
                domain.append(("order_uuid", "=", str(UUID(order_uuid))))
            if payment_line_uuid is not None:
                domain.append(("payment_line_uuid", "=", str(UUID(payment_line_uuid))))
            operation = env["pos.revolut.refund.operation"].sudo().search(domain, limit=1)
            if not operation:
                if operation_id:
                    raise AccessError(_("This refund is not accessible."))
                return False
            source = operation.original_operation_id
            return {"snapshot": operation._snapshot(), "id": operation.id,
                    "environment": source.environment, "secret_reference": source.secret_reference,
                    "original_order_id": source.revolut_order_id, "amount_minor": operation.amount_minor,
                    "currency_code": operation.currency_id.name, "idempotency_key": operation.idempotency_key,
                    "order_id": operation.revolut_order_id, "state": operation.state}

    def _update_refund_owned(self, operation_id, values):
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    cursor.execute("SELECT id FROM pos_revolut_refund_operation WHERE id = %s FOR UPDATE", [operation_id])
                    operation = env["pos.revolut.refund.operation"].sudo().browse(operation_id)
                    if operation.state not in {"verified", "failed"}:
                        final = values.get("state") in {"verified", "failed"}
                        operation.write({**values, "next_reconcile_at": False if final else fields.Datetime.now() + timedelta(seconds=30)})
                    snapshot = operation._snapshot()
                    cursor.commit()
                    return snapshot
            except SerializationFailure:
                if attempt == 2:
                    raise

    def _validate_refund_response(self, operation, response):
        try:
            UUID(response["id"])
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("invalid refund reference") from None
        if (response.get("type") != "refund" or response.get("related_order_id") != operation["original_order_id"]
                or response.get("amount") != operation["amount_minor"] or response.get("currency") != operation["currency_code"]
                or (operation["order_id"] and response["id"] != operation["order_id"])):
            raise ValueError("refund details do not match")

    def revolut_find_refund(self, order_uuid, payment_line_uuid):
        result = self._read_refund_owned(order_uuid=order_uuid, payment_line_uuid=payment_line_uuid)
        return result["snapshot"] if result else False

    def revolut_poll_refund(self, operation_id, order_uuid, payment_line_uuid):
        operation = self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        if operation["state"] in {"verified", "failed"}:
            return operation["snapshot"]
        try:
            if not operation["order_id"]:
                # A missing response is not permission to POST again. Recover by
                # the persisted merchant reference and verify the full order.
                payload = self._revolut_api_request(operation, "GET", "/api/orders", params={"merchant_order_data_reference": operation["idempotency_key"]})
                candidates = payload.get("orders")
                if not isinstance(candidates, list) or len(candidates) != 1:
                    raise ValueError("refund association is uncertain")
                candidate = candidates[0]
                merchant_data = candidate.get("merchant_order_data") if isinstance(candidate, dict) else None
                if not isinstance(merchant_data, dict) or merchant_data.get("reference") != operation["idempotency_key"]:
                    raise ValueError("refund reference does not match")
                self._validate_refund_response(operation, candidate)
                operation["order_id"] = candidate["id"]
            payload = self._revolut_api_request(operation, "GET", f"/api/orders/{operation['order_id']}")
            self._validate_refund_response(operation, payload)
            state = payload.get("state")
            values = {"revolut_order_id": operation["order_id"], "provider_state": state,
                      "state": "verified" if state == "completed" else "failed" if state in {"failed", "cancelled"} else "pending",
                      "local_outcome": False}
            if values["state"] == "verified":
                values["verified_at"] = fields.Datetime.now()
            return self._update_refund_owned(operation_id, values)
        except (requests.RequestException, UserError, ValueError):
            return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "interrupted"})

    def revolut_mark_refund_timeout(self, operation_id, order_uuid, payment_line_uuid):
        self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "timed_out"})

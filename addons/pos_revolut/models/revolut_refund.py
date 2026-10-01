import logging
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .return_allocation import ReturnAllocation
from .financial_snapshot import FinancialSnapshotError


_logger = logging.getLogger(__name__)


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
    return_total_minor = fields.Integer(readonly=True)
    allocation_explicit = fields.Boolean(readonly=True)
    base_amount_minor = fields.Integer(readonly=True)
    tip_amount_minor = fields.Integer(readonly=True)
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
    reconcile_failures = fields.Integer(readonly=True, default=0)

    _unique_return_line = models.Constraint("UNIQUE(company_id, order_uuid, payment_line_uuid)", "A return payment line can only have one Revolut refund.")
    _unique_key = models.Constraint("UNIQUE(idempotency_key)", "Refund idempotency keys must be unique.")
    _unique_provider = models.Constraint("UNIQUE(revolut_order_id)", "A Revolut refund can only be linked once.")
    _unique_payment = models.Constraint("UNIQUE(pos_payment_id)", "A refund can only settle one payment.")
    _positive_amount = models.Constraint("CHECK(amount_minor > 0)", "Refund amounts must be positive.")

    _component_amounts = models.Constraint(
        "CHECK((COALESCE(allocation_explicit, FALSE) AND "
        "COALESCE(base_amount_minor, -1) >= 0 AND COALESCE(tip_amount_minor, -1) >= 0 AND "
        "base_amount_minor + tip_amount_minor = amount_minor) OR "
        "(NOT COALESCE(allocation_explicit, FALSE) AND "
        "COALESCE(base_amount_minor, 0) = 0 AND COALESCE(tip_amount_minor, 0) = 0))",
        "Refund base and terminal tip amounts must match the refund total.",
    )

    def write(self, values):
        immutable = {"original_operation_id", "pos_session_id", "order_uuid", "payment_line_uuid",
                     "amount", "amount_minor", "return_total_minor", "allocation_explicit", "base_amount_minor", "tip_amount_minor", "currency_id", "financial_snapshot", "idempotency_key", "dispatched_at"}
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
            "original_operation_id": self.original_operation_id.id,
            "amount_minor": self.amount_minor,
            "return_total_minor": self.return_total_minor,
            "base_amount_minor": self.base_amount_minor if self.allocation_explicit else self.amount_minor,
            "tip_amount_minor": self.tip_amount_minor,
            "terminal_tip_evidence": self.allocation_explicit,
            "provider_state": self.provider_state or False,
            "local_outcome": self.local_outcome or False, "retry_safe": False,
        }

    @api.model
    def _cron_reconcile_refunds(self, batch_size=50):
        operations = self.sudo().search([
            ("state", "in", ["dispatching", "pending", "unresolved"]),
            ("next_reconcile_at", "<=", fields.Datetime.now()),
        ], order="next_reconcile_at, id", limit=max(1, min(int(batch_size), 50)))
        for operation in operations:
            payment_method = operation.payment_method_id.sudo().with_company(operation.company_id)
            try:
                payment_method.revolut_poll_refund(
                    operation.id, operation.order_uuid, operation.payment_line_uuid
                )
            except (SerializationFailure, DeadlockDetected):
                # The adapter has ended the failed transaction. Reschedule in
                # a fresh locked cursor without repeating a refund request.
                _logger.warning("Revolut refund operation %s deferred after a transaction conflict", operation.id)
                try:
                    payment_method._update_refund_owned(operation.id, {
                        "state": "unresolved", "local_outcome": "interrupted",
                    })
                except (SerializationFailure, DeadlockDetected):
                    _logger.warning("Revolut refund operation %s could not be rescheduled; retains its previous schedule", operation.id)

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

    def revolut_refund_sources(self, session_id, currency_id, financial_snapshot):
        self._check_refund_authority()
        session = self.env["pos.session"].browse(session_id).exists()
        if (not session or session.company_id != self.company_id or session.currency_id.id != currency_id
                or session.state != "opened" or self not in session.config_id.payment_method_ids):
            raise AccessError(_("This POS session is not available for Revolut refunds."))
        return ReturnAllocation(self.env).sources(session, financial_snapshot)

    def revolut_start_refund(self, session_id, order_uuid, payment_line_uuid, amount, currency_id, financial_snapshot, original_operation_id=None, base_amount_minor=None, tip_amount_minor=None):
        self._check_refund_authority()
        try:
            amount = Decimal(str(amount))
            if not amount.is_finite() or amount >= 0:
                raise ValueError()
        except (ValueError, ArithmeticError):
            raise UserError(_("The Revolut return amount must be negative.")) from None
        session, currency, normalized, minor, order_uuid, payment_line_uuid = self._validate_revolut_pos_request(
            session_id, order_uuid, payment_line_uuid, -amount, currency_id,
            require_current_credential=False,
        )
        # The reservation and dispatch claim commit before any provider call.
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    reservation = ReturnAllocation(env).reserve(
                        env["pos.payment.method"].browse(self.id),
                        env["pos.session"].browse(session.id), order_uuid,
                        payment_line_uuid, normalized, minor,
                        env["res.currency"].browse(currency.id),
                        financial_snapshot, original_operation_id, base_amount_minor, tip_amount_minor,
                    )
                    if reservation.existing_status is not None:
                        return reservation.existing_status
                    source = env["pos.revolut.refund.operation"].sudo().browse(
                        reservation.operation_id
                    ).original_operation_id
                    env["pos.payment.method"].browse(self.id)._revolut_authorized_operation_secret({
                        "credential_operation_id": source.id,
                        "environment": source.environment,
                        "secret_reference": source.secret_reference,
                    })
                    cursor.commit()
                break
            except FinancialSnapshotError as error:
                return self._reject_revolut_snapshot_owned(order_uuid, payment_line_uuid, error)
            except (IntegrityError, SerializationFailure):
                if attempt == 2:
                    raise UserError(_("Another refund request is in progress. Check status.")) from None
        operation_id = reservation.operation_id
        source_amount_minor = reservation.source_amount_minor
        verified_before_claim = reservation.verified_before_claim
        operation = self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        try:
            original = self._revolut_api_request(operation, "GET", f"/api/orders/{operation['original_order_id']}")
            if (original.get("id") != operation["original_order_id"] or original.get("state") != "completed"
                    or type(original.get("amount")) is not int
                    or original.get("amount") != source_amount_minor or original.get("currency") != operation["currency_code"]
                    or original.get("refunded_amount", verified_before_claim) != verified_before_claim
                    or (reservation.source_base_minor is not None and (
                        type(original.get("refunded_amount")) is not int
                        or reservation.source_base_minor + reservation.source_tip_minor != source_amount_minor))):
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
                    "credential_operation_id": source.id,
                    "environment": source.environment, "secret_reference": source.secret_reference,
                    "original_order_id": source.revolut_order_id, "amount_minor": operation.amount_minor,
                    "currency_code": operation.currency_id.name, "idempotency_key": operation.idempotency_key,
                    "order_id": operation.revolut_order_id, "state": operation.state}

    def _update_refund_owned(self, operation_id, values):
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    operation = env["pos.revolut.refund.operation"].sudo().browse(operation_id).exists()
                    if not operation or operation.payment_method_id.id != self.id:
                        raise AccessError(_("This refund is not accessible."))
                    env["pos.revolut.payment.operation"]._lock_order(operation.company_id.id, operation.order_uuid)
                    cursor.execute("SELECT id FROM pos_revolut_refund_operation WHERE id = %s FOR UPDATE", [operation_id])
                    operation.invalidate_recordset()
                    if operation.state not in {"verified", "failed"}:
                        final = values.get("state") in {"verified", "failed"}
                        cause = values.get("local_outcome")
                        failures = operation.reconcile_failures
                        if cause == "interrupted":
                            failures += 1
                            delay = min(60 * 2 ** min(failures - 1, 5), 1800)
                        elif cause == "unknown":
                            delay = 300
                        else:
                            failures, delay = 0, 30
                        operation.write({
                            **values, "reconcile_failures": 0 if final else failures,
                            "next_reconcile_at": False if final else fields.Datetime.now() + timedelta(seconds=delay),
                        })
                        if cause in {"unknown", "interrupted"}:
                            _logger.warning("Revolut refund operation %s remains unresolved (%s)", operation.id, cause)
                    snapshot = operation._snapshot()
                    cursor.commit()
                    return snapshot
            except (SerializationFailure, DeadlockDetected):
                if attempt == 2:
                    raise

    def _validate_refund_response(self, operation, response):
        if not isinstance(response, dict):
            raise ValueError("invalid refund response")
        try:
            UUID(response["id"])
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("invalid refund reference") from None
        if (response.get("type") != "refund" or response.get("related_order_id") != operation["original_order_id"]
                or type(response.get("amount")) is not int
                or response.get("amount") != operation["amount_minor"] or response.get("currency") != operation["currency_code"]
                or (operation["order_id"] and response["id"] != operation["order_id"])):
            raise ValueError("refund details do not match")
        state = response.get("state")
        if not isinstance(state, str) or state not in {
            "pending", "processing", "authorised", "completed", "failed", "cancelled"
        }:
            raise ValueError("refund outcome is not established")

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
        except requests.RequestException:
            return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "interrupted"})
        except (UserError, ValueError):
            return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "unknown"})

    def revolut_mark_refund_timeout(self, operation_id, order_uuid, payment_line_uuid):
        self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "timed_out"})


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _revolut_return_target_minor(self):
        self.ensure_one()
        original = self.lines.refunded_orderline_id.order_id
        if (len(original) == 1 and original.revolut_authorization_id
                and self.lines and all(line.refunded_orderline_id and line.qty < 0 for line in self.lines)):
            allocation = ReturnAllocation(self.env)
            snapshot = allocation._normalize_return(self._revolut_order_values(), native_order=True)
            return -allocation._return_total_minor(snapshot, original, self.currency_id)
        return None

    def _compute_prices(self):
        result = super()._compute_prices()
        for order in self:
            target = order._revolut_return_target_minor()
            if target is not None:
                order.amount_total = target / (10 ** order.currency_id.decimal_places)
                order.amount_difference = order.amount_paid - order.amount_total
        return result

    def _get_rounded_amount(self, amount, force_round=False):
        # A returned terminal tip must not enter global cash rounding again.
        # Keep native original line prices/taxes and refund their frozen base
        # allocation separately from the exact collected customer tip.
        target = self._revolut_return_target_minor()
        if target is not None:
            return target / (10 ** self.currency_id.decimal_places)
        return super()._get_rounded_amount(amount, force_round=force_round)

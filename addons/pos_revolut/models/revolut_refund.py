import logging
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import format_amount

from .return_allocation import ReturnAllocation
from .financial_snapshot import FinancialSnapshotError


_logger = logging.getLogger(__name__)


class PosRevolutRefundOperation(models.Model):
    _name = "pos.revolut.refund.operation"
    _inherit = ["pos.revolut.financial.operation.mixin"]
    _description = "Revolut POS Refund"
    _order = "id desc"

    origin = fields.Selection([
        ("odoo", "Odoo POS"), ("external", "Detected in Revolut"),
    ], string="Source", required=True, readonly=True, default="odoo", index=True)
    original_operation_id = fields.Many2one("pos.revolut.payment.operation", required=True, readonly=True, ondelete="restrict", index=True)
    payment_method_id = fields.Many2one(related="original_operation_id.payment_method_id", store=True)
    company_id = fields.Many2one(related="original_operation_id.company_id", store=True)
    original_order_id = fields.Many2one(string="Original Sale", related="original_operation_id.pos_order_id")
    pos_session_id = fields.Many2one("pos.session", required=True, readonly=True, ondelete="restrict")
    pos_order_id = fields.Many2one("pos.order", readonly=True, ondelete="restrict")
    pos_payment_id = fields.Many2one("pos.payment", readonly=True, ondelete="restrict")
    display_return_id = fields.Many2one("pos.order", string="Odoo Return", compute="_compute_return_display")
    native_completion_label = fields.Char(string="Native completion", compute="_compute_return_display")
    order_uuid = fields.Char(readonly=True, index=True)
    payment_line_uuid = fields.Char(readonly=True, index=True)
    amount = fields.Monetary(required=True, readonly=True)
    amount_minor = fields.Integer(required=True, readonly=True)
    return_total_minor = fields.Integer(readonly=True)
    return_allocation = fields.Json(readonly=True)
    allocation_explicit = fields.Boolean(readonly=True)
    base_amount_minor = fields.Integer(readonly=True)
    tip_amount_minor = fields.Integer(readonly=True)
    currency_id = fields.Many2one("res.currency", required=True, readonly=True, ondelete="restrict")
    financial_snapshot = fields.Json(readonly=True)
    idempotency_key = fields.Char(readonly=True)
    native_reconciliation_status = fields.Selection([
        ("not_required", "Not required"), ("outstanding", "Outstanding"),
        ("reconciled", "Historical acknowledgement (unproven)"),
        ("native_draft", "Native return awaiting completion"),
        ("native_completed", "Native return completed"),
        ("financial_only", "No products returned — accounting completed"),
    ], required=True, readonly=True, default="not_required", index=True)
    native_reconciled_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    native_reconciled_at = fields.Datetime(readonly=True)
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

    _sql_constraints = [
        ("unique_return_line","UNIQUE(company_id, order_uuid, payment_line_uuid)", "A return payment line can only have one Revolut refund."),
        ("unique_key","UNIQUE(idempotency_key)", "Refund idempotency keys must be unique."),
        ("unique_provider","UNIQUE(revolut_order_id)", "A Revolut refund can only be linked once."),
        ("unique_payment","UNIQUE(pos_payment_id)", "A refund can only settle one payment."),
        ("positive_amount","CHECK(amount_minor > 0)", "Refund amounts must be positive."),
        ("origin_identity",
            "CHECK((origin = 'odoo' AND order_uuid IS NOT NULL AND payment_line_uuid IS NOT NULL "
            "AND financial_snapshot IS NOT NULL AND idempotency_key IS NOT NULL) OR "
            "(origin = 'external' AND idempotency_key IS NULL AND revolut_order_id IS NOT NULL AND ("
            "(order_uuid IS NULL AND payment_line_uuid IS NULL AND financial_snapshot IS NULL "
            "AND pos_order_id IS NULL AND pos_payment_id IS NULL "
            "AND COALESCE(return_total_minor, 0) = 0 AND return_allocation IS NULL) OR "
            "(order_uuid IS NOT NULL AND payment_line_uuid IS NOT NULL AND financial_snapshot IS NOT NULL "
            "AND pos_order_id IS NOT NULL AND pos_payment_id IS NOT NULL "
            "AND return_total_minor > 0 AND return_allocation IS NOT NULL))))",
            "External refunds require a complete manager-confirmed native association or no product return.",
        ),
        ("component_amounts",
            "CHECK((COALESCE(allocation_explicit, FALSE) AND "
            "COALESCE(base_amount_minor, -1) >= 0 AND COALESCE(tip_amount_minor, -1) >= 0 AND "
            "base_amount_minor + tip_amount_minor = amount_minor) OR "
            "(NOT COALESCE(allocation_explicit, FALSE) AND "
            "COALESCE(base_amount_minor, 0) = 0 AND COALESCE(tip_amount_minor, 0) = 0))",
            "Refund base and terminal tip amounts must match the refund total.",
        ),
    ]

    @api.depends("pos_order_id", "pos_order_id.state", "order_uuid", "pos_session_id", "state", "origin", "native_reconciliation_status")
    def _compute_return_display(self):
        # Display recovery is not settlement evidence. Search as the current
        # user, preserving native order rules as well as register visibility.
        labels = dict(self._fields["native_reconciliation_status"]._description_selection(self.env))
        for refund in self:
            order = refund.pos_order_id
            if not order and refund.origin == "odoo" and refund.order_uuid:
                order = self.env["pos.order"].search([
                    ("uuid", "=", refund.order_uuid),
                    ("company_id", "=", refund.company_id.id),
                    ("config_id", "=", refund.pos_session_id.config_id.id),
                ], limit=1)
            refund.display_return_id = order
            label = labels.get(refund.native_reconciliation_status)
            if refund.origin == "odoo" and refund.state != "failed":
                if order and order.state in ("paid", "done", "invoiced"):
                    label = _("Native return completed")
                elif refund.state != "verified":
                    label = _("Return awaiting refund confirmation")
                else:
                    label = _("Native return awaiting validation") if order else _("Return recovery required")
            refund.native_completion_label = label

    @api.depends("amount", "currency_id", "original_order_id.display_name")
    def _compute_display_name(self):
        for refund in self:
            amount = format_amount(self.env, refund.amount, refund.currency_id)
            sale = refund.original_order_id.display_name
            refund.display_name = (
                _("Refund %(amount)s — %(sale)s", amount=amount, sale=sale)
                if sale else _("Refund %(amount)s", amount=amount)
            )

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for values in vals_list:
            values = dict(values)
            if values.get("origin", "odoo") == "external":
                values["native_reconciliation_status"] = "not_required" if values.get("state") == "failed" else "outstanding"
            else:
                values.setdefault("idempotency_key", str(uuid4()))
                values["native_reconciliation_status"] = "not_required"
            values.pop("native_reconciled_by", None)
            values.pop("native_reconciled_at", None)
            prepared.append(values)
        return super().create(prepared)

    @api.constrains("origin", "pos_session_id", "original_operation_id")
    def _check_external_source_session(self):
        for operation in self:
            if operation.origin == "external" and operation.pos_session_id != operation.original_operation_id.pos_session_id:
                raise ValidationError(_("An external refund must retain its original payment session."))

    def write(self, values):
        if {"native_reconciliation_status", "native_reconciled_by", "native_reconciled_at"}.intersection(values):
            raise ValidationError(_("A manager must acknowledge native reconciliation through the dedicated action."))
        immutable = {"origin", "original_operation_id", "pos_session_id", "order_uuid", "payment_line_uuid",
                     "amount", "amount_minor", "return_total_minor", "return_allocation", "allocation_explicit", "base_amount_minor", "tip_amount_minor", "currency_id", "financial_snapshot", "idempotency_key", "dispatched_at"}
        if immutable.intersection(values):
            raise ValidationError(_("Refund operation details are immutable."))
        for operation in self:
            for name in {"revolut_order_id", "pos_order_id", "pos_payment_id"}.intersection(values):
                old = operation[name]
                if self._fields[name].type == "many2one":
                    old = old.id
                if old and values[name] != old:
                    raise ValidationError(_("Refund references are immutable."))
        result = super().write(values)
        if values.get("state") == "failed":
            external = self.filtered(lambda operation: operation.origin == "external")
            super(PosRevolutRefundOperation, external).write({"native_reconciliation_status": "not_required"})
        return result

    def _revolut_deployment_terminal_states(self):
        return {"verified", "failed"}

    def _check_revolut_register_access(self):
        self.ensure_one()
        if self.env.su:
            return
        self.check_access("read")
        self.original_operation_id._check_revolut_register_access()
        session = self.pos_session_id
        order = self.original_order_id if self.origin == "external" else self.pos_order_id or self.env["pos.order"].sudo().search([
            ("company_id", "=", self.company_id.id), ("uuid", "=", self.order_uuid),
        ], limit=1).with_env(self.env)
        session.config_id._check_revolut_register_access(session=session, order=order)
        if session.config_id != self.original_operation_id.pos_config_id:
            raise AccessError(_("The refund belongs to another Point of Sale register."))

    def _snapshot(self):
        self.ensure_one()
        return {
            "operation_id": self.id, "kind": "refund",
            "origin": self.origin,
            "native_reconciliation_status": self.native_reconciliation_status,
            "state": "unresolved" if self.state == "dispatching" else self.state,
            "order_id": self.revolut_order_id or False,
            "payment_id": self.revolut_order_id or False,
            "original_order_id": self.related_order_id,
            "original_operation_id": self.original_operation_id.id,
            "amount_minor": self.amount_minor,
            "return_total_minor": self.return_total_minor if self.order_uuid else False,
            "base_amount_minor": (self.base_amount_minor if self.allocation_explicit else self.amount_minor) if self.order_uuid else False,
            "tip_amount_minor": self.tip_amount_minor if self.order_uuid else False,
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

    def action_recover_return(self):
        """Restore an Odoo-origin return draft using its verified allocations.

        The provider refund is already complete. Recovery saves native review
        data only; cashier validation still owns stock and accounting effects.
        """
        self.ensure_one()
        self.payment_method_id._check_refund_authority()
        self._check_revolut_register_access()
        if self.origin != "odoo" or self.state != "verified":
            raise UserError(_("Only a completed Odoo refund can recover its original return."))
        with self.env.cr.savepoint():
            order_domain = [("company_id", "=", self.company_id.id), ("uuid", "=", self.order_uuid)]
            existing = self.env["pos.order"].sudo().search(order_domain, limit=1).with_env(self.env)
            if existing:
                existing.check_access("read")
            session = existing.session_id if existing else self.pos_session_id.config_id.current_session_id
            with ReturnAllocation(self.env).recover(self, session) as evidence:
                recovery = evidence.read(self.env)
                existing = recovery.existing_order
                if existing and existing.state != "draft":
                    return {"type": "ir.actions.act_window", "res_model": "pos.order",
                            "res_id": existing.id, "view_mode": "form", "target": "current"}
                if not existing:
                    values = self._recovered_return_values(recovery, session)
                    saved = self.env["pos.order"].sync_from_ui([values])
                    existing = self.env["pos.order"].browse(next(
                        item["id"] for item in saved["pos.order"] if item["uuid"] == self.order_uuid
                    ))
                else:
                    from .pos_order import _revolut_mutation
                    # Project all checked siblings together. Native validation
                    # binds their canonical references and rolls back the whole
                    # projection if the saved return conflicts with its proof.
                    with _revolut_mutation(self.env):
                        for refund in recovery.refunds:
                            payment = existing.payment_ids.filtered(
                                lambda item: item.uuid == refund.payment_line_uuid)
                            payment.write({"payment_status": "done", "transaction_id": refund.revolut_order_id,
                                           "payment_ref_no": refund.revolut_order_id})
                if session.state != "opened":
                    raise UserError(_("Reopen the original return's session before continuing in POS."))
                return {"type": "ir.actions.act_url", "target": "self",
                        "url": f"/pos/ui?from_backend=1&config_id={session.config_id.id}&revolut_return_uuid={existing.uuid}"}

    def _recovered_return_values(self, recovery, session):
        snapshot, original = recovery.snapshot, recovery.original
        values = {
            "name": _("%(name)s REFUND", name=original.name),
            "uuid": self.order_uuid, "session_id": session.id, "user_id": self.env.uid,
            "company_id": session.company_id.id, "config_id": session.config_id.id,
            "state": "draft", "is_refund": True, "to_invoice": False,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "pricelist_id": snapshot["pricelist_id"],
            "fiscal_position_id": snapshot["fiscal_position_id"] or False,
            "partner_id": original.partner_id.id or False,
            "amount_total": -recovery.decision.total_minor / 10 ** session.currency_id.decimal_places,
            "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                **line, "qty": float(line["qty"]), "price_unit": float(line["price_unit"]),
                "discount": float(line["discount"]), "tax_ids": [Command.set(line["tax_ids"])],
                "price_subtotal": 0, "price_subtotal_incl": 0,
            }) for line in snapshot["lines"]],
            "payment_ids": [Command.create({
                "uuid": refund.payment_line_uuid, "payment_method_id": refund.payment_method_id.id,
                "amount": -refund.amount_minor / 10 ** session.currency_id.decimal_places,
                "payment_status": "done",
                "transaction_id": refund.revolut_order_id, "payment_ref_no": refund.revolut_order_id,
                "name": fields.Datetime.now(),
            }) for refund in recovery.refunds],
        }
        # Native tax calculation and validation remain caller-owned projection.
        draft = self.env["pos.order"].new(values)
        for line in draft.lines:
            line.order_id = draft
            line.update(line._compute_amount_line_all())
        draft._compute_prices()
        for command, line in zip(values["lines"], draft.lines):
            command[2].update(price_subtotal=line.price_subtotal, price_subtotal_incl=line.price_subtotal_incl)
        values.update(amount_total=draft.amount_total, amount_tax=draft.amount_tax,
                      amount_paid=draft.amount_paid, amount_return=draft.amount_return)
        return values

    def action_acknowledge_native_reconciliation(self):
        for operation in self:
            operation.payment_method_id._check_refund_authority()
            operation._check_revolut_register_access()
        raise UserError(_("Confirm a native return or record the no-products-returned disposition with its accounting document."))


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
        session.config_id._check_revolut_register_access(session=session)
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
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context), su=self.env.su)
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
        operation = self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        try:
            original = self._revolut_api_request(operation, "GET", f"/api/orders/{operation['original_order_id']}")
            if (original.get("id") != operation["original_order_id"] or original.get("state") != "completed"
                    or type(original.get("amount")) is not int
                    or original.get("amount") != source_amount_minor or original.get("currency") != operation["currency_code"]
                    or type(original.get("refunded_amount")) is not int
                    or not 0 <= original["refunded_amount"] <= source_amount_minor
                    or (reservation.source_base_minor is not None and (
                        reservation.source_base_minor + reservation.source_tip_minor != source_amount_minor))
                    or not self._revolut_matches_refunded_amount(operation, original["refunded_amount"], reservation)):
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

    def _revolut_matches_refunded_amount(self, operation, refunded_minor, reservation):
        accounted = reservation.verified_before_claim
        if refunded_minor == accounted:
            return True
        if refunded_minor < accounted:
            return False
        # Revolut can count a processing refund in the original's aggregate.
        # Match that amount to exact prior provider records, not a numerical
        # allowance. These reads neither complete refunds nor release capacity.
        # Both sets were frozen under the same reservation locks, preventing a
        # concurrently verified refund from being counted twice.
        for prior in reservation.pending_refunds_before_claim:
            expected = {**operation, **prior}
            detail = self._revolut_api_request(operation, "GET", f"/api/orders/{prior['order_id']}")
            self._validate_refund_response(expected, detail)
            if detail["state"] in {"pending", "processing", "authorised", "completed"}:
                accounted += prior["amount_minor"]
        return refunded_minor == accounted

    def _read_refund_owned(self, operation_id=None, order_uuid=None, payment_line_uuid=None):
        self._check_refund_authority()
        if not operation_id and not (order_uuid and payment_line_uuid):
            raise UserError(_("The refund identifiers are invalid."))
        with self.env.registry.cursor() as cursor:
            env = api.Environment(cursor, self.env.uid, dict(self.env.context), su=self.env.su)
            domain = [("payment_method_id", "=", self.id), ("company_id", "in", self.env.companies.ids)]
            if operation_id:
                domain.append(("id", "=", operation_id))
            if order_uuid:
                domain.append(("order_uuid", "=", str(UUID(order_uuid))))
            if payment_line_uuid:
                domain.append(("payment_line_uuid", "=", str(UUID(payment_line_uuid))))
            if not operation_id and not (order_uuid and payment_line_uuid):
                domain.append(("origin", "=", "odoo"))
            operation = env["pos.revolut.refund.operation"].sudo().search(domain, limit=1)
            if not operation:
                if operation_id:
                    raise AccessError(_("This refund is not accessible."))
                return False
            operation.with_env(env)._check_revolut_register_access()
            source = operation.original_operation_id
            return {"snapshot": operation._snapshot(), "id": operation.id, "origin": operation.origin,
                    "credential_operation_id": source.id,
                    "environment": source.environment, "secret_reference": source.secret_reference,
                    "original_order_id": source.revolut_order_id, "amount_minor": operation.amount_minor,
                    "currency_code": operation.currency_id.name, "idempotency_key": operation.idempotency_key,
                    "order_id": operation.revolut_order_id, "state": operation.state}

    def _update_refund_owned(self, operation_id, values):
        values = dict(values)
        authenticated_detail = values.pop("_authenticated_refund_detail", None)
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context), su=self.env.su)
                    operation = env["pos.revolut.refund.operation"].sudo().browse(operation_id).exists()
                    if not operation or operation.payment_method_id.id != self.id:
                        raise AccessError(_("This refund is not accessible."))
                    operation.with_env(env)._check_revolut_register_access()
                    ReturnAllocation(env).acquire_refund_status(operation)
                    if authenticated_detail is not None:
                        operation._record_provider_refund_time(authenticated_detail)
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

    def revolut_confirm_refund_absence(self, order_uuid, payment_line_uuid, session_id=None):
        """Prove a lost start never reserved this line before allowing a retry."""
        self._check_refund_authority()
        try:
            order_uuid = str(UUID(order_uuid))
            payment_line_uuid = str(UUID(payment_line_uuid))
        except (TypeError, ValueError, AttributeError):
            raise UserError(_("The refund identifiers are invalid.")) from None
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context), su=self.env.su)
                    refunds = env["pos.revolut.refund.operation"].sudo().search([
                        ("company_id", "=", self.company_id.id),
                        ("order_uuid", "=", order_uuid),
                    ])
                    if refunds:
                        for refund in refunds.with_env(env):
                            refund._check_revolut_register_access()
                    else:
                        order = env["pos.order"].sudo().search([
                            ("company_id", "=", self.company_id.id), ("uuid", "=", order_uuid),
                        ], limit=1).with_env(env)
                        if order:
                            order.config_id._check_revolut_register_access(session=order.session_id, order=order)
                        else:
                            # With no persisted return/attempt, the existing POS
                            # session supplies initial authority. Known financial
                            # identity always wins over this caller-selected ID.
                            charges = env["pos.revolut.payment.operation"].sudo().search([
                                ("company_id", "=", self.company_id.id), ("order_uuid", "=", order_uuid),
                            ])
                            for charge in charges.with_env(env):
                                charge._check_revolut_register_access()
                            if charges:
                                return False
                            session = env["pos.session"].browse(session_id).exists() if type(session_id) is int else env["pos.session"]
                            if (not session or session.company_id != self.company_id
                                    or session.state != "opened" or self not in session.config_id.payment_method_ids):
                                raise AccessError(_("Select an authorized POS session before checking refund absence."))
                            session.config_id._check_revolut_register_access(session=session)
                    env["pos.revolut.payment.operation"].sudo()._lock_order(
                        self.company_id.id, order_uuid,
                    )
                    current = refunds.filtered(lambda item: item.payment_line_uuid == payment_line_uuid)
                    if current and current[0].payment_method_id.id != self.id:
                        result = False
                    elif current:
                        result = current[0]._snapshot()
                    elif any(item.state not in {"verified", "failed"} for item in refunds):
                        result = False
                    else:
                        result = {
                            "dispatched": False,
                            "order_uuid": order_uuid,
                            "payment_line_uuid": payment_line_uuid,
                            "start_rejected": "no_refund_attempt",
                        }
                    cursor.commit()
                    return result
            except (SerializationFailure, DeadlockDetected):
                if attempt == 2:
                    raise UserError(_("Could not confirm whether the refund was sent. Check status again.")) from None

    def revolut_poll_refund(self, operation_id, order_uuid=None, payment_line_uuid=None):
        operation = self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        if operation["state"] in {"verified", "failed"}:
            return operation["snapshot"]
        try:
            if not operation["order_id"]:
                if operation["origin"] == "external":
                    raise ValueError("external refund reference is missing")
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
                      "_authenticated_refund_detail": payload,
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
        operation = self._read_refund_owned(operation_id, order_uuid, payment_line_uuid)
        if operation["origin"] != "odoo":
            raise AccessError(_("An external refund has no Odoo return payment identity."))
        return self._update_refund_owned(operation_id, {"state": "unresolved", "local_outcome": "timed_out"})


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _revolut_return_target_minor(self):
        self.ensure_one()
        return ReturnAllocation(self.env).display_target(self)

    def _compute_prices(self):
        # Native recomputation must not overwrite completed pre-upgrade amounts
        # whose product-level adjustment was never recorded as new evidence.
        historical = {order.id: self.env["pos.revolut.payment.operation"].normalize_amount(
            order.currency_id, order.amount_total)[1]
            for order in self if order.state in {"paid", "done", "invoiced"}
            and not order.revolut_return_allocation and order._revolut_return_source()}
        result = super()._compute_prices()
        for order in self:
            target = historical.get(order.id) if order.id in historical else order._revolut_return_target_minor()
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

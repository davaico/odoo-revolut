from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PosRevolutPaymentOperation(models.Model):
    _name = "pos.revolut.payment.operation"
    _inherit = ["pos.revolut.financial.operation.mixin"]
    _description = "Revolut POS Payment Operation"
    _order = "id desc"

    payment_method_id = fields.Many2one(
        "pos.payment.method", required=True, ondelete="restrict", index=True
    )
    company_id = fields.Many2one(
        "res.company", required=True, ondelete="restrict", index=True
    )
    pos_config_id = fields.Many2one(
        "pos.config", required=True, ondelete="restrict", index=True
    )
    pos_session_id = fields.Many2one(
        "pos.session", required=True, ondelete="restrict", index=True
    )
    pos_order_id = fields.Many2one(
        "pos.order", readonly=True, ondelete="restrict", index=True
    )
    pos_payment_id = fields.Many2one(
        "pos.payment", readonly=True, ondelete="restrict", index=True
    )
    order_uuid = fields.Char(required=True, readonly=True, index=True)
    payment_line_uuid = fields.Char(required=True, readonly=True, index=True)
    attempt_number = fields.Integer(required=True, default=1, readonly=True)
    previous_operation_id = fields.Many2one(
        "pos.revolut.payment.operation", readonly=True, ondelete="restrict"
    )
    amount = fields.Monetary(
        required=True, readonly=True, currency_field="currency_id"
    )
    amount_minor = fields.Integer(required=True, readonly=True)
    currency_id = fields.Many2one(
        "res.currency", required=True, readonly=True, ondelete="restrict"
    )
    currency_code = fields.Char(required=True, readonly=True)
    environment = fields.Selection(
        [("sandbox", "Sandbox"), ("production", "Production")],
        required=True,
        readonly=True,
    )
    location_id = fields.Char(required=True, readonly=True)
    terminal_id = fields.Char(required=True, readonly=True)
    fulfilment_type = fields.Selection(
        [("eat_in", "Eat In"), ("take_away", "Take Away")],
        required=True,
        readonly=True,
    )
    secret_reference = fields.Char(required=True, readonly=True)
    state = fields.Selection(
        [
            ("created", "Created"),
            ("dispatching_order", "Creating Revolut Order"),
            ("order_created", "Revolut Order Created"),
            ("dispatching_intent", "Pushing to Terminal"),
            ("pending", "Waiting for Terminal"),
            ("verified", "Verified"),
            ("declined", "Declined"),
            ("failed", "Failed"),
            ("cancelled", "Cancelled"),
            ("unresolved", "Unresolved"),
        ],
        required=True,
        default="created",
        readonly=True,
        index=True,
    )
    revolut_order_id = fields.Char(readonly=True, index=True)
    revolut_payment_intent_id = fields.Char(readonly=True, index=True)
    revolut_payment_id = fields.Char(readonly=True, index=True)
    provider_state = fields.Char(readonly=True)
    retry_safe = fields.Boolean(readonly=True)
    local_outcome = fields.Selection(
        [("interrupted", "Interrupted"), ("timed_out", "Timed Out")], readonly=True
    )
    verified_at = fields.Datetime(readonly=True)
    financial_snapshot = fields.Json(readonly=True)
    next_reconcile_at = fields.Datetime(
        readonly=True, index=True, default=fields.Datetime.now
    )
    reconcile_failures = fields.Integer(readonly=True, default=0)
    blocking_order_key = fields.Char(readonly=True)
    blocking_terminal_key = fields.Char(readonly=True)

    _unique_logical_start = models.Constraint(
        "UNIQUE(company_id, order_uuid, payment_line_uuid, attempt_number)",
        "A Revolut payment attempt can only be created once.",
    )
    _unique_replacement = models.Constraint(
        "UNIQUE(previous_operation_id)", "A Revolut attempt can only be replaced once."
    )
    _unique_blocking_order = models.Constraint(
        "UNIQUE(blocking_order_key)",
        "Another Revolut operation already blocks this order.",
    )
    _unique_blocking_terminal = models.Constraint(
        "UNIQUE(blocking_terminal_key)",
        "Another unresolved payment is using this Revolut terminal.",
    )
    _unique_revolut_order = models.Constraint(
        "UNIQUE(revolut_order_id)", "A Revolut order can only be linked once."
    )
    _unique_revolut_intent = models.Constraint(
        "UNIQUE(revolut_payment_intent_id)",
        "A Revolut payment intent can only be linked once.",
    )
    _unique_revolut_payment = models.Constraint(
        "UNIQUE(revolut_payment_id)",
        "A verified Revolut payment can only be linked once.",
    )
    _unique_pos_payment = models.Constraint(
        "UNIQUE(pos_payment_id)",
        "A verified Revolut operation can only settle one POS payment.",
    )

    _IMMUTABLE_FIELDS = {
        "attempt_number",
        "previous_operation_id",
        "payment_method_id",
        "company_id",
        "pos_config_id",
        "pos_session_id",
        "order_uuid",
        "payment_line_uuid",
        "amount",
        "amount_minor",
        "currency_id",
        "currency_code",
        "environment",
        "location_id",
        "terminal_id",
        "fulfilment_type",
        "secret_reference",
        "financial_snapshot",
    }

    @api.model
    def lock_order(self, company_id, order_uuid):
        # The row is updated by both payment start and POS checkout. Under
        # Odoo's repeatable-read isolation, a competing stale transaction gets
        # a serialization failure and must retry with a fresh snapshot.
        self.env.cr.execute(
            "INSERT INTO pos_revolut_order_lock "
            "(company_id, order_uuid, create_uid, write_uid, create_date, write_date) "
            "VALUES (%s, %s, %s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC') "
            "ON CONFLICT (company_id, order_uuid) DO UPDATE "
            "SET write_date = NOW() AT TIME ZONE 'UTC'",
            [company_id, order_uuid, self.env.uid, self.env.uid],
        )

    @api.model
    def _cron_reconcile_payments(self, batch_size=50):
        # Missing provider IDs require authoritative manual association. They
        # must never cause a replacement order or intent dispatch.
        operations = self.sudo().search(
            [
                ("state", "in", ["pending", "unresolved", "dispatching_intent"]),
                ("revolut_order_id", "!=", False),
                ("revolut_payment_intent_id", "!=", False),
                ("next_reconcile_at", "<=", fields.Datetime.now()),
            ],
            order="next_reconcile_at, id",
            limit=max(1, min(int(batch_size), 50)),
        )
        for operation in operations:
            operation.payment_method_id.sudo().with_company(
                operation.company_id
            ).revolut_poll_payment(
                operation.id, operation.order_uuid, operation.payment_line_uuid
            )

    def _revolut_deployment_terminal_states(self):
        return {"verified", "declined", "failed", "cancelled"}

    def write(self, values):
        if self._IMMUTABLE_FIELDS.intersection(values):
            raise ValidationError(_("Revolut payment operation details are immutable."))
        reference_fields = {
            "revolut_order_id",
            "revolut_payment_intent_id",
            "revolut_payment_id",
            "pos_order_id",
            "pos_payment_id",
        }
        for operation in self:
            for field_name in reference_fields.intersection(values):
                old_value = operation[field_name]
                if operation._fields[field_name].type == "many2one":
                    old_value = old_value.id
                if old_value and values[field_name] != old_value:
                    raise ValidationError(
                        _("Persisted Revolut transaction references are immutable.")
                    )
        return super().write(values)

    def _apply_payment_observation(self, kind, evidence=None):
        """Apply provider or local evidence to the current locked attempt.

        The caller owns the transaction. In particular, manager association and
        its audit share a transaction, while cashier observations are committed
        by their separate transaction adapter.
        """
        self.ensure_one()
        evidence = evidence or {}
        self.env.cr.execute(
            "SELECT id FROM pos_revolut_payment_operation WHERE id = %s FOR UPDATE",
            [self.id],
        )
        self.invalidate_recordset()

        if kind.startswith("dispatch_"):
            return self._apply_dispatch_observation(kind, evidence)
        if kind == "association":
            return self._apply_association_observation(evidence)
        if kind == "legacy_final":
            self._recover_legacy_final()
            return self.operation_snapshot(self)
        if kind == "references_unavailable":
            # Missing references were seen before this lock. A dispatch may
            # still be in flight, or a manager may have just linked them and
            # scheduled reconciliation. That earlier read proves no outcome.
            return self.operation_snapshot(self)
        if (self.state == "verified" or self.retry_safe
                or (kind == "timed_out"
                    and self.state in {"declined", "failed", "cancelled"})):
            return self.operation_snapshot(self)
        if kind == "timed_out" and self.state in {
            "created", "dispatching_order", "order_created", "dispatching_intent"
        }:
            # A local wait limit cannot cancel a server request between its
            # committed steps. Preserve the claimable state; the public
            # snapshot still reports unresolved with a timed-out outcome.
            self.sudo().write({
                "local_outcome": "timed_out", "next_reconcile_at": False,
            })
            return self.operation_snapshot(self)

        values = {}
        if kind == "terminal_check_failed":
            # This check precedes every financial dispatch. An older attempt
            # can have a final failure without retry_safe after an upgrade.
            if self.env["pos.revolut.payment.dispatch"].sudo().search_count(
                [("operation_id", "=", self.id)], limit=1
            ) or self.revolut_order_id or self.revolut_payment_intent_id:
                kind = "unknown"
            else:
                values = {"state": "failed", "provider_state": evidence["reason"]}
        elif kind == "intent":
            intent = evidence
            if (intent.get("id") != self.revolut_payment_intent_id
                    or intent.get("order_id") != self.revolut_order_id):
                kind = "unknown"
            else:
                state = intent.get("state")
                if (state in {"cancelled", "failed"}
                        and not intent.get("payment_id")
                        and self.revolut_payment_id):
                    return self.operation_snapshot(self)
                payment_id = intent.get("payment_id") or self.revolut_payment_id
                if payment_id and (not isinstance(payment_id, str) or not payment_id):
                    kind = "unknown"
                elif payment_id:
                    if self.revolut_payment_id and self.revolut_payment_id != payment_id:
                        kind = "unknown"
                    else:
                        values = {"state": "pending", "provider_state": state,
                                  "revolut_payment_id": payment_id}
                elif state in {"pending", "processing"}:
                    values = {"state": "pending", "provider_state": state}
                elif state in {"cancelled", "failed"}:
                    values = {"state": state, "provider_state": state}
                else:
                    kind = "unknown"
        elif kind == "payment":
            payment = evidence
            if (not self.revolut_payment_id
                    or payment.get("id") != self.revolut_payment_id
                    or payment.get("order_id") != self.revolut_order_id
                    or payment.get("amount") != self.amount_minor
                    or payment.get("currency") != self.currency_code):
                kind = "unknown"
            else:
                state = payment.get("state")
                if state in {"captured", "completed"}:
                    values = {"state": "verified", "provider_state": state,
                              "verified_at": fields.Datetime.now()}
                elif state in {"declined", "failed", "cancelled"}:
                    values = {"state": state, "provider_state": state}
                elif state in {"authorised", "capture_started", "declining",
                               "cancelling", "failing"}:
                    values = {"state": "pending", "provider_state": state}
                else:
                    kind = "unknown"
        if kind in {"unknown", "interrupted", "timed_out"}:
            failures = self.reconcile_failures + (kind == "interrupted")
            delay = (30 if kind == "timed_out" else
                     min(60 * 2 ** min(failures - 1, 5), 1800) if failures else 300)
            values = {
                "state": "unresolved",
                "local_outcome": kind if kind != "unknown" else False,
                "reconcile_failures": failures,
                "next_reconcile_at": (
                    fields.Datetime.now() + timedelta(seconds=delay)
                    if self.revolut_order_id and self.revolut_payment_intent_id else False
                ),
            }
        else:
            state = values["state"]
            values["local_outcome"] = False
            if state in {"verified", "declined", "failed", "cancelled"}:
                values.update({"next_reconcile_at": False, "reconcile_failures": 0,
                               "blocking_terminal_key": False,
                               "blocking_order_key": False})
                if state != "verified":
                    values["retry_safe"] = True
            else:
                values.update({
                    "next_reconcile_at": fields.Datetime.now() + timedelta(seconds=30),
                    "reconcile_failures": 0,
                })
        self.sudo().write(values)
        return self.operation_snapshot(self)

    def _recover_legacy_final(self):
        if self.state not in {"declined", "failed", "cancelled"} or self.retry_safe:
            return
        confirmed = (
            self.provider_state == self.state and self.revolut_order_id
            and (self.revolut_payment_id or (
                self.state in {"failed", "cancelled"}
                and self.revolut_payment_intent_id
            ))
        )
        pre_dispatch = (
            self.state == "failed"
            and self.provider_state in {"terminal_unavailable", "terminal_check_failed"}
            and not self.revolut_order_id and not self.revolut_payment_intent_id
            and not self.revolut_payment_id
            and not self.env["pos.revolut.payment.dispatch"].sudo().search_count(
                [("operation_id", "=", self.id)], limit=1
            )
        )
        if confirmed or pre_dispatch:
            self.sudo().write({"retry_safe": True, "blocking_order_key": False,
                               "blocking_terminal_key": False,
                               "next_reconcile_at": False, "reconcile_failures": 0})

    def _apply_dispatch_observation(self, kind, evidence):
        action = kind.removeprefix("dispatch_")
        dispatch = self.env["pos.revolut.payment.dispatch"].sudo().search([
            ("operation_id", "=", self.id), ("action", "=", action)
        ], limit=1)
        if not dispatch:
            raise UserError(_("The Revolut dispatch was not claimed."))
        if evidence.get("uncertain"):
            if not dispatch.completed_at:
                dispatch.write({"completed_at": fields.Datetime.now(),
                                "outcome": "unresolved"})
            if self.state != "verified" and not self.retry_safe:
                return self._apply_payment_observation(
                    evidence.get("cause", "unknown")
                )
            return self.operation_snapshot(self)

        reference = evidence.get("reference")
        if action in {"create_order", "create_intent"}:
            if not isinstance(reference, str) or not reference:
                raise UserError(_("Revolut returned no transaction reference."))
            field_name = ("revolut_order_id" if action == "create_order"
                          else "revolut_payment_intent_id")
            if self[field_name] and self[field_name] != reference:
                raise UserError(_("A different Revolut reference is already linked."))
            if action == "create_intent" and not self.revolut_order_id:
                raise UserError(_("The Revolut order reference is missing."))
            already_linked = bool(self[field_name])
            if not already_linked:
                self.sudo().write({field_name: reference})
            claimed_state = ("dispatching_order" if action == "create_order"
                             else "dispatching_intent")
            if (self.state == claimed_state
                    or (self.state == "unresolved" and not already_linked
                        and self.local_outcome == "timed_out")
                    or (action == "create_order" and self.state == "unresolved"
                        and already_linked and not self.revolut_payment_intent_id)):
                # A local timeout does not refute this claimed request. Its
                # valid acknowledgement may continue the original sequence.
                # A manager's matching order-only association is likewise
                # incomplete evidence and cannot stop the first intent.
                values = {
                    "state": "order_created" if action == "create_order" else "pending",
                    **({"provider_state": evidence.get("state") or "pending"}
                       if action == "create_intent" else {}),
                }
                if action == "create_intent" and not self.next_reconcile_at:
                    values["next_reconcile_at"] = (
                        fields.Datetime.now() + timedelta(seconds=30)
                    )
                self.sudo().write(values)
        dispatch.write({"completed_at": fields.Datetime.now(),
                        "outcome": "succeeded", "provider_reference": reference})
        return self.operation_snapshot(self)

    def _apply_association_observation(self, evidence):
        order_reference = evidence["order_reference"]
        intent_reference = evidence.get("intent_reference")
        if self.state == "verified" or self.retry_safe:
            raise UserError(_("This Revolut attempt already has a final outcome."))
        if self.revolut_order_id and self.revolut_order_id != order_reference:
            raise UserError(_("A different Revolut order is already linked."))
        if (intent_reference and self.revolut_payment_intent_id
                and self.revolut_payment_intent_id != intent_reference):
            raise UserError(_("A different Revolut payment intent is already linked."))
        order = evidence["order"]
        metadata = order.get("metadata")
        if (order.get("id") != order_reference
                or order.get("amount") != self.amount_minor
                or order.get("currency") != self.currency_code
                or order.get("location_id") != self.location_id
                or not isinstance(metadata, dict)
                or metadata.get("pos_order_uuid") != self.order_uuid
                or metadata.get("pos_payment_line_uuid") != self.payment_line_uuid):
            raise UserError(_("The Revolut order does not match the original POS payment."))
        intent = evidence.get("intent")
        if intent_reference and (
            not isinstance(intent, dict)
            or intent.get("id") != intent_reference
            or intent.get("order_id") != order_reference
            or intent.get("amount") != self.amount_minor
            or intent.get("currency") != self.currency_code
            or intent.get("terminal_id") != self.terminal_id
        ):
            raise UserError(_("The Revolut intent does not match the original POS payment."))
        ownership_domain = [("id", "!=", self.id)]
        if intent_reference:
            ownership_domain.append("|")
        ownership_domain.append(("revolut_order_id", "=", order_reference))
        if intent_reference:
            ownership_domain.append(
                ("revolut_payment_intent_id", "=", intent_reference)
            )
        owned = self.sudo().search(ownership_domain, limit=1)
        if owned:
            raise UserError(_("A Revolut reference is already owned by another attempt."))
        # An order-only association confirms the order reference but does not
        # invalidate this request's already claimed creation sequence.
        state = self.state if (
            not intent_reference
            and self.state in {"dispatching_order", "order_created",
                               "dispatching_intent"}
        ) else "unresolved"
        values = {"revolut_order_id": order_reference, "state": state}
        if intent_reference:
            values.update({"revolut_payment_intent_id": intent_reference,
                           "next_reconcile_at": fields.Datetime.now()})
        self.sudo().write(values)
        return self.operation_snapshot(self)

    @api.model
    def normalize_financial_snapshot(self, data):
        """Compare the cart sent before dispatch with the final POS order."""
        if not isinstance(data, dict) or not isinstance(data.get("lines"), list):
            raise UserError(_("The Revolut order contents are unavailable."))

        def decimal_text(value):
            number = Decimal(str(value))
            if not number.is_finite():
                raise ValueError("non-finite POS amount")
            return format(number.normalize(), "f")

        try:
            lines = []
            for raw_line in data["lines"]:
                line = raw_line[2] if isinstance(raw_line, (list, tuple)) else raw_line
                if (
                    not isinstance(line, dict)
                    or not line.get("uuid")
                    or not line.get("product_id")
                ):
                    raise ValueError("invalid POS line")
                taxes = line.get("tax_ids") or []
                if taxes and isinstance(taxes[0], (list, tuple)):
                    taxes = taxes[0][2]
                lines.append({
                    "uuid": line["uuid"],
                    "product_id": int(line["product_id"]),
                    "qty": decimal_text(line["qty"]),
                    "price_unit": decimal_text(line["price_unit"]),
                    "discount": decimal_text(line.get("discount") or 0),
                    "tax_ids": sorted(int(tax_id) for tax_id in taxes),
                })
            if not lines or len({line["uuid"] for line in lines}) != len(lines):
                raise ValueError("missing or duplicate POS lines")
            return {
                "pricelist_id": int(data.get("pricelist_id") or 0),
                "fiscal_position_id": int(data.get("fiscal_position_id") or 0),
                "lines": sorted(lines, key=lambda line: line["uuid"]),
            }
        except (KeyError, TypeError, ValueError, ArithmeticError):
            raise UserError(_("The Revolut order contents are invalid.")) from None

    @api.model
    def normalize_amount(self, currency, amount):
        amount_decimal = Decimal(str(amount))
        exponent = Decimal(1).scaleb(-currency.decimal_places)
        normalized = amount_decimal.quantize(exponent, rounding=ROUND_HALF_UP)
        return normalized, int(normalized.scaleb(currency.decimal_places))

    @api.model
    def operation_snapshot(self, operation):
        public_state = operation.state
        if public_state in {
            "created",
            "dispatching_order",
            "order_created",
            "dispatching_intent",
        }:
            public_state = "unresolved"
        return {
            "operation_id": operation.id,
            "state": public_state,
            "order_id": operation.revolut_order_id or False,
            "payment_intent_id": operation.revolut_payment_intent_id or False,
            "payment_id": operation.revolut_payment_id or False,
            "provider_state": operation.provider_state or False,
            "retry_safe": operation.retry_safe,
            "local_outcome": operation.local_outcome or False,
        }

class PosRevolutPaymentDispatch(models.Model):
    _name = "pos.revolut.payment.dispatch"
    _description = "Revolut POS Mutating Dispatch Claim"
    _order = "id desc"

    operation_id = fields.Many2one(
        "pos.revolut.payment.operation",
        required=True,
        readonly=True,
        ondelete="restrict",
        index=True,
    )
    action = fields.Selection(
        [("create_order", "Create Order"), ("create_intent", "Create Intent"),
         ("cancel_intent", "Cancel Intent")],
        required=True,
        readonly=True,
    )
    claimed_at = fields.Datetime(
        required=True, readonly=True, default=fields.Datetime.now
    )
    completed_at = fields.Datetime(readonly=True)
    outcome = fields.Selection(
        [("succeeded", "Succeeded"), ("unresolved", "Unresolved")],
        readonly=True,
    )
    provider_reference = fields.Char(readonly=True)

    _unique_operation_action = models.Constraint(
        "UNIQUE(operation_id, action)",
        "A Revolut mutating action can only be claimed once.",
    )

    def write(self, values):
        if {"operation_id", "action", "claimed_at"}.intersection(values):
            raise UserError(_("Revolut dispatch claims are immutable."))
        return super().write(values)


class PosRevolutOrderLock(models.Model):
    _name = "pos.revolut.order.lock"
    _description = "Revolut POS Order Transaction Lock"

    company_id = fields.Many2one("res.company", required=True, ondelete="cascade")
    order_uuid = fields.Char(required=True)

    _unique_order = models.Constraint(
        "UNIQUE(company_id, order_uuid)",
        "A POS order can only have one Revolut transaction lock.",
    )

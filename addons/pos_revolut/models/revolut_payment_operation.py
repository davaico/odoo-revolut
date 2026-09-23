from decimal import Decimal, ROUND_HALF_UP

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
    verified_at = fields.Datetime(readonly=True)
    blocking_order_key = fields.Char(readonly=True)
    blocking_terminal_key = fields.Char(readonly=True)

    _unique_logical_start = models.Constraint(
        "UNIQUE(company_id, order_uuid, payment_line_uuid)",
        "A Revolut payment line can only have one operation.",
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
    }

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
        [("create_order", "Create Order"), ("create_intent", "Create Intent")],
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

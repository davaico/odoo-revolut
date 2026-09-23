import os
import re
from datetime import timedelta
from uuid import UUID

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


REVOLUT_SECRET_REFERENCE_PATTERN = re.compile(r"ODOO_REVOLUT_SECRET_[A-Z0-9_]+")
REVOLUT_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
REVOLUT_API_VERSION = "2026-08-17"
REVOLUT_API_HOSTS = {
    "sandbox": "https://sandbox-merchant.revolut.com",
    "production": "https://merchant.revolut.com",
}
REVOLUT_REQUEST_TIMEOUT_SECONDS = 10
REVOLUT_SUCCESS_STATES = {"captured", "completed"}
REVOLUT_PAYMENT_TRANSITIONAL_STATES = {
    "authorised",
    "capture_started",
    "declining",
    "cancelling",
    "failing",
}


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    revolut_environment = fields.Selection(
        selection=[("sandbox", "Sandbox"), ("production", "Production")],
        string="Revolut Environment",
        default="sandbox",
        copy=False,
        groups="point_of_sale.group_pos_manager",
    )
    revolut_location_id = fields.Char(
        string="Revolut Location ID",
        copy=False,
        groups="point_of_sale.group_pos_manager",
    )
    revolut_terminal_id = fields.Char(
        string="Revolut Terminal ID",
        copy=False,
        groups="point_of_sale.group_pos_manager",
    )
    revolut_fulfilment_type = fields.Selection(
        selection=[("eat_in", "Eat In"), ("take_away", "Take Away")],
        string="Revolut Fulfilment",
        copy=False,
        groups="point_of_sale.group_pos_manager",
        help=(
            "The restaurant fulfilment sent to Revolut. Retail terminal "
            "fulfilment is not enabled until Revolut confirms its contract."
        ),
    )
    revolut_secret_reference = fields.Char(
        string="Revolut Secret Reference",
        copy=False,
        groups="point_of_sale.group_pos_manager",
        help=(
            "Name of a server environment variable in the "
            "ODOO_REVOLUT_SECRET_ namespace. The secret itself is never stored."
        ),
    )

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [("revolut", "Revolut")]

    @api.constrains("use_payment_terminal", "revolut_secret_reference")
    def _check_revolut_secret_reference(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if not REVOLUT_SECRET_REFERENCE_PATTERN.fullmatch(
                payment_method.revolut_secret_reference or ""
            ):
                raise ValidationError(
                    _(
                        "The Revolut secret reference must name a variable in the "
                        "ODOO_REVOLUT_SECRET_ namespace."
                    )
                )

    @api.constrains(
        "use_payment_terminal", "revolut_location_id", "revolut_terminal_id"
    )
    def _check_revolut_identifiers(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if not all(
                REVOLUT_UUID_PATTERN.fullmatch(identifier or "")
                for identifier in (
                    payment_method.revolut_location_id,
                    payment_method.revolut_terminal_id,
                )
            ):
                raise ValidationError(
                    _("Revolut location and terminal IDs must be valid UUIDs.")
                )

    @api.constrains("use_payment_terminal", "revolut_environment")
    def _check_revolut_environment(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if payment_method.revolut_environment not in REVOLUT_API_HOSTS:
                raise ValidationError(
                    _("Select Sandbox or Production for the Revolut environment.")
                )

    @api.constrains("use_payment_terminal", "revolut_fulfilment_type")
    def _check_revolut_fulfilment_type(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if payment_method.revolut_fulfilment_type not in {
                "eat_in",
                "take_away",
            }:
                raise ValidationError(
                    _(
                        "Select Eat In or Take Away. Revolut has not confirmed "
                        "a retail fulfilment value."
                    )
                )

    def action_revolut_check_connection(self):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(_("Only Point of Sale managers can check a terminal."))
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(_("You cannot check a terminal for another company."))
        if self.use_payment_terminal != "revolut":
            raise UserError(_("This payment method does not use Revolut."))

        if not REVOLUT_SECRET_REFERENCE_PATTERN.fullmatch(
            self.revolut_secret_reference or ""
        ):
            raise UserError(_("The Revolut secret reference is invalid."))
        secret = os.environ.get(self.revolut_secret_reference)
        if not secret:
            raise UserError(
                _("The Revolut credential is not available on the Odoo server.")
            )

        try:
            response = requests.get(
                f"{REVOLUT_API_HOSTS[self.revolut_environment]}/api/terminals",
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Revolut-Api-Version": REVOLUT_API_VERSION,
                },
                params={
                    "operation_mode": "pos",
                    "location_id": self.revolut_location_id,
                },
                timeout=REVOLUT_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            raise UserError(
                _("The Revolut terminal check could not be completed.")
            ) from None

        terminals = payload.get("terminals") if isinstance(payload, dict) else None
        if not isinstance(terminals, list):
            raise UserError(_("Revolut returned an invalid terminal response."))
        terminal = next(
            (
                item
                for item in terminals
                if isinstance(item, dict)
                and item.get("id") == self.revolut_terminal_id
            ),
            None,
        )
        if not terminal:
            raise UserError(
                _("The configured terminal was not found at this Revolut location.")
            )
        if terminal.get("online") is not True:
            raise UserError(_("The configured Revolut terminal is offline."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Revolut terminal connected"),
                "message": _(
                    "%(terminal)s is online.",
                    terminal=terminal.get("name") or self.revolut_terminal_id,
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def _validate_revolut_pos_request(
        self, session_id, order_uuid, payment_line_uuid, amount, currency_id
    ):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale users can start terminal payments."))
        self.check_access("read")
        if self.use_payment_terminal != "revolut":
            raise UserError(_("This payment method does not use Revolut."))
        if self.company_id not in self.env.companies:
            raise AccessError(_("You cannot use a terminal from another company."))
        session = self.env["pos.session"].browse(session_id).exists()
        if (
            not session
            or session.company_id != self.company_id
            or self not in session.config_id.payment_method_ids
        ):
            raise AccessError(_("This Revolut terminal is not available in the POS session."))
        if session.state != "opened":
            raise UserError(_("The Point of Sale session is not open."))
        if not session.config_id.auto_validate_terminal_payment:
            raise UserError(
                _("Enable automatic terminal payment validation for this Point of Sale.")
            )
        currency = self.env["res.currency"].browse(currency_id).exists()
        if not currency or currency != session.currency_id:
            raise UserError(_("The payment currency does not match the POS session."))
        try:
            order_uuid = str(UUID(order_uuid))
            payment_line_uuid = str(UUID(payment_line_uuid))
        except (TypeError, ValueError, AttributeError):
            raise UserError(_("The POS payment identifiers are invalid.")) from None
        if not os.environ.get(self.sudo().revolut_secret_reference or ""):
            raise UserError(_("The Revolut credential is not available on the Odoo server."))
        amount_decimal = self.env["pos.revolut.payment.operation"].normalize_amount(
            currency, amount
        )[0]
        if amount_decimal <= 0:
            raise UserError(_("The Revolut payment amount must be positive."))
        normalized_amount, amount_minor = self.env[
            "pos.revolut.payment.operation"
        ].normalize_amount(currency, amount)
        return session, currency, normalized_amount, amount_minor, order_uuid, payment_line_uuid

    def _revolut_operation_values(
        self,
        session,
        currency,
        amount,
        amount_minor,
        order_uuid,
        payment_line_uuid,
        financial_snapshot=False,
    ):
        # The caller's POS permissions and ownership have already been checked.
        # Configuration stays manager-only; only the server reads it for dispatch.
        configuration = self.sudo()
        return {
            "payment_method_id": self.id,
            "company_id": self.company_id.id,
            "pos_config_id": session.config_id.id,
            "pos_session_id": session.id,
            "order_uuid": order_uuid,
            "payment_line_uuid": payment_line_uuid,
            "amount": float(amount),
            "amount_minor": amount_minor,
            "currency_id": currency.id,
            "currency_code": currency.name,
            "environment": configuration.revolut_environment,
            "location_id": configuration.revolut_location_id,
            "terminal_id": configuration.revolut_terminal_id,
            "fulfilment_type": configuration.revolut_fulfilment_type,
            "secret_reference": configuration.revolut_secret_reference,
            "blocking_order_key": f"{self.company_id.id}:{order_uuid}",
            "financial_snapshot": (
                self.env["pos.revolut.payment.operation"].normalize_financial_snapshot(
                    financial_snapshot
                ) if financial_snapshot else False
            ),
            "blocking_terminal_key": (
                f"{self.company_id.id}:{configuration.revolut_environment}:"
                f"{configuration.revolut_terminal_id}"
            ),
        }

    def _create_revolut_operation_owned(self, values, previous_operation_id=False):
        logical_domain = [
            ("company_id", "=", values["company_id"]),
            ("order_uuid", "=", values["order_uuid"]),
            ("payment_line_uuid", "=", values["payment_line_uuid"]),
        ]
        # Fresh owned transactions observe the winner after uniqueness or
        # repeatable-read serialization conflicts. Nothing is dispatched here.
        for _attempt in range(3):
            with self.env.registry.cursor() as cursor:
                owned_env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                operations = owned_env["pos.revolut.payment.operation"].sudo()
                try:
                    previous = operations.browse()
                    if previous_operation_id:
                        previous = operations.search(
                            logical_domain + [("id", "=", previous_operation_id)], limit=1
                        )
                        if not previous or previous.payment_method_id.id != self.id:
                            raise AccessError(_("The prior Revolut attempt is not accessible."))
                        cursor.execute(
                            "SELECT id FROM pos_revolut_payment_operation WHERE id = %s FOR UPDATE",
                            [previous.id],
                        )
                        previous.invalidate_recordset()
                        operation = operations.search(
                            [("previous_operation_id", "=", previous.id)], limit=1
                        )
                    else:
                        operation = operations.search(logical_domain, limit=1)
                    if operation:
                        if (
                            operation.amount_minor != values["amount_minor"]
                            or operation.currency_id.id != values["currency_id"]
                            or operation.pos_session_id.id != values["pos_session_id"]
                            or operation.payment_method_id.id != self.id
                            or (
                                operation.financial_snapshot
                                and operation.financial_snapshot != values["financial_snapshot"]
                            )
                        ):
                            raise UserError(_("The existing Revolut attempt has different payment details."))
                        snapshot = operations.operation_snapshot(operation)
                        cursor.commit()
                        return snapshot, False
                    if previous:
                        if not previous.retry_safe:
                            raise UserError(_("Reconcile the previous Revolut attempt before retrying."))
                        values = {
                            **values,
                            "previous_operation_id": previous.id,
                            "attempt_number": previous.attempt_number + 1,
                        }
                    blocker = operations.search(
                        [
                            "|",
                            ("blocking_order_key", "=", values["blocking_order_key"]),
                            ("blocking_terminal_key", "=", values["blocking_terminal_key"]),
                        ],
                        limit=1,
                    )
                    if blocker:
                        raise UserError(_("An existing Revolut payment blocks this order or terminal."))
                    operation = operations.create(values)
                    snapshot = operations.operation_snapshot(operation)
                    cursor.commit()
                    return snapshot, True
                except (IntegrityError, SerializationFailure):
                    cursor.rollback()
        raise UserError(_("Another Revolut request is in progress. Check its status."))

    def _read_revolut_operation_owned(
        self, operation_id, order_uuid=None, payment_line_uuid=None
    ):
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale users can access terminal payments."))
        self.check_access("read")
        registry = self.env.registry
        context = dict(self.env.context)
        user_id = self.env.uid
        with registry.cursor() as cursor:
            owned_env = api.Environment(cursor, user_id, context)
            operation = owned_env["pos.revolut.payment.operation"].sudo().browse(
                operation_id
            ).exists()
            if (
                not operation
                or operation.payment_method_id.id != self.id
                or operation.company_id not in owned_env.companies
                or (order_uuid and operation.order_uuid != order_uuid)
                or (payment_line_uuid and operation.payment_line_uuid != payment_line_uuid)
            ):
                raise AccessError(_("The Revolut payment operation is not accessible."))
            has_dispatch = False
            if operation.state == "failed" and not operation.retry_safe:
                has_dispatch = bool(owned_env["pos.revolut.payment.dispatch"].sudo().search_count(
                    [("operation_id", "=", operation.id)], limit=1
                ))
            data = {
                "id": operation.id,
                "has_dispatch": has_dispatch,
                "state": operation.state,
                "environment": operation.environment,
                "location_id": operation.location_id,
                "terminal_id": operation.terminal_id,
                "fulfilment_type": operation.fulfilment_type,
                "secret_reference": operation.secret_reference,
                "amount_minor": operation.amount_minor,
                "currency_code": operation.currency_code,
                "order_id": operation.revolut_order_id,
                "payment_intent_id": operation.revolut_payment_intent_id,
                "payment_id": operation.revolut_payment_id,
                "config_name": operation.pos_config_id.name,
                "snapshot": owned_env[
                    "pos.revolut.payment.operation"
                ].operation_snapshot(operation),
            }
            cursor.commit()
        return data

    def _claim_revolut_dispatch_owned(self, operation_id, action, state):
        registry = self.env.registry
        context = dict(self.env.context)
        user_id = self.env.uid
        with registry.cursor() as cursor:
            try:
                owned_env = api.Environment(cursor, user_id, context)
                cursor.execute(
                    "SELECT id FROM pos_revolut_payment_operation "
                    "WHERE id = %s FOR UPDATE",
                    [operation_id],
                )
                operation = owned_env["pos.revolut.payment.operation"].sudo().browse(
                    operation_id
                )
                if action == "cancel_intent" and (
                    operation.state != "pending"
                    or operation.provider_state != "pending"
                    or operation.revolut_payment_id
                ):
                    return False
                dispatches = owned_env["pos.revolut.payment.dispatch"].sudo()
                if dispatches.search_count(
                    [("operation_id", "=", operation_id), ("action", "=", action)]
                ):
                    cursor.commit()
                    return False
                try:
                    with cursor.savepoint():
                        dispatches.create(
                            {"operation_id": operation_id, "action": action}
                        )
                except IntegrityError:
                    return False
                operation.write({"state": state})
                cursor.commit()
            except SerializationFailure:
                cursor.rollback()
                return False
        return True

    def _complete_revolut_dispatch_owned(
        self, operation_id, action, provider_reference, operation_values
    ):
        registry = self.env.registry
        context = dict(self.env.context)
        user_id = self.env.uid
        with registry.cursor() as cursor:
            owned_env = api.Environment(cursor, user_id, context)
            cursor.execute(
                "SELECT id FROM pos_revolut_payment_operation WHERE id = %s FOR UPDATE",
                [operation_id],
            )
            operation = owned_env["pos.revolut.payment.operation"].sudo().browse(
                operation_id
            )
            dispatch = owned_env["pos.revolut.payment.dispatch"].sudo().search(
                [("operation_id", "=", operation_id), ("action", "=", action)],
                limit=1,
            )
            dispatch.write(
                {
                    "completed_at": fields.Datetime.now(),
                    "outcome": "succeeded",
                    "provider_reference": provider_reference,
                }
            )
            operation.write(operation_values)
            snapshot = owned_env[
                "pos.revolut.payment.operation"
            ].operation_snapshot(operation)
            cursor.commit()
        return snapshot

    def _update_revolut_operation_owned(
        self, operation_id, values, release_terminal=False, intent_only=False
    ):
        registry = self.env.registry
        context = dict(self.env.context)
        user_id = self.env.uid
        with registry.cursor() as cursor:
            owned_env = api.Environment(cursor, user_id, context)
            cursor.execute(
                "SELECT id FROM pos_revolut_payment_operation WHERE id = %s FOR UPDATE",
                [operation_id],
            )
            operation = owned_env["pos.revolut.payment.operation"].sudo().browse(
                operation_id
            )
            # A slower poll, timeout or cancellation must never overwrite an
            # authoritative final outcome committed by another request.
            if operation.state == "verified" or operation.retry_safe:
                return owned_env["pos.revolut.payment.operation"].operation_snapshot(operation)
            # The HTTP read used an earlier snapshot. A competing poll may have
            # saved a payment reference while this intent response was in flight.
            # Intent-only failure cannot release a payment awaiting verification.
            if intent_only and operation.revolut_payment_id:
                return owned_env["pos.revolut.payment.operation"].operation_snapshot(operation)
            if values.get("state") in {"declined", "failed", "cancelled"}:
                values = {**values, "retry_safe": True, "blocking_order_key": False}
            if values.get("state") != "unresolved":
                values = {**values, "local_outcome": False}
            if values.get("state") in {"verified", "declined", "failed", "cancelled"}:
                values = {**values, "next_reconcile_at": False, "reconcile_failures": 0}
            else:
                values = {
                    **values,
                    "next_reconcile_at": fields.Datetime.now() + timedelta(seconds=30),
                    "reconcile_failures": 0,
                }
            if release_terminal:
                values = {**values, "blocking_terminal_key": False}
            operation.write(values)
            snapshot = owned_env[
                "pos.revolut.payment.operation"
            ].operation_snapshot(operation)
            cursor.commit()
        return snapshot

    def _mark_revolut_unresolved_owned(self, operation_id, action=None, local_outcome=False):
        registry = self.env.registry
        context = dict(self.env.context)
        user_id = self.env.uid
        with registry.cursor() as cursor:
            owned_env = api.Environment(cursor, user_id, context)
            cursor.execute(
                "SELECT id FROM pos_revolut_payment_operation WHERE id = %s FOR UPDATE",
                [operation_id],
            )
            operation = owned_env["pos.revolut.payment.operation"].sudo().browse(
                operation_id
            )
            if operation.state != "verified" and not operation.retry_safe:
                failures = operation.reconcile_failures + bool(local_outcome == "interrupted")
                if local_outcome == "timed_out":
                    delay = 30
                elif failures:
                    delay = min(60 * 2 ** min(failures - 1, 5), 1800)
                else:
                    delay = 300
                operation.write({
                    "state": "unresolved",
                    "local_outcome": local_outcome,
                    "reconcile_failures": failures,
                    "next_reconcile_at": (
                        fields.Datetime.now() + timedelta(seconds=delay)
                        if operation.revolut_order_id and operation.revolut_payment_intent_id
                        else False
                    ),
                })
            if action:
                dispatch = owned_env["pos.revolut.payment.dispatch"].sudo().search(
                    [("operation_id", "=", operation_id), ("action", "=", action)],
                    limit=1,
                )
                if dispatch and not dispatch.completed_at:
                    dispatch.write(
                        {
                            "completed_at": fields.Datetime.now(),
                            "outcome": "unresolved",
                        }
                    )
            snapshot = owned_env[
                "pos.revolut.payment.operation"
            ].operation_snapshot(operation)
            cursor.commit()
        return snapshot

    def _revolut_api_request(self, operation, method, path, **kwargs):
        secret = os.environ.get(operation["secret_reference"])
        if not secret:
            raise UserError(_("The Revolut credential is not available on the Odoo server."))
        response = requests.request(
            method,
            f"{REVOLUT_API_HOSTS[operation['environment']]}{path}",
            headers={
                "Authorization": f"Bearer {secret}",
                "Revolut-Api-Version": REVOLUT_API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=REVOLUT_REQUEST_TIMEOUT_SECONDS,
            **kwargs,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("invalid Revolut response")
        return payload

    def _revolut_terminal_is_eligible(self, operation):
        payload = self._revolut_api_request(
            operation,
            "GET",
            "/api/terminals",
            params={
                "operation_mode": "pos",
                "location_id": operation["location_id"],
            },
        )
        terminals = payload.get("terminals")
        if not isinstance(terminals, list):
            return False
        terminal = next(
            (
                item
                for item in terminals
                if isinstance(item, dict) and item.get("id") == operation["terminal_id"]
            ),
            None,
        )
        return bool(
            terminal
            and terminal.get("online") is True
            and terminal.get("operation_mode", "pos") == "pos"
            and terminal.get("location_id", operation["location_id"])
            == operation["location_id"]
        )

    def revolut_start_payment(
        self, session_id, order_uuid, payment_line_uuid, amount, currency_id,
        previous_operation_id=False, financial_snapshot=False,
    ):
        self.ensure_one()
        (
            session,
            currency,
            normalized_amount,
            amount_minor,
            order_uuid,
            payment_line_uuid,
        ) = self._validate_revolut_pos_request(
            session_id, order_uuid, payment_line_uuid, amount, currency_id
        )
        if not financial_snapshot:
            raise UserError(_("The original POS order contents are required before payment."))
        operation_values = self._revolut_operation_values(
            session,
            currency,
            normalized_amount,
            amount_minor,
            order_uuid,
            payment_line_uuid,
            financial_snapshot,
        )
        snapshot, created = self._create_revolut_operation_owned(
            operation_values, previous_operation_id
        )
        if not created:
            return snapshot
        operation = self._read_revolut_operation_owned(snapshot["operation_id"])
        try:
            if not self._revolut_terminal_is_eligible(operation):
                return self._update_revolut_operation_owned(
                    operation["id"],
                    {"state": "failed", "provider_state": "terminal_unavailable"},
                    release_terminal=True,
                )
        except (requests.RequestException, ValueError, UserError):
            return self._update_revolut_operation_owned(
                operation["id"],
                {"state": "failed", "provider_state": "terminal_check_failed"},
                release_terminal=True,
            )
        if not self._claim_revolut_dispatch_owned(
            operation["id"], "create_order", "dispatching_order"
        ):
            return self._read_revolut_operation_owned(operation["id"])["snapshot"]
        try:
            order_payload = self._revolut_api_request(
                operation,
                "POST",
                "/api/orders",
                json={
                    "amount": operation["amount_minor"],
                    "currency": operation["currency_code"],
                    "channel": "pos",
                    "location_id": operation["location_id"],
                    "fulfilment_type": operation["fulfilment_type"],
                    "capture_mode": "manual",
                    "metadata": {"pos_partner_name": operation["config_name"]},
                },
            )
            revolut_order_id = order_payload.get("id")
            if not isinstance(revolut_order_id, str) or not revolut_order_id:
                raise ValueError("missing Revolut order ID")
            self._complete_revolut_dispatch_owned(
                operation["id"],
                "create_order",
                revolut_order_id,
                {"state": "order_created", "revolut_order_id": revolut_order_id},
            )
        except (requests.RequestException, ValueError, UserError) as error:
            return self._mark_revolut_unresolved_owned(
                operation["id"], "create_order",
                local_outcome="interrupted" if isinstance(error, requests.RequestException) else False,
            )
        operation = self._read_revolut_operation_owned(operation["id"])
        if not self._claim_revolut_dispatch_owned(
            operation["id"], "create_intent", "dispatching_intent"
        ):
            return self._read_revolut_operation_owned(operation["id"])["snapshot"]
        try:
            intent_payload = self._revolut_api_request(
                operation,
                "POST",
                f"/api/orders/{operation['order_id']}/payment-intents",
                json={
                    "amount": operation["amount_minor"],
                    "terminal_id": operation["terminal_id"],
                },
            )
            payment_intent_id = intent_payload.get("id")
            if not isinstance(payment_intent_id, str) or not payment_intent_id:
                raise ValueError("missing Revolut payment intent ID")
            return self._complete_revolut_dispatch_owned(
                operation["id"],
                "create_intent",
                payment_intent_id,
                {
                    "state": "pending",
                    "provider_state": intent_payload.get("state") or "pending",
                    "revolut_payment_intent_id": payment_intent_id,
                },
            )
        except (requests.RequestException, ValueError, UserError) as error:
            return self._mark_revolut_unresolved_owned(
                operation["id"], "create_intent",
                local_outcome="interrupted" if isinstance(error, requests.RequestException) else False,
            )

    def revolut_find_payment(self, order_uuid, payment_line_uuid):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_user"):
            raise AccessError(_("Only Point of Sale users can read terminal payments."))
        self.check_access("read")
        if self.use_payment_terminal != "revolut":
            raise UserError(_("This payment method does not use Revolut."))
        if self.company_id not in self.env.companies:
            raise AccessError(_("You cannot use a terminal from another company."))
        try:
            order_uuid = str(UUID(order_uuid))
            payment_line_uuid = str(UUID(payment_line_uuid))
        except (TypeError, ValueError, AttributeError):
            raise UserError(_("The POS payment identifiers are invalid.")) from None
        operation = self.env["pos.revolut.payment.operation"].sudo().search(
            [
                ("payment_method_id", "=", self.id),
                ("company_id", "=", self.company_id.id),
                ("order_uuid", "=", order_uuid),
                ("payment_line_uuid", "=", payment_line_uuid),
            ],
            limit=1,
        )
        if not operation:
            return False
        return self.env[
            "pos.revolut.payment.operation"
        ].operation_snapshot(operation)

    def revolut_poll_payment(self, operation_id, order_uuid, payment_line_uuid):
        self.ensure_one()
        try:
            order_uuid = str(UUID(order_uuid))
            payment_line_uuid = str(UUID(payment_line_uuid))
        except (TypeError, ValueError, AttributeError):
            raise UserError(_("The POS payment identifiers are invalid.")) from None
        operation = self._read_revolut_operation_owned(
            operation_id, order_uuid, payment_line_uuid
        )
        if operation["state"] == "verified" or operation["snapshot"]["retry_safe"]:
            return operation["snapshot"]
        # Ticket 03 recorded authoritative final outcomes but had no retry_safe
        # field. Recognize that evidence on status checks after upgrade. A lost
        # response or absent reference alone can never qualify as a safe failure.
        provider_state = operation["snapshot"]["provider_state"]
        if operation["state"] in {"declined", "failed", "cancelled"}:
            confirmed_failure = (
                provider_state == operation["state"]
                and operation["order_id"]
                and (operation["payment_id"] or (
                    operation["state"] in {"failed", "cancelled"}
                    and operation["payment_intent_id"]
                ))
            )
            pre_dispatch_failure = (
                operation["state"] == "failed"
                and provider_state in {"terminal_unavailable", "terminal_check_failed"}
                and not operation["has_dispatch"]
                and not operation["order_id"]
                and not operation["payment_intent_id"]
                and not operation["payment_id"]
            )
            if confirmed_failure or pre_dispatch_failure:
                return self._update_revolut_operation_owned(
                    operation_id,
                    {"state": operation["state"], "provider_state": provider_state},
                    release_terminal=True,
                    intent_only=not operation["payment_id"],
                )
        if not operation["payment_intent_id"] or not operation["order_id"]:
            return self._mark_revolut_unresolved_owned(operation_id)
        try:
            intent = self._revolut_api_request(
                operation,
                "GET",
                f"/api/payment-intents/{operation['payment_intent_id']}",
            )
            intent_state = intent.get("state")
            if intent.get("id") != operation["payment_intent_id"]:
                raise ValueError("payment intent reference mismatch")
            if intent.get("order_id") != operation["order_id"]:
                raise ValueError("payment intent order mismatch")
            payment_id = intent.get("payment_id") or operation["payment_id"]
            if intent_state in {"pending", "processing"} and not payment_id:
                return self._update_revolut_operation_owned(
                    operation_id,
                    {"state": "pending", "provider_state": intent_state},
                )
            if intent_state in {"cancelled", "failed"} and not payment_id:
                return self._update_revolut_operation_owned(
                    operation_id,
                    {"state": intent_state, "provider_state": intent_state},
                    release_terminal=True,
                    intent_only=True,
                )
            if not isinstance(payment_id, str) or not payment_id:
                return self._mark_revolut_unresolved_owned(operation_id)
            self._update_revolut_operation_owned(
                operation_id,
                {
                    "state": "pending",
                    "provider_state": intent_state,
                    "revolut_payment_id": payment_id,
                },
            )
            operation = self._read_revolut_operation_owned(operation_id)
            payment = self._revolut_api_request(
                operation, "GET", f"/api/payments/{payment_id}"
            )
            payment_state = payment.get("state")
            if (
                payment.get("id") != payment_id
                or payment.get("order_id") != operation["order_id"]
                or payment.get("amount") != operation["amount_minor"]
                or payment.get("currency") != operation["currency_code"]
            ):
                return self._mark_revolut_unresolved_owned(operation_id)
            if payment_state in REVOLUT_SUCCESS_STATES:
                return self._update_revolut_operation_owned(
                    operation_id,
                    {
                        "state": "verified",
                        "provider_state": payment_state,
                        "verified_at": fields.Datetime.now(),
                    },
                    release_terminal=True,
                )
            if payment_state in {"declined", "failed", "cancelled"}:
                return self._update_revolut_operation_owned(
                    operation_id,
                    {"state": payment_state, "provider_state": payment_state},
                    release_terminal=True,
                )
            if payment_state in REVOLUT_PAYMENT_TRANSITIONAL_STATES:
                return self._update_revolut_operation_owned(
                    operation_id,
                    {"state": "pending", "provider_state": payment_state},
                )
            return self._mark_revolut_unresolved_owned(operation_id)
        except requests.RequestException:
            return self._mark_revolut_unresolved_owned(operation_id, local_outcome="interrupted")
        except (ValueError, UserError):
            return self._mark_revolut_unresolved_owned(operation_id)

    def revolut_cancel_payment(self, operation_id, order_uuid, payment_line_uuid):
        # A fresh read decides eligibility. A POST result alone never means the
        # line can be removed: cancellation can race with customer payment.
        result = self.revolut_poll_payment(operation_id, order_uuid, payment_line_uuid)
        if result["state"] != "pending" or result["provider_state"] != "pending":
            return result
        if not self._claim_revolut_dispatch_owned(operation_id, "cancel_intent", "pending"):
            return self._read_revolut_operation_owned(operation_id)["snapshot"]
        operation = self._read_revolut_operation_owned(operation_id)
        try:
            self._revolut_api_request(
                operation, "POST",
                f"/api/payment-intents/{operation['payment_intent_id']}/cancel",
            )
            self._complete_revolut_dispatch_owned(
                operation_id, "cancel_intent", operation["payment_intent_id"], {}
            )
        except (requests.RequestException, ValueError, UserError):
            self._mark_revolut_unresolved_owned(
                operation_id, "cancel_intent", local_outcome="interrupted"
            )
        # Even a rejection or lost response must be reconciled, never replayed.
        return self.revolut_poll_payment(operation_id, order_uuid, payment_line_uuid)

    def revolut_mark_timeout(self, operation_id, order_uuid, payment_line_uuid):
        self.ensure_one()
        operation = self._read_revolut_operation_owned(
            operation_id, str(UUID(order_uuid)), str(UUID(payment_line_uuid))
        )
        if operation["state"] not in {"verified", "declined", "failed", "cancelled"}:
            return self._mark_revolut_unresolved_owned(operation_id, local_outcome="timed_out")
        return operation["snapshot"]

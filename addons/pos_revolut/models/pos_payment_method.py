import os
import re
from uuid import UUID

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .financial_snapshot import FinancialSnapshotError


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

    def _revolut_configuration_credential(self, *, provision=False):
        self.ensure_one()
        configuration = self.sudo()
        credentials = self.env["pos.revolut.merchant.credential"]
        if provision:
            if not self.env.user.has_group("base.group_system"):
                raise AccessError(_("Only a system administrator can authorize Revolut credentials."))
            existing = credentials.sudo().search([
                ("secret_reference", "=", configuration.revolut_secret_reference),
            ], limit=1)
            if not existing:
                credentials.create({
                    "company_id": configuration.company_id.id,
                    "environment": configuration.revolut_environment,
                    "secret_reference": configuration.revolut_secret_reference,
                })
        return credentials._for_snapshot(
            configuration.company_id.id,
            configuration.revolut_environment,
            configuration.revolut_secret_reference,
        )

    @api.model_create_multi
    def create(self, vals_list):
        methods = super().create(vals_list)
        for method in methods.filtered(lambda item: item.use_payment_terminal == "revolut"):
            method._revolut_configuration_credential(
                provision=self.env.user.has_group("base.group_system")
            )
        return methods

    def write(self, values):
        if "company_id" in values:
            moved = self.filtered(lambda method: method.company_id.id != values["company_id"])
            if moved and self.env["pos.revolut.payment.operation"].sudo().search_count([
                ("payment_method_id", "in", moved.ids),
            ]):
                raise ValidationError(_(
                    "A Revolut payment method with recorded attempts cannot change company."
                ))
        result = super().write(values)
        for method in self.filtered(lambda item: item.use_payment_terminal == "revolut"):
            # Saving an existing method must not attest legacy references.
            # Provision its independently reviewed authority explicitly first.
            method._revolut_configuration_credential()
        return result

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

        credential = self._revolut_configuration_credential()
        secret = os.environ.get(credential.secret_reference)
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
                allow_redirects=False,
            )
            response.raise_for_status()
            if response.status_code in range(300, 400):
                raise ValueError("Revolut redirects are not accepted")
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
        self, session_id, order_uuid, payment_line_uuid, amount, currency_id,
        require_current_credential=True,
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
        session.config_id._check_revolut_register_access(session=session)
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
        if require_current_credential:
            credential = self._revolut_configuration_credential()
            if not os.environ.get(credential.secret_reference):
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
        snapshot = (self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(
            financial_snapshot
        ) if financial_snapshot else False)
        configuration = self.sudo()
        fulfilment_type = configuration.revolut_fulfilment_type
        if ("module_pos_restaurant" in session.config_id._fields
                and session.config_id.module_pos_restaurant):
            context = financial_snapshot.get("restaurant") if isinstance(financial_snapshot, dict) else None
            if not isinstance(context, dict):
                raise UserError(_("Restaurant order context is required for Revolut payment."))
            try:
                preset_id = int(context.get("preset_id") or 0)
            except (TypeError, ValueError):
                raise UserError(_("The restaurant order preset is invalid.")) from None
            takeout = self.env.ref("pos_revolut.pos_takeout_preset", raise_if_not_found=False)
            takein = self.env.ref("pos_revolut.pos_takein_preset", raise_if_not_found=False)
            delivery = self.env.ref("pos_revolut.pos_delivery_preset", raise_if_not_found=False)
            if delivery and preset_id == delivery.id:
                raise UserError(_("Delivery orders are not supported by the Revolut terminal contract."))
            if takeout and preset_id == takeout.id:
                if context.get("table_id"):
                    raise UserError(_("A takeaway payment cannot be attached to a table."))
                fulfilment_type = "take_away"
            elif takein and preset_id == takein.id:
                fulfilment_type = "eat_in"
            else:
                raise UserError(_(
                    "Select a Dine In or Takeout preset before starting a Revolut payment."
                ))
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
            "fulfilment_type": fulfilment_type,
            "secret_reference": configuration.revolut_secret_reference,
            "credential_id": self._revolut_configuration_credential().id,
            "blocking_order_key": f"{self.company_id.id}:{order_uuid}",
            "financial_snapshot": snapshot,
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
                    session = owned_env["pos.session"].browse(values["pos_session_id"])
                    session.config_id._check_revolut_register_access(session=session)
                    # Session closure and the first reservation must conflict
                    # even when no operation existed in the closing snapshot.
                    cursor.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [values['pos_session_id']])
                    operations._lock_order(values["company_id"], values["order_uuid"])
                    from .cart_authorization import _authority_mutation
                    if owned_env["pos.revolut.refund.operation"].sudo().search_count([
                        ("company_id", "=", values["company_id"]), ("order_uuid", "=", values["order_uuid"]),
                    ]):
                        raise UserError(_("A Revolut refund already exists for this order. Reconcile it first."))
                    previous = operations.browse()
                    if previous_operation_id:
                        previous = operations.search(
                            logical_domain + [("id", "=", previous_operation_id)], limit=1
                        )
                        if previous:
                            previous.with_env(owned_env)._check_revolut_register_access()
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
                        operation.with_env(owned_env)._check_revolut_register_access()
                        if (
                            operation.amount_minor != values["amount_minor"]
                            or operation.currency_id.id != values["currency_id"]
                            or operation.pos_session_id.id != values["pos_session_id"]
                            or operation.payment_method_id.id != self.id
                            or operation.authorization_id.id != values.get("authorization_id")
                            or (
                                operation.financial_snapshot
                                and operation.financial_snapshot != values["financial_snapshot"]
                            )
                        ):
                            raise UserError(_("The existing Revolut attempt has different payment details."))
                        snapshot = operations.operation_snapshot(operation)
                        cursor.commit()
                        return snapshot, False
                    paid_order = owned_env["pos.order"].sudo().search([
                        ("company_id", "=", values["company_id"]),
                        ("uuid", "=", values["order_uuid"]),
                        ("state", "!=", "draft"),
                    ], limit=1)
                    if paid_order:
                        raise UserError(_("This POS order has already been completed."))
                    if previous:
                        if not previous.retry_safe:
                            raise UserError(_("Reconcile the previous Revolut attempt before retrying."))
                        values = {
                            **values,
                            "previous_operation_id": previous.id,
                            "attempt_number": previous.attempt_number + 1,
                        }
                    authority = owned_env["pos.revolut.cart.authorization"].sudo().browse(
                        values.get("authorization_id")
                    ).exists()
                    if not authority or (
                        authority.company_id.id != values["company_id"]
                        or authority.order_uuid != values["order_uuid"]
                        or authority.session_id.id != values["pos_session_id"]
                        or authority.currency_id.id != values["currency_id"]
                    ):
                        raise UserError(_("Prepare the exact original cart before payment."))
                    with _authority_mutation(owned_env):
                        values = {**values, **authority._admit(owned_env["pos.payment.method"].browse(self.id), values)}
                    # Earlier verified lines release the order lock so another
                    # allocation can start, but their cart and POS ownership
                    # remain bound to the original order.
                    earlier = operations.search([
                        ("company_id", "=", values["company_id"]),
                        ("order_uuid", "=", values["order_uuid"]),
                        ("state", "=", "verified"),
                    ])
                    if any(
                        not item.financial_snapshot
                        or item.financial_snapshot != values["financial_snapshot"]
                        or item.pos_session_id.id != values["pos_session_id"]
                        or item.currency_id.id != values["currency_id"]
                        for item in earlier
                    ):
                        raise UserError(_(
                            "The order changed after a Revolut payment. "
                            "Reconcile it before another charge."
                        ))
                    blocker = operations.search(
                        [
                            "|",
                            ("blocking_order_key", "=", values["blocking_order_key"]),
                            ("blocking_terminal_key", "=", values["blocking_terminal_key"]),
                        ],
                        limit=1,
                    )
                    if blocker:
                        # This request reached neither operation creation nor
                        # financial dispatch. Discard its temporary order lock.
                        cursor.rollback()
                        return {
                            "start_rejected": "terminal_busy",
                            "dispatched": False,
                            "order_uuid": values["order_uuid"],
                            "payment_line_uuid": values["payment_line_uuid"],
                            "previous_operation_id": previous_operation_id or False,
                        }, False
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
            operation.with_env(owned_env)._check_revolut_register_access()
            data = {
                "id": operation.id,
                "state": operation.state,
                "environment": operation.environment,
                "location_id": operation.location_id,
                "terminal_id": operation.terminal_id,
                "fulfilment_type": operation.fulfilment_type,
                "secret_reference": operation.secret_reference,
                "credential_operation_id": operation.id,
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

    def _claim_revolut_dispatch_owned(self, operation_id, action):
        registry = self.env.registry
        context = dict(self.env.context)
        user_id = self.env.uid
        for attempt in range(3):
            with registry.cursor() as cursor:
                try:
                    owned_env = api.Environment(cursor, user_id, context)
                    locked_operation = owned_env["pos.revolut.payment.operation"].sudo().browse(operation_id)
                    locked_operation._lock_order(locked_operation.company_id.id, locked_operation.order_uuid)
                    cursor.execute(
                        "SELECT id FROM pos_revolut_payment_operation "
                        "WHERE id = %s FOR UPDATE",
                        [operation_id],
                    )
                    operation = owned_env["pos.revolut.payment.operation"].sudo().browse(
                        operation_id
                    )
                    if (action == "create_order" and (
                        operation.state != "created" or operation.revolut_order_id
                    )) or (action == "create_intent" and (
                        operation.state != "order_created"
                        or not operation.revolut_order_id
                        or operation.revolut_payment_intent_id
                    )) or (action == "cancel_intent" and (
                        operation.state != "pending"
                        or operation.provider_state != "pending"
                        or operation.revolut_payment_id
                        or not self._revolut_cancel_observation_is_current(operation)
                    )):
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
                    if action != "cancel_intent":
                        operation.write({"state": {
                            "create_order": "dispatching_order",
                            "create_intent": "dispatching_intent",
                        }[action]})
                    cursor.commit()
                except SerializationFailure:
                    cursor.rollback()
                    continue
            return True
        return False

    def _revolut_authorized_operation_secret(self, operation):
        """Resolve the frozen operation authority before every provider request."""
        self.ensure_one()
        operation_id = operation.get("credential_operation_id")
        def authorized_reference(source):
            credential = source.credential_id if source else False
            if (not source or source.payment_method_id.id != self.id
                    or source.company_id != self.company_id or not credential
                    or credential.company_id != source.company_id
                    or credential.environment != source.environment
                    or credential.secret_reference != source.secret_reference
                    or any(operation.get(key) != source[key] for key in (
                        "environment", "secret_reference"
                    ))):
                raise UserError(_(
                    "Revolut credential authority for this attempt is unverified. "
                    "Ask a system administrator to review and authorize its original Merchant account."
                ))
            return credential.secret_reference

        source = self.env["pos.revolut.payment.operation"].sudo().browse(
            operation_id if type(operation_id) is int else 0
        ).exists()
        if source:
            reference = authorized_reference(source)
        else:
            # A payment/refund reservation commits through an owned cursor.
            # The caller's repeatable-read snapshot may predate that commit.
            with self.env.registry.cursor() as cursor:
                owned_env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                source = owned_env["pos.revolut.payment.operation"].sudo().browse(
                    operation_id if type(operation_id) is int else 0
                ).exists()
                reference = authorized_reference(source)
        # The mapping can only be created or changed by a system administrator;
        # the frozen operation never follows edits to the current POS method.
        secret = os.environ.get(reference)
        if not secret:
            raise UserError(_("The Revolut credential is not available on the Odoo server."))
        return secret

    def _revolut_api_request(self, operation, method, path, **kwargs):
        secret = self._revolut_authorized_operation_secret(operation)
        if not secret:
            raise UserError(_("The Revolut credential is not available on the Odoo server."))
        idempotency_key = kwargs.pop("idempotency_key", None)
        response = requests.request(
            method,
            f"{REVOLUT_API_HOSTS[operation['environment']]}{path}",
            headers={
                "Authorization": f"Bearer {secret}",
                "Revolut-Api-Version": REVOLUT_API_VERSION,
                "Content-Type": "application/json",
                **({"Idempotency-Key": idempotency_key} if idempotency_key else {}),
            },
            timeout=self._revolut_observation_remaining(operation),
            allow_redirects=False,
            **kwargs,
        )
        response.raise_for_status()
        if response.status_code in range(300, 400):
            raise ValueError("Revolut redirects are not accepted")
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

    def _reject_revolut_snapshot_owned(self, order_uuid, payment_line_uuid, error,
                                      previous_operation_id=False):
        # A validation exception alone never proves a previous start was absent.
        # Use the same order lock as creation/reservation, then discard it along
        # with the rejected request. Existing evidence remains reconciliation-only.
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    charges = env["pos.revolut.payment.operation"].sudo()
                    charges._lock_order(self.company_id.id, order_uuid)
                    domain = [("company_id", "=", self.company_id.id), ("order_uuid", "=", order_uuid)]
                    if (previous_operation_id or charges.search_count(domain)
                            or env["pos.revolut.refund.operation"].sudo().search_count(domain)
                            or env["pos.order"].sudo().search_count(domain[:1] + [
                                ("uuid", "=", order_uuid), ("state", "!=", "draft"),
                            ])):
                        raise error
                    cursor.rollback()
                    return {
                        "start_rejected": "snapshot_invalid", "dispatched": False,
                        "order_uuid": order_uuid, "payment_line_uuid": payment_line_uuid,
                        "previous_operation_id": False, "message": str(error),
                    }
            except (IntegrityError, SerializationFailure):
                if attempt == 2:
                    raise error from None

    def revolut_start_payment(
        self, session_id, order_uuid, payment_line_uuid, amount, currency_id,
        previous_operation_id=False, financial_snapshot=False,
        authorization_id=False, cart_version=False, tender_revision=False,
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
        if not authorization_id or type(authorization_id) is not int:
            raise UserError(_("Prepare a server-authorized persisted cart before Revolut payment."))
        authority = self.env["pos.revolut.cart.authorization"].sudo().browse(authorization_id).exists()
        if not authority or authority.company_id != self.company_id or authority.order_uuid != order_uuid:
            raise UserError(_("This cart authorization does not belong to the original sale."))
        authority.pos_order_id.with_env(self.env)._revolut_check_prepare_identity(order_uuid)
        try:
            operation_values = self._revolut_operation_values(
                session,
                currency,
                normalized_amount,
                amount_minor,
                order_uuid,
                payment_line_uuid,
                {**authority.canonical["snapshot"], "restaurant": {
                    "preset_id": authority.pos_order_id.preset_id.id,
                    "table_id": authority.pos_order_id.table_id.id if "table_id" in authority.pos_order_id._fields else False,
                }},
            )
            # Restaurant context is derived from the frozen server cart.
            operation_values.update({"authorization_id":authorization_id,
                "cart_version":cart_version, "tender_revision":tender_revision})
        except FinancialSnapshotError as error:
            return self._reject_revolut_snapshot_owned(
                order_uuid, payment_line_uuid, error, previous_operation_id
            )
        try:
            snapshot, created = self._create_revolut_operation_owned(
                operation_values, previous_operation_id
            )
        except UserError as error:
            return self._reject_revolut_snapshot_owned(order_uuid, payment_line_uuid, error, previous_operation_id)
        if not created:
            return snapshot
        operation = self._read_revolut_operation_owned(snapshot["operation_id"])
        try:
            if not self._revolut_terminal_is_eligible(operation):
                return self._apply_revolut_observation_owned(
                    operation["id"], "terminal_check_failed",
                    {"reason": "terminal_unavailable"},
                )
        except (requests.RequestException, ValueError, UserError):
            return self._apply_revolut_observation_owned(
                operation["id"], "terminal_check_failed",
                {"reason": "terminal_check_failed"},
            )
        if not self._claim_revolut_dispatch_owned(
            operation["id"], "create_order"
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
                    "metadata": {
                        "pos_partner_name": operation["config_name"],
                        "pos_order_uuid": order_uuid,
                        "pos_payment_line_uuid": payment_line_uuid,
                    },
                },
            )
            revolut_order_id = order_payload.get("id")
            if not isinstance(revolut_order_id, str) or not revolut_order_id:
                raise ValueError("missing Revolut order ID")
            self._apply_revolut_observation_owned(
                operation["id"], "dispatch_create_order",
                {"reference": revolut_order_id},
            )
        except (requests.RequestException, ValueError, UserError) as error:
            return self._apply_revolut_observation_owned(
                operation["id"], "dispatch_create_order",
                {"uncertain": True, "cause": (
                    "interrupted" if isinstance(error, requests.RequestException) else "unknown"
                )},
            )
        operation = self._read_revolut_operation_owned(operation["id"])
        if not self._claim_revolut_dispatch_owned(
            operation["id"], "create_intent"
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
            return self._apply_revolut_observation_owned(
                operation["id"], "dispatch_create_intent",
                {"reference": payment_intent_id, "state": intent_payload.get("state")},
            )
        except (requests.RequestException, ValueError, UserError) as error:
            return self._apply_revolut_observation_owned(
                operation["id"], "dispatch_create_intent",
                {"uncertain": True, "cause": (
                    "interrupted" if isinstance(error, requests.RequestException) else "unknown"
                )},
            )

    def revolut_find_payment(self, order_uuid, payment_line_uuid, session_id=None):
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
        if session_id is not None:
            session = self.env["pos.session"].browse(session_id).exists()
            if (not session or session.company_id != self.company_id
                    or self not in session.config_id.payment_method_ids):
                raise AccessError(_("This Revolut terminal is not available in the POS session."))
            session.config_id._check_revolut_register_access(session=session)
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
            # A saved checkout still supplies the register for absent attempts.
            orders = self.env["pos.order"].sudo().search([
                ("company_id", "=", self.company_id.id), ("uuid", "=", order_uuid),
            ])
            for order in orders:
                order.with_env(self.env).config_id._check_revolut_register_access(
                    session=order.session_id, order=order)
            return False
        operation.with_env(self.env)._check_revolut_register_access()
        return self.env[
            "pos.revolut.payment.operation"
        ].operation_snapshot(operation)

    def revolut_mark_timeout(self, operation_id, order_uuid, payment_line_uuid):
        self.ensure_one()
        self._read_revolut_operation_owned(
            operation_id, str(UUID(order_uuid)), str(UUID(payment_line_uuid))
        )
        return self._apply_revolut_observation_owned(operation_id, "timed_out")

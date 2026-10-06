"""Committed, fenced leases for provider observation (never financial dispatch).

Elapsed budgets are cooperative checks, not cancellable HTTP deadlines. A
stalled socket can outlive the lease; its result cannot modify newer evidence.
"""
import math
import re
import time
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import requests
from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .return_allocation import ReturnAllocation


OBSERVATION_LEASE_SECONDS = 60
OBSERVATION_CADENCE_SECONDS = 1
OBSERVATION_PAYMENT_SECONDS = 20
OBSERVATION_REPORT_SECONDS = 30
OBSERVATION_TOTAL_SECONDS = 50
_OBSERVATION = ContextVar("revolut_observation", default=None)
_OBSERVATION_FIELDS = {
    "observation_token", "observation_expires_at", "observation_started_at",
    "observation_finished_at", "observation_not_before",
}


def observation_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class PosRevolutPaymentOperation(models.Model):
    _inherit = "pos.revolut.payment.operation"

    observation_token = fields.Char(readonly=True, copy=False)
    observation_expires_at = fields.Datetime(readonly=True, copy=False)
    observation_started_at = fields.Datetime(readonly=True, copy=False)
    observation_finished_at = fields.Datetime(readonly=True, copy=False)
    observation_not_before = fields.Datetime(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any(_OBSERVATION_FIELDS.intersection(values) for values in vals_list):
            raise ValidationError(_("Provider observation claims are server-owned."))
        return super().create(vals_list)

    def write(self, values):
        if _OBSERVATION_FIELDS.intersection(values):
            raise ValidationError(_("Provider observation claims are server-owned."))
        return super().write(values)

    @api.model
    def operation_snapshot(self, operation):
        snapshot = super().operation_snapshot(operation)
        now = observation_now()
        busy = bool(operation.observation_token and operation.observation_expires_at
                    and operation.observation_expires_at > now)
        eligible_at = max(
            now,
            operation.observation_expires_at if busy else now,
            operation.observation_not_before or now,
            (operation.observation_started_at + timedelta(seconds=OBSERVATION_CADENCE_SECONDS)
             if operation.observation_started_at else now),
        )
        final = snapshot["state"] == "verified" or snapshot["retry_safe"]
        snapshot.update({
            "observation_in_progress": busy and not final,
            "observation_deferred": not final and eligible_at > now,
            "observation_fresh": False,
            "observation_finished_at": fields.Datetime.to_string(operation.observation_finished_at),
            "next_check_seconds": 0 if final else min(60, max(1, math.ceil((eligible_at - now).total_seconds()))),
        })
        return snapshot


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _revolut_cancel_observation_is_current(self, operation):
        scope = _OBSERVATION.get()
        return bool(scope and scope["operation_id"] == operation.id
                    and not scope["failed"] and operation.observation_token == scope["token"]
                    and operation.observation_expires_at
                    and operation.observation_expires_at > observation_now()
                    and time.monotonic() < min(scope["deadline"], scope["phase_deadline"]))

    def _claim_revolut_observation_owned(self, operation_id):
        # Authorization is repeated in an owned cursor before touching the
        # claim; provider credentials also remain checked for cached callers.
        operation = self._read_revolut_operation_owned(operation_id)
        try:
            self._revolut_authorized_operation_secret(operation)
        except UserError:
            # Unbound historical attempts retain their blocked state and
            # administrator remedy; one bad credential cannot abort cron's
            # remaining batch. Final cached evidence still requires authority.
            if operation["snapshot"]["state"] == "verified" or operation["snapshot"]["retry_safe"]:
                raise
            return False
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    now, token = observation_now(), str(uuid4())
                    cursor.execute(
                        "UPDATE pos_revolut_payment_operation SET observation_token = %s, "
                        "observation_started_at = %s, observation_expires_at = %s "
                        "WHERE id = %s AND state != 'verified' AND NOT COALESCE(retry_safe, FALSE) "
                        "AND (observation_expires_at IS NULL OR observation_expires_at <= %s) "
                        "AND (observation_started_at IS NULL OR observation_started_at <= %s) "
                        "AND (observation_not_before IS NULL OR observation_not_before <= %s) "
                        "RETURNING id",
                        [token, now, now + timedelta(seconds=OBSERVATION_LEASE_SECONDS), operation_id,
                         now, now - timedelta(seconds=OBSERVATION_CADENCE_SECONDS), now],
                    )
                    won = bool(cursor.fetchone())
                    cursor.commit()
                    return token if won else False
            except (SerializationFailure, DeadlockDetected):
                if attempt == 2:
                    raise

    def _finish_revolut_observation_owned(self, operation_id, scope):
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    now = observation_now()
                    cursor.execute(
                        "UPDATE pos_revolut_payment_operation SET observation_token = NULL, "
                        "observation_expires_at = NULL, observation_finished_at = %s "
                        "WHERE id = %s AND observation_token = %s AND observation_expires_at > %s "
                        "RETURNING id",
                        [now, operation_id, scope["token"], now],
                    )
                    finished = bool(cursor.fetchone())
                    cursor.commit()
                result = self._read_revolut_operation_owned(operation_id)["snapshot"]
                result["observation_fresh"] = finished and not scope["failed"]
                if finished:
                    # The caller observed a provider outcome. Only cached
                    # callers should keep waiting through unresolved evidence.
                    result["observation_deferred"] = False
                return result
            except (SerializationFailure, DeadlockDetected):
                if attempt == 2:
                    raise

    def _apply_revolut_observation_owned(self, operation_id, kind, evidence=None):
        scope = _OBSERVATION.get()
        if not scope or scope["operation_id"] != operation_id:
            return super()._apply_revolut_observation_owned(operation_id, kind, evidence)
        if kind in {"interrupted", "unknown", "tip_report_invalid", "references_unavailable"}:
            scope["failed"] = True
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    operation = env["pos.revolut.payment.operation"].sudo().browse(operation_id)
                    # Preserve financial lock ordering; fence before *all*
                    # applications, including report claims and projection.
                    ReturnAllocation(env).acquire_payment_observation(operation)
                    if (operation.observation_token != scope["token"]
                            or not operation.observation_expires_at
                            or operation.observation_expires_at <= observation_now()):
                        scope["failed"] = True
                        return operation.operation_snapshot(operation)
                    snapshot = operation._apply_payment_observation(kind, evidence)
                    if kind != "legacy_final" and snapshot["state"] == "unresolved":
                        scope["failed"] = True
                    if scope.get("defer_until"):
                        # Flush the outcome's scheduled ORM write before SQL
                        # extends it, so commit cannot overwrite Retry-After.
                        operation.flush_recordset(["next_reconcile_at"])
                        cursor.execute(
                            "UPDATE pos_revolut_payment_operation SET observation_not_before = %s, "
                            "next_reconcile_at = GREATEST(next_reconcile_at, %s) WHERE id = %s",
                            [scope["defer_until"], scope["defer_until"], operation_id],
                        )
                        operation.invalidate_recordset(["observation_not_before", "next_reconcile_at"])
                    cursor.commit()
                    return snapshot
            except (SerializationFailure, DeadlockDetected):
                if attempt == 2:
                    raise

    def _revolut_observation_remaining(self, operation):
        scope = _OBSERVATION.get()
        if not scope or scope["operation_id"] != operation.get("id"):
            return 10
        current = self._read_revolut_operation_owned(scope["operation_id"])
        with self.env.registry.cursor() as cursor:
            cursor.execute(
                "SELECT observation_token, observation_expires_at FROM pos_revolut_payment_operation WHERE id = %s",
                [scope["operation_id"]],
            )
            token, expires = cursor.fetchone()
        remaining = min(scope["deadline"], scope["phase_deadline"]) - time.monotonic()
        now = observation_now()
        if (token != scope["token"] or not expires or expires <= now or remaining <= 0
                or (scope.get("defer_until") and scope["defer_until"] > now)):
            scope["failed"] = True
            raise requests.Timeout("Revolut observation budget expired")
        # Also revalidate frozen authority at each I/O boundary.
        self._revolut_authorized_operation_secret(current)
        return min(10, remaining)

    def _revolut_observation_error(self, error):
        scope = _OBSERVATION.get()
        if not scope:
            return
        scope["failed"] = True
        response = getattr(error, "response", None)
        if response is not None and response.status_code == 429:
            value = response.headers.get("Retry-After")
            if isinstance(value, str) and re.fullmatch(r"[0-9]{1,10}", value.strip()):
                seconds = int(value)
                if 0 < seconds <= 2147483647:
                    scope["defer_until"] = observation_now() + timedelta(seconds=seconds)

    def _revolut_api_request(self, operation, method, path, **kwargs):
        self._revolut_observation_remaining(operation)
        try:
            result = super()._revolut_api_request(operation, method, path, **kwargs)
            self._revolut_observation_remaining(operation)
            return result
        except requests.RequestException as error:
            self._revolut_observation_error(error)
            raise

    def _revolut_report_request(self, operation, method, path, **kwargs):
        scope = _OBSERVATION.get()
        if scope and not scope["report_phase"]:
            scope["report_phase"] = True
            scope["phase_deadline"] = min(scope["deadline"], time.monotonic() + OBSERVATION_REPORT_SECONDS)
        self._revolut_observation_remaining(operation)
        try:
            result = super()._revolut_report_request(operation, method, path, **kwargs)
            self._revolut_observation_remaining(operation)
            return result
        except requests.RequestException as error:
            self._revolut_observation_error(error)
            raise

    def _observe_revolut_payment(self, operation_id, order_uuid, payment_line_uuid, *, cancel=False):
        self.ensure_one()
        try:
            order_uuid, payment_line_uuid = str(UUID(order_uuid)), str(UUID(payment_line_uuid))
        except (TypeError, ValueError, AttributeError):
            raise UserError(_("The POS payment identifiers are invalid.")) from None
        self._read_revolut_operation_owned(operation_id, order_uuid, payment_line_uuid)
        token = self._claim_revolut_observation_owned(operation_id)
        if not token:
            return self._read_revolut_operation_owned(operation_id, order_uuid, payment_line_uuid)["snapshot"]
        started = time.monotonic()
        scope = {"operation_id": operation_id, "token": token, "failed": False,
                 "deadline": started + OBSERVATION_TOTAL_SECONDS,
                 "phase_deadline": started + OBSERVATION_PAYMENT_SECONDS, "report_phase": False}
        context_token = _OBSERVATION.set(scope)
        try:
            try:
                if cancel:
                    super().revolut_cancel_payment(operation_id, order_uuid, payment_line_uuid)
                else:
                    super().revolut_poll_payment(operation_id, order_uuid, payment_line_uuid)
            except (SerializationFailure, DeadlockDetected):
                # Recovery belongs to the original holder too. An expired
                # holder must not postpone its successor's schedule after
                # exhausting the evidence transaction's local retries.
                self._apply_revolut_observation_owned(operation_id, "interrupted")
            return self._finish_revolut_observation_owned(operation_id, scope)
        finally:
            # A killed worker/failed RPC leaves its fixed lease recoverable.
            # Never slide expiry or release without the original fenced token.
            _OBSERVATION.reset(context_token)

    def revolut_poll_payment(self, operation_id, order_uuid, payment_line_uuid):
        scope = _OBSERVATION.get()
        if scope and scope["operation_id"] == operation_id:
            # Cancellation's precheck and immediate recovery stay under the
            # same claim, without a cadence gap or replay of its POST.
            scope["phase_deadline"] = min(scope["deadline"], time.monotonic() + OBSERVATION_PAYMENT_SECONDS)
            scope["report_phase"] = False
            return super().revolut_poll_payment(operation_id, order_uuid, payment_line_uuid)
        return self._observe_revolut_payment(operation_id, order_uuid, payment_line_uuid)

    def revolut_cancel_payment(self, operation_id, order_uuid, payment_line_uuid):
        return self._observe_revolut_payment(operation_id, order_uuid, payment_line_uuid, cancel=True)

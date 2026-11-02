"""Own payment reads, tip-report follow-up and cancellation under fenced leases.

Financial dispatch claims remain separate from observation claims.
Elapsed budgets are cooperative checks, not cancellable HTTP deadlines. A
stalled socket can outlive the lease; its result cannot modify newer evidence.
"""
import csv
import logging
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
from .terminal_tip import ReportPaymentNotFinal


OBSERVATION_LEASE_SECONDS = 60
OBSERVATION_CADENCE_SECONDS = 1
OBSERVATION_PAYMENT_SECONDS = 20
OBSERVATION_REPORT_SECONDS = 30
OBSERVATION_TOTAL_SECONDS = 50
_logger = logging.getLogger(__name__)
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
        # Retry only local application, never HTTP or financial dispatch.
        scope = _OBSERVATION.get()
        if scope and scope["operation_id"] != operation_id:
            scope = None
        if scope and kind in {"interrupted", "unknown", "tip_report_invalid", "references_unavailable"}:
            scope["failed"] = True
        for attempt in range(3):
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                    operation = env["pos.revolut.payment.operation"].sudo().browse(operation_id)
                    # Preserve financial lock ordering; fence before *all*
                    # applications, including report claims and projection.
                    ReturnAllocation(env).acquire_payment_observation(operation)
                    if scope and (operation.observation_token != scope["token"]
                            or not operation.observation_expires_at
                            or operation.observation_expires_at <= observation_now()):
                        scope["failed"] = True
                        return operation.operation_snapshot(operation)
                    applied_kind, applied_evidence = kind, evidence
                    if (scope and kind in {
                            "intent", "payment", "tip_report_claim", "tip_report_created", "tip_report_retire",
                            "tip_report_wait", "tip_report_verified",
                        } and time.monotonic() >= min(scope["deadline"], scope["phase_deadline"])):
                        # Local lock waits consume the same cooperative budget
                        # as HTTP. Never verify late evidence after this wait.
                        scope["failed"] = True
                        applied_kind, applied_evidence = "interrupted", None
                    snapshot = operation._apply_payment_observation(applied_kind, applied_evidence)
                    if (scope and kind not in {"legacy_final", "cancel_unclaimed"}
                            and snapshot["state"] == "unresolved"):
                        # An ineligible local cancellation check establishes
                        # no provider outcome. Let the following fresh read
                        # decide whether normal intent cancellation is safe.
                        scope["failed"] = True
                    if scope and scope.get("defer_until"):
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
        operation = self._read_revolut_operation_owned(operation_id, order_uuid, payment_line_uuid)
        self._revolut_check_environment_access(operation["environment"])
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
                    self._cancel_revolut_payment(operation_id)
                else:
                    self._poll_revolut_payment(operation_id)
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

    def _poll_revolut_payment(self, operation_id):
        # Both cancellation passes reuse the original claim and total budget.
        # Phase ordering is explicit instead of public RPC/MRO re-entry.
        scope = _OBSERVATION.get()
        scope["phase_deadline"] = min(scope["deadline"], time.monotonic() + OBSERVATION_PAYMENT_SECONDS)
        scope["report_phase"] = False
        snapshot = self._read_revolut_payment(operation_id)
        return self._read_revolut_terminal_tip(operation_id, snapshot)

    def _read_revolut_payment(self, operation_id):
        operation = self._read_revolut_operation_owned(operation_id)
        snapshot = self._apply_revolut_observation_owned(operation_id, "legacy_final")
        if snapshot["state"] == "verified" or snapshot["retry_safe"]:
            return snapshot
        if not operation["payment_intent_id"] or not operation["order_id"]:
            return self._apply_revolut_observation_owned(
                operation_id, "references_unavailable"
            )
        try:
            intent = self._revolut_api_request(
                operation, "GET",
                f"/api/payment-intents/{operation['payment_intent_id']}",
            )
            snapshot = self._apply_revolut_observation_owned(
                operation_id, "intent", intent
            )
            if snapshot["state"] in {"verified", "unresolved"} or snapshot["retry_safe"]:
                # An invalid intent must not be overridden by a later payment
                # read using a reference retained from an earlier observation.
                return snapshot
            if (intent.get("state") in ("cancelled", "failed")
                    and not intent.get("payment_id")
                    and not operation["payment_id"]):
                # Another poll may have stored a payment while this intent GET
                # was in flight. Its result is authoritative only after a
                # fresh payment read; leave that to the next poll.
                return snapshot
            if not snapshot["payment_id"]:
                return snapshot
            operation = self._read_revolut_operation_owned(operation_id)
            payment = self._revolut_api_request(
                operation, "GET", f"/api/payments/{snapshot['payment_id']}"
            )
            return self._apply_revolut_observation_owned(
                operation_id, "payment", payment
            )
        except requests.RequestException:
            return self._apply_revolut_observation_owned(operation_id, "interrupted")
        except (ValueError, UserError):
            return self._apply_revolut_observation_owned(operation_id, "unknown")

    def _cancel_revolut_payment(self, operation_id):
        # A fresh read decides eligibility. A POST result alone never means the
        # line can be removed: cancellation can race with customer payment.
        result = self._apply_revolut_observation_owned(operation_id, "cancel_unclaimed")
        if result["state"] == "verified" or result["retry_safe"]:
            return result
        result = self._poll_revolut_payment(operation_id)
        if result["state"] != "pending" or result["provider_state"] != "pending":
            return result
        if not self._claim_revolut_dispatch_owned(operation_id, "cancel_intent"):
            return self._read_revolut_operation_owned(operation_id)["snapshot"]
        operation = self._read_revolut_operation_owned(operation_id)
        try:
            self._revolut_api_request(
                operation, "POST",
                f"/api/payment-intents/{operation['payment_intent_id']}/cancel",
            )
            self._apply_revolut_observation_owned(
                operation_id, "dispatch_cancel_intent",
                {"reference": operation["payment_intent_id"]},
            )
        except (requests.RequestException, ValueError, UserError):
            self._apply_revolut_observation_owned(
                operation_id, "dispatch_cancel_intent",
                {"uncertain": True, "cause": "interrupted"},
            )
        # Even a rejection or lost response must be reconciled, never replayed.
        return self._poll_revolut_payment(operation_id)

    def _read_revolut_terminal_tip(self, operation_id, snapshot):
        if snapshot["state"] == "verified" or snapshot["retry_safe"]:
            return snapshot
        # An invalid fresh intent/payment observation must not be overridden by
        # a report applied against captured data retained from an earlier poll.
        if snapshot["state"] != "pending" or snapshot["provider_state"] not in {"captured", "completed"}:
            return snapshot
        operation = self._read_revolut_operation_owned(operation_id)
        if not operation["authorized"] or not operation["captured_amount_minor"]:
            return snapshot
        run_id = operation["report_run_id"]
        report_resource = True
        try:
            if not run_id:
                claim = str(uuid4())
                self._apply_revolut_observation_owned(operation_id, "tip_report_claim", {"claim": claim})
                operation = self._read_revolut_operation_owned(operation_id)
                if operation["report_claim"] != claim:
                    return operation["snapshot"]
                report = self._revolut_report_request(operation, "POST", "/api/report-runs",
                                                       body=self._revolut_report_body(operation))
                run_id, status = self._revolut_report_run(report)
                self._apply_revolut_observation_owned(operation_id, "tip_report_created", {"claim": claim, "run_id": run_id})
                operation = self._read_revolut_operation_owned(operation_id)
                if operation["report_run_id"] != run_id:
                    return operation["snapshot"]
            else:
                report = self._revolut_report_request(operation, "GET", f"/api/report-runs/{run_id}")
                _, status = self._revolut_report_run(report, run_id)
            if status in {"expired", "failed"}:
                return self._apply_revolut_observation_owned(operation_id, "tip_report_retire", {"run_id": run_id, "reason": status})
            if status == "processing":
                return self._apply_revolut_observation_owned(operation_id, "tip_report_wait")
            content = self._revolut_report_request(operation, "GET", f"/api/report-runs/{run_id}/file", csv_file=True)
            report_resource = False
            order = self._revolut_report_request(operation, "GET", f"/api/orders/{operation['order_id']}")
            evidence = self._revolut_tip_report_evidence(operation, content, order)
            if evidence is None:
                return self._apply_revolut_observation_owned(operation_id, "tip_report_retire", {"run_id": run_id, "reason": "payment_not_yet_reported"})
            return self._apply_revolut_observation_owned(operation_id, "tip_report_verified", evidence)
        except ReportPaymentNotFinal:
            return self._apply_revolut_observation_owned(operation_id, "tip_report_retire", {"run_id": run_id, "reason": "payment_not_final"})
        except requests.HTTPError as error:
            if report_resource and run_id and error.response is not None and error.response.status_code in {404, 410}:
                return self._apply_revolut_observation_owned(operation_id, "tip_report_retire", {"run_id": run_id, "reason": "file_unavailable"})
            return self._apply_revolut_observation_owned(operation_id, "interrupted")
        except requests.RequestException:
            return self._apply_revolut_observation_owned(operation_id, "interrupted")
        except (ValueError, TypeError, UnicodeError, csv.Error, UserError) as error:
            # Configuration/settlement errors are already safe user messages.
            # Never log report rows, response bodies or credential headers.
            _logger.warning("Revolut operation %s tip reconciliation remains unresolved (%s)",
                            operation_id, str(error) if isinstance(error, UserError) else type(error).__name__)
            return self._apply_revolut_observation_owned(operation_id, "tip_report_invalid")

    def revolut_poll_payment(self, operation_id, order_uuid, payment_line_uuid):
        return self._observe_revolut_payment(operation_id, order_uuid, payment_line_uuid)

    def revolut_cancel_payment(self, operation_id, order_uuid, payment_line_uuid):
        return self._observe_revolut_payment(operation_id, order_uuid, payment_line_uuid, cancel=True)

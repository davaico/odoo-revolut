"""Authenticated payments-report evidence for terminal-selected tips.

The report is a separate asynchronous, non-financial request. A captured
payment remains reserved until a report explicitly proves even a zero tip.
"""
import csv
import hashlib
import io
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pos_payment_method import (
    REVOLUT_API_HOSTS, REVOLUT_API_VERSION, REVOLUT_REQUEST_TIMEOUT_SECONDS,
)
from .revolut_payment_operation import _tip_evidence_write
from .cart_pricing import _conserve_terminal_tip_base

REPORT_COLUMNS = (
    "payment_id", "type", "order_id", "state", "amount", "currency",
    "surcharge_amount", "tip_amount", "refunded_amount", "created_date",
    "captured_date", "location_id",
)
REPORT_MAX_BYTES = 262144
REPORT_MAX_ROWS = 1000
REPORT_MAX_CELL = 128
REPORT_SUCCESS_STATES = {"CAPTURED", "COMPLETED"}
REPORT_DECIMAL = re.compile(r"[0-9]{1,16}(?:\.[0-9]{1,6})?\Z")


class ReportPaymentNotFinal(ValueError):
    """A valid transitional row needs a fresh report, never verification."""


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _revolut_verified_terminal_tip_minor(self):
        self.ensure_one()
        authority = self.order_id.revolut_authorization_id.sudo()
        if (not authority or self.uuid != str(uuid5(NAMESPACE_URL, f"revolut-tip:{authority.id}"))
                or self.product_id != authority.tip_product_id or self.qty != 1):
            return 0
        return sum(operation.terminal_tip_minor for operation in authority._operations()
                   if operation.state == "verified")

    def _compute_amount_line_all(self):
        if not self._revolut_verified_terminal_tip_minor():
            return super()._compute_amount_line_all()
        # Native compute_all does not use the manual-base seam. The line's
        # stored totals must use the same native baseline as the whole order.
        bases = self.order_id.lines._prepare_tax_base_line_values()
        taxes = self.env["account.tax"]
        taxes._add_tax_details_in_base_lines(bases, self.order_id.company_id)
        taxes._round_base_lines_tax_details(bases, self.order_id.company_id)
        details = next(base["tax_details"] for base in bases if base["record"] == self)
        return {"price_subtotal": details["total_excluded_currency"],
                "price_subtotal_incl": details["total_included_currency"]}

    def _prepare_tax_base_line_values(self):
        base_lines = super()._prepare_tax_base_line_values()
        for order in self.order_id:
            authority = order.revolut_authorization_id.sudo()
            if not authority:
                continue
            tip_uuid = str(uuid5(NAMESPACE_URL, f"revolut-tip:{authority.id}"))
            tip_base = next((base for base in base_lines if base["record"].order_id == order
                             and base["record"].uuid == tip_uuid
                             and base["record"].product_id == authority.tip_product_id
                             and base["record"].qty == 1), None)
            if tip_base is None:
                continue
            tip_minor = tip_base["record"]._revolut_verified_terminal_tip_minor()
            if not tip_minor:
                continue
            # Only authenticated, server-projected tips use this native seam.
            # Ordinary goods, browser tax overrides and return lines do not.
            selected = [base for base in base_lines if base["record"].order_id == order]
            taxes = self.env["account.tax"]
            taxes._add_tax_details_in_base_lines(selected, order.company_id)
            taxes._round_base_lines_tax_details(selected, order.company_id)
            _conserve_terminal_tip_base(tip_base, tip_minor / 10 ** order.currency_id.decimal_places,
                                       order.currency_id)
        return base_lines


def _utc_datetime(value):
    if not isinstance(value, str) or not 20 <= len(value) <= 40:
        raise ValueError("missing payment creation timestamp")
    # UTC payments-report timestamps may include the provider's zone annotation.
    if value.endswith("[UTC]"):
        value = value[:-5]
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("payment timestamp must be UTC")
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _minor_units(value, exponent, *, empty_zero=False):
    # Only surcharge has a documented blank-as-none convention. In particular,
    # missing/blank tip evidence can never prove that the customer skipped it.
    if value == "" and empty_zero:
        return 0
    if not isinstance(value, str) or len(value) > 24 or not REPORT_DECIMAL.fullmatch(value):
        raise ValueError("ambiguous report amount")
    amount = Decimal(value) * (10 ** exponent)
    if amount != amount.to_integral_value() or amount > 2147483647:
        raise ValueError("report amount is not representable in currency minor units")
    return int(amount)


class PosRevolutPaymentOperation(models.Model):
    _inherit = "pos.revolut.payment.operation"

    def _terminal_payment_created_at(self, value):
        return _utc_datetime(value)

    def _apply_terminal_tip_observation(self, kind, evidence):
        # The caller has acquired the shared order boundary and operation row.
        self.ensure_one()
        if not self.authorization_id or self.state == "verified" or self.retry_safe or not self.captured_amount_minor:
            return self.operation_snapshot(self)
        now = fields.Datetime.now()
        values = {"next_reconcile_at": now + timedelta(seconds=30)}
        if kind == "tip_report_claim":
            if self.report_run_id or (self.report_claim and self.report_claimed_at and self.report_claimed_at > now - timedelta(seconds=60)):
                return self.operation_snapshot(self)
            values.update({"report_claim": evidence["claim"], "report_claimed_at": now})
        elif kind == "tip_report_created":
            if self.report_claim != evidence.get("claim") or self.report_run_id:
                return self.operation_snapshot(self)
            values.update({"report_run_id": evidence["run_id"], "report_claim": False,
                           "report_claimed_at": False})
        elif kind == "tip_report_retire":
            if self.report_run_id != evidence.get("run_id"):
                return self.operation_snapshot(self)
            history = list(self.report_run_history or [])
            # Only identifiers/status/timestamps are retained, never other
            # companies' report rows or returned file URLs.
            history.append({"report_run_id": self.report_run_id, "reason": evidence["reason"],
                            "retired_at": fields.Datetime.to_string(now)})
            values.update({"report_run_id": False, "report_run_history": history})
        elif kind == "tip_report_verified":
            if self.report_run_id != evidence.get("run_id"):
                return self.operation_snapshot(self)
            gross, tip = evidence["gross_minor"], evidence["tip_minor"]
            if (type(gross) is not int or type(tip) is not int or tip < 0
                    or gross != self.captured_amount_minor or gross != self.amount_minor + tip):
                raise ValueError("inconsistent terminal tip decomposition")
            values.update({"state": "verified", "provider_state": "captured",
                           "gross_amount_minor": gross, "terminal_tip_minor": tip,
                           "terminal_tip_evidence": evidence["provenance"],
                           "verified_at": now, "next_reconcile_at": False,
                           "reconcile_failures": 0, "local_outcome": False,
                           "blocking_order_key": False, "blocking_terminal_key": False})
        elif kind == "tip_report_invalid":
            values.update({"state": "unresolved", "local_outcome": False,
                           "next_reconcile_at": now + timedelta(seconds=300)})
        elif kind != "tip_report_wait":
            raise ValueError("unknown terminal report observation")
        with _tip_evidence_write(self.env):
            self.sudo().write(values)
        if kind == "tip_report_verified":
            # Root's hook projects the canonical tip and gross tender in this
            # same transaction. Failure rolls back verification and projection.
            self._revolut_project_tip()
        return self.operation_snapshot(self)


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    def _read_revolut_operation_owned(self, operation_id, order_uuid=None, payment_line_uuid=None):
        data = super()._read_revolut_operation_owned(operation_id, order_uuid, payment_line_uuid)
        with self.env.registry.cursor() as cursor:
            env = api.Environment(cursor, self.env.uid, dict(self.env.context))
            operation = env["pos.revolut.payment.operation"].sudo().browse(operation_id)
            data.update({
                "authorized": bool(operation.authorization_id),
                "captured_amount_minor": operation.captured_amount_minor,
                "payment_created_at": fields.Datetime.to_string(operation.captured_payment_created_at),
                "decimal_places": operation.currency_id.decimal_places,
                "report_run_id": operation.report_run_id,
                "report_claim": operation.report_claim,
                "snapshot": operation.operation_snapshot(operation),
            })
            cursor.commit()
        return data

    def _revolut_report_request(self, operation, method, path, *, body=None, csv_file=False):
        secret = self._revolut_authorized_operation_secret(operation)
        if not secret:
            raise UserError(_("The Revolut credential is not available on the Odoo server."))
        response = requests.request(
            method, f"{REVOLUT_API_HOSTS[operation['environment']]}{path}",
            headers={"Authorization": f"Bearer {secret}", "Revolut-Api-Version": REVOLUT_API_VERSION,
                     "Accept": "text/csv" if csv_file else "application/json",
                     "Content-Type": "application/json"},
            timeout=self._revolut_observation_remaining(operation), allow_redirects=False, stream=True,
            **({"json": body} if body is not None else {}),
        )
        try:
            response.raise_for_status()
            if 300 <= response.status_code < 400:
                raise ValueError("report redirects are not accepted")
            content = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                self._revolut_observation_remaining(operation)
                if len(content) + len(chunk) > REPORT_MAX_BYTES:
                    raise ValueError("report response exceeds byte limit")
                content.extend(chunk)
            if csv_file:
                return bytes(content)
            payload = json.loads(content.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("report response must be an object")
            return payload
        finally:
            response.close()

    def _revolut_report_body(self, operation):
        created = fields.Datetime.to_datetime(operation["payment_created_at"])
        if not created:
            raise ValueError("missing authenticated payment creation time")
        # Revolut rejects a future report end during immediate capture polling.
        end = min(created + timedelta(seconds=60), fields.Datetime.now())
        return {
            "type": "payments_report", "format": "csv",
            "filter": {"from": (created - timedelta(seconds=60)).isoformat() + "Z",
                       "to": end.isoformat() + "Z"},
            "options": {"timezone": "UTC", "columns": list(REPORT_COLUMNS)},
        }

    def _revolut_report_run(self, response, expected=None):
        run_id = response.get("report_run_id")
        if not isinstance(run_id, str) or str(UUID(run_id)) != run_id or (expected and run_id != expected):
            raise ValueError("report run identity mismatch")
        status = response.get("status")
        if status not in {"processing", "completed", "failed", "expired"}:
            raise ValueError("unknown report run state")
        return run_id, status

    def _revolut_tip_report_evidence(self, operation, content, order):
        if (order.get("id") != operation["order_id"] or order.get("currency") != operation["currency_code"]
                or order.get("location_id") != operation["location_id"]):
            raise ValueError("pushed order identity mismatch")
        payments = order.get("payments")
        if not isinstance(payments, list) or not 1 <= len(payments) <= REPORT_MAX_ROWS:
            raise ValueError("missing or unbounded pushed order payments")
        matching = []
        ids = set()
        for payment in payments:
            if not isinstance(payment, dict) or not isinstance(payment.get("id"), str) or payment["id"] in ids:
                raise ValueError("ambiguous pushed order payments")
            ids.add(payment["id"])
            if payment.get("state") in {"captured", "completed"}:
                matching.append(payment)
            elif payment.get("state") not in {"declined", "failed", "cancelled"}:
                # Another pending payment may still capture; absence of a
                # successful second payment alone does not prove safe finality.
                raise ValueError("another pushed payment is not final")
        if (len(matching) != 1 or matching[0]["id"] != operation["payment_id"]
                or type(matching[0].get("amount")) is not int
                or matching[0]["amount"] != operation["captured_amount_minor"]):
            raise ValueError("unexpected successful payment on pushed order")
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        headers = next(reader, [])
        if len(headers) != len(REPORT_COLUMNS) or set(headers) != set(REPORT_COLUMNS):
            raise ValueError("missing/duplicate/unrequested report columns")
        candidates = []
        related_successful = []
        for number, row in enumerate(reader, 1):
            if number > REPORT_MAX_ROWS or len(row) != len(headers) or any(len(cell) > REPORT_MAX_CELL for cell in row):
                raise ValueError("report row limit or shape invalid")
            record = dict(zip(headers, row))
            if record["payment_id"] == operation["payment_id"]:
                candidates.append(record)
            if record["order_id"] == operation["order_id"] and record["type"] == "PAYMENT" and record["state"] in REPORT_SUCCESS_STATES:
                related_successful.append(record)
        if not candidates:
            if related_successful:
                raise ValueError("report contains an unexpected successful pushed payment")
            return None
        if len(candidates) != 1:
            raise ValueError("ambiguous report payment evidence")
        row = candidates[0]
        refresh_needed = row["state"] == "CAPTURE_STARTED"
        if len(related_successful) != (0 if refresh_needed else 1):
            raise ValueError("ambiguous report payment evidence")
        if (row["type"] != "PAYMENT" or (not refresh_needed and row["state"] not in REPORT_SUCCESS_STATES)
                or row["order_id"] != operation["order_id"]
                or row["currency"] != operation["currency_code"]
                or row["location_id"] != operation["location_id"]):
            raise ValueError("report payment identity mismatch")
        created = _utc_datetime(row["created_date"])
        if abs(created - fields.Datetime.to_datetime(operation["payment_created_at"])) > timedelta(seconds=1):
            raise ValueError("report payment creation identity mismatch")
        if (row["captured_date"] or not refresh_needed) and _utc_datetime(row["captured_date"]) < created:
            raise ValueError("report capture precedes payment")
        exponent = operation["decimal_places"]
        gross = _minor_units(row["amount"], exponent)
        tip = _minor_units(row["tip_amount"], exponent)
        if (_minor_units(row["surcharge_amount"], exponent, empty_zero=True)
                or _minor_units(row["refunded_amount"], exponent)
                or gross != operation["captured_amount_minor"] or gross != operation["amount_minor"] + tip):
            raise ValueError("unexplained report amount")
        if refresh_needed:
            # Completed reports are generated files: an earlier capture state
            # cannot become payment evidence by downloading that run again.
            raise ReportPaymentNotFinal()
        return {"run_id": operation["report_run_id"], "gross_minor": gross, "tip_minor": tip,
                "provenance": {"report_run_id": operation["report_run_id"],
                               "payment_id": operation["payment_id"], "order_id": operation["order_id"],
                               "currency": operation["currency_code"], "location_id": operation["location_id"],
                               "created_date": row["created_date"], "captured_date": row["captured_date"],
                               "amount": row["amount"], "tip_amount": row["tip_amount"],
                               "file_sha256": hashlib.sha256(content).hexdigest()}}

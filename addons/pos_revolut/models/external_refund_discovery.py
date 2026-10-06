"""Read-only, restartable discovery in the original Merchant authority.

The order list has no documented ordering or continuation token. A full time
window is subdivided rather than treating its last row as a safe cursor.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import requests
from psycopg2.errors import DeadlockDetected, SerializationFailure

from odoo import api, fields, models
from odoo.exceptions import UserError

from .return_allocation import ReturnAllocation


_logger = logging.getLogger(__name__)
PAGE_LIMIT = 100
EPOCH = "1970-01-01T00:00:00.000000Z"


def _stamp(value):
    return value.isoformat(timespec="microseconds") + "Z"


def _date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    ).replace(tzinfo=None)


class MerchantDiscovery(models.Model):
    _inherit = "pos.revolut.merchant.credential"

    refund_discovery_windows = fields.Json(readonly=True, copy=False)
    refund_discovery_had_malformed = fields.Boolean(readonly=True, copy=False)
    refund_discovery_latest_end = fields.Datetime(readonly=True, copy=False)
    refund_discovery_retry_windows = fields.Json(readonly=True, copy=False)
    refund_discovery_steps = fields.Integer(readonly=True, copy=False)
    next_refund_discovery_at = fields.Datetime(
        readonly=True, default=lambda self: datetime(1970, 1, 1), index=True,
    )


class PaymentDiscovery(models.Model):
    _inherit = "pos.revolut.payment.operation"

    external_refund_review_required = fields.Boolean(
        compute="_compute_external_refund_review",
    )
    external_refund_review_note = fields.Char(compute="_compute_external_refund_review")

    def _compute_external_refund_review(self):
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo()
        for source in self:
            blocked = evidence.search_count([
                ("credential_id", "=", source.credential_id.id), ("deployment_blocking", "=", True),
                "|", ("original_operation_id", "=", source.id),
                ("original_operation_id", "=", False),
            ], limit=1) if source.credential_id else 0
            source.external_refund_review_required = bool(blocked)
            source.external_refund_review_note = (
                "External refund evidence needs manager investigation; further refunds are blocked."
                if blocked else False
            )


class RefundDiscovery(models.Model):
    _inherit = "pos.revolut.refund.operation"

    @api.model
    def _cron_reconcile_refunds(self, batch_size=50):
        super()._cron_reconcile_refunds(batch_size=batch_size)
        self._cron_discover_external_refunds()

    @api.model
    def _cron_discover_external_refunds(self, batch_size=1):
        # One credential/window per ordinary cron call, fairly ordered. Every
        # retry uses a fresh transaction; provider requests are GET only.
        sources = self.env["pos.revolut.payment.operation"].sudo().search([
            ("state", "=", "verified"), ("credential_id", "!=", False),
            ("revolut_order_id", "!=", False),
        ])
        credentials = sources.credential_id.filtered(
            lambda item: not item.next_refund_discovery_at
            or item.next_refund_discovery_at <= fields.Datetime.now()
        ).sorted(lambda item: (item.next_refund_discovery_at or datetime.min, item.id))
        limit = max(1, min(int(batch_size), 5))
        processed = 0
        for credential in credentials[:limit * 5]:
            try:
                with self.env.registry.cursor() as cursor:
                    env = api.Environment(cursor, self.env.uid, dict(self.env.context), su=True)
                    cursor.execute(
                        "SELECT id FROM pos_revolut_merchant_credential WHERE id = %s FOR UPDATE SKIP LOCKED",
                        [credential.id],
                    )
                    if not cursor.fetchone():
                        continue
                    env["pos.revolut.refund.operation"]._discover_credential(credential.id)
                    cursor.commit()
                    processed += 1
            except (SerializationFailure, DeadlockDetected):
                _logger.warning("External refund discovery deferred for credential %s", credential.id)
            if processed >= limit:
                break

    @api.model
    def _discovery_evidence(self, credential, reference, reason, source=None, candidate=None):
        evidence = self.env["pos.revolut.external.refund.evidence"].sudo()
        record = evidence.search([
            ("credential_id", "=", credential.id), ("provider_order_id", "=", reference),
        ], limit=1)
        if record:
            record.write({"reason": reason, "resolved": False})
            return
        candidate = candidate if isinstance(candidate, dict) else {}
        evidence.create({
            "credential_id": credential.id, "provider_order_id": reference,
            "original_operation_id": source.id if source else False,
            "related_order_id": candidate.get("related_order_id") if isinstance(candidate.get("related_order_id"), str) else False,
            "amount_minor": candidate.get("amount") if type(candidate.get("amount")) is int and 0 <= candidate["amount"] <= 2147483647 else 0,
            "currency_code": candidate.get("currency") if isinstance(candidate.get("currency"), str) and len(candidate["currency"]) <= 3 else False,
            "reason": reason,
        })

    @api.model
    def _resolve_discovery_evidence(self, credential, reference):
        self.env["pos.revolut.external.refund.evidence"].sudo().search([
            ("credential_id", "=", credential.id), ("provider_order_id", "=", reference),
        ]).write({"resolved": True})

    @api.model
    def _discover_credential(self, credential_id):
        credential = self.env["pos.revolut.merchant.credential"].sudo().browse(credential_id)
        sources = self.env["pos.revolut.payment.operation"].sudo().search([
            ("state", "=", "verified"), ("credential_id", "=", credential.id),
            ("company_id", "=", credential.company_id.id), ("revolut_order_id", "!=", False),
            ("environment", "=", credential.environment),
            ("secret_reference", "=", credential.secret_reference),
        ], order="id")
        if not sources:
            return
        anchor = sources[0]
        method = anchor.payment_method_id.sudo().with_company(anchor.company_id)
        authority = {"credential_operation_id": anchor.id,
                     "environment": anchor.environment, "secret_reference": anchor.secret_reference}
        now = fields.Datetime.now()
        windows = credential.refund_discovery_windows or [[EPOCH, _stamp(now)]]
        latest_end = credential.refund_discovery_latest_end
        if not credential.refund_discovery_windows or not latest_end:
            latest_end = now
        elif now - latest_end >= timedelta(minutes=5):
            # Recent visibility must advance even during a saturated or long
            # historical scan. The older intervals and evidence are retained.
            windows = [[_stamp(latest_end - timedelta(seconds=1)), _stamp(now)]] + windows
            latest_end = now
        retries = credential.refund_discovery_retry_windows or []
        retrying = bool(retries and credential.refund_discovery_steps % 10 == 9)
        active = retries if retrying else windows
        start, end = active[0]
        malformed = bool(credential.refund_discovery_had_malformed) if credential.refund_discovery_windows else False
        schedule = {"next_refund_discovery_at": now + timedelta(minutes=1),
                    "refund_discovery_latest_end": latest_end,
                    "refund_discovery_windows": windows,
                    "refund_discovery_steps": (credential.refund_discovery_steps + 1) % 10}
        try:
            payload = method._revolut_api_request(authority, "GET", "/api/orders", params={
                "limit": PAGE_LIMIT, "from": start, "to": end,
            })
            candidates = payload.get("orders")
            if not isinstance(candidates, list) or len(candidates) > PAGE_LIMIT:
                raise ValueError("invalid page")
        except (requests.RequestException, UserError, ValueError):
            self._discovery_evidence(credential, f"failed-window:{start}:{end}", "interrupted")
            if retrying:
                retries = retries[1:] + retries[:1]
            else:
                if [start, end] not in retries:
                    retries = retries + [[start, end]]
                windows = windows[1:]
            credential.write({**schedule, "refund_discovery_windows": windows,
                              "refund_discovery_retry_windows": retries})
            return

        self._resolve_discovery_evidence(credential, f"failed-window:{start}:{end}")

        # Provider candidate order is unspecified. Acquire the complete visible
        # source set before any per-candidate refund locks, rather than holding source
        # B while later waiting for source A against a native sorted contender.
        ReturnAllocation(self.env).acquire_discovery(sources, candidates=candidates)

        # Process even a full page before splitting. This gives immediate
        # reservations for visible refunds while the rest of the scan resumes.
        for candidate in candidates:
            if not isinstance(candidate, dict):
                self._discovery_evidence(credential, "malformed-page", "malformed_page")
                malformed = True
                continue
            if candidate.get("type") not in (
                "payment", "payment_request", "refund", "chargeback",
                "chargeback_reversal", "credit_reimbursement",
            ):
                self._discovery_evidence(credential, "malformed-page", "invalid_order_type")
                malformed = True
                continue
            if candidate.get("type") != "refund":
                continue
            with self.env.cr.savepoint():
                if self._discover_refund(credential, sources, method, authority, candidate) is False:
                    malformed = True

        if len(candidates) == PAGE_LIMIT:
            lower, upper = _date(start), _date(end)
            if upper - lower <= timedelta(microseconds=4):
                self._discovery_evidence(credential, f"saturated-window:{start}:{end}", "saturated_window")
                # The normal history queue must finish and restart despite a
                # permanently saturated interval. Retry it in a separate turn.
                if retrying:
                    retries = retries[1:] + retries[:1]
                else:
                    if [start, end] not in retries:
                        retries = retries + [[start, end]]
                    windows = windows[1:]
            else:
                middle = lower + (upper - lower) / 2
                children = [[_stamp(middle - timedelta(microseconds=1)), end],
                            [start, _stamp(middle + timedelta(microseconds=1))]]
                if retrying:
                    retries = retries[1:]
                    windows = children + windows
                else:
                    windows = children + windows[1:]
        else:
            if retrying:
                retries = retries[1:]
            else:
                windows = windows[1:]
            self._resolve_discovery_evidence(credential, f"saturated-window:{start}:{end}")
            self._resolve_discovery_evidence(credential, f"failed-window:{start}:{end}")
            if not retrying and not windows and not malformed:
                self._resolve_discovery_evidence(credential, "malformed-page")
        credential.write({**schedule, "refund_discovery_windows": windows,
                          "refund_discovery_retry_windows": retries,
                          "refund_discovery_had_malformed": malformed})

    @api.model
    def _discover_refund(self, credential, sources, method, authority, candidate):
        reference = candidate.get("id")
        try:
            if not isinstance(reference, str) or str(UUID(reference)) != reference:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            self._discovery_evidence(credential, "malformed-page", "invalid_identity")
            return False
        detail = None
        if candidate.get("related_order_id") is None:
            # List responses can omit the parent. Establish it from a full
            # read before deciding whether this refund concerns our payments.
            try:
                detail = self._validated_discovery_detail(method, authority, candidate)
            except (requests.RequestException, UserError, ValueError):
                self._discovery_evidence(credential, reference, "unmatched_source", candidate=candidate)
                return
            candidate = detail
        matches = sources.filtered(lambda item: item.revolut_order_id == candidate.get("related_order_id"))
        if len(matches) != 1:
            if matches:
                self._discovery_evidence(credential, reference, "ambiguous_source", candidate=candidate)
                return
            self._discover_unmatched_refund(credential, method, authority, candidate, detail=detail)
            return
        source = matches
        amount = candidate.get("amount")
        if (type(amount) is not int or not 0 < amount <= source._revolut_paid_minor()
                or candidate.get("currency") != source.currency_id.name):
            self._discovery_evidence(credential, reference, "amount_or_currency_mismatch", source, candidate)
            return
        try:
            detail = self._validated_discovery_detail(method, authority, candidate, detail=detail)
        except (requests.RequestException, UserError, ValueError):
            detail = None
        # Financial discovery uses the compatible source/refund suffix and
        # never requests native session, identity or sale locks afterward.
        ReturnAllocation(self.env).acquire_discovery(source)
        if (amount > source._revolut_paid_minor()
                or candidate.get("currency") != source.currency_id.name):
            self._discovery_evidence(credential, reference, "amount_or_currency_mismatch", source, candidate)
            return
        existing = self.sudo().search([("revolut_order_id", "=", reference)], limit=1)
        # The simplified list may omit an Odoo merchant reference. Consult the
        # authoritative detail before deciding this is an external refund.
        merchant = (detail if detail is not None else candidate).get("merchant_order_data")
        merchant_reference = merchant.get("reference") if isinstance(merchant, dict) else None
        if not isinstance(merchant_reference, str):
            merchant_reference = None
        by_key = self.sudo().search([("idempotency_key", "=", merchant_reference)], limit=1) if merchant_reference else self.browse()
        if existing and by_key and existing != by_key:
            self._discovery_evidence(credential, reference, "conflicting_reference", source, candidate)
            return
        existing = existing or by_key
        if existing and (existing.original_operation_id != source or existing.amount_minor != amount
                         or existing.currency_id != source.currency_id
                         or existing.revolut_order_id not in (False, reference)):
            self._discovery_evidence(credential, reference, "conflicting_reference", source, candidate)
            return
        if not existing:
            ambiguous = self.sudo().search_count([
                ("original_operation_id", "=", source.id), ("origin", "=", "odoo"),
                ("revolut_order_id", "=", False), ("amount_minor", "=", amount),
                ("state", "in", ["dispatching", "pending", "unresolved"]),
            ], limit=1) if not merchant_reference else 0
            if ambiguous:
                self._discovery_evidence(credential, reference, "ambiguous_odoo_attempt", source, candidate)
                return
            # No native return, tender UUID, product allocation or refund key is
            # invented. Even an unverified read reserves this financial amount.
            existing = self.sudo().create({
                "origin": "external", "original_operation_id": source.id,
                "pos_session_id": source.pos_session_id.id,
                "amount": amount / (10 ** source.currency_id.decimal_places),
                "amount_minor": amount, "currency_id": source.currency_id.id,
                "revolut_order_id": reference, "state": "unresolved",
            })
        if detail is None:
            self._discovery_evidence(credential, reference, "unverified_refund", source, candidate)
            return
        existing._record_provider_refund_time(detail)
        if existing.state not in {"verified", "failed"}:
            state = detail["state"]
            values = {"revolut_order_id": reference, "provider_state": state,
                      "state": "verified" if state == "completed" else "failed" if state in {"failed", "cancelled"} else "pending",
                      "local_outcome": False}
            if state == "completed":
                values["verified_at"] = fields.Datetime.now()
            existing.write(values)
        elif ((existing.state == "verified" and detail["state"] != "completed")
              or (existing.state == "failed" and detail["state"] not in {"failed", "cancelled"})):
            self._discovery_evidence(credential, reference, "conflicting_final_state", source, candidate)
            return
        self._resolve_discovery_evidence(credential, reference)

    @api.model
    def _validated_discovery_detail(self, method, authority, candidate, detail=None):
        reference = candidate["id"]
        if detail is None:
            detail = method._revolut_api_request(authority, "GET", f"/api/orders/{reference}")
        if "related_order_id" in detail and detail["related_order_id"] is None:
            raise ValueError("invalid refund parent")
        parent = candidate.get("related_order_id")
        if parent is None:
            parent = detail.get("related_order_id")
        if parent is not None and (not isinstance(parent, str) or str(UUID(parent)) != parent):
            raise ValueError("invalid refund parent")
        # Both observations come from authenticated provider GETs. Complement
        # an omitted field; a present null or conflicting parent must fail.
        if "related_order_id" not in detail and parent is not None:
            detail = {**detail, "related_order_id": parent}
        listed_merchant, detailed_merchant = candidate.get("merchant_order_data"), detail.get("merchant_order_data")
        listed_key = listed_merchant.get("reference") if isinstance(listed_merchant, dict) else None
        if isinstance(listed_key, str) and listed_key:
            if "merchant_order_data" not in detail:
                detail = {**detail, "merchant_order_data": {"reference": listed_key}}
            elif isinstance(detailed_merchant, dict) and "reference" not in detailed_merchant:
                detail = {**detail, "merchant_order_data": {**detailed_merchant, "reference": listed_key}}
            elif not isinstance(detailed_merchant, dict) or detailed_merchant.get("reference") != listed_key:
                raise ValueError("conflicting refund reference")
        # Read-only foreign metadata can exceed the integer ledger field.
        # Matching originals still enforce their paid ceiling before import.
        amount, currency = candidate.get("amount"), candidate.get("currency")
        if (type(amount) is not int or amount <= 0
                or not isinstance(currency, str) or len(currency) != 3
                or not currency.isascii() or not currency.isalpha() or not currency.isupper()):
            raise ValueError("invalid refund amount or currency")
        method._validate_refund_response({
            **authority, "order_id": reference, "original_order_id": parent,
            "amount_minor": amount, "currency_code": currency,
        }, detail)
        return detail

    @api.model
    def _discover_unmatched_refund(self, credential, method, authority, candidate, detail=None):
        # An unrelated Merchant refund must not disable every POS sale. Exclude
        # it only after a full read and checking all integration payments,
        # including unverified/legacy originals and other credential scopes.
        reference, parent = candidate["id"], candidate.get("related_order_id")
        amount, currency = candidate.get("amount"), candidate.get("currency")
        if parent is None and detail is not None and self._outside_integration_location(credential, detail):
            self._discovery_evidence(credential, reference, "outside_integration_location", candidate=candidate)
            return
        try:
            if not isinstance(parent, str) or str(UUID(parent)) != parent:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            self._discovery_evidence(credential, reference, "unmatched_source", candidate=candidate)
            return
        known = self.env["pos.revolut.payment.operation"].sudo().with_context(active_test=False).search([
            ("revolut_order_id", "=", parent),
        ])
        if known:
            scoped = known.filtered(lambda source:
                source.credential_id == credential and source.company_id == credential.company_id
                and source.environment == credential.environment
                and source.secret_reference == credential.secret_reference
            )
            self._discovery_evidence(
                credential, reference, "unverified_original" if scoped else "conflicting_original_authority",
                scoped if len(scoped) == 1 else None, candidate,
            )
            return
        if (type(amount) is not int or not 0 < amount <= 2147483647
                or not isinstance(currency, str) or len(currency) != 3
                or not currency.isascii() or not currency.isalpha() or not currency.isupper()):
            self._discovery_evidence(credential, reference, "unmatched_source", candidate=candidate)
            return
        try:
            detail = self._validated_discovery_detail(method, authority, candidate, detail=detail)
        except (requests.RequestException, UserError, ValueError):
            self._discovery_evidence(credential, reference, "unmatched_source", candidate=candidate)
            return
        if self._known_discovery_reference(detail):
            self._discovery_evidence(credential, reference, "conflicting_reference", candidate=candidate)
            return
        self._discovery_evidence(credential, reference, "unrelated_source", candidate=candidate)

    @api.model
    def _outside_integration_location(self, credential, detail):
        # A shared Merchant account can contain other POS locations. Retain
        # their final observations without an account-wide integration block.
        # This never proves a card balance: dispatch still validates the exact
        # original's refunded_amount against its verified local refund ledger.
        location = detail.get("location_id")
        if detail["state"] not in {"completed", "failed", "cancelled"}:
            return False
        try:
            if not isinstance(location, str) or str(UUID(location)) != location:
                return False
        except (ValueError, TypeError, AttributeError):
            return False
        if self._known_discovery_reference(detail):
            return False
        payments = self.env["pos.revolut.payment.operation"].sudo().with_context(active_test=False)
        if payments.search_count([
            ("secret_reference", "=", credential.secret_reference),
            ("environment", "=", credential.environment), ("location_id", "=", location),
        ], limit=1):
            return False
        return not self.env["pos.payment.method"].sudo().with_context(active_test=False).search_count([
            ("revolut_secret_reference", "=", credential.secret_reference),
            ("revolut_environment", "=", credential.environment),
            ("revolut_location_id", "=", location),
        ], limit=1)

    @api.model
    def _known_discovery_reference(self, detail):
        merchant = detail.get("merchant_order_data")
        key = merchant.get("reference") if isinstance(merchant, dict) else None
        refund_domain = [("revolut_order_id", "=", detail["id"])]
        if isinstance(key, str) and key:
            refund_domain = ["|", *refund_domain, ("idempotency_key", "=", key)]
        if self.sudo().search_count(refund_domain, limit=1):
            return True
        payments = self.env["pos.revolut.payment.operation"].sudo().with_context(active_test=False)
        return bool(payments.search_count([
            ("revolut_order_id", "=", detail["id"]),
        ], limit=1))

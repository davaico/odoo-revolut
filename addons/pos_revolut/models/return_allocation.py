"""Return invariants shared by source discovery, reservation, and checkout."""

from dataclasses import dataclass
from decimal import Decimal

from odoo import _
from odoo.exceptions import AccessError, UserError


@dataclass(frozen=True)
class ReservationClaim:
    operation_id: int
    existing_status: dict | None = None
    source_amount_minor: int | None = None
    verified_before_claim: int | None = None


class ReturnAllocation:
    def __init__(self, env):
        self.env = env

    def _normalize_return(self, data):
        snapshot = self.env["pos.revolut.payment.operation"].normalize_financial_snapshot(data)
        try:
            originals = {}
            for raw in data["lines"]:
                line = raw[2] if isinstance(raw, (tuple, list)) else raw
                originals[line["uuid"]] = int(line["refunded_orderline_id"])
            for line in snapshot["lines"]:
                line["refunded_orderline_id"] = originals[line["uuid"]]
                if not line["refunded_orderline_id"] or Decimal(line["qty"]) >= 0:
                    raise ValueError()
        except (KeyError, ValueError, TypeError):
            raise UserError(_("Use the normal POS return flow for the original sale.")) from None
        return snapshot

    def _return_original(self, snapshot, session):
        ids = [line["refunded_orderline_id"] for line in snapshot["lines"]]
        originals = self.env["pos.order.line"].browse(ids).exists()
        originals.check_access("read")
        orders = originals.order_id
        if len(originals) != len(ids) or len(set(ids)) != len(ids) or len(orders) != 1:
            raise UserError(_("Return lines must belong to one original sale."))
        original = orders
        if original.company_id != session.company_id or original.currency_id != session.currency_id:
            raise AccessError(_("The original sale belongs to another company or currency."))
        if original.state not in {"paid", "done", "invoiced"}:
            raise UserError(_("Only a return of a completed sale is supported."))
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        if normalize(session.currency_id, original.amount_total)[1] <= 0:
            raise UserError(_("The original sale amount is invalid."))
        by_id = {line.id: line for line in originals}
        for line in snapshot["lines"]:
            old = by_id[line["refunded_orderline_id"]]
            if (Decimal(line["qty"]) < -Decimal(str(old.qty))
                    or old.qty <= 0 or line["product_id"] != old.product_id.id
                    or Decimal(line["price_unit"]) != Decimal(str(old.price_unit))
                    or Decimal(line["discount"]) != Decimal(str(old.discount))
                    or line["tax_ids"] != sorted(old.tax_ids.ids)):
                raise UserError(_("Return no more than the original quantity with unchanged prices, discounts and taxes."))
        if (snapshot["pricelist_id"] != original.pricelist_id.id
                or snapshot["fiscal_position_id"] != (original.fiscal_position_id.id or 0)):
            raise UserError(_("The return's price list or fiscal position changed."))
        return original

    def _return_total_minor(self, snapshot, original, currency):
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        by_id = {line.id: line for line in original.lines}
        return sum(normalize(
            currency,
            Decimal(str(by_id[line["refunded_orderline_id"]].price_subtotal_incl))
            * -Decimal(line["qty"]) / Decimal(str(by_id[line["refunded_orderline_id"]].qty)),
        )[1] for line in snapshot["lines"])

    def _validate_return_quantities(self, snapshot, original, order_uuid):
        requested = {line["refunded_orderline_id"]: -Decimal(line["qty"]) for line in snapshot["lines"]}
        used = {line.id: Decimal(0) for line in original.lines}
        completed = self.env["pos.order.line"].sudo().search([
            ("refunded_orderline_id", "in", original.lines.ids),
            ("order_id.state", "in", ["paid", "done", "invoiced"]),
        ])
        for line in completed:
            if line.order_id.uuid != order_uuid:
                used[line.refunded_orderline_id.id] -= Decimal(str(line.qty))
        reservations = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id.pos_order_id", "=", original.id),
            ("state", "!=", "failed"),
        ])
        pending_by_return = {}
        for reservation in reservations:
            if reservation.order_uuid == order_uuid or (reservation.pos_order_id and reservation.pos_order_id.state in {"paid", "done", "invoiced"}):
                continue
            prior = pending_by_return.setdefault(reservation.order_uuid, reservation.financial_snapshot)
            if prior != reservation.financial_snapshot:
                raise UserError(_("An earlier refund has inconsistent return details. Reconcile it first."))
        for prior in pending_by_return.values():
            for line in prior["lines"]:
                old_id = line["refunded_orderline_id"]
                if old_id in used:
                    used[old_id] -= Decimal(line["qty"])
        if any(used.get(line.id, 0) + requested.get(line.id, 0) > Decimal(str(line.qty)) for line in original.lines):
            raise UserError(_("The return exceeds the original quantity after earlier returns and reservations."))

    def _eligible_sources(self, original, session):
        sources = self.env["pos.revolut.payment.operation"].sudo().browse()
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        for payment in original.payment_ids.sudo():
            source = payment.revolut_operation_id
            if not source:
                continue
            if (source.state != "verified" or source.pos_order_id != original
                    or source.pos_payment_id != payment or source.company_id != session.company_id
                    or source.currency_id != session.currency_id
                    or source.amount_minor != normalize(session.currency_id, payment.amount)[1]
                    or payment.transaction_id != source.revolut_payment_id
                    or not source.revolut_order_id or not source.revolut_payment_id):
                raise UserError(_("An original Revolut payment is not verified or does not match this sale."))
            sources |= source
        return sources

    def _validate_original(self, snapshot, method, session, amount_minor, original_operation_id=None):
        original = self._return_original(snapshot, session)
        sources = self._eligible_sources(original, session)
        if not sources:
            raise UserError(_("The original sale has no verified Revolut payment."))
        if original_operation_id:
            source = sources.filtered(lambda item: item.id == original_operation_id)
        elif len(sources) == 1:
            source = sources
        else:
            raise UserError(_("Select the original Revolut payment for this refund allocation."))
        if len(source) != 1 or source.payment_method_id != method or amount_minor > source.amount_minor:
            raise UserError(_("The refund allocation does not match an eligible original Revolut payment."))
        return source

    def _check_total(self, snapshot, original, currency, total_minor):
        if total_minor != self._return_total_minor(snapshot, original, currency):
            raise UserError(_("The return total does not match its original sale lines."))

    def _lock_original_return(self, snapshot, original, order_uuid):
        # A row update also makes stale repeatable-read contenders retry.
        # Both reservation and checkout need this lock before checking quantities.
        self.env.cr.execute(
            "UPDATE pos_order SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s",
            [original.id],
        )
        self._validate_return_quantities(snapshot, original, order_uuid)

    def sources(self, session, financial_snapshot):
        """Advisory balances for the manager's allocation picker."""
        snapshot = self._normalize_return(financial_snapshot)
        original = self._return_original(snapshot, session)
        total_minor = self.env["pos.revolut.payment.operation"].normalize_amount(
            session.currency_id, -Decimal(str(financial_snapshot.get("amount_total")))
        )[1]
        self._check_total(snapshot, original, session.currency_id, total_minor)
        refunds = self.env["pos.revolut.refund.operation"].sudo()
        result = []
        for source in self._eligible_sources(original, session):
            reserved = sum(refunds.search([
                ("original_operation_id", "=", source.id), ("state", "!=", "failed"),
            ]).mapped("amount_minor"))
            remaining = max(0, source.amount_minor - reserved)
            result.append({
                "operation_id": source.id, "payment_method_id": source.payment_method_id.id,
                "payment_method_name": source.payment_method_id.name,
                "original_order_id": source.revolut_order_id,
                "original_payment_id": source.revolut_payment_id,
                "amount_minor": source.amount_minor, "remaining_minor": remaining,
                "remaining_amount": remaining / (10 ** session.currency_id.decimal_places),
                "currency_id": session.currency_id.id,
            })
        return result

    def reserve(self, method, session, order_uuid, payment_line_uuid, normalized,
                minor, currency, financial_snapshot, original_operation_id):
        """Authoritative claim in the caller's dedicated reservation transaction."""
        snapshot = self._normalize_return(financial_snapshot)
        raw_total = financial_snapshot.get("amount_total") if isinstance(financial_snapshot, dict) else None
        if raw_total is None:
            raise UserError(_("The requested return total is missing."))
        try:
            return_total_minor = self.env["pos.revolut.payment.operation"].normalize_amount(
                currency, -Decimal(str(raw_total))
            )[1]
        except (ValueError, ArithmeticError):
            raise UserError(_("The return total is invalid.")) from None
        if return_total_minor <= 0 or minor > return_total_minor:
            raise UserError(_("The Revolut allocation exceeds the return total."))
        if original_operation_id:
            try:
                original_operation_id = int(original_operation_id)
            except (ValueError, TypeError):
                raise UserError(_("Select a valid original Revolut payment.")) from None
        original = self._return_original(snapshot, session)
        self._check_total(snapshot, original, currency, return_total_minor)

        refunds = self.env["pos.revolut.refund.operation"].sudo()
        charges = self.env["pos.revolut.payment.operation"].sudo()
        charges.lock_order(method.company_id.id, order_uuid)
        if charges.search_count([
            ("company_id", "=", method.company_id.id), ("order_uuid", "=", order_uuid),
        ]):
            raise UserError(_("A Revolut charge already exists for this return. Reconcile it first."))
        existing = refunds.search([
            ("company_id", "=", method.company_id.id), ("order_uuid", "=", order_uuid),
            ("payment_line_uuid", "=", payment_line_uuid),
        ], limit=1)
        if existing:
            if (existing.payment_method_id.id != method.id
                    or existing.amount_minor != minor or existing.currency_id.id != currency.id
                    or existing.pos_session_id.id != session.id or existing.financial_snapshot != snapshot
                    or (original_operation_id and existing.original_operation_id.id != original_operation_id)):
                raise UserError(_("The existing refund has different return details."))
            return ReservationClaim(existing.id, existing_status=existing._snapshot())

        source = self._validate_original(snapshot, method, session, minor, original_operation_id)
        self._lock_original_return(snapshot, original, order_uuid)
        # Lock the selected source after the original sale, in the same order
        # for every contender. It serializes refundable balance decisions.
        self.env.cr.execute(
            "UPDATE pos_revolut_payment_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s",
            [source.id],
        )
        source_refunds = refunds.search([
            ("original_operation_id", "=", source.id), ("state", "!=", "failed"),
        ])
        reserved = sum(source_refunds.mapped("amount_minor"))
        verified_before_claim = sum(source_refunds.filtered(
            lambda item: item.state == "verified"
        ).mapped("amount_minor"))
        if reserved + minor > source.amount_minor:
            raise UserError(_("The original Revolut payment has insufficient refundable balance."))
        return_refunds = refunds.search([
            ("company_id", "=", method.company_id.id), ("order_uuid", "=", order_uuid),
        ])
        if any(item.financial_snapshot != snapshot or item.pos_session_id.id != session.id
               or item.return_total_minor not in (0, return_total_minor) for item in return_refunds):
            raise UserError(_("The return changed after a refund allocation was reserved."))
        if sum(item.amount_minor for item in return_refunds if item.state != "failed") + minor > return_total_minor:
            raise UserError(_("Revolut allocations exceed the return total."))
        if self.env["pos.order"].sudo().search_count([
            ("uuid", "=", order_uuid), ("state", "!=", "draft"),
        ]):
            raise UserError(_("This return has already been completed."))
        refund = refunds.create({
            "original_operation_id": source.id, "pos_session_id": session.id,
            "order_uuid": order_uuid, "payment_line_uuid": payment_line_uuid,
            "amount": float(normalized), "amount_minor": minor,
            "return_total_minor": return_total_minor,
            "currency_id": currency.id, "financial_snapshot": snapshot,
        })
        return ReservationClaim(
            refund.id, source_amount_minor=source.amount_minor,
            verified_before_claim=verified_before_claim,
        )

    def validate_settlement(self, order, existing_order, payments):
        session = self.env["pos.session"].browse(order["session_id"]).exists()
        if not session:
            raise UserError(_("The Point of Sale session does not exist."))
        order_uuid = order.get("uuid") or (existing_order and existing_order.uuid)
        self.env["pos.revolut.payment.operation"].sudo().lock_order(session.company_id.id, order_uuid)
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", session.company_id.id), ("order_uuid", "=", order_uuid),
        ])
        # Find original return relationships even before a Revolut operation
        # exists, so selecting cash cannot bypass the verified-refund boundary.
        original_ids = []
        for raw in order.get("lines", []):
            line = raw[2] if isinstance(raw, (tuple, list)) and len(raw) > 2 else raw
            if isinstance(line, dict) and line.get("refunded_orderline_id"):
                original_ids.append(line["refunded_orderline_id"])
        if existing_order:
            original_ids += existing_order.lines.refunded_orderline_id.ids
        original_lines = self.env["pos.order.line"].sudo().browse(original_ids).exists()
        source_revolut = original_lines.order_id.payment_ids.filtered(
            lambda payment: payment.payment_method_id.use_payment_terminal == "revolut" or payment.revolut_operation_id
        )
        references = [value.get("transaction_id") for value in payments.values() if value.get("transaction_id")]
        copied = self.env["pos.revolut.refund.operation"].sudo().search([
            "|", ("payment_line_uuid", "in", list(payments)), ("revolut_order_id", "in", references),
        ]) if payments else refunds.browse()
        if any(item not in refunds for item in copied):
            raise UserError(_("A Revolut refund belongs to another return."))
        if any(value.get("transaction_id") == item.revolut_order_id and value["uuid"] != item.payment_line_uuid
               for item in copied if item.revolut_order_id for value in payments.values()):
            raise UserError(_("A Revolut refund reference belongs to another return payment line."))
        negative_revolut = any(
            value.get("amount", 0) < 0 and self.env["pos.payment.method"].browse(value.get("payment_method_id")).use_payment_terminal == "revolut"
            for value in payments.values()
        )
        if not refunds and not source_revolut and not negative_revolut:
            return None
        if refunds:
            self.env.cr.execute("SELECT id FROM pos_revolut_refund_operation WHERE id = ANY(%s) ORDER BY id FOR UPDATE", [refunds.ids])
            refunds.invalidate_recordset()
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        total_minor = normalize(session.currency_id, order.get("amount_total"))[1]
        if total_minor >= 0:
            raise UserError(_("A Revolut-linked return must have a negative total."))
        snapshot = self._normalize_return(order)
        original = self._return_original(snapshot, session)
        # Cash-only returns of a mixed-tender sale use the same original-sale lock.
        self._lock_original_return(snapshot, original, order_uuid)
        self._check_total(snapshot, original, session.currency_id, -total_minor)
        active = refunds.filtered(lambda item: item.state != "failed")
        verified = refunds.browse()
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            payment = payments.get(refund.payment_line_uuid)
            if refund.state == "failed":
                if payment and payment.get("payment_status") == "done":
                    raise UserError(_("A failed Revolut refund cannot complete a return payment."))
                continue
            if (not payment or snapshot != refund.financial_snapshot
                    or refund.original_order_id != original
                    or refund.pos_session_id != session or refund.currency_id != session.currency_id
                    or (refund.return_total_minor and refund.return_total_minor != -total_minor)
                    or (refund.pos_order_id and refund.pos_order_id != existing_order)
                    or payment.get("payment_method_id") != refund.payment_method_id.id
                    or normalize(session.currency_id, payment.get("amount"))[1] != -refund.amount_minor):
                raise UserError(_("The return changed after a Revolut refund allocation was reserved."))
            if refund.state != "verified":
                if order.get("state") != "draft" or payment.get("payment_status") == "done":
                    raise UserError(_("Only completed Revolut refunds can complete this return."))
                continue
            if payment.get("payment_status") != "done" or payment.get("transaction_id") != refund.revolut_order_id:
                raise UserError(_("The refund payment details do not match Revolut verification."))
            verified |= refund
        if sum(active.mapped("amount_minor")) > -total_minor:
            raise UserError(_("Revolut allocations exceed the return total."))
        for payment in payments.values():
            method = self.env["pos.payment.method"].browse(payment.get("payment_method_id"))
            payment_minor = normalize(session.currency_id, payment.get("amount"))[1]
            if payment_minor > 0:
                raise UserError(_("Return payment allocations must not contain a positive tender."))
            if (method.use_payment_terminal == "revolut" and payment_minor < 0
                    and payment["uuid"] not in active.mapped("payment_line_uuid")
                    and (order.get("state") != "draft" or payment.get("payment_status") == "done")):
                raise UserError(_("A Revolut refund payment has no verified allocation."))
        # Non-Revolut tender remains limited to its original payment method,
        # including cash-only partial returns of a mixed-tender sale.
        original_nonrevolut = {}
        for original_payment in original.payment_ids.sudo().filtered(lambda item: item.payment_method_id.use_payment_terminal != "revolut"):
            method_id = original_payment.payment_method_id.id
            original_nonrevolut[method_id] = original_nonrevolut.get(method_id, 0) + normalize(session.currency_id, original_payment.amount)[1]
        current_nonrevolut = {}
        for item in payments.values():
            method_id = item.get("payment_method_id")
            method = self.env["pos.payment.method"].browse(method_id)
            amount_minor = normalize(session.currency_id, item.get("amount"))[1]
            if method.use_payment_terminal != "revolut" and amount_minor < 0:
                current_nonrevolut[method_id] = current_nonrevolut.get(method_id, 0) - amount_minor
        for method_id, current_minor in current_nonrevolut.items():
            original_minor = original_nonrevolut.get(method_id, 0)
            prior = self.env["pos.payment"].sudo().search([
                ("pos_order_id.lines.refunded_orderline_id", "in", original.lines.ids),
                ("pos_order_id.state", "in", ["paid", "done", "invoiced"]),
                ("payment_method_id", "=", method_id), ("amount", "<", 0),
            ])
            prior_minor = -sum(normalize(session.currency_id, item.amount)[1] for item in prior if not existing_order or item.pos_order_id != existing_order)
            if prior_minor + current_minor > original_minor:
                raise UserError(_("The non-Revolut refund exceeds its original tender."))
        if order.get("state") != "draft":
            if len(verified) != len(active):
                raise UserError(_("Reconcile every Revolut allocation before completing the return."))
            if sum(normalize(session.currency_id, item.get("amount"))[1] for item in payments.values()) != total_minor:
                raise UserError(_("Return allocations do not match the requested return total."))
        return verified

    def link_settled_refunds(self, refunds, pos_order):
        for refund in refunds:
            payment = pos_order.payment_ids.filtered(lambda item: item.uuid == refund.payment_line_uuid)
            if len(payment) != 1:
                raise UserError(_("The verified Revolut refund payment was not saved."))
            payment.write({"revolut_refund_operation_id": refund.id,
                           "transaction_id": refund.revolut_order_id,
                           "revolut_order_id": refund.revolut_order_id,
                           "payment_ref_no": refund.revolut_order_id})
            refund.write({"pos_order_id": pos_order.id, "pos_payment_id": payment.id})

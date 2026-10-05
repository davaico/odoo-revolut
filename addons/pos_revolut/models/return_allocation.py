"""Return invariants shared by source discovery, reservation, and checkout."""

from dataclasses import dataclass
from decimal import Decimal

from odoo import _
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_round

from .financial_snapshot import MAX_LINES, check_line_count, check_line_count_size, snapshot_id


@dataclass(frozen=True)
class ReservationClaim:
    operation_id: int
    existing_status: dict | None = None
    source_amount_minor: int | None = None
    verified_before_claim: int | None = None
    source_base_minor: int | None = None
    source_tip_minor: int | None = None


class ReturnAllocation:
    def __init__(self, env):
        self.env = env

    def _normalize_return(self, data, *, native_order=False):
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(
            data, native_order=native_order
        )
        try:
            for line in snapshot["lines"]:
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
        original.config_id._check_revolut_register_access(session=original.session_id, order=original)
        session.config_id._check_revolut_register_access(session=session)
        if original.config_id != session.config_id:
            raise AccessError(_("Refunds must use the original Point of Sale register."))
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

    def _return_line_total_minor(self, snapshot, original, currency):
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        by_id = {line.id: line for line in original.lines}
        return sum(normalize(
            currency,
            Decimal(str(by_id[line["refunded_orderline_id"]].price_subtotal_incl))
            * -Decimal(line["qty"]) / Decimal(str(by_id[line["refunded_orderline_id"]].qty)),
        )[1] for line in snapshot["lines"])

    def _return_total_minor(self, snapshot, original, currency, order_uuid=None):
        base, tip = self._return_components(snapshot, original, currency, order_uuid)
        return base + tip

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
            ("origin", "=", "odoo"),
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
            source.with_env(self.env)._check_revolut_register_access()
            if source.pos_config_id != session.config_id:
                raise AccessError(_("The original Revolut payment belongs to another register."))
            if (source.state != "verified" or source.pos_order_id != original
                    or source.pos_payment_id != payment or source.company_id != session.company_id
                    or source.currency_id != session.currency_id
                    or source._revolut_paid_minor() != normalize(session.currency_id, payment.amount)[1]
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
        if len(source) != 1 or source.payment_method_id != method or amount_minor > source._revolut_paid_minor():
            raise UserError(_("The refund allocation does not match an eligible original Revolut payment."))
        return source

    def _check_total(self, snapshot, original, currency, total_minor, order_uuid=None, *, frozen_total=None):
        line_total = self._return_line_total_minor(snapshot, original, currency)
        accepted = {line_total}
        if frozen_total is None:
            accepted.add(self._return_total_minor(snapshot, original, currency, order_uuid))
        elif frozen_total:
            accepted.add(frozen_total)
        authority = original.revolut_authorization_id.sudo()
        if authority:
            rounding = authority.rounding
            if rounding["enabled"] and not rounding["cash_only"]:
                # Native clients may still submit the whole-return rounded
                # display total. It is only a checked transport representation;
                # refund capacity is always the separate frozen base plus tip.
                rounded = float_round(line_total / 10**currency.decimal_places,
                                      precision_rounding=rounding["quantum"],
                                      rounding_method=rounding["method"])
                accepted.add(self.env["pos.revolut.payment.operation"].normalize_amount(currency, rounded)[1])
        if total_minor not in accepted:
            raise UserError(_("The return total does not match its original sale lines."))

    def _lock_original_return(self, snapshot, original, order_uuid):
        # A row update also makes stale repeatable-read contenders retry.
        # Both reservation and checkout need this lock before checking quantities.
        self.env.cr.execute(
            "UPDATE pos_order SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s",
            [original.id],
        )
        self._validate_return_quantities(snapshot, original, order_uuid)

    def _source_components(self, source):
        """Historical amounts stay base-only; new amounts need verified evidence."""
        if not source.authorization_id:
            return source.amount_minor, 0, False
        gross = source._revolut_paid_minor()
        if (not source.terminal_tip_evidence or source.terminal_tip_minor < 0 or gross <= 0
                or gross != source.amount_minor + source.terminal_tip_minor):
            raise UserError(_("The original payment's base and terminal tip evidence are inconsistent."))
        return source.amount_minor, source.terminal_tip_minor, True

    def _original_line_entitlements(self, original, currency):
        # Freeze product identity and base cash rounding independently of tips.
        # Full base returns refund P, not unrounded T. For partial returns,
        # assign each original line its proportion of P once; the final UUID
        # retains the minor-unit remainder, so all line ceilings sum exactly P.
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        sources = self._eligible_sources(original, original.session_id)
        authorities = sources.filtered(lambda item: item.authorization_id).authorization_id
        if not authorities:
            # Historical sales retain their recorded line ceilings and have no
            # authority to classify a currently configured tip product.
            entitlements = {line.id: (normalize(currency, line.price_subtotal_incl)[1], 0)
                            for line in original.lines}
            if sum(base for base, _tip in entitlements.values()) != normalize(currency, original.amount_total)[1]:
                raise UserError(_("The historical sale has no trustworthy per-line rounding basis. Reconcile it before another return."))
            return entitlements
        tip_products = authorities.tip_product_id
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        original_base = original.lines.filtered(lambda line: line.product_id not in tip_products).sorted("uuid")
        allocation = {line.id: normalize(currency, line.price_subtotal_incl)[1] for line in original_base}
        if len(authorities) != 1:
            raise UserError(_("The original sale has inconsistent frozen cart authority."))
        authority = authorities
        raw_base = sum(allocation.values())
        if raw_base <= 0:
            raise UserError(_("The original base line allocations are invalid."))
        if authority.payable_minor != raw_base:
            # Native global tax rounding may itself make the whole-cart total
            # differ from summed line totals. The immutable payable authority
            # supplies the final ceiling, while original line amounts supply
            # only relative weights, never extra payment entitlement.
            remaining = authority.payable_minor
            for line in original_base[:-1]:
                minor = normalize(currency, Decimal(allocation[line.id])
                                  * Decimal(authority.payable_minor) / Decimal(raw_base)
                                  / (10 ** currency.decimal_places))[1]
                allocation[line.id] = minor
                remaining -= minor
            allocation[original_base[-1].id] = remaining
        return {line.id: ((0, normalize(currency, line.price_subtotal_incl)[1])
                          if line.product_id in tip_products else (allocation[line.id], 0))
                for line in original.lines}

    def _historical_return_allocation(self, snapshot, target, entitlements):
        # A whole-return amount only proves its line allocation when one original
        # line was returned. Do not invent a product split for older documents.
        if len(snapshot["lines"]) != 1 or type(target) is not int or target < 0:
            raise UserError(_("An earlier return has no trustworthy per-line monetary allocation. Reconcile its history before another return."))
        line = snapshot["lines"][0]
        old_id = line["refunded_orderline_id"]
        base, tip = entitlements[old_id]
        return [{"original_line_id": old_id, "quantity": str(-Decimal(line["qty"])),
                 "base_minor": target if not tip else 0,
                 "tip_minor": target if tip else 0}]

    def _validate_line_allocation(self, allocation, snapshot, entitlements):
        requested = {line["refunded_orderline_id"]: -Decimal(line["qty"])
                     for line in snapshot["lines"]}
        try:
            if not isinstance(allocation, list) or len(allocation) != len(requested):
                raise ValueError()
            seen = set()
            for row in allocation:
                old_id = row["original_line_id"]
                base, tip = row["base_minor"], row["tip_minor"]
                if (type(old_id) is not int or old_id in seen or old_id not in requested
                        or Decimal(row["quantity"]) != requested[old_id]
                        or type(base) is not int or type(tip) is not int
                        or base < 0 or tip < 0
                        or base > entitlements[old_id][0] or tip > entitlements[old_id][1]):
                    raise ValueError()
                seen.add(old_id)
        except (KeyError, ValueError, TypeError, ArithmeticError):
            raise UserError(_("An earlier return has inconsistent per-line monetary evidence. Reconcile it first.")) from None
        return allocation

    def _return_allocation(self, snapshot, original, currency, order_uuid=None):
        """Allocate residual quantity and money once per native return identity.

        Callers establishing a dispatch claim hold the original-sale row lock.
        Discovery may project the same calculation but does not reserve it.
        Removing a definitively failed return subtracts neither its quantities
        nor its cents; all other saved allocations remain immutable.
        """
        entitlements = self._original_line_entitlements(original, currency)
        completed = self.env["pos.order"].sudo().search([
            ("lines.refunded_orderline_id", "in", original.lines.ids),
            ("state", "in", ["paid", "done", "invoiced"]),
        ])
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        completed_by_uuid = {order.uuid: order for order in completed}
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id.pos_order_id", "=", original.id),
            ("origin", "=", "odoo"), ("state", "!=", "failed"),
        ], order="id")
        claims = {}
        snapshots = {}
        for refund in refunds:
            prior = snapshots.setdefault(refund.order_uuid, refund.financial_snapshot)
            if prior != refund.financial_snapshot:
                raise UserError(_("An earlier refund has inconsistent return details. Reconcile it first."))
            allocation = refund.return_allocation
            if not allocation:
                target = refund.return_total_minor
                native = completed_by_uuid.get(refund.order_uuid)
                if not target and native:
                    target = -normalize(currency, native.amount_total)[1]
                if not target:
                    raise UserError(_("An earlier refund has no trustworthy return target. Reconcile its history before another return."))
                allocation = self._historical_return_allocation(prior, target, entitlements)
            self._validate_line_allocation(allocation, prior, entitlements)
            previous = claims.setdefault(refund.order_uuid, allocation)
            if previous != allocation:
                raise UserError(_("An earlier refund has inconsistent per-line monetary evidence. Reconcile it first."))
            if (refund.return_total_minor
                    and sum(row["base_minor"] + row["tip_minor"] for row in allocation) != refund.return_total_minor):
                raise UserError(_("An earlier refund has inconsistent return target evidence. Reconcile it first."))
        for order in completed:
            prior = self._normalize_return(order._revolut_order_values(), native_order=True)
            allocation = order.revolut_return_allocation or claims.get(order.uuid)
            if not allocation:
                allocation = self._historical_return_allocation(
                    prior, -normalize(currency, order.amount_total)[1], entitlements)
            self._validate_line_allocation(allocation, prior, entitlements)
            if sum(row["base_minor"] + row["tip_minor"] for row in allocation) != -normalize(currency, order.amount_total)[1]:
                raise UserError(_("An earlier return's native total and refund allocations disagree. Reconcile it first."))
            if order.uuid in claims and claims[order.uuid] != allocation:
                raise UserError(_("An earlier return's native and refund allocations disagree. Reconcile it first."))
            claims[order.uuid] = allocation
            snapshots[order.uuid] = prior
        if not order_uuid:
            matching = [uuid for uuid, prior in snapshots.items() if prior == snapshot]
            if len(matching) == 1:
                order_uuid = matching[0]
        if order_uuid in claims:
            if snapshots[order_uuid] != snapshot:
                raise UserError(_("The return changed after its monetary allocation was reserved."))
            return claims[order_uuid]
        used_qty = {line.id: Decimal(0) for line in original.lines}
        used_base = dict.fromkeys(entitlements, 0)
        used_tip = dict.fromkeys(entitlements, 0)
        for allocation in claims.values():
            for row in allocation:
                old_id = row["original_line_id"]
                used_qty[old_id] += Decimal(row["quantity"])
                used_base[old_id] += row["base_minor"]
                used_tip[old_id] += row["tip_minor"]
        by_id = {line.id: line for line in original.lines}
        result = []
        for line in snapshot["lines"]:
            old_id = line["refunded_orderline_id"]
            quantity = -Decimal(line["qty"])
            remaining_qty = Decimal(str(by_id[old_id].qty)) - used_qty[old_id]
            remaining_base = entitlements[old_id][0] - used_base[old_id]
            remaining_tip = entitlements[old_id][1] - used_tip[old_id]
            if (remaining_qty <= 0 or quantity > remaining_qty
                    or remaining_base < 0 or remaining_tip < 0):
                raise UserError(_("The return exceeds the original quantity or remaining monetary entitlement."))
            row = {"original_line_id": old_id, "quantity": str(quantity)}
            for name, remaining in (("base_minor", remaining_base), ("tip_minor", remaining_tip)):
                row[name] = (remaining if quantity == remaining_qty else normalize(
                    currency, Decimal(remaining) * quantity / remaining_qty
                    / (10 ** currency.decimal_places))[1])
            result.append(row)
        return result

    def _return_components(self, snapshot, original, currency, order_uuid=None):
        allocation = self._return_allocation(snapshot, original, currency, order_uuid)
        return (sum(row["base_minor"] for row in allocation),
                sum(row["tip_minor"] for row in allocation))

    def _refund_components(self, refund):
        return ((refund.base_amount_minor, refund.tip_amount_minor)
                if refund.allocation_explicit else (refund.amount_minor, 0))

    def _allocation(self, source, minor, base_minor, tip_minor, reserved):
        base, tip, explicit = self._source_components(source)
        if not explicit:
            if tip_minor not in (None, 0) or base_minor not in (None, minor):
                raise UserError(_("Historical payments have no terminal tip evidence."))
            return minor, 0, False
        if base_minor is None and tip_minor is None and not reserved and minor == base + tip:
            return base, tip, True
        if (type(base_minor) is not int or type(tip_minor) is not int
                or base_minor < 0 or tip_minor < 0 or base_minor + tip_minor != minor):
            raise UserError(_("Specify the base and terminal tip amounts for this partial refund in currency minor units."))
        return base_minor, tip_minor, True

    def sources(self, session, financial_snapshot):
        """Advisory balances for the manager's allocation picker."""
        snapshot = self._normalize_return(financial_snapshot)
        original = self._return_original(snapshot, session)
        total_minor = self.env["pos.revolut.payment.operation"].normalize_amount(
            session.currency_id, -Decimal(str(financial_snapshot.get("amount_total")))
        )[1]
        order_uuid = financial_snapshot.get("uuid")
        self._check_total(snapshot, original, session.currency_id, total_minor, order_uuid)
        return_base, return_tip = self._return_components(snapshot, original, session.currency_id, order_uuid)
        refunds = self.env["pos.revolut.refund.operation"].sudo()
        result = []
        for source in self._eligible_sources(original, session):
            base, tip, explicit = self._source_components(source)
            claimed = refunds.search([
                ("original_operation_id", "=", source.id), ("state", "!=", "failed"),
            ])
            reserved = sum(claimed.mapped("amount_minor"))
            allocations = [self._refund_components(item) for item in claimed]
            remaining_base = max(0, base - sum(item[0] for item in allocations))
            remaining_tip = max(0, tip - sum(item[1] for item in allocations))
            remaining = max(0, source._revolut_paid_minor() - reserved)
            needs_review = source.external_refund_review_required
            unknown_components = tip and any(item.origin == "external" for item in claimed)
            if needs_review:
                remaining = 0
            if needs_review or unknown_components:
                remaining_base = remaining_tip = 0
            result.append({
                "operation_id": source.id, "payment_method_id": source.payment_method_id.id,
                "payment_method_name": source.payment_method_id.name,
                "original_order_id": source.revolut_order_id,
                "original_payment_id": source.revolut_payment_id,
                "amount_minor": source._revolut_paid_minor(), "remaining_minor": remaining,
                "external_refund_review_required": needs_review,
                "external_refund_review_note": source.external_refund_review_note,
                "base_amount_minor": base, "tip_amount_minor": tip,
                "remaining_base_minor": remaining_base, "remaining_tip_minor": remaining_tip,
                "terminal_tip_evidence": explicit,
                "return_base_minor": return_base, "return_tip_minor": return_tip,
                "return_total_minor": return_base + return_tip,
                "remaining_amount": remaining / (10 ** session.currency_id.decimal_places),
                "currency_id": session.currency_id.id,
            })
        return result

    def reserve(self, method, session, order_uuid, payment_line_uuid, normalized,
                minor, currency, financial_snapshot, original_operation_id,
                base_amount_minor=None, tip_amount_minor=None):
        """Authoritative claim in the caller's dedicated reservation transaction."""
        return_order = self.env["pos.order"].sudo().search([
            ("company_id", "=", session.company_id.id), ("uuid", "=", order_uuid),
        ], limit=1).with_env(self.env)
        session.config_id._check_revolut_register_access(session=session, order=return_order)
        # Closure takes the session lock before examining its order claims.
        # Recheck here: the outer RPC's session check may already be stale.
        self.env.cr.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [session.id])
        session.invalidate_recordset()
        if session.state != "opened":
            raise UserError(_("The Point of Sale session is not open."))
        prior_refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", session.company_id.id), ("order_uuid", "=", order_uuid),
        ])
        for refund in prior_refunds.with_env(self.env):
            refund._check_revolut_register_access()
            if refund.pos_session_id.config_id != session.config_id:
                raise AccessError(_("The refund belongs to another Point of Sale register."))
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
        if return_total_minor <= 0:
            raise UserError(_("The Revolut allocation exceeds the return total."))
        if original_operation_id:
            try:
                original_operation_id = int(original_operation_id)
            except (ValueError, TypeError):
                raise UserError(_("Select a valid original Revolut payment.")) from None
        original = self._return_original(snapshot, session)
        submitted_total_minor = return_total_minor

        refunds = self.env["pos.revolut.refund.operation"].sudo()
        charges = self.env["pos.revolut.payment.operation"].sudo()
        charges._lock_order(method.company_id.id, order_uuid)
        if charges.search_count([
            ("company_id", "=", method.company_id.id), ("order_uuid", "=", order_uuid),
        ]):
            raise UserError(_("A Revolut charge already exists for this return. Reconcile it first."))
        existing = refunds.search([
            ("company_id", "=", method.company_id.id), ("order_uuid", "=", order_uuid),
            ("payment_line_uuid", "=", payment_line_uuid),
        ], limit=1)
        if existing:
            existing.with_env(self.env)._check_revolut_register_access()
            self._check_total(snapshot, original, currency, submitted_total_minor,
                              order_uuid, frozen_total=existing.return_total_minor)
            if (existing.payment_method_id.id != method.id
                    or existing.amount_minor != minor or existing.currency_id.id != currency.id
                    or existing.pos_session_id.id != session.id or existing.financial_snapshot != snapshot
                    or (original_operation_id and existing.original_operation_id.id != original_operation_id)
                    or (base_amount_minor is not None and base_amount_minor != self._refund_components(existing)[0])
                    or (tip_amount_minor is not None and tip_amount_minor != self._refund_components(existing)[1])):
                raise UserError(_("The existing refund has different return details."))
            return ReservationClaim(existing.id, existing_status=existing._snapshot())

        # Native order, line and payment mutations take this same UUID lock.
        # Read saved evidence only after locking; existing attempts above remain
        # recoverable even when their pre-upgrade browser draft was lost.
        return_order = self.env["pos.order"].sudo().search([
            ("company_id", "=", session.company_id.id), ("uuid", "=", order_uuid),
        ], limit=1).with_env(self.env)
        if not return_order:
            raise UserError(_("Save the return in the POS before starting its Revolut refund."))

        return_order.check_access("read")
        session.config_id._check_revolut_register_access(session=session, order=return_order)
        if (return_order.state != "draft" or return_order.session_id != session
                or return_order.config_id != session.config_id
                or return_order.company_id != session.company_id or return_order.currency_id != currency
                or self._normalize_return(return_order._revolut_order_values(), native_order=True) != snapshot):
            raise UserError(_("The saved return changed. Reopen it in the POS and save it before refunding."))
        normalize = charges.normalize_amount
        saved_total = normalize(currency, return_order.amount_total)[1]
        if saved_total >= 0:
            raise UserError(_("The saved return must have a negative total. Correct and save it before refunding."))
        payment = return_order.payment_ids.filtered(lambda item: item.uuid == payment_line_uuid)
        if (len(payment) != 1 or payment.payment_method_id != method
                or payment.company_id != session.company_id or payment.session_id != session
                or normalize(currency, payment.amount)[1] != -minor
                or payment.payment_status in {"done", "reversed"}
                or payment.transaction_id or payment.revolut_operation_id or payment.revolut_refund_operation_id
                or payment.revolut_order_id or payment.revolut_payment_intent_id or payment.payment_ref_no):
            raise UserError(_("The saved return payment does not match this refund. Save the selected payment line before refunding."))

        source = self._validate_original(snapshot, method, session, minor, original_operation_id)
        self._lock_original_return(snapshot, original, order_uuid)
        return_allocation = self._return_allocation(snapshot, original, currency, order_uuid)
        return_total_minor = sum(row["base_minor"] + row["tip_minor"] for row in return_allocation)
        self._check_total(snapshot, original, currency, submitted_total_minor, order_uuid)
        self._check_total(snapshot, original, currency, -saved_total, order_uuid)
        if minor > return_total_minor:
            raise UserError(_("The Revolut allocation exceeds the return total. Reload its current allocation before refunding."))
        # Lock the selected source after the original sale, in the same order
        # for every contender. It serializes refundable balance decisions.
        self.env.cr.execute(
            "UPDATE pos_revolut_payment_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s",
            [source.id],
        )
        source_refunds = refunds.search([
            ("original_operation_id", "=", source.id), ("state", "!=", "failed"),
        ])
        if source.external_refund_review_required:
            raise UserError(_("External refund evidence needs manager investigation before another refund."))
        reserved = sum(source_refunds.mapped("amount_minor"))
        verified_before_claim = sum(source_refunds.filtered(
            lambda item: item.state == "verified"
        ).mapped("amount_minor"))
        base_minor, tip_minor, explicit = self._allocation(
            source, minor, base_amount_minor, tip_amount_minor, reserved,
        )
        source_base, source_tip, _evidence = self._source_components(source)
        if source_tip and any(item.origin == "external" for item in source_refunds):
            raise UserError(_("An external refund has no verified base and terminal tip allocation. Reconcile its components separately before another refund."))
        claimed = [self._refund_components(item) for item in source_refunds]
        if (sum(item[0] for item in claimed) + base_minor > source_base
                or sum(item[1] for item in claimed) + tip_minor > source_tip):
            raise UserError(_("The original payment has insufficient refundable base or terminal tip balance."))
        if reserved + minor > source._revolut_paid_minor():
            raise UserError(_("The original Revolut payment has insufficient refundable balance."))
        return_refunds = refunds.search([
            ("company_id", "=", method.company_id.id), ("order_uuid", "=", order_uuid),
        ])
        if any(item.financial_snapshot != snapshot
               or (item.pos_session_id != session and (
                   item.state != "verified"
                   or item.pos_session_id.state != "closed"
                   or session.state != "opened"
                   or item.pos_session_id.config_id != session.config_id
               ))
               or (item.state != "failed" and item.return_total_minor not in (0, return_total_minor))
               or (item.state != "failed" and item.return_allocation
                   and item.return_allocation != return_allocation) for item in return_refunds):
            raise UserError(_("The return changed after a refund allocation was reserved."))
        return_base, return_tip = self._return_components(snapshot, original, currency, order_uuid)
        return_allocations = [self._refund_components(item) for item in return_refunds if item.state != "failed"]
        if (sum(item[0] for item in return_allocations) + base_minor > return_base
                or sum(item[1] for item in return_allocations) + tip_minor > return_tip):
            raise UserError(_("Refund base and terminal tip allocations exceed the original return lines."))
        if sum(item.amount_minor for item in return_refunds if item.state != "failed") + minor > return_total_minor:
            raise UserError(_("Revolut allocations exceed the return total."))
        if self.env["pos.order"].sudo().search_count([
            ("uuid", "=", order_uuid), ("state", "!=", "draft"),
        ]):
            raise UserError(_("This return has already been completed."))
        return_order._revolut_freeze_return_allocation(return_allocation)
        refund = refunds.create({
            "original_operation_id": source.id, "pos_session_id": session.id,
            "order_uuid": order_uuid, "payment_line_uuid": payment_line_uuid,
            "amount": float(normalized), "amount_minor": minor,
            "allocation_explicit": explicit,
            "base_amount_minor": base_minor if explicit else 0,
            "tip_amount_minor": tip_minor if explicit else 0,
            "return_total_minor": return_total_minor, "return_allocation": return_allocation,
            "currency_id": currency.id, "financial_snapshot": snapshot,
        })
        return ReservationClaim(
            refund.id, source_amount_minor=source._revolut_paid_minor(),
            source_base_minor=source_base if explicit else None,
            source_tip_minor=source_tip if explicit else None,
            verified_before_claim=verified_before_claim,
        )

    def _has_revolut_original(self, original_ids):
        originals = self.env["pos.order.line"].sudo().browse(original_ids).exists()
        return any(
            payment.payment_method_id.use_payment_terminal == "revolut" or payment.revolut_operation_id
            for payment in originals.order_id.payment_ids
        )

    def _discover_revolut_return(self, order, existing_order):
        # Unknown cash carts still require native relationship classification.
        # Bound each metadata batch and ID lookup without imposing financial
        # snapshot limits on unrelated cash sales/returns. No decimal is parsed.
        lines = order.get("lines", [])
        if not isinstance(lines, list):
            check_line_count(lines)
        for start in range(0, len(lines), MAX_LINES):
            batch = lines[start:start + MAX_LINES]
            check_line_count(batch)
            original_ids = []
            for raw in batch:
                line = raw[2] if isinstance(raw, (tuple, list)) and len(raw) > 2 else raw
                if isinstance(line, dict) and line.get("refunded_orderline_id"):
                    original_ids.append(snapshot_id(line["refunded_orderline_id"]))
            if original_ids and self._has_revolut_original(original_ids):
                check_line_count(lines)
                return True
        if existing_order:
            for start in range(0, len(existing_order.lines), MAX_LINES):
                original_ids = existing_order.lines[start:start + MAX_LINES].refunded_orderline_id.ids
                if original_ids and self._has_revolut_original(original_ids):
                    check_line_count(lines)
                    check_line_count_size(len(existing_order.lines))
                    return True
        return False

    def preflight_order_lines(self, order):
        """Guard oversized financial carts before native POS return discovery."""
        lines = order.get("lines", [])
        if not isinstance(lines, list):
            check_line_count(lines)
        if len(lines) <= MAX_LINES:
            return
        domain = [("company_id", "in", self.env.companies.ids), ("order_uuid", "=", order.get("uuid"))]
        if any(self.env[model].sudo().search_count(domain) for model in (
            "pos.revolut.payment.operation", "pos.revolut.refund.operation",
        )):
            check_line_count(lines)
        for command in order.get("payment_ids", []):
            if len(command) >= 3 and isinstance(command[2], dict):
                method_id = command[2].get("payment_method_id")
                if method_id and self.env["pos.payment.method"].browse(method_id).use_payment_terminal == "revolut":
                    check_line_count(lines)
        self._discover_revolut_return(order, None)

    def validate_settlement(self, order, existing_order, payments):
        session = self.env["pos.session"].browse(order["session_id"]).exists()
        if not session:
            raise UserError(_("The Point of Sale session does not exist."))
        order_uuid = order.get("uuid") or (existing_order and existing_order.uuid)
        charges = self.env["pos.revolut.payment.operation"].sudo()
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", session.company_id.id), ("order_uuid", "=", order_uuid),
        ])
        revolut_tender = any(
            self.env["pos.payment.method"].browse(value.get("payment_method_id")).use_payment_terminal == "revolut"
            for value in payments.values()
        )
        if refunds or revolut_tender or charges.search_count([
            ("company_id", "=", session.company_id.id), ("order_uuid", "=", order_uuid),
        ]):
            check_line_count(order.get("lines", []))
        # A return may omit its refund flag or use cash: neither can exempt a
        # relationship to an original Revolut sale from allocation checks.
        source_revolut = self._discover_revolut_return(order, existing_order)
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
        session.config_id._check_revolut_register_access(session=session, order=existing_order)
        for refund in refunds.with_env(self.env):
            refund._check_revolut_register_access()
        charges._lock_order(session.company_id.id, order_uuid)
        check_line_count(order.get("lines", []))
        if order.get("state") in {"draft", "cancel"} and not refunds and not any(
            payment.get("payment_status") == "done"
            and self.env["pos.payment.method"].browse(payment.get("payment_method_id")).use_payment_terminal == "revolut"
            for payment in payments.values()
        ):
            # Backend refund() prepares lines and recomputes totals in separate
            # calls. An unclaimed draft or cancellation is not a settlement. Claims
            # and finalization still require the full allocation checks below.
            return refunds.browse()
        if refunds:
            self.env.cr.execute("SELECT id FROM pos_revolut_refund_operation WHERE id = ANY(%s) ORDER BY id FOR UPDATE", [refunds.ids])
            refunds.invalidate_recordset()
        snapshot = self._normalize_return(order, native_order=True)
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        total_minor = normalize(session.currency_id, order.get("amount_total"))[1]
        if total_minor >= 0:
            raise UserError(_("A Revolut-linked return must have a negative total."))
        original = self._return_original(snapshot, session)
        # Cash-only returns of a mixed-tender sale use the same original-sale lock.
        self._lock_original_return(snapshot, original, order_uuid)
        self._check_total(snapshot, original, session.currency_id, -total_minor, order_uuid)
        total_minor = -self._return_total_minor(snapshot, original, session.currency_id, order_uuid)
        active = refunds.filtered(lambda item: item.state != "failed")
        verified = refunds.browse()
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            payment = payments.get(refund.payment_line_uuid)
            if refund.state == "failed":
                if payment and payment.get("payment_status") == "done":
                    raise UserError(_("A failed Revolut refund cannot complete a return payment."))
                continue
            # A verified refund can outlive its closed POS session. Keep its
            # original allocation fixed while allowing the same register to finish.
            if (not payment or snapshot != refund.financial_snapshot
                    or refund.original_order_id != original
                    or (refund.pos_session_id != session and (
                        refund.state != "verified"
                        or refund.pos_session_id.state != "closed"
                        or session.state != "opened"
                        or refund.pos_session_id.config_id != session.config_id
                    ))
                    or refund.currency_id != session.currency_id
                    or (refund.return_total_minor and refund.return_total_minor != -total_minor)
                    or (refund.return_allocation and refund.return_allocation != self._return_allocation(
                        snapshot, original, session.currency_id, order_uuid))
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
        return_base, return_tip = self._return_components(snapshot, original, session.currency_id, order_uuid)
        components = [self._refund_components(item) for item in active]
        base_allocated = sum(item[0] for item in components)
        tip_allocated = sum(item[1] for item in components)
        if base_allocated > return_base or tip_allocated > return_tip:
            raise UserError(_("Refund base and terminal tip allocations exceed the original return lines."))
        if order.get("state") != "draft" and tip_allocated != return_tip:
            raise UserError(_("Return every terminal tip through its explicit original Revolut allocation."))
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
        # A later method reconfiguration cannot turn a provider-backed payment
        # into an original manual tender balance.
        original_nonrevolut = {}
        for original_payment in original.payment_ids.sudo().filtered(
            lambda item: not item.revolut_operation_id
            and item.payment_method_id.use_payment_terminal != "revolut"
        ):
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

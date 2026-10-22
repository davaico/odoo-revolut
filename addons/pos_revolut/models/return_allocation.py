"""Return invariants shared by source discovery, reservation, and checkout."""

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

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
    pending_refunds_before_claim: tuple = ()
    source_base_minor: int | None = None
    source_tip_minor: int | None = None


@dataclass(frozen=True)
class ReturnDecision:
    allocation: list

    @property
    def base_minor(self):
        return sum(row["base_minor"] for row in self.allocation)

    @property
    def tip_minor(self):
        return sum(row["tip_minor"] for row in self.allocation)

    @property
    def total_minor(self):
        return self.base_minor + self.tip_minor


@dataclass(frozen=True)
class RefundCapacity:
    gross_minor: int
    base_minor: int
    tip_minor: int
    reserved_minor: int
    reserved_base_minor: int
    reserved_tip_minor: int

    def check(self, gross=0, base=0, tip=0, *, component_error, gross_error):
        if (self.reserved_base_minor + base > self.base_minor
                or self.reserved_tip_minor + tip > self.tip_minor):
            raise UserError(component_error)
        if self.reserved_minor + gross > self.gross_minor:
            raise UserError(gross_error)


@dataclass(frozen=True)
class RecoveryContents:
    existing_order: object
    original: object
    snapshot: dict
    decision: ReturnDecision
    refunds: object


class RecoveryEvidence:
    """Checked contents usable only inside this recovery transaction/scope."""

    def __init__(self, env, contents):
        self._cursor = env.cr
        self._contents = contents
        self._valid = True
        env.cr.postcommit.add(self._expire)
        env.cr.postrollback.add(self._expire)

    def _expire(self):
        self._valid = False

    def read(self, env):
        if not self._valid or env.cr is not self._cursor or self._cursor.closed:
            raise UserError(_("Reload the return recovery evidence in its current transaction."))
        return self._contents


class ReturnAllocation:
    def __init__(self, env):
        self.env = env

    def acquire_many(self, sessions, identities, originals, refunds=None, sources=None):
        """Acquire authoritative evidence in one deterministic transaction order.

        Pointer reads select locks only. Callers validate freshly invalidated
        records afterward; no returned evidence survives the caller transaction.
        Row updates force repeatable-read contenders to retry on changed evidence.
        """
        sessions.flush_recordset()
        for session in sessions.sorted("id"):
            self.env.cr.execute("UPDATE pos_session SET write_date = write_date WHERE id = %s", [session.id])
        charges = self.env["pos.revolut.payment.operation"].sudo()
        for company_id, identity in sorted(set(identities)):
            if identity:
                charges._lock_order(company_id, identity)
        originals.flush_recordset()
        for original in originals.sorted("id"):
            self.env.cr.execute("UPDATE pos_order SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [original.id])
        selected = charges.search([("pos_order_id", "in", originals.ids)], order="id")
        for company_id, identity in sorted(set(identities)):
            if identity:
                selected |= charges.search([("company_id", "=", company_id), ("order_uuid", "=", identity)])
        sources = (selected | sources.sudo() if sources is not None else selected).sorted("id")
        sources.flush_recordset()
        for source in sources:
            self.env.cr.execute("UPDATE pos_revolut_payment_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [source.id])
        records = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "in", sources.ids)], order="id")
        if refunds is not None:
            records |= refunds.sudo()
        records.flush_recordset()
        if records:
            self.env.cr.execute("SELECT id FROM pos_revolut_refund_operation WHERE id = ANY(%s) ORDER BY id FOR UPDATE", [records.ids])
        # Refresh participating relations and financial evidence, retaining
        # unrelated native caches (including accounting's privileged projection).
        sessions.invalidate_recordset()
        originals.invalidate_recordset()
        originals.lines.invalidate_recordset()
        originals.payment_ids.invalidate_recordset()
        sources.invalidate_recordset()
        records.invalidate_recordset()

    def acquire(self, session, company_id, order_uuid, original, *, refunds=None):
        self.acquire_many(session, [(company_id, order_uuid)], original, refunds)

    def associate(self, refunds, bindings, *, return_order_id=None, selection=None,
                  session_id=None, exact_payments=False):
        """Validate a complete already-issued batch and persist exact native links.

        Native product construction stays in the Odoo adapter. The caller owns
        the savepoint, mutation scope and final action; this operation never
        dispatches a reimbursement or commits its transaction.
        """
        from uuid import uuid4
        from odoo import fields

        if (not refunds or len(refunds) > 100 or not isinstance(bindings, list)
                or len(bindings) != len(refunds) or not all(isinstance(row, dict) for row in bindings)
                or any(type(row.get("refund_id")) is not int for row in bindings)
                or {row["refund_id"] for row in bindings} != set(refunds.ids)):
            raise UserError(_("Select each external refund and its exact native reimbursement payment once."))
        payment_ids = [row.get("payment_id") for row in bindings if row.get("payment_id") is not None]
        if (any(type(identity) is not int for identity in payment_ids)
                or len(payment_ids) != len(set(payment_ids))
                or exact_payments and len(payment_ids) != len(bindings)):
            raise UserError(_("Select each external refund and its exact native reimbursement payment once."))
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            refund._check_revolut_register_access()
        originals = refunds.original_order_id
        if len(originals) != 1 or any(refund.origin != "external" for refund in refunds):
            raise UserError(_("Select external refunds matched to one original sale."))
        original = originals
        orders = refunds.pos_order_id
        if len(orders) > 1 or orders and return_order_id and orders.id != return_order_id:
            raise UserError(_("This refund already belongs to another native return."))
        order = orders or self.env["pos.order"].browse(return_order_id).exists()
        if return_order_id and not order:
            raise UserError(_("Select an existing native return."))
        session = (order.session_id if order else self.env["pos.session"].browse(session_id).exists()
                   if session_id else original.config_id.current_session_id)
        if not session:
            raise UserError(_("Open the original register before preparing a native return."))
        identity = order.uuid if order else str(uuid4())
        self.acquire(session, original.company_id.id, identity, original | order, refunds=refunds)
        # None of the pointer discovery above is monetary or state authority.
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            refund._check_revolut_register_access()
            if (refund.origin != "external" or refund.original_order_id != original
                    or refund.state == "failed" or refund.native_reconciliation_status == "financial_only"
                    or refund.financial_correction_move_id):
                raise UserError(_("This refund cannot be allocated to a product return."))
        if (order and order.session_id != session or not order and session.state != "opened"
                or order and order.state == "draft" and session.state != "opened"):
            raise UserError(_("Open the original register before preparing a native return."))
        session.config_id._check_revolut_register_access(session=session, order=order)
        if order:
            order.check_access("write" if order.state == "draft" else "read")
            if order.state not in {"draft", "paid", "done", "invoiced"}:
                raise UserError(_("Select a draft or completed native return."))
            if selection is not None:
                try:
                    selected = {row["original_line_id"]: Decimal(str(row["quantity"])) for row in selection}
                except (KeyError, TypeError, ArithmeticError):
                    raise UserError(_("Resume the existing return without changing confirmed products or quantities.")) from None
                saved = {line.refunded_orderline_id.id: abs(Decimal(str(line.qty))) for line in order.lines}
                if len(selected) != len(selection) or selected != saved:
                    raise UserError(_("Resume the existing return without changing confirmed products or quantities."))
        else:
            order = refunds[0]._prepare_native_products(selection, session, identity)
        snapshot = self._normalize_return(order._revolut_order_values(), native_order=True)
        if self._return_original(snapshot, session) != original:
            raise UserError(_("The native return belongs to a different original sale."))
        self._validate_return_quantities(snapshot, original, order.uuid)
        for line in order.lines:
            refunds[0]._check_selected_lots(line.refunded_orderline_id, abs(Decimal(str(line.qty))),
                                           line.pack_lot_ids.mapped("lot_name"), order)
        decision = self._decision(snapshot, original, order.currency_id, order.uuid)
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        sources = self._eligible_sources(original, session)
        by_id = {row["refund_id"]: row for row in bindings}
        prospective = []
        used_payments = set()
        lots = {str(line.refunded_orderline_id.id): sorted(line.pack_lot_ids.mapped("lot_name")) for line in order.lines}
        for refund in refunds.sorted("id"):
            row = by_id[refund.id]
            source = refund.original_operation_id
            if (source not in sources or source.payment_method_id != refund.payment_method_id
                    or refund.company_id != session.company_id or refund.currency_id != session.currency_id
                    or normalize(refund.currency_id, refund.amount)[1] != refund.amount_minor):
                raise UserError(_("The refund allocation does not match an eligible original Revolut payment."))
            base, tip = row.get("base_amount_minor"), row.get("tip_amount_minor")
            if refund.pos_order_id:
                if (refund.pos_order_id != order or row.get("payment_id") not in (None, refund.pos_payment_id.id)
                        or base is not None and base != refund.base_amount_minor
                        or tip is not None and tip != refund.tip_amount_minor
                        or refund.financial_snapshot != snapshot or refund.return_allocation != decision.allocation
                        or refund.return_total_minor != decision.total_minor or refund.native_lot_snapshot != lots):
                    raise UserError(_("The confirmed native return, payment or monetary allocation cannot change."))
                base, tip = refund.base_amount_minor, refund.tip_amount_minor
            source_base, source_tip, _explicit = self._source_components(source)
            if not source_tip and base is None and tip is None:
                base, tip = refund.amount_minor, 0
            base, tip, _explicit = self._allocation(source, refund.amount_minor, base, tip, refund.amount_minor)
            payment = (refund.pos_payment_id or order.payment_ids.filtered(lambda item: item.id == row.get("payment_id")))
            if row.get("payment_id") and not payment:
                raise UserError(_("Select a payment on this native return."))
            if not payment and order.state != "draft":
                raise UserError(_("A completed return requires its exact existing Revolut reimbursement payment."))
            if not payment and order.payment_ids.filtered(lambda item: item.payment_method_id == refund.payment_method_id
                                                         and not item.revolut_refund_operation_id):
                raise UserError(_("Select the existing card reimbursement explicitly; do not duplicate its payment line."))
            if payment:
                if payment.id in used_payments or not self._native_payment_matches(payment, refund, order):
                    raise UserError(_("The native payment is unrelated, ambiguous, or already used by another refund."))
                used_payments.add(payment.id)
            prospective.append((refund, payment, base, tip))
        # Imported money already protects source capacity. Replace only the
        # selected batch's unknown components, never add its gross amount twice.
        for source in refunds.original_operation_id:
            _capacity, claimed, _explicit = self._source_capacity(source)
            outside = claimed - refunds
            source_base, source_tip, _explicit = self._source_components(source)
            if source_tip and any(item.origin == "external" and not item.allocation_explicit for item in outside):
                raise UserError(_("Confirm the unknown external refund components before allocating another native return."))
            selected = [item for item in prospective if item[0].original_operation_id == source]
            self._capacity(source._revolut_paid_minor(), source_base, source_tip, outside).check(
                sum(item[0].amount_minor for item in selected), sum(item[2] for item in selected), sum(item[3] for item in selected),
                component_error=_("Confirmed refunds exceed the original base or terminal tip capacity."),
                gross_error=_("Existing financial refunds exceed the original card payment; reconcile their evidence first."))
        peers = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", order.company_id.id), ("order_uuid", "=", order.uuid), ("state", "!=", "failed")]) - refunds.sudo()
        if not self._native_peers_match(peers, snapshot, decision):
            raise UserError(_("The return changed after a refund allocation was reserved."))
        self._capacity(decision.total_minor, decision.base_minor, decision.tip_minor, peers).check(
            sum(item[0].amount_minor for item in prospective), sum(item[2] for item in prospective), sum(item[3] for item in prospective),
            component_error=_("External refund allocations exceed the selected native return."),
            gross_error=_("External refund allocations exceed the selected native return."))
        if order.state != "draft" and normalize(order.currency_id, order.amount_total)[1] != -decision.total_minor:
            raise UserError(_("The completed native return has incompatible monetary evidence."))
        # Every member passed before any binding. The caller savepoint also
        # rolls back newly constructed native records on a rejected member.
        for refund, payment, base, tip in prospective:
            if refund.pos_order_id:
                continue
            if not payment:
                payment = self.env["pos.payment"].create({"pos_order_id": order.id, "uuid": str(uuid4()),
                    "payment_method_id": refund.payment_method_id.id, "amount": -refund.amount,
                    "payment_status": "waiting", "name": fields.Datetime.now()})
            refund._write_native_completion({"order_uuid": order.uuid, "payment_line_uuid": payment.uuid,
                "pos_order_id": order.id, "pos_payment_id": payment.id, "financial_snapshot": snapshot,
                "return_allocation": decision.allocation, "return_total_minor": decision.total_minor,
                "allocation_explicit": True, "base_amount_minor": base, "tip_amount_minor": tip,
                "native_reconciliation_status": "native_draft", "native_lot_snapshot": lots})
        if order.state == "draft":
            order._revolut_freeze_return_allocation(decision.allocation)
        for refund in refunds:
            refund._resume_native_payment()
        order._check_revolut_order()
        if order.state != "draft":
            for refund in refunds:
                refund._complete_native_return()
        return order

    def _native_payment_matches(self, payment, refund, order):
        """Shared read-only eligibility for the picker and locked association."""
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        return (payment.pos_order_id == order and payment.payment_method_id == refund.payment_method_id
                and normalize(refund.currency_id, payment.amount)[1] == -refund.amount_minor
                and payment.revolut_refund_operation_id in (refund.browse(), refund)
                and not payment.revolut_operation_id
                and payment.transaction_id in (False, refund.revolut_order_id)
                and payment.payment_ref_no in (False, refund.revolut_order_id)
                and (order.state == "draft" or refund.state == "verified"
                     and payment.transaction_id == refund.revolut_order_id))

    def _native_peers_match(self, peers, snapshot, decision):
        return all(peer.financial_snapshot == snapshot
                   and (not peer.return_allocation or peer.return_allocation == decision.allocation)
                   and peer.return_total_minor in (0, decision.total_minor) for peer in peers)

    def _normalize_return(self, data, *, native_order=False):
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(
            data, native_order=native_order
        )
        try:
            for line in snapshot["lines"]:
                if not line["refunded_orderline_id"] or not Decimal(line["qty"]):
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
            if (Decimal(line["qty"]) * Decimal(str(old.qty)) >= 0
                    or abs(Decimal(line["qty"])) > abs(Decimal(str(old.qty)))
                    or line["product_id"] != old.product_id.id
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
        requested = {line["refunded_orderline_id"]: abs(Decimal(line["qty"])) for line in snapshot["lines"]}
        used = {line.id: Decimal(0) for line in original.lines}
        completed = self.env["pos.order.line"].sudo().search([
            ("refunded_orderline_id", "in", original.lines.ids),
            ("order_id.state", "in", ["paid", "done", "invoiced"]),
        ])
        for line in completed:
            if line.order_id.uuid != order_uuid:
                used[line.refunded_orderline_id.id] += abs(Decimal(str(line.qty)))
        reservations = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id.pos_order_id", "=", original.id),
            ("order_uuid", "!=", False),
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
                    used[old_id] += abs(Decimal(line["qty"]))
        if any(used.get(line.id, 0) + requested.get(line.id, 0) > abs(Decimal(str(line.qty))) for line in original.lines):
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
        else:
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

    def _source_components(self, source):
        """Historical amounts stay base-only; new amounts need verified evidence."""
        if not source.authorization_id:
            return source.amount_minor, 0, False
        gross = source._revolut_paid_minor()
        if (not source.terminal_tip_evidence or source.terminal_tip_minor < 0 or gross <= 0
                or gross != source.amount_minor + source.terminal_tip_minor):
            raise UserError(_("The original payment's base and terminal tip evidence are inconsistent."))
        return source.amount_minor, source.terminal_tip_minor, True

    def _original_line_entitlements(self, original, currency, *, legacy=False):
        # Preserve healthy existing ceilings. If independent rounding creates
        # negative capacity, distribute the collected base over positive goods
        # by cumulative rounding. Negative adjustments keep their native lines
        # but have no separate monetary entitlement; their discount is shared
        # proportionally by goods. Terminal tips remain a separate component.
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        sources = self._eligible_sources(original, original.session_id)
        authorities = sources.filtered(lambda item: item.authorization_id).authorization_id
        if not authorities:
            # Exact recorded totals can prove a historical base ceiling, but
            # cannot classify a currently configured terminal tip product.
            entitlements = {line.id: (normalize(currency, line.price_subtotal_incl)[1], 0)
                            for line in original.lines}
            if sum(base for base, _tip in entitlements.values()) != normalize(currency, original.amount_total)[1]:
                raise UserError(_("The historical sale has no trustworthy per-line rounding basis. Reconcile it before another return."))
            if not legacy and any(base < 0 for base, _tip in entitlements.values()):
                weights = {line.id: max(0, entitlements[line.id][0]) for line in original.lines.sorted("uuid")}
                allocated = self._distribute_minor(normalize(currency, original.amount_total)[1], weights)
                entitlements = {identity: (base, 0) for identity, base in allocated.items()}
            return entitlements
        tip_products = authorities.tip_product_id
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        original_base = original.lines.filtered(lambda line: line.product_id not in tip_products).sorted("uuid")
        allocation = {line.id: normalize(currency, line.price_subtotal_incl)[1] for line in original_base}
        if len(authorities) != 1:
            raise UserError(_("The original sale has inconsistent frozen cart authority."))
        authority = authorities
        raw_base = sum(allocation.values())
        raw_amounts = {line.id: Decimal(str(line.price_subtotal_incl)) for line in original_base}
        if raw_base <= 0:
            # A whole-cart authorization can collect sub-minor-priced goods
            # even when recorded line subtotals cancel or round to zero. Native
            # unrounded gross amounts supply weights only while their original
            # tax/fiscal inputs remain unchanged since the frozen authority.
            taxes = original_base.tax_ids | original_base.tax_ids_after_fiscal_position
            references = (list(taxes | taxes.flatten_taxes_hierarchy())
                          + list(original.fiscal_position_id) + list(original.fiscal_position_id.tax_ids))
            if any(record.write_date and record.write_date > authority.create_date for record in references):
                raise UserError(_("The original sale has no trustworthy unrounded tax basis. Reconcile its history before another return."))
            base_lines = original_base._prepare_tax_base_line_values()
            self.env["account.tax"]._add_tax_details_in_base_lines(base_lines, original.company_id)
            raw_amounts = {base["record"].id: Decimal(str(base["tax_details"]["raw_total_included_currency"]))
                           for base in base_lines}
        if sum(raw_amounts.values()) <= 0 or authority.payable_minor <= 0:
            raise UserError(_("The original base line allocations are invalid."))
        if raw_base > 0 and authority.payable_minor != raw_base:
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
        if raw_base <= 0 or not legacy and (any(minor < 0 for minor in allocation.values())
                                          or any(amount < 0 for amount in raw_amounts.values())):
            # Product precision can exceed currency precision: individually
            # rounded zero-cent lines still have positive relative weights.
            weights = {identity: max(Decimal(0), amount) for identity, amount in raw_amounts.items()}
            allocation = self._distribute_minor(authority.payable_minor, weights)
        return {line.id: ((0, normalize(currency, line.price_subtotal_incl)[1])
                          if line.product_id in tip_products else (allocation[line.id], 0))
                for line in original.lines}

    def _distribute_minor(self, total, weights):
        """Conserve integer money without rounding a last line below zero."""
        denominator = sum(weights.values())
        if total < 0 or denominator <= 0:
            raise UserError(_("The original base line allocations are invalid."))
        cumulative = Decimal(0)
        allocated = 0
        result = {}
        for identity, weight in weights.items():
            cumulative += weight
            target = int((Decimal(total) * cumulative / denominator).quantize(
                Decimal(1), rounding=ROUND_HALF_UP))
            result[identity] = target - allocated
            allocated = target
        return result

    def _historical_return_allocation(self, snapshot, target, entitlements):
        # A whole-return amount only proves its line allocation when one original
        # line was returned. Do not invent a product split for older documents.
        if len(snapshot["lines"]) != 1 or type(target) is not int or target < 0:
            raise UserError(_("An earlier return has no trustworthy per-line monetary allocation. Reconcile its history before another return."))
        line = snapshot["lines"][0]
        old_id = line["refunded_orderline_id"]
        base, tip = entitlements[old_id]
        return [{"original_line_id": old_id, "quantity": str(abs(Decimal(line["qty"]))),
                 "base_minor": target if not tip else 0,
                 "tip_minor": target if tip else 0}]

    def _validate_line_allocation(self, allocation, snapshot, entitlements):
        requested = {line["refunded_orderline_id"]: abs(Decimal(line["qty"]))
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
        legacy = self._original_line_entitlements(original, currency, legacy=True)
        historical_limits = {identity: (max(base, legacy[identity][0]), tip)
                             for identity, (base, tip) in entitlements.items()}
        completed = self.env["pos.order"].sudo().search([
            ("lines.refunded_orderline_id", "in", original.lines.ids),
            ("state", "in", ["paid", "done", "invoiced"]),
        ])
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        completed_by_uuid = {order.uuid: order for order in completed}
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id.pos_order_id", "=", original.id),
            ("order_uuid", "!=", False), ("state", "!=", "failed"),
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
            self._validate_line_allocation(allocation, prior, historical_limits)
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
            self._validate_line_allocation(allocation, prior, historical_limits)
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
        if (sum(used_base.values()) > sum(base for base, _tip in entitlements.values())
                or any(used_tip[identity] > tip for identity, (_base, tip) in entitlements.items())
                or any(used_qty[identity] > abs(Decimal(str(by_id[identity].qty))) for identity in entitlements)):
            raise UserError(_("Earlier returns exceed the original monetary or quantity entitlement. Reconcile their evidence first."))
        if any(used_base[identity] > base or
               used_qty[identity] == abs(Decimal(str(by_id[identity].qty))) and used_base[identity] != base
               for identity, (base, _tip) in entitlements.items()):
            remaining = sum(base for base, _tip in entitlements.values()) - sum(used_base.values())
            weights = {identity: max(0, base - used_base[identity])
                       for identity, (base, _tip) in entitlements.items()
                       if used_qty[identity] < abs(Decimal(str(by_id[identity].qty)))}
            if remaining and not sum(weights.values()):
                raise UserError(_("Earlier returns leave no trustworthy remaining product allocation. Reconcile their evidence first."))
            residual = (self._distribute_minor(remaining, weights) if sum(weights.values())
                        else dict.fromkeys(weights, 0))
            entitlements = {identity: (used_base[identity] + residual.get(identity, 0), tip)
                            for identity, (_base, tip) in entitlements.items()}
        result = []
        for line in snapshot["lines"]:
            old_id = line["refunded_orderline_id"]
            quantity = abs(Decimal(line["qty"]))
            remaining_qty = abs(Decimal(str(by_id[old_id].qty))) - used_qty[old_id]
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

    def _capacity(self, gross, base, tip, refunds):
        components = [self._refund_components(refund) for refund in refunds]
        return RefundCapacity(gross, base, tip, sum(refunds.mapped("amount_minor")),
                              sum(item[0] for item in components),
                              sum(item[1] for item in components))

    def _source_capacity(self, source):
        base, tip, explicit = self._source_components(source)
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("original_operation_id", "=", source.id), ("state", "!=", "failed"),
        ])
        return self._capacity(source._revolut_paid_minor(), base, tip, refunds), refunds, explicit

    def _decision(self, snapshot, original, currency, order_uuid):
        return ReturnDecision(self._return_allocation(snapshot, original, currency, order_uuid))

    def _native_return_sale(self, order):
        original = order.lines.refunded_orderline_id.order_id
        if not (len(original) == 1 and order._revolut_return_source() and order.lines
                and all(line.refunded_orderline_id and line.qty * line.refunded_orderline_id.qty < 0
                        for line in order.lines)):
            return None
        return original

    def display_target(self, order):
        """Advisory native total. Never locks, freezes or recomputes prices."""
        if order.revolut_return_allocation:
            return -ReturnDecision(order.revolut_return_allocation).total_minor
        original = self._native_return_sale(order)
        if not original:
            return None
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        if order.state in {"paid", "done", "invoiced"}:
            return normalize(order.currency_id, order.amount_total)[1]
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", order.company_id.id), ("order_uuid", "=", order.uuid),
            ("origin", "=", "odoo"), ("state", "!=", "failed"),
        ])
        targets = set(refunds.mapped("return_total_minor")) - {0}
        if len(targets) == 1:
            return -targets.pop()
        if len(targets) > 1:
            raise UserError(_("The refund allocations have inconsistent return targets."))
        if refunds:
            # Historical uncertain claims without a target retain their display.
            return normalize(order.currency_id, order.amount_total)[1]
        snapshot = self._normalize_return(order._revolut_order_values(), native_order=True)
        return -self._decision(snapshot, original, order.currency_id, order.uuid).total_minor

    def freeze_native_return(self, order):
        """Independently validate saved contents and freeze under the sale lock."""
        if not self._native_return_sale(order):
            return
        self.acquire(order.session_id, order.company_id.id, order.uuid,
                     order | order.lines.refunded_orderline_id.order_id)
        snapshot = self._normalize_return(order._revolut_order_values(), native_order=True)
        original = self._return_original(snapshot, order.session_id)
        self._validate_return_quantities(snapshot, original, order.uuid)
        decision = self._decision(snapshot, original, order.currency_id, order.uuid)
        total = -self.env["pos.revolut.payment.operation"].normalize_amount(order.currency_id, order.amount_total)[1]
        self._check_total(snapshot, original, order.currency_id, total, order.uuid,
                          frozen_total=decision.total_minor)
        order._revolut_freeze_return_allocation(decision.allocation)

    @contextmanager
    def recover(self, refund, session):
        """Check fresh siblings under shared locks; caller reconstructs native work."""
        refund.ensure_one()
        refund.payment_method_id._check_refund_authority()
        refund._check_revolut_register_access()
        if refund.origin != "odoo" or refund.state != "verified":
            raise UserError(_("Only a completed Odoo refund can recover its original return."))
        if not session:
            raise UserError(_("Open the original Point of Sale register before recovering this return."))
        session.config_id._check_revolut_register_access(session=session)
        if (session.config_id != refund.pos_session_id.config_id
                or session.company_id != refund.company_id or session.currency_id != refund.currency_id):
            raise AccessError(_("Recover the return in its original register, company and currency."))
        existing = self.env["pos.order"].sudo().search([
            ("company_id", "=", refund.company_id.id), ("uuid", "=", refund.order_uuid)], limit=1)
        self.acquire(session, refund.company_id.id, refund.order_uuid,
                     refund.original_order_id | existing, refunds=refund)
        if refund.origin != "odoo" or refund.state != "verified":
            raise UserError(_("Only a completed Odoo refund can recover its original return."))
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", refund.company_id.id), ("order_uuid", "=", refund.order_uuid),
            ("state", "!=", "failed"),
        ], order="id", limit=101)
        if len(refunds) > 100:
            raise UserError(_("Reconcile this return's allocations before recovery."))
        if refund.id not in refunds.ids:
            raise UserError(_("Reconcile every refund allocation before recovering this return."))
        for sibling in refunds.with_env(self.env):
            sibling.payment_method_id._check_refund_authority()
            sibling._check_revolut_register_access()
        if any(sibling.state != "verified" or not sibling.revolut_order_id
               or (sibling.origin == "external" and (
                   sibling.provider_state != "completed" or not sibling.verified_at)) for sibling in refunds):
            raise UserError(_("Reconcile every refund allocation before recovering this return."))
        existing = self.env["pos.order"].sudo().search([
            ("company_id", "=", refund.company_id.id), ("uuid", "=", refund.order_uuid),
        ], limit=1).with_env(self.env)
        if existing:
            existing.check_access("read")
            if existing.session_id != session:
                raise UserError(_("The return was recovered in another session. Reload its existing draft."))
        if session.state != "opened" and (not existing or existing.state == "draft"):
            raise UserError(_("Reopen the original return's session before continuing in POS."))
        snapshot = self._normalize_return(refund.financial_snapshot)
        if any(sibling.financial_snapshot != snapshot for sibling in refunds):
            raise UserError(_("The refund allocations have inconsistent return contents."))
        original = self._return_original(snapshot, session)
        sources = self._eligible_sources(original, session)
        if any(sibling.original_operation_id not in sources or sibling.original_order_id != original
               or sibling.currency_id != session.currency_id
               or sibling.pos_session_id.config_id != session.config_id
               or (sibling.pos_session_id != session and sibling.origin == "odoo"
                   and sibling.pos_session_id.state != "closed") for sibling in refunds):
            raise UserError(_("The refund allocations have inconsistent original sale or session evidence."))
        self._validate_return_quantities(snapshot, original, refund.order_uuid)
        decision = self._decision(snapshot, original, session.currency_id, refund.order_uuid)
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        if any((sibling.return_total_minor and sibling.return_total_minor != decision.total_minor)
               or (sibling.return_allocation and sibling.return_allocation != decision.allocation)
               or normalize(session.currency_id, sibling.amount)[1] != sibling.amount_minor
               for sibling in refunds):
            raise UserError(_("The refund allocations have inconsistent conserved monetary evidence."))
        self._capacity(decision.total_minor, decision.base_minor, decision.tip_minor, refunds).check(
            component_error=_("Refund base and terminal tip allocations exceed the original return lines."),
            gross_error=_("Revolut allocations exceed the return total."))
        for source in refunds.original_operation_id:
            capacity, _claimed, _explicit = self._source_capacity(source)
            capacity.check(component_error=_("The original payment has insufficient refundable base or terminal tip balance."),
                           gross_error=_("The original Revolut payment has insufficient refundable balance."))
        payments = self.env["pos.payment"].sudo().search([("uuid", "in", refunds.mapped("payment_line_uuid"))])
        if (len(set(refunds.mapped("payment_line_uuid"))) != len(refunds)
                or any(sibling.pos_order_id and sibling.pos_order_id != existing
                       or sibling.pos_payment_id and sibling.pos_payment_id.pos_order_id != existing
                       for sibling in refunds)
                or any(payment.pos_order_id != existing for payment in payments)):
            raise UserError(_("An allocation already belongs to another saved return."))
        if existing:
            for sibling in refunds:
                matching = payments.filtered(lambda payment: payment.uuid == sibling.payment_line_uuid)
                if (len(matching) != 1 or sibling.pos_payment_id and sibling.pos_payment_id != matching
                        or matching.payment_method_id != sibling.payment_method_id
                        or normalize(session.currency_id, matching.amount)[1] != -sibling.amount_minor
                        or matching.transaction_id != sibling.revolut_order_id
                        or matching.revolut_refund_operation_id
                        and matching.revolut_refund_operation_id != sibling):
                    raise UserError(_("The verified refund payment link does not match its original allocation."))
            existing._check_revolut_order()
        elif any(original.lines.filtered(lambda line: line.id == row["refunded_orderline_id"])
                 .product_id.tracking != "none" for row in snapshot["lines"]):
            raise UserError(_("The lost return has tracked products. A manager must recover its original lot details first."))
        evidence = RecoveryEvidence(self.env, RecoveryContents(existing, original, snapshot, decision, refunds))
        try:
            yield evidence
        finally:
            evidence._expire()

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
        decision = self._decision(snapshot, original, session.currency_id, order_uuid)
        self._check_total(snapshot, original, session.currency_id, total_minor, order_uuid,
                          frozen_total=decision.total_minor)
        result = []
        for source in self._eligible_sources(original, session):
            capacity, claimed, explicit = self._source_capacity(source)
            base, tip = capacity.base_minor, capacity.tip_minor
            remaining_base = max(0, base - capacity.reserved_base_minor)
            remaining_tip = max(0, tip - capacity.reserved_tip_minor)
            remaining = max(0, capacity.gross_minor - capacity.reserved_minor)
            needs_review = source.external_refund_review_required
            unknown_components = tip and any(item.origin == "external" and not item.allocation_explicit for item in claimed)
            if not needs_review and not unknown_components:
                capacity.check(component_error=_("The original payment's refund components exceed its refundable balance."),
                               gross_error=_("The original Revolut payment has insufficient refundable balance."))
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
                "return_base_minor": decision.base_minor, "return_tip_minor": decision.tip_minor,
                "return_total_minor": decision.total_minor,
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
        snapshot = self._normalize_return(financial_snapshot)
        original_rows = self.env["pos.order.line"].sudo().browse(
            [line["refunded_orderline_id"] for line in snapshot["lines"]]).exists().order_id
        self.acquire(session, session.company_id.id, order_uuid, original_rows | return_order)
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
        self._validate_return_quantities(snapshot, original, order_uuid)
        decision = self._decision(snapshot, original, currency, order_uuid)
        return_allocation = decision.allocation
        return_total_minor = decision.total_minor
        self._check_total(snapshot, original, currency, submitted_total_minor, order_uuid,
                          frozen_total=return_total_minor)
        self._check_total(snapshot, original, currency, -saved_total, order_uuid,
                          frozen_total=return_total_minor)
        if minor > return_total_minor:
            raise UserError(_("The Revolut allocation exceeds the return total. Reload its current allocation before refunding."))
        source_capacity, source_refunds, _source_explicit = self._source_capacity(source)
        if source.external_refund_review_required:
            raise UserError(_("External refund evidence needs manager investigation before another refund."))
        verified_before_claim = sum(source_refunds.filtered(
            lambda item: item.state == "verified"
        ).mapped("amount_minor"))
        base_minor, tip_minor, explicit = self._allocation(
            source, minor, base_amount_minor, tip_amount_minor, source_capacity.reserved_minor,
        )
        source_base, source_tip = source_capacity.base_minor, source_capacity.tip_minor
        if source_tip and any(item.origin == "external" and not item.allocation_explicit for item in source_refunds):
            raise UserError(_("An external refund has no verified base and terminal tip allocation. Reconcile its components separately before another refund."))
        source_capacity.check(minor, base_minor, tip_minor,
                              component_error=_("The original payment has insufficient refundable base or terminal tip balance."),
                              gross_error=_("The original Revolut payment has insufficient refundable balance."))
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
        return_capacity = self._capacity(decision.total_minor, decision.base_minor, decision.tip_minor,
                                         return_refunds.filtered(lambda item: item.state != "failed"))
        return_capacity.check(minor, base_minor, tip_minor,
                              component_error=_("Refund base and terminal tip allocations exceed the original return lines."),
                              gross_error=_("Revolut allocations exceed the return total."))
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
            pending_refunds_before_claim=tuple(
                {"order_id": item.revolut_order_id, "amount_minor": item.amount_minor}
                for item in source_refunds if item.state != "verified" and item.revolut_order_id
            ),
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
        # Native draft construction may not yet have complete financial lines.
        # Acquire from identity pointers, then distinguish preparation from settlement.
        self.acquire_native_creation([order])
        if existing_order:
            self.acquire_native_mutation(existing_order)
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("company_id", "=", session.company_id.id), ("order_uuid", "=", order_uuid)])
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
        snapshot = self._normalize_return(order, native_order=True)
        normalize = self.env["pos.revolut.payment.operation"].normalize_amount
        total_minor = normalize(session.currency_id, order.get("amount_total"))[1]
        original = self._return_original(snapshot, session)
        # Cash-only returns of a mixed-tender sale use the same original-sale lock.
        self._validate_return_quantities(snapshot, original, order_uuid)
        decision = self._decision(snapshot, original, session.currency_id, order_uuid)
        if total_minor >= 0 and decision.total_minor:
            raise UserError(_("A Revolut-linked return must have a negative total."))
        self._check_total(snapshot, original, session.currency_id, -total_minor, order_uuid,
                          frozen_total=decision.total_minor)
        total_minor = -decision.total_minor
        active = refunds.filtered(lambda item: item.state != "failed")
        for source in active.original_operation_id:
            source_capacity, _claimed, _explicit = self._source_capacity(source)
            source_capacity.check(
                component_error=_("The original payment has insufficient refundable base or terminal tip balance."),
                gross_error=_("The original Revolut payment has insufficient refundable balance."))
        verified = refunds.browse()
        for refund in refunds:
            refund.payment_method_id._check_refund_authority()
            payment = payments.get(refund.payment_line_uuid)
            if refund.state == "failed":
                if payment and payment.get("payment_status") == "done":
                    raise UserError(_("A failed Revolut refund cannot complete a return payment."))
                continue
            if refund.origin == "external" and refund.state == "verified" and (refund.provider_state != "completed" or not refund.verified_at):
                raise UserError(_("An external refund requires authoritative successful financial evidence."))
            # A verified refund can outlive its closed POS session. Keep its
            # original allocation fixed while allowing the same register to finish.
            if (not payment or snapshot != refund.financial_snapshot
                    or refund.original_order_id != original
                    or (refund.pos_session_id != session and (
                        (refund.state != "verified" and not (refund.origin == "external" and order.get("state") == "draft"))
                        or (refund.pos_session_id.state != "closed" and refund.origin != "external")
                        or (session.state != "opened" and not (refund.origin == "external" and existing_order and existing_order.state in {"paid", "done", "invoiced"}))
                        or refund.pos_session_id.config_id != session.config_id
                    ))
                    or refund.currency_id != session.currency_id
                    or (refund.return_total_minor and refund.return_total_minor != -total_minor)
                    or (refund.return_allocation and refund.return_allocation != decision.allocation)
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
        capacity = self._capacity(decision.total_minor, decision.base_minor, decision.tip_minor, active)
        capacity.check(component_error=_("Refund base and terminal tip allocations exceed the original return lines."),
                       gross_error=_("Revolut allocations exceed the return total."))
        if order.get("state") != "draft" and capacity.reserved_tip_minor != decision.tip_minor:
            raise UserError(_("Return every terminal tip through its explicit original Revolut allocation."))
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

    def _acquire_sources_and_refunds(self, sources, refunds=None):
        """Compatible suffix for discovery, which never requests earlier locks."""
        sources.flush_recordset()
        for source in sources.sorted("id"):
            self.env.cr.execute(
                "UPDATE pos_revolut_payment_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [source.id],
            )
        sources.invalidate_recordset()
        ledger = self.env["pos.revolut.refund.operation"].sudo()
        current = ledger.search([("original_operation_id", "in", sources.ids)], order="id") if sources else ledger.browse()
        current |= refunds if refunds is not None else ledger.browse()
        current.flush_recordset()
        for refund in current.sorted("id"):
            self.env.cr.execute(
                "UPDATE pos_revolut_refund_operation SET write_date = NOW() AT TIME ZONE 'UTC' WHERE id = %s", [refund.id],
            )
        current.invalidate_recordset()
        return current

    def _native_line_auxiliary_owners(self, values):
        """Discover the two native line relations whose child hooks watch POS."""
        owners = self.env["pos.order"].sudo().browse()
        for field, model in (
            ("pack_lot_ids", "pos.pack.operation.lot"),
            ("custom_attribute_value_ids", "product.attribute.custom.value"),
        ):
            commands = values.get(field) or []
            for start in range(0, len(commands), MAX_LINES):
                referenced = []
                line_ids = []
                for command in commands[start:start + MAX_LINES]:
                    if not isinstance(command, (tuple, list)) or not command:
                        continue
                    kind = command[0]
                    if kind in {1, 2, 3, 4} and len(command) > 1:
                        if type(command[1]) is int and command[1] > 0:
                            referenced.append(command[1])
                    elif kind == 6 and len(command) > 2 and isinstance(command[2], (tuple, list)):
                        referenced.extend(identifier for identifier in command[2]
                                          if type(identifier) is int and identifier > 0)
                    if kind in {0, 1} and len(command) > 2 and isinstance(command[2], dict):
                        line_id = command[2].get("pos_order_line_id")
                        if type(line_id) is int and line_id > 0:
                            line_ids.append(line_id)
                for offset in range(0, len(referenced), MAX_LINES):
                    records = self.env[model].sudo().browse(referenced[offset:offset + MAX_LINES]).exists()
                    owners |= records.pos_order_line_id.order_id
                owners |= self.env["pos.order.line"].sudo().browse(line_ids).exists().order_id
        return owners

    def _native_command_identities(self, values):
        """Discover complete ORM owner/source sets in bounded lookup batches.

        This interprets relationship identifiers only. Native ORM access and
        allocation validation remain authoritative after acquisition.
        """
        owners = self.env["pos.order"].sudo().browse()
        originals = self.env["pos.order"].sudo().browse()
        for field, model, owner_field in (
            ("lines", "pos.order.line", "order_id"),
            ("payment_ids", "pos.payment", "pos_order_id"),
        ):
            commands = values.get(field) or []
            for start in range(0, len(commands), MAX_LINES):
                referenced = []
                original_ids = []
                owner_ids = []
                for command in commands[start:start + MAX_LINES]:
                    if not isinstance(command, (tuple, list)) or not command:
                        continue
                    kind = command[0]
                    if kind in {1, 2, 3, 4} and len(command) > 1:
                        if type(command[1]) is int and command[1] > 0:
                            referenced.append(command[1])
                    elif kind == 6 and len(command) > 2 and isinstance(command[2], (tuple, list)):
                        # SET can itself contain more identifiers than one
                        # lookup batch; preserve the same bound below.
                        referenced.extend(identifier for identifier in command[2]
                                          if type(identifier) is int and identifier > 0)
                    if kind in {0, 1} and len(command) > 2 and isinstance(command[2], dict):
                        content = command[2]
                        if field == "lines":
                            owners |= self._native_line_auxiliary_owners(content)
                        owner_id = content.get(owner_field)
                        if type(owner_id) is int and owner_id > 0:
                            owner_ids.append(owner_id)
                        identifier = content.get("refunded_orderline_id") if field == "lines" else None
                        if type(identifier) is int and identifier > 0:
                            original_ids.append(identifier)
                for offset in range(0, len(referenced), MAX_LINES):
                    records = self.env[model].sudo().browse(referenced[offset:offset + MAX_LINES]).exists()
                    owners |= records.mapped(owner_field)
                    if field == "lines":
                        originals |= records.refunded_orderline_id.order_id
                owners |= self.env["pos.order"].sudo().browse(owner_ids).exists()
                originals |= self.env["pos.order.line"].sudo().browse(original_ids).exists().order_id
        return owners, originals

    def acquire_native_mutation(self, orders, values=None, *, related_orders=None):
        """Acquire every command owner and related order before native SQL."""
        orders = orders.exists()
        if not orders:
            return
        targets = orders
        new_originals = self.env["pos.order"].sudo().browse()
        if values:
            if values.get("lines") is not None and values.get("lines") is not False:
                for target in targets:
                    self.preflight_order_lines({**values, "uuid": target.uuid,
                                                "lines": list(values["lines"])})
            owners, new_originals = self._native_command_identities(values)
            orders |= owners
        if related_orders is not None:
            orders |= related_orders
        originals = orders | orders.sudo().lines.refunded_orderline_id.order_id | new_originals
        sessions = orders.session_id
        identities = {(order.company_id.id, order.uuid) for order in orders}
        if values:
            if values.get("session_id"):
                sessions |= self.env["pos.session"].browse(values["session_id"]).exists()
            identities.update((values.get("company_id") or order.company_id.id,
                               values.get("uuid") or order.uuid) for order in targets)
        self.acquire_many(sessions, identities, originals)
        orders.invalidate_recordset()
        orders.lines.invalidate_recordset()
        orders.payment_ids.invalidate_recordset()

    def acquire_native_creation(self, vals_list):
        """Choose native identity and acquire all command owners before INSERT."""
        from uuid import uuid4

        defaults = self.env["pos.order"].default_get(["session_id", "company_id"])
        prepared = [dict(values) for values in vals_list]
        sessions = self.env["pos.session"].browse()
        owners = self.env["pos.order"].sudo().browse()
        originals = self.env["pos.order"].sudo().browse()
        identities = set()
        for values in prepared:
            if values.get("lines") is not None and values.get("lines") is not False:
                self.preflight_order_lines({**values, "lines": list(values["lines"])})
            values.setdefault("uuid", str(uuid4()))
            session = self.env["pos.session"].browse(values.get("session_id") or defaults.get("session_id")).exists()
            if session:
                sessions |= session
                identities.add((values.get("company_id") or session.company_id.id, values["uuid"]))
            command_owners, command_originals = self._native_command_identities(values)
            owners |= command_owners
            originals |= command_originals
        sessions |= owners.session_id
        identities.update((owner.company_id.id, owner.uuid) for owner in owners)
        originals |= owners | owners.lines.refunded_orderline_id.order_id
        self.acquire_many(sessions, identities, originals)
        return prepared

    def acquire_native_line_mutation(self, orders, original_line_ids, values=None):
        """Discover a newly introduced original before native line SQL."""
        if values is not None:
            for content in values if isinstance(values, list) else [values]:
                orders |= self._native_line_auxiliary_owners(content)
        originals = (orders | orders.sudo().lines.refunded_orderline_id.order_id
                     | self.env["pos.order.line"].sudo().browse(original_line_ids).exists().order_id)
        self.acquire_many(orders.session_id,
                                 {(order.company_id.id, order.uuid) for order in orders}, originals)

    def acquire_discovery(self, source, candidates=None):
        """Serialize financial discovery without requesting native locks later."""
        if candidates is not None:
            refunds = [item for item in candidates
                       if isinstance(item, dict) and item.get("type") == "refund"]
            # Listing can omit the parent and require an unchanged detail GET.
            # Such a page conservatively protects the complete source set.
            if not any(item.get("related_order_id") is None for item in refunds):
                parents = {item["related_order_id"] for item in refunds
                           if isinstance(item.get("related_order_id"), str)}
                source = source.filtered(lambda operation: operation.revolut_order_id in parents)
        return self._acquire_sources_and_refunds(source)

    def acquire_payment_observation(self, operation):
        """Allow tip projection to mutate native evidence without an inversion."""
        operation.ensure_one()
        order = operation.pos_order_id or operation.authorization_id.pos_order_id
        self.acquire_many(operation.pos_session_id,
                          [(operation.company_id.id, operation.order_uuid)], order,
                          sources=operation)

    def acquire_refund_status(self, refund):
        """Apply observed status in the same order as native finalization."""
        refund.ensure_one()
        if refund.order_uuid:
            order = refund.pos_order_id or self.env["pos.order"].sudo().search([
                ("company_id", "=", refund.company_id.id), ("uuid", "=", refund.order_uuid),
            ], limit=1)
            session = order.session_id or refund.pos_session_id
            self.acquire(session, refund.company_id.id, refund.order_uuid,
                         refund.original_order_id | order, refunds=refund)
        else:
            self._acquire_sources_and_refunds(refund.original_operation_id, refund)
        refund.invalidate_recordset()

    def acquire_session_closure(self, sessions):
        """Protect financial evidence before native session accounting starts."""
        sessions = sessions.sorted("id")
        charges = self.env["pos.revolut.payment.operation"].sudo().search([
            ("pos_session_id", "in", sessions.ids),
        ], order="id")
        refunds = self.env["pos.revolut.refund.operation"].sudo().search([
            ("order_uuid", "!=", False), "|", ("pos_session_id", "in", sessions.ids),
            ("pos_order_id.session_id", "in", sessions.ids),
        ], order="id")
        identities = {(record.company_id.id, record.order_uuid) for record in charges}
        identities.update((record.company_id.id, record.order_uuid) for record in refunds)
        native_orders = sessions.sudo().order_ids | refunds.pos_order_id
        identities.update((order.company_id.id, order.uuid) for order in native_orders)
        originals = (charges.pos_order_id | refunds.original_order_id | native_orders
                     | native_orders.lines.refunded_orderline_id.order_id)
        self.acquire_many(sessions, identities, originals, refunds=refunds, sources=charges)
        charges.invalidate_recordset()
        refunds.invalidate_recordset()
        return charges, refunds

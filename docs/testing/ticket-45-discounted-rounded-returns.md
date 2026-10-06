# Ticket 45 — Discounted and globally rounded returns

Implementation baseline: fetched `origin/main` / `main` `062409c`, 2026-10-06.
Branch: `codex/45-refund-discounted-and-rounded-sales`.
Addon version: `19.0.1.18.0`.

## Public test seams and reproductions

The owner confirmed these seams: persisted public cart preparation, mocked terminal start/poll and report verification, finalized native sale, manager source selection, saved return, refund reservation/verification/recovery, and native completion including external association. Merchant HTTP is mocked in pinned Odoo `19.0.20260908`, with the environment's real Merchant HTTP guard enabled.

Two separate regressions reproduced the ticket against unchanged allocation behavior. A 10.00 goods line plus a -1.00 adjustment settled at 9.00; source selection rejected negative entitlement. Six 10.01 lines plus a final-UUID 0.01 line settled at 60.05 under five-cent global rounding; source selection rejected its negative last-line remainder. Both verified and finalized the original sale before failing; neither reached a refund POST. Log: `/tmp/ticket45-red3.log`. Fixture setup failures before these reproductions are not product evidence.

## Allocation and compatibility

Healthy nonnegative conserved ceilings keep their established distribution. Supported negative adjustments have zero separate entitlement; their effect reduces positive goods proportionally. If an independent rounding remainder is negative, cumulative integer rounding over positive weights conserves the original frozen payable and cannot manufacture negative capacity. If recorded line subtotals cancel or round to zero, native unrounded gross weights use the original product inputs only while tax and fiscal-position records have not changed since the frozen authorization. Changed historical tax inputs block this ambiguous fallback for manager reconciliation. No historical tax rate is guessed or financial record rewritten.

Return quantities are magnitudes, with each native line carrying the opposite sign to its linked original. Original products, prices, discounts and taxes remain unchanged. Terminal tips and base payment allocations remain separate, with source and original tender caps still enforced. Zero-entitlement native returns complete without any provider reimbursement or positive balancing tender.

Existing claims are validated against the original accepted ceilings as well as the corrected ones. Earlier actual cents and quantities are deducted once per return identity. When historical claims have already exhausted a line at an older ceiling, only remaining unclaimed entitlement is distributed over eligible remaining quantities. Saved claim JSON, native completed totals, provider references and surviving reservations are never rewritten. Ambiguous historical totals or missing multi-line allocation evidence remain blocked for manager reconciliation.

Native taxes keep the existing Odoo engine's evidence while the accepted allocation controls monetary totals. The discounted included-tax regression verifies actual stock restocking, a posted balanced credit note, unchanged product inputs and no duplicated native effects on replay. Browser tests exercise actual TicketScreen selection, positive reversal editing and verified native receipts.

## Verification

Final combined verification and independent Standards/Spec review will be recorded before closure.

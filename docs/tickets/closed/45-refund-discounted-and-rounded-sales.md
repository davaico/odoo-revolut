# 45 — Complete refunds for discounted and rounded sales

**Work branch:** `codex/45-refund-discounted-and-rounded-sales`

**State:** closed

**Triage:** ready-for-agent

**Severity:** P2

## What to build

A manager can fully or partially return an eligible paid sale containing supported negative/discount adjustments or global rounding. Source selection, saved return, refund dispatch, recovery and native completion agree on the original collected amount, with no excessive refund or stranded entitlement.

This groups two review findings because both concern the original per-line entitlement calculation and its downstream native return workflow. Keep their independent reproductions and acceptance checks.

## Source and evidence

Full integration review of main `597a59ae0f8e489773e02f7776bda7001beb5741`, 2026-10-06. Both cases were reproduced in pinned Odoo through public cart preparation, mocked payment start/poll, verified payment and native sale finalization:

1. Quantity-one lines priced 10.00 and -1.00 successfully settled at 9.00. Their entitlements became 1000 and -100 minor units. Native return creation and public refund-source selection rejected the negative entitlement. Omitting the adjustment instead requires 10.00 against a 9.00 source capacity.
2. Six 10.01 lines and one 0.01 line, with five-cent global rounding, successfully settled at 60.05. When the small line sorts last by UUID, independently rounded preceding shares leave entitlements of 1001 times six and -1. Native return creation and public refund-source selection both rejected the return.

Neither failing return sent a provider refund request. The approved cart contract retains legitimate negative/discount sale lines; the mission requires full and partial refunds. The approved rounding work requires all eligible returned quantities to exhaust entitlement exactly without extra cents or stranded residuals.

## Acceptance criteria

- [x] Preserve separate failing public-workflow regressions for both examples before changing allocation behavior.
- [x] Define and implement a conserved allocation for supported sale adjustments that permits eligible returns without changing original product prices, discounts, quantities or taxes. Cover both negative-price lines and supported negative-quantity adjustments, respecting native Odoo return semantics.
- [x] Distribute global rounding without manufacturing negative capacity for positive goods. Cover rounding up/down, varied UUID ordering, multiple lines, very small lines and supported currency precision.
- [x] Exercise full returns, multiple partial returns in different orders and the final remaining balance through source selection, saved return, reservation, mocked provider verification and native completion. All eligible returned quantities exhaust the original collected entitlement exactly.
- [x] Preserve mixed-tender caps, explicit base/terminal-selected-tip allocation, quantity limits and the rejection of positive balancing tenders that conceal excessive reimbursement.
- [x] Preserve verified, pending and uncertain reservations under concurrency and interruption. Failed allocations release only their own reservation; surviving allocations and completed refunds are never recalculated or replayed.
- [x] Verify saved payment amounts, return totals, native receipts and applicable stock/accounting effects. Exercise external refund association where it consumes the same allocation decisions, without issuing another provider refund.
- [x] Preserve immutable financial history and frozen return allocations. Test compatibility with previously accepted partial returns and retain conservative handling of genuinely ambiguous historical evidence.
- [x] Run focused mocked regressions and affected integrated tests; document any required compatibility or operator guidance. Do not silently disable approved cart features to make refunds pass.

## Blocked by

None. Can start immediately against the current integration baseline. Earlier return-allocation tickets are closed; neither other review ticket is a prerequisite.

## Scope limits

No new refund policy, provider contract change, rewrite of historical financial evidence, live refund, deployment or unrelated architecture cleanup. If supporting an approved sale shape requires a new business policy, document that precise decision for the owner rather than weakening source limits.

## Approval and publication — 2026-10-06

The owner approved the three-ticket breakdown and explicitly requested direct
publication as ready-for-agent. This ticket was claimed for implementation on 2026-10-06. Its
work branch is an implementation assignment, not a branch created by this
publication. Recheck the current implementation before starting; review
evidence describes the pinned main revision above. Implementation has not started as part of this publication. Deployment and
live financial operations remain outside this ticket's automated work.

## Implementation and closure — 2026-10-06

Closed on runtime `00b46ed4840a8ec659f8b38f27f9cdaec06910e3`, based on fetched
current main `062409c`. The separate reported failures were reproduced through
verified public sale/refund workflows before correction. Conserved allocations
support discounted and globally rounded sales, both adjustment signs, zero-value
native reversals, earlier frozen partial claims and external refund association.

Complete mocked acceptance passed **591 fresh-install tests and 591 upgrade
tests**, zero failures or errors, including actual concurrency, native browser
receipts, stock and accounting effects. Focused regressions, 99 payment-state
checks and 54 tooling checks also pass (three existing optional PDF probes skip).
Independent Standards and Spec reviews each report zero findings.

[Verification and compatibility evidence](../../testing/ticket-45-discounted-rounded-returns.md)
records reproductions, commands, logs and review limits. Upgrade guidance is in
[installation instructions](../../installation.md). No historical financial
record is rewritten, and no live financial operation or deployment occurred.

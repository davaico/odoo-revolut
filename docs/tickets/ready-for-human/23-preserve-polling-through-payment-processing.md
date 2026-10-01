# 23 — Preserve payment polling through valid processing states

**Work branch:** `codex/23-preserve-polling-through-payment-processing`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-23`

**State:** open

**Triage:** ready-for-human

**Priority:** P2

## Observed problem

Live ticket-12 acceptance on 2026-09-29 at deployed revision `76209bb` found
approved card payments that initially appeared unresolved in POS. Operations
`10`, `11`, `16` and `17` required manual Check status, which reconciled their
existing captured payments. Fully paid orders then opened receipts with
matching references. Operation `16` correctly left one penny due on a
partially paid order. Operations `4` and `14` completed automatically, so
this is intermittent live behavior, not a total loss of automatic checkout.

The exact early live Merchant payload was not captured. Local characterization
found a software gap: valid initial pending/authentication/early-authorisation
payment states are classified unresolved, and the foreground state machine
treats unresolved as final failure, stopping before later capture.
`authorised` and `capture_started` continue pending; captured verifies.
The prior stored provider state `processing` belongs to the intent and does
not identify the underlying payment state rejected earlier.

This gap is reproducible with mocks but does not prove a particular early
state caused all four live incidents. Diagnose against the documented contract
and matching identity/amount/currency evidence before changing the classifier.
Generic unresolved or malformed evidence must remain protected.

## Acceptance criteria

- [x] Identify and cover provider-documented non-final underlying-payment states relevant to terminal polling. Require matching operation/order/intent/payment identity, exact integer amount and currency before accepting transitions.
- [x] Continue bounded observation through valid processing states to capture, without another financial start. A completed intent alone never establishes payment success.
- [x] Only verified captured/completed underlying payment marks a tender done. A fully paid unchanged order completes automatically; a partially paid order stays open with the correct remaining amount.
- [x] Keep malformed, mismatched, unknown or uncertain evidence guarded. Do not make every unresolved result pollable/retry-safe; retain foreground timeout and later reconciliation.
- [x] Add real ORM observation regressions and lifecycle/POS-adapter tests for intermediate-to-captured progression, split/multiple card lines, failures, invalid fields and timeouts. Financial calls are mocked or blocked.
- [ ] Record a reviewed candidate and repeat controlled full and split/multiple-line live payments, explicitly recording whether Check status or Validate was needed. One automatic success does not cover previously failing paths.

## Blocked by

None for local diagnosis/mocked implementation; verification/classifier and
POS lifecycle seams are present on reviewed main.

Reviewed local implementation and mocked verification are complete at
`97f5c0d4e427e232b5985cce121cf4adbf71049c`. Human deployment/retest remains
subject to a fresh read-only check of financial blockers, including all five
test refunds, before deployment.

## Validation limits and live gates

- The exact early live payload remains unavailable; existing probes do not exercise real ORM transactions/locks or replay captured network traffic.
- The five test refunds now appear Refunded in the operator's Revolut
  screenshot, with Odoo completion operator-reported on 2026-10-01. Confirm
  their local final state and any other blockers read-only before deployment;
  retain the financial guard.

## Release gate

Blocks closure of ticket 12. Diagnosis and mocked implementation may start
locally; the reviewed fix and affected live retests remain outstanding.

## Verification evidence

The [mocked implementation record](../../testing/ticket-23-payment-processing.md)
records real committed ORM regressions, lifecycle tests and actual POS tours.
The reviewed candidate passed **221 fresh-install**, **221 upgrade** and
**8 Restaurant** tests, plus **49 lifecycle** and **29 deployment-tooling**
tests. Independent Standards and Spec review found no remaining actionable
issues after correcting a stale-final-intent timeout regression. Deployment and
physical acceptance stay gated by financial reconciliation; none was performed.

See [operator observations](../../testing/ticket-12-operator-observations.md),
sections covering the Cash/Revolut split, three-unit sale and separate
one-penny card payments. Each manual recovery retained the same operation and
payment references, without a replacement charge.

A deterministic Node replay of pending, unresolved/prior provider processing,
then verified reproduces foreground failure before capture. A standalone
probe of the deployed Python observation method with fake ORM plumbing
confirms the classifier gap. Neither probe is a real ORM/lock regression or
a replay of the missing live payload; commands and limits are in the chronology.

Primary sources checked during diagnosis:
[payment lifecycle](https://developer.revolut.com/docs/guides/merchant/reference/order-lifecycle)
and [terminal polling](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments).

## Comments

2026-09-29: Recorded during controlled acceptance and published with its
evidence. Diagnose and fix locally while retaining all pending refund claims;
deployment and physical retests remain gated by financial reconciliation.

2026-09-29: Implemented and reviewed the mocked fix in the assigned worktree
after updating from main. Provider-documented early payment states retain
bounded polling, and invalid intent evidence cannot override payment guards.
Review's timeout/stale-final-intent finding was reproduced through real ORM,
corrected and re-reviewed. Final candidate `97f5c0d` passed mocked install,
upgrade, Restaurant, lifecycle and tooling verification. Moved to
`ready-for-human` for the retained full/split/multiple-card live acceptance
criterion. No deployment or live financial tests; pending refund claims remain
intact.

2026-09-29: Triaged as ready-for-agent after the owner moved this ticket to
`ready-for-agents/`. The bounded polling contract and required ORM/lifecycle
regressions are defined. Missing early live payload limits root-cause
attribution and live validation; it does not prevent local diagnosis against
the documented contract or mocked implementation.

2026-09-30: The operator reports five separate £0.01 Revolut credits for the
test refunds, but all five Odoo refund operations still show Pending. A fresh
Odoo status check of refund `5` still reported provider `processing`, and
refund `1` showed the same stored provider state. These refund observations do
not establish the early payment-state payload behind this ticket's automatic
polling defect. The reviewed local correction is merged into main but remains
undeployed; live validation remains gated on authoritative refund
reconciliation. See [ticket 12's refund checkpoint](12-live-terminal-release-evidence.md).

2026-10-01: The operator reports Odoo Completed, and the supplied Revolut
Merchant screenshot shows all five matching £0.01 refund orders as Refunded.
This supersedes the preceding pending-refund observation; it does not establish
the early payment-state payload relevant to this ticket. The merged fix remains
undeployed. After read-only financial/deployment preflight, repeat controlled
full and split/multiple-card payments and record whether each receipt opens
automatically or needs Check status. The live criterion remains unchecked.

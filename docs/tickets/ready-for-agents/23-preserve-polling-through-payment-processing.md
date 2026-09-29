# 23 — Preserve payment polling through valid processing states

**Work branch:** `codex/23-preserve-polling-through-payment-processing`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-23`

**State:** open

**Triage:** ready-for-agent

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

- [ ] Identify and cover provider-documented non-final underlying-payment states relevant to terminal polling. Require matching operation/order/intent/payment identity, exact integer amount and currency before accepting transitions.
- [ ] Continue bounded observation through valid processing states to capture, without another financial start. A completed intent alone never establishes payment success.
- [ ] Only verified captured/completed underlying payment marks a tender done. A fully paid unchanged order completes automatically; a partially paid order stays open with the correct remaining amount.
- [ ] Keep malformed, mismatched, unknown or uncertain evidence guarded. Do not make every unresolved result pollable/retry-safe; retain foreground timeout and later reconciliation.
- [ ] Add real ORM observation regressions and lifecycle/POS-adapter tests for intermediate-to-captured progression, split/multiple card lines, failures, invalid fields and timeouts. Financial calls are mocked or blocked.
- [ ] Record a reviewed candidate and repeat controlled full and split/multiple-line live payments, explicitly recording whether Check status or Validate was needed. One automatic success does not cover previously failing paths.

## Blocked by

None for local diagnosis/mocked implementation; verification/classifier and
POS lifecycle seams are present on reviewed main.

## Validation limits and live gates

- The exact early live payload remains unavailable; existing probes do not exercise real ORM transactions/locks or replay captured network traffic.
- Live deployment/retest requires reconciliation of unresolved financial operations; pending refunds must not be bypassed.

## Release gate

Blocks closure of ticket 12. Diagnosis and mocked implementation may start
locally; the reviewed fix and affected live retests remain outstanding.

## Verification evidence

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

2026-09-29: Triaged as ready-for-agent after the owner moved this ticket to
`ready-for-agents/`. The bounded polling contract and required ORM/lifecycle
regressions are defined. Missing early live payload limits root-cause
attribution and live validation; it does not prevent local diagnosis against
the documented contract or mocked implementation.

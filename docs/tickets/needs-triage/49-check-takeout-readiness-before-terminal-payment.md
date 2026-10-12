# 49 — Check timed Takeout readiness before collecting terminal payment

**Work branch:** `codex/49-check-takeout-readiness`

**State:** open

**Triage:** needs-triage

**Reported:** 2026-10-12, ticket 12 Restaurant manual acceptance.

## Problem and observed evidence

During live acceptance, a £0.01 Takeout terminal payment succeeded, but native
checkout reported a missing time slot and left the captured order Draft. The payment screen says
Payment Successful while no completed POS sales receipt exists. Required
pickup scheduling should be resolved before collecting payment, with a clear
safe completion path if a captured payment is already present.

Owner screenshots show a completed dine-in receipt 261-4-000001, then Takeout
Payment Successful, no Monday October 12 slots, and Tuesday October 13 slots.
Read-only SQL at 11:03:30 UTC confirms:

- Dine-in operation76 verified/captured £0.01, tip0, fulfilment eat_in;
  order62 / 261-4-000001 Paid, table3, preset1, tender82 done.
- Takeout operation77 verified/captured £0.01, tip0, fulfilment take_away;
  order63 / 261-4-000002 Draft, no table, preset2, tender83 done.
- Each operation has exactly one succeeded create_order and create_intent;
  neither retains an order/terminal lock. No duplicate capture is established.
- Takeout preset2 uses timed scheduling. Calendar2 has Tuesday–Saturday
  lunch/afternoon hours and no Monday hours, explaining the empty Monday view.
- At inspection, the same draft already has preset_time October13 10:00 UTC
  (12:00 in the owner's timezone). Selection timing relative to capture was
  not independently recorded. Counts76 operations/169 dispatch claims.

## Inspection limits

Installed native PosOrder.presetRequirementsFilled rejects a timed preset with
no preset_time. OrderPaymentValidation checks that readiness before native
finalization. The addon financial snapshot binds preset/table, not preset_time.
These are static observations, not a reproduced runtime root cause.

No independent browser replay, regression suite, runtime fix or deployment was
performed. The owner already exercised the live symptom; do not repeat a real
charge to diagnose it. A mocked native checkout reproducer is required before
implementation. Manual Validate of the same captured tender completed the
order; this does not establish automatic completion with a valid slot selected
before dispatch.

## Same-payment recovery — verified

Owner screenshot `codex-clipboard-cf547165-5829-431b-8dfb-87fd83c5ba5f.png`
after Continue/Validate shows POS sales receipt 261-4-000002, Takeout October13
12:00, total/Revolut £0.01. Read-only SQL at 11:07:54 UTC confirms original order63
now Paid, original tender83 done, same operation77 captured1p/tip0/take_away.
Counts remain 76 operations / 169 dispatch claims / 17 refunds; one succeeded
order/intent pair per Restaurant operation. No additional payment attempt or
charge recorded. Observed recovery PASS; no runtime fix or automated replay.

## Acceptance criteria

- [ ] A missing required pickup slot produces actionable feedback before a
  Revolut payment starts; zero provider dispatches in a narrow mocked test.
- [ ] With a valid Takeout slot, one capture automatically completes the same
  native order and yields its POS sales receipt.
- [x] An already captured tender can complete after correcting scheduling
  without another payment, replacement tender or force-completion bypass.
- [ ] Preserve financial cart authority, table/preset checks, and ordinary
  untimed dine-in checkout; do not loosen timing globally to hide this case.

## Dependencies and fixture preservation

Keep order63/tender83/operation77 intact. Do not pay again, remove its tender,
cancel the order or refund it as part of diagnosis. No implementation dependency
identified. Ticket12 Takeout financial/context and same-payment manual
completion checks pass; automatic completion remains unresolved. Dine-in native
completion passes. Subsequent session closure posted £0.02 and reopened
cleanly, with a free table screenshot; both original orders are now Done.
Remaining gross charge budget £0.03.

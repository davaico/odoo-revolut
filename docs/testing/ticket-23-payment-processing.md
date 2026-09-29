# Ticket 23 — Observe valid payment processing through capture

## Diagnosis and provider contract

The assigned branch was fast-forwarded to reviewed `main`
`ffae23dcfcf71dc61293404e3c7183b3fe70e750` before implementation.
The early live payload from the four manually recovered payments remains
unavailable. These regressions establish a software gap and its correction;
they do not attribute all four live incidents to a particular provider state.

Rechecked primary sources on 2026-09-29:

- [Order and payment lifecycle](https://developer.revolut.com/docs/guides/merchant/reference/order-lifecycle)
  documents payment `pending`, `authentication_challenge`,
  `authentication_verified`, `authorisation_started`, `authorisation_passed`,
  `authorised` and `capture_started` before capture. Observing those intermediate
  states establishes neither success nor retry eligibility.
- [Terminal push-payment polling](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
  requires underlying-payment observation after intent completion. It also
  documents `declining`, `cancelling` and `failing` as transitional, and
  `captured`/`completed` as successful final payment states.

`processing` is an order/intent state, not an accepted underlying-payment
state in this classifier. Unknown underlying states remain unresolved.

## Implementation

Addon `19.0.1.7.7` adds the five missing early payment states to the existing
pending classification. Matching payment/order references, an exact integer
minor-unit amount and currency remain mandatory. The public RPC still checks
operation, order and payment-line ownership; intent identity and payment
association must also match. A completed intent alone cannot verify payment.

An adversarial ORM regression also reproduced a guard gap: after a payment
reference was stored, an invalid intent could be overwritten by a subsequent
payment read. Polling now returns the unresolved intent result immediately,
retaining the known reference for a later valid observation.

Review found and corrected an edge in that guard: a valid stale final intent
omitting an already-known payment reference after timeout must still allow a
fresh underlying-payment read. The observation now uses its existing stored
reference fallback and records pending. A separate real ORM regression failed
for both `cancelled` and `failed` intents before this correction, then verified
the same captured/completed payments afterward. Invalid intents still stop.

The existing lifecycle needs no production change. It continues observing
server-confirmed pending states within its original 60-second limit and stops
on generic unresolved evidence. It never dispatches a replacement charge for
these processing observations. Only verified payment lets Odoo mark the line
done; native Odoo validation then completes a fully paid unchanged order.
Partial payment retains the exact remaining amount.

No new setting, credential rotation, dependency or schema migration is needed.
When release is authorized, follow the offline addon upgrade instructions and
reopen POS. This task performs no deployment or live financial test.

## Agreed seams and verification

Ticket 23 specifies the real ORM observation/RPC, controlled lifecycle and
actual Odoo POS adapter seams. Tests mock provider HTTP and time only; ORM
observations use real committed cursors and row locks. The Docker test runtime
blocks unmocked Merchant HTTP and has no external network route.

- ORM TDD: the progression regression failed for all five missing early
  states on main, then passed after the minimal classifier change. The
  known-payment/foreign-intent regression separately failed before the guard
  correction and passed afterward.
- Focused public-payment and committed-transaction tests: **55 passed**, zero
  failures/errors. They cover documented progression, identity and money
  mismatches, non-integer amounts, malformed/unknown states, all unsuccessful
  final outcomes, retained timeout claims and later cron recovery on the same
  attempt. The observation fixture rejects every HTTP mutation.
- The reviewed correction and affected ORM/payment/concurrency suites:
  **80 passed**, zero failures/errors, including both stale final intents after
  timeout. The unchanged invalid-intent regressions remain green.
- Controlled lifecycle file: **49 passed**, zero failures/skips. New tests
  exercise early states to capture, unsuccessful transitions, a bounded
  timeout followed by read-only recovery, and generic unresolved stopping
  despite a prior documented processing state.
- Focused POS progression tours: **3 passed**, zero failures/errors. Full
  payment, cash/card split and two successive card lines complete without
  Check status or Validate. The first card line pays 12.33 of 12.34, leaves
  exactly 0.01 due on the same order, and retains its own reference while the
  second card line completes. Each tender dispatches one order/intent pair.
- The full-payment browser regression fails on unchanged `ffae23d` with the
  same fixture and 20-second receipt wait used by the passing candidate. The
  extended test wait observes seven intermediate states; the product timeout
  remains 60 seconds.
- Focused POS guard tours: **4 passed**, zero failures/errors. Decline and
  failure follow early authorisation; malformed processing amounts stay
  guarded through Check status and deletion attempts; a known underlying
  payment in authentication challenge reaches the foreground timeout with
  its reference intact and no replacement charge.

There is no configured static typechecker, linter or coverage measurement.
Python/JavaScript syntax checks complement runtime verification and are not
reported as type checking. Full-suite and independent review evidence will be
recorded after the candidate is pinned.

## Live gate and retained acceptance work

Ticket 23 stays open until a reviewed candidate is authorized for deployment
after reconciliation of ticket 12's unresolved financial operations, including
pending refunds. The current task is limited to mocked implementation,
tests and review. Existing refund claims are preserved.

After that gate clears, repeat controlled full, cash/card split and multiple
card-line payments, including the paths that previously required recovery.
Record each operation/order/intent/payment reference, the remaining amount
after partial payment, and whether Check status or Validate was needed.
One automatic success cannot cover the previously failing paths. Capture the
early provider evidence if a path still fails. Ticket 12 remains open.

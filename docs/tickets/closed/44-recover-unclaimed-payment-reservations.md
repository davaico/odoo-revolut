# 44 — Recover payment reservations interrupted before dispatch

**Work branch:** `codex/44-recover-unclaimed-payment-reservations`

**State:** closed

**Triage:** ready-for-agent

**Severity:** P2

## What to build

A cashier can recover the original payment after its worker stops between committing the reservation and claiming the first financial dispatch. Recovery preserves the authorized cart, payment identity and audit history, and allows the payment to proceed or become safely retryable without leaving the terminal or session permanently blocked.

## Source and evidence

Full integration review of main `597a59ae0f8e489773e02f7776bda7001beb5741`, 2026-10-06. A simulated interruption during terminal eligibility checking left a durable operation in the created state. Pinned Odoo runtime reproduction established zero provider requests and zero dispatch claims. Duplicate start, polling and cancellation returned unresolved; manager and scheduled reconciliation left the attempt unchanged. The terminal remained blocked and session closure was rejected.

The approved cart contract requires committed operations to resume with dispatch claims preventing replay. Existing timeout tests resume the original worker and do not establish recovery when that worker has stopped.

## Acceptance criteria

- [x] Reproduce the interruption after reservation commits and before financial dispatch is claimed, with the original request permanently stopped. Exercise the ordinary cashier recovery path against the saved authorized cart.
- [x] Establish recovery eligibility under the existing financial locks using durable dispatch evidence. An empty provider lookup alone never proves that a claimed request was not sent.
- [x] Resume the existing operation or record an explicitly safe terminal outcome, preserving its original identity and history. The cashier can then complete the intended payment or take the permitted safe retry/removal path.
- [x] A delayed original worker racing recovery, multiple cashiers and concurrent reconciliation cannot dispatch the same financial step twice or release an active reservation incorrectly.
- [x] Cover interruption immediately before and after each relevant dispatch claim. Claimed requests with ambiguous outcomes retain their reservations and follow existing reconciliation; no blind order or intent replay is introduced.
- [x] Verify the resulting native POS line and sale, terminal availability and session closure through public workflows. A verified recovery completes only the unchanged original order with matching amount, currency and references.
- [x] Add mocked regression coverage and concise operator recovery guidance. Tests never contact a real terminal or Merchant API.

## Blocked by

None. Can start immediately against the current integration baseline. The other findings from this review do not gate this slice.

## Scope limits

No provider idempotency assumptions, manual force-success action, live payment, deployment or broad state-machine refactor. Existing release acceptance remains separate.

## Approval and publication — 2026-10-06

The owner approved the three-ticket breakdown and explicitly requested direct
publication as ready-for-agent. This ticket remains open and unclaimed. Its
work branch is an implementation assignment, not a branch created by this
publication. Recheck the current implementation before starting; review
evidence describes the pinned main revision above. Implementation has not started as part of this publication. Deployment and
live financial operations remain outside this ticket's automated work.


## Completion and verification — 2026-10-06

Implemented on `codex/44-recover-unclaimed-payment-reservations` from fetched
main `b672985386f907e19e898f9df3befdf978462303`. Tested runtime:
`15575ffb1abc7df9d6e018ba6e7913cfb0865e79`, addon `19.0.1.17.1`.

Explicit cashier cancellation records a safe outcome only when durable claims
prove terminal dispatch was never claimed. Original authorization, identity and
history remain intact; the cashier can remove or retry the line. Claimed or
ambiguous requests keep their reservations and existing reconciliation rules.

Verification: **573 fresh-install / 573 upgrade** Odoo tests passed with zero
failures/errors and runner exit 0; **73** affected recovery/register tests and
both native recovery/checkout/session-closure regressions passed; **99** POS
lifecycle tests passed. Host tooling ran **57** tests: **54 passed / 3 optional
PDF-dependency skips**. Syntax/whitespace checks passed. Independent Standards
and Spec reviews each reported **0 actionable findings**.

[Verification and recovery proof](../../testing/ticket-44-unclaimed-reservation-recovery.md)
records commands, red/green evidence, concurrency controls and native fixture
limitations. Operator guidance is in `docs/installation.md`. This completion
supersedes the publication-time open/unclaimed status above. Deployment and
live-device acceptance remain separate.

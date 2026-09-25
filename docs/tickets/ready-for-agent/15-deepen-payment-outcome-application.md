# 15 — Deepen payment outcome application

**Work branch:** `codex/15-deepen-payment-outcome-application`

**State:** open

**Triage:** ready-for-agent

## What to build

Preserve the same durable payment result across cashier polling, cancellation, timeout, scheduled reconciliation, and manager association while concentrating finality, retry safety, reference updates, reconciliation scheduling, and release rules behind the payment-operation seam. Cashiers and managers must observe the authoritative outcome despite competing or delayed observations.

## Acceptance criteria

- [ ] Concentrate payment outcome application so callers no longer select persistence flags or repeat lock-and-finality protocols to enforce the same transition rules. A file move alone does not satisfy this criterion.
- [ ] Only a verified successful underlying payment can authorize sale completion. Intent completion alone remains insufficient, and intent-only failure cannot release an attempt whose payment still awaits verification.
- [ ] Authoritative final outcomes survive stale polling, timeout, cancellation, and scheduled reconciliation. Order and terminal protection are released only when the existing evidence rules permit it.
- [ ] Preserve durable claim-before-dispatch behavior and current reconciliation timing. Ambiguous creation or cancellation remains recoverable without replaying a financial mutation; safe replacement attempts retain their history.
- [ ] Manager association retains authorization, reference ownership checks, audit evidence, and final-state protection while using the same owner for applicable outcome rules. Association alone cannot establish a verified payment.
- [ ] Keep payment and refund outcome rules distinct. Retain the current external adapter seam, production transaction semantics, browser-facing results, and stored operation/reference compatibility.
- [ ] Preserve real-path database concurrency tests for stale foreground/background polling, stale cancellation, and cancellation during payment verification, alongside manager-association tests. Any changed dispatch tests must exercise the production claim path rather than reproduce its SQL or algorithm.
- [ ] Demonstrate a stale observation arriving after verified success and an uncertain payment resolved through manager association and reconciliation, with correct POS recovery and references. Record focused test results and the transition knowledge removed from callers; all provider calls remain mocked.

## Blocked by

- None. Existing recovery, manager reconciliation, and target-version acceptance foundations are complete; this ticket does not depend on the other architecture tickets.
- No external blocker for mocked development. Coordinate overlapping payment-model and test edits at integration without making them artificial blockers.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown and requested triage.
Ready for an agent: the workflow, preservation constraints, and verification
criteria are specified; there are no unmet ticket or external blockers for
mocked development. Claim the work and update its existing work branch from the latest
reviewed main before implementation. Use a separate worktree for concurrent work.

## Verification evidence

Not started. This ticket describes a behavior-preserving refactor opportunity, not a confirmed payment defect.

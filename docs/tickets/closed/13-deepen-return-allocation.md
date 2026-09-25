# 13 — Deepen Return allocation

**Work branch:** `codex/13-deepen-return-allocation`

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

Preserve the complete manager return workflow—from choosing original payment allocations through refund reservation, reconciliation, and return checkout—while concentrating quantities, refundable balances, reservation consistency, and original tender rules in one Return allocation module. A change to those rules should have one owner across source discovery, reservation, and settlement.

## Acceptance criteria

- [x] Source discovery, refund reservation, and return settlement share ownership of the applicable return invariants. Callers no longer assemble the repeated original-sale locking and quantity-validation protocol themselves; source discovery remains advisory and reservation performs authoritative checks.
- [x] Preserve the distinct reservation and checkout transaction lifetimes. Persist the reservation and dispatch claim before the external mutation, and exercise the production locking protocol in concurrent database tests.
- [x] Full and partial returns preserve matching company, currency, original payment, return contents, quantities, and totals. Repeated or concurrent allocations cannot exceed the original payment balance or original sale quantities.
- [x] Pending, dispatching, unresolved, and verified refunds retain their reservations; failed refunds release them. Completed allocations survive another allocation's failure, and interrupted mutations are reconciled without replay.
- [x] Mixed-tender and cash-only partial returns remain limited to the original tender balances. Positive balancing tender cannot conceal an excessive refund, and an unverified Revolut allocation cannot complete a return.
- [x] Preserve existing behavior tests for repeated partial refunds, multiple originals, quantity conservation, mixed tender, partial failure, duplicate submission, competing reservations, and stale results. Extend tests only for uncovered behavior, using real local database transactions and mocked provider calls.
- [x] Demonstrate the complete path from allocation selection to verified return settlement, plus one competing-reservation rejection. Record the focused test results and explain any required checks not run.
- [x] Record which caller-owned rules moved behind the module's seam and how that improved locality and leverage. Retain the existing external adapter seam and current browser-facing behavior; keep dispatch implementation outside the return-invariant refactor.

## Blocked by

- None. The partial-refund and target-version acceptance foundations are already complete; this ticket does not depend on either of the other architecture tickets.
- No external blocker for mocked development. Provider-contract clarification and live-terminal acceptance remain separate work.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown and requested triage.
Ready for an agent: the workflow, preservation constraints, and verification
criteria are specified; there are no unmet ticket or external blockers for
mocked development. Claim the work and update its existing work branch from the latest
reviewed main before implementation. Use a separate worktree for concurrent work.

## Verification evidence

The manager allocation picker, refund RPC, and POS return checkout now call
`ReturnAllocation` in `addons/pos_revolut/models/return_allocation.py`. It owns
original-sale identity and line checks, total and quantity conservation,
source eligibility and refundable balances, reservation consistency, and
return tender and verification checks. It also owns the shared original-sale
row lock used by reservation and checkout. Callers no longer repeat that
protocol. A rule change can be made in one module and exercised through the
same three public workflows; the provider adapter and browser contract remain
unchanged. Reservation still commits in a dedicated cursor before provider
dispatch, while checkout runs in the POS order transaction.

Focused checks on Odoo 19.0.20260908 with mocked provider responses:

- `./scripts/test-addon --test-tags /pos_revolut:TestRevolutRefund`: 26 passed,
  including source selection through verified mixed-tender settlement.
- `./scripts/test-addon --test-tags /pos_revolut:TestRevolutRefundConcurrency`:
  5 passed using independently committed database transactions, including a
  competing-reservation rejection and a surviving dispatch claim.
- A new duplicate-submit test reproduced an unchecked changed return total
  (1 expected failure), then passed after the replay validation fix.

- `./scripts/test-addon`: the full addon test container exited 0. The console
  session was interrupted while browser tests were running, so its final test
  count was not retained; the container completed successfully in the
  background. The disposable database and volume were then removed.
- `python3 -m compileall -q addons/pos_revolut/models
  addons/pos_revolut/tests/test_revolut_refund.py` and `git diff --check` passed.
  No Python static type checker is configured in this repository. The
  install/upgrade gate was not repeated because this refactor changes no model
  fields, security rules, or manifest entries.

This ticket describes a behavior-preserving refactor opportunity, not a
confirmed pre-existing payment defect.

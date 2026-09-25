# 13 — Deepen Return allocation

**Work branch:** `codex/13-deepen-return-allocation`

**State:** claimed

**Triage:** ready-for-agent

## What to build

Preserve the complete manager return workflow—from choosing original payment allocations through refund reservation, reconciliation, and return checkout—while concentrating quantities, refundable balances, reservation consistency, and original tender rules in one Return allocation module. A change to those rules should have one owner across source discovery, reservation, and settlement.

## Acceptance criteria

- [ ] Source discovery, refund reservation, and return settlement share ownership of the applicable return invariants. Callers no longer assemble the repeated original-sale locking and quantity-validation protocol themselves; source discovery remains advisory and reservation performs authoritative checks.
- [ ] Preserve the distinct reservation and checkout transaction lifetimes. Persist the reservation and dispatch claim before the external mutation, and exercise the production locking protocol in concurrent database tests.
- [ ] Full and partial returns preserve matching company, currency, original payment, return contents, quantities, and totals. Repeated or concurrent allocations cannot exceed the original payment balance or original sale quantities.
- [ ] Pending, dispatching, unresolved, and verified refunds retain their reservations; failed refunds release them. Completed allocations survive another allocation's failure, and interrupted mutations are reconciled without replay.
- [ ] Mixed-tender and cash-only partial returns remain limited to the original tender balances. Positive balancing tender cannot conceal an excessive refund, and an unverified Revolut allocation cannot complete a return.
- [ ] Preserve existing behavior tests for repeated partial refunds, multiple originals, quantity conservation, mixed tender, partial failure, duplicate submission, competing reservations, and stale results. Extend tests only for uncovered behavior, using real local database transactions and mocked provider calls.
- [ ] Demonstrate the complete path from allocation selection to verified return settlement, plus one competing-reservation rejection. Record the focused test results and explain any required checks not run.
- [ ] Record which caller-owned rules moved behind the module's seam and how that improved locality and leverage. Retain the existing external adapter seam and current browser-facing behavior; keep dispatch implementation outside the return-invariant refactor.

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

Not started. This ticket describes a behavior-preserving refactor opportunity, not a confirmed payment defect.

# 09 — Issue partial refunds across original payment allocations

**Work branch:** `codex/09-partial-allocated-refunds`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `feat/project-definition` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**Status:** blocked

**Category:** Blocked

## What to build

A manager selects original Revolut payments and refunds all or part of their remaining balances, including sales originally paid with mixed tender.

## Acceptance criteria

- [ ] Show eligible original Revolut payments and remaining refundable balances in the return workflow; require an explicit manager allocation when more than one source payment is eligible.
- [ ] Link each allocation to its original payment and create a separately persisted, idempotent refund operation. Enforce matching company/currency and requested return totals.
- [ ] Count completed, pending and uncertain refund reservations under a lock when checking available balance. Multiple partial or concurrent refunds must never exceed the original paid amount.
- [ ] Preserve completed allocations when another allocation fails or remains uncertain. Retry/reconcile only the affected operation; do not replay successful refunds or falsely finalize an incomplete return.
- [ ] Keep non-Revolut tender distinguishable; do not automatically refund a cash portion through Revolut or silently change the allocation.
- [ ] Tests cover repeated partial refunds, full remaining-balance refund, mixed tender, multiple originals, over-refund rejection, concurrent allocation, partial batch failure and recovery.
- [ ] Document allocation, remaining-balance calculations and recovery of partially completed returns.

## Blocked by

- 07 — Use Revolut with split tender and restaurant checkout
- 08 — Issue and reconcile a full Revolut refund

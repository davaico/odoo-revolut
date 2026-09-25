# 09 — Issue partial refunds across original payment allocations

**Work branch:** `codex/09-partial-allocated-refunds`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

A manager selects original Revolut payments and refunds all or part of their remaining balances, including sales originally paid with mixed tender.

## Acceptance criteria

- [x] Show eligible original Revolut payments and remaining refundable balances in the return workflow; require an explicit manager allocation when more than one source payment is eligible.
- [x] Link each allocation to its original payment and create a separately persisted, idempotent refund operation. Enforce matching company/currency and requested return totals.
- [x] Count completed, pending and uncertain refund reservations under a lock when checking available balance. Multiple partial or concurrent refunds must never exceed the original paid amount.
- [x] Preserve completed allocations when another allocation fails or remains uncertain. Retry/reconcile only the affected operation; do not replay successful refunds or falsely finalize an incomplete return.
- [x] Keep non-Revolut tender distinguishable; do not automatically refund a cash portion through Revolut or silently change the allocation.
- [x] Tests cover repeated partial refunds, full remaining-balance refund, mixed tender, multiple originals, over-refund rejection, concurrent allocation, partial batch failure and recovery.
- [x] Document allocation, remaining-balance calculations and recovery of partially completed returns.

## Blocked by

- 07 — Use Revolut with split tender and restaurant checkout
- 08 — Issue and reconcile a full Revolut refund

## Implementation

The manager's POS allocation dialog lists each verified original Revolut
payment, its references and remaining balance. A manager confirms the selected
source and amount before dispatch. Each return payment line has its own
immutable refund operation, original-payment link and idempotency key. The
server locks the original sale and source payment, then counts completed,
pending and uncertain reservations before accepting an allocation. Completed
and active returns also reserve original product quantities.

Settlement validates the full return total, every original tender allocation,
and each Revolut refund's verified completion. A cash-only partial return of a
mixed-tender sale is permitted within the original cash share. A failed
allocation can be removed and replaced with a new payment line; completed
allocations remain linked and are not replayed. Pending and uncertain
allocations remain reserved and require reconciliation.

See [manager workflow](../../installation.md#partial-and-allocated-revolut-returns-pos-manager)
and [refund provider contract](../../revolut-refund-contract-2026-09-23.md).

## Review

Reviewed against the reviewed integration baseline `9497ce7`. The Standards
axis found no hard violations and one minor duplicate source-ID parse, which
was removed. The Spec axis found two conservation gaps: positive balancing
tender and cumulative original-line quantities. Both were corrected and
covered by regression tests. The re-audit found no remaining blocking spec
gap. A source list can show a monetary balance for a return with exhausted
product quantity; the authoritative dispatch check rejects that request.

## Verification

On pinned Odoo Community `19.0.20260908`, the final
`./scripts/test-addon --verify-install-upgrade` passed **125 addon tests on
clean install**, **125 on upgrade**, and **7 Restaurant tests**, with zero
failures or errors. Browser tours exercised the allocation dialog, completed
refund, failed refund and lost-response recovery. Focused model tests exercised
repeated partial refunds, remaining-balance exhaustion, mixed tender,
multiple original payments, failed allocation replacement, positive-tender
rejection, and cumulative returned quantities. An independently committed
transaction test exercised concurrent partial allocations.

`python3 -m unittest discover -s tests -v` passed all 14 deployment tests.
Python compilation, JavaScript syntax checks, XML parsing and `git diff --check`
passed. No static typechecker is configured. All Merchant API calls were
mocked; no real terminal or Merchant API request was made. Upgrade the addon
to `19.0.1.7.0`; no new credentials or credential rotation are required.

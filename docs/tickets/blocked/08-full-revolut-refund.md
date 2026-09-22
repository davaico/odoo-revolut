# 08 — Issue and reconcile a full Revolut refund

**Work branch:** `codex/08-full-revolut-refund`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**Status:** blocked

**Category:** Blocked

## What to build

A POS manager returns a sale originally paid by one Revolut payment, with a linked refund that completes only after Revolut confirms it.

## Acceptance criteria

- [ ] Use the normal Odoo return flow and enforce POS-manager authority on the server. Reject unrelated originals, cross-company references and unverified source payments.
- [ ] Confirm the original Revolut order is eligible for refund. Persist an operation linked to the original payment and return, with immutable amount/currency and a stable idempotency key before dispatch.
- [ ] Lock and reserve the refundable amount, including pending/uncertain operations. Repeated submissions reuse the same operation; never create a new key to bypass uncertainty.
- [ ] Save the returned refund-order ID and original relationship. Acceptance alone remains pending; foreground and background reconciliation determine verified completion or failure.
- [ ] Only a completed refund can complete its Revolut return payment line. Expose pending/failed/uncertain refunds and references to managers, including after reload, and do not silently substitute cash or another refund method.
- [ ] Reuse the durable dispatch/recovery conventions and documented provider idempotency semantics; retain uncertainty where safe replay cannot be established.
- [ ] Mocked model/browser tests cover full refund, duplicate submit, unauthorized user, failed refund, lost response, reload, late completion and simultaneous refund requests. Document the manager workflow.

## Blocked by

- 05 — Recover payments after interruption or late success

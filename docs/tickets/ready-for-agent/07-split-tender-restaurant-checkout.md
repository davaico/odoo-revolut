# 07 — Use Revolut with split tender and restaurant checkout

**Work branch:** `codex/07-split-tender-restaurant-checkout`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-agent

## What to build

Retail and restaurant cashiers pay part of an order using Revolut and settle the remainder through normal Odoo checkout without misapplying payments.

## Acceptance criteria

- [ ] Send the selected payment-line amount, not the entire order amount. A verified partial payment leaves the order open until all required tender is paid; completion remains automatic only when fully paid.
- [ ] Support restaurant dine-in/takeaway context through optional integration, preserving installation without restaurant modules. Use the documented provisional terminal contract until ticket 02 confirms live acceptance; do not claim live retail fulfilment compatibility before then.
- [ ] Preserve payment association across restaurant table changes and checkout navigation. Prevent order edits, merges/transfers or copied payment lines from silently assigning an active or settled payment to unrelated financial content.
- [ ] Keep operation locking and recovery correct with multiple payment lines and configured terminals. Uncertain Revolut payments cannot be bypassed by settling the same exposure through another tender.
- [ ] Tests cover cash plus Revolut, multiple Revolut lines, partially paid orders, dine-in/takeaway, reload, table changes and financial edits. Verify amount/currency/reference matching for every line.
- [ ] Document split-tender and restaurant behavior, including any guarded operation that requires reconciliation rather than automatic continuation.

## Blocked by

- 05 — Recover payments after interruption or late success

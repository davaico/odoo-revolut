# 07 — Use Revolut with split tender and restaurant checkout

**Work branch:** `codex/07-split-tender-restaurant-checkout`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

Retail and restaurant cashiers pay part of an order using Revolut and settle the remainder through normal Odoo checkout without misapplying payments.

## Acceptance criteria

- [x] Send the selected payment-line amount, not the entire order amount. A verified partial payment leaves the order open until all required tender is paid; completion remains automatic only when fully paid.
- [x] Support restaurant dine-in/takeaway context through optional integration, preserving installation without restaurant modules. Use the documented provisional terminal contract until ticket 02 confirms live acceptance; do not claim live retail fulfilment compatibility before then.
- [x] Preserve payment association across restaurant table changes and checkout navigation. Prevent order edits, merges/transfers or copied payment lines from silently assigning an active or settled payment to unrelated financial content.
- [x] Keep operation locking and recovery correct with multiple payment lines and configured terminals. Uncertain Revolut payments cannot be bypassed by settling the same exposure through another tender.
- [x] Tests cover cash plus Revolut, multiple Revolut lines, partially paid orders, dine-in/takeaway, reload, table changes and financial edits. Verify amount/currency/reference matching for every line.
- [x] Document split-tender and restaurant behavior, including any guarded operation that requires reconciliation rather than automatic continuation.

## Blocked by

- 05 — Recover payments after interruption or late success

## Verification evidence

Implemented on 2026-09-23 from reviewed `main` baseline `eace2b8`, which
includes closed blocker 05. The agreed test seams were POS payment-method RPCs,
POS checkout/browser behavior and `pos.order` submission. Cash plus Revolut
sent only the 4.34 remaining line amount after 8.00 cash, while two verified
Revolut allocations retained distinct order, intent and payment references.
A verified partial draft stayed open and completed only after normal tender
covered the remainder. Dine-in and takeaway tests checked the provisional
`eat_in` and `take_away` order payloads; an unknown Restaurant context,
with or without a table, was rejected before dispatch. A Restaurant draft kept
its verified payment after changing tables without changing order UUID. Browser
coverage rejected merge and transfer after a settled Revolut line. Server
tests rejected edited financial content, copied lines and references,
per-line amount/currency/reference mismatches, and a failed line counted as paid.
A two-terminal test blocked the second line while the first was pending, then
dispatched the second line to its own terminal after verification. The existing
suite covers reload and reconciliation.

Verification commands:

```bash
./scripts/test-addon --verify-install-upgrade
./scripts/test-restart-recovery
python3 -m compileall -q addons/pos_revolut addons/pos_revolut_restaurant
node --check addons/pos_revolut/static/src/app/payment_revolut.js
node --check addons/pos_revolut/static/tests/tours/pos_revolut_acceptance.js
node --check addons/pos_revolut_restaurant/static/src/app/restaurant_revolut.js
git diff --check
```

The Odoo run reported **92 addon tests on clean install**, **92 on upgrade**,
and **7 Restaurant tests**, with zero failures or errors. An earlier
post-review full run hit a browser harness timeout in the existing
foreground-timeout tour; that tour passed alone and the repeated full run
passed. The separate-process check reported `RESTART_SEED_OK` and `RESTART_RECOVERY_OK`. Syntax checks
passed. No static typechecker is configured; Python compilation is not type
checking. Merchant requests were mocked; no live terminal or API call was made.
The Restaurant bridge is a separate, auto-installed addon solely so it can
depend on optional `pos_restaurant` while the base addon remains installable
without Restaurant. Upgrade the addon to `19.0.1.5.0` for the new locking
model. No credential rotation is required. Retail fulfilment and live provider acceptance
remain gated by ticket 02.

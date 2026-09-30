# 27 — Enforce the authorized order balance before terminal dispatch

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/27-enforce-authorized-terminal-allocation`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-27`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Remediation

## What to build

Cashiers can complete ordinary and split payments with explicit authorized tips, while crafted or concurrent requests cannot send an amount beyond the server-authorized remaining allocation to Revolut.

## Source and scope

Five confirmed source findings describe the same pre-dispatch amount-authority failure. POS role/company/session and positive-amount checks currently allow an independently chosen amount to reach Merchant order/intent creation. The existing snapshot equality and verified settlement controls apply later. Cardholder approval is still required; no silent-capture or unpaid-order settlement bypass was established.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 2: `csf_0b4fc44391fd910988783f68` — Terminal charges are not bounded by the authoritative order balance
- Scan input 8: `csf_d02ef7b60758186e1139e6f3` — A POS user can push an arbitrary unbound amount to the Revolut terminal
- Scan input 19: `csf_409b8b3f2ce2176b4e36c4bf` — A cashier can send an unauthorised amount to the payment terminal
- Scan input 21: `csf_e23e164c7c609f0b17ad9500` — Terminal charges are not capped to the cart's remaining balance
- Scan input 29: `csf_56ed0a276c5e664ceff5ac60` — A cashier can send an off-cart amount to the payment terminal

## Acceptance criteria

- [ ] Implement ticket 26's selected authority model end to end through persisted authorization/reservation, server validation, POS behavior and final settlement. Reject missing, forged, stale or mismatched authority before provider financial mutations.
- [ ] Derive the chargeable order amount from server-authorized Odoo state, not a browser total or independently supplied snapshot. Enforce binding to company, session/configuration, currency, order/cart version and payment allocation.
- [ ] Under an atomic shared allocation boundary, cap a new charge plus relevant verified and unresolved/in-flight allocations to the authorized remaining balance. Cover concurrent requests, different payment-line UUIDs, sequential verified payments and safe retry; no unchecked second allocation may slip through.
- [ ] Keep tips explicit according to the approved design. Preserve ordinary no-tip checkout, supported tipping and authorized pricing; reject disguising arbitrary excess as a tip or counting a tip twice.
- [ ] Preserve cash/Revolut splits, multiple Revolut lines, partial-payment order state and Restaurant checkout. A rejected pre-dispatch amount has an actionable POS recovery path; it must not strand an untouched line or imply retry safety for an existing uncertain charge.
- [ ] Reload, lost responses, authorization expiry, process restart and concurrent cashiers retain the original financial operation and immutable provider references. Historical verified/uncertain operations follow the approved compatibility path without invented evidence or automatic replay.
- [ ] Add bounded pinned-Odoo direct-RPC and concurrency regressions demonstrating rejection before financial POSTs, plus legitimate split/tip/rounding/tax/discount controls. Exercise native POS checkout/recovery and assert operation/reservation/provider mutation counts.
- [ ] Run affected payment/refund/settlement/lifecycle and install/upgrade checks appropriate to changed persistence, then independent Standards/Spec review and explicit security-fix verification for every linked source claim. Record commands, revision and remaining human/device checks; all provider calls are mocked.
- [ ] Document configuration/migration needs and cashier behavior. Keep the change scoped to amount authorization; if ticket 26's selected design cannot fit one reviewed slice, stop at a concrete revised breakdown rather than landing a partial financial guard.

## Blocked by

26 — Decide server-authorized cart and tip behavior.

## External prerequisites

None for local mocked implementation once declared design blockers are resolved. Deployment and live acceptance remain separate.

## Out of scope

No automatic refund of prior overcharges, real terminal experiment, unrelated receipt feature, or permission/credential overhaul.

## Release and integration relationship

The reviewed fix and combined regression evidence must be considered before ticket 12's final release acceptance. This ticket does not modify ticket 12.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

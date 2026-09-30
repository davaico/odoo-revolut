# 26 — Decide server-authorized cart and tip behavior

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/26-decide-order-and-tip-authorization`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-26`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Design decision

## What to build

A reviewed, implementable contract for authorizing the order balance and explicit tips before Revolut dispatch, compatible with native Odoo checkout. This resolves the remaining design questions for ticket 27; it does not ship a speculative payment rewrite.

## Source and scope

The owner requires the actual order charge to respect a server-verified cart balance and any extra to be an explicit tip. The current adapter accepts the charge amount separately from its browser-owned snapshot. Later settlement checks cannot undo an already approved charge. Native tip timing, editable prices and the absence of an authoritative persisted draft at dispatch need inspection before choosing the implementation.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 2: `csf_0b4fc44391fd910988783f68` — Terminal charges are not bounded by the authoritative order balance
- Scan input 8: `csf_d02ef7b60758186e1139e6f3` — A POS user can push an arbitrary unbound amount to the Revolut terminal
- Scan input 19: `csf_409b8b3f2ce2176b4e36c4bf` — A cashier can send an unauthorised amount to the payment terminal
- Scan input 21: `csf_e23e164c7c609f0b17ad9500` — Terminal charges are not capped to the cart's remaining balance
- Scan input 29: `csf_56ed0a276c5e664ceff5ac60` — A cashier can send an off-cart amount to the payment terminal

## Acceptance criteria

- [ ] Inspect the pinned Odoo 19 checkout, draft persistence, pricing/tax/discount and tip flows. Record which price overrides are legitimate under existing permissions and where authoritative amount calculation can occur; do not silently prohibit ordinary cashier pricing or trust a browser total.
- [ ] Choose one repository-native authorization design after comparing reuse of persisted Odoo draft orders with a server-authorized quote/version where necessary. Explain what makes it authoritative; merely signing unchecked browser data is insufficient.
- [ ] Specify the authorized amount and remaining-balance calculation across cash/Revolut split tender, multiple Revolut lines, verified charges, in-flight or uncertain reservations, safely failed attempts and concurrent starts. Identify the atomic reservation boundary.
- [ ] Establish how an explicit tip is represented and authorized, whether existing tips are included in Odoo's order total, and what happens before and after capture. Prevent double counting and arbitrary excess relabeling. Do not invent provider-side post-payment tip support; unresolved product/provider behavior is an explicit owner decision.
- [ ] Define cart-version binding, normal edits before financial exposure, reload/shared-cashier recovery, Restaurant context, session closure and historical operations. Unknown financial outcomes must not be released or reassigned because an authorization expires.
- [ ] Produce a concrete state/behavior table and implementation acceptance matrix for ticket 27, including rejected direct RPCs and legitimate order/tip controls. Use an isolated mocked prototype only if a design question needs execution, and retain the result as evidence.
- [ ] Record the selected decision and any necessary owner answer in project decision documentation. Ticket 27 becomes actionable only when no material authorization/tip decision remains. No production implementation, live financial call or deployment is part of this ticket.

## Blocked by

None (can start immediately).

## External prerequisites

Local source research can start immediately. If a material tip/product decision cannot be derived from evidence, record the precise owner question; ticket 27 stays blocked.

## Out of scope

No broad session-permission redesign, credential redesign, new provider tipping capability or generalized POS repricing project.

## Release and integration relationship

This is a design prerequisite for ticket 27, not proof of a remediated vulnerability.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.



# 26 — Decide server-authorized cart and tip behavior

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/26-decide-order-and-tip-authorization`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-26`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** closed

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

- [x] Inspect the pinned Odoo 19 checkout, draft persistence, pricing/tax/discount and tip flows. Record which price overrides are legitimate under existing permissions and where authoritative amount calculation can occur; do not silently prohibit ordinary cashier pricing or trust a browser total.
- [x] Choose one repository-native authorization design after comparing reuse of persisted Odoo draft orders with a server-authorized quote/version where necessary. Explain what makes it authoritative; merely signing unchecked browser data is insufficient.
- [x] Specify the authorized amount and remaining-balance calculation across cash/Revolut split tender, multiple Revolut lines, verified charges, in-flight or uncertain reservations, safely failed attempts and concurrent starts. Identify the atomic reservation boundary.
- [x] Establish how an explicit tip is represented and authorized, whether existing tips are included in Odoo's order total, and what happens before and after capture. Prevent double counting and arbitrary excess relabeling. Do not invent provider-side post-payment tip support; unresolved product/provider behavior is an explicit owner decision.
- [x] Define cart-version binding, normal edits before financial exposure, reload/shared-cashier recovery, Restaurant context, session closure and historical operations. Unknown financial outcomes must not be released or reassigned because an authorization expires.
- [x] Produce a concrete state/behavior table and implementation acceptance matrix for ticket 27, including rejected direct RPCs and legitimate order/tip controls. Use an isolated mocked prototype only if a design question needs execution, and retain the result as evidence.
- [x] Record the selected decision and any necessary owner answer in project decision documentation. Ticket 27 becomes actionable only when no material authorization/tip decision remains. No production implementation, live financial call or deployment is part of this ticket.

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

## Decision and owner answers — 2026-09-30

Selected [ADR 0001](../../adr/0001-authorize-revolut-cart-before-dispatch.md) and [the implementation contract](../../revolut-cart-authorization.md): validated persisted Odoo draft, immutable base-cart authorization and shared atomic tender ledger; customer selects the required tip on Revolut Terminal before card payment; verify captured gross and explicit tip separately through authenticated `payments_report` before native settlement. Missing/late evidence preserves exposure and recovery without replay.

The owner clarified that terminal tips were the original intention, superseding the initial Odoo-pre-entry-only assumption. Customers may choose optional terminal tips within provider limits; the cashier 25%/manager rule applies only to Odoo-entered tips. The owner approved awaiting report details when needed. Restricted manual prices require authenticated Odoo POS manager approval, including POS HR advanced-employee overrides; unrestricted cashier pricing is preserved. Post-payment Restaurant adjustment remains distinct and unsupported.

No material owner decision remains. Ticket 27 can start once this reviewed closure is integrated. The contract includes direct-RPC/ORM controls, native pricing/tax/discount parity, cash rounding, concurrent reservations, per-payment tip projections, gross receipts/refunds, legacy/session recovery, state/behavior tables and implementation acceptance cases. No production implementation or remediation claim is made by ticket 26. Actual target-terminal tip/report behavior and latency remain release acceptance, not invented API evidence.

## Verification evidence

- Reviewed local main: `4adf1ab9f45605dfc023b7544189c78d5d29a057`; starting assigned branch `080f3fb0a72df80fa772bb72b31eeba4fdc7d965` already contains main with an identical tree. Fast-forward update checked before claiming.
- Pinned source: local Odoo package `19.0.20260908`, exact image/source hashes and source seams recorded in the contract. Full official Merchant OpenAPI YAML was inspected; report-only tip fields are distinguished from ordinary payment retrieval.
- No prototype was needed to select the documented draft/report boundaries. This ticket creates documentation only; TDD/typechecking have no implementation seam here. The ticket 27 matrix defines the public RPC/ORM/checkout and independent-transaction seams to exercise.
- Existing Node payment-state suite passed (one test file); all 29 deployment-tooling unit tests passed. Full pinned-Odoo suite and independent Standards/Spec review results are recorded in the final verification update below.
- No real Merchant request, terminal interaction, provider message, deployment or production mutation occurred. Public documentation downloads and local source/test inspection only.

### Final verification update

[Verification and review record](../../testing/ticket-26-cart-and-terminal-tip-design.md): the guarded fresh-install retail suite completed with **265 tests, 0 failures, 0 errors**; 29 deployment unit tests and the Node payment-state test file passed. Restaurant-only classes skip in this retail phase. No upgrade/Restaurant-phase or new design implementation was claimed for these documentation-only changes.

Independent final review at `ece85a85a8f61839dd84f65746a7e88058fbd72d`: **Standards 0, Spec 0 outstanding findings**. Initial Spec findings about reopening rounded cash capacity and exact taxed-tip representation were corrected and re-reviewed. Local Markdown links/whitespace pass, the ready-folder marker is preserved, and the self-evaluation records remaining release-validation limits.

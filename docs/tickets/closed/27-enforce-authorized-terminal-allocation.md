# 27 — Enforce the authorized order balance before terminal dispatch

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/27-enforce-authorized-terminal-allocation`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-27`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** closed

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

- [x] Implement ticket 26's selected authority model end to end through persisted authorization/reservation, server validation, POS behavior and final settlement. Reject missing, forged, stale or mismatched authority before provider financial mutations.
- [x] Derive the chargeable order amount from server-authorized Odoo state, not a browser total or independently supplied snapshot. Enforce binding to company, session/configuration, currency, order/cart version and payment allocation.
- [x] Under an atomic shared allocation boundary, cap a new charge plus relevant verified and unresolved/in-flight allocations to the authorized remaining balance. Cover concurrent requests, different payment-line UUIDs, sequential verified payments and safe retry; no unchecked second allocation may slip through.
- [x] Keep tips explicit according to the approved design. Preserve ordinary no-tip checkout, supported tipping and authorized pricing; reject disguising arbitrary excess as a tip or counting a tip twice.
- [x] Preserve cash/Revolut splits, multiple Revolut lines, partial-payment order state and Restaurant checkout. A rejected pre-dispatch amount has an actionable POS recovery path; it must not strand an untouched line or imply retry safety for an existing uncertain charge.
- [x] Reload, lost responses, authorization expiry, process restart and concurrent cashiers retain the original financial operation and immutable provider references. Historical verified/uncertain operations follow the approved compatibility path without invented evidence or automatic replay.
- [x] Add bounded pinned-Odoo direct-RPC and concurrency regressions demonstrating rejection before financial POSTs, plus legitimate split/tip/rounding/tax/discount controls. Exercise native POS checkout/recovery and assert operation/reservation/provider mutation counts.
- [x] Run affected payment/refund/settlement/lifecycle and install/upgrade checks appropriate to changed persistence, then independent Standards/Spec review and explicit security-fix verification for every linked source claim. Record commands, revision and remaining human/device checks; all provider calls are mocked.
- [x] Document configuration/migration needs and cashier behavior. Keep the change scoped to amount authorization; if ticket 26's selected design cannot fit one reviewed slice, stop at a concrete revised breakdown rather than landing a partial financial guard.

## Blocked by

26 — Decide server-authorized cart and tip behavior (closed; reviewed design integrated into the assigned branch at `719bae93390c3a326673af2d0e6b89aea0a84b65`).

The owner reauthorized complete implementation on 2026-10-01. The [breakdown](../../ticket-27-implementation-breakdown.md) guides development within this ticket; it is not an additional approval gate. The accepted design is unchanged.

## External prerequisites

None for local mocked implementation once declared design blockers are resolved. Deployment and live acceptance remain separate.

## Out of scope

No automatic refund of prior overcharges, real terminal experiment, unrelated receipt feature, or permission/credential overhaul.

## Release and integration relationship

The reviewed fix and combined regression evidence must be considered before ticket 12's final release acceptance. This ticket does not modify ticket 12.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

## Ticket 26 implementation contract — 2026-09-30

Use [ADR 0001](../../adr/0001-authorize-revolut-cart-before-dispatch.md) and [the selected cart/terminal-tip contract](../../revolut-cart-authorization.md). The owner requires the customer's Revolut terminal tip popup, not mandatory Odoo tip pre-entry. Authorize the frozen base cart and reserve each base allocation; retrieve final payment and authenticated `payments_report` evidence (explicit tip, including zero), then project the tip and gross tender into Odoo once. Missing/late evidence remains exposed with recovery and no new charge. Customer terminal tips are permitted within provider limits; the 25%/manager rule applies only to cashier-entered Odoo tips. Preserve gross receipts and explicit base/tip full/partial refund accounting.

The design's tables/matrix are part of this ticket's acceptance criteria. No invented tip field on payment retrieval, amount-difference inference, duplicate tip, browser-only authority or partial financial guard satisfies this ticket. Target-device tip/report timing and currency identity evidence remain release acceptance; local tests use documented fixtures and guarded mocked HTTP. If the complete native-pricing/tip/receipt/refund slice cannot fit this ticket, follow its existing concrete-breakdown requirement before implementing.

## Implementation assessment — 2026-10-01

This is the historical planning-only assessment, superseded by the completed implementation and verification below.

The assigned branch was fast-forwarded from `080f3fb0a72df80fa772bb72b31eeba4fdc7d965` to reviewed main `719bae93390c3a326673af2d0e6b89aea0a84b65`, including ticket 26's closure and required terminal-tip contract. Independent read-only pricing and tip/receipt/refund assessments confirmed that current snapshot checks establish no canonical pricing authority, remaining-base ledger or authenticated report evidence. Capture verification, native snapshot/tender equality, receipts and refund ceilings all currently use the requested amount; the approved base/gross/tip flow needs coordinated changes to each.

Following this ticket's explicit stop condition, record [P1–P6 development dependencies, public seams, acceptance gates and source-claim verification requirements](../../ticket-27-implementation-breakdown.md) before runtime implementation. The proposal introduces no partial financial guard and is awaiting triage of its sequencing. Planning labels are not new numbered tickets; publish those only after breakdown triage. Keep this ticket open as the complete remediation acceptance gate. All five linked source claims remain open, and none of the acceptance checkboxes is satisfied by this documentation change. Terminal-selected tips and the existing approved decisions remain required.

The pinned temporary Odoo source extraction is absent. Docker image inspection after permitted escalation failed because `/var/run/docker.sock` is unavailable; fresh pinned-Odoo extraction/verification could not run here. This test-environment limitation is separate from the implementation scope assessment. Local checks and independent Standards/Spec review are recorded in the breakdown; they validate this proposal only, not payment behavior. Ticket 12 and deployment/live acceptance remain unchanged.

## Implementation resumed — 2026-10-01

Owner explicitly requested continuing implementation with Docker started. Ticket is claimed on its assigned branch. P1–P6 are internal milestones for one complete candidate; no newly numbered tickets or further scope approval are required. Previous documentation-only evidence remains historical, not remediation evidence.

## Completed and verified — 2026-10-01

The complete coordinated implementation is committed on the assigned branch. Final runtime `88c88a5da9636d644bd66048ce654efa31fd53c8` implements native canonical cart pricing and exact manager approval, immutable authority and atomic remaining-base reservations, authenticated explicit terminal-tip reports, once-only native gross projection, full/partial base-and-tip refunds, receipts and historical compatibility. No isolated cap-only guard was landed as the completed fix.

[Final evidence](../../testing/ticket-27-cart-authority.md) records the exact revisions, addon trees, delivered archive hash, commands, failed controls and repaired regressions. The final combined runner exited 0 with 340 tests on fresh installation, 340 after module upgrade and nine Restaurant checks, all with zero failures/errors. Both exact-archive retail and migration scenarios exited 0. Additional controls cover actual historical upgrade, three-process restart, nine independent-cursor races, posted gross sale/credit-note accounting, native checkout/recovery and 73 JavaScript payment-state cases. Configuration, migration and cashier instructions are in [installation](../../installation.md).

Independent Standards and Spec reviews have no unresolved actionable findings. Explicit read-only security-fix verification assessed all five source IDs in this ticket as **fixed** against the final committed runtime; each verdict and its original source/control/sink boundary appears in the evidence table.

Ticket 27 is closed for local implementation and mocked verification. The work branch awaits shared integration. Target-device popup/report identity, units, latency and physical release acceptance remain ticket 12's separate gate. Ticket 12 and the live POS were not edited, exercised or deployed to.

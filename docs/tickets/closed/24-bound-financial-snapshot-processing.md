# 24 — Bound financial snapshot processing before numeric expansion

**Work branch:** `codex/24-bound-financial-snapshot-processing`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-24`

**State:** closed

**Triage:** ready-for-agent

Create or update the assigned branch from reviewed main before implementation, preserving existing work. Use an isolated worktree when another task is changing the repository. A branch name is not evidence that a branch has been created.

## What to build

Payment and refund cart snapshots must have a predictable, bounded server processing cost. Reject unsupported numeric representations and oversized carts before expensive conversion or accumulation, give the operator an actionable error, and preserve legitimate payment, return, recovery and settlement comparisons.

This is one complete remediation slice: establish safe pinned-runtime evidence, implement shared server bounds and appropriate RPC exposure, preserve POS recovery behavior, add regression coverage, and record reviewed verification. It needs no separate architecture spec or standalone refactoring ticket.

## Source and triage evidence

The owner supplied the Codex Security report **Small cart values can exhaust Odoo payment workers** on 2026-09-30. The report does not supply a finding ID or the original scanned revision; do not invent either. The source report remains in the originating conversation attachment.

The report describes authenticated caller control over cart line count and numeric quantities, unit prices and discounts. Finite scientific-notation values are expanded to fixed-point strings, then retained across an unrestricted line list. The supported payment-start path reaches this work before creating the payment operation or contacting the provider. A directly callable normalization utility may broaden exposure.

The report states that an extracted, unchanged method running in a disposable harness with 256 MiB memory and a five-second CPU limit expanded a 347-byte input containing three lines into 600355 output bytes. Ordinary prices normalized and non-finite inputs were rejected. These are supplied report results, not a reproduction performed during triage. The report expressly did not exercise Odoo RPC, exhaust a worker, contact the Merchant API or operate a terminal.

Static triage at revision `ffae23dcfcf71dc61293404e3c7183b3fe70e750`, addon version `19.0.1.7.6`, found the reported normalization behavior still present. The supported payment route validates the POS role, company, open session, currency, identifiers, configuration and server credential, but does not bound snapshot expansion. Return allocation and final cart comparison share normalization and must retain equivalent protection.

The full worker-exhaustion claim has verdict **needs_review**, confidence **medium**, and rank **1 in the needs_review queue**. This security verdict is separate from the ticket's implementation-readiness label. The resource-amplification path is supported by source evidence; deployed outage severity, effective runtime controls and direct RPC access by non-POS authenticated users remain proof gaps. No applicable SECURITY.md was found; project instructions and the shipped payment workflow establish browser cart input as lower-trust than the server. No unauthenticated exposure, payment-verification bypass, stolen funds or observed outage is asserted.

## Acceptance criteria

- [x] Establish bounded red/green evidence in the pinned Odoo runtime through the supported payment-start entry point under ordinary POS cashier permissions, with a valid configured open session and all provider calls mocked or blocked. Establish the direct helper's actual RPC exposure for the relevant roles separately. Use small, capped demonstrations and deterministic assertions; do not attempt an actual worker outage. Record which original claims are demonstrated, constrained or still unverified.
- [x] Define concrete, documented limits for numeric input length, supported precision/exponents and quantity, unit-price and discount ranges, plus cart line count and aggregate normalized snapshot size. Justify limits against supported Odoo sale/return behavior and existing fixtures, including fractional quantities and negative return quantities. Do not silently round, clamp or truncate values to make them pass. If a proposed limit excludes a required workflow, surface that compatibility decision before enforcing it.
- [x] Enforce cheap shape, input-length and line-count checks before expensive parsing or iteration. Validate the numeric representation and prospective fixed-point size before normalization/formatting can allocate expanded strings. Enforce a bounded aggregate budget before appending or serializing excessive output, including retained snapshot fields and collections. Checking only after a large result has been built does not satisfy this criterion.
- [x] Keep the bounds in the shared server normalization boundary used by payment starts, return discovery/reservation and final order comparisons. Make the computation-only helper private if direct RPC exposure is unnecessary, updating all callers; if public exposure must remain, document its supported purpose and enforce appropriate authorization. Neither authentication, helper privacy nor deployment worker limits substitutes for resource bounds on supported calls.
- [x] A newly rejected invalid snapshot must cause no provider dispatch and leave no new payment/refund operation, reservation or coordination state that permanently blocks a line. Show a clear, actionable POS error and verify that a demonstrably undispatched line can be corrected or removed safely. Preserve existing attempts, reservations, references and uncertain-start guards; an exception or empty lookup alone must never authorize a financial retry or discard evidence of a possibly dispatched request.
- [x] Preserve canonical comparison behavior for valid carts across retail, Restaurant, split tender, full/partial refunds, reload/recovery and final settlement. Verify representative persisted snapshots remain comparable after upgrade; keep payment verification, original-return allocation and duplicate-prevention invariants unchanged. Document and test any necessary compatibility handling rather than silently rewriting financial evidence.
- [x] Add deterministic boundary regressions for oversized positive and negative exponents, long numeric text, excessive precision, non-finite and malformed values, each affected numeric field, excessive line counts, aggregate budget overflow, and values just inside/outside the chosen limits. Demonstrate rejection before dangerous expansion, and before traversing excessive line lists, without allocating an exhausting test payload. Include valid controls for normal prices, supported scientific notation if retained, discounts and fractional/negative return quantities.
- [x] Exercise the public payment/refund paths and actual POS adapter error/recovery behavior with mocked provider I/O. Verify rejected requests make zero provider mutations, valid controls still complete one verified workflow, and lost-response/uncertain-attempt controls remain blocked appropriately. Use actual Odoo entrypoint evidence rather than relying solely on an extracted-method harness; use browser coverage where recovery behavior changes.
- [x] Record the exact reviewed revision, chosen limits, bounded reproduction and regression results, remaining deployment-impact limitations, and independent security fix verification. Run the affected payment, refund, settlement and lifecycle tests plus pinned install/upgrade and Restaurant acceptance for the combined correction. Update operator guidance for limit rejections. Keep secrets, sensitive payment data, live Merchant calls, destructive load testing and hosting changes out of this work.

## Blocked by

None for local validation and mocked implementation. Work from reviewed main with the completed security and architecture corrections present. Physical-terminal access and deployment-specific outage reproduction are not prerequisites.

Tickets 22 and 23 are not logical blockers. Coordinate any overlapping POS recovery changes during integration and verify the combined result instead of adding artificial dependency gates.

## Blocks

Ticket 12 release acceptance and closure. After this correction is integrated, update the final candidate's automated evidence to cover the bounds and affected workflows. Preserve previous dated acceptance evidence and all outstanding financial reconciliation and human checks; this ticket does not authorize staging changes or real financial operations.

## Scope boundaries

Remediate the supplied snapshot-processing finding as one unit. Do not expand this into a repository-wide security scan, arbitrary business-policy redesign, generic rate-limiting project, or deployment resource-tuning exercise. A demonstrated input-amplification regression and verified bounds are sufficient; actual service exhaustion is not required for closure.

## Owner approval — 2026-09-30

The owner approved this single-ticket scope, direct placement in the agent-ready folder, and the ticket index and ticket 12 dependency updates. The approval covers ticket publication; implementation, staging changes and financial operations are not performed by this documentation update.


## Verification evidence — 2026-09-30

Implemented and reviewed on `codex/24-bound-financial-snapshot-processing` in
an isolated worktree, preserving the owner's main-checkout changes.
The final implementation is `604962a41d74552a497f661baa66b45c8db72113`, based on
reviewed main `ffae23dcfcf71dc61293404e3c7183b3fe70e750`, addon `19.0.1.7.7`.
The [verification record](../../testing/ticket-24-financial-snapshot-bounds.md)
contains the precise bounds, capped pinned-Odoo cashier and role-dispatcher
red/green evidence, zero-dispatch rejection, native POS recovery, literal
persisted comparisons and the narrow native unset-discount compatibility rule.
Operator upgrade and correction guidance is in the
[installation guide](../../installation.md#financial-cart-limits-and-safe-correction).

Final mocked verification passed 234 fresh-install, 234 upgrade and eight
Restaurant tests; 154 affected payment/refund/settlement/mutation and native
checkout tests; 65 lifecycle and 29 deployment tests; and recovery across two
Odoo processes. Standards and Spec findings are zero. Fresh independent security
fix verification reports `fixed` for the reproduced resource boundary. Syntax
and whitespace checks passed; no typechecker or coverage claim is made.

All nine local criteria are complete. The worker-outage claim's deployment
impact remains unverified; generic unrelated cash relationship classification
remains proportional to native input with bounded temporary batches. No live
financial operation, destructive load test or hosting/staging change occurred.
Ticket 12 remains open for integration/combined-candidate acceptance and its
existing financial reconciliation and human checks. Ticket 22's local source
fix was in that initial base; ticket 23 was then separate. Previous dated evidence
is preserved.

## Integration follow-up — 2026-09-30

After ticket 23 merged into main through PR #29, PR #28 was updated from
main `fbab631`. Combined candidate `d64e962` preserves the previous ticket 24
head and main through a two-parent merge. The ticket-index conflict retains
both tickets' states, and addon `19.0.1.7.8` distinguishes the combined release
from their earlier shared version. The
[combined verification](../../testing/ticket-24-financial-snapshot-bounds.md#combined-candidate-after-ticket-23-integration--2026-09-30)
records retained resource bounds, recovery and processing behavior plus refreshed
acceptance. Ticket 24 stays closed locally; PR #28 is not merged by this work.

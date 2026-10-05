# 41 — Complete Revolut-initiated refunds through native Odoo returns

**Work branch:** `codex/41-complete-external-refund-returns`

**State:** closed

**Triage:** ready-for-agent

**Category:** feature

**Approved scope:** 2026-10-05. The owner confirmed manager product/quantity confirmation before stock changes, support for refunds without returned goods, and one complete workflow ticket. Partial-refund rounding remains ticket 40.

**What to build:** Staff can finish a refund already issued through Revolut from the same refund worklist used for Odoo refunds. They open its original sale, identify and confirm returned products and quantities, and create or associate the appropriate native Odoo return. The verified card refund pays its selected part of that return without issuing money again. After normal native validation, the return appears in Orders with traceable financial references, a POS sales receipt, configured stock effects and the applicable native accounting effects. An amount-only refund never establishes returned goods by itself.

**Blocked by:** None for local implementation and mocked verification. Closed ticket 37 supplies automatic discovery, exact original-payment matching, financial verification and capacity reservations. Coordinate with ticket 40's ongoing rounding correction; do not reimplement that correction or make it a prerequisite to starting this workflow. Final deployment and physical acceptance remain the existing release process; do not modify or close its parent ticket.

**Approved product decisions:** An authorized manager reviews product/quantity selection and validates the native return; discovery does not automatically finalize returns or change stock. Refunds with no returned goods have an explicit financial-only disposition, a reason and links to applicable separate native correction documents, without invented product returns or stock movements.

## Acceptance criteria

- [x] Both origins use the same refund worklist and understandable labels for original sale, native return, amount/currency, financial outcome and native completion. Retain Odoo versus external provenance; do not claim terminal versus portal origin without evidence.
- [x] The original sale is accessible with its purchase date, product lines, original amounts and tenders. Show native return links when one exists. Distinguish provider refund initiation time, when authenticated and available, from Odoo discovery/import and reconciliation times; missing provider time is labelled unavailable, never inferred from import time.
- [x] An authorized manager can start native completion from a matched external refund, select valid original product lines and remaining quantities, and review a native return draft. Preserve original pricing, taxes and existing access rules. Do not guess items from the refund amount, including full refunds of one card tender on a mixed-tender sale.
- [x] Permit safe association with a compatible existing draft or finalized native return where its evidence establishes the same original sale and refund allocation. Reject incompatible or ambiguous associations and any reuse of unrelated reimbursement rather than duplicating documents, quantities or money. Existing separate native work is a supported reconciliation case, not an automatic second return.
- [x] Consume the existing verified external refund as recorded card reimbursement on the native return. Creating, associating, saving, resuming, validating and reprinting this workflow send zero new refund/payment financial requests. Preserve the original financial record, provider references, provenance and amount; count its financial capacity once.
- [x] Support full and partial product returns, multiple original card tenders, multiple external refunds and mixed cash/card sales with exact allocations. Never represent an external card refund as reimbursement of the cash portion. Any additional refund not already issued is a separate explicit operation under existing authority and caps.
- [x] Pending, uncertain, failed and cancelled refunds remain explicit and cannot become verified negative card tenders by manager acknowledgement. Native completion requires authoritative successful financial evidence and exact tender totals. A pending refund may remain associated with a draft while preserving its reservation and preventing final validation.
- [x] Native validation creates the expected negative order/payment linkage, POS sales receipt and configured Odoo stock/accounting effects exactly once. Exercise actual stock moves and native accounting output for applicable products and invoiced originals. Services create no inventory movements; tracked products require valid lot/serial details. Closed original sessions and permitted current-session completion retain original financial provenance.
- [x] Record explicit base versus terminal-tip allocation when relevant to a product return; never infer it from gross refund amount. Unknown components remain protected with an actionable review outcome. Confirmed native allocation enables later valid refunds without erasing historical financial evidence or weakening source/component caps.
- [x] Provide an explicit no-products-returned disposition with reason, responsible manager and time, original-sale/refund links and references to any required native correction documents. It creates no returned quantities or inventory movements. Where a native accounting correction is required, create or associate the appropriate native document and verify its amount and original-sale relationship before marking that work complete; acknowledgement alone is insufficient. Document which supported cases require a correction and which do not.
- [x] Replace the acknowledgement-only completion path with verifiable native association or an explicit documented financial-only disposition. Preserve old acknowledgements as historical assertions; do not silently convert them to proven document links. Historical unlinked external refunds can enter the new workflow without repeating financial instructions.
- [x] Reloads, failed native validation, crashes, repeated clicks and concurrent managers preserve a recoverable draft/association and cannot double-apply a provider refund, return quantities, stock moves or accounting entries. Company/register restrictions hold on UI and server entry points.
- [x] Mock all Merchant calls. Verify public workflow and native finalization for full/partial, mixed/multiple tenders, existing-return association, pending-to-completed, failure, recovery/concurrency, historical migration, tips and tracked products. Assert zero financial POSTs for already-issued money and actual native stock/accounting results. Reuse the rounding policy delivered by ticket 40.
- [x] Document the staff workflow in plain terms, including refund origin, import versus transaction time, product confirmation, stock treatment, native documents, pending recovery and financial-only disposition. Provide a controlled acceptance scenario using an existing external refund without a replacement charge/refund.

## Out of scope

- Ticket 40's partial-refund rounding correction, discovery menu removal, ordinary payment changes and a general refund-framework refactor.
- Automatic product identification or stock/accounting changes based solely on Revolut money movement.
- Importing unrelated Merchant purchases or creating original Odoo sales for unknown payments.
- New custom Revolut receipts, live deployment, production data repairs or new real-money operations during ticket implementation.

## Publication and verification

Published after the owner approved all three decisions in the ticket-planning conversation. This feature extends ticket 37's completed financial discovery with an explicit manager-driven native completion workflow; it does not reinterpret provider money movement as automatic proof of returned goods. Closed ticket 37 and the original-sale, financial verification, native settlement and acknowledgement behavior were inspected. No duplicate native-completion implementation ticket was found. The ticket is one end-to-end slice covering both agreed dispositions; no application code or parent ticket was changed.

Initially published under needs-triage according to the local tracker mapping, then promoted to ready-for-agent at the owner's request on 2026-10-05. Product decisions are settled and no additional reporter information is required. Choosing the smallest compatible native return/accounting representation and proving it through real Odoo workflows with mocked provider I/O are implementation milestones, not outstanding product questions. The ticket is open and unclaimed, with no implementation blockers. Documentation verification checks the ticket metadata, index link and whitespace. Runtime tests were not run because this change only publishes the approved specification.

## Completion — 2026-10-05

Implemented on `codex/41-complete-external-refund-returns` in the dedicated ticket-41 worktree. Published in [PR 56](https://github.com/davaico/odoo-revolut/pull/56). Addon version: `19.0.1.17.0`; merged runtime candidate: `541c7f67a221dbd2f8e7898e851a1f84b0ccd049`. Current main's evidence-page retirement and release checklist are preserved.

Managers confirm original products, quantities, tracking and applicable base/tip allocation, then create or atomically associate exact native returns without repeating issued money. Actual native stock, credit notes, receipts and financial-only posted corrections are verified. Pending reservations, historical assertions, source provenance, access boundaries and concurrent recovery remain protected. Ticket 40's existing rounding is reused.

Verification: 546 clean-install tests passed with zero failures/errors; 90 targeted merged-code tests passed; focused actual stock/accounting, financial-only and concurrency suites passed. Shared-access tests passed on installation and upgrade (26 each). Both actual historical-refund and evidence-retirement upgrades passed with zero Merchant HTTP. Both independent review axes have zero outstanding findings. The final full upgrade phase was stopped at the owner's request and is not claimed as passing.

See [staff workflow, controlled acceptance and detailed verification](../../testing/ticket-41-external-refund-completion.md). Physical acceptance and deployment remain the existing release process.

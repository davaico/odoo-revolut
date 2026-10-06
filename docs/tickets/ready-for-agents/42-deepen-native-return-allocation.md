# 42 — Deepen native return allocation and recovery

**Work branch:** `codex/42-deepen-native-return-allocation`

**State:** claimed

**Triage:** ready-for-agent

**Category:** architecture

**Approved scope:** Owner approved the merged two-ticket breakdown on 2026-10-06 and requested publication on main.

## What to build

Staff can preview, save, refund, recover and complete a native Odoo return with the same conserved product amounts and original tender limits as today. Return allocation owns monetary decisions, quantity checks and recovery evidence, so callers do not interpret balances or assemble recovery protocols themselves.

This is the first prefactoring slice, exercised through the complete existing native workflow. Keep explicit workflow operations on the existing module. Separate advisory display from authoritative freezing; native Odoo remains responsible for tax calculation, stock, receipts and accounting projection. Preserve browser-facing requests, Revolut communication and existing transaction lifetimes.

Include recovery of a lost draft from its already verified reimbursements. The module gathers all relevant siblings, checks original-sale identity and conserved evidence, and owns the existing recovery locking protocol. The caller reconstructs native Odoo data and opens the normal staff flow. Recovery evidence is valid only in the transaction that produced it.

Implement shared monetary decisions first, then migrate recovery to consume them within this ticket. Retain external association's current behavior until ticket 43 completes that workflow and verifies the common lock protocol.

## Acceptance criteria

- [ ] Source previews, native refund reservation and return finalization use shared decisions for source gross/base/terminal-selected-tip capacities and whole-return capacities. Callers do not calculate authoritative entitlement.
- [ ] Display target selection is nonlocking and nonmutating, including when called during native price recomputation. Freezing independently checks and persists the accepted per-line allocation and exact total without recursive recomputation.
- [ ] New reservations derive authority from the saved native return/payment and reject changed submitted evidence. Existing attempts are checked before requiring a saved draft; unchanged historical replay without that draft remains recoverable without another dispatch.
- [ ] Preserve quantity reservation once per return, immutable surviving allocations, residual cents, historical base-only payments and rejection of ambiguous per-line history. Displaying completed historical documents does not rewrite their recorded amounts.
- [ ] Full/partial, mixed-tender and cash-only returns retain original tender caps and separate terminal-selected tips. Positive balancing payments cannot conceal an excessive reimbursement.
- [ ] One explicit recovery operation accepts a refund identifying the return and a destination session, gathers all relevant siblings itself and returns checked original contents, conserved target and exact verified tenders. Callers no longer choose which siblings count or assemble private allocation helpers.
- [ ] Reject uncertain siblings, inconsistent snapshots/targets/components, changed identity, incompatible register/company/currency and reused payment links. Recovery preserves the same return/payment identities, provider references, financial provenance and frozen per-line allocation; repeated recovery resumes existing work without new dispatch.
- [ ] Preserve permitted session rollover, opened-session checks and manager/register authority. Do not invent missing cash reimbursement or missing lot/serial evidence. Recovery and closure retain protection for a newly reconstructed draft.
- [ ] Native reconstruction and validation remain in the caller's surrounding transaction. Failed reconstruction leaves no partial native return and does not erase an already durable reimbursement.
- [ ] Reservation still commits in the caller's dedicated transaction before provider dispatch; native checkout retains its surrounding transaction. Do not reorder unrelated locks in this slice.
- [ ] Exercise public source selection through reservation, verified reimbursement and native finalization with mocked Revolut calls. Check accepted totals in saved payments, receipts and applicable native accounting, including an odd-cent partial return and remaining balance. Preserve historical replay, failure-release and existing competing-reservation coverage.
- [ ] Exercise lost-draft recovery with one and multiple verified allocations, session rollover, repeated recovery, uncertain siblings, mixed tenders, tracked products and failed reconstruction through the public manager/native workflow. Assert no new financial dispatch and verify applicable native completion effects exactly once.
- [ ] Record the narrow tests run and which caller-owned decisions moved behind the module's interface. Remove redundant private-helper tests only after equivalent interface coverage exists.

## Blocked by

- None (can start immediately). Earlier return allocation, rounding and external-refund work is already closed.

## Scope limits

No new staff flow, refund policy, provider contract, schema redesign, repository adapter, automatic recovery of missing lots, historical data repair, deployment or real-money operation. Existing Odoo hooks remain the native projection mechanism. All provider calls in tests are mocked.

## Publication and verification

Initially published under needs-triage according to the local tracker mapping. The owner approved this behavior-preserving architecture work; implementation has not started. Earlier closed tickets remain historical evidence and are not reopened. The declared work branch is an implementation assignment, not a branch created by publication. No parent issue, runtime code, provider communication or deployment is changed. Publication checks cover ticket metadata, dependency/index links and whitespace; runtime tests are not required for this documentation-only change.

## Triage decision — 2026-10-06

The owner requested promotion to ready-for-agent. The approved scope and acceptance criteria are fully specified for local implementation with mocked provider calls; no additional product decision or external access is required. State remains open and unclaimed. Ticket 42 can start immediately. Implementation, deployment and live acceptance have not been performed by this triage change.

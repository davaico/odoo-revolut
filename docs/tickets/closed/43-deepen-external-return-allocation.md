# 43 — Deepen external return association and unify return locking

**Work branch:** `codex/43-deepen-external-return-allocation`

**State:** closed

**Triage:** ready-for-agent at closure

**Category:** architecture

**Approved scope:** Owner approved the merged two-ticket breakdown on 2026-10-06 and requested publication on main.

## What to build

A manager can create, resume or associate a native Odoo return for reimbursements already issued through Revolut, using the same checks as native refunds and without issuing money again. Return allocation accepts the complete association batch and owns source/return capacities, frozen monetary evidence and exact reimbursement bindings.

Preserve the current product confirmation, lot/serial selection, worklist and native completion behavior. For a newly constructed return, acquire the required locks before invoking native construction helpers; moving only the arithmetic while leaving a caller-owned lock protocol is insufficient.

This is the final workflow migration. Once association uses shared allocation decisions, unify authoritative locking across native reservation/settlement, monetary freezing, recovery and external association, then remove superseded caller protocols. Implement association first and consolidation second within this ticket, keeping intermediate changes compatible.

The target acquisition order is session, return identity, original sale, original source payments, then refund records, with deterministic ordering within sets and fresh evidence reads under locks. This is a design target, not a claim of a proven existing deadlock. Check neighboring native mutations, financial discovery/reconciliation and session closure for compatibility before adopting it.

## Acceptance criteria

- [x] One explicit module operation accepts an existing return or confirmed original product selection plus exact reimbursement bindings. Callers no longer assemble private allocation helpers or gross/base/tip capacity arithmetic.
- [x] Validate the entire selected batch together, including unique refunds/payments, original sale, register/company/currency, immutable contents and source/whole-return capacities. A rejected member rolls back every new association and any newly prepared native records.
- [x] Count each already-issued financial reimbursement exactly once, including one being associated now. Preserve explicit base/terminal-selected-tip evidence and protected unknown components.
- [x] Repeated preparation, resume and association reuse the same return/payment relationships. Compatible existing completed returns retain their stock/accounting history; ambiguous or unrelated payments are rejected without duplicate native work.
- [x] Pending reimbursements may protect a draft but cannot finalize it. Failed or uncertain reimbursements cannot become verified tenders; authoritative successful evidence remains necessary for completion.
- [x] Preserve financial-only dispositions, historical acknowledgements, register authority, native product/lot confirmation and exact original manual-tender limits.
- [x] Inspect and document participating acquisition orders, including native order/payment mutation hooks, external discovery, refund status application and session closure. Resolve inversions without making authoritative decisions from evidence read before locking.
- [x] All four authoritative workflows use module-owned acquisition and validation, with deterministic multiple-record ordering and appropriate rereads/invalidation. Caller workflows no longer invoke private allocation monetary/locking helpers.
- [x] Advisory picker/display calls remain nonlocking and nonmutating. Transactions, conflict retries, commits and provider dispatch remain caller-owned; no transaction-scoped result acts as authority after a cursor change or commit.
- [x] Exercise full/partial returns, multiple reimbursements and original tenders, mixed cash/card, pending-to-verified resume, historical completed-return association and a failing batch through the manager workflow. Assert zero financial requests for issued money and actual applicable native stock/accounting effects exactly once.
- [x] Verify independent PostgreSQL transactions for duplicate submission, competing returns for final quantities/cents, reservation versus external association/discovery, recovery versus closure and finalization versus changing refund status. Assert conserved quantities/money, durable recoverability and no duplicate provider dispatch/native effects.
- [x] Preserve failed-sibling release with a surviving immutable allocation, historical replay without a saved draft, protected uncertain outcomes and exact refund/payment linking across the combined workflows.
- [x] Remove superseded helpers and redundant tests only after equivalent interface coverage passes. Keep bounded preflight guards and native transport/lifecycle hooks; cleanup must not bypass unrelated-order or access checks.
- [x] Run the narrow affected allocation, refund, recovery, external-association, concurrency and native-accounting tests, then required integration checks. Record actual results and explain any checks not run; a build alone is insufficient evidence.
- [x] Record final interface responsibilities and demonstrate complete native and already-issued external refund paths, plus a competing-request rejection. Existing Odoo/Revolut communication and native staff behavior remain unchanged.

## Blocked by

- 42 — Deepen native return allocation and recovery. Association reuses its shared capacity and frozen-target decisions, and final lock consolidation requires the native recovery migration to be present.

## Scope limits

No automatic goods identification from money, replacement reimbursement, generic framework, invented dependency adapters, new provider communication or new staff flow. Native Odoo validation still owns stock, receipts and accounting completion. Use real Odoo/PostgreSQL transactions and mocked provider calls for verification. Deployment and live acceptance remain separate.

## Publication and verification

Initially published under needs-triage according to the local tracker mapping. The owner approved this behavior-preserving architecture work; implementation has not started. Earlier closed tickets remain historical evidence and are not reopened. The declared work branch is an implementation assignment, not a branch created by publication. No parent issue, runtime code, provider communication or deployment is changed. Publication checks cover ticket metadata, dependency/index links and whitespace; runtime tests are not required for this documentation-only change.

## Triage decision — 2026-10-06

The owner requested promotion to ready-for-agent. The approved scope and acceptance criteria are fully specified for local implementation with mocked provider calls; no additional product decision or external access is required. State remains open and unclaimed. Ticket 43 remains blocked by ticket 42; readiness does not waive that dependency. Implementation, deployment and live acceptance have not been performed by this triage change.


## Completion — 2026-10-06

Ticket 42 was already closed and present in the user-confirmed `57e9a67`
baseline. Implementation is committed on
`codex/43-deepen-external-return-allocation`, in
`/home/gary/delivery/Tek2/stage/odoo-rev/worktree/43-external-return-allocation`.
The verified runtime candidate is `c183c2f` (`d5b4c8d` plus `c183c2f`);
final closure/evidence edits change documentation only.

One batch association operation now owns exact binding/capacity decisions and
locks before native construction. Native reservation, settlement, freezing,
recovery and external association share deterministic acquisition. Neighboring
parent/child mutation, observation, discovery and closure hooks acquire complete
affected owners and reread evidence under locks. Transactions, retries and
provider dispatch remain caller-owned.

The user agreed to test manager completion/resume and independent PostgreSQL
transactions and to review against `57e9a67`. A terminal-tip sibling regression
and genuine session-lock contention regression fail on that baseline and pass
on the candidate. Manager association/replay preserves actual historical stock
and posted credit-note identities with zero HTTP. Failed batch association
preserves all existing links/effects. Independent-transaction tests cover
reservation, discovery, recovery, closure, status/finalization and four native
line/payment LINK/SET transfers; only serialization conflicts are retried.

Full fresh installation and current-version upgrade each passed **561 tests**,
with zero failures/errors and runner exit 0. The affected historical
`external-native` and `return-rounding` upgrade scenarios passed. Narrow native,
refund/tip, recovery, association, discovery, accounting and concurrency runs
passed. JavaScript lifecycle checks passed 88 tests; host tooling ran 53 tests
with 50 passing and 3 opt-in PDF-runtime checks skipped. Syntax/whitespace checks
passed; no static typechecker is configured. A build is not used as proof of
payment correctness.

Independent review found 0 documented Standards violations and 0 remaining Spec
findings. One minor optional Standards duplication heuristic remains in two
command-discovery identifier collectors; no concrete locking regression was
found. Exact results, scope of skipped checks, reproduction commands, interface
responsibilities and complete/competing path evidence are recorded in
[the verification record](../../testing/ticket-43-external-return-allocation.md)
and [the lock audit](../../testing/ticket-43-lock-orders.md).

No schema, migration, credential, provider contract, deployment or staff-flow
changes are introduced. Deployment and live acceptance remain ticket 12.

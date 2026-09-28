# 19 — Enforce verified settlement and internal-operation permissions

**Work branch:** `codex/19-enforce-payment-server-boundaries`

**State:** open

**Triage:** ready-for-agent

**Priority:** P1 (includes the related P2 internal-lock authorization correction)

## What to build

A POS sale or return can record a Revolut settlement only when the server has
verified the matching financial operation, regardless of which supported
client entry point is used. Cashiers and managers cannot bypass verification
or mutate another company's internal coordination records through public
methods. Legitimate checkout, recovery and reconciliation continue to work.

## Observed problems

The integrated audit on 2026-09-28 at revision `9bc9a0a` reproduced a
non-manager, non-superuser POS user recording a fabricated Revolut tender and
marking its order paid through inherited public methods, without a verified
operation or provider request. The normal POS synchronization path checked
verification, but these alternate paths did not.

The same audit reproduced a public raw-SQL locking helper creating a protected
coordination record for a company outside that user's allowed companies.
Existing ORM permissions and company read rules did not cover this method.
This second issue demonstrated unauthorized internal writes, not a provider
charge or disclosure of credentials. These two corrections share the server
authorization boundary and are independently asserted within this ticket.

## Acceptance criteria

- [ ] Identify and guard the public model entry points that can create, change, remove or finalize Revolut-linked orders and payment records. An authenticated non-superuser POS user cannot record an unverified Revolut payment or refund as settled through direct model operations or inherited public methods. A browser-supplied done status or transaction reference is never sufficient proof.
- [ ] Enforce matching verified operation identity, company, POS ownership, currency, amount, order contents and payment-line/provider references at the authoritative mutation and settlement boundaries. Preserve one-operation/one-settlement ownership and the existing return quantity, reservation and original-tender limits. Do not introduce a caller-controlled context flag or alternate public helper that bypasses verification.
- [ ] Once financial exposure or verified settlement exists, direct edits, reassignment or deletion cannot detach the evidence, reuse it on another order, alter protected financial contents or substitute another tender to evade an unresolved operation. Reject forbidden mutations atomically without leaving a forged paid order, altered payment or partial linkage.
- [ ] Remove unintended RPC access to internal transaction-lock mutation, or enforce the intended authorization before any SQL. Cashiers, managers outside the active allowed-company context and users without POS permission cannot create or change protected coordination records through a public helper. Preserve ticket 18's internal-record read isolation and manager/cashier direct-mutation prohibitions.
- [ ] Keep authorized payment starts, return allocation, concurrent claims and settlement locking functional. Preserve normal draft persistence, verified split tender, full/partial refunds, allowed Restaurant table changes, cash/bank checkout, manager reconciliation and audit evidence. Keep invariant ownership in the existing domain components rather than duplicating their rules across entry points.
- [ ] Add regressions using ordinary non-manager/non-superuser POS users, managers, restricted multi-company contexts and an unauthorized role. Reproduce both audit defects before the fix, then prove rejection through the actual public-call boundary and affected ORM paths. Include missing, pending, failed, mismatched and reused evidence, plus allowed verified-payment/refund controls. Do not rely solely on the normal POS synchronization helper or frontend guards.
- [ ] Run the affected authorization, payment, return, concurrency and browser acceptance checks on the pinned Odoo version. Verify installation and upgrade apply the correction. All provider calls are mocked or blocked; no real terminal or credentials are required.
- [ ] Record implementation revision, regression evidence and an independent security review of the reachable mutation paths. Update operating guidance if supported behavior changes. Preserve trusted-server credentials, persisted claims before provider mutations and reconciliation before uncertain retries.

## Blocked by

- None. Existing payment, return and authorization foundations are implemented. Tickets 02, 20 and 21 do not gate this mocked correction.

## Release gate

Blocks ticket 12. Integrate and review this correction before live acceptance.

## Scope and execution

Combine audit findings 1 and 2 only. Implement the settlement protection first,
then close the internal-helper bypass, with separately identifiable regression
evidence. Keep any necessary prefactoring local to enforcement of these
invariants; this is not an Odoo-wide permission redesign.

Create the declared branch from reviewed main when implementation starts, or
update it if it already exists. Use an isolated worktree for concurrent work.
The branch is declared here and will be created when implementation starts.

## Verification evidence

Audit evidence only: both defects reproduced in disposable Odoo
`19.0.20260908` with synthetic fixtures, non-superuser POS permissions and HTTP
blocked; fixtures were rolled back. The public methods were invoked through
the ORM under the user's permissions, not an HTTP exploit test. New regression
coverage must exercise the public-call boundary. Fix implementation has not
started.

## Triage decision

2026-09-28: The owner approved this three-ticket breakdown and direct
publication as ready-for-agent. All three corrections are independently
actionable with mocked provider calls and block ticket 12. Recommended priority
is 19, then 20, then 21; this is not a dependency chain.

# 18 — Isolate internal payment records by allowed company

**Work branch:** `codex/18-isolate-internal-payment-records`

**State:** open

**Triage:** ready-for-agent

## What to build

A POS manager can inspect only the internal Revolut payment information
permitted by their allowed companies. Direct model reads must not reveal
another company's dispatch references or order identifiers, while authorized
reconciliation and payment processing continue to work.

## Observed problem

The integrated-revision audit on 2026-09-25 at `086dd12` reproduced a manager
restricted to company B reading company A's dispatch reference, action and
outcome, and order-lock UUID. The parent payment operation was correctly
hidden. Read ACLs on the internal models did not have corresponding company
record rules; the parent operation's rule did not protect direct reads of
dispatch fields. This is metadata disclosure, not a demonstrated financial
mutation bypass.

## Acceptance criteria

- [ ] Direct searches and reads of payment dispatch claims and order locks cannot expose records outside the manager's allowed companies, including requests for scalar fields that do not read the parent operation.
- [ ] Use existing Odoo access-control conventions: remove unnecessary manager read access or restrict required access by the owning company. Derive dispatch ownership from its operation and prevent inconsistent ownership from bypassing the restriction.
- [ ] Legitimate manager inspection and reconciliation continue to work for allowed companies. Where internal-model access is unnecessary, denying it must not break supported manager workflows. Users with access to multiple companies remain restricted to their active allowed-company context.
- [ ] Preserve cashier restrictions and existing prohibitions on direct creation, modification or deletion of financial operation internals. Company scoping must not introduce a mark-paid, unlock or dispatch bypass.
- [ ] Add two-company Odoo regressions that reproduce the original disclosure through direct model reads with no parent relation requested. Assert the parent operation isolation control, denied foreign internal records, allowed-company behavior and restricted multi-company context using non-superuser access.
- [ ] Exercise authorized payment dispatch and manager reconciliation after the access change, retaining transaction and audit guarantees. Verify the security update applies on upgrade as well as fresh installation; all provider calls remain mocked.
- [ ] Document any intentional change to supported manager access and record focused authorization/workflow test results. Never include credentials or real payment/customer data in evidence.

## Blocked by

- None. Existing payment and manager reconciliation foundations are implemented. Tickets 02, 16 and 17 do not gate this authorization correction.

## Release gate

Blocks ticket 12 — Validate real terminal payments and publish release evidence.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown, requested publication
directly under ready-for-agent, and required all three corrections before
ticket 12. This ticket is independently actionable with mocked provider calls.
Its declared work branch has been created. Update it from the latest reviewed
main before starting; use an isolated worktree for concurrent implementation.

## Verification evidence

The audit reproduced both disclosures in the disposable Odoo environment with
synthetic records, a manager restricted to the other company and direct model
reads. The parent-operation isolation control passed. HTTP was blocked and all
fixtures were rolled back. Implementation has not started.

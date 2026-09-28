# 18 — Isolate internal payment records by allowed company

**Work branch:** `codex/18-isolate-internal-payment-records`

**State:** claimed

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

Implemented on `codex/18-isolate-internal-payment-records`, fast-forwarded to
reviewed `main` at `ebd67fa` before implementation. Addon `19.0.1.7.1` retains
manager read-only access and restricts dispatch claims through
`operation_id.company_id`; order locks are restricted through `company_id`.
Both rules use Odoo's active `company_ids` context and load on module update.
No separately writable dispatch company can override its operation's owner.

Verification on Odoo `19.0.20260908`, using synthetic records only:

- Red/green regressions reproduced each disclosure before its corresponding
  rule was added. The parent operation isolation control passed. The final
  tests request only scalar dispatch or order-lock fields, check direct reads,
  searches and search/reads, and verify authorized manager reads.
- Focused fresh install: `./scripts/test-addon --test-tags
  /pos_revolut:TestRevolutAuthorization,/pos_revolut:TestRevolutReconciliation`
  passed 13 tests, with 0 failures and 0 errors. This includes a manager with
  both companies restricted to one active company, cashier read denial, denied
  manager/cashier create/write/unlink, and a non-superuser cashier dispatch
  followed by manager reconciliation. The same operation, two completed
  dispatch claims, provider references and manager audit are retained.
- Actual legacy upgrade: installed `pos_revolut` from `ebd67fa`
  (`19.0.1.7.0`) in a disposable database and committed a pending payment,
  two dispatch claims and its order lock through the public payment start.
  A foreign manager could read both internal models' scalar fields while the
  parent operation remained hidden. After updating that same database to
  `19.0.1.7.1`, the 13 focused tests passed. Direct reads/searches of the
  persisted foreign records were denied, including for a multi-company
  manager with a restricted active-company context. Authorized manager
  reconciliation verified the original payment using only mocked GETs and
  committed its audit in the production-owned transactions; a fresh
  transaction confirmed the verified reference, manager actor and preserved
  dispatch claims.
- Controlled lifecycle suite passed all 12 tests; repository deployment unit
  suite passed all 29 tests. Python compilation, security XML parsing and
  `git diff --check` passed. No static typechecker is configured for the addon.

All expected provider calls were mocked. The test network is internal and the
Merchant HTTP guard was verified before Odoo ran. No credentials or real
payment/customer data were used. Manager access and the focused verification
command are documented in `docs/installation.md`.

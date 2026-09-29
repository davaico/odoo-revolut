# 19 — Enforce verified settlement and internal-operation permissions

**Work branch:** `codex/19-enforce-payment-server-boundaries`

**State:** closed

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

- [x] Identify and guard the public model entry points that can create, change, remove or finalize Revolut-linked orders and payment records. An authenticated non-superuser POS user cannot record an unverified Revolut payment or refund as settled through direct model operations or inherited public methods. A browser-supplied done status or transaction reference is never sufficient proof.
- [x] Enforce matching verified operation identity, company, POS ownership, currency, amount, order contents and payment-line/provider references at the authoritative mutation and settlement boundaries. Preserve one-operation/one-settlement ownership and the existing return quantity, reservation and original-tender limits. Do not introduce a caller-controlled context flag or alternate public helper that bypasses verification.
- [x] Once financial exposure or verified settlement exists, direct edits, reassignment or deletion cannot detach the evidence, reuse it on another order, alter protected financial contents or substitute another tender to evade an unresolved operation. Reject forbidden mutations atomically without leaving a forged paid order, altered payment or partial linkage.
- [x] Remove unintended RPC access to internal transaction-lock mutation, or enforce the intended authorization before any SQL. Cashiers, managers outside the active allowed-company context and users without POS permission cannot create or change protected coordination records through a public helper. Preserve ticket 18's internal-record read isolation and manager/cashier direct-mutation prohibitions.
- [x] Keep authorized payment starts, return allocation, concurrent claims and settlement locking functional. Preserve normal draft persistence, verified split tender, full/partial refunds, allowed Restaurant table changes, cash/bank checkout, manager reconciliation and audit evidence. Keep invariant ownership in the existing domain components rather than duplicating their rules across entry points.
- [x] Add regressions using ordinary non-manager/non-superuser POS users, managers, restricted multi-company contexts and an unauthorized role. Reproduce both audit defects before the fix, then prove rejection through the actual public-call boundary and affected ORM paths. Include missing, pending, failed, mismatched and reused evidence, plus allowed verified-payment/refund controls. Do not rely solely on the normal POS synchronization helper or frontend guards.
- [x] Run the affected authorization, payment, return, concurrency and browser acceptance checks on the pinned Odoo version. Verify installation and upgrade apply the correction. All provider calls are mocked or blocked; no real terminal or credentials are required.
- [x] Record implementation revision, regression evidence and an independent security review of the reachable mutation paths. Update operating guidance if supported behavior changes. Preserve trusted-server credentials, persisted claims before provider mutations and reconciliation before uncertain retries.

## Blocked by

- None. Existing payment, return and authorization foundations are implemented. Tickets 02, 20 and 21 do not gate this mocked correction.

## Release gate

Blocks ticket 12. Integrate and review this correction before live acceptance.

## Scope and execution

Combine audit findings 1 and 2 only. Implement the settlement protection first,
then close the internal-helper bypass, with separately identifiable regression
evidence. Keep any necessary prefactoring local to enforcement of these
invariants; this is not an Odoo-wide permission redesign.

The declared work branch has been created from the committed ticket baseline.
Update it from reviewed main before implementation without overwriting existing
work. Use an isolated worktree for concurrent work.

## Verification evidence

Implemented at `9e460f1` (following `64693b8`, `b620413` and `a184df8`) on
`codex/19-enforce-payment-server-boundaries`, based on reviewed `main` at
`7a2ad28`. A fresh fetch of `origin/main` confirmed that baseline before
implementation commits. Addon version is `19.0.1.7.2`.

The order, payment and order-line create/write/unlink boundaries share the
existing charge and Return allocation validators. The private Python mutation
scope is cursor-bound and validates the final aggregate once inside its own
savepoint; browser context flags cannot forge it. Inherited payment addition,
paid-state actions, invoice/refund/copy helpers and relational commands enter
those guarded ORM boundaries. Private transaction locking remains available
to internal dispatch and allocation, without an RPC entry point. Ticket 18's
ACLs and company rules remain in force.

Verification on pinned Odoo `19.0.20260908` with synthetic records:

- Red/green regressions reproduced the fabricated done-tender create,
  inherited payment addition and alternate finalization, then rejected them.
  The public `lock_order` defect reproduced unauthorized SQL mutation across
  all four tested roles before it was renamed `_lock_order`; both names are
  now rejected through RPC before internal rows can be changed.
- New regressions use `odoo.service.model.call_kw`, including its public
  method lookup, with ordinary non-superuser cashiers, managers, restricted
  multi-company contexts and a user without POS permission. Plain unittest
  exception contexts deliberately avoid Odoo's test-savepoint helper so the
  assertions verify the production-owned rollback after a caught exception.
  Rejected batch creation also removes its otherwise valid companion order.
- Direct creation, edits, deletion, reassignment and relational commands cover
  missing/pending/failed/mismatched/reused charge and refund evidence, copied
  provider references, protected lines/subtotals, original-return detachment,
  tender substitution and one-operation/one-payment linkage. Authorized
  verified sale/refund controls, partial drafts, full split balance, cash/bank
  completion and unexposed draft cancellation/discard remain functional.
- Independent review exposed additional creation/edit paths for POS config,
  stored child company/session ownership, conversion rate, refund document
  classification, initial line totals and incomplete final tender balance.
  Each concrete bypass was reproduced and corrected. Odoo's canonical
  calculation now checks line totals and final balance; creation controls
  confirm that Odoo normalizes supplied stored related ownership and computed
  conversion rates. Date changes cannot alter an exposed conversion rate.
- Final focused run passed 113 tests with zero failures/errors:
  `/pos_revolut:TestRevolutMutationBoundaries`, `TestRevolutRefund`,
  `TestRevolutAuthorization`, `TestRevolutOrderSettlement`,
  `TestRevolutRetryConcurrency` and `TestRevolutRefundConcurrency`.
- Actual legacy upgrade: installed addon `19.0.1.7.1` from `7a2ad28` in a
  separate disposable database, passed its 23 authorization/settlement tests,
  confirmed the installed version, then updated the same database to
  `19.0.1.7.2`. All 113 affected tests passed after that update.
- Final full run: `./scripts/test-addon --verify-install-upgrade` at
  `9e460f1` exited successfully. Fresh installation passed 185 tests; module
  update passed the same 185 tests; the Restaurant bridge run passed 8 tests.
  Every phase recorded zero failures/errors, with no browser skips. Manager,
  retail checkout, Restaurant table changes, verification rejection and
  concurrency workflows were exercised by the existing acceptance suites.
- Controlled JavaScript lifecycle suite: 12 passed. Repository deployment
  unit suite: 29 passed. Python compilation and `git diff --check` passed.
  The addon has no configured standalone static typechecker.

Merchant calls are mocked or blocked by the verified test HTTP guard; Compose
uses an internal network. No real terminal, Merchant credential or customer
data was used. Earlier full runs are preliminary evidence only;
closure relies on the final run after the review corrections. Operating
guidance documents the offline server upgrade, reopen-POS step, retained
evidence, permitted draft cancellation and prohibition on repairing an older
fabricated order by deleting or rewriting its references. No new settings or
credential rotation are needed. Ticket 12 retains integrated and live gates.

## Independent security review

The independent reviewer inspected public order/payment/line mutations and
inherited checkout, invoice, refund, copy and sync helpers; the ContextVar and
savepoint lifetime; company/POS ownership; evidence matching/reuse; return
origin; private locking; and concurrent settlement. Pinned Odoo One2many
implementation confirmed that indirect link/set/update/create/delete commands
enter the guarded overrides. The discovered ownership, accounting-field,
cancellation and creation-classification paths were corrected and re-reviewed.
Final re-review also reproduced a refund-origin bypass of Odoo's generic
paid check. The sale check now compares its actual rounded total with
persisted tender amounts, so a caller-supplied cash-return origin cannot
reduce the required balance. The added cashier RPC regression reproduced
the bypass before correction and passed with the final 113-test run.
The independent reviewer found no remaining actionable ticket-19 defect
at `9e460f1`; final installation/upgrade/browser acceptance also passed.

## Standards

No documented-standard breaches in `git diff 7a2ad28...9e460f1`. The change
uses Odoo's existing amount and payment checks, stays within the addon and
follows trusted-server/mocked-HTTP conventions. One optional possible
Duplicated Code heuristic remains in deliberate mismatch-fixture setup;
`_matched_operation_payload` shares verified and partial-payment setup.
The remaining repetition keeps distinct forged inputs explicit and is a
maintenance suggestion, not a blocker.

## Spec

No remaining actionable findings in `git diff 7a2ad28...9e460f1`. Both initial
findings were corrected: canonical stored line totals and complete final sale
balance, including the independently found refund-origin override.
Public-call red/green tests verify rejection and atomic rollback,
preserve partially paid drafts and allow finalization after the cash remainder
is added. No unasked scope was identified. Full acceptance passed.

Review summary: Standards 0 hard violations and 1 optional heuristic; Spec
0 remaining findings (2 corrected). Neither axis has a blocking finding.

## Triage decision

2026-09-28: The owner approved this three-ticket breakdown and direct
publication as ready-for-agent. All three corrections are independently
actionable with mocked provider calls and block ticket 12. Recommended priority
is 19, then 20, then 21; this is not a dependency chain.

## Closure

2026-09-28: All acceptance criteria are met on the declared work branch.
Final fetch confirmed `origin/main` remains `7a2ad28` and is an ancestor of
the implementation. The reviewed code is `9e460f1`; the closure commit adds
only operating guidance, verification evidence and tracker updates.
Ticket 12 remains open for integration of the other corrections and controlled
live-terminal acceptance.

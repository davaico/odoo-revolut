# Ticket 70 — Recover an existing waiting return after refund verification

Base and integration target: sanitized `feat/v18_rev`, base `484a96f`.
Task branch: `codex/70-v18-verified-refund-return-recovery`.
The maintainer explicitly approved this base, the brief and implementation.
No older private ancestry, operational identifiers or protected evidence is
included. Odoo 19 is assessed separately below.

## Red gate before correction

`9fe5ff8` adds the portable primary regression before any production changes.
It persists a native draft with its waiting negative tender, starts one mocked
processing refund, verifies the same refund through backend Check status, then
calls the public manager recovery action with further provider HTTP forbidden.
It raises the exact reported allocation-link UserError in
`ReturnAllocation.recover()`: the matching tender has no final transaction
reference. One test ran, one error (`/tmp/t70-red.log`).

Earlier synthetic stock-product fixture errors were corrected before this
meaningful red; they are not bug-reproduction evidence.

## Correction

Reviewed candidate: `a868add`. Recovery uses the existing native-tender
eligibility check to distinguish absent draft references from contradictions.
It validates populated native references before writing and projects all
verified siblings inside the established native mutation/savepoint scope.
Canonical settlement then binds original refund/tender identities and checks
the complete saved return. Rejected contents roll back the projection.

Only the verified card allocation is projected. Normal POS validation still
owns stock and accounting, and the cashier explicitly completes any remaining
manual Cash portion. The manager action is called **Recover return** for both
existing and genuinely missing returns and remains available after linkage.
A completed return opens for review. No credentials or configuration changed.
Use a normal reviewed addon update to load the view change; deployment and live
financial actions require separate authorization.

## Verification

All tests use synthetic records. Runtime: pinned Odoo Community `18.0.20261015`,
PostgreSQL 16.14, bundled Chrome 153, disposable Compose project
`revolut-ticket70`, isolated internal network and global Merchant HTTP guard.
The existing manual-acceptance environment was not changed or tested.

- Primary red → green exercises existing identity preservation, canonical card
  references/linkage, repeated recovery, ordinary `sync_from_ui()` validation,
  one stock return and one posted credit note through repeated validation.
  The first green run passed one test (`/tmp/t70-green.log`).
- Standalone and mixed native browser flows perform backend Check status,
  click Recover return, load the existing order into PaymentScreen, reload,
  and validate to the native receipt. They preserve original order/tender
  database identities and allow exactly one mocked status GET, no dispatch.
  Mixed coverage asserts the Cash balance remains outstanding before the
  explicit Cash action. Two initial browser checks passed (`/tmp/t70-native.log`).
- Focused selection of `TestRevolutRefund` and `TestExternalRefundManagerUi`
  ran 69 tests: 68 passed, one test-only assertion failed because a list of
  false references was asserted false. The assertion was corrected to test
  `any(...)`; its narrow sibling rerun passed (`/tmp/t70-siblings.log`).
  The initial focused run is `/tmp/t70-focused.log`; the final full run below
  is authoritative for the combined candidate.
- Conflict tests seed otherwise ORM-forbidden inconsistent evidence to exercise
  the public recovery action: method, amount, tender/order ownership, populated
  transaction/reference/order/intent/charge links, existing refund links and
  changed native contents. Every rejection preserves the prior evidence.
  Native persistence separately rejects duplicate tender UUIDs. Pending and
  unresolved operations, and an uncertain sibling, cannot be projected.
- JavaScript: 144 passed (`/tmp/t70-js.log`). Host tooling: 70 passed, three
  PDF-runtime skips (`/tmp/t70-host.log`). No standalone typechecker/linter
  configuration exists; changed Python, JavaScript and XML parse, and diff
  whitespace checks pass. Native runtime checks exercise ORM contracts.

Full addon run on the committed candidate: **778 tests, zero failures/errors**
(`/tmp/t70-full.log`, exit 0). The log reports 691 post-install tests in
1459.59 seconds; one optional employee-list characterization was skipped
because `pos_hr` is not installed. This combined run includes all six new #70
regressions, both affected classes and existing missing-return, refund,
concurrency, Restaurant, rounding, stock/accounting and checkout browser checks.
Merchant HTTP guard verification also passed for both hosts. The tested addon
tree is `70c1b0cb1db67144a46961e5e690fa1bd146dc3d`; final evidence/index changes
are documentation only.

Reproduction selection (run from this task checkout, using only its disposable
Compose project):

```sh
docker compose --project-name revolut-ticket70 --file compose.yaml run --rm odoo \
  --database ticket70 --update pos_revolut \
  --test-tags /pos_revolut:TestRevolutRefund.test_manager_recovers_existing_waiting_return_after_backend_verification \
  --stop-after-init --workers 0 --max-cron-threads 0
```

Use `--test-tags /pos_revolut:TestRevolutRefund,/pos_revolut:TestExternalRefundManagerUi`
for the two affected classes, or `/pos_revolut` for the complete addon suite.
The initial red used the unchanged production code and the test from `9fe5ff8`;
current production code should pass that regression.

## Independent review

Both read-only reviews used the immutable diff `484a96f...a868add`.

## Standards

No documented-standard violations or actionable baseline smells were found.
The reviewer checked repository guidelines, ADR 0002, tracker rules, domain
vocabulary, contributing and architecture guidance. The correction reuses
existing allocation eligibility and native mutation validation, preserves
server verification and identities, and adds mocked recovery coverage.

One nonblocking documentation observation: a blank line broke the #71 row
out of the open-ticket Markdown table. The formatting was corrected.

## Spec

No actionable findings. The reviewer confirmed the portable regression was
committed before production changes; existing-draft projection reuses original
identities and validates all siblings inside the mutation/savepoint boundary;
normal validation retains contents, ownership, allocation and reference checks.
Cash remains outstanding for explicit completion. Tests cover contradictory
evidence, uncertain siblings, repeated recovery and native stock/credit-note
effects; existing missing-return tests remain applicable. Odoo 19 is explicitly
outstanding in #71. UI wording supports the requested manager route without
scope expansion. Completion was conditional on the final runtime checks.

Both reviews were static; test results above supply runtime evidence.
Review summary: Standards 0 substantive findings (1 formatting observation,
corrected); Spec 0 actionable findings.

## Odoo 19 and physical acceptance

Independent source assessment of maintained Odoo 19 `main` at `e783d6f` found
the same unconditional reference guard and absent existing-draft projection.
Ticket #71 records its own mocked failing-regression gate and required runtime
adaptations. This change does not implement or claim Odoo 19 runtime parity.
No real terminal/merchant request, live database repair, deployment, credential
rotation or physical acceptance occurred. Protected manual-acceptance records
remain intact; this work establishes synthetic Odoo 18 recovery correctness.

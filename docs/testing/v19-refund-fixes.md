# Combined Odoo 19 refund fixes

Candidate: `codex/v19-refund-fixes`, addon `19.0.1.18.16`. Base and PR
target: production `19.0` at `440f1a8c89048e5c2170425a4684ed23cbb0e261`.

Only standalone V19 commits are selected: PR #87 (`904cc56`), #71
(`3964148`, `e114589`, `e21127b`, `17a6287`), and #74 (`f121796`,
`0c19616`). Cherry-pick messages retain the original source hashes. No V18
commit, V18 addon path, or divergent `main` history is included. The final
release commit assigns the combined version, corrects the description of
request metadata, and aligns the retained upgrade fixture with that version.

## Current verification

- JavaScript state and checkout suite: 159 passed.
- Portable tooling suite: 23 passed.
- Whitespace and original-patch scope checks pass.
- Standards review of `440f1a8...f41b9bf`: zero actionable findings.
- Combined native payment/refund/browser verification has no recoverable final
  outcome: the terminal session and temporary logs became unavailable after
  the test environment changed. Do not treat the run as passing.
- The versioned production-base upgrade rehearsal has not run. Native tests
  and upgrade preservation remain required before marking the PR ready.
- Spec review of `440f1a8...f41b9bf`: zero actionable findings. Both
  independent reviews were static and did not execute tests.
- The first native runner attempt stopped before tests because Docker's
  default address pools were exhausted. A second attempt used an explicit
  unused internal subnet. Docker is now inaccessible from the execution
  environment; existing environments were not pruned or changed.

Source-branch histories and earlier failed/timing checkpoints remain in
[ticket 71](ticket-71-refund-recovery.md) and
[ticket 74](ticket-74-refund-refresh.md). Those independent runs do not prove
the assembled candidate. This report records the combined candidate separately.

No deployment, real Merchant API request, live financial operation or physical
terminal acceptance is performed. PR publication leaves `19.0` unchanged.

## Remaining checks before release review

Run the combined `TestRevolutPayment`, `TestRevolutRefund` and
`TestRevolutRefundRecoveryUi` classes, plus the single/two-refund native
refresh, verified-refund rejection/timeout/offline loader, pending-refund
recovery and ordinary Cash/bank browser cases in `TestRevolutVerifiedCheckout`.
Use the pinned Odoo 19 runner, mocked provider HTTP and Merchant guard.

In a separate disposable database, install the archived `440f1a8` addon, run
`pos_revolut/tests/refund_recovery_upgrade_seed.py` in an Odoo shell, stop the
old process, update to this candidate, then run
`pos_revolut/tests/refund_recovery_upgrade_verify.py`. The fixture expects
`19.0.1.18.14` before and `19.0.1.18.16` after, preserves all snapshotted records,
and verifies uncertain-refund blocking and repeat recovery without provider
HTTP. Never seed a deployment database. Retain actual exit codes and logs.

The PR is a draft for review of this bounded patch. It does not claim the
combined native or upgrade gates have passed.

## Combo rounding regression fix

The Odoo 19 configurator's `getSelectedComboItems()` enumerates numeric
combo/item keys by ID before `computeComboItems()` allocates the parent price.
The server instead iterated combo groups in their default `sequence, id` order.
Sort groups by ID so a display-sequence change cannot move the rounding cent
between tax rates or classify native prices as a restricted manual override.

Two native regressions persist selections in reversed display order for a
0.05 combo with equal bases and 20%/0% taxes. Odoo allocates 0.03/0.02,
producing a 0.06 total. Before the fix, the unrestricted cart rejected that
tender against a 0.05 authorized balance, and the restricted cart wrongly
required manager approval. Both fail before the fix and pass afterward.

Validation on the pinned Odoo 19 image: `TestRevolutCartPricing`, all 19 tests
passed (0 failures, 0 errors), including existing extra-selection and genuine
manual-override coverage. Run via `scripts/test-addon --test-tags
/pos_revolut:TestRevolutCartPricing`; a temporary Compose override supplied an
unused internal subnet because Docker's default pools were exhausted. Provider
HTTP stayed mocked and guarded. No configuration or credential change is
needed. This targeted run does not replace the outstanding combined refund,
browser and upgrade checks above.

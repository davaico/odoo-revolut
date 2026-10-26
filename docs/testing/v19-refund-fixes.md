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
- Spec review is pending.
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

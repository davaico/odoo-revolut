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
- Combined native payment/refund/browser verification, versioned upgrade
  preservation, and independent Standards/Spec review are in progress.
- The first native runner attempt stopped before tests because Docker's
  default address pools were exhausted. Verification uses an explicit unused
  internal subnet; existing environments are not pruned or changed.

Source-branch histories and earlier failed/timing checkpoints remain in
[ticket 71](ticket-71-refund-recovery.md) and
[ticket 74](ticket-74-refund-refresh.md). Those independent runs do not prove
the assembled candidate. This report records the combined candidate separately.

No deployment, real Merchant API request, live financial operation or physical
terminal acceptance is performed. PR publication leaves `19.0` unchanged.

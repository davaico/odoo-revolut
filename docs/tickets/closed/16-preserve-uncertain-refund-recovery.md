# 16 — Preserve uncertain refunds when original-sale recovery fails

**Work branch:** `codex/16-preserve-uncertain-refund-recovery`

**State:** closed

**Triage:** ready-for-agent

## What to build

A manager can recover the same uncertain Revolut refund after a reload even
when loading the original sale temporarily fails. The existing return payment
line, its identity and its financial protection survive until the server
establishes the refund outcome.

## Observed problem

The integrated-revision audit on 2026-09-25 at `086dd12` reproduced a lost
refund-start response followed by failure to reload original sale records.
The browser discarded the started refund line before querying its operation,
removed its exposure guards and displayed a preparation error saying no refund
was sent. Server settlement still rejected the missing active allocation;
this finding does not demonstrate a duplicate provider dispatch or successful
cash substitution.

## Acceptance criteria

- [x] A failed or timed-out original-sale read preserves a started or uncertain refund line, its original order/payment-line UUIDs and any known references. It cannot convert uncertainty into an unstarted or safely replaceable allocation.
- [x] The cashier sees an interrupted/recoverable outcome without a false claim that no refund was sent. Deletion, alternative tender and checkout remain guarded while the refund outcome is uncertain.
- [x] Retrying status recovery after connectivity returns discovers or polls the same server operation and restores its final result and references. No second refund mutation, replacement identity or idempotency key is created.
- [x] Preserve legitimate preparation dismissal before dispatch and replacement of a server-confirmed failed allocation. Verified sibling allocations remain intact; payment and refund rules retain their distinct behavior.
- [x] Add a controlled lifecycle regression for a started refund with a lost response and no local operation snapshot, followed by an original-sale loading failure. Exercise known-reference recovery as well, and assert observable line preservation and permitted actions through the lifecycle interface.
- [x] Exercise the failure and subsequent recovery through the actual POS reload workflow with mocked provider calls. Assert retained identity, exactly one refund dispatch, correct receipt references and verified return settlement; retain the server's missing-allocation rejection coverage.
- [x] Update recovery guidance if the visible message or procedure changes, and record focused lifecycle/browser results plus affected regression checks on the reviewed implementation revision.

## Blocked by

- None. Existing refund and POS lifecycle foundations are implemented. Tickets 02, 17 and 18 do not gate this mocked software correction.

## Release gate

Blocks ticket 12 — Validate real terminal payments and publish release evidence.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown, requested publication
directly under ready-for-agent, and required all three corrections before
ticket 12. This ticket is independently actionable with mocked provider calls.
Its declared work branch has been created. Update it from the latest reviewed
main before starting; use an isolated worktree for concurrent implementation.

## Verification evidence

Implemented and reviewed on `codex/16-preserve-uncertain-refund-recovery` at
`faf57d2` against `main`. Original-sale read failures now preserve a refund
with a prior start or surviving operation/reference evidence, report an
interrupted or timed-out outcome, and keep financial guards active. A status
retry finds or polls the same server operation. A genuinely unstarted refund
still dismisses on preparation failure. No provider request was made outside
mocked tests.

Verification on Odoo `19.0.20260908`:

- Controlled lifecycle: `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`
  passed 12 tests, including a lost start response with no local snapshot,
  a surviving reference with no start flag, known-reference timeout recovery,
  preparation dismissal, payment retry and verified refund behavior.
- Focused Odoo run: `./scripts/test-addon --test-tags
  /pos_revolut:TestRevolutVerifiedCheckout.test_lost_refund_response_recovers_after_reload_without_second_refund,/pos_revolut:TestRevolutRefund.test_missing_active_refund_allocation_cannot_settle_return`
  passed 2 tests. The browser tour reloads POS, fails the original-sale read,
  retains the return/payment UUIDs and guards, then recovers the refund. The
  server test rejects a missing active allocation.
- Full `./scripts/test-addon` on `faf57d2`: 144 passed, 0 failures, 0 errors,
  including all browser tours and refund/payment regressions. `node --check`
  on the changed application and tour files, Python compile checks, and
  `git diff --check` passed.
- Two-axis standards/spec review on `faf57d2` found no remaining code issue.
  The recovery procedure is documented in `docs/installation.md`.

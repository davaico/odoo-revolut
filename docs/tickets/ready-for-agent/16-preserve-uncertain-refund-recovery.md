# 16 — Preserve uncertain refunds when original-sale recovery fails

**Work branch:** `codex/16-preserve-uncertain-refund-recovery`

**State:** claimed

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

- [ ] A failed or timed-out original-sale read preserves a started or uncertain refund line, its original order/payment-line UUIDs and any known references. It cannot convert uncertainty into an unstarted or safely replaceable allocation.
- [ ] The cashier sees an interrupted/recoverable outcome without a false claim that no refund was sent. Deletion, alternative tender and checkout remain guarded while the refund outcome is uncertain.
- [ ] Retrying status recovery after connectivity returns discovers or polls the same server operation and restores its final result and references. No second refund mutation, replacement identity or idempotency key is created.
- [ ] Preserve legitimate preparation dismissal before dispatch and replacement of a server-confirmed failed allocation. Verified sibling allocations remain intact; payment and refund rules retain their distinct behavior.
- [ ] Add a controlled lifecycle regression for a started refund with a lost response and no local operation snapshot, followed by an original-sale loading failure. Exercise known-reference recovery as well, and assert observable line preservation and permitted actions through the lifecycle interface.
- [ ] Exercise the failure and subsequent recovery through the actual POS reload workflow with mocked provider calls. Assert retained identity, exactly one refund dispatch, correct receipt references and verified return settlement; retain the server's missing-allocation rejection coverage.
- [ ] Update recovery guidance if the visible message or procedure changes, and record focused lifecycle/browser results plus affected regression checks on the reviewed implementation revision.

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

The audit reproduced the behavior through the production lifecycle with an
adapter matching the existing line-removal guard. A complete browser regression
for this failure remains part of this ticket. Implementation has not started.

# 20 — Recover POS lines after a failed pre-payment lookup

**Work branch:** `codex/20-recover-undispatched-pos-lines`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-20`

**Parallel work:** Only T20 and T21 run in parallel; coordinate shared-file edits and check for conflicts before merging.

**State:** closed

**Triage:** ready-for-agent

**Priority:** P2

## What to build

A cashier or refund-authorized manager can recover a new payment line after
its initial read-only operation lookup fails, without abandoning the order.
The POS distinguishes a request that never attempted a financial start from
an existing or possibly dispatched payment/refund, keeping uncertain money
protected while allowing genuinely undispatched lines to recover normally.

## Observed problem

The integrated audit on 2026-09-28 at revision `9bc9a0a` reproduced the initial
lookup failing before any payment/refund start call. The lifecycle nevertheless
retained a started flag. Subsequent lookups returning no operation could not
recover the line; deletion, amount editing, alternative tender and checkout
remained blocked, and there was no server operation for manager reconciliation.
This is an availability defect, not demonstrated duplicate charging.

## Acceptance criteria

- [x] For both payments and refunds, an initial discovery exception or timeout before any attempted financial start does not permanently classify the line as having uncertain dispatched money. After connectivity returns, the user can resume the normal first-start flow or safely remove the genuinely undispatched line and choose another tender.
- [x] Base that distinction on actual lifecycle history and surviving evidence. A missing lookup result alone cannot prove that an earlier start was never sent. Preserve the order/payment-line identity, prior references and guards whenever a start may have been attempted or an operation is discovered.
- [x] Keep protective UI behavior while discovery is in progress and preserve same-line request coalescing. A late lookup response, repeated click or cancellation racing the lookup cannot start duplicate work, restore stale state or falsely mark the line paid. Recovery after a rejected lookup and after a timeout is covered separately.
- [x] Preserve refund authority, original-sale restoration, allocation selection and safe preparation dismissal. Keep ticket 16's protection for a lost refund-start response followed by an original-sale read failure, including surviving references without a local start snapshot, and retain the no-cancel rule for dispatched refunds.
- [x] User-facing messages and permitted actions reflect whether a financial start was actually attempted. A recoverable preparation failure must not indefinitely instruct the user to reconcile a nonexistent operation. Only verified server evidence permits successful payment response and settlement.
- [x] Add controlled lifecycle regressions for payment and refund discovery failure, timeout, subsequent empty/successful discovery, late responses and reload/state restoration. Assert observable recovery actions, stable identity and exactly one start only when explicitly resumed. Include lost-start-response controls proving that uncertainty remains protected.
- [x] Exercise the defect and successful recovery through the actual POS adapter/browser flow with mocked provider calls: an initial read-only lookup fails, normal interaction resumes, and the eventual payment or refund settles with the correct references and no duplicate mutation. Preserve ordinary cash/bank checkout and existing cancellation/reload regressions.
- [x] Record the reviewed revision and focused lifecycle/browser plus affected payment/refund regression results. Update recovery guidance if messages or procedures change. All automated financial calls remain mocked or blocked.

## Blocked by

- None. Existing lifecycle and refund recovery foundations are implemented. Tickets 02, 19 and 21 do not gate this mocked correction.

## Release gate

Blocks ticket 12. Integrate and review this correction before live acceptance.

## Scope and execution

Addresses audit finding 3. Keep the existing lifecycle/Odoo-adapter split and
distinct payment/refund rules. No new terminal contract or financial retry
policy is introduced.

The declared work branch has been created from the committed ticket baseline.
Update it from reviewed main before implementation without overwriting existing
work. Use an isolated worktree for concurrent work.

## Verification evidence

Implemented and independently reviewed at
`b6834e1b781d71d641e6f4ece2155decb9a02e64`, based on latest reviewed main
`5081551d77a5db6d62b84965f5c115bd8f3cb236`. The lifecycle records undispatched
preparation separately from attempted starts and discovered operations. POS
offers Retry or safe removal for failed first discovery and retains Check
status plus financial guards for uncertain money. Refund authority, allocation
selection and original-tender restrictions remain intact.

On pinned Odoo `19.0.20260908`: 27 controlled lifecycle tests, 9 focused
browser/refund regressions, 189 full tests after install, 189 after upgrade,
and 8 Restaurant tests passed. The interrupted first Restaurant stage was
completed in a separate narrow run, which also passed retail startup after
install and upgrade. Syntax/Python compile and diff checks passed. All
financial calls were mocked or blocked.

Standards review: no hard violations, one accepted minor duplication
observation. Spec review: no findings. Recovery guidance for addon version
`19.0.1.7.3` is in `docs/installation.md`. Detailed commands, revision evidence,
review reports and the self-evaluation are recorded in the
[ticket 20 verification report](../../testing/ticket-20-undispatched-recovery.md).

## Triage decision

2026-09-28: The owner approved this three-ticket breakdown and direct
publication as ready-for-agent. All three corrections are independently
actionable with mocked provider calls and block ticket 12. Recommended priority
is 19, then 20, then 21; this is not a dependency chain.

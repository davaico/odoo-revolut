# 20 — Recover POS lines after a failed pre-payment lookup

**Work branch:** `codex/20-recover-undispatched-pos-lines`

**State:** open

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

- [ ] For both payments and refunds, an initial discovery exception or timeout before any attempted financial start does not permanently classify the line as having uncertain dispatched money. After connectivity returns, the user can resume the normal first-start flow or safely remove the genuinely undispatched line and choose another tender.
- [ ] Base that distinction on actual lifecycle history and surviving evidence. A missing lookup result alone cannot prove that an earlier start was never sent. Preserve the order/payment-line identity, prior references and guards whenever a start may have been attempted or an operation is discovered.
- [ ] Keep protective UI behavior while discovery is in progress and preserve same-line request coalescing. A late lookup response, repeated click or cancellation racing the lookup cannot start duplicate work, restore stale state or falsely mark the line paid. Recovery after a rejected lookup and after a timeout is covered separately.
- [ ] Preserve refund authority, original-sale restoration, allocation selection and safe preparation dismissal. Keep ticket 16's protection for a lost refund-start response followed by an original-sale read failure, including surviving references without a local start snapshot, and retain the no-cancel rule for dispatched refunds.
- [ ] User-facing messages and permitted actions reflect whether a financial start was actually attempted. A recoverable preparation failure must not indefinitely instruct the user to reconcile a nonexistent operation. Only verified server evidence permits successful payment response and settlement.
- [ ] Add controlled lifecycle regressions for payment and refund discovery failure, timeout, subsequent empty/successful discovery, late responses and reload/state restoration. Assert observable recovery actions, stable identity and exactly one start only when explicitly resumed. Include lost-start-response controls proving that uncertainty remains protected.
- [ ] Exercise the defect and successful recovery through the actual POS adapter/browser flow with mocked provider calls: an initial read-only lookup fails, normal interaction resumes, and the eventual payment or refund settles with the correct references and no duplicate mutation. Preserve ordinary cash/bank checkout and existing cancellation/reload regressions.
- [ ] Record the reviewed revision and focused lifecycle/browser plus affected payment/refund regression results. Update recovery guidance if messages or procedures change. All automated financial calls remain mocked or blocked.

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

Audit evidence only: a controlled adapter reproduction executed the production
lifecycle for payments and refunds. The first find call threw, later finds
returned no operation, and cancellation was attempted. Assertions confirmed
zero start calls and retained blocking actions. The audit did not run this new
case as a browser tour; that stronger regression is required above. Fix
implementation has not started.

## Triage decision

2026-09-28: The owner approved this three-ticket breakdown and direct
publication as ready-for-agent. All three corrections are independently
actionable with mocked provider calls and block ticket 12. Recommended priority
is 19, then 20, then 21; this is not a dependency chain.

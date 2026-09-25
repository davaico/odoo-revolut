# 14 — Deepen POS payment state

**Work branch:** `codex/14-deepen-pos-payment-state`

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

Preserve cashier payment and manager refund behavior across start, polling, cancellation, timeout, reload, and checkout while giving the POS payment state module ownership of transitions and permitted actions. Odoo hooks should consume that knowledge instead of independently combining flags and correcting each other's results.

## Approved design

The owner approved these decisions during the architecture discussion:

- **Own the complete browser-side lifecycle.** The module coordinates requests,
  polling, cancellation, deadlines, reload recovery, result ordering, and
  permitted actions. Extracting state predicates alone leaves the coordination
  problem in callers and does not satisfy this ticket.
- **One lifecycle owner per payment line.** Identify the logical line by its
  stable order and payment-line UUIDs. Its owner coordinates replacement
  attempts as well as the current attempt; order-level guards aggregate the
  lines' states. A verified split-tender line remains intact while another line
  is pending. Reload reconstructs ownership and reconciles the existing server
  operation rather than relying on surviving browser promises.
- **Share coordination, keep payment/refund rules explicit.** Both flows share
  waiting, recovery, and stale-response protection. Their permitted actions
  remain distinct: payments can sometimes be cancelled, dispatched refunds
  cannot, and replacing a failed refund requires a new payment line. Callers
  consume these decisions instead of reconstructing the differences.
- **Keep Odoo presentation in an adapter.** Screens, dialogs, allocation
  selection, and receipt rendering stay with the Odoo hooks. The lifecycle
  module owns the payment decisions behind them; server verification remains
  authoritative. Preserve the existing restaurant exposure seam and normal
  checkout behavior.
- **Test the lifecycle interface and the Odoo adapter.** Add controlled reply
  and time adapters for deterministic lifecycle tests, while retaining the
  existing browser tours for framework integration. Tests exercise the same
  lifecycle interface as callers rather than private state helpers.

## Acceptance criteria

- [x] Concentrate the complete browser-side lifecycle behind one POS payment state seam. Payment-line and screen hooks no longer duplicate request coordination, result-ordering rules, or the relevant flag combinations.
- [x] A logical payment line has one lifecycle owner across repeated actions and replacement attempts. Distinct lines remain independent; order-level guards aggregate their states, preserving verified split-tender allocations while another line is pending.
- [x] Repeated requests, reload, and reconnect recover the same payment or refund operation. Losing browser state or reaching the foreground deadline does not authorize another financial dispatch.
- [x] Delayed poll, cancellation, and foreground-failure responses cannot regress a verified result. Preserve the existing bounded wait and the handling of late success through the normal unchanged-order checkout path.
- [x] Amount edits, line deletion, alternative tender, force completion, and restaurant order changes retain their existing protections for unresolved or verified exposure. Preserve existing permitted operations and ordinary non-Revolut checkout.
- [x] Refund allocation selection, dismissal before dispatch, failed-allocation replacement, and unresolved-refund recovery retain their distinct behavior. Preserve completed refund allocations and their references.
- [x] Server verification remains authoritative for payment success and settlement. Browser recovery and receipt state cannot turn intent completion or a local timeout into payment success or retry safety.
- [x] Controlled lifecycle tests explicitly deliver verified success followed by an older failure, race polling against cancellation, and advance time through a foreground deadline. Assert observable outcomes and permitted actions: success survives, uncertain operations stay protected, and repeated actions do not duplicate dispatch.
- [x] Preserve browser tours for verified checkout, reload recovery, cancellation, cancellation races, refund recovery, and restaurant guards. Verify the Odoo adapter still produces correct status, checkout, receipt references, and payment/refund-specific actions.
- [x] Demonstrate payment recovery after reload and a cancellation-versus-success race, with correct receipt references and no duplicate dispatch. Record focused test results and describe the removed caller knowledge; use mocked provider calls throughout.

## Blocked by

- None. Existing server behavior supplies the required contract; this ticket does not require Return allocation or payment outcome application to be refactored first.
- No external blocker for mocked development. Coordinate shared acceptance-test edits during integration without inventing a sequencing dependency.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown and requested triage.
Ready for an agent: the workflow, preservation constraints, and verification
criteria are specified; there are no unmet ticket or external blockers for
mocked development. Claim the work and update its existing work branch from the latest
reviewed main before implementation. Use a separate worktree for concurrent work.

## Verification evidence

`revolut_payment_state.js` now owns the order/payment-line UUID lifecycle,
in-flight request and cancellation coalescing, operation discovery and
replacement, polling, deadlines, result ordering, reload recovery, and
payment/refund action decisions. The Odoo adapter retains RPC wiring,
allocation and error dialogs, receipt text, and normal screen invocation.
`PaymentRevolut` no longer has its own request/cancellation maps, deadline
loop, or result merge rule. Payment, order, and screen hooks consume the
module's line and order decisions; the restaurant exposure export still
delegates to that same seam. The server remains the sole authority for
verified payment and refund results.

Verification on pinned Odoo 19.0.20260908 with mocked Revolut HTTP calls:

- `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`:
  8 passed. Controlled replies cover both cancellation/poll arrival orders,
  an uncertain start through the 60-second foreground deadline and reload,
  same-line safe replacement, independent split-tender lines, refund dismissal,
  and refund recovery. The poll-verifies-then-cancellation-fails test failed
  before the review fix and passed afterward.
- `./scripts/test-addon --test-tags
  '/pos_revolut:TestRevolutManagerUi.test_manager_configures_and_checks_terminal_in_browser,/pos_revolut:TestRevolutVerifiedCheckout.test_declined_payment_can_retry_once_without_duplicate_charge,/pos_revolut:TestRevolutVerifiedCheckout.test_reload_recovers_late_success_without_new_charge,/pos_revolut:TestRevolutVerifiedCheckout.test_cancel_racing_with_capture_preserves_successful_payment,/pos_revolut:TestRevolutVerifiedCheckout.test_manager_returns_full_revolut_sale_in_normal_pos_flow,/pos_revolut:TestRevolutVerifiedCheckout.test_lost_refund_response_recovers_after_reload_without_second_refund'`:
  6 passed. The changed tours assert the payment or refund reference in the
  rendered terminal receipt. An earlier single verified-checkout tour also
  passed.
- Final `./scripts/test-addon`: 129 of 130 passed; the retail POS startup
  tour timed out before its first screen appeared. That same tour passed
  alone (1 of 1) with no code change. A preceding full run had 128 of 130
  pass, with manager-setup and declined-payment tours timing out during
  browser startup; both passed in the focused six-tour rerun. No payment or
  refund assertion failed in either full run.
- `node --check` on both changed application modules and the acceptance tour,
  plus `git diff --check`, passed. No JavaScript typechecker is configured.

The two-axis review found no code-level standards breach. Its spec review
identified the cancellation-error-after-verification race, now covered by the
controlled test and fixed. The remaining duplicated promise cleanup is a
judgement-call style observation; payment, screen, and cancellation promises
have separate completion semantics. No live provider or terminal was used.

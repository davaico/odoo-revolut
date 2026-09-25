# 14 — Deepen POS payment state

**Work branch:** `codex/14-deepen-pos-payment-state`

**State:** claimed

**Triage:** ready-for-agent

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

- [ ] Concentrate the complete browser-side lifecycle behind one POS payment state seam. Payment-line and screen hooks no longer duplicate request coordination, result-ordering rules, or the relevant flag combinations.
- [ ] A logical payment line has one lifecycle owner across repeated actions and replacement attempts. Distinct lines remain independent; order-level guards aggregate their states, preserving verified split-tender allocations while another line is pending.
- [ ] Repeated requests, reload, and reconnect recover the same payment or refund operation. Losing browser state or reaching the foreground deadline does not authorize another financial dispatch.
- [ ] Delayed poll, cancellation, and foreground-failure responses cannot regress a verified result. Preserve the existing bounded wait and the handling of late success through the normal unchanged-order checkout path.
- [ ] Amount edits, line deletion, alternative tender, force completion, and restaurant order changes retain their existing protections for unresolved or verified exposure. Preserve existing permitted operations and ordinary non-Revolut checkout.
- [ ] Refund allocation selection, dismissal before dispatch, failed-allocation replacement, and unresolved-refund recovery retain their distinct behavior. Preserve completed refund allocations and their references.
- [ ] Server verification remains authoritative for payment success and settlement. Browser recovery and receipt state cannot turn intent completion or a local timeout into payment success or retry safety.
- [ ] Controlled lifecycle tests explicitly deliver verified success followed by an older failure, race polling against cancellation, and advance time through a foreground deadline. Assert observable outcomes and permitted actions: success survives, uncertain operations stay protected, and repeated actions do not duplicate dispatch.
- [ ] Preserve browser tours for verified checkout, reload recovery, cancellation, cancellation races, refund recovery, and restaurant guards. Verify the Odoo adapter still produces correct status, checkout, receipt references, and payment/refund-specific actions.
- [ ] Demonstrate payment recovery after reload and a cancellation-versus-success race, with correct receipt references and no duplicate dispatch. Record focused test results and describe the removed caller knowledge; use mocked provider calls throughout.

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

Implementation not started. The owner requested recording the approved design
in this ticket only. This ticket describes a behavior-preserving refactor
opportunity, not a confirmed payment defect.

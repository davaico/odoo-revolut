# 14 — Deepen POS payment state

**Work branch:** `codex/14-deepen-pos-payment-state`

**State:** open

**Triage:** ready-for-agent

## What to build

Preserve cashier payment and manager refund behavior across start, polling, cancellation, timeout, reload, and checkout while giving the POS payment state module ownership of transitions and permitted actions. Odoo hooks should consume that knowledge instead of independently combining flags and correcting each other's results.

## Acceptance criteria

- [ ] Concentrate result ordering, foreground request coordination, recovery state, and permitted actions behind one POS payment state seam. Payment-line and screen hooks no longer duplicate the relevant flag-combination rules.
- [ ] Repeated requests, reload, and reconnect recover the same payment or refund operation. Losing browser state or reaching the foreground deadline does not authorize another financial dispatch.
- [ ] Delayed poll, cancellation, and foreground-failure responses cannot regress a verified result. Preserve the existing bounded wait and the handling of late success through the normal unchanged-order checkout path.
- [ ] Amount edits, line deletion, alternative tender, force completion, and restaurant order changes retain their existing protections for unresolved or verified exposure. Preserve existing permitted operations and ordinary non-Revolut checkout.
- [ ] Refund allocation selection, dismissal before dispatch, failed-allocation replacement, and unresolved-refund recovery retain their distinct behavior. Preserve completed refund allocations and their references.
- [ ] Server verification remains authoritative for payment success and settlement. Browser recovery and receipt state cannot turn intent completion or a local timeout into payment success or retry safety.
- [ ] Preserve browser tours for verified checkout, reload recovery, cancellation, cancellation races, refund recovery, and restaurant guards. Exercise delayed-result ordering through the module's behavior where additional coverage is needed; keep browser tests for Odoo hook integration.
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

Not started. This ticket describes a behavior-preserving refactor opportunity, not a confirmed payment defect.

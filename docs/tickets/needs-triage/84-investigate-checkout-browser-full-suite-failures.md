# 84 — Investigate full-suite checkout browser failures

**State:** open

**Triage:** needs-triage

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Related:** [77 — Company credentials](../closed/77-manage-company-revolut-credentials-in-odoo.md)
and [81 — Release validation](../ready-for-agents/81-prepare-odoo-sh-production-release-pr.md).

**Blocked by:** None.

**External blockers:** Reproduction needs a controlled host with available CPU,
memory and swap headroom. No live Merchant account or terminal is needed.

## Observation

The complete Odoo Community 18 suite on
`6fbea9d7a78e96a4684ef2679934c40079345f48` ran 811 cases with three failures,
zero errors and one optional `pos_hr` skip. Every new credential case passed.
The three existing `TestRevolutVerifiedCheckout` tests failed late in the run:

- `test_verified_card_first_rounds_only_the_remaining_cash`: overall browser
  script timeout during receipt validation.
- `test_verified_saved_refund_checkout_rejection_recovers_without_second_refund`:
  the tour could not find its initial POS login control.
- `test_verified_saved_refund_checkout_timeout_recovers_without_second_refund`:
  the combined assertion reported financial verification completing checkout
  before canonical restoration.

All three passed unchanged on isolated reruns: the first two together on a fresh
database and the third on that retained database. No timeouts or financial
assertions were relaxed. Full-run log: `/tmp/ticket77-full.log`; rerun logs:
`/tmp/ticket77-recheck.log` and `/tmp/ticket77-recheck-timeout.log`.
[Verification commands](../../testing/ticket-77-company-credentials.md) retain
the runtime, temporary network configuration and test tags.

Host load above 100 and full swap were observed during investigation. This is
context, not an established cause. The third failure follows unchanged
`pos.order.revolut_checkout_state` and does not invoke credential resolution.
Its tour waits three seconds for a held RPC response while restoration allows
five seconds. The combined assertion does not reveal which condition failed.

## Investigation and acceptance

- [ ] Reproduce the affected tests under controlled resources on the candidate
  and a temporary `bcc2f9395a931fae9f90e3d8979165ae2272e293` addon snapshot with
  the same pinned Odoo image and mocked provider HTTP.
- [ ] If the restoration assertion repeats, capture identical temporary
  diagnostics on both revisions: response-release presence, attempt counts,
  payment-line status, order state, receipt presence and elapsed time.
- [ ] Distinguish a runtime defect from fixture/timing or environment effects;
  retain financial finality and duplicate-operation assertions.
- [ ] Obtain clean full release-candidate evidence or document the established
  defect and gate release accordingly. Isolated successes do not turn the
  original full run green.

## Verification evidence

Reported on 2026-10-30 during ticket 77. Cause remains unestablished. This ticket
does not claim a credential regression or authorize deployment/live operations.

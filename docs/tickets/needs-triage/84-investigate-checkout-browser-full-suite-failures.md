# 84 — Investigate full-suite checkout browser failures

**State:** open

**Triage:** needs-triage

**Work branch:** `staging/18-enterprise`; base further task branches on its
latest reviewed revision and integrate back there. Do not push to `18.0`.

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


## Comments

### 2026-11-02 — Ticket 79 candidate

The full suite on addon source
`0fd1ae777efeb6b879f02c0c6d0ecf18ff3903c0` (`18.0.1.0.8`) ran **815 cases,
two failures, zero errors and two skips**, exit 1. All three ticket 79 native
configuration cases passed in that run. Additional existing-tour observations:

- `TestRevolutRefundHistory.test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund`:
  tour `pos_revolut_unavailable_original_refund` reached refund confirmation,
  then timed out waiting for `.pos .receipt-screen`; browser shutdown also
  timed out. This does not establish the provider/native financial outcome.
- `TestRevolutTakeoutReadinessUi.test_captured_tender_finishes_after_native_scheduling_correction`:
  tour `pos_revolut_takeout_captured_scheduling_recovery` exceeded its overall
  script timeout.
- `TestRevolutRetailPosStarts.test_retail_pos_starts_with_addon_installed` was
  skipped after a Chrome connection error. The other skip was optional `pos_hr`.

After incorporating staging's routing-only `eff53ba` (identical addon bytes),
both failed cases passed together, including their original financial/native
assertions, and retail startup passed separately with no skip. No application
or test assertions/timeouts were changed for these reruns. Full log:
`/tmp/ticket79-full-container.log`; actual exit: `/tmp/ticket79-full-exit`;
reruns: `/tmp/ticket79-recheck.log`, `/tmp/ticket79-retail-recheck.log`.
[Commands and evidence](../../testing/ticket-79-configuration-workflow.md).

Review found no concrete change-caused link: #79 changes backend configuration
views/metadata and its own tours, not the failing POS paths or shared fixture.
The French test ran after both failures. Host memory/swap pressure was observed,
but root cause remains unestablished. The full result remains red and #81 is
explicitly gated by this open ticket. Do not weaken financial assertions or
close this issue based on isolated successes.

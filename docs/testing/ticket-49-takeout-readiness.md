# Ticket 49 — Timed Takeout payment readiness

Implementation starts from `main` at
`6a973d566f39eb7de0677a98fab3cc6fcaf4f57c`, in the isolated
`codex/49-check-takeout-readiness` worktree. All provider traffic is mocked in
the disposable Odoo 19.0.20260908 test image. The original live
order63/tender83/operation77 is untouched; no staging deployment or live charge
is part of this work.

Final verification on `556782e`: **19 focused tests passed**; the full suite
completed **653 passed / 1 browser timeout / 0 errors (654 total)**, and the
timed-out test **passed alone on unchanged source**. All ticket 49 regressions
passed in both the focused matrix and the full run. The timeout remains
recorded below rather than being presented as a clean full-suite pass.

## Diagnosis before implementation

The first native browser reproducer reached the reported failure sequence:
`revolut_start_payment`, verified capture at native `PosPayment.pay`, then
`OrderPaymentValidation.validateOrder` all observed `preset_time = false`.
Automatic validation was invoked; native validation displayed **Slot required**
and kept the order Draft with its successful tender. Selecting an available
pickup time through Odoo's native picker and pressing Validate reached the
POS sales receipt. The tour's final identity assertion needed correction, so
this initial run is evidence of the failure sequence, not a passing recovery
regression.

The baseline ran against the starting product revision, with the new mocked
fixture, before either readiness guard was implemented:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-reproducer scripts/test-addon \
  --test-tags '/pos_revolut:TestRevolutTakeoutReadinessUi.test_missing_slot_native_reproducer_and_same_tender_recovery'
```

It failed at the final receipt-identity assertion (step 24/24), at 11:42:21 UTC.
The initial local log was overwritten by later diagnosis retries; the executed
phase and Draft assertions above are preserved in this report. The baseline
tour was then replaced by the three focused regressions in the implementation.

The first server regression failed as expected: preparation accepted a timed
Takeout order without a pickup time (`UserError not raised`). This establishes
that both payment preparation and native completion allowed collection to
precede scheduling readiness. The observed live slot-selection timing remains
unknown; the mocked sequence proves the missing-slot failure path.

## Boundaries

New payment preparation and new-operation admission must require the timed
preset's pickup time. Existing payment discovery, status checks and captured
checkout recovery remain accessible. Pickup time remains scheduling data and
is not added to the immutable financial fingerprint. Odoo continues to own
calendar slot selection and final native order validation.

## Verification

Initial implementation commit: `ae9969d80dc80371c429a3af5837b15b72021027`.
Final tested runtime revision: `556782e61f808c4e77278ad370c721023eb6c482`,
which integrates ticket 47's approved merged main `5793723`. The approved
review base remains `6a973d5`; the ticket 49 patch is also isolated against
merged main for the final integration review.

The project has no configured static type checker. Python compilation,
JavaScript module syntax checks, `git diff --check`, and both existing Node
payment-state/refund-allowance test files pass.

Server checks:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-server scripts/test-addon \
  --test-tags '/pos_revolut:TestRevolutRestaurantAuthority'
```

Final server result: **4 passed, zero failures/errors**, 2026-10-12
12:00:56 UTC (`/tmp/ticket49-server-authority-stable-green.log`). The preceding
red tests proved missing-slot preparation was accepted and direct admission
reached provider HTTP. Fixtures flush native draft writes and invalidate after
owned-cursor capture, matching separate POS RPCs; status comparisons retain
stable financial evidence rather than the observation-freshness flag.

The first broader focused run exercised 13 tests: 12 passed, and the captured
recovery tour reached receipt before the backend save completed. Its assertion
correctly rejected the server's still-Draft state. The native picker closes
before its asynchronous save completes; the committed tour now awaits the
public `openPresetTiming` action before Validate. The corrected
tour has now passed with its persisted backend Paid assertion; a receipt alone
is not counted as proof of checkout.

Browser runs that timed out attaching Chrome are excluded from passing
evidence. The host exhausted memory/swap during overlapping ticket 47/48/49
runs. Further Docker validation is serialized with those chats.

Client red command:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-client-red scripts/test-addon \
  --test-tags '/pos_revolut:TestRevolutTakeoutReadinessUi.test_missing_slot_blocks_new_financial_preparation_and_provider_dispatch'
```

Actual browser failure at 11:51:13 UTC confirmed one preparation RPC and zero
payment starts (`/tmp/ticket49-client-red.log`). The client guard now prevents
that preparation RPC as well as provider traffic.

Corrected native command, using an archive of the implementation commit:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-takeout-final scripts/test-addon \
  --addons-dir /tmp/ticket49-release/addons \
  --test-tags '/pos_revolut:TestRevolutTakeoutReadinessUi'
```

Result: **3 passed, zero failures/errors**, 2026-10-12 12:40:23 UTC
(`/tmp/ticket49-takeout-final.log`), with actual browser execution and no Chrome
startup skips. The native tours verify missing-slot zero preparation/provider
traffic and available-date selection, one-capture automatic Paid checkout,
and original captured-tender correction/status recovery/Paid completion.
Backend assertions confirm the same single verified operation, its original
payment reference, and exactly one provider order/intent creation pair.

The earlier focused 13-test matrix also passed ordinary untimed Dine In,
Restaurant ownership/merge guards, pending authorization cancellation,
invalid-snapshot correction after reload, and verified-checkout recovery.
Only its now-corrected scheduling-save race failed.

The first full run on `ae9969d` completed at 12:59:32 UTC with **627 tests,
2 failures and 1 error** (`/tmp/ticket49-full.log`). It found:

- The existing positive Takeout payload fixture had no native scheduling time.
  Its test now supplies an explicit `preset_time`; the fixture helper accepts
  that optional native field without adding it to financial identity or
  automatically filling negative tests (`0d6b680`).
- A static import of the POS-only validation class from the new tour prevented
  backend manager assets from loading. The tour now observes PaymentScreen
  validation through the runtime `pos_pages` registry (`014ecac`).
- The saved-refund offline checkout tour timed out at its Check status modal.
  No production change was made for that timeout; the integrated rerun below
  executes and passes that scenario.

After merging ticket 47, an immutable archive of `556782e` passed this focused
matrix:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-integrated-focused scripts/test-addon \
  --addons-dir /tmp/ticket49-integrated-release/addons \
  --test-tags '/pos_revolut:TestRevolutRestaurantContext,/pos_revolut:TestRevolutTakeoutReadinessUi,/pos_revolut:TestRevolutRestaurantAuthority,/pos_revolut:TestRevolutRestaurantPosStarts,/pos_revolut:TestRevolutManagerUi,/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_offline_loader_recovers_without_second_refund,/pos_revolut:TestRevolutVerifiedCheckout.test_missing_tip_preparation_reload_resumes_original_tender_once,/pos_revolut:TestRevolutVerifiedCheckout.test_delayed_native_preparation_cannot_start_after_same_tender_recovery'
```

Result: **19 passed, zero failures/errors**, 2026-10-12 13:09:18 UTC
(`/tmp/ticket49-integrated-focused.log`). Native browser execution occurred
without Chrome startup skips. This covers the corrected payload and manager
asset fixtures, saved-refund recovery, and ticket 47's reload/delayed-start
fencing alongside all ticket 49 regressions.

Final full-suite command on the same immutable runtime archive:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-integrated-full scripts/test-addon \
  --addons-dir /tmp/ticket49-integrated-release/addons
```

Result: **653 passed, 1 failed, zero errors, 654 total**, 2026-10-12
13:36:01 UTC. The container exit status was `1`. The original shell was
interrupted during this run, while its Docker test container continued;
`/tmp/ticket49-integrated-full-container.log` preserves the complete container
output and `/tmp/ticket49-integrated-full-exit.txt` records its exit status.
There were no Chrome-startup skips. All ticket 49 tests passed.

The sole failure was the existing
`TestRevolutVerifiedCheckout.test_completed_refund_recovers_from_saved_return_without_browser_state`:
its browser script timed out, then Chrome also failed to answer the shutdown
request; several Chrome processes were reported in disk sleep. This is not a
clean full-suite pass, and the timeout's cause is not established by that log.
The failed scenario was rerun alone on the identical runtime archive:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket49-refund-rerun scripts/test-addon \
  --addons-dir /tmp/ticket49-integrated-release/addons \
  --test-tags '/pos_revolut:TestRevolutVerifiedCheckout.test_completed_refund_recovers_from_saved_return_without_browser_state'
```

Isolated rerun: **1 passed, zero failures/errors**, 2026-10-12 13:37:48 UTC,
exit status `0` (`/tmp/ticket49-refund-rerun.log`). The native browser test
executed without startup skips. No source change was made between the full
run and this rerun. The timeout did not reproduce in isolation; this does not
establish its root cause. Both disposable test projects were cleaned up and
the agreed serial test window was released.

## Release gate

For rollout, upgrade `pos_revolut` to `19.0.1.18.14` and reopen POS to load
its browser assets. No credential rotation or data migration is introduced.
Ticket 47 is integrated here. Combine ticket 48 with this revision and validate
that combined revision before ticket 12's staging acceptance.

Ticket 12 still owns deployment and physical-terminal acceptance. This ticket
must not repeat a charge against the preserved live fixture or treat its
already observed manual recovery as valid-slot automatic checkout evidence.

## Review

### Standards

No documented-standard violations or actionable baseline smells found in the
original review or the integrated ticket 49 patch at `556782e`. The final
integration review also checked all three merge resolutions, preserving
ticket 47's recovery revision capture and exact-tender admission checks.
The final evidence and ticket closure follow the local tracker rules, retain
the tracked `.gitkeep`, and accurately record the full-suite limitation.
Standards findings: **0**.

### Spec

No implementation defects or unasked scope found. Client/server timing
predicates match native readiness, while existing-operation recovery remains
accessible. The corrected native recovery and integrated 19-test matrix are
verified. The full suite and the passing isolated rerun of its sole timeout are
recorded above. Final evidence review confirms that the implementation and
verification support closure, with the full-suite timeout limitation retained.
Spec findings: **0**; no outstanding ticket 49 verification requirements.

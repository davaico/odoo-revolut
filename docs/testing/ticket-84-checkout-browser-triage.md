# Ticket 84 — Checkout browser validation

Completed locally on 2026-11-02. Task branch:
`codex/84-checkout-browser-triage`. Reviewed starting base and integration target:
`staging/18-enterprise` at `fdfa74596f2445e0a54a1206cb28a052386cda01`.
Triage: `0257994`. Fixture correction: `fccfd12635b863b2761470afe920f3b7925c54e3`.
The tested addon tree is `0210304b5bdde70956001e78d03d4485c8cff420`, unchanged
through published documentation candidate `e0707f8` and the final handoff.

## Result and release gate

The corrected candidate completed **816 cases with zero failures and zero
errors**, exit 0, in approximately 28 minutes 46 seconds. The only skip was
`TestSharedPosSessionAccess.test_employee_list_does_not_restrict_backend_user_rpc`,
the existing optional `pos_hr` characterization. All ten affected browser cases
below succeeded; no Chrome connection skip was accepted.

[Ticket 84](../tickets/closed/84-investigate-checkout-browser-full-suite-failures.md)
is closed on this evidence. Its full-suite prerequisite for #81 is satisfied.
Ticket 81 remains open and blocked by hosted acceptance #80 and its remaining
release requirements. This local Community-image run is not Enterprise/Odoo.sh
lifecycle acceptance or production readiness.

The established defect was a false fixture assertion. The exact causes of the
broader historical browser stalls remain unestablished. Their original red
results remain red; this report does not assert a credential/configuration
regression or a payment-finality bypass.

## Correction and native red/green evidence

The recovery tour previously polled for three seconds before inspecting a held
canonical response, while native restoration allowed five seconds. A response
inside the native budget could miss the shorter fixture deadline. The combined
assertion then incorrectly reported financial prematurity without identifying
which condition failed.

The correction waits for the actual held-response notification or native request
completion. Its existing five-second restoration bound remains unchanged.
Separate errors identify duplicate restoration, premature checkout and native
completion before the response could be held. Diagnostics include response
presence, attempt count, payment status, order state, receipt presence and
elapsed time. No application payment code or financial assertion changed.

The new native saved-refund case delays canonical delivery by 3,200 ms and uses
the same real server interfaces, mocked provider and original server-side
refund assertions as the existing recovery cases. Identical temporary
`[DEBUG-T84]` diagnostics were applied to baseline and uncorrected-candidate
snapshots, then excluded from the corrected addon.

| Native phase | Result | Observed duration including installation | Sampled Odoo peak |
| --- | --- | --- | --- |
| Baseline `bcc2f9395a931fae9f90e3d8979165ae2272e293` with delayed tracer, original assertion | Expected failure: 1 failed, 0 errors, exit 1 | 81.13 s | 1.080 GiB |
| Uncorrected candidate with identical tracer | Expected failure: 1 failed, 0 errors, exit 1 | 86.40 s | 1.228 GiB |
| Unchanged baseline, six original browser cases | 6 passed, no failures/errors/skips, exit 0 | 137.26 s | 0.936 GiB |
| Corrected candidate, six original cases plus delayed-response regression | 7 passed, no failures/errors/skips, exit 0 | 147.20 s | 0.962 GiB |

Both native red traces showed response held `false`, exactly one restoration
attempt, payment status `waiting`, order state `draft`, no receipt and a
`verified` financial snapshot. The false assertion occurred at 3,006 ms on the
baseline and 3,007 ms on the uncorrected candidate. The corrected delayed case
completed the original saved refund with its original identity and exactly-once
financial/native effects; the original POST-count assertions passed.

A disposable harness loading the actual reconnect step also reproduced the
false assertion on both original tour sources. Its corrected-step probes still
reject simulated premature completion, duplicate restoration and a native
request settling without a held response. These harness probes are supplementary;
the native runs above provide the real browser/server evidence.

## Full-suite browser coverage

The full run verified success signals for all ten cases, alongside the complete
server assertions and final zero-failure/error summary:

- `TestRevolutVerifiedCheckout.test_verified_card_first_rounds_only_the_remaining_cash`
- `TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_rejection_recovers_without_second_refund`
- `TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_timeout_recovers_without_second_refund`
- `TestRevolutRefundHistory.test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund`
- `TestRevolutTakeoutReadinessUi.test_captured_tender_finishes_after_native_scheduling_correction`
- `TestRevolutRetailPosStarts.test_retail_pos_starts_with_addon_installed`
- `TestRevolutVerifiedCheckout.test_terminal_busy_inflight_snapshot_reconciles_after_reload_without_duplicate_charge`
- `TestRevolutVerifiedCheckout.test_terminal_busy_line_can_be_removed_for_cash_without_second_dispatch`
- `TestRevolutVerifiedCheckout.test_verified_payment_checkout_timeout_recovers_without_second_charge`
- `TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_waits_for_delayed_canonical_response`

The native six-case comparisons used the first six names; the corrected
seven-case comparison added the final delayed-response case. Native result
counts follow test methods and `odoo.tests.result`, not the statistics logger's
larger fixture-accounting count.

## Runtime and resources

All final native phases and the full suite used the same derived image:
`sha256:a138d2204f1249d295f99df82bd399706e7494e45d5a674b4e977ad8858b1c05`.
Package inspection confirmed Odoo Community `18.0.20261015`; browser logs
confirmed Chrome `153.0.8010.52`. PostgreSQL was the repository-pinned
`16.14-bookworm` image. The derived image's HTTP-guard files match the repository
byte-for-byte; the guard passed before every phase. The cached image tag had
changed since initial triage, so the temporary Compose copy was pinned to this
actual immutable image ID. Every result artifact records that same image.

Each phase used a fresh disposable database and volumes, an internal network
on explicit subnet `10.237.185.0/24`, a read-only addon snapshot, synthetic
credentials and `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`. Provider HTTP was mocked.
No real account, terminal, credentials or financial operation was used.

The start guard required at least 3 GiB available RAM, one-minute load at most 8
on this 16-CPU host, and memory full-pressure `avg10` below 1 percent. Containers
were limited to 3 GiB/4 CPUs for Odoo and 1.5 GiB/2 CPUs for PostgreSQL.
Memory-plus-swap limits equalled memory limits, explicitly disabling swapping.
This fulfills swap control without relying on the shared host's changing free
swap. Admission checks do not claim the host stayed idle throughout execution.

In the full run, sampled Odoo peak memory was 1.164 GiB and PostgreSQL's final
peak counter was 0.572 GiB. Recorded swap counters were zero. Sampled Odoo and
final PostgreSQL counters reported no memory-limit or OOM events; the containers
reported no OOM kill or restart. Host available RAM reached a minimum sampled
1.084 GiB; one-minute load ranged from 2.06 to 5.08. Resource observations alone
are not proof of the causes of earlier stalls.

Two monitoring clients ended with status 143 while detached Odoo kept running.
Monitoring resumed against that same container and later used direct checks;
there was **one full-suite invocation**, no retry or timeout/assertion relaxation.
Initial and final container identity was
`ade05a4b96518e1c9b8584e6ca4e74fb46b7cbf3af90e01c92e7665df813b638`, with zero
restarts. Resource samples were approximately five seconds apart during active
sampling, with gaps/client changes and later direct checks; they are not an
uninterrupted trace. The actual Docker exit status and full log were captured
independently. Task containers, volumes and networks were removed afterward.

## Commands and artifacts

`git archive` exported only the addon from recorded revisions into disposable
snapshot directories. A 172-file checksum inventory of the corrected snapshot
matches `fccfd12` exactly. The temporary Compose copy retained repository pins,
HTTP blocking and internal networking, used an absolute build context, pinned
the derived image ID above, and added the stated resource limits. No image was
rebuilt or pulled for these comparisons.

The full invocation was:

```bash
export ODOO_REVOLUT_ADDONS_DIR=/tmp/ticket84-implementation/candidate
compose=(docker compose -p odoo-revolut-ticket84-full -f /tmp/ticket84-implementation/compose.yaml)
"${compose[@]}" up --detach --wait db
"${compose[@]}" run --detach --no-deps --name odoo-revolut-ticket84-full odoo \
  --database odoo_revolut_tests --init pos_revolut --stop-after-init --workers 0 \
  --log-level warn --log-handler odoo.tests.result:INFO \
  --log-handler odoo.tests.stats:INFO --log-handler odoo.addons.pos_revolut:INFO \
  --test-tags /pos_revolut
```

Native invocations used the same Odoo arguments and runtime, fresh databases,
and comma-joined `/pos_revolut:<class>.<method>` tags from the coverage list.
Version and HTTP-guard checks preceded every phase. Before cleanup, finalization
required the zero-failure/error result, successful execution of all ten browser
cases and absence of unexpected skips. No isolated result replaced the full run.

Transient artifacts under `/tmp/ticket84-implementation/` include native
`*-command.json`, `*-result.json`, `*-resources.jsonl`, phase logs and snapshots;
`full-command.json`, `full-result.json`, `full.log`, `full-resources.jsonl`,
PostgreSQL state/resource records, browser artifacts and checksum inventories.
Temporary orchestration/monitoring scripts are retained there. The full verifier
checked the permitted `pos_hr` skip explicitly. This report preserves the result
if `/tmp` is cleared.

`node --test --test-isolation=none pos_revolut/static/tests/*.test.mjs` passed
**146 checks**, no failures/skips (`js-final.log`). Python compilation,
changed-tour JavaScript syntax and `git diff --check` passed. There is no
configured static type checker. Documentation-link and tracker checks accompany
the final handoff; syntax checks do not substitute for the native behavior above.

## Historical evidence and scope

The [ticket 77 record](ticket-77-company-credentials.md) retains its 811-case,
three-failure run and isolated successes. The [ticket 79 record](ticket-79-configuration-workflow.md)
retains its 815-case, two-failure run, Chrome startup skip and isolated successes.
Initial #84 triage also ran six unchanged cases successfully on candidate and
baseline using the earlier cached image; exhausted host swap prevented a
controlled-resource/full-suite conclusion at that time.

The additional ticket 80 local run used addon tree
`3218ad4a5803cddb4b7f7535b31cefd8510beb57`, identical to `fdfa745`; its task HEAD
`2fff881` added documentation only. Its log, retained as
`host-full-pre-fix.log`, reports 815 cases, two failures, zero errors and two
skips (optional `pos_hr` plus Chrome connection failure). A busy-inflight case
failed at the initial login control with a POS-loader screenshot; a checkout
case failed at its first Check-status modal, which appeared by the later failure
screenshot. Both occurred before the corrected held-response assertion. Host
memory/swap pressure was observed, but a causal link remains unestablished.
These cases subsequently succeeded inside the corrected full run.

Redundancy search covered checkout restoration, saved-refund/history, Takeout
and startup tests, and tickets 77–79's evidence. No prior completed investigation
or fix was found; no `.out-of-scope/` rejection records existed.

The same short fixture wait exists on released Community 18 and 19 branches.
Their application runtime behavior is unchanged by this staging-only fixture
correction; selective fixture backports and version-specific verification remain
separate. This work does not certify those lines or hosted Enterprise behavior.

## Independent review

Final independent review of `fdfa745...e0707f8` plus the closing evidence and
tracker delta found **Standards: 0 findings; Spec: 0 findings**. Native/full-suite
acceptance, preservation of financial assertions, honest historical limits,
closure of #84 and retention of #80's gate on #81 were verified. No remaining
implementation or validation requirement was identified for this ticket.

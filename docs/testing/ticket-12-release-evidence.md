# Ticket 12 — Release evidence and terminal acceptance handoff

**Live acceptance remains open.** This record covers software verification and
the operator procedure. Physical-device and financial checks below are **NOT
RUN** until an authorized operator records an observed result. Mocked success
does not establish terminal certification.

## Software candidate

Reviewed `origin/main` at `935d07713d519698d7a2cf9414900ec611675ff9` was fetched
on 2026-09-28. It contains the closed implementations for blockers 02, 11 and
16–21. As requested by the implement skill, this work stays on the current
branch, `codex/02-confirm-terminal-contract`, fast-forwarded to that baseline.

| Identity | Value |
| --- | --- |
| Exact tested candidate | `76209bb3c3ac705dcc724ba329e044c6626c59cd` |
| Base addon Git tree | `ad4eaaef8985cbe8d3ed0a596cac4586adea893a` |
| Restaurant bridge Git tree | `2b98f76f0adb34debc19ddbc3b4e75f030771fb7` |
| POS Revolut / Restaurant bridge versions | `19.0.1.7.5` / `19.0.1.0.0` |
| Odoo Community / PostgreSQL | `19.0.20260908` / `16.14` |
| Merchant API version | `2026-08-17` |
| Two-addon delivered archive SHA-256 | `472364a875c89f43c2cdceee58203528020c057c9cddb29e36fe712d80f4d476`; identical in both artifact scenarios |
| Independent payment-boundary review | Reproduced refund-classification finding corrected; no remaining actionable finding in the bounded re-review |

The [earlier payment safety audit](release-audit-2026-09-28.md) covered
`9bc9a0a`, before tickets 19–21. Its results are baseline evidence only.

The correction candidate includes all upstream blockers plus the acceptance
review fix below. It still needs integration into the reviewed release ref
before deployment; the deployer's reviewed-ref requirement remains mandatory.

## Independent boundary review and acceptance correction

A separate reviewer inspected public order/payment/line creation, changes,
deletion and finalization; underlying-payment identity/finality; permissions
and company isolation; uncertain retries/refunds; and malformed-response batch
recovery. The fixes and adversarial regressions for the earlier four audit
findings are present. Pinned Odoo source was inspected with networking disabled.
This is a bounded software review, not live certification or an infrastructure
penetration test.

The review found one additional return-classification candidate. A controlled
regression confirmed that a manager could reconfigure an original sale's
payment method after closing its session, then record a paid manual return
without any provider refund. Original manual-tender allowance now excludes
payments with a persisted Revolut operation, irrespective of later method
configuration. The original association remains protected by settlement
mutation guards. A separate re-review found no remaining actionable issue in
this correction; existing mixed-tender and verified-refund behavior is retained.

The regression uses a synthetic closed-session fixture and non-superuser
`call_kw` payment-method reconfiguration/return creation. It asserts atomic
rejection, preserved original evidence and zero provider requests. It does not
claim actual session accounting closure or an HTTP penetration test.

```bash
./scripts/test-addon --test-tags /pos_revolut:TestRevolutRefund.test_reconfigured_method_cannot_turn_original_revolut_into_manual_refund
./scripts/test-addon --test-tags /pos_revolut:TestRevolutRefund
```

On baseline product code, the first command failed with `UserError not raised`:
the forbidden return was accepted. After the correction, it passed (1 test,
zero failures/errors), and the affected refund class passed all 36 tests.
Both use the existing public-return seam. No new field, dependency, provider
mutation or credential change was introduced; version `19.0.1.7.5` uses the
normal stopped-service upgrade procedure.

## Automated acceptance — 2026-09-28

| Command | Result on the candidate |
| --- | --- |
| `./scripts/test-addon --verify-install-upgrade` | 208 fresh-install, 208 upgrade and 8 Restaurant tests passed; zero failures/errors |
| `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | 27 passed, zero failed/skipped |
| `python3 -m unittest discover -s tests -p 'test*.py'` | 29 passed |
| `./scripts/test-restart-recovery` | Passed across two Odoo processes; `RESTART_RECOVERY_OK` |
| `./scripts/test-deployment-guard` | Passed against actual disposable payment/refund rows; each blocker clears only after settlement |
| `./scripts/test-delivered-addon --revision 76209bb3c3ac705dcc724ba329e044c6626c59cd --scenario retail` | 2 retail tests, then 8 Restaurant tests after later installation; zero failures/errors |
| Same artifact command with `--scenario migration` | 8 base-only migration tests, then 8 bridge update tests; zero failures/errors |
| Python, JavaScript, XML, shell syntax and `git diff --check` | 32 Python files parsed, 7 JavaScript files syntax-checked, 6 XML files parsed and 2 shell runners checked; passed |

All seven runtime commands returned zero between **14:36:04 and 14:46:24 UTC**.
Repeated install/upgrade/artifact counts are executions, not additional unique
tests. No browser-tour skipping warnings occurred. The test credential and
synthetic cardholder/PAN canaries were absent from every runtime log. The
existing browser acceptance also scans exported POS data; this is mocked-data
evidence, not an inspection of a production credential or customer card.
Warnings include expected unresolved-state exercises, Odoo configuration and
Chrome crashpad cleanup; none caused a test failure.

The temporary orchestration wrapper included a generated cache directory in its
final syntax inventory after all runtime commands had succeeded. Source-only
syntax verification was corrected and rerun separately with the passing counts
above. No repository runner or addon failed. Disposable containers were cleaned
up. Local raw logs and command UTC/exit-code metadata are under
`/tmp/revolut-ticket-12-20260928/` (`results.json`); they are temporary execution
evidence, not portable repository fixtures.

The full suite includes adversarial regressions for ticket 19's public
order/payment/line mutations, settlement balance and lock permissions; ticket
20's failed/timed-out discovery, reload and no-replay recovery; and ticket 21's
malformed evidence, later healthy batch operations, transaction isolation and
backoff. It also exercises ticket 16's uncertain-refund reload, ticket 18's
company isolation and ticket 17's complete delivered Restaurant artifact.

All expected Merchant HTTP calls are mocked. Disposable runners verify the
Merchant HTTP guard before Odoo starts; Compose uses an internal network.
Artifact acceptance mounts only the extracted addons from the stated commit.
There is no configured static typechecker, linter or coverage measurement;
syntax checks complement runtime acceptance. No staging deployment, Merchant
account request, device operation, charge or live refund occurs in these runs.

### Standards

No documented-standard violations or actionable baseline smells. The correction
uses the established refund module and public RPC test seam. Candidate/tree
identities, documentation links, stopped-service upgrade guidance and tracker
updates follow the repository conventions.

### Spec

No remaining implementation findings or scope creep in the automated slice.
The correction closes the reproduced unverified-return path; the combined suite,
artifact identity and human checklist cover the ticket's software preparation.
Physical and financial results remain unexecuted and ticket 12 remains open.

Two-axis review uses fixed point `935d07713d519698d7a2cf9414900ec611675ff9`
and includes the correction plus its documentation/handoff. Standards: 0
findings; Spec: 0 findings; neither axis has a blocking finding.

## Operator preflight — verified for the GBP test session, 2026-09-29

The [operator observations](ticket-12-operator-observations.md) record the
authorized 2026-09-28 staging upgrade and successful Cash smoke, followed by
2026-09-29 device discovery, GBP configuration, financial authorization and
controlled terminal tests. Results below summarize the checkpoint at
**2026-09-29 13:42:07 UTC**; the dated chronology contains supporting references
and narrower limitations. Ticket 12 remains open. Recheck financial blockers
and device eligibility before another test or deployment.

The production Merchant account **Test Guzman**, Davai location and configured
terminal were verified for the isolated GBP test register. Authorization is
limited to the amounts recorded below; these observations do not authorize
additional spending or use of another account/device.

| Required observation | Recorded evidence |
| --- | --- |
| Operator, POS-manager account and UTC session start | PASS: Administrator / Odoo user `2`; session `5` opened at `2026-09-29 08:53:13 UTC` |
| Reviewed deployed SHA, archive checksum, running Odoo and addon versions | PASS on 2026-09-28: exact tested `76209bb` and matching checksum; Odoo `19.0.20260908`, base `19.0.1.7.5`; Restaurant uninstalled, bridge delivered; see operator observations |
| Database, company, currency and POS configuration/session | PASS: `revolut_staging`, company Davai; dedicated GBP POS `2`, session `5`; existing EUR register retained |
| Intended approved Merchant account and environment | PASS: Test Guzman production credential authenticated and returned the matching physical location/device; controlled GBP payments subsequently verified through Merchant GETs |
| Server-only secret reference | PASS: process variable `ODOO_REVOLUT_SECRET_TEST_GUZMAN_PRODUCTION`; systemd encrypted credential and server-process presence checked without disclosure; no browser credential |
| Matching physical location and configured terminal UUID | PASS: Davai location `7a531302-52af-4f7c-82c2-eaa6b2fe371b`, terminal `aec8020d-cdf6-4f16-a7f4-a6ca908a1f64`; see discovery evidence |
| Terminal app version, account login and internet connection | OBSERVED: operator reports app `1.102 (101)`, firmware `V1.0.37`, Test Guzman login and Wi-Fi; matching device returned online by Merchant discovery |
| Matching device location and Pay at Counter enabled | PASS: operator reported Davai and Pay at Counter; provider discovery matched location and `operation_mode=pos` |
| Manager **Check Connection** result and UTC time | PASS during GBP preparation; method `4` found the configured online terminal; UTC checkpoints in operator observations |
| Amount/currency per scenario, maximum exposure and refund plan | AUTHORIZED: original `0.01 GBP` charge/refund plus aggregate `0.10 GBP` in additional charges with refund plan; seven additional pence captured, three pence remain; refunds do not replenish the charge budget |
| Explicit owner authorization for real-money operations | Recorded owner approval in the guided session and operator chronology before paid scenarios; only the operator sent financial requests through POS/device |
| Backup/upgrade record, baseline Cash smoke and no unresolved existing operations | PASS on 2026-09-28: guarded upgrade and backup, Cash `261-1-000004` / `11.50 EUR`, zero financial blockers at postflight; recheck blockers before financial acceptance |

Device prerequisites follow the [Revolut terminal
guide](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments),
checked on 2026-09-28. Sandbox and production credentials/devices are separate;
the fixed Sandbox virtual terminal cannot identify the physical device. The
[contract record](../revolut-terminal-contract-2026-09-22.md) documents the
Sandbox simulator failure and the owner's interim retail `eat_in` mapping.
Do not create more Sandbox payment attempts while the provider issue remains
unresolved. No example amount here authorizes a production transaction.

## Controlled scenario matrix — partial live acceptance, 2026-09-29

Use a dedicated test session. Record each row's authorized amount and original
refundable balances, run one scenario at a time, and reconcile its references
before continuing. Record a provider-supported controlled method for decline,
failure or interruption first. If unavailable, record **NOT REPRODUCIBLE**, its
reason and next action; it remains an open release gap. Do not deliberately
create duplicate charges or induce uncontrolled network/device failures.
Record separate entries for each subcase, such as L03 dine-in/takeaway and L04
decline/failure; a pass for one does not cover the others.

| ID | Operator action | Required observed result | Result |
| --- | --- | --- | --- |
| L01 | Pay a full retail sale using interim `eat_in` | Device amount/currency match; only a verified `captured`/`completed` underlying payment completes the fully paid order; stored and receipt references agree | PASS for original one-penny sale `4`, with operator-confirmed automatic receipt; later automatic-status failures remain open |
| L02 | Pay Cash/Revolut split tender and multiple Revolut lines | Each request uses its line amount; verified partial payment keeps the order open; full balance completes; each line retains distinct references | PARTIAL: Cash/Revolut and two-Revolut-line allocations settled correctly after manual Check status; initial automatic status handling failed on operations `10`, `11`, `16`, `17` |
| L03 | Pay Restaurant dine-in and takeaway; resume an unchanged partially paid order | Correct `eat_in`/`take_away`; retained identity/references; guarded exposed split/merge/transfer; permitted same-order table move | NOT RUN |
| L04 | Produce controlled decline and provider failure, then safely retry | Distinct unpaid outcomes; provider-final evidence enables retry; predecessors retained and only one intended new charge | PARTIAL: controlled decline and safe cancellation observed; cancellation-to-paid retries passed; provider failure and decline-to-paid retry not run |
| L05 | Cancel pending payment using POS/device controls | Confirmed cancellation stays unpaid; processing/uncertain cancellation stays guarded; capture winning a race preserves verified success | PARTIAL: multiple no-card cancellations verified unpaid, including `18`; processing/capture-winning-race subcases not run |
| L06 | Exercise controlled interruption, local timeout and reload/late success | Original UUIDs and operation survive; no replacement charge/alternate tender while uncertain; status recovery resumes the same unchanged order | PARTIAL: single-attempt no-card reload/recovery/cancel and post-success refresh passed; broader network interruption/capture-to-persistence window not run |
| L07 | Repeat status checks and resume with another authorized cashier | Same operation/references, no extra financial mutation, serialized order/terminal exposure | PARTIAL: same-browser and independent-browser server guards passed under one account; independent-browser busy feedback/recovery FAILED; different-user resume and simultaneous-start race not run |
| L08 | Manager returns all of a designated original Revolut sale | Linked original/refund references; accepted/pending refund cannot finish return; only asynchronous verified completion settles | IN PROGRESS: original full one-penny refund `1` processing/unverified; guarded return remains open |
| L09 | Partially return a different sale with multiple Revolut allocations and mixed tender | Correct original allocations and reserved balances; original non-Revolut tender handles its share; final references and remaining balances agree | PARTIAL: source/return/quantity caps, source discovery and dispatched-amount lock passed; refunds `2`–`5` processing; remaining Cash/source-`16` allocations and final settlement open |
| L10 | Recover controlled interrupted/failed refund and reconcile all test money | Same operation/reference/key; completed siblings retained; uncertain amounts stay reserved; no second dispatch or excess refund | PARTIAL: normal reload/status check retained the same refund reference without duplication; all five refunds still unverified, controlled failure and complete financial reconciliation open |

The [Revolut refund
guide](https://developer.revolut.com/docs/guides/merchant/operations/refunds)
confirms asynchronous processing through a separate refund order linked to its
original. Provider completion may precede the funds appearing on the customer's
account; record those observations separately when available.

## Per-attempt evidence and reconciliation

The [operator chronology](ticket-12-operator-observations.md) contains entries
for all eighteen payment operations, five refund operations, their UTC checks,
sanitized external references and observed outcomes. Reconciliation checkpoint:
eight pence captured in total (original penny plus seven additional pence), five
pence reserved by processing refunds, zero verified completed refunds, and
three captured pence still unallocated to refunds (two on source `11`, one on
source `16`). The mixed sale's separate Cash penny also remains to be returned.
These pending reservations are not successful refunds or cardholder credits.

Use this template for subsequent attempts/allocations, including unsuccessful ones:

| Field | Entry |
| --- | --- |
| Scenario, operator, authorization reference, UTC start and final observation | NOT RUN |
| Deployed SHA, environment/company, currency and approved minor-unit amount | NOT RUN |
| POS session/order/payment-line or return identifiers and local operation ID | NOT RUN |
| Provider order/intent/payment; refund order and original link | NOT RUN; stable aliases permitted with a restricted authoritative mapping |
| Observed device, underlying payment/refund and Odoo state transitions | NOT RUN |
| Intended mutation count, retry predecessor/reference and outcome | NOT RUN |
| Captured total, completed refunds, active reservations and remaining balance | NOT RUN |
| Pass/fail/NOT REPRODUCIBLE, discrepancy and restricted evidence location | NOT RUN |

Keep credentials, headers, raw API responses, cardholder names, card numbers,
PINs and customer screenshots out of this shared record. Sanitized reference
UUIDs/aliases, amounts, timestamps and final-state observations suffice; retain
a restricted mapping for authoritative manager reconciliation.

At session end, match every charge/refund to the same Merchant account and Odoo
reconciliation/refund worklists. For each original payment, completed refunds
plus active reservations must not exceed the captured amount. Record deliberate
retained balances and their owner's approval; refund only under the authorized
plan. Keep uncertain exposure open with an owner and next action. A timeout,
empty lookup or missing reference never establishes that no charge occurred.

## Operating instructions and release closure

Use the [installation guide](../installation.md) for fresh installation of both
addons, optional Restaurant activation, server secret provisioning/rotation,
configuration, cashier recovery, manager reconciliation and allocated refunds.
Use the [deployment runbook](../staging-deployment.md) for reviewed artifact
install/upgrade, backups, financial guards, Cash smoke and safe failure recovery.
Record differences observed on the target before finalizing those procedures.

For discovery failures, verify account, physical location, device connectivity
and Pay at Counter; **Check Connection** creates no charge. For uncertainty,
retain the original line and use **Check status**; managers associate missing
references through reconciliation. Never force paid, delete claims/locks,
substitute tender, replace an uncertain refund or restore a stale database to
clear exposure.

Close ticket 12 only after preflight, observed mandatory scenario passes,
test-money reconciliation, resolution of provider discrepancies affecting
required acceptance, and instructions finalized from those observations.
Changed addon/deployment code requires a new reviewed candidate and affected
acceptance. Documentation-only commits can retain these results only when the
addon trees and deployment/test tooling match the tested revision; record that
comparison before deployment.

Open release gaps: remaining L02–L10 subcases and complete test-money
reconciliation; [terminal-busy recovery](../tickets/ready-for-human/22-recover-terminal-busy-rejection.md)
and [automatic payment-status handling](../tickets/ready-for-human/23-preserve-polling-through-payment-processing.md);
the Sandbox simulator issue for required non-production acceptance; and final
guidance based on physical-terminal observations. Before a live addon
upgrade/restart, confirm all refund final states and any other financial
blockers read-only. These findings require reviewed fixes and affected retests;
documenting a narrow guard pass does not close the full scenario.

## Local snapshot-resource candidate — 2026-09-30

The locally reviewed ticket 24 implementation is
`604962a41d74552a497f661baa66b45c8db72113` on
`codex/24-bound-financial-snapshot-processing`, addon `19.0.1.7.7`.
Its [evidence record](ticket-24-financial-snapshot-bounds.md) demonstrates capped
authenticated Odoo input amplification before the fix, authenticated helper
dispatch, shared bounds before expansion/retention, strict start validation,
safe native rejection/recovery and preserved literal payment/refund comparisons.

| Final local check | Result |
| --- | --- |
| Pinned mocked fresh install / upgrade / Restaurant | 234 / 234 / 8 tests; zero failures/errors; runner exit 0 |
| Affected public payment/refund/settlement/mutation and native checkout | 154 tests; zero failures/errors |
| POS lifecycle / deployment unit checks | 65 / 29 tests passed |
| Persisted payment/refund restart recovery | Two processes; `RESTART_RECOVERY_OK`; exit 0 |
| Independent Standards / Spec / security fix verification | 0 / 0 findings; reproduced resource boundary `fixed` |

This is local branch evidence, awaiting integration and combined-candidate
release verification. It includes ticket 22's local source correction from
reviewed main; ticket 23 remains separate. The earlier candidate/artifact/live
results above retain their original dates and identities. No staging deployment,
real financial operation or worker-outage experiment accompanied these tests.
All outstanding reconciliation, human acceptance and final deployment gates
remain open in ticket 12.

## Combined ticket 23/24 candidate — 2026-09-30

Main `fbab631` includes ticket 23 through PR #29. PR #28 now contains both
local corrections in executable candidate `d64e962`, addon `19.0.1.7.8`.
The [combined evidence](ticket-24-financial-snapshot-bounds.md#combined-candidate-after-ticket-23-integration--2026-09-30)
retains the earlier run identities, the unchanged snapshot/recovery boundary,
processing-state guards and refreshed acceptance. The preceding report's
separate-branch note describes its earlier checkpoint.

Final combined mocked verification passed 243 fresh-install, 243 upgrade and
eight Restaurant tests; 71 lifecycle and 29 deployment checks; and restart
recovery across two processes. Standards/Spec source findings are zero. The
linked record separately retains the initial browser timeout, its passing
unchanged isolated rerun and the final passing full suite.

Ticket 24 still awaits PR integration into main; ticket 23's live retests and
ticket 12's reconciliation/release requirements remain open. The branch update
performs no deployment or real financial operation and does not merge PR #28.

## Refund finality and next acceptance step — 2026-10-01

The preceding matrix and 2026-09-29 reconciliation totals are historical
checkpoints. The operator now reports **Completed** for all five test refunds
in Odoo. Their Revolut Merchant Orders screenshot shows the five matching
£0.01 refund-order prefixes as **Refunded**. The
[dated follow-up](ticket-12-operator-observations.md#refund-final-state-follow-up--2026-10-01)
lists all five IDs and evidence limits. PR #28 has also since merged into
main; the preceding candidate paragraph describes its earlier state.

Next, read all five Odoo refund records and the payment/refund worklists
without financial mutation. Confirm completed/verified local states,
original-payment links, amounts, no pending/unresolved reservations and no deployment
blockers. Reconcile £0.05 refunded against £0.08 captured and document the
remaining £0.03 Revolut and £0.01 Cash disposition. This update grants no
new financial authorization; retain the existing budget and obtain fresh
authorization for any operation outside it. If the read-only preflight is clear, prepare
the reviewed combined candidate for a guarded staging upgrade, then perform
ticket 22's independent-browser busy/recovery retest and ticket 23's full and
split/multiple-card automatic-status retests. Restaurant and the other open
L02–L10 subcases, final combined release evidence and operating instructions
remain ticket 12 gates. No live deployment or financial operation was run by
this documentation update.

## Staging upgrade checkpoint — 2026-10-01

The owner confirmed staging idle, and reviewed `origin/main` revision
`97fcc2b7e051e5d2037e1bd108bf365ac829f1a3` passed both focused
delivered-artifact scenarios. The guarded upgrade completed after successful
backup/restore-health checks and pre/post-quiescence financial blocker checks.
Staging now serves the new immutable release with Odoo active and HTTP 200;
`pos_revolut` is installed at `19.0.1.8.0`. The
[ticket 12 deployment checkpoint](../tickets/ready-for-human/12-live-terminal-release-evidence.md#guarded-staging-upgrade--2026-10-01)
records the archive hash, release and configuration-backup paths, test limits
and server observations.

The operator could not perform the post-upgrade Cash smoke or physical-terminal
acceptance in this session. Tickets 22 and 23 remain open for their affected
live retests, and ticket 12 remains open for its wider release gates. The
successful deployment guard is not a per-refund reconciliation audit.

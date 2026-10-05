# 12 — Validate real terminal payments and publish release evidence

**Work branch:** `codex/12-live-terminal-release-evidence`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-human

## Current handoff — 2026-10-05

Resume from the [deployed discovery correction and next-step matrix](../../testing/ticket-12-release-evidence.md#shared-merchant-discovery-rollout--2026-10-05).
Staging now runs **19.0.1.15.3**, with saved matching return/payment enforcement
and corrected shared-Merchant discovery. PRs #46 and #47 are merged. Final
install and upgrade each passed 490 tests; live API rejection checks made zero
provider HTTP calls. Financial blockers remain zero after the restored cron ran.
All discovery evidence is retained; unfamiliar foreign transactions are not
assumed to be cash returns or attributed to this register.

The approved recovery already restored native draft 24, displayed **2 (Refund)**,
total **-£0.02**, with both original refunds verified. Review and Validate that
existing receipt; do not recover it again or send replacement refunds. The
verified external penny refund 10 / source 36 separately needs manager review
of its outstanding native bookkeeping. Administrator's GBP register grant is
preserved. Standard Restaurant is installed, but GBP register 2 remains retail.

Remaining human work is the receipt, external native reconciliation, unseen
tip/report and Restaurant scenarios, unexecuted failure/race/interruption cases,
final test-money reconciliation and combined-runtime/device acceptance. Retain
the completed full/split/two-card, busy-terminal and older-return evidence.
The checkpoint below describes earlier states and is superseded by this handoff.
The ticket remains open and ready-for-human.

## Resume checkpoint — 2026-10-01, 13:40 UTC

Resume from the [current checkpoint and remaining-work matrix](../../testing/ticket-12-release-evidence.md#current-refund-repair-checkpoint--2026-10-05).
Completed full/split/two-card automatic checkout, terminal-busy recovery and
the four finalized older returns retain their evidence; do not restart those
scenarios. Read-only staging checks on 2026-10-05 show all six refunds
verified/completed. The last two allocations have no saved native return for
the original UUID previously displayed as `1012`. Recover that draft with its
existing references before validating its receipt; send no replacement refund.

Remaining device work covers terminal tips, Restaurant, the unexecuted
failure/race/interruption subcases and final reconciliation. Staging has no
Restaurant installation or configured GBP Tip Product. Earlier packaged-artifact
checks were blocked by the sandbox Docker socket; this repair now has access
to the disposable Docker runtime. Exact combined-artifact acceptance remains
required before rollout. Ticket 12 remains open; other ticket states are unchanged.

## What to build

Controlled real-terminal acceptance establishes whether the documented addon is ready for use, with traceable payment/refund evidence and complete operating instructions.

## Acceptance criteria

- [x] Confirm the reviewed release includes completed corrections 16–21 and an independent review of the payment-verification boundary. Before live acceptance, record the full integrated mocked suite on the final combined revision: install/upgrade, Restaurant, lifecycle, deployment checks, restart recovery, delivered-artifact acceptance and the new adversarial regressions for tickets 19–21.
- [ ] Integrate the reviewed ticket 24 snapshot-resource correction and record its bounded Odoo validation, rejection/recovery regressions and independent security fix verification on the final combined candidate. Refresh affected payment/refund, settlement, lifecycle, install/upgrade and Restaurant evidence before release acceptance and closure; preserve earlier dated results as historical evidence.
- [x] Confirm the deployed revision, target Odoo version, merchant environment, location, eligible terminal and operator-authorized test amounts before financial tests. Use non-production testing where supported; separately obtain explicit authorization for any real-money operation.
- [ ] Validate successful full payment, split tender and retail/restaurant fulfilment using the confirmed contract. Demonstrate that only verified successful payment completes a fully paid order.
- [ ] Validate decline/failure/cancellation and interruption/late recovery with provider-supported controlled methods. Verify safe retry and duplicate prevention using actual provider transaction references; never deliberately create uncontrolled duplicate charges.
- [ ] Validate full and partial refunds through their asynchronous final outcome, preserving original and refund references. Reconcile all test charges and refunds.
- [ ] Record observed results, sanitized references, timestamps and any scenarios that cannot be reproduced. Unexecuted required acceptance scenarios remain open release gaps, not implied passes.
- [ ] Finalize fresh-install, configuration/secret rotation, cashier, manager reconciliation/refund, upgrade and troubleshooting instructions based on observed behavior.
- [ ] Close only after mandatory acceptance gaps and provider contract discrepancies are resolved. Keep credentials and sensitive cardholder data out of release evidence; no changes to hosting or parent issues.

## Blocked by

- 02 — Resolve the Revolut terminal contract and testing prerequisites (closed)
- 11 — Verify the complete addon on the target Odoo version
- 16 — Preserve uncertain refunds when original-sale recovery fails
- 17 — Deliver the Restaurant bridge with the reviewed addon release
- 18 — Isolate internal payment records by allowed company
- 19 — Enforce verified settlement and internal-operation permissions
- 20 — Recover POS lines after a failed pre-payment lookup
- 21 — Keep reconciliation progressing after malformed provider responses
- 22 — Recover a POS line after a terminal-busy rejection (closed after live retest)
- 23 — Preserve payment polling through valid processing states (closed after full, split and two-card live retests)
- 24 — Bound financial snapshot processing before numeric expansion (closed; final combined release evidence remains required)
- 27 — Enforce the authorized order balance before terminal dispatch (closed locally and merged; updated release still needs guarded deployment and target-device acceptance)
- 28 — Bind Revolut credential authority to the owning company (closed; [fix, migration and independent verification evidence](../../testing/ticket-28-credential-authority-evidence.md) accepted; final combined-runtime acceptance remains)

## Release gate update — 2026-09-25

The owner approved the final audit corrections and required all three before
this ticket. The existing contract/access and target-version acceptance gates
remain in place. Ticket 02 is now closed with its contract and Sandbox evidence.

## Release gate update — 2026-09-28

The owner approved tickets 19–21 as three independently actionable software
corrections covering the four new payment-safety audit findings. They block
this ticket in addition to its existing gates. The current passing suite is
baseline evidence; final acceptance must include the added security and
failure-recovery regressions on the combined fixed revision. Ticket 02 is
closed; this ticket remains open for all physical-terminal configuration and
controlled live acceptance.

## Physical-terminal handoff — 2026-09-28

The project owner reports that a test Revolut Terminal is physically available
and linked to the production Business user **Test Guzman**. Before any financial
test, this ticket must verify the device is on app version 1.56 or later, is
logged in to the intended production Merchant account, is assigned to the
matching production physical location and has Pay at Counter enabled. Production
terminal discovery must then return that online device for the matching
`location_id` and `operation_mode=pos`.

The Sandbox secret and fixed Sandbox virtual terminal are separate and must not
be used for the physical device. No production credential value, card detail or
real transaction is authorized or recorded by this availability note.

## Automated preparation and human handoff — 2026-09-28

The agent-completable slice is recorded in the
[release evidence and operator checklist](../../testing/ticket-12-release-evidence.md).
Reviewed `origin/main` at `935d077` contains the closed blockers 02, 11 and
16–21. The user-invoked implement skill requires committing on the current
branch; `codex/02-confirm-terminal-contract` was therefore fast-forwarded to
that baseline rather than using this ticket's original branch snapshot.

Independent payment-boundary review found an additional historical-tender
reclassification gap. A synthetic closed-session/public-manager regression
reproduced a manual return accepted after its original Revolut method was
reconfigured. Commit `76209bb3c3ac705dcc724ba329e044c6626c59cd`
(`19.0.1.7.5`) preserves persisted Revolut classification. The regression passed
red/green, all 36 refund regressions passed, and independent re-review found no
remaining actionable issue in that correction. Combined acceptance is recorded
against this exact candidate in the linked evidence; it must enter the reviewed
release ref before deployment.

Final combined verification passed 208 fresh-install, 208 upgrade and 8
Restaurant tests; 27 lifecycle and 29 deployment unit tests; restart recovery
and deployment guards; and both delivered-artifact scenarios (2 + 8 retail/later
Restaurant, 8 + 8 migration/update). All runtime commands returned zero. The
two-addon archive checksum is recorded in the evidence, syntax checks passed,
and no browser-skip warnings or credential/cardholder canaries appeared in the
runtime logs. Standards and Spec reviews found no remaining actionable finding.

The checklist supplies device/account preflight, separate controlled scenario
records, sanitized UTC/reference evidence and test-money reconciliation. Existing
install, server-secret rotation, cashier recovery, manager refund/reconciliation,
upgrade and troubleshooting guidance is linked and the correction's upgrade is
documented. Final instruction changes based on actual device observations stay
open.

At this 2026-09-28 handoff the ticket remained `ready-for-human`: no staging deployment or Merchant request
was made, and no physical-terminal charge/refund was run. Deployed-version
verification, production account/location/device eligibility, explicit test
amounts and financial authorization, observed live outcomes, reconciliation and
remaining provider discrepancies still need human completion. All unexecuted
scenarios are explicit release gaps; this preparation does not close the ticket.

## Controlled live acceptance checkpoint — 2026-09-29

The [operator observations](../../testing/ticket-12-operator-observations.md)
record the authorized staging upgrade, production device/location discovery,
server-only credential, dedicated GBP POS/session, explicit financial budget,
and controlled live outcomes. The
[release matrix](../../testing/ticket-12-release-evidence.md) now distinguishes
completed narrow checks, partial scenarios, pending refunds and unexecuted
subcases. Earlier handoff statements above describe that earlier checkpoint.

At 13:42:07 UTC there were eighteen payment operations, no active card-payment
blocker, six verified sources totalling eight pence, and five one-penny refunds
still processing/unverified. Seven of ten authorized additional pence had been
captured; three remained in that aggregate budget. Three captured pence and
the mixed sale's Cash penny still need allocation/return. Pending refund
reservations retain their deployment blockers and are not completed refunds.

L01's original one-penny automatic payment passed. Cash/Revolut and two-card
allocations, selected cancellation/retry/reload paths, refund caps and locks,
and both browser terminal guards have passing subcases. Initial automatic
status handling failed on four later operations, and an independent browser
remained stuck after a definitive busy-terminal rejection. Reports
[22](../closed/22-recover-terminal-busy-rejection.md) and
[23](../closed/23-preserve-polling-through-payment-processing.md) preserve
these release findings and their mocked characterizations without claiming a
fix or deployment. They are ready for local work; reviewed fixes/retests are
required before closure. Read-only reconciliation of the pending refunds can
continue independently.

Ticket 12 remains open. Final refunds/test-money reconciliation, Restaurant,
remaining failure/race/interruption subcases, provider discrepancies and final
observed operating guidance remain incomplete. No addon code is changed by
this evidence update, and it does not authorize bypassing financial guards or
upgrading/restarting staging while unresolved refunds remain.

## Snapshot resource-bound release gate — 2026-09-30

The owner approved [ticket 24](../closed/24-bound-financial-snapshot-processing.md)
as an additional blocker for release acceptance and closure. Its local mocked
validation and implementation can proceed independently of terminal access,
financial reconciliation and tickets 22–23. Review the combined correction and
refresh affected automated evidence before closing this release gate.

The report demonstrates bounded numeric amplification in an extracted-method
harness, and static triage found the behavior in the current code. Neither
triage nor this ticket update establishes an actual deployed worker outage.
Preserve that limitation alongside the eventual Odoo regression and fix evidence.
All existing human acceptance, financial reconciliation and deployment safety
requirements remain in force.

## Local snapshot correction verified — 2026-09-30

Ticket 24 is closed on `codex/24-bound-financial-snapshot-processing`, with
implementation `604962a41d74552a497f661baa66b45c8db72113`, addon `19.0.1.7.7`.
The [bounded reproduction and independent verification](../../testing/ticket-24-financial-snapshot-bounds.md)
record authenticated cashier/helper dispatcher evidence, shared resource limits,
zero-dispatch rejection and native payment/refund correction/recovery. Final
mocked acceptance passed 234 install, 234 upgrade and eight Restaurant tests;
65 lifecycle and 29 deployment tests; and recovery across two Odoo processes.
Standards and Spec reviews have zero remaining findings; independent security
fix verification reports `fixed` for the reproduced resource boundary.

This branch includes ticket 22's local correction from reviewed main; ticket 23
is a separate branch. Integrate and review the combined correction, refresh the
affected final-candidate evidence and complete existing financial/human gates
before release acceptance. The integration criterion above remains unchecked.
No staging change, real Merchant request, physical-terminal test or deployed
worker-exhaustion experiment occurred in ticket 24 work. Prior dated live and
automated evidence remains historical evidence.

## Combined branch update after ticket 23 entered main — 2026-09-30

Ticket 23's reviewed local fix is now in main `fbab631`, through PR #29.
Ticket 24's PR #28 incorporates that main in executable candidate `d64e962`,
addon `19.0.1.7.8`, retaining both corrections and their tests. The earlier
separate-branch statement describes the preceding checkpoint.
The [combined verification](../../testing/ticket-24-financial-snapshot-bounds.md#combined-candidate-after-ticket-23-integration--2026-09-30)
records conflict resolution, refreshed acceptance and preserved live gates.
Final combined acceptance passed 243 install, 243 upgrade and eight Restaurant
tests; 71 lifecycle and 29 deployment checks; and two-process restart recovery.
Independent Standards and Spec reviews have zero remaining source findings.
PR #28 subsequently merged into main at `1d549c1`; human/financial acceptance
and final release evidence are still required.

## Refund reconciliation checkpoint — 2026-09-30

The operator reports five separate £0.01 credits received in their Revolut
account, corresponding in count and amount to the five test refunds. This is
cardholder-side evidence, not an individual match to the five Merchant refund
order IDs or an authoritative final Merchant API status.

At 12:48–12:49 UTC, Odoo's Revolut Refunds list still showed all five records
as **Pending**. An Odoo **Check status** on refund operation `5` returned
**Pending**, provider state `processing`, and advanced its next reconciliation
time. Operation `1` also displayed **Pending** / `processing` with a recent
next reconciliation time. The Odoo status action read the existing refund;
no new refund was issued. The direct Merchant payloads for this checkpoint
were not captured. See the [operator observations](../../testing/ticket-12-operator-observations.md)
for the bounded evidence.

Keep the final-refund criterion and ticket 12 open. Do not mark these refunds
verified, release their reservations, or lift the staging upgrade gate from the
customer credits alone. Compare each stored refund order with an authoritative
Merchant final outcome; investigate the prolonged `processing` state with
Revolut if it persists. The reviewed ticket 22 and 23 fixes are merged into
main but remain undeployed; their live retests remain gated.

## Refund final-state follow-up — 2026-10-01

The operator now reports **Refunded** in Revolut and **Completed** in Odoo for
the five £0.01 test refunds. The supplied Revolut Merchant Orders screenshot
shows five refunded orders dated 2026-09-29; each displayed ID prefix matches
one of the five Merchant refund orders in the
[operator chronology](../../testing/ticket-12-operator-observations.md#refund-final-state-follow-up--2026-10-01).
This supersedes the preceding pending-status checkpoint for those orders.
Odoo completion is operator-reported; a new Odoo export or direct Merchant API
response was not captured in this follow-up.

Before a guarded staging upgrade or further live financial testing, perform a
read-only check that all five Odoo refund operations are verified/completed,
still linked to their original source payments, and no other payment/refund
operation blocks deployment. The five one-penny refunds reconcile £0.05 of
the prior £0.08 Revolut captures. Document the disposition of the remaining
£0.03 Revolut captures and the mixed sale's £0.01 Cash portion. Do not infer
that this final-state observation closes L08–L10 or authorizes additional
charges, refunds, or Force done.

Tickets 22 and 23 remain open for deployment of their reviewed corrections
and controlled affected live retests. Ticket 12 also retains Restaurant,
failure/race/interruption, final combined-candidate and operating-guidance
gates. The new refund evidence removes the observed provider-processing
discrepancy; it does not close this release ticket.

## Guarded staging upgrade — 2026-10-01

The owner confirmed staging was idle. From a clean isolated test invocation,
the exact reviewed `origin/main` revision
`97fcc2b7e051e5d2037e1bd108bf365ac829f1a3` passed both delivered-artifact
scenarios (`retail` and `migration`, exit 0) against pinned Odoo
`19.0.20260908`; the two-addon archive SHA-256 was
`329964852246be8330dc1ef8eafcb0321e59fd96bfbe2303235f68547586486a`.
These focused artifact checks do not replace the earlier full mocked suites or
the remaining physical-terminal tests.

The staging host's latest `odoo-backup.service` and
`odoo-restore-test.service` runs both reported success (2026-10-01 06:01 UTC
and 03:02 UTC). The guarded upgrade then passed its financial-operation checks
before and after checkout quiescence, took a fresh backup and upgraded the
existing staging database. It reported the immutable release
`/opt/odoo-releases/revolut/staging/97fcc2b7e051e5d2037e1bd108bf365ac829f1a3/pos_revolut`
and configuration backup
`/var/backups/odoo-revolut-deploy/20261001T090834Z-97fcc2b7e051`.
Afterward Odoo was active, both addon symlinks resolved to that release, the
local `/web/login` returned HTTP 200 and the service error journal since the
upgrade had no entries. Odoo registered `pos_revolut` installed at
`19.0.1.8.0`; the optional Restaurant bridge remained uninstalled in this
retail database. This guard result does not independently audit every original
payment/refund link or prove final Merchant settlement.

The operator was unavailable for the Cash-only smoke order after the upgrade.
No physical terminal action, new sale or refund, or ticket 22/23 live retest
was performed during this checkpoint. Reopen the POS to load the new browser
assets, complete the runbook's Cash smoke, then perform ticket 22's no-card
two-browser scenario and ticket 23's full/split/multiple-card status tests.
Keep all three tickets open pending observed results. The owner said to proceed
with testing without first settling the previously retained £0.03 test spend;
that preference is not evidence that every reconciliation and release gate is
closed.

## Post-upgrade Cash smoke and terminal-busy retest — 2026-10-01

After reopening the upgraded POS, the operator completed a £0.01 sale entirely
with **Cash - Davai GBP Test**. The receipt opened automatically and showed the
Cash tender for the full £0.01. This passes the post-upgrade retail Cash smoke;
it does not exercise Revolut payment polling.

The operator then used two independent browsers for ticket 22's no-card
terminal-busy scenario. While the first browser occupied the terminal, the
second showed **Terminal busy — no payment request sent**, offered **Resume**
and **Check status**, left £0.01 due and kept Validate disabled. A read-only
operation-ledger observation at that point found no second-order operation.
The first-browser terminal request was subsequently cancelled.

After the terminal was released, the second browser reached the terminal's
payment screen. The operator cancelled that request without presenting a card.
The read-only ledger then showed two successive £0.01 GBP attempts on the same
second-order payment line: the first was cancelled before the second began,
and the second is now cancelled too. Both have provider state `cancelled`, are
retry-safe and hold no order or terminal lock; no verified payment was observed
in these records. The exact operator action between the two attempts remains
unconfirmed, so this observation does not establish the ticket 22 requirement
of one intended dispatch per explicit Resume. Leave ticket 22 and the broader
ticket 12 live acceptance open until that sequence is resolved and the remaining
affected tests are completed.

The operator later recalled pressing Resume a few times, which plausibly
explains the successive attempts without establishing a one-click-to-one-
operation count. Removing the cancelled second-browser Revolut payment line
left no payment line and the order still showed £0.01 due. The controlled
single-Resume count and ticket 23's card-payment polling retests remain open.

## Controlled terminal-busy recovery passed — 2026-10-01

A second no-card, two-browser run resolved the preceding ambiguous retry
sequence. While the first browser's £0.01 GBP request held the terminal, the
second browser showed clear **Terminal busy — no payment request sent**
feedback, £0.01 due and disabled Validate. Read-only ledger checks found no
new second-order operation. Cancelling the first request produced provider
state `cancelled` and released the terminal lock. The second browser's one
**Check status** call created no operation. One subsequent **Resume** on its
same visible line created exactly one pending £0.01 GBP operation and displayed
the payment on the terminal. The operator presented no card and cancelled it;
the ledger recorded provider state `cancelled`, no further operation and no
remaining lock. This passes ticket 22's controlled live criterion, which is
now [closed](../closed/22-recover-terminal-busy-rejection.md). Ticket 23's
full and split/multiple-card automatic-status retests and ticket 12's other
release requirements remain open.

## Automatic full-card receipt — 2026-10-01

On a fresh £0.01 GBP sale paid entirely by Revolut, the operator reports that
the receipt opened automatically without Check status or Validate. The supplied
receipt screenshot shows success and a single £0.01 Revolut tender. Read-only
server verification found the linked payment operation `verified`, provider
state `captured`, exact £0.01 amount, a paid £0.01 POS order and no remaining
terminal/order lock. This passes ticket 23's full-card live subcase. Its split
tender and multiple-card-line cases remain open, as do ticket 12's other
release gates and test-sale reconciliation.

## Cash/Revolut split receipt — 2026-10-01

The operator prepared a £0.02 GBP cart, assigned £0.01 Cash and paid the
£0.01 remainder by card. The supplied receipt screenshot shows both £0.01
tenders on a successful £0.02 sale. Read-only server verification found the
Revolut operation `verified` and underlying payment `captured` for one GBP
minor unit, a paid £0.02 POS order, two stored £0.01 tender lines on the
expected methods, and no remaining lock. The operator confirmed the receipt
opened automatically without Check status or Validate. The multiple-Revolut-line
live case and other ticket 12 release gates remain open.
This new £0.01 card capture is part of the test-sale reconciliation still due.

## Two-Revolut-line automatic receipt — 2026-10-01

On a £0.02 GBP sale, the initial £0.02 terminal request was cancelled before
any card was presented. The cancelled line was changed to £0.01 and retried.
The first £0.01 card payment became successful automatically while Odoo kept
the order open with £0.01 due. The second £0.01 Revolut payment then completed;
the operator reports the £0.02 receipt opened automatically without Check
status or Validate. Read-only server verification found paid POS order
`261-2-000019`, two distinct captured/verified one-penny Revolut operations,
two stored £0.01 tender lines with distinct provider references, and no
terminal/order lock. The initial £0.02 attempt was provider-cancelled and had
no underlying card payment. This closes [ticket 23](../closed/23-preserve-polling-through-payment-processing.md).
Ticket 12 remains open for its other release gates and reconciliation of these
two additional £0.01 card captures.

## Read-only staging reconciliation — 2026-10-01

At 10:48 UTC, the staging operation ledger had 15 verified/captured GBP minor
units and five verified/completed one-unit refunds. The nominal retained card
balance is therefore £0.10. All five completed refund operations still have
no linked finalized POS return order or POS payment. The order table likewise
has no completed negative GBP return corresponding to them. Resume those
existing return drafts and verify their completed allocations before closing
them; do not dispatch replacement provider refunds for these five sources.

| Original Revolut operation | Original POS order | Captured | Completed refund | Remaining card balance |
| --- | --- | ---: | ---: | ---: |
| 4 | 261-2-000001 | £0.01 | £0.01 | £0.00 |
| 10 | 261-2-000004 | £0.01 | £0.01 | £0.00 |
| 11 | 261-2-000006 | £0.03 | £0.01 | £0.02 |
| 14 | 261-2-000009 | £0.01 | £0.01 | £0.00 |
| 16 | 261-2-000011 | £0.01 | £0.00 | £0.01 |
| 17 | 261-2-000011 | £0.01 | £0.01 | £0.00 |
| 19 | 261-2-000013 | £0.01 | £0.00 | £0.01 |
| 20 | 261-2-000014 | £0.01 | £0.00 | £0.01 |
| 27 | 263-2-000004 | £0.01 | £0.00 | £0.01 |
| 35 | 261-2-000017 | £0.01 | £0.00 | £0.01 |
| 36 | 261-2-000018 | £0.01 | £0.00 | £0.01 |
| 38 | 261-2-000019 | £0.01 | £0.00 | £0.01 |
| 39 | 261-2-000019 | £0.01 | £0.00 | £0.01 |

The dedicated GBP Cash test method has three recorded £0.01 tenders on orders
`261-2-000004`, `261-2-000015` and `261-2-000018`; their physical cash or
test-drawer disposition remains to be recorded separately. The £0.10 retained
card balance needs an owner-approved refund or retention decision by source,
including the separate `263-2-000004` sale. This table supersedes the earlier
dated £0.08 captured/£0.05 refunded/£0.03 retained checkpoint.

## Latest merged release gate — 2026-10-01

Current `main` includes ticket 27's reviewed `19.0.1.9.0` cart-authority and
terminal-tip implementation. Its addon and test-script trees match the tested
`88c88a5` candidate exactly; that candidate passed 340 fresh-install, 340
upgrade and nine Restaurant tests plus its recorded delivered-artifact and
concurrency checks. Staging still runs reviewed `97fcc2b` / `19.0.1.8.0`,
which passed the live payment retests above but does not exercise ticket 27.
Before final release acceptance, complete ticket 28's company-credential
binding and migration, refresh affected combined checks on the resulting
candidate, then perform a guarded staging upgrade when the POS is idle and
financial blockers are clear. The target device still needs explicit zero-
and nonzero-tip popup/report identity, amount-unit and latency observations,
along with ticket 12's remaining Restaurant, failure/recovery and refund
acceptance cases. The current live success of ticket 23 is not a live pass for
the newer ticket 27 code.

## Return finalization after session rollover — 2026-10-01

The first existing completed refund (`1002 (Refund)`) could not finalize after
the test register was closed and reopened. The unchanged one-penny return
showed **Refund Successful** and £0.00 remaining, but Validate reported that
the return had changed after allocation. Read-only records show the refund
reserved in closed session `5` and the same register now open as session `9`;
the provider refund remains verified and no POS return/tender was saved.
The server guard also required the same session for settlement. A focused
mocked test reproduced that error; candidate `19.0.1.9.1` allows a verified
refund to settle in a later opened session of the same register only when
the old session is closed and every existing allocation and cart check still
passes. Two targeted tests and all 45 refund tests pass locally. Staging
still needs the combined candidate upgrade and a live retest of the five
existing returns before the refund and reconciliation criteria can pass.

## Guarded upgrade and return settlement — 2026-10-01

The exact combined `f303580` artifact passed delivered retail and migration
acceptance with zero failures. The idle staging register passed financial
preflight, database/filestore backup and the guarded upgrade to addon
`19.0.1.10.0`; the Odoo service and local health check succeeded. The release
archive SHA-256 was
`b0ab7eb213e01b0ddd6b0f06baf07aaecd3661ef4f457e0deeafb4355388e8a3`.
The configuration snapshot is
`/var/backups/odoo-revolut-deploy/20261001T113028Z-f3035802518b`.
The administrator created the Davai/production authority for the previously
verified Test Guzman server reference. No historical attempt was bound by the
upgrade. The five existing provider refunds stayed verified throughout.

The operator resumed the existing POS return tabs. `1002 (Refund)` finalized
its already-verified one-penny Revolut tender as paid after Validate.
`1005 (Refund)` finalized its existing one-penny Revolut refund together with
the original sale's one-penny test Cash share. `1007 (Refund)` and
`1010 (Refund)` reached receipts after Check status and finalized their
existing one-penny refunds. Read-only order/payment checks confirmed all four
paid negative orders and their linked original refund operations. The provider
refund operation count remained five; no replacement refund was sent.

`1012 (Refund)` remains a two-penny return with one successful one-penny
Revolut refund and one penny remaining. The original sale had two distinct
captured one-penny Revolut payments. Source operation `17` has the completed
refund; source `16` has no refund. Its recorded order, intent and payment IDs
match the independent Merchant verification in the operator chronology.
Before issuing the remaining one-penny refund, the administrator attestation
action on source `16` raised an Odoo access-control error. The action wrote
neither a credential binding nor a provider refund. A real-administrator Odoo
test reproduced the error; a scoped server-authority fix passed that test and
the surrounding 53 credential/refund tests. Keep `1012` untouched until the
follow-up addon release is checked and deployed. Ticket 12 and the remaining
Restaurant, failure/recovery, tip and full reconciliation gates stay open.

The follow-up `d52a4079522b9fd56ff282e02d3ec91f92147e5d` was pushed
conflict-free to `main`. Its packaged migration test passed with zero
failures/errors, and the guarded staging upgrade installed addon
`19.0.1.10.1` with a configuration backup at
`/var/backups/odoo-revolut-deploy/20261001T115207Z-d52a4079522b`.
The real-administrator attestation of reviewed source `16` then succeeded;
readback confirmed its authority binding and no change to the five provider
refund operations. The final one-penny allocation on `1012` remains for the
operator to issue and verify before its POS return can be finalized.

## Second allocation blocked after register rollover — 2026-10-01

On the existing `1012 (Refund)` two-penny return, the operator selected the
remaining one-penny original Revolut source `16` after source `17` had already
been refunded. The second refund start failed before reservation: the server
logged **The return changed after a refund allocation was reserved**. The
cashier UI instead reported a communication interruption and kept the second
negative one-penny line unresolved after Check status. Read-only records still
show exactly five provider refunds, all verified, and no operation for the
second line. The provider was not called for the rejected attempt.

The first refund had been reserved in closed POS session `5`; the same register
was reopened in session `9`. The allocation guard rejected that prior verified
refund solely because of the session change, although final settlement already
allows this safe same-register rollover. Candidate `19.0.1.10.2` applies the
same constraint to an additional allocation: prior refunds from another
session must be verified, from a closed session of the same register, and the
current session must be open. Its server-side absence check holds the order
lock before telling the cashier that an empty lookup means no refund request
was sent. A pending or mismatched line remains locked. The live second line
must stay untouched until this candidate is deployed; then Check status and an
explicit retry on that same line can recover without creating a duplicate
attempt.

## Deployed split-refund recovery and current gate — 2026-10-01

Commit `25e096d74ca62ac7f39558e0257f609be85185d7` was pushed to `main`
without conflicts. The guarded staging upgrade installed addon
`19.0.1.10.2`, passed financial preflight and Odoo health checks, and saved a
configuration backup at
`/var/backups/odoo-revolut-deploy/20261001T122450Z-25e096d74ca6`.
The focused real-Odoo refund suite passed 47 tests on fresh install and 47 on
upgrade; nine Restaurant upgrade tests and 75 POS-state tests passed. A focused
regression also verified that the reopened same register accepts a second
allocation while a different register is rejected before provider HTTP. The
longer exact packaged-artifact retail and migration runs were interrupted and
are **not** counted as passed for this revision.

The operator refreshed the existing `1012 (Refund)` line, used Check status to
recover the earlier pre-reservation failure, then explicitly retried once.
Read-only staging records show exactly one new one-penny refund operation `6`
from original source `16`, alongside the prior verified operation `5` from
source `17`; the new operation has a provider refund reference and no linked
POS return yet. At 12:31 UTC, operation `6` was `unresolved` with provider
state `processing`. The operator reports that Odoo still shows it processing
or unresolved. Do not start another refund, use Force done, or finalize the
return until authoritative reconciliation marks the new operation verified.

Ticket 28 remains open for its own scope and closure decision. Tickets 22 and
23 remain closed on their own controlled live retests. Ticket 12 remains open
for this refund's final outcome and POS receipt, final test-money
reconciliation, target-device
tip/report observations, Restaurant checkout, remaining failure/recovery
cases, and final release documentation/combined-artifact acceptance.

## Native historical printing gate — ticket 36

Before ticket 12 closes, verify the integrated release's native POS historical
**Details** and **Print Receipt** using a saved paid sale at least one week old,
without an accounting invoice, with its original session closed and a fresh
browser load. Check Revolut references and that reprinting changes no payment
or refund outcome and initiates no terminal transaction. Separately retrieve
and print an existing native accounting invoice. Preserve Odoo's normal later
invoice-creation flow without automatically invoicing every sale.

On the physical terminal, confirm current and historical transaction-history
receipt printing still works. The owner's earlier report of working terminal
history and disposable browser/PDF tests do not establish physical-printer
acceptance. Ticket 34 independently retains native invoice PDF verification
after separately authorized staging repair/rollout; missing historical invoice
fixtures are a blocker, not permission to create a financial transaction.


## External refund acceptance gate — ticket 37

Before closing ticket 12, accept the automatically discovered external refund
workflow described in [the release evidence](../../testing/ticket-12-release-evidence.md#external-financial-refunds--ticket-37-candidate)
and [ticket 37's local verification](../../testing/ticket-37-external-refunds.md).
Recheck the dated source 36 refund `6abf7eec` and existing source 16 operation 6
`6abe5180` with their full original references. Keep one card financial record
and reservation per provider refund; discovery must send no financial POST.
Verify original-sale links, provenance, per-card remaining capacity, pending
state safety and manager native reconciliation separately from product, cash
and accounting work. Preserve return 1012 and its existing Odoo identity.

The reported pending financial operations still require current reconciliation
before guarded rollout. Mocked ticket 37 tests do not settle those live refunds
or authorize deployment or additional money movement.

## Missing native return repair — 2026-10-05

The operator reports all refunds completed and that `1012` no longer exists in
POS. Read-only SQL confirms operations 5 and 6 are verified/completed, but no
native order exists for their original return UUID. Candidate `19.0.1.14.1`
addresses the missing pre-dispatch draft save and offers manager recovery from
existing verified allocations. It preserves original identities and creates a
draft without another provider refund or automatic stock/accounting effects.
See the [current repair checkpoint](../../testing/ticket-12-release-evidence.md#current-refund-repair-checkpoint--2026-10-05)
and [recovery operating instructions](../../installation.md#partial-and-allocated-revolut-returns-pos-manager).
The cause of browser draft loss itself remains unproven. Native receipt
validation and remaining physical/release gates keep this ticket open.

The repair passed final 463-test install and 463-test upgrade suites, 9
Restaurant tests, 79 POS lifecycle tests and both exact artifact scenarios.
Standards and Spec review have no remaining findings. The guarded staging
upgrade installed `19.0.1.14.1` from `30492a67020acdfe34d7f560a9cf6d7fb20f6430`.
After the operator's explicit approval, Administrator user 2 received access
to GBP register 2. Public manager recovery restored native draft order 24,
shown as **2 (Refund)**, with the original return UUID and both existing
verified penny refunds. The ledger still contains six Odoo-origin refunds.
The current next step is operator review and **Validate** on that draft; no
replacement refund is needed. The final receipt is still an open live gate.

## Saved-return server protection — 2026-10-05

The requested server-side matching draft/payment requirement is implemented
in candidate `19.0.1.15.1`, with direct authenticated API rejection tests,
preserved legacy replay and automatic POS persistence. Full install/upgrade
passed 478 tests each; exact-archive acceptance passed 80 checks. Standards
and Spec reviews found no remaining findings. See the
[verification and deployment record](../../testing/refund-saved-return.md).

The guarded deployment stopped before changing staging because 15 unresolved
external discovery evidence records block financial preflight. Nine lack a
verified source association and six report missing original credential
attribution. The count does not establish pending money movement. Staging
remains `19.0.1.14.1`; no evidence was cleared or credential grant inferred to
force rollout. Authoritative reconciliation and the established administrator
attestation process must precede another guarded deployment. The recovered
native receipt and other physical acceptance gates remain open.

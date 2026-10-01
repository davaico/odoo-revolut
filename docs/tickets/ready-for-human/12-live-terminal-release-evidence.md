# 12 — Validate real terminal payments and publish release evidence

**Work branch:** `codex/12-live-terminal-release-evidence`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-human

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
- 22 — Recover a POS line after a terminal-busy rejection (reviewed local fix; live retest open)
- 23 — Preserve payment polling through valid processing states (reviewed local fix; live retest open)
- 24 — Bound financial snapshot processing before numeric expansion (closed; final combined release evidence remains required)

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
[22](../ready-for-human/22-recover-terminal-busy-rejection.md) and
[23](../ready-for-human/23-preserve-polling-through-payment-processing.md) preserve
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

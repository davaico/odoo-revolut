# 12 — Validate real terminal payments and publish release evidence

**Work branch:** `codex/12-live-terminal-release-evidence`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-human

## What to build

Controlled real-terminal acceptance establishes whether the documented addon is ready for use, with traceable payment/refund evidence and complete operating instructions.

## Acceptance criteria

- [x] Confirm the reviewed release includes completed corrections 16–21 and an independent review of the payment-verification boundary. Before live acceptance, record the full integrated mocked suite on the final combined revision: install/upgrade, Restaurant, lifecycle, deployment checks, restart recovery, delivered-artifact acceptance and the new adversarial regressions for tickets 19–21.
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
- 22 — Recover a POS line after a terminal-busy rejection (open live finding; needs triage)
- 23 — Preserve payment polling through valid processing states (open live finding; needs triage)

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
[22](../needs-triage/22-recover-terminal-busy-rejection.md) and
[23](../needs-triage/23-preserve-polling-through-payment-processing.md) preserve
these release findings and their mocked characterizations without claiming a
fix or deployment. Their triage and reviewed fixes/retests are required before
closure; they do not prevent read-only reconciliation of the pending refunds.

Ticket 12 remains open. Final refunds/test-money reconciliation, Restaurant,
remaining failure/race/interruption subcases, provider discrepancies and final
observed operating guidance remain incomplete. No addon code is changed by
this evidence update, and it does not authorize bypassing financial guards or
upgrading/restarting staging while unresolved refunds remain.

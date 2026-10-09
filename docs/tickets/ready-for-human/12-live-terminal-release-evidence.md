# 12 — Retest the complete integration before release and open-source publication

**Work branch:** `codex/12-live-terminal-release-evidence`

**State:** open

**Triage:** ready-for-human

**Updated:** 2026-10-09, after concurrent tip-refund submission.

Start new implementation work from the latest reviewed `main`, preserving this
handoff and any local documentation edits. PR #70 is already merged.

## Start here

Read the [current manual testing handoff](../../testing/ticket-12-fresh-retest-2026-10-08.md)
first. It contains completed manual subcases, current refund state, financial
budget, operator setup, open issues and the next test. Then consult the
[R01–R24 checklist](../../testing/ticket-12-final-release-checklist.md) for the
specific scenario being run. Read [release provenance](../../testing/ticket-12-release-evidence.md)
when verifying deployment or automated coverage. Older chronological logs are
available through Git history; loading them is not required to resume.

## Current checkpoint

- Campaign: **Revolut Acceptance — 2026-10-07**, GBP retail; operator testing is
  underway. Resume unfinished subcases, not the original empty-register setup.
- Last verified deployment: **19.0.1.18.9**, merged PR #70, retaining PR #69's
  independent fix. Source/artifact/backup and test results are in release provenance.
- Manual automatic tipped checkout and both cancellation directions succeeded.
  The latest test successfully submitted a separate £0.01 tip refund while the
  £0.01 product refund was still pending on the same £0.02 sale.
- **Three refunds remain pending at the last observations:** a full £0.01 refund
  on another sale, plus the product/tip pair. Submission success is not final
  completion. Keep existing references/reservations; Validate stays blocked
  until verified completion. No Force done or replacement refunds.
- Next: inspect existing refund states, verify PRODUCT/TIP reload recovery with
  no new dispatch, finalize the same returns only when verified, and continue
  independent Cash/terminal-contention tests if still pending.
- Approved gross card-charge cap **£0.25**, recorded spend **£0.10**, remaining
  **£0.15**; tips count and refunds do not replenish it.
- Open acceptance issues include clipped printed references, a supported first
  allocation entry path for the fresh two-card test, negative permission
  feedback, final refund/native reconciliation, and unexecuted checklist rows.

## Acceptance criteria

- [x] Dedicated GBP register prepared/opened; initial empty native Orders,
  £0.00 cash and empty-basket reload observed. Preserve its current history.
- [x] Campaign automated baseline A01–A10 completed October 8, with exact-source
  carry-forward limits recorded; later fixes have focused/artifact verification.
- [x] Current deployed candidate, artifact, review, backup and health verified
  October 9. Reverify drift and affected coverage before final release freeze.
- [ ] Complete all applicable R01–R24 subcases with separate UI/device/backend
  evidence. PARTIAL/PENDING rows are not full passes; preserve explicit blockers.
- [ ] Reconcile charges, pending/completed refunds, Cash, base/tip allocations,
  native quantities/documents, reservations and approved retained balances.
- [ ] Complete native full/partial/mixed/multiple-source returns and external
  refund goods/no-goods/existing-return/recovery paths without duplicate money.
- [ ] Accept Restaurant, authorization/pricing/rounding, interruptions/concurrency,
  recovery, keyboard usability and session closure on appropriate fixtures.
- [ ] Accept current/historical native receipts, physical and terminal printing,
  and an existing native invoice PDF. Resolve the clipped-reference print issue.
- [ ] Review complete combined automated/artifact coverage at final source freeze;
  mocked checks do not replace manual physical-device evidence.
- [ ] Finalize install, configuration, secrets/rotation, upgrade, operator and
  reconciliation guidance from actual observations.
- [ ] Resolve private evidence preservation/publication review, licensing and
  chosen distribution material/history; record owner go/no-go. Publication
  itself remains a separate authorized action.

## Dependencies and closure

Implementation tickets 40–46 are closed inputs; do not reopen them merely to
run acceptance. Remaining closure gates:

- [33 — Evidence preservation/publication review](../needs-info/33-investigate-release-evidence-disclosure.md):
  permanent restricted archive/custodian/mapping and actual publication material/history.
- [34 — Native invoice PDF acceptance](34-provision-and-gate-odoo-pdf-generation.md).
- Physical operator/terminal, supported controlled-failure methods and suitable
  Restaurant, rounding, permissions, historical document and external-refund fixtures.

Destructive/forged-request/race tests belong in disposable databases with mocked
Merchant HTTP. Preserve old registers and completed refunds; outstanding
historical native dispositions are identified in the handoff. Ticket 12 remains
open until mandatory financial, manual, document and publication gaps are resolved.

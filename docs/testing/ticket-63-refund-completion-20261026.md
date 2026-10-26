# Ticket 63 — refund completion continuation, 2026-10-26

Base and integration target: `feat/v18_rev`. Live candidate at entry: frozen
`fcb59c4`, addon 18.0.1.0.3. No new collection is authorized or performed.
Exact identities and credentials remain in restricted evidence.

## Provider verification

After the owner explicitly authorized restoration of the exact existing
credential reference, the original local environment was reopened without
upgrading or replacing its database. A fresh private snapshot was saved.
All five outstanding refunds from the two latest acceptance batches are now
provider Completed / locally verified: GBP 0.01, 0.01, 0.02, 0.02 and 0.01.
The two GBP 0.02 refunds each comprise GBP 0.01 base and GBP 0.01 terminal tip.
Reconciliation ran in a GET-only process that rejected financial POSTs.

The remaining previously authorized GBP 0.01 refund against the other source
of the earlier split return was submitted once through native allocation.
The already-refunded source was disabled. This final refund is processing;
its original native return remains incomplete. No existing refund was replayed.
The normal worker's Merchant HTTP block was restored and verified afterward.

## Native return result and blocker

Two returns completed through normal Validate and were independently confirmed
paid in the database. Two other fully verified returns fail native validation
with “The refund payment details do not match Revolut verification.” Their
browser tenders show done but lack a transaction reference. The backend rejects
them rather than accepting incomplete proof. They remain drafts; no Force done
or direct financial-record repair was used. The initial progress statement that
four returns had completed was premature; independent database checks identified
the two failed validations.

The defect is under focused synthetic reproduction. Final acceptance, affected
session posting and release sign-off remain open until it is resolved and the
last refund and native return finish. Already accepted physical limitations
and previously passed non-refund checks are unchanged.

Private before/after snapshots confirm all 14 original payment operations retain
their business fields (only ORM write timestamps changed on five), all 27
payment dispatch claims remain, and exactly one new refund operation was added
for the previously unsubmitted final split leg. No new collection occurred.

## Focused diagnosis

A deterministic native browser regression reproduced the failure by recovering
a completed refund, re-reading its saved waiting tender through native Odoo
`pos.data.read`, then selecting normal Validate. The retained restored flag was
insufficient after that read removed transaction references. A state regression
also failed before correction. Initial focused corrected-browser coverage passed
three tests; independent review identified the additional same-return multi-tender
case, now being covered before deployment. No original records are changed by
the isolated mocked test runs.

The proposed 18.0.1.0.4 update was rehearsed on a separately restored acceptance
database, with an internal-only network, no production key mount and Merchant
HTTP blocked. Update exited 0; all nine snapshotted financial/native tables
matched exactly before and after. This is an upgrade-preservation check, not
proof that the browser defect is fixed; original-record retesting remains required.


## Final result

Reviewed fix committed locally as `334c8a8f7e0a80f31e7de2eca0a7fe7a5fadf6bb`,
addon 18.0.1.0.4, on `feat/v18_rev`. A stale successful recovery flag is
invalidated when native refund references no longer match verified evidence.
Validation restores the committed evidence after native reads and projects all
verified refund tenders after the final shared refresh. Order, draft-state,
tender-membership, snapshot and operation-identity guards fence that projection.
Backend settlement checks are unchanged; no financial requests were added.

Verification: 142 state tests passed; the original native overwrite regression
failed before the fix and passed afterward. Three focused browser cases passed.
The two-refund native regression passed independently and again on a fresh
database with final source: both tenders done, exact distinct references, one
paid return, exactly two intended refund POSTs. A combined four-test attempt
had three passes and a Chrome script/shutdown timeout under severe host memory
pressure; it is retained as a failed attempt, not reported as four green.
The standalone final run used 1 GiB shared memory after idle task resources were
released, with no source change or timeout increase. Independent review found
no remaining concrete blocker. Temporary diagnostic code was removed.

The local candidate update exited 0 with Merchant HTTP blocked. All nine
financial/native snapshot tables remained exactly unchanged across the update.
Both originally failing returns then passed normal native Validate and receipt
presentation, with matching original references and correct negative amounts.
No existing refund was replayed and no original financial row was repaired.

Both fully refunded Restaurant sessions closed through native controls and
posted balanced accounting moves: GBP 0.03 debit and GBP 0.03 credit each, zero
net card total and zero counted difference. Their four returns are finalized;
the five old refunds all have correct linked native tender references. The
remaining old refund belongs to the earlier split return, which stays draft
until its second leg finishes. These service-product fixtures create no stock
pickings; this does not assert physical stock movement.

Final GET-only check: the newly submitted last GBP 0.01 refund is still
processing/pending. Its original split return and session remain open. Finish
that same refund/return, verify session accounting, then record final release
sign-off. No other physical test is newly required; the previously accepted
untested limitations remain explicit. No monitor was created. Worker Merchant
HTTP blocking is restored and verified; cron remains disabled. Disposable
rehearsal database and diagnostic test resources were removed.

Ticket 73 is resolved on Odoo 18. Odoo 19 has a similar fast path but is not
validated by this work; ticket 74 records a separate reproduction/parity check.
This continuation has not pushed the new fix or granted overall release approval.

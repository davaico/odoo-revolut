# Ticket 12 — Manual testing handoff

Updated **2026-10-12**, through completed usability regressions, refund receipts,
the session closure attempt and new recovery ticket 47. This campaign began October 7.
Read this file first; use the [R01–R24 checklist](ticket-12-final-release-checklist.md)
for full subcase requirements. Resume unfinished subcases rather than restarting
the campaign. A successful subcase does not pass an entire checklist row.

## Authoritative handoff checkpoint — October 12

Latest continuation: actual saved FULL return PDF passed inspection; one
session-close attempt was rejected for active drafts. Close/reopen is blocked
by the preserved pending/unsettled return 1019. Its campaign test is DONE /
OWNER-ACCEPTED: continue independent work without waiting or repeating it.

New R19 scenario: cashier Price disabled PASS; manager could enter £0.02, but
exact cart approval was not reached. Missing Tip Product blocked preparation;
owner restored existing Tips. After reload, the unstarted waiting tender could
not be removed: first red X displayed a communication-failure message, later
clicks did nothing visibly. This is [ticket 47](../tickets/needs-triage/47-recover-unstarted-tender-after-reload.md),
needs-triage. Preserve order 1022 / saved order 59 and tender 79. Read-only SQL
at 09:40:19 UTC confirms no payment attempt/cart authority, counts 72/161/17,
Price Control restored to false and Tips product 1 configured (native Tips on).
Do not repeat removal, clear storage or create a replacement order/tender.
Manager-approval testing is BLOCKED pending safe recovery; no code fix/deployment.

Agent follow-up completed: **125 JavaScript passed; 62 Python passed, 3 PDF
skipped**. Focused Odoo rerun could not start (Docker unavailable). Read-only
staging audit at 08:48–08:50 UTC reconciled Paid totals and found no duplicate
refund references or excess refund allocations. Refund 20 remains processing;
1019 stays owner-accepted but its native draft still needs settlement before
session closure. Correction 13 remains empty/draft. The current checklist now
maps existing automated coverage and supersedes the broad 4–8-hour manual plan
with the owner's **three-hour maximum**. Do not repeat completed scenarios.

Read the [current acceptance summary](ticket-12-final-release-checklist.md#current-acceptance-summary--october-12-owner-handoff)
for finished checks, owner acceptance of return 1019, remaining work and time
estimates. All five PR #73 UI regressions passed; five campaign native return
validations/receipts passed. Owner explicitly accepts 1019 as finished/working;
remove it from the manual retest queue, while preserving its last observed
processing refund/draft return for operational reconciliation. Ticket 12 stays
open. Earlier entries below are historical evidence, not the current task list.


## Older closed-session sale receipt — PASS for preview, October 12

Operator selected original sale 261-2-000014 dated September 30 and supplied
its one-page browser print preview. It shows quantity 1, £0.01 total and
Revolut tender, original receipt date September 30 11:39, a readable wrapped
payment reference and Davai GBP Terminal Test. Preflight read-only SQL
verified order 14, original sale name ending 000014, state done, total £0.01,
and original session Davai GBP Terminal Test/00003 closed. The sale is older
than one week at this October 12 retest. Close the older-sale/closed-original-
session retrieval and receipt-preview subcase under R16.

No actual Save as PDF, physical print or explicit fresh-browser/reload was
reported; those properties are not inferred from the preview. No new payment,
refund or invoice creation was requested. Three current-campaign finish-up
stages remain: two-card return 1019 finality/validation, final reconciliation,
and session close/reopen. These stages are not the full release acceptance
scope; setup-dependent and controlled technical coverage remain separate.
Refund 20/source 69 was still pending/processing at the latest read-only check
on October 12 08:29:30 UTC. Refund 19/source 70 remained verified/completed,
and return 57 remained draft. Do not infer a newer provider outcome from this
receipt test.


## Draft return link label / navigation — PASS, October 12

Operator supplied the opened native return and then its parent refund form.
The form is refund 19 / original card source 70 (not the requested newer source
69), showing Completed, Native return awaiting validation and Odoo Return
261-3-000019. Clicking the link reached the existing New/draft return with page
title 261-3-000019, quantity −2 and original sale 000017. Its underlying Order
Ref remains /, while the user-facing title/link correctly uses the POS reference.
Close the original slash-only link-label failure and PR #73 targeted R17
label/navigation retest using this same historically failing fixture.

Do not infer source 69 / refund 20 finality from the source-70 Completed status.
The newer refund remains processing at its last read-only observation, and
return 1019 validation is still pending. No new refund, backend Payment action,
edit or validation was requested during this UI check. The pending native
completion label is appropriate for the displayed draft return.

All five recorded PR #73 usability-fix retests now passed within their stated
scope: historical Paid Orders loading, Choose amount Enter, payment/Retry
keyboard focus, association layout/Create affordance, and draft return link.
This does not close wider association, accounting, setup-dependent acceptance
or the unfinished two-card refund/native return.


## Existing-return association layout / Create affordance — PASS, October 12

Operator opened external refund 10 for Davai GBP Terminal Test – 000018,
Complete native work, Associate an existing native return, and its existing-
return dropdown. Screenshot shows a full-width usable selector, normally
wrapped instructions, readable table headings and base/tip columns, and no
former horizontal overflow or vertically wrapped Association Lines label.
The dropdown displays No records and no Create option. Close the two original
UI failures and PR #73 targeted layout/Create-affordance retests (R15/R17).

No return was selected and no Review native work/association was reported.
No records only establishes the displayed empty result; it does not prove the
selector's full eligibility rules, successful compatible association or server
rejection of incompatible records. Those R15 cases remain open. This is the
existing no-goods fixture with outstanding native disposition/correction draft
13; do not invent a goods return to populate the selector. Cancel this dialog.
No new financial action or native disposition was requested in the retest.


## Choose amount Enter regression — PASS, October 12

Operator followed the order 1018 / Payment / Choose amount £0.01 / Enter-once
steps and supplied the resulting screenshot. One £0.01 Revolut line is shown,
Send has a clearly visible keyboard focus outline, no electronic-payment-in-
progress alert appears, remaining £0.01 and Validate disabled. This matches
the intended unsent amount-confirmation state. Close the original Choose amount
Enter failure and targeted PR #73 manual retest (R17). No Send activation was
requested or reported in this test.

Read-only SQL at 08:11:37 UTC confirms unchanged totals of 72 payment operations,
161 payment dispatch claims and 17 refunds, supporting no newly recorded
payment operation/dispatch. Lookup by assumed POS reference 261-3-000018 found
no saved order, so no individual backend order identity/state is claimed for
this browser draft. The screenshot establishes its visible state. No live card
payment or successful terminal-send keyboard test is claimed, and no repeat
financial test is required to close this specific error/focus regression.


## Keyboard focus visibility — PASS, October 12

In response to the explicit question about clearly seeing focus while tabbing
through Cash, Revolut and Retry, the operator confirmed Yes. Combined with the
preceding keyboard Retry activation and read-only terminal-unavailable audit,
close the original payment-method/Retry keyboard focus visibility failure and
the targeted PR #73 manual retest under R17. Cash and Revolut focus/reachability
and Retry focus are operator-confirmed; Retry activation was exercised. This
does not claim keyboard activation of Cash/Revolut, Choose amount Enter
handling, or all other keyboard paths. No additional request or payment was
made for this confirmation.


## Keyboard Retry / unavailable terminal — PASS for activation, October 12

The operator activated Retry using the keyboard on order 1020 while the
physical terminal was off, and reported it worked. Screenshot shows Terminal
unavailable — no charge sent, Retry available, £0.01 remaining and Validate
disabled. Read-only SQL at 08:02:47 UTC confirms one new retry operation 72,
linked to cancelled operation 71 and existing draft order 58: failed /
terminal_unavailable, retry_safe true, no capture recorded, no terminal lock.
Operation 72 has zero payment dispatch claims. Counts are 72 operations (+1),
161 dispatch claims (unchanged), 17 refunds (unchanged). No new recorded
order/intent dispatch occurred; the original order remains draft.

Close keyboard Retry reachability/activation (R17) and this terminal-unavailable
safe-failure subcase (R06/R07). User activated Retry rather than merely moving
focus; do not infer visible focus on both Cash and Revolut from this screenshot
or mark the entire keyboard-focus failure resolved. Payment-method reachability
and focus-outline clarity, including Retry's outline before activation, still
need explicit operator confirmation. No repeated retry or card presentation
requested. Terminal availability failure is expected for the reported powered-
off device, not an unexpected integration failure. Charge budget unchanged.


## Historical external-return receipt preview — PASS, October 12

After the historical Paid Orders loading retest passed, the operator selected
4 (Refund) / 260-2-000004 and opened Print Receipt. The screenshot shows a
one-page browser preview for Davai GBP Terminal Test, ticket 260-2-000004,
original receipt date October 9 at 13:35, quantity −1, total −£0.01 and Revolut
tender −£0.01. Content is readable and fits the page. Close the previously
blocked external native return 53 receipt retrieval/rendering subcase under
R13/R16. Together with the preceding populated-history screenshot, the former
Paid Orders error no longer blocks this fixture.

No provider refund/original reference footer is visible in this historical
receipt; do not claim reference-printing coverage from it. Existing backend
refund linkage was verified separately. Save as PDF is selected but no file
save or physical print was reported. This three-day-old return does not prove
the broader week-old/closed-session receipt requirement. No new refund,
invoice creation or backend mutation was requested. Two-card refund 20 remains
pending at its last backend observation; no status refresh was performed here.


## Historical register Paid Orders — PASS, October 12

Operator followed the targeted Davai GBP Terminal Test / Orders / Paid retest.
Screenshot shows Paid selected, count 1–19 / 19 and populated historical orders
without the former quantity/remaining-monetary-entitlement error. The first
row is 4 (Refund), POS reference 260-2-000004, Paid −£0.01, matching the
previously verified external native return 53 for original sale 000014.
Close the specific historical Paid Orders loading failure under R13/R16/R17:
PR #73's targeted manual history-loading retest passes. The earlier failure
entries retain their historical release scope; they are no longer an active
loading blocker. No backend mutation or new financial action was requested.
Next inspect Print Receipt on that existing top-row return; historical receipt
preview remains open until observed. No physical print, saved PDF or broader
history/session-age coverage is inferred from the list screenshot.


## FULL Paid Orders reprint — PASS, October 12

Following the guided Orders / Paid / Print Receipt steps, the operator supplied
a browser print preview for ticket 261-3-000003 in POS config 3 (Revolut
Acceptance). The populated order history is visible behind the preview. The
one-page preview shows quantity −1, total and Revolut tender −£0.01, and
readable wrapped refund/original references matching the earlier FULL receipt.
Close the current-register FULL history retrieval and reprint-preview subcase
(R16). This screenshot does not prove a saved PDF, physical printing, explicit
browser reload, zero outbound HTTP requests, or that the earlier entitlement
failure in config 2 (Davai GBP Terminal Test) has been fixed in its original
fixture. That historical-register regression remains open for a targeted
read-only retest using completed return 53 / 260-2-000004 / 000014 REFUND.
Pending two-card return 1019 remains untouched; no financial action requested.


## Two-card remainder submitted — PENDING, October 12 07:51 UTC

On return 1019 the operator observed source 70 Refund Successful −£0.01,
remaining −£0.01 and Validate disabled. Allocation picker showed source 70
exhausted/disabled (0 remaining), source 69 selected with £0.01 remaining,
base £0.01 and tip £0.00. Operator then confirmed the remaining allocation
once. Screenshot shows source 69 Refund in process, both −£0.01 tenders,
remaining −£0.01 and disabled Validate. Exhausted-source display, remaining
allocation and partial-completion guard subcases PASS; final two-card return
completion remains PENDING.

Read-only SQL at 07:51:55 UTC verifies new refund 20, source 69, pending /
processing, base 1 minor unit and tip 0, dispatched 07:51:27 UTC. Its saved
return/tender UUIDs match existing return 57 / 261-3-000019 and new tender 78
(waiting). Direct native foreign keys are currently blank for refund 20.
Existing refund 19 / source 70 remains verified/completed with its October 10
verification timestamp, linked to return 57 and tender 76 (done). There are
exactly two refund records with two distinct provider references for these
sources, combined 2 minor units. Return 57 remains draft, total/recorded paid
−£0.02; waiting tender is not proof of completion. Counts are now 71 operations,
161 payment dispatch claims and 17 refund records (+1 refund). This is
record-level evidence, not exact outbound HTTP single-dispatch proof.

One new £0.01 refund now awaits provider finality; the six earlier refunds
remain completed. Preserve this same return and both references. Do not Force
done, send another allocation or validate until the remaining refund is
verified successful. Resume with Check status if offered after the wait limit;
final negative receipt/native validation remains open. No new card charge;
gross charge budget remains £0.06. Five prior native return checks remain PASS.


## DISCOUNT native completion — PASS, October 12 07:46 UTC

Operator receipt for 1014 / 261-3-000014 shows quantity −2 at £0.01, the
original 50% discount and total/Revolut tender −£0.01, with refund/original
references. Read-only SQL at 07:46:21 UTC confirms existing return 51 Paid,
total/paid −£0.01, quantity −2, price_unit £0.01 and discount 50%; existing
tender 69 is done with matching UUID. Refund 18 retains verified/completed,
amount 1 minor unit and the October 10 verification timestamp; direct links
restored to 51/69. Counts remain 71 operations / 161 payment dispatch claims /
16 refunds. Close this discounted full-return native validation, retained
pricing and on-screen receipt subcase (R21/R11/R16), plus its native-tender
reconciliation subcase (R18). Wider fractional/global-rounding partitions,
physical printing, history persistence, exact outbound refund HTTP evidence
and final accounting are not claimed. Pre-validation automatic status recovery
was not separately reported. Refund Initiated wording remains the R17 observation.

FULL, PRODUCT, TIP, MIXED and DISCOUNT native validation/receipt checks passed.
Only the two-card return 1019 remains among the six original pending returns:
source 70 has already refunded £0.01; source 69 has not. Inspect its Payment
screen before any further allocation or validation; do not resend source 70.


## MIXED native completion — PASS, October 12 07:44 UTC

Before validation, the operator screenshot for 1013 showed total −£0.02,
Revolut −£0.01 Refund Successful/source 63, Cash −£0.01, zero change and
Validate enabled. After validation, receipt 261-3-000013 shows quantity −2,
total −£0.02 and both original −£0.01 tenders with refund/original references.
Read-only SQL at 07:44:26 UTC confirms existing return 50 Paid, total/paid
−£0.02; Cash tender 67 −£0.01 and Revolut tender 68 −£0.01/done. Refund 17
retains verified/completed, base 1 minor unit/tip 0 and the October 10
verification timestamp; direct links restored to 50/68, card tender UUID matches.
Ledger counts remain 71 payment operations / 161 payment dispatch claims /
16 refunds. Close MIXED native validation/link restoration, tender-split and
on-screen receipt subcases (R10/R11/R16), plus this native-tender reconciliation
subcase (R18). Physical cash handover, printed receipt, exact outbound refund
HTTP proof and final session/accounting reconciliation are not claimed.

FULL, PRODUCT, TIP and MIXED native validation/receipt checks are now complete.
DISCOUNT and the two-card return remain. Receipt-screen Refund Initiated
wording repeats the existing R17 observation. Next: existing DISCOUNT return
1014; use its successful £0.01 refund, without another financial request.


## TIP native completion — PASS, October 12 07:42 UTC

Operator receipt for 1009 / 261-3-000009 shows Tips quantity −1, total and
Revolut tender −£0.01, £0.00 base plus −£0.01 tip, and refund/original
references. Read-only SQL at 07:42:32 UTC confirms original return 40 Paid,
total/paid −£0.01, tender 56 done with matching UUID and restored direct links.
Refund 16 remains verified/completed, base 0 and tip 1 minor unit, with the
same October 10 verification timestamp. PRODUCT return 39/tender 53 also
remain Paid/done. Their combined verified refunds are 2 minor units (base 1,
tip 1), exactly source 58's captured 2 minor units, including tip 1.

Close TIP native validation/link restoration and on-screen receipt subcases
(R05/R10/R11/R16), and this product-plus-tip financial/native-tender
reconciliation subcase (R18). Ledger counts remain 71/161/16. No new refund
record is observed; exact outbound HTTP dispatch proof, physical print,
history persistence and wider accounting effects are not claimed. The
pre-validation status-recovery interaction was not separately reported.
FULL, PRODUCT and TIP are now complete for these native validation/receipt
checks. Three other native returns remain: MIXED, DISCOUNT and two-card.
Refund Initiated wording repeats the existing R17 observation.


## PRODUCT native completion — PASS, October 12 07:41 UTC

Operator supplied the negative receipt for 1008 / 261-3-000008: quantity −1,
total and Revolut tender −£0.01, refund and original references displayed.
Read-only SQL at 07:41:09 UTC confirms existing return 39 Paid, total/paid
−£0.01, existing tender 53 done with matching UUID, and refund 13 still
verified/completed (base 1 minor unit, tip 0, October 10 verification timestamp).
Direct links are restored to 39/53. Ledger counts remain 71 operations / 161
payment dispatch claims / 16 refunds. Close PRODUCT native validation/link
restoration and on-screen receipt subcases under R10/R11/R16. The screenshot
does not independently establish whether status recovery was automatic.
No physical printing or exact outbound refund HTTP proof is claimed.
FULL and PRODUCT are complete; four other native returns remain. Next is TIP
1009, using its existing successful refund, without a new financial request.
Receipt-screen Refund Initiated wording repeats the existing R17 observation.


## Latest result — FULL return completed, October 12 07:39 UTC

FULL / 1003 is now PASS for automatic status recovery, native validation and
on-screen receipt. Return 34 is Paid −£0.01, tender 48 done, refund 12 still
verified/completed with restored links and unchanged ledger counts (71/161/16).
The operator needed no Check status; one Validate click opened the matching
negative receipt. Five other returns still require completion/reconciliation.
Receipt-screen wording says Refund Initiated although the refund is completed;
retain as an R17 wording observation. Older six-draft snapshots below describe
the pre-validation state, not the current FULL result.

## Current checkpoint — refund finality confirmed, 2026-10-12

All six awaited refunds are verified/completed and the owner confirms receipt
of the £0.06. Their financial-completion checks are CLOSED. No provider waiting
remains. Read the [October 12 refund audit](ticket-12-final-release-checklist.md#refund-completion-audit--2026-10-12) for each result and outstanding native work.
All six returns remain drafts with waiting card tenders and blank direct refund
links, although saved UUIDs locate the correct records. Next: recover the same
FULL return and verify native completion; no new refund is needed. Return 1019
also has an unrefunded £0.01 second source. Accounting correction 13 and broader
refund fixtures remain open. Ticket 12 is not complete. Installed .18.11 was
read-only verified; no new deployment or money request was made.

## Checkpoint — manual evidence reconciled with PRs #73 and #74

The last deployment verified in this campaign is **19.0.1.18.10 / PR #72**.
PR #73 (code `7d553c1`, addon **19.0.1.18.11**) is now merged into main:
it addresses the Paid Orders entitlement error, Choose amount Enter handling,
payment/Retry keyboard focus, existing-return association layout/Create option,
and draft-return link label. PR #73 records deployment of main `557f8a8` with 118 file hashes, installed
version, service and login health checks verified. Targeted manual retests
remain outstanding; the earlier failures below retain their original
version scope. No new deployment or runtime pass is claimed by this update.
The revoked-register feedback retest already passed on .18.10; grants were
restored and the payment ledger was unchanged. Do not repeat passed subcases
without a specific regression reason. Ticket 12 remains open.

PR #74 closed [ticket 34](../tickets/closed/34-provision-and-gate-odoo-pdf-generation.md) after native staging invoice PDF inspection and
repeat retrieval. Physical printing was explicitly skipped; historical and
closed-session checks in ticket 12 remain separate.

Remaining work is explicitly separated:

- Implemented in PR #73, awaiting targeted retest: historical register Paid
  Orders entitlement error (reproduced on current deployment, receipt blocked);
  Enter after Choose amount alert; POS payment/Retry focus visibility;
  existing-return association layout/Create affordance; '/' draft link label.
  Revoked-access feedback subsequently passed its owner-selected .18.10 live retest; grants restored and payment ledger unchanged.
- Provider outcome resolved October 12: all six refunds completed and funds
  received. Complete/reconcile their SAME draft returns and check negative
  receipts, original capacity and totals. The second card source on return
  1019 is not refunded.
  Final session closure/reopening follows reconciliation; closure guard itself
  is not yet exercised. Do not send replacement refunds or force-close.
- Genuinely untested manual scenarios needing fixtures/setup: Restaurant
  dine-in/takeaway/table controls (current registers are retail); restricted
  price approval by manager; controlled terminal decline/failure; compatible
  existing-return association and tracked-stock/accounting effects. Wider
  external discovery/attribution cases remain partial. No fresh financial
  transactions solely to fill missing fixtures.
- Accounting/document blockers: financial-only correction draft 13 needs an
  appropriately authorized accountant. Native invoice PDF acceptance is now
  complete under ticket 34; do not retain the earlier missing-fixture blocker.
- Controlled technical cases: precise dispatch/capture races, interrupted
  reservations, verified-to-native-save failures, lost-draft reconstruction,
  fractional/rounded partitions and concurrent managers use disposable/mocked
  scenarios, not ad hoc cashier clicks. Existing automated evidence must be
  mapped to the final candidate; do not label all these tests untested merely
  because their live R rows are incomplete. .18.10 remediation reports 619
  clean-install tests plus focused browser/JS/PDF checks; full final artifact,
  upgrade and coverage provenance still require review at release freeze.

Already passed/accepted recently: split amounts and persistence, backend
capture/native-tender reconciliation, automatic terminal cancellation display,
pending-refund reload/status continuity, base/tip hints, manager return-link
navigation and quantity editor. Single printed payment reference is explicitly
accepted. Positive refund-line subtotal magnitudes were explained as native
representation by the remediation investigation, not an established accounting
bug. Do not send these back as blanket failure retests. Remaining live charge
budget £0.06; all pending/cancelled drafts and correction evidence preserved.

## Latest continuation

The manual results below were observed through PR #72 / .18.10. Resume from
the checkpoint above: confirm the browser uses the deployed PR #73 candidate before retests,
preserve pending refunds, and prepare remaining fixtures separately. The
chronological selections below are historical instructions, not a new test queue.

## Earlier resume checkpoint

1. Read-only staging verification at **2026-10-09 10:18 UTC** confirmed
   **19.0.1.18.9 / PR #70**, the expected release symlink and active service.
   No provider call or financial mutation was made by the agent.
2. PRODUCT and TIP refresh/Check status UI continuity is observed and explicitly
   confirmed by the operator. FULL also recovered Refund in process after
   Check status with the same amount/references; its earlier explicit reload
   confirmation remains open. Backend records match all three displayed refund
   references and retain all three saved draft returns and payment lines.
   Counts match the handoff (one FULL, two referenced PRODUCT/TIP and two earlier
   failed tip attempts). This supports no additional refund record; exact
   HTTP dispatch-count proof remains open because there was no fresh backend
   snapshot immediately before the operator's reloads. FULL is locally
   unresolved with recorded provider state processing; PRODUCT/TIP are
   pending/processing. No refund is verified complete.
3. If a refund has completed, recover/check its existing status, validate that
   same return when eligible, then inspect the negative receipt, Orders entry
   and native amounts/links. Record provider completion separately from funds
   arriving in the cardholder's bank account. If still pending, leave it open
   and continue an independent case; do not wait days before continuing testing.
4. R01 current-release Cash smoke is PASS. First R08 run confirms busy
   rejection and two final backend cancellations. Both final cancelled UI states
   are now observed. A required refresh and had no Check status available at
   that recovery point: record automatic cancellation-display recovery FAIL,
   cause unverified. Do not repeat financial attempts to recreate it without a
   planned retest. Explicit physical terminal-idle confirmation remains open.
   Owner explicitly deferred investigation; the failure is recorded directly
   on ticket 12. R08 manual near-simultaneous starts now show A winning, B
   rejected and no B attempt; A cancelled. Operator confirms B Check status
   twice, A cancellation displayed without refresh, and terminal idle: this
   manual contention/repeated-status/cancellation subcase PASS.
   R01/R08 grant revocation now exercised: screenshot with only Administrator
   granted shows native pos.payment create-access denial, not the intended
   register-grant message. At 10:43:25 UTC both grants are restored; counts
   remain 61 operations, 140 dispatch claims, 13 refunds, zero active payments.
   No-dispatch/restoration checks PASS; intended denial feedback FAIL and exact
   register-check path not isolated. Check status is read-only; do not Resume
   merely to prove observation. Restored provider-start access is not tested.
   Latest R02 .18.9 test-cashier sale is verified/captured £0.01 with zero tip,
   native Paid and matching receipts while all three refunds remain pending.
   Operator confirms terminal £0.01 GBP/approval, automatic checkout and
   browser refresh before reopened receipt: current R02 retail flow PASS.
   Exact approval-to-receipt delay is unmeasured (no duration supplied). At 10:47:56 UTC: 62 operations / 142 claims /
   13 refunds; one new successful order/intent pair. Card budget now £0.14.
   R03 fresh split sale now verified: £0.02 total, £0.01 Cash and £0.01
   captured Revolut; unpaid intermediate screen observed. At 10:53:26 UTC
   counts are 63 operations / 144 claims / 13 refunds. Operator confirms idle
   terminal during Cash-only stage, terminal £0.01 GBP, automatic checkout and
   browser refresh before reopened receipt: Cash/card split subcase PASS. Preserve this
   two-unit sale as MIXED for later mixed-tender return; budget now £0.13. Leave prior denied/cancelled drafts untouched. No precise race injection on staging. The live multi-card
   amount-entry blocker below must be solved before attempting that R03 subcase.

## Execution priority — avoid repeated passed tests

Owner requests faster completion and no unnecessary repeats. Current-release
Cash smoke, ordinary no-tip retail sale, Cash/card split (including unpaid
intermediate state), manual contention/repeated-status and PRODUCT/TIP reload
subcases are already covered. Do not rerun them without a relevant code change,
new failure or specifically identified missing acceptance requirement. Preserve
their remaining parent-row gaps rather than repeating whole scenarios. Earlier
repeat sales closed concrete current-release/device/partial-payment gaps; those
gaps are now closed. Skip refresh/reprint on a new pricing case unless that
case itself requires it; ask for its device/automatic result in the initial
instructions to avoid an extra confirmation turn. Reuse MIXED and other eligible
paid fixtures for their planned refunds; do not recreate originals.

**R19 per-line cashier discount: PASS.** Existing settings
verified: manual_discount on, restrict_price_control off, cash rounding off,
automatic terminal validation on. Use quantity 2 at £0.01 with 50% line discount
for a £0.01 no-tip card sale; preserve it as DISCOUNT for a later R21 discounted
return. At 10:55:32 UTC baseline 63 operations / 144 dispatch claims / 13 refunds,
all three existing refunds processing; no active payment. Card budget £0.13
before this test. At 10:57:34 UTC, receipt and SQL confirm 50% discount,
quantity 2, canonical payable/captured/native total £0.01, zero tip, one
order/intent pair (64 operations / 146 claims / 13 refunds). Preserve as
DISCOUNT; budget now £0.12. Operator confirms terminal £0.01/approval and
automatic checkout; the basket screenshot need not be repeated because receipt and
saved line establish the discount. Other R19/R21 requirements remain open.

The operator now requests **all steps of one test together**. Supply a complete
scenario with stop conditions, then inspect its result.
Update the relevant checklist row and this checkpoint after each test. Keep
observed UI, backend verification and untested expectations distinct.

## Active refunds — preserve these attempts

These aliases identify scenarios, not provider identifiers. Locate them in the
campaign register using original sale, amount, component and pending return;
retain exact IDs/references in restricted evidence, not this shared document.

| Alias | Original sale | Base / tip / total | Last observation | Next acceptance |
| --- | --- | --- | --- | --- |
| FULL | Late-success, no-tip £0.01 sale | £0.01 / £0.00 / £0.01 | Check status recovered Refund in process, same −£0.01/references and disabled Validate; 10:18 UTC backend unresolved/processing; 10:31 UTC pending/processing | R09 finality, native validation/receipt; finish R11 identity proof |
| PRODUCT | Latest automatically completed £0.02 tipped sale | £0.01 / £0.00 / £0.01 | Operator confirms refresh before Check status; before/after screenshots show Refund pending then Refund in process, same −£0.01/refund/original references and disabled Validate | Backend identity/single-dispatch proof, then finality/native settlement |
| TIP | Same original as PRODUCT | £0.00 / £0.01 / £0.01 | Operator explicitly refreshed after Request sent stalled; Check status recovered Refund in process with the same amount/refund/original references and disabled Validate | Backend identity/single-dispatch proof, then finality/native settlement |

PRODUCT and TIP have **two distinct provider references and idempotency keys**
on the same paid original. Combined active amount is £0.02: the whole original
£0.01 base + £0.01 tip is reserved. Two earlier tip attempts failed
`original_ineligible` before dispatch, have no provider reference and do not
count in that active sum. Concurrent submission passes; completion does not.

The owner explicitly wants multiple pending refunds against one original,
within its reserved component/gross limits. They also chose to keep **Validate
blocked until verified completion**. Preserve both decisions. Do not use Force
done, replace a processing refund, clear reservations manually, refund the same
amount again, or force-close the session. A missing final native order link
alone does not prove the saved pending return is missing.

## Environment and authorization

- Staging: `https://odoo-revolut.davaiodoo.com`, POS `/pos/ui/3`.
- Register: **Revolut Acceptance — 2026-10-07**, retail, GBP, initial opening
  cash £0.00. Existing sessions and all financial history must be preserved.
- Methods: **Revolut - Davai** and **Cash - Acceptance 2026-10-07**; automatic
  order validation enabled. Native **Tips** product mapping exists; operator
  now reports tipping enabled in checkout and sees the terminal tip menu.
  Recheck saved settings before any configuration-dependent case.
- Current operator: Administrator. A separate internal POS User was configured
  and explicitly granted register access; its no-tip sale and split sale
  succeeded. Current screenshots do not establish fresh non-admin acceptance.
- Owner approved aggregate **£0.25 gross card charges**, including tips, and
  allows retained charges. Recorded spend **£0.13**, remaining **£0.12** after the verified discounted sale.
  Refunds do not replenish this budget. Count uncertain charges until reconciled;
  Cash smokes are separate and still need final cash reconciliation.
- This is a physical production Merchant terminal used with staging Odoo.
  Automated tests mock all Merchant calls. Read-only staging inspection is
  appropriate; run destructive/race/forged-request tests only in disposable DBs.
- Deployment/review details and local log locations:
  [release evidence](ticket-12-release-evidence.md). Read
  [staging deployment](../staging-deployment.md) before any further deployment.

## Manual results so far

| Case | Observed result | Still missing |
| --- | --- | --- |
| R01 setup/reload | Dedicated GBP register opened with zero cash; empty native Orders filter and empty-basket reload observed | Complete attempt/session evidence and broader access/revocation cases |
| R01 Cash | Current .18.9 smoke PASS: £0.01 Cash receipt, Paid backend with one Cash tender, explicit refresh confirmation and matching reopened receipt preview. Operator reports everything worked in response to the remaining checks, including terminal inactivity. Payment/dispatch/refund counts unchanged at 10:23 UTC. Earlier Cash evidence retained below/in Git history | Final Cash reconciliation; wider R01 permission/setup subcases remain separate |
| R01 permissions | Ungranted test-user attempt rejected with pos.payment AccessError, not the expected register-grant message. Later explicit grant and successful cashier checkout | Repeat precise negative permission case with correct native permissions; do not mark the earlier error as the intended denial PASS |
| R02 retail | Earlier .18.4 cashier success retained. New .18.9 cashier £0.01 no-tip sale: successful receipt, Paid Orders and reopened preview observed; 10:47 UTC backend verified/captured GBP 1 minor unit, zero tip, native Paid and one order/intent pair. Three refunds remain pending | Current R02 retail flow PASS: operator confirms terminal £0.01 GBP/approval, automatic checkout and refresh before reopened receipt. Exact delay unmeasured; long-reference clipping remains under R16 |
| R03 split | Current .18.9 two-unit £0.02 sale: Cash £0.01 / remaining £0.01 unpaid screenshot, then waiting card with Validate disabled; final receipt, Paid Orders and reopened preview agree. Backend captured only £0.01, zero tip, native distinct Cash/Revolut £0.01 shares and one order/intent pair | Cash/card split subcase PASS with explicit operator terminal idle/£0.01 GBP, automatic checkout and refresh confirmation; two-card UI path blocked; preserve MIXED fixture for later mixed-tender refund |
| R05 tips | First £0.01 base + £0.01 tip sale needed Check status after warning. After .18.6, repeat £0.02 sale reached receipt entirely automatically; backend verified base/tip/gross and one successful order/intent dispatch pair | Final tip refund, remaining no-tip/report subcases |
| R06 cancel | After .18.5, Odoo Cancel stopped payment on both Odoo and terminal; terminal-origin cancellation then detected automatically | Backend/timing detail, controlled decline/failure/retry and capture/cancel race |
| R07 timeout | 60-second local wait expired while terminal remained active. Terminal cancellation plus Check status recovered Cancelled. Reload then cancellation also recovered | Remaining interruption boundaries and dispatch/identity proof |
| R07 late success | £0.01 payment after timeout recovered through Check status to receipt; Paid Orders and reopened receipt observed after requested reload | Complete backend dispatch/identity verification for the scenario |
| R08 contention | Administrator A / authorized test cashier B: busy warning observed in B while operator confirms terminal retained A; A cancellation screenshot, then B waiting-for-card screenshot. At 10:31 UTC backend both £0.01 operations cancelled/retry-safe, distinct draft orders, terminal locks released; exactly one order/intent pair and one cancellation claim each; B created after A cancellation | Final A/B cancelled UI observed; A required refresh and operator reports Check status unavailable at the final recovery step: automatic UI recovery FAIL. Post-refresh ledger counts unchanged at 10:34 UTC. Physical terminal-idle confirmation, explicit earlier B busy Check status observation, warning/cancel-response explanation and other R08 subcases remain open |
| R09 full refund | FULL submitted; Odoo and Revolut Processing; Validate disabled | Verified completion and native settlement |
| R10/R05 partial + tip | PRODUCT submitted, then TIP accepted while PRODUCT pending after .18.9 fix; backend confirms two references, component sum and same original | Both completions, native settlement and remaining-capacity enforcement |
| R11 pending reload | FULL screenshot after guided reload retained same reference/amount/processing and disabled Validate. TIP refresh explicitly confirmed by operator; Check status recovered Refund in process, same −£0.01/refund/original references and disabled Validate. PRODUCT refresh explicitly confirmed; screenshots after guided refresh/status steps retain the same −£0.01 and references, changing Refund pending to Refund in process; Validate disabled | Backend records/references and three draft returns confirmed at 10:18 UTC; exact HTTP single-dispatch proof and FULL explicit reload confirmation remain open; investigate TIP Request sent stall |
| R16 print | Split-sale, reopened late-sale and current .18.9 Cash-sale native previews show correct totals/tenders; Cash receipt reopened after confirmed browser refresh | Long reference clipped with scrollbar; saved PDF, physical/historical/invoice and terminal printing unverified |

Full R04/R12–R15/R17–R18/R20–R24 scenarios remain unexecuted in this campaign;
partial overlaps above do not waive their distinct requirements. Restaurant,
rounding, restricted-price and tracked-stock fixtures need explicit setup.
The [checklist](ticket-12-final-release-checklist.md) defines every remaining
subcase and final financial/document/publication gates.

## Current-release Cash smoke — 2026-10-09

At **2026-10-09 10:18:34 UTC**, staging has 58 payment operations, 131
payment dispatch records and 13 refund operation records. The campaign session
is open in retail mode with a tip product configured; it contains 10 paid
orders totalling £0.13, three draft returns totalling −£0.03 and one cancelled
£0.01 order. These are native order totals, not a new card-spend calculation.
Compare counts and the specific new Cash order after the smoke; unrelated
activity must be distinguished.

The operator then supplied a £0.01 Cash receipt and matching Paid Orders entry
for the new sale, served by Administrator. Read-only SQL at **10:23:03 UTC**
confirms that exact sale (created **10:22:25 UTC**) is Paid, total/amount paid
£0.01, zero change, exactly one £0.01 Cash tender and zero linked Revolut
payment operations. Counts and maximum IDs in all three ledgers are unchanged
from the 10:18:34 baseline: **58 payment operations, 131 payment dispatches,
13 refunds**. Backend Cash settlement and no new recorded Revolut dispatch
PASS. The operator explicitly confirmed refreshing before the Orders screenshot,
then supplied the matching reopened native print preview (£0.01 total /
£0.01 Cash) and reported "everything worked" in response to the remaining
checks, including the terminal staying idle. **R01 current-release Cash smoke
PASS**; broader R01 permission/setup requirements remain open. Save as PDF is
selected in the preview; a saved PDF file or physical print is not established. All three pending return tabs remain visible.
Card-charge budget remains £0.15; add this Cash penny to final cash reconciliation.
Evidence is the chat screenshots and read-only SQL tool output; this summary
does not fulfill ticket 33's durable restricted archive gate.

## R08 first two-browser run — 2026-10-09

Operator confirms A is Administrator and B is the previously authorized test
cashier, using distinct browser sessions. B displayed Terminal busy — no payment
request sent while the physical terminal retained A's request. A also displayed
Communication interrupted — payment unresolved; this is not evidence that its
terminal request had stopped. Subsequent screenshots show A cancelled and B
waiting for card; the last supplied A screen instead says Request sent. Do not
infer final UI recovery from those screenshots alone.

Read-only SQL at **10:31:41 UTC**, compared with the **10:27:08 UTC** baseline,
shows 60 payment operations (+2), 137 dispatch claims (+6), and 13 refunds
(unchanged). Both new £0.01 operations are cancelled with recorded provider
state cancelled, retry_safe true, no payment reference or verified timestamp,
and cleared terminal locks. Each has exactly one successful create_order and
create_intent claim, and one cancel_intent claim with outcome **unresolved**.
Final operation cancellation is confirmed; successful cancellation POST
acknowledgement is not claimed. A's cancellation claim was at 10:30:32 UTC;
B's operation was created at 10:30:45 UTC and cancelled at 10:30:59 UTC.
No additional attempt appears for busy rejection or interim observation.

Both native orders remain draft; stored payment lines remain waiting and draft
amount_paid is £0.01. Those fields are not proof of successful payment. A later screenshot confirms both existing lines show Payment cancelled with
Retry and disabled Validate. Operator reports Check status was unavailable for
this final recovery step and explicitly says A required a page refresh to show
cancellation. Automatic cancellation-display recovery on A is **FAIL**; refresh
recovery is **PASS**, with cause unverified. Read-only verification at
**10:34:12 UTC** confirms unchanged counts/max IDs (60 operations, 137 dispatch
claims, 13 refunds), both operations still cancelled/retry-safe with cleared
terminal locks and both orders still draft. No additional attempt/dispatch was
recorded during refresh. All three
original refund references remain present; FULL is now pending/processing like
PRODUCT/TIP. No new captured payment is recorded; card budget remains £0.15.
Busy rejection and backend serialization/cancellation subchecks PASS; R08 stays
PARTIAL with the observed A UI recovery failure and other unexecuted subcases. B's use of Check status
while busy and exact user action timing are not separately confirmed. Existing
screenshots/SQL outputs are working evidence, not the ticket 33 durable archive.

## R08 manual near-simultaneous starts — 2026-10-09

Operator reports A was clicked slightly before B and owned the terminal.
Screenshots show A Waiting for card, B Terminal busy — no payment request sent,
then A Payment cancelled while B remains busy-rejected. This demonstrates the
observed manual ordering, not a precisely synchronized server race.

Read-only SQL at **10:38:29 UTC** versus the **10:35:50 UTC** baseline confirms
61 payment operations (+1), 140 dispatch claims (+3), 13 refunds (unchanged).
The only new operation belongs to A's £0.01 order: cancelled/provider cancelled,
retry-safe, terminal lock released, no payment reference. Its claims are one
successful create_order and create_intent plus one cancel_intent whose response
outcome remains unresolved despite final cancellation. A's and B's new native
orders are both draft; B has **zero payment attempts**. Accepted/rejected starts
and backend non-duplication/cancellation subchecks PASS. Operator explicitly confirms two B Check status clicks, A displaying Payment
cancelled without refresh this time, and the physical terminal returning idle.
**This manual contention/repeated-status/cancellation subcase PASS.** Earlier UI recovery FAIL remains open and
its investigation deferred. No additional card charge recorded; budget £0.15.

## R01/R08 grant revocation — 2026-10-09

First screenshot shows only Administrator in the register grant list and the
test cashier rejected with native **create access to pos.payment** denied,
under Revolut cart needs correction. It also states no payment request was
sent. This reproduces the earlier negative-permission feedback gap: intended
register-grant explanation **FAIL**, specific guard path not isolated. Do not
infer a general POS-role misconfiguration or bypass from this screen alone.

Second screenshot shows the test cashier restored in the grant list; its
payment line still says Review or approve the cart — no new payment request
sent. Operator reports Check status does not relaunch payment: this is expected
read-only behavior. The screen appears to be the newly denied line rather than
the earlier busy-rejected line, so successful restored server-read authority
is not established by this screenshot. Resume was not requested for this test.

Read-only verification at **10:43:25 UTC** confirms Administrator and the test
cashier both granted, with counts/max IDs unchanged from **10:40:26 UTC**:
61 payment operations, 140 dispatch claims, 13 refunds; zero nonfinal payment
operations. Saved grant restoration and no new recorded dispatch **PASS**.
Physical terminal inactivity and a restored-access server interaction are not
separately confirmed. No additional card spend recorded. Outcome remains
PARTIAL; feedback failure recorded directly on ticket 12.

## R02 no-tip sale after regrant — 2026-10-09

Operator supplied successful £0.01 Revolut receipt, Paid Orders entry and
reopened native print preview from the test cashier. Backend at **10:47:56 UTC**
confirms one new operation verified/captured, GBP base/captured/gross all 1 minor
unit, tip 0, native Paid total/tender £0.01, correct cashier and payment link,
and exact provider-payment reference matching the receipt. Counts changed from
61/140/13 to **62 operations / 142 dispatch claims / 13 refunds**. Both new
claims succeeded: order at 10:46:34 UTC, intent completed 10:46:35 UTC; verified
at 10:46:55 UTC. These server times do not establish terminal-to-receipt latency.
FULL/PRODUCT/TIP remain pending/processing with the same provider references.
Restored cashier payment access and new-sale coexistence with pending refunds
PASS. Operator explicitly confirms terminal £0.01 GBP and approval, automatic
checkout, and refreshing B before reopening the order/receipt. **Current R02
retail payment flow PASS** with receipt/Orders/tender/reference consistency.
No numerical terminal-approval-to-receipt delay was supplied: timing remains
unmeasured; server timestamps are not substituted for the operator observation. Print preview still clips the long reference with a horizontal scrollbar;
no PDF save or physical print claimed. Spend now **£0.11**, remaining **£0.14**.

## R03 fresh Cash/card split — 2026-10-09

Screenshots show £0.02 order, £0.01 Cash allocation with £0.01 remaining and
Validate disabled, then a £0.01 Revolut line waiting for card while the order
remains open. Successful receipt, Paid Orders entry and reopened print preview
all show two £0.01 product units and Cash £0.01 / Revolut £0.01. The long
reference remains clipped/scrolling in print preview.

Read-only SQL at **10:53:26 UTC** confirms native Paid £0.02, correct test
cashier, quantity 2 at £0.01, distinct Cash/Revolut £0.01 tenders, card line done,
and one verified/captured GBP operation for base/captured/gross 1 minor unit,
zero tip. Its payment reference matches the receipt. One successful order/intent
pair, no duplicate: ledger counts **63 operations / 144 dispatch claims / 13
refunds**, versus 62/142/13 baseline. Existing three refunds still pending/
processing. Intermediate-unpaid and backend allocation/settlement subchecks
PASS. Operator explicitly confirms terminal idle during Cash-only stage, then
terminal £0.01 GBP, automatic checkout and actual refresh before reopening the
receipt. **Cash/card split subcase PASS**; R03 remains partial because the
separate two-card allocation UI path is blocked. Gross card spend
now **£0.12**, remaining **£0.13**; account separately for this Cash penny.
Preserve this sale as **MIXED**, the fresh two-unit mixed-tender-return fixture;
no refund has been requested for it.

## R19 cashier line discount — 2026-10-09

Receipt shows two units at £0.01, 50% off £0.02, £0.01 total and one £0.01
Revolut tender, served by the test cashier. Read-only SQL at **10:57:34 UTC**
confirms quantity 2, unit price £0.01, discount 50%, line total £0.01, native
Paid and Revolut tender done £0.01, verified/captured GBP 1 minor unit with
zero tip, exact receipt reference and correct cashier. Linked cart authorization
has base/payable 1 minor unit. Exactly one successful create_order/create_intent
pair; counts **64 operations / 146 dispatch claims / 13 refunds**. Discount
pricing and native/card settlement subcheck **PASS**. No pre-payment basket
screenshot supplied; receipt and stored line establish the same pricing, so
no repeat is requested. Operator explicitly confirms terminal £0.01 and approval, with automatic
Odoo checkout: **line-discount subcase PASS**. Keep this sale as **DISCOUNT** for a
later discounted return; R19's other cases and R21 are not passed by this sale.
Card spend **£0.13**, remaining **£0.12**.

## Known issues and behavior to retain

- **Observed UI failure:** during R08, A remained on Request sent despite
  backend cancellation and required browser refresh to show Payment cancelled.
  Operator reports no Check status available at that final recovery step. Both
  A/B now display cancelled; read-only ledger comparison proves no new
  attempt/dispatch during refresh. Root cause and relation to the earlier
  communication-interrupted warning/cancel-response uncertainty are unverified.

- **New observation, cause unverified:** opening the existing TIP return showed
  Request sent with a spinner and Force done. Operator reported it remained
  stuck, then refreshed and clicked Check status. The next screenshot shows
  Refund in process with unchanged amount and refund/original references;
  Validate remains disabled. Exact wait duration and UTC event time were not
  captured. UI recovery is observed, not automatic restoration or backend proof
  of zero duplicate dispatch. Evidence is the before/after screenshots in the
  resumed chat; durable restricted preservation remains outstanding.
- **Open:** long Revolut reference clipped/scrolling in native print preview.
- **Open:** native auto-dispatch starts the first card allocation before the
  cashier can enter a smaller amount; the fresh two-card test is blocked on a
  supported UI path. Do not use browser internals to manufacture acceptance.
- **Open:** exact negative user/register permission feedback and evidence.
- **Expected:** local 60-second waiting expiry does not cancel the terminal.
  Recover the existing operation with Check status; timeout is not nonpayment.
- **Fixed and manually retested:** cancel/status-check overlap (.18.5), automatic
  tipped checkout (.18.6), concurrent product/tip refund submission (.18.9).
  The original tipped transient payload was not retained; the matching defect
  was reproduced, but the old warning's exact cause was not conclusively proven.
- **Preserved:** PR #69 allows ordinary new sales while API refunds are pending.
  Its real browser regression passed with PR #70; live .18.9 cashier sale now
  verified/captured and native Paid while all three existing refunds remain
  pending with their original references. Operator confirms automatic checkout;
  exact terminal-approval-to-receipt delay remains unmeasured.
- Tip dialog retains the terminal-tip remaining allowance. The misleading
  whole-return hint beneath the base field was removed in .18.9.

## Historical obligations that still matter

The pre-campaign six Odoo refunds were verified/completed. Their formerly lost
split return was recovered and validated to a −£0.02 native receipt on October 5
without replacement refunds. That recovery is complete; do not repeat it.

Historical externally initiated refunds still require native disposition review:
including the older penny sale ending 000018 (owner previously said no products
needed returning; its separate Cash penny also needs disposition evidence),
and the credential-unbound historical refund imported after
approved authority attestation on October 9. Financial verification/import is
not native product-return or accounting completion. Inspect current evidence and
any existing native work before R13/R14; never issue those refunds again. Full
historical mappings remain in Git history/restricted server evidence.

Ticket 33's durable restricted evidence preservation/publication review remains
open. [Ticket 34](../tickets/closed/34-provision-and-gate-odoo-pdf-generation.md)'s
native invoice PDF acceptance closed on October 9 after actual PDF inspection
and operator-confirmed repeat downloads; physical printing was skipped by the
owner and the original session remains In Progress. Ticket 12's other historical,
session and physical printing checks remain separate. Ignored build logs and
temporary screenshots are working copies, not a completed permanent archive.

## Maintaining this handoff

Keep this checkpoint current in place; append only distinct evidence, not whole
conversation transcripts. Put complete criteria/status in the checklist and
revision/test provenance in release evidence. Old chronology is recoverable
from the pre-compaction commit linked there. No financial history was deleted
by this documentation cleanup. Ticket 12 remains **open / ready-for-human**.


## R10 mixed-tender return — 2026-10-09 11:07 UTC

Reused MIXED sale 3005 / 263-3-000005 (source #63), without a new sale.
Operator screenshots show a full £0.02 return allocated as £0.01 Cash and
£0.01 Revolut, source #63, base £0.01 and tip £0.00. Read-only staging SQL
confirms saved draft return 261-3-000013, total −£0.02, native Cash −£0.01
and waiting Revolut −£0.01. Exactly one refund record exists for source #63:
base 1 / tip 0 minor units, provider reference matching the screenshot,
local unresolved / provider processing, no verified completion. Ledger totals
are 64 payment operations / 146 payment dispatch claims / 14 refunds (max 17).
No new card charge; approved remaining budget stays £0.12. Allocation and draft
persistence observed; completion, native final settlement and physical terminal
idle confirmation remain open. Preserve this existing return and reference.

Operator reports manually typing positive Cash 0.01 initially increased the
remaining refund magnitude. Installed native Odoo payment-screen code passes
the signed numeric buffer directly to setAmount; no refund-sign normalization
occurs there. The addon delegates editable amount input to that native handler.
The screenshots and saved draft show Cash corrected to −£0.01 before dispatch.
Record as a cash refund-entry usability gap, not evidence of an incorrect
provider refund or completed positive cash tender. Investigation/change deferred.

The allocation dialog's “Remaining on this return: 0.00 £” is specifically the
available terminal-tip component: template calls defaultTip, which takes the
minimum of remaining source tip and return tip. Zero is correct for this no-tip
sale, but the generic label is ambiguous. Record wording FAIL / usability
follow-up: label should explicitly identify the tip component. Operator also
requests a separate hint beside the base refund amount: “Remaining base refund
on this return (excluding tips)”. Show the eligible base amount for the selected
source and this return, respecting existing allocations; never add terminal-tip
capacity to that figure. Keep the tip hint separate and explicitly labelled.
This is a recorded UI requirement; no implementation or deployment in this test. The source card
balance £0.01 and base allocation £0.01 are correct. Payment-screen remaining
−£0.01 while the Revolut line is pending is consistent with the uncompleted card
refund; Validate is disabled. Do not alter the correct cash line or add another
refund to make the pending balance disappear.


## R21 discounted full return — 2026-10-09 11:10 UTC

Reused DISCOUNT sale 3006 / 263-3-000006, source #64. Operator screenshots show
base refund £0.01, tip £0.00, then Refund in process with the original/source
references retained and Validate disabled. Read-only SQL confirms exactly one
refund for source #64, pending / provider processing, base 1 / tip 0 minor units,
no verified completion, and provider reference matching the screenshot. Saved
return 261-3-000014 remains draft, total −£0.01, quantity −2, original unit price
£0.01 and 50% discount; one waiting Revolut tender −£0.01. Submission and retained
quantity/discount evidence recorded; R21 remains PARTIAL pending final refund,
native settlement and its separate partition/global-rounding/adjustment cases.
Operator explicitly confirms the physical terminal stayed idle during this discounted refund.

Reconciliation observation to retain: saved price_subtotal_incl on the return
line is +£0.01 although the native order total is −£0.01 and quantity is −2.
Cause and final accounting effect are not investigated in this manual step;
do not mark native line/tax/accounting consistency passed from the order total.
Preserve the existing pending refund; do not recreate it to investigate this.
Ledger totals: 64 payment operations / 146 payment dispatch claims / 15 refunds
(max refund id 18). No new card charge; remaining approved budget stays £0.12.


## R19 unrestricted cashier unit-price override — PASS, 2026-10-09 11:13 UTC

Operator reports the complete requested test worked: test gary changed one
£0.01 product's unit price to £0.02 with quantity 1 and discount 0%, confirmed
the terminal amount/no-tip payment and automatic checkout. Receipt for sale
3007 / 263-3-000007 shows one unit at £0.02, total and Revolut tender £0.02.
Read-only SQL at 11:13:18 UTC confirms cashier id 7, saved quantity 1 / unit
price £0.02 / discount 0%, native Paid £0.02, tender done £0.02 and operation
#65 verified/captured 2 minor units, zero tip, gross 2. Receipt payment reference
matches; exactly one successful create_order and one create_intent claim exist.
Counts: 65 payment operations / 148 dispatch claims / 15 refunds (max 18).
Unrestricted manual-price subcase PASS; no redundant reload/reprint requested.
R19 restricted manager approval, stale-cart and post-exposure cases remain open.
Cumulative approved gross card spend is now £0.15 of £0.25; remaining £0.10.
Refunds do not replenish the budget. Existing pending returns remain unchanged.

The same screenshot incidentally shows DISCOUNT refund source #64 back at
Request sent, with its existing reference and Validate disabled, after the
previous Refund in process screenshot. No operator action/timing or fresh
refund-state query established why; retain this UI observation without treating
it as a new refund or proof of completion. Investigation remains deferred.


## R17 manager refund keyboard access — 2026-10-09

Operator confirms keyboard focus works and is visible, and Check status could
be activated. Screenshots show the manager refund list and DISCOUNT refund
form with Details visible, focus on Original Card Payment #64, matching refund
reference, base 1 / tip 0 minor units and pending / reported processing state.
Visible focus and keyboard Check status subcase PASS; do not infer complete
cashier/payment/recovery keyboard coverage or every list-navigation step.
Read-only SQL after the action retains 65 payment operations / 148 dispatch
claims / 15 refunds (max 18), unchanged from the preceding sale check. No new
financial record observed; source #64 still pending/processing.

The two red Failed rows are the known earlier £0.01 tip-only attempts #14/#15
against source #58, created at 09:12:49 and 09:13:03 UTC, with provider_state
original_ineligible and no Revolut refund references. These are historical
failed attempts, not failures of the new MIXED or DISCOUNT refund. Preserve
them as audit history; do not retry/recreate them now that the later tip refund
already exists.

R17 clarity follow-up: pending Odoo-origin refunds display blank Odoo Return
and Native completion “Not required”. For DISCOUNT, SQL confirms pos_order_id
is unset but order_uuid identifies the saved draft already verified at 11:10.
Do not interpret the blank link as a missing draft, or “Not required” as permission
to skip native completion. Review the linkage presentation and applicability of
this label for Odoo-origin refunds; final settlement remains required. Investigation
deferred with other ticket 12 findings. Overall R17 remains PARTIAL.


## R12 historical external-refund matching — 2026-10-09

Operator supplied native original-sale, external-refund Details and Revolut
Orders screenshots for the historical sale ending 000018. Native sale shows
two units at £0.01, total £0.02; read-only SQL confirms £0.01 Cash plus £0.01
Revolut. Thus the dashboard original card order amount £0.01 is consistent
with the native £0.02 mixed-tender total. Odoo refund record #10 is external,
verified/provider completed GBP 1 minor unit against original operation #36;
full stored original/refund references match the Odoo screenshot. Native
completion is Outstanding with no linked return. Do not issue another refund.

Revolut list shows the matching original reference prefix at £0.01 Paid on
October 1 and refund prefix at −£0.01 Refunded on October 2. The opened provider
detail panel is the original payment, not the refund. Exact full refund-ID and
original-transaction relationship confirmation in the provider UI remains open;
prefix/amount/date agreement is observed, not full-ID comparison proof.
The differing October 2 provider initiation and October 5 Odoo import times
are explicitly distinguished in Odoo. Counts remain 65 payment operations /
148 payment dispatch claims / 15 refunds (max 18). No new financial record
observed. R12 PARTIAL: stored linkage and visible prefix/amount match checked;
full provider comparison, repeated discovery and wider shared-account cases
remain open. R14 native disposition and the separate Cash penny remain open.


### R12 provider refund-detail follow-up

Operator opened the actual historical external refund in the Revolut dashboard.
Screenshot shows the matching refund prefix, October 2 at 11:52 AM, status
Refunded and a −£0.01 card reimbursement. Provider refund amount/status/date
and visible reference-prefix comparison PASS. The heading's positive £0.01
is the displayed magnitude; the reimbursement line is explicitly negative.
The Order ID remains abbreviated in this screenshot, so exact full-ID comparison
and provider-side original-transaction relationship are not newly established.
A copy control is visible beside Order ID; compare its copied value with Odoo's
full Refund Reference to close the remaining identifier check without another
payment, refund or repeated screenshot. R12 overall remains PARTIAL, with
wider discovery cases and separate native disposition still outstanding.


### R12 full refund-reference confirmation

Operator supplied the complete Order ID copied from the provider refund detail.
It exactly matches the full Revolut Refund Reference on historical external
refund #10, previously verified by read-only SQL. Full refund-ID, amount and
completed-status matching subcase PASS. The stored link to original operation
#36 / sale ending 000018 is verified in Odoo; direct provider UI evidence of
that original-transaction relationship remains separate. Overall R12 remains
PARTIAL for wider discovery/shared-account/repeated-discovery requirements.
Native completion remains Outstanding; this identifier confirmation performs
no financial or native accounting action. No repeat of this matching test needed.


## R14 no-products correction preparation — 2026-10-09

For the existing verified external refund #10 / historical sale ending 000018,
pre-test read-only SQL found no linked correction and no existing account.move
for this refund. Operator followed No products returned / Review native work.
Screenshot shows a Draft journal entry linked to that exact refund and original
sale, but only Other Info is visible; no Journal Items tab or line editor is
shown. Read-only SQL confirms one linked draft account.move #13, move_type entry,
journal #10, and zero account.move.line rows. Refund now links correction #13,
native completion remains Outstanding and final financial_only_reason is blank.

Source inspection confirms this is intentionally an empty linked draft for an
uninvoiced original: action_prepare_financial_correction supplies no journal
lines and leaves account selection to accounting review. The earlier instruction
to check generated £0.01 lines overstated what preparation implements. Draft
creation/linkage subcase PASS; monetary correction and completed R14 are NOT
passed. Current screen lacks the journal-line editor needed to continue; record
this UI/access/configuration blocker without assuming its cause or widening
permissions. Preserve draft #13 unposted and reuse it later, not a new correction.
Accounting review must supply and verify the exact original-card settlement
correction; the separate Cash penny remains untouched. No products/quantities
were selected in this flow. No new financial request was authorized by this step.


## R13 external refund product-return preparation — 2026-10-09

Reused external refund #11 / source #20 / historical sale ending 000014.
Pre-test SQL confirmed a verified/completed £0.01 refund, one original £0.01
product paid wholly by Revolut, no linked native return/correction or prior
returned line, and an open session on its original register. Operator opened
Complete native work and selected the return quantity after guidance locating
the editable “Quantity re…” column. Its truncated label required clarification;
retain this R17 usability observation.

Screenshot and read-only SQL confirm saved draft return #53, named original
sale + REFUND, quantity −1 at £0.01 and zero discount, linked to original line
#15, total/paid −£0.01. Existing external refund #11 now links order #53 and
payment #71, Revolut −£0.01 with status done; native completion native_draft.
The provider refund remains verified/completed. Counts unchanged: 65 payment
operations / 148 dispatch claims / 15 refunds (max 18). Preparation/linkage
subcase PASS; no added financial record observed. Reload, final validation,
stock/accounting effects and receipt remain unverified.

The screenshot and saved line again show positive £0.01 tax-exclusive and
inclusive subtotals despite quantity −1 and native total −£0.01. This reproduces
the earlier DISCOUNT draft subtotal-sign discrepancy on an undiscounted external
return. Preserve for deferred investigation; native line/accounting consistency
is not passed. Do not manually edit the original price or subtotal to hide it.


### R13 external native validation result — 2026-10-09 11:37 UTC

Operator screenshots show return #53 Paid at −£0.01 and external refund #11
Native return completed with the correct Odoo Return link. Read-only SQL
confirms native_completed, manager Administrator (id 2), native_reconciled_at
11:37:14 UTC, same return #53/payment #71, base 1 / tip 0 minor units, and native
Paid total/paid −£0.01. Existing provider refund remains verified/completed.
Payment operations / dispatch claims / refunds remain 65 / 148 / 15 (max refund
18), unchanged from preparation: no additional financial record observed.
The returned product is a service; zero stock pickings is consistent with that
configuration. Native validation/linkage and service inventory subcases PASS.
Explicit operator refresh confirmation and native POS receipt remain unverified.

The positive £0.01 stored tax-exclusive and inclusive line subtotals persist
AFTER validation despite quantity −1 and total −£0.01; this is not only a draft
display observation. Record native line-total consistency FAIL on ticket 12;
accounting impact remains uninvestigated. R13 overall stays PARTIAL rather than
passing the entire native/accounting/receipt criterion. Preserve the finalized
return and refund; do not redo the return or change its amounts to conceal this.


### R13/R16 Paid Orders loading failure — 2026-10-09

During the requested receipt check for completed external return #53 (historical
sale ending 000014), the operator reports that opening Paid Orders raises
“Invalid Operation: The return exceeds the original quantity or remaining
monetary entitlement.” The screenshots show Paid selected and pagination
“1-19 / 19”, but “No orders found”; dismissing the error leaves that empty list.
Evidence: operator screenshots ending 1d4c820b and f63bc72b in this chat.

Paid-history loading subcase FAIL; R13 native receipt/reprint and the associated
R16 PDF check are BLOCKED by this failure, not passed. The previously verified
Paid native return and native_completed linkage remain separate passed evidence.
These screenshots do not establish deletion, a duplicate refund, the triggering
record or the root cause. No new backend/dispatch check was performed for this
observation. Defer investigation per the operator's instruction; preserve the
completed return, pending refunds and open sessions. Do not repeat the return,
change quantities, or clear browser storage as a workaround.


### R16 physical terminal receipt — 2026-10-09

Terminal transaction-history reprint subcase PASS. Operator located the existing
£0.02 transaction for cashier order 3007 / native reference 263-3-000007, printed
its receipt, and explicitly confirmed printing succeeded and receipt information
looked correct. Read-only SQL beforehand matched source operation #65 to that
native order and confirmed requested/captured 2 minor units. The terminal showed
the Revolut order-reference prefix, whereas the initially supplied reference was
the separate payment ID; the matching order reference was then verified and
provided. The terminal clock was reported incorrect (showing 08:48), so matching
used transaction identity and amount rather than displayed time.

This is operator-confirmed physical terminal output; no receipt image was
supplied. No new payment was requested for the test. No post-print ledger check
was performed, so this observation does not independently prove zero dispatch
delta. R16 overall remains PARTIAL: Odoo receipt-reference clipping, blocked
Paid-history loading, saved PDF/historical receipt and existing invoice checks
remain separate outstanding items. Do not repeat the passed terminal reprint.


### R06 safe retry selected — 2026-10-09

Next distinct manual subcase: retry the existing cancelled £0.01 payment on
native draft 261-3-000012 in Revolut Acceptance — 2026-10-07. Read-only preflight
confirms source operation #61 cancelled/provider cancelled, retry_safe true,
no terminal blocking key and no other operation holding a terminal key.
Baseline remains 65 payment operations / 148 dispatch claims / 15 refunds.
Operator should use Retry once on that same cancelled payment, approve £0.01
GBP without tip, and observe automatic checkout. Stop if the old cancelled
line cannot be located or the screen is pending/uncertain. This case tests safe
retry after cancellation; it does not repeat ordinary cancellation or sale
coverage. Result pending. One successful retry would raise cumulative captured
spend from £0.15 to £0.16 of the £0.25 budget; it is not yet counted as spent.


### R06 cancelled-payment retry result — 2026-10-09

Operator screenshot shows Payment Successful and receipt 261-3-000012 for
£0.01, one £0.01 Revolut tender and the matching new payment reference.
Read-only SQL verifies new operation #66 explicitly links previous_operation_id
#61; #61 remains cancelled/provider cancelled. New #66 is verified/captured,
requested/captured 1 minor unit, zero tip, on the same native order now Paid
with total/paid £0.01 and linked £0.01 tender done. Exactly one successful
create_order and one successful create_intent claim exist for #66. Ledger delta
from preflight is +1 payment operation and +2 dispatch claims; refunds remain
15 (current totals 66 / 150 / 15).

Safe retry linkage, successful capture and native settlement subcase PASS.
Operator explicitly confirms the receipt appeared automatically, without
Validate or Force done: automatic checkout after safe retry PASS. No repeat charge
is needed. Wider R06 decline/failure/race coverage stays open. Cumulative
captured test spend is now £0.16 of £0.25; remaining charge budget £0.09.


### R19 cart edit after terminal dispatch — 2026-10-09

Operator screenshot for order 1015 shows the basket accessible but the attempted
cart change blocked by “Revolut cart frozen: Recover or reconcile the original
payment before changing this cart.” Visible quantity remains 1 and total £0.01.
Read-only SQL confirms native draft 261-3-000015 with quantity 1, unit price and
subtotal £0.01, matching operation #67 requested amount 1 minor unit. Cart-edit
UI guard and unchanged saved cart subcase PASS; wider stale-cart/restricted
manager approval coverage remains open.

By the subsequent read-only check, #67 is cancelled/provider cancelled,
retry_safe true, with no terminal blocking key or captured amount recorded.
Its history retains one successful create_order, one successful create_intent
and one cancel_intent claim with unresolved outcome; final operation evidence
is cancelled despite that historical claim outcome. Backend cancellation and
lock release confirmed; operator subsequently explicitly confirms physical
terminal back to idle. Cart-protection subcase complete.
No additional payment operation beyond #67 was observed. Preserve the unpaid
draft and do not repeat the test. Charge budget remains £0.09 (captured £0.16).


### Next independent check — R17 POS keyboard recovery controls

Read-only status check after R19 cleanup still finds FULL, PRODUCT, TIP, MIXED
and DISCOUNT refunds pending/processing. No new provider action was requested.
Use the existing cancelled order 1015 to check POS keyboard focus on recovery
controls and keyboard navigation back to the basket. Earlier manager-backend
keyboard/Check status evidence does not cover these POS controls. Do not
activate Retry, remove the payment line, or start another charge. Result pending.


### R17 POS keyboard focus visibility — FAIL, 2026-10-09

During the keyboard recovery-controls check on the existing cancelled order
1015, the operator reports that the focus indicator is unclear for payment
method controls and Retry: they cannot tell whether those controls are selected.
Record keyboard focus visibility FAIL for these POS controls. Earlier PASS for
manager-backend keyboard focus/Check status remains separate and does not cover
the register screen.

The report does not establish that controls are unreachable by keyboard or
that keyboard activation fails. Back-arrow keyboard activation was not confirmed.
Do not activate uncertainly focused payment methods or Retry merely to determine
focus, since those controls can initiate payment. No new payment or retry was
requested for this check. Defer diagnosis/fix and preserve the cancelled order.
Retest after a relevant fix should demonstrate obvious focus on each payment
method and Retry, distinct from selection/hover, with Tab and Shift+Tab, then
verify navigation. No new financial attempt is required to assess focus.


### R24 pending-order closure rejection selected — 2026-10-09

Read-only preflight confirms config #3 session #10 remains opened with five
pending/unresolved refund records. Installed native closing-control handler
rejects draft orders before entering closing_control; native rejection would
therefore demonstrate protection of this campaign session, not isolate the
addon's refund-specific guard. Ask operator to attempt normal closure through
the existing configuration banner and capture rejection; do not delete drafts,
force close, enter balancing corrections or confirm any override. If a cash
count/final confirmation appears instead, stop there. Actual reconciled closure
and reopen remain deferred until reconciliation. Result pending.


### R24 closing summary observed; closure guard not exercised — 2026-10-09

Configuration close-session banner reopened the POS. Register menu then opened
the Closing Register dialog. Screenshot shows 16 orders / £0.21, expected Cash
£0.05, Revolut £0.16, cash count £0.00 with difference −£0.05, and card count
£0.16 with zero difference. These are displayed summary values, not completed
cash reconciliation; the cash discrepancy reflects the currently entered zero
count and is not proof of a loss. Card summary agrees with recorded cumulative
captured campaign spend £0.16.

Operator stopped at the instructed cash-count/final-confirmation boundary.
No final Close Register action or closure rejection is observed. Merely opening
this dialog neither passes nor fails the pending-refund/session-close guard.
R24 remains PARTIAL / NOT EXERCISED for actual rejection and reconciled closure.
Instruction: Discard the dialog, leave counts unchanged and session open;
do not finalize closure or invent cash adjustments. All five pending refund
attempts and saved drafts must remain preserved. No additional backend check
was performed after this screenshot.


### R18 current-session Daily Sale PDF totals — PASS, 2026-10-09

Operator screenshot shows the downloaded Sales Details.pdf open as a readable
one-page Daily Sales Report X for Revolut Acceptance — 2026-10-07/00006.
Payments: Revolut £0.16, Cash £0.05, total £0.21. Session Control shows £0.21
and 16 transactions, matching the previously observed closing summary. Sales
show £0.19 test products plus £0.02 Tips, total £0.21; discount summary shows
one discount totalling £0.01. Taxes displayed £0.00. Report export/opening and
current-session displayed payment-total agreement subcase PASS.

Evidence is the operator's PDF-viewer screenshot ending 53604b29, not an
agent-inspected PDF file or a physical print. This does not complete R18's
per-transaction/refund/capacity/accounting reconciliation, verify pending refunds
as paid, or resolve the separate native return subtotal and receipt issues.
Actual session closure remains deferred; Discard the closing dialog if still
open. No new transaction was requested. Remaining charge budget £0.09.


### R07 browser-offline approval recovery selected — 2026-10-09

Distinct remaining live subcase: after the terminal displays a new £0.01
request, put only the POS browser tab offline with DevTools Network, approve
£0.01 without tip on the still-connected terminal, observe the POS before
reconnecting, then restore No throttling and recover the existing attempt.
Earlier late-success evidence covers approval after local timeout, not this
explicit browser network interruption. Do not classify this broad interruption
as proof of R22's precise verified-to-native-save boundary; that requires its
separate controlled automated evidence.

Read-only preflight: zero terminal blocking keys; 67 operations (max 67),
153 dispatch claims, 15 refunds. Existing drafts/refunds remain preserved.
Expected: no premature Paid receipt while disconnected; on reconnection the
same attempt settles once, automatically or via available read-only Check status.
Never Retry, Resume, Force done, replace tender or pay again for an uncertain
approved attempt. Stop and capture any failure. Successful charge would raise
spend from £0.16 to £0.17, leaving £0.08; not yet counted as captured. Result pending.


### R07 browser-offline recovery result — 2026-10-09

First operator screenshot shows DevTools Network set to Offline, a communication
interrupted/payment unresolved dialog, Check status available, remaining £0.01
and Validate disabled. Operator asked whether to pay; guidance permitted one
£0.01/no-tip approval only if the terminal still held the original request.
Next screenshot shows Payment Successful and native receipt 261-3-000016 for
£0.01, matching Revolut tender/reference.

Read-only SQL confirms only new operation #68 since preflight, no predecessor,
verified/captured 1 minor unit with zero tip, matching native Paid order and
£0.01 done payment. Exactly one successful create_order and one successful
create_intent claim; totals 68 operations / 155 dispatch claims / 15 refunds,
versus preflight 67 / 153 / 15. Native settlement and single recorded financial
attempt PASS. Cumulative captured spend £0.17; remaining budget £0.08.

Operator explicitly confirms payment was approved while the browser remained
Offline, then connectivity was restored and Check status was clicked; Odoo
then automatically opened the receipt. Browser-offline approval followed by
read-only status recovery and automatic native checkout subcase PASS. Recovery
was user-triggered through Check status, not spontaneous on reconnect. Evidence
combines operator sequence confirmation, offline/final screenshots and the
single-attempt backend check. No post-approval offline screenshot was supplied.
This does not prove R22's exact verified-to-native-save boundary. No repeat
payment is needed.


### R15 completed external-refund persistence — 2026-10-09

Operator supplied the requested post-refresh/refund-link screenshots for
historical sale 000014. Refund form remains Completed / Native return completed,
with the same Odoo Return link and no Complete native work button. Linked return
remains Paid, quantity −1, total/paid −£0.01. Native reconciliation manager/time
remain Administrator / October 9 13:37 local. UI persistence and completed-action
visibility subcase PASS based on this response to the prescribed refresh test.

No new validation or refund was requested. This is UI evidence; no fresh backend
ledger count was taken for this check. It does not prove stale-tab/concurrent
completion idempotency, incompatible association rejection or other R15 cases.
The positive £0.01 line tax-exclusive/inclusive subtotals remain visible and
continue as the already recorded line-total consistency FAIL, not a new issue.
Native receipt remains blocked by the separate Paid Orders loading failure.


### Next coverage selection — 2026-10-09

Read-only setup check finds all three POS configurations have restaurant mode
false. Native pos_restaurant is installed; no pos_revolut_restaurant module row
was returned. R04 is not ready in the current registers; no configuration or
module changes were made. Do not repeat retail scenarios as restaurant evidence.

Next zero-charge R15 subcase: open incomplete external refund for original
000018, choose Associate an existing native return, and search the Existing
native return picker for the completed return belonging to original 000014.
Expected wrong-original return excluded by the picker domain. Cancel the wizard
without Review native work, creating an order, or altering correction draft #13.
This tests UI selection scope only, not server rejection of forged associations.
Result pending.


### R15 existing-return picker / R17 layout — 2026-10-09

Operator opened external refund for original sale 000018, selected Associate
an existing native return, and reports being unable to find 000014 REFUND.
Screenshots show severe horizontal overflow/clipped instructions and labels,
a large blank region, and the Association Lines label wrapping vertically
character by character. Existing native return dropdown offers Create….

Record R17 association-wizard layout/readability FAIL and existing-return
picker creation-affordance UX FAIL: this association path should clearly select
an existing compatible return, without inviting creation of a new generic order.
The screenshot proves the Create option is exposed, not that creating an order
would succeed or bypass backend validation. No creation or association was
requested. Instruct Cancel; preserve original 000018's existing correction draft.

Wrong-sale return 000014 not appearing is consistent with the intended domain,
but there is no demonstrated completed search or compatible positive-control
selection, and the field is impaired by the layout. Keep wrong-original picker
filtering PARTIAL/INCONCLUSIVE rather than claiming server rejection or a full
R15 pass. Defer investigation/fixes under ticket 12; do not use Create or Review
native work to work around the picker. Evidence: operator screenshots ending
7130990f, 307ae122 and 8fa8bcfe in this chat. No backend mutation/check performed
for this observation; no additional financial attempt requested.


### Resume on PR #72 / .18.10 — 2026-10-09

Owner reports a newer deployment and requests continuation from main, with
historical failures revisited later. Fast-forwarded the handoff branch to
main merge 93b06c2, preserving uncommitted acceptance evidence. Read-only staging
check confirms release d232c57b797b898aef57d5139290f11699d4678c,
installed version 19.0.1.18.10 and active Odoo service. This is a version/path
check, not a repeated full deployed-source comparison. PR #72 includes the
mocked remediation recorded in ticket-12-mocked-remediation.md; those automated
results do not automatically pass historical live failures. That report also
explains native positive refund-line subtotal magnitudes; the historical
screenshot alone does not establish an accounting defect.

Resume with newly available R03 two-card allocation using Choose amount,
previously blocked by automatic full-balance dispatch. One new £0.02 sale,
allocated £0.01 then £0.01 to Revolut, no tips. Confirm terminal idle before
Send, first successful payment leaves £0.01 unpaid, second completes the same
order automatically with two distinct references. Stop on any uncertainty;
never repeat an approved payment. Result pending. Prior association-picker
layout/Create findings remain historical, deferred for a later retest.

Read-only preflight: 68 operations (max 68), 155 dispatch claims, zero terminal
owners; acceptance session 10 remains opened. Verified captured amount totals
17 minor units, including the existing tip scenarios. Campaign budget remains
£0.17 captured / £0.08 available before this test; successful two-card test
would leave £0.06. Refund 10 remains outstanding with correction draft 13;
refund 11 remains native_completed with return 53. No provider calls or
financial mutations were made during this preflight.


### R03 two-card split PASS; R17 Enter-key issue — .18.10, 2026-10-09

Operator confirms the split worked using Send. Screenshot d1cb2f0d shows the
first £0.01 Revolut payment successful, £0.01 remaining on the £0.02 order and
Validate disabled. Screenshot e5c300d9 shows receipt 261-3-000017 for two units,
£0.02 total and two £0.01 Revolut tenders. This supports the two-card allocation
and partial-payment behavior. Automatic checkout is reported through the
operator's confirmation of the prescribed flow, not independently timed.

Read-only backend check confirms native order 56 Paid, total/paid £0.02;
payments 74/75 both done at £0.01. Operations 69/70 are each verified/captured
one minor unit, zero tips, distinct provider payment references and no retry
predecessor. Each has exactly one successful create_order/create_intent pair.
Ledger changed from 68 operations / 155 dispatch claims to 70 / 159, with zero
terminal owners. No extra recorded provider attempt from the reported Enter
interaction. Captured campaign spend is now £0.19, leaving £0.06. The receipt
screenshot visibly shows only one provider reference; both references are
confirmed distinct in the backend, but full multi-reference receipt coverage
is not established by this screenshot.

Separate keyboard UX FAIL / R17: after Choose amount and entering £0.01,
pressing Enter produces Revolut allocation: “There is already an electronic
payment in progress.” Clicking Send works. Screenshot e26d7996 is on a new
cart 1018 (not the completed 1017), showing £0.01 due and an unsent £0.00
payment line behind the dialog. Record that visible amount discrepancy without
assuming the operator entered zero or proving Enter reset it. No saved native
261-3-000018 was returned by the read-only query. Focus/event routing is not
verified; reactivation of Choose amount is a hypothesis, not an established
root cause. Preserve the completed split, dismiss the dialog and do not pay
again merely to reproduce it. Investigation/fix deferred under ticket 12.


### Next R03/R16 subcase — two-card receipt persistence, .18.10

Use completed sale 261-3-000017 (order 56, operations 69/70); no new financial
attempt. Refresh acceptance POS, open Orders / Paid and locate exact ticket,
then reopen its receipt. Verify £0.02 total and two separate £0.01 Revolut
payments survive reload. Inspect the full receipt for provider references,
including below the visible fold. Screenshot the result. If Paid Orders
loading fails, stop and record the error without recreating the sale or
clearing storage. This adds multi-card persistence/reference coverage; prior
single-card/Cash-card passes are not being repeated. No printing, invoice,
refund, payment or edit action is requested. Result pending; budget £0.06.


### R03/R16 reopened two-card receipt — .18.10, 2026-10-09

Operator supplied screenshot 48fc4a92 in response to the refresh/reopen test.
Paid Orders is populated and print preview displays ticket 261-3-000017:
two product units, total £0.02, two Revolut tenders of £0.01. Reopened two-card
receipt/tender persistence subcase PASS on this evidence. This demonstrates
Paid Orders loading for this register/test; it does not establish every
historical Paid Orders failure is fixed. Refresh is supported by the response
to the requested sequence, not independently instrumented.

The complete one-page browser print preview shows one Revolut payment reference,
wrapped across two lines without visible clipping. Current split receipt
reference wrapping subcase PASS in this preview; no saved PDF or physical
print is established (Save as PDF dialog remains open). Only one provider
reference is printed despite the two distinct verified references confirmed
for operations 69/70: record multi-card receipt reference completeness FAIL,
with investigation/fix deferred under ticket 12. Both payment amounts remain
correct; this is not evidence of a missing financial payment. No new payment,
refund, invoice or backend mutation requested; budget unchanged at £0.06.


### Owner acceptance and next multi-card refund-source check — .18.10

Owner explicitly accepts printing a single payment reference on the Odoo
receipt. Reclassify the previously recorded multi-card receipt completeness
FAIL as ACCEPTED for this release, not a fix/retest requirement. The observed
single reference and backend retention of both distinct references remain
accurate; no claim is made about which component owns all receipt rendering.

Next zero-charge R10 subcase uses sale 261-3-000017: select both product units
for return (total −£0.02), open Payment / Revolut to view the allocation dialog.
Expect two original sources (operations 69/70), each £0.01 remaining; select
each in turn and inspect £0.01 base / £0.00 tip, with base excluding tips.
Capture the dialog and Cancel without Confirm refund allocation. This tests
multi-source discovery/selection only, not dispatch, provider completion or
server cap enforcement. Stop on any unexpected error. Preserve the draft for
later continuation; budget remains £0.06. Result pending.


### R10 multi-card source discovery observed — .18.10

Screenshot d8713fcd shows return cart 1019, total −£0.02, and allocation
sources 70/69 with separate original/payment references and £0.01 remaining
each. Both radio buttons are unselected and Refund amount is blank. Source
discovery/listing subcase PASS; selection defaults and allowance hints remain
pending. Do not infer those from an unselected screenshot. Current template
shows component/tip fields conditionally on the selected source's terminal-tip
evidence, so a separate tip field need not appear before selection. Continue
by selecting each source, checking the suggested £0.01 and base allowance,
then Cancel without confirming any refund. No dispatch or finality claimed.


### R10 accidental confirmation of source 70 — .18.10, 2026-10-09

Operator reports accidentally confirming with only source 70 selected.
Screenshot 19b95441 shows cart 1019, total −£0.02, one −£0.01 Revolut line,
Refund pending / Check status and an error: “Reconcile the unresolved Revolut
payment before adding another tender.” The exact action producing this second
error is not established. This is no longer a selection-only test; do not
repeat the submission or assume the dialog reversed the submitted refund.

Read-only SQL confirms exactly one refund for sources 69/70: refund 19 against
source 70, one minor unit base, zero tip, pending/provider processing, provider
reference present, dispatched 2026-10-09 13:40:09 UTC, no verified_at. Source 69
has no refund record. Native return 57 / 261-3-000019 remains draft at −£0.02,
with payment 76 at −£0.01 / waiting. Its stored amount_paid is −£0.01 but this
is not evidence of refund finality. UI Remaining −£0.02 includes the unsettled
refund; it must not be treated as an instruction to issue another £0.02.

Totals now 16 refunds (max 19), 70 payment operations / 159 payment dispatch
claims, zero terminal owners. Those dispatch-claim totals concern payments,
not proof of refund HTTP call counts. No agent provider call or mutation.
Guidance: dismiss the error, use existing Check status once, preserve pending
line/draft and stop if still pending; no new tender, Force done or resubmission.
Source-specific £0.01 submission observed, provider completion/native checkout
remain pending. Selection-default screenshot and source-69 selection are still
unverified. Original gross charge budget remains £0.19 spent / £0.06 available;
refunds do not replenish it.


### R10 source-70 status observation after Check status — .18.10

Operator response screenshot 89f974cf shows return 1019 with source 70's
−£0.01 line now Refund in process, the existing original/refund references,
return total/Remaining −£0.02 and disabled Validate. This confirms the UI
processing state after the requested status check, not provider completion or
native settlement. No fresh backend count was taken for this screenshot, so
no additional HTTP/idempotency assertion is made. Preserve the draft and line;
do not Force done or submit another allocation while this remains unresolved.
Further selection/default coverage for source 69 remains deferred. Budget
unchanged at £0.06; no additional financial action requested.


### R18 captured-payment/native-tender reconciliation — 2026-10-09

Read-only database reconciliation of acceptance session 10, performed while
source-70 refund remains pending. All 16 verified payment operations link to
16 distinct native payment records and 16 distinct non-null provider payment
references. Every linked native tender is done, its amount equals the captured
gross amount, and its order is Paid. Totals: £0.17 base + £0.02 tips = £0.19
gross Revolut; native completed-order Revolut tenders also total £0.19.
Cash tenders total £0.05. All 18 completed orders have amount_total = amount_paid
= sum of native tenders, for an aggregate £0.24. No mismatch or duplicate
payment reference/tender link in this checked set. Captured-payment/native-
tender reconciliation subcase PASS. The earlier £0.21 X report predates the
£0.01 offline sale and £0.02 split sale; their addition explains the £0.03
increase, without changing that earlier report's historical result.

Six campaign refunds (12/13/16/17/18/19) remain pending/provider processing,
£0.06 total (£0.05 base + £0.01 tip); none verified complete. Their per-source
active sums do not exceed captured amounts: source 55 £0.01, 58 £0.02,
63 £0.01, 64 £0.01, 70 £0.01. Failed historical attempts 14/15 remain excluded
from active reservations. The £0.13 arithmetic balance after active reservations
is not an operator-approved retained balance or proof of all refund eligibility.
This snapshot does not prove server race/cap enforcement, provider/bank
settlement, every draft/stock/accounting effect, or full R18 completion. No
provider calls or database mutations; no user charge/refund needed. Budget
remains £0.06; return 1019 stays open.


### Next .18.10 retest — terminal cancellation display recovery

After new split/source/reconciliation coverage, revisit the PR #72 cancellation
recovery fix with one unpaid £0.01 sale in the acceptance register. Preserve
return 1019 and all pending refunds. Start Revolut normally, do not present a
card, cancel the displayed request on the physical terminal, and observe Odoo
for up to 60 seconds without refresh or Check status. Expected final cancelled
UI, no paid receipt, and physical terminal back to idle. Capture the final
screen or the stuck screen at 60 seconds. Do not Retry/Force done or pay.
This is single-browser cancellation-display coverage, not the exact historical
two-browser timing or a controlled stale-sync race. Result pending; no capture
intended, remaining budget £0.06. Read-only preflight: 70 operations, max 70,
159 payment dispatch claims, 16 refund records, zero terminal owners.


### .18.10 cancellation retest — final state observed

Screenshot 6845d2ac shows cart 1020 Payment cancelled, cancellation dialog,
Retry available, £0.01 remaining and disabled Validate. Read-only backend
confirms operation 71 cancelled/provider cancelled, retry_safe true, no
captured amount and no terminal blocking key; native order 58 / 261-3-000020
is draft at £0.01. Exactly one successful create_order/create_intent pair.
Totals 71 operations / 161 payment dispatch claims, zero terminal owners.
Final cancellation display and backend non-capture subcase PASS. Explicit
operator confirmation of no refresh/Check status and physical terminal idle
is still requested before marking automatic-display sequence PASS; screenshot
alone does not establish those facts. No Retry needed. This single-browser
result does not prove the historical two-browser race or every stale-sync path.
Budget remains £0.06; preserve pending refunds and the cancelled order.


### .18.10 automatic cancellation display confirmed — 2026-10-09

Operator explicitly confirms no refresh or other click: the only action was
cancelling on the physical terminal. Combined with screenshot 6845d2ac and
operation 71's cancelled/non-captured backend state, automatic cancellation-
display recovery subcase PASS on .18.10. No Retry or paid order was created.
Physical idle-screen confirmation was not separately supplied; backend lock
release is verified. Historical two-browser timing remains a separate scope.
Budget unchanged at £0.06.


### Next .18.10 test — reload existing partial multi-card refund

Owner clarified “next test”, not a switch of tickets. Remain on ticket 12;
no ticket state/branch move. Use return 1019 / 261-3-000019, refund 19 against
source 70. Refresh the POS, reopen that same return and verify total −£0.02,
one Revolut line −£0.01 and the same refund/source reference. Observe automatic
recovery; if Check status is offered, use it once and distinguish user-triggered
from automatic recovery. Capture the resulting screen and report whether Check
status was needed. Pending/processing is acceptable continuity, not financial
completion. Stop on missing/changed evidence or errors; no new tender, Retry,
Force done, replacement return or repeat refund. Pending-refund reload on the
new release and this partial multi-card draft is the scope. Result pending.


### .18.10 pending-refund reload screenshot — 2026-10-09

Operator response screenshot 12112e36 retains return 1019, total −£0.02,
one −£0.01 Revolut line, source 70 and the same original/refund references
as screenshot 89f974cf. Status is Refund in process; Validate remains disabled.
UI identity/amount continuity observed in response to the reload test. Operator
has not yet specified whether recovery was automatic or Check status was used;
that distinction remains open, so automatic recovery is not marked PASS.
No fresh backend count or provider check performed for this observation.
Financial completion remains pending; no repeat refund requested.


### Clarification: source-70 recovery was Check status only

Operator clarifies: “all i did was click check status.” Classify screenshot
12112e36 as user-triggered status recovery/identity continuity, not evidence
of browser reload or automatic restoration. Source-70 Check status UI recovery
subcase PASS; .18.10 reload behavior remains unverified. Next step is an actual
browser refresh with return 1019 selected, then observe before any Check status
click; do not repeat a refund. This clarification supersedes any inference of
reload from the preceding screenshot response.


### .18.10 refund reload persistence observed — 2026-10-09

Following the explicit F5/reopen instruction, operator supplied screenshot
9bc93861 before further Check status: return 1019, total −£0.02, same −£0.01
line and source-70 original/refund references survive. Status is “Waiting limit
expired — refund unresolved”; Check status is available and Validate disabled.
Saved-draft identity/amount persistence and actionable unresolved recovery UI
subcase PASS on this supplied sequence. This is not automatic financial
resolution, refund failure, or proof of new provider observation. Prior Check
status recovery to Refund in process was already observed; do not repeat it
solely for coverage. No fresh backend/dispatch check for this screenshot.
Keep the pending return intact and move to independent coverage. R11 broader
missing-draft, API and concurrency cases remain outside this result.


### Next .18.10 manager-worklist return-link retest

Open Point of Sale backend / Revolut Refunds while keeping POS return 1019
intact. Inspect refund 19, £0.01 against original sale 261-3-000017 / source 70.
Expected Odoo Return is populated and clickable, Native completion reads
Return awaiting refund confirmation while unverified. Follow the link and
verify the same saved return 261-3-000019, New/draft, total −£0.02, product
quantity −2 and one −£0.01 Revolut tender. Capture refund form and linked
return; do not validate, pay, invoice or issue another refund. This exercises
the .18.10 display-only UUID-based return recovery/clearer completion label,
not settlement or provider finality. Stop on unexpected status/error and report
it. Result pending; zero-cost read-only operator navigation.


### .18.10 pending-refund manager link — navigation PASS, label unclear

Screenshots e8e5f4a1/523778f6 show refund 19 Pending, Native completion
“Return awaiting refund confirmation”, and clickable Odoo Return labelled “/”.
Following it opens New return quantity −2, total −£0.02, stored paid −£0.01,
with original-sale smart link to 000017. Read-only SQL confirms linked order
57 has name '/', pos_reference 261-3-000019, draft state, and UUID matching
refund 19's order_uuid. Payment 76 remains −£0.01 / waiting. Therefore the
correct saved return is resolved and opened: display-link navigation and
completion-label subcases PASS. The '/' is the stored draft name, not proof
of a broken URL/path or missing return. Previous instruction to expect 000019
as the visible order title was too specific: that is its POS reference.

Record a usability follow-up: show an identifiable draft reference (for example
261-3-000019) rather than '/' in the refund worklist link. No relabelling or
code fix performed. Native total-paid field records the pending tender and
must not be read as verified refund completion. Payments tab was not supplied,
but the existing single waiting tender is independently verified in SQL.
Positive line subtotal magnitudes are the previously documented native refund
representation, not a newly established accounting defect. No validation,
payment, invoice or provider call; preserve draft 57 and pending refund 19.


### Next .18.10 historical native return receipt retest

Read-only preflight confirms native return 53, name Davai GBP Terminal Test -
000014 REFUND, POS ticket 260-2-000004, remains Paid at −£0.01 in open session
9 / register 2 Davai GBP Terminal Test. Use that register's existing session
in a separate tab, leaving acceptance pending drafts intact. Orders / Paid,
locate the return by name/reference, Print Receipt and inspect negative total,
quantity and tender in preview. Capture and Cancel print dialog. No Refund,
Payment, Invoice or new session requested. Stop if the earlier Paid Orders
error recurs. This retests previously blocked historical completed-return
receipt access and output, not a new financial return. Result pending.


### Historical Paid Orders error recurs during .18.10 retest

Operator screenshots 01fc013b/d324c5fc reproduce the previous result when
following the historical return-receipt test in Davai GBP Terminal Test:
Paid selected, pager 1–19 / 19, empty list, and Invalid Operation: “The return
exceeds the original quantity or remaining monetary entitlement.” Dismissing
the dialog leaves No orders found. Paid Orders loading retest FAIL;
historical return 53 receipt inspection remains BLOCKED. Record recurrence
under the currently deployed .18.10 campaign; exact browser asset build and
root cause were not independently checked in this observation. Successful
Paid Orders loading in acceptance register 3 does not resolve register 2's
failure. Do not infer deletion or an invalid actual return from this message.

The immediately preceding read-only preflight confirmed return 53 Paid at
−£0.01 in open session 9. No mutation, provider request or post-error database
check performed by the agent. Defer investigation/fixes per the working
agreement; stop this test, preserve existing orders/session/storage and
return to the acceptance tab. No replacement return, financial action or
clearing browser storage requested. Budget unchanged at £0.06.


### Next .18.10 base/tip allowance-hint retest

Read-only fixture check confirms acceptance sale 261-3-000005 / native order
36 / source 57 remains Paid £0.02: one £0.01 test product and one £0.01 Tips
line, verified base/tip 1/1 minor units, no refund records against source 57.
Use this existing sale, select return quantity 1 for both product and Tips
lines, open the −£0.02 return's Revolut allocation dialog. Expected source 57,
base refund/default and base-excluding-tips allowance £0.01, terminal tip
refund/default and tip allowance £0.01. Capture without Confirm refund
allocation, then Cancel. Explicit stop before confirmation; no provider refund
requested. This directly checks the requested separated base hint on a tipped
fixture and revised tip wording. If another source/total/error appears, stop.
Preserve the unsubmitted draft; result pending and charge budget stays £0.06.


### .18.10 base/tip allowance hints PASS — 2026-10-09

Screenshot 1bf827f1 shows unconfirmed return 1021 at −£0.02 with source 57
selected and £0.02 source remaining. Base refund amount defaults to £0.01;
“Base refund allowance excluding tips, after other allocations” is £0.01.
Terminal tip refund amount defaults to £0.01 and its separately labelled
allowance is £0.01. Requested base-excluding-tips hint, separate tip wording,
and component defaults PASS for this tipped fixture. Screenshot shows the
allocation popup before confirmation; instruct Cancel. No refund dispatch or
completion claimed, no fresh backend check. Preserve the unsubmitted draft;
charge budget remains £0.06. This does not establish all multi-source/reserved
allowance arithmetic or server cap enforcement.


### Next .18.10 return-quantity editor retest

Use existing external refund 10 for original Davai GBP Terminal Test - 000018.
Open Complete native work and choose Select returned products. Inspect revised
columns Product / Return now / Purchased / Already returned. Enter 1 in Return
now for the test product and move focus away; expect entered 1 remains visible,
Purchased 2 and Already returned 0 remain unchanged/read-only. Screenshot then
Cancel; do not Review native work. The quantity is a wizard-only inspection,
not authorization to record actual goods returned: prior no-products-returned
disposition and correction draft 13 remain preserved. If incompatible values
or errors appear, stop. This retests the reported quantity-entry discoverability
on .18.10, not association layout, stock effects or native completion.
Result pending; no financial action or charge requested.


### .18.10 return-quantity editor retest PASS — 2026-10-09

Screenshot 09d609d3 shows external refund 10 / original 000018 in Select
returned products: Return now contains 1.00, Purchased remains 2.00 and
Already returned remains 0.00. The new guidance identifies the editable
positive return quantity and read-only reference quantities. Entry/display
subcase PASS in response to the prescribed input/blur test. The Already
returned column heading is shortened on this viewport, but its full meaning
is provided by the visible guidance. This does not prove all keyboard paths,
read-only enforcement or the separate existing-return association layout.
Instruct Cancel without Review native work; no actual goods disposition,
return creation, correction posting or financial outcome is claimed. Preserve
existing correction draft 13; no fresh backend check needed for this UI result.


### Next .18.10 revoked-register feedback retest

Read-only preflight confirms acceptance config 3 grants Administrator (2) and
test gary (7), 71 operations / 161 payment dispatch claims and zero terminal
owners. Use existing separate test-gary browser login (employee switching is
not sufficient). Administrator temporarily removes only test gary from config
3 Revolut backend users and saves. In the already-open test-gary acceptance
POS, start a fresh £0.01 order and select Revolut once. Expected actionable
register-access denial before native payment-save failure/provider dispatch;
terminal stays idle. Capture error, then immediately restore test gary to the
same grant list and save, retaining Administrator throughout. Do not pay/retry;
if the terminal unexpectedly receives a request, cancel on the terminal and
report it. Restore grants even on failure. Result pending; no grant mutation
performed by agent in preflight. Pending refunds and sessions remain intact.


### Owner-selected revoked-access retest resumed — 2026-10-09

Owner explicitly requests the implemented-but-unverified register-access
feedback retest. This is a targeted exception to the pause on routine repeats.
Fresh read-only preflight confirms config 3 grants Administrator (2) and test
gary (7), 71 operations / 161 payment dispatch claims and zero terminal owners.
Follow the previously described temporary test-gary revocation, one attempted
fresh £0.01 Revolut request in the existing separate backend login, screenshot,
then immediate grant restoration. No card presentation/payment. Preserve
Administrator and all pending drafts. Result pending; agent has not changed
grants. Compare ledger after result to confirm no new financial attempt.


### .18.10 revoked-register feedback retest PASS — 2026-10-09

Screenshot ebe5987b shows the acceptance configuration with only Administrator
granted during the test and cashier dialog “Revolut register access required”.
The message explains backend-user access, administrator grant review, preserved
existing payments/refunds and status recovery after restoration. The line also
shows “Register access required — contact an administrator”; order remains
unpaid with Validate disabled. Intended denial feedback subcase PASS, replacing
the earlier generic native pos.payment access error for this tested path.

Operator explicitly confirms test gary was regranted access. Read-only postcheck
confirms config 3 again grants Administrator (2) and test gary (7). Ledger stays
71 operations (max 71) / 161 payment dispatch claims, zero terminal owners,
identical to preflight: no new recorded financial attempt/dispatch. Restoration
of grants PASS. No Retry or post-restoration charge requested/needed for this
feedback test; no claim that a new post-restoration payment was exercised.
Budget remains £0.06. This closes the targeted implemented-but-unverified
feedback retest, not all negative-authority/concurrent revocation cases.

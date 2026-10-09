# 12 — Retest the complete integration before release and open-source publication

**Work branch:** `codex/12-live-terminal-release-evidence`

**State:** open

**Triage:** ready-for-human

**Updated:** 2026-10-09, after Cash smoke and the first R08 two-browser test; UI-failure investigation deferred by owner.

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
- Current .18.9 Cash smoke PASS; PRODUCT/TIP refresh continuity observed.
  First R08 busy rejection, backend serialization and cancellation checks PASS;
  A required refresh for its final cancellation display (FAIL below).
- Second R08 manual near-simultaneous run: A clicked slightly first, B rejected;
  backend verifies only A created an attempt and it is cancelled. Both orders
  remain draft. Operator confirms two B Check status clicks, A cancellation
  displayed without refresh, and terminal idle: this subcase PASS. Access
  revocation now exercised with zero new dispatch, but native payment-access
  error masks intended grant feedback (see below); precise synchronized
  concurrency remains untested manually. The earlier UI FAIL is
  still open/deferred. Existing refunds remain pending; finalize only when verified.
- New .18.9 test-cashier £0.01 no-tip sale after regrant: verified/captured,
  native Paid, one successful order/intent pair while three refunds remain
  pending. Restored payment access and pending-refund/new-sale coexistence PASS.
  Operator confirms automatic checkout, terminal £0.01 GBP/approval and
  post-refresh receipt: R02 current retail flow PASS. Exact receipt delay
  remains unmeasured; printed-reference clipping stays open under R16.
- Current .18.9 R03 split: intermediate unpaid screenshot captured; backend
  verifies £0.02 Paid with Cash £0.01 / Revolut captured £0.01, zero tip, one
  order/intent pair. Operator confirms terminal idle before card request,
  terminal £0.01 GBP, automatic checkout and post-refresh receipt: Cash/card
  split subcase PASS. Separate two-card UI blocker remains open. Preserve this two-unit sale as MIXED for later R10 refund.
- R19 line-discount subcase PASS: cashier two-unit line at £0.01
  less 50%, captured/native Paid £0.01, zero tip, one order/intent pair.
  Operator confirms terminal £0.01/approval and automatic checkout; preserve
  DISCOUNT for R21. Other R19 requirements remain open.
- Approved gross card-charge cap **£0.25**, recorded spend **£0.13**, remaining
  **£0.12**; tips count and refunds do not replenish it.
- Open acceptance issues include clipped printed references, a supported first
  allocation entry path for the fresh two-card test, negative permission
  feedback, final refund/native reconciliation, and unexecuted checklist rows.

## Recorded manual failure — investigation deferred

**R08 / .18.9 / 2026-10-09: automatic cancellation-display recovery FAIL.**
In browser A (Administrator), the payment screen remained on Request sent even
though the backend payment was cancelled. The operator reported no Check status
available at that recovery point and had to refresh A to display Payment
cancelled. Browser B used the previously authorized test cashier. Both final
screens show cancellation and disabled Validate. At 10:34 UTC, backend records
still showed both attempts cancelled/retry-safe, terminal locks released and
native orders draft; refreshing added no operation or dispatch (counts remained
60 payment operations, 137 dispatch claims, 13 refunds).

Earlier A displayed a communication-interrupted warning; both cancellation
claims have unresolved response outcomes despite the final operation states
being cancelled. Their cause and relationship to the UI failure are unverified.
The owner explicitly chose to **defer investigation and continue manual tests**;
this is an open failure, not waived acceptance. Preserve the existing cancelled
orders and refund records. Details/screenshots are referenced in the
[handoff](../../testing/ticket-12-fresh-retest-2026-10-08.md) and
[R08 evidence](../../testing/ticket-12-final-release-checklist.md).

## Recorded permission-feedback failure

**R01/R08 / .18.9 / 2026-10-09: intended register-access denial feedback FAIL.**
With only Administrator granted, the test cashier's new payment line was
rejected for native pos.payment create access under Revolut cart needs
correction, rather than the expected request for a register grant. This
reproduces the earlier negative-permission message gap. No new payment or
dispatch was recorded. At **10:43:25 UTC**, SQL verifies the cashier grant was
restored alongside Administrator; counts/max IDs remain 61 operations, 140
dispatch claims, 13 refunds, zero nonfinal payment operations. Restoration and
no-dispatch subchecks PASS; precise guard ordering/cause and restored server
interaction remain unverified. Check status not starting a payment is expected;
Resume would be a separate explicit start, not an observation check. Do not
silently broaden native POS permissions to change this result.

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

PR #74 closed [ticket 34](../closed/34-provision-and-gate-odoo-pdf-generation.md) after native staging invoice PDF inspection and
repeat retrieval. Physical printing was explicitly skipped; historical and
closed-session checks in ticket 12 remain separate.

Remaining work is explicitly separated:

- Implemented in PR #73, awaiting targeted retest: historical register Paid
  Orders entitlement error (reproduced on current deployment, receipt blocked);
  Enter after Choose amount alert; POS payment/Retry focus visibility;
  existing-return association layout/Create affordance; '/' draft link label.
  Revoked-access feedback subsequently passed its owner-selected .18.10 live retest; grants restored and payment ledger unchanged.
- Awaiting external outcome: six existing processing refunds. Once final,
  complete/reconcile their SAME returns and check negative receipts, original
  capacity and totals. The second card source on return 1019 is not refunded.
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
- [34 — Native invoice PDF acceptance](../closed/34-provision-and-gate-odoo-pdf-generation.md): closed 2026-10-09; native PDF inspected and repeat downloads confirmed, with physical printing skipped by owner. Ticket 12's other historical/session/physical checks remain independent.
- Physical operator/terminal, supported controlled-failure methods and suitable
  Restaurant, rounding, permissions, historical document and external-refund fixtures.

Destructive/forged-request/race tests belong in disposable databases with mocked
Merchant HTTP. Preserve old registers and completed refunds; outstanding
historical native dispositions are identified in the handoff. Ticket 12 remains
open until mandatory financial, manual, document and publication gaps are resolved.

# Ticket 12 — Manual testing handoff

Updated **2026-10-09**, after the operator's successful concurrent tip-refund
submission. This is the current checkpoint for the campaign begun October 7.
Read this file first; use the [R01–R24 checklist](ticket-12-final-release-checklist.md)
for full subcase requirements. Resume unfinished subcases rather than restarting
the campaign. A successful subcase does not pass an entire checklist row.

## Resume here

1. Verify the current deployed version and read the status of the three existing
   refunds below. The last verified release is **19.0.1.18.9 / PR #70**. Start
   with read-only inspection; the agent has not submitted the live refunds.
2. With the operator, reload the existing product-only and tip-only returns,
   one at a time. Confirm the same amount and refund reference survive and
   compare backend refund counts/references before and after. Expected: no new
   refund dispatch, same original payment, processing state retained or an
   authoritative completed state recovered. This extends R11; it is not yet done
   for the newly submitted tip refund.
3. If a refund has completed, recover/check its existing status, validate that
   same return when eligible, then inspect the negative receipt, Orders entry
   and native amounts/links. Record provider completion separately from funds
   arriving in the cardholder's bank account. If still pending, leave it open
   and continue an independent case; do not wait days before continuing testing.
4. Next independent case: R01 Cash smoke on the current deployment, then the
   remaining R08 terminal-contention cases with a second browser. Reconfirm
   terminal readiness and the fixtures before starting. The live multi-card
   amount-entry blocker below must be solved before attempting that R03 subcase.

Give the operator **two or three steps per turn**, then inspect their result.
Update the relevant checklist row and this checkpoint after each test. Keep
observed UI, backend verification and untested expectations distinct.

## Active refunds — preserve these attempts

These aliases identify scenarios, not provider identifiers. Locate them in the
campaign register using original sale, amount, component and pending return;
retain exact IDs/references in restricted evidence, not this shared document.

| Alias | Original sale | Base / tip / total | Last observation | Next acceptance |
| --- | --- | --- | --- | --- |
| FULL | Late-success, no-tip £0.01 sale | £0.01 / £0.00 / £0.01 | Odoo and Revolut Processing; still pending at last backend check | R09 finality, native validation/receipt; finish R11 identity proof |
| PRODUCT | Latest automatically completed £0.02 tipped sale | £0.01 / £0.00 / £0.01 | Backend pending/processing | Same return reload, then finality/native settlement |
| TIP | Same original as PRODUCT | £0.00 / £0.01 / £0.01 | Latest operator screenshot and backend pending/processing, own provider reference | Same return reload, then finality/native settlement |

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
  allows retained charges. Recorded spend **£0.10**, remaining **£0.15**.
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
| R01 Cash | Initial £0.01 Cash receipt and Paid backend tender verified; operator said terminal idle. Later .18.6 £0.01 Cash receipt also observed | Current-release smoke and comprehensive zero-terminal-dispatch proof |
| R01 permissions | Ungranted test-user attempt rejected with pos.payment AccessError, not the expected register-grant message. Later explicit grant and successful cashier checkout | Repeat precise negative permission case with correct native permissions; do not mark the earlier error as the intended denial PASS |
| R02 retail | Granted-cashier £0.01 no-tip sale successful on .18.4; native Paid, matching tender/receipt and post-refresh persistence verified | Complete device amount/currency/timing record; broader row remains partial |
| R03 split | £0.02 sale paid £0.01 Cash + £0.01 Revolut; native tender shares and receipt verified | Intermediate unpaid screen, two-card UI path and mixed-tender refund |
| R05 tips | First £0.01 base + £0.01 tip sale needed Check status after warning. After .18.6, repeat £0.02 sale reached receipt entirely automatically; backend verified base/tip/gross and one successful order/intent dispatch pair | Final tip refund, remaining no-tip/report subcases |
| R06 cancel | After .18.5, Odoo Cancel stopped payment on both Odoo and terminal; terminal-origin cancellation then detected automatically | Backend/timing detail, controlled decline/failure/retry and capture/cancel race |
| R07 timeout | 60-second local wait expired while terminal remained active. Terminal cancellation plus Check status recovered Cancelled. Reload then cancellation also recovered | Remaining interruption boundaries and dispatch/identity proof |
| R07 late success | £0.01 payment after timeout recovered through Check status to receipt; Paid Orders and reopened receipt observed after requested reload | Complete backend dispatch/identity verification for the scenario |
| R09 full refund | FULL submitted; Odoo and Revolut Processing; Validate disabled | Verified completion and native settlement |
| R10/R05 partial + tip | PRODUCT submitted, then TIP accepted while PRODUCT pending after .18.9 fix; backend confirms two references, component sum and same original | Both completions, native settlement and remaining-capacity enforcement |
| R11 pending reload | FULL screenshot after guided reload retained same reference/amount/processing and disabled Validate | Explicit reload confirmation/backend single-dispatch proof; newly pending PRODUCT/TIP reload checks |
| R16 print | Split-sale and reopened late-sale native previews show correct totals/tenders | Long reference clipped with scrollbar; saved PDF, physical/historical/invoice and terminal printing unverified |

Full R04/R08/R12–R15/R17–R24 scenarios remain unexecuted in this campaign;
partial overlaps above do not waive their distinct requirements. Restaurant,
rounding, restricted-price and tracked-stock fixtures need explicit setup.
The [checklist](ticket-12-final-release-checklist.md) defines every remaining
subcase and final financial/document/publication gates.

## Known issues and behavior to retain

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
  Its real browser regression passed with PR #70; live dedicated verification
  on the combined release remains to be recorded.
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

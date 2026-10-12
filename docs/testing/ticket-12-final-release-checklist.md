# Ticket 12 — Final release and open-source checklist

Current status: **2026-10-12** agent audit and manual retests on **19.0.1.18.11**.
All five PR #73 usability retests passed; see the authoritative summary below. Parent: [ticket 12](../tickets/ready-for-human/12-live-terminal-release-evidence.md).
Read the [manual handoff](ticket-12-fresh-retest-2026-10-08.md) for active refunds,
remaining budget, completed subcases and the next test. This checklist is the
complete acceptance contract; [release provenance](ticket-12-release-evidence.md)
contains automated counts, candidate hashes and evidence history.

The October 7 fresh campaign superseded older campaigns. Resume from its current
checkpoint. A successful subcase does not pass its entire row; older passes do
not waive fresh checks. A01–A10 passed on the October 8 baseline. Later releases
have focused/artifact coverage; assess remaining combined coverage at final
freeze rather than claiming the full baseline suite ran on every later revision.

PR #73 implements the recorded usability fixes; targeted manual retests passed
on October 12. PR #74 closes the native invoice PDF gate. See the
handoff checkpoint before using older chronological entries as next steps.

## Current acceptance summary — October 12 owner handoff

This section is authoritative for the next session; the dated entries below
are evidence history and must not be read as a fresh queue of failures.

Ticket 47's automated implementation is closed on `19.0.1.18.12`; 648 tests
passed on installation and again after update. R19 remains pending reviewed
deployment, POS asset reload and **Check status → Resume** on original order
1022/tender 79, with the intended Price Control policy restored for manager
approval. Preserve Tips product 1, the original fixture and the current £0.03 live budget.
See the [verification and recovery handoff](ticket-47-unstarted-tender-recovery.md).
No staging deployment or new live financial operation was performed by ticket 47.
The owner explicitly holds the staging upgrade and dependent acceptance until
they give the go, with ticket 49 still in progress. Ticket 48 implementation
has also merged; its live wording acceptance remains pending.

### Finished checks

**Recorded pre-fix October 12 finding, after completed regressions:** order
1022's unstarted waiting tender cannot be removed after reload. Owner reports first red-X click
gave a communication-failure popup; subsequent clicks do nothing visibly even
after refresh. Local mocked lifecycle reproduction matches the stuck removal
and single interruption message. R19 exact manager approval is BLOCKED by this
recovery failure until the reviewed upgrade and original-tender recovery. Do
not repeat completed regressions or create replacement orders to work around
it. Details are in the restricted-pricing entry below.

| Check | Disposition |
| --- | --- |
| FULL return 1003 | PASS: automatic status recovery, native Paid/done, restored links, negative receipt and history reprint preview |
| PRODUCT return 1008 | PASS: native Paid/done, restored links and negative receipt |
| TIP return 1009 | PASS: native Paid/done, tip-only receipt; product + tip equals original capture |
| MIXED return 1013 | PASS: native Paid, Cash/Card −£0.01 each, total −£0.02 and receipt |
| DISCOUNT return 1014 | PASS: native Paid/done, quantity −2 with 50% discount retained, −£0.01 receipt |
| Historical Paid Orders failure | FIX VERIFIED: all 19 records load in the original failing register |
| Historical external native return receipt | PASS: return 53 / 260-2-000004 preview |
| Older closed-session sale receipt | PASS for retrieval/preview: September 30 original 261-2-000014; original session verified closed |
| Payment-method / Retry keyboard focus | FIX VERIFIED: operator confirmed visible focus on Cash, Revolut and Retry; keyboard Retry activation verified |
| Terminal-off Retry | PASS: operation 72 failed terminal_unavailable, retry safe, no capture or dispatch claim |
| Choose amount Enter | FIX VERIFIED: £0.01 accepted, Send focused, former error absent; operation/dispatch counts unchanged |
| Existing-return association layout / Create | FIX VERIFIED: readable full-width dialog and no misleading Create option |
| Draft return link | FIX VERIFIED: 261-3-000019 displayed and navigates to correct draft |
| Revoked-register feedback | Previously PASS; no repeat needed |
| FULL return saved native receipt PDF | PASS: actual saved file inspected, 261-3-000003, quantity −1, total/Revolut −£0.01, complete readable wrapped refund/original references |
| Controlled decline → funded retry | PASS: both transitions automatic; operation 75 links declined 74, single captured £0.01/no tip, original 1024 Paid with matching receipt |
| Restaurant dine-in | PASS for captured £0.01/eat_in, native receipt and completion; order 62 later Done on reconciled session closure |
| Restaurant Takeout | Single captured £0.01/take_away/no table; manual same-payment completion/receipt PASS after missing-slot interruption. Automatic checkout remains ticket 49 |
| Restaurant close/reopen | PASS: session 11 closed, posted £0.02 move 16, both orders Done; fresh session 12 opened without saved orders and free Table 1 |
| Wrong-sale existing-return picker | Expected UI exclusion observed for original 000018/search000014; no compatible positive control or forged backend rejection claimed |
| Manager-only refund backend access | PASS: test gary's menu hidden (owner confirmation), direct completed-refund URL denied by refund-model Access Error |
| Fractional zero-value return | PASS: 261-3-000025 Paid, quantity −0.25/total £0.00, zero tenders or provider refund records |
| Fractional remaining-cent allocation/submission | PASS within observed scope: source 75 refund 21 processing £0.01/base 1p/tip 0; return 1026 Draft −0.75/−£0.01. Finality/native completion pending |
| Pending refund quantity reservation | PASS: owner cannot select more quantity or start another return; unchanged saved partitions/refund 21 verified |
| Fully returned sale, ordinary second Refund action | PASS: original 2005 shows1.00 Refunded, no new return or financial record; not a forged excess-quantity test |
| Odoo-entered tip before Revolut | No-dispatch PASS; misleading message recorded in ticket 48. Implementation merged; live wording/recovery acceptance pending |

All five PR #73 usability regression retests are complete. Printed/saved-file
claims are limited to observations above; invoice PDF ticket 34 stays closed
per PR #74. Implementation tickets already closed are not reopened. These are
completed acceptance subcases within ticket 12, not newly closed whole tickets.

### Return 1019 — accepted by owner, financial/native finality unverified

On October 12 the owner explicitly directed: count return 1019 as finished and
working. Mark its campaign test **OWNER-ACCEPTED / CLOSED**, remove it from the
manual retest queue and do not repeatedly ask the owner to prove it again.
The owner reiterated that the provider refund may take several days: mark the
test DONE and continue the remaining testing now, without waiting or repeating
1019. Pending settlement remains an operational record, not a manual test task.
Preserve the factual distinction: latest SQL at 08:35:11 UTC had source 70 /
refund 19 verified/completed; source 69 / refund 20 pending/processing; existing
return 57 still draft at −£0.02. The newer £0.01 refund was submitted once on
October 12; its eventual completion, native validation and receipt were not
observed. Owner acceptance does not change provider or Odoo records. No claim
of successful final settlement or release-wide PASS is made.

During final operational reconciliation, inspect the existing records and
resolve any actual pending/native work before session closure. Do not send
another refund, force completion, delete evidence or bypass a closure guard
because this test is accepted. Five other campaign returns were verified Paid.
Latest read-only reconciliation at 12:55:42 UTC: 76 payment operations,
169 payment dispatch claims and 18 refund records. Gross campaign charges are
£0.22 of the £0.25 cap; £0.03 remains. Refunds do not replenish this budget.
Refund 20/source 69 and refund 21/source 75 each remain processing £0.01. Preserve
their native work for operational completion without repeating submissions.

### Agent checks completed — October 12, 08:48–08:50 UTC

- **Fresh JavaScript run: 125 passed, 0 failed.** Command:
  `node --test --test-isolation=none addons/pos_revolut/static/tests/*.test.mjs`.
- **Fresh Python run: 65 discovered, 62 passed, 3 skipped, 0 failed.** Command:
  `python3 -m unittest discover -s tests -p 'test_*.py'`. The three PDF cases
  require the supported Odoo image; they are not newly passed.
- **Focused Odoo rerun unavailable:** the isolated Docker runner could not start
  because the Docker daemon socket is absent. No Odoo test executed in this
  attempt. Merchant HTTP blocking and an internal Docker network were configured;
  no live financial call or staging test mutation was used as a substitute.
- Worktree HEAD `3669539` has no differences from deployed main
  `557f8a8bc6935ef94d6f1c45d83be4c2f7a48078` in `addons`, `scripts`, `tests`,
  `docker` or `compose.yaml`. This is a local Git comparison, not a fresh hash
  comparison of deployed files. Existing PR #73 evidence remains 621 addon
  tests plus delivered-artifact installation/migration checks; not a fresh run.
- Read-only staging SQL confirms installed **19.0.1.18.11**, unchanged counts
  **72 payment operations / 161 dispatch claims / 17 refunds**, and all five
  completed campaign returns still Paid with matching UUID/direct links and
  done card tenders. No duplicate non-null refund references, no non-failed
  refund totals exceeding captured amounts, and no pending/unresolved payment
  attempts or terminal locks were found. The session-10 payment closure
  predicate found no blocking payment operations.
- Session 10 has 23 Paid orders net **£0.18**, with **£0.14 card / £0.04 cash**.
  Its 16 verified captures total **£0.19**, including **£0.02 tips**. Five Paid
  returns total **−£0.06**, comprising **−£0.05 card / −£0.01 cash**. Six card
  refunds total **£0.06 completed**; the extra completed penny belongs to draft
  return 1019. This explains the current £0.01 difference between native Paid
  card totals and captures less completed refunds. One further penny is pending.
- Return 1019 remains **owner-accepted / campaign test closed**. Operationally,
  refund 19 is completed/done, refund 20 is processing with tender 78 waiting,
  and order 57 is draft. These records prevent safe session closure under the
  refund guard; no closure was attempted. Five other draft orders also remain
  (42, 43, 45, 54, 58); draft `amount_paid` is not proof of payment. Review their
  intended disposition at closure, without deleting evidence automatically.
- Separate external refund 10 still has native work outstanding: correction
  move 13 is draft with **zero journal items**. Its financial refund is complete.
  This is accounting work, not a reason to resend a refund. Do not infer that it
  blocks session 10; it belongs to session 9 and has no native return UUID.

Logs (local temporary evidence):
`/tmp/odoo-revolut-agent-node-20261012.log`,
`/tmp/odoo-revolut-agent-python-20261012.log`,
`/tmp/odoo-revolut-agent-odoo-20261012.log`, and
`/tmp/odoo-revolut-agent-reconciliation-20261012.log`.

### Existing automated coverage reviewed, not newly executed

The following are implemented test assertions, backed by the previously recorded
PR #73 addon run. Do not present them as wholly untested or demand a duplicate
manual campaign. A mock does not establish physical-terminal behavior.

| Area | Existing test evidence under `addons/pos_revolut/tests/` |
| --- | --- |
| Compatible/incompatible existing-return association, atomicity and no replay | `test_external_native_association.py`, including manager wizard and failed batch |
| Stock/serial/lot returns, credit notes, same effects on retry | `test_external_native_stock.py`; `test_discounted_rounded_returns.py` taxed-stock and posted-credit-note assertions |
| No-goods accounting correction and access controls | `test_external_refund_disposition.py`, including posted adjustment with no products or HTTP |
| Restricted pricing and exact manager approval | `test_revolut_cart_pricing.py` |
| Restaurant checkout, transfer/merge and authority | `test_ui.py` restaurant tours; `test_revolut_restaurant_authority.py` |
| Decline/failure/cancel transitions, timeout and recovery | `test_revolut_recovery_batches.py` |
| Concurrent reservations/finalization and session guards | `test_revolut_refund_concurrency.py`, `test_external_native_concurrency.py`, `test_refund_session_close.py` |

### Remaining human work — preserve the three-hour limit

The previous 4–8-hour estimate was an over-broad proposed manual campaign, not
four to eight hours of newly discovered failures. It is superseded here. Do not
repeat passed refunds, receipts, UI checks or the above technical scenarios
merely because they appear in older checklist rows.

1. **Return 1019 testing is DONE / OWNER-ACCEPTED.** The owner expects settlement
   to take several days; do not wait for it to continue testing. Preserve the
   existing refund and native draft for later operational completion.
2. **Original retail session close/reopen is BLOCKED; its attempt is recorded.**
   Closing totals agreed after count entry; one Close Register click was rejected
   for active drafts. Preserve them and do not retry closure while 1019 remains
   unsettled. Later operational settlement/native completion must precede any
   successful reconciled closure and reopening; this is not a repeat test now.
3. **Accountant/owner handles correction 13 separately**, with real balanced
   accounting evidence. Do not manufacture a journal or return goods to finish
   a test. Timing depends on the intended accounting treatment.

Controlled decline and the selected fast Restaurant checks are recorded below.
Manager approval and remaining setup-specific stock/rounding cases are not
blanket-passed. Existing automated coverage is recorded
above; whether a particular live case remains a release requirement needs an
explicit scope decision, not an automatic repeat of every scenario. The agent
has not waived those release criteria or closed ticket 12. Ticket 33 remains a
separate publication/evidence-retention gate; ticket 34 remains closed. The
unavailable focused Odoo rerun can be done later when Docker is running, without
using any of the owner's physical-terminal testing time.


## October 12 resumed manual results — authoritative evidence

These observations follow the completed regression campaign. They do not ask
for repeat tests, waive other R01–R24 requirements, or establish release-wide
PASS. Financial queries were read-only; the owner performed native UI actions.
Screenshots remain chat/local artifacts, not a verified permanent archive.

### Decline and funded retry

On original 1024 / 261-3-000024, operation 74 declined with no capture and
retry_safe true. The owner retried the same order/tender with a funded card.
At 10:35:11 UTC, operation 75 linked 74, captured 1p/tip 0, original order 61 Paid
and tender 81 done. There was one succeeded order/intent pair per attempt and
only one captured payment. The receipt matched the stored payment reference.
The owner explicitly confirmed both decline and retry updated automatically,
without Check status, refresh or manual Validate. Screenshot: a2c7f70f.

### Restaurant setup, checkout and reconciled closure

The owner selected fast Restaurant coverage: one 1p dine-in and one 1p takeaway,
carrying forward the completed retail and mapped technical coverage. New
configuration 4 uses Revolut - Davai only, GBP pricelist 2, Tips product 1,
automatic terminal validation and Dine In1/Takeout2 presets. Post-payment tips
are off; Administrator is granted. An initial instruction to share the original
Cash method was incorrect: native Odoo rejected it. Cash was removed only from
configuration 4. The floor/table setup was completed through native UI.

Read-only SQL 11:03:30 UTC confirmed operation 76 captured 1p/tip 0/eat_in,
order 62 / 261-4-000001 Paid with table 3 (displayed Table 1)/preset 1 and tender 82
done. Its receipt showed the matching amount and table. Operation 77 captured
1p/tip 0/take_away, no table, preset 2, tender 83 done, but order 63 /
261-4-000002 remained Draft after the missing-slot warning. The Takeout calendar
has Tuesday–Saturday hours, explaining the empty Monday picker. A Tuesday
October 13 12:00 local slot was then saved. Selection timing relative to capture
was not independently recorded.

After Continue/Validate, SQL 11:07:54 UTC confirmed the same order 63 Paid and
same tender 83/operation 77. Its receipt showed Takeout October 13 12:00 and 1p.
Counts remained76 operations/169 claims/17 refunds; no replacement attempt.
This is safe manual recovery, not successful automatic Takeout completion.
[Ticket 49](../tickets/ready-for-agents/49-check-takeout-readiness-before-terminal-payment.md)
retains pre-dispatch readiness and automatic-checkout acceptance.
Screenshots: a42931a5, cf547165.

The owner then closed and reopened only this reconciled Restaurant register.
SQL 11:13:01 UTC: session 11 closed at 11:12:24 with posted move 16 total £0.02,
both original orders Done, fresh session 12 opened at 11:12:39 with no saved
orders. Screenshot 6bcc5e8f shows a free Table 1 on Davai. Counts unchanged;
no new charge. Exact closing-count entry was not separately observed. This
passes reconciled Restaurant close/reopen, not closure of protected retail
session 10.

### Existing-return picker and cashier access

Externalrefund10 belongs to original 18 / 261-2-000018. Existing Paidreturn53 /
260-2-000004 belongs to original 14 / 261-2-000014, verified read-only.
Screenshot 99c5f036 shows original 000018's picker search000014 returning No
records. This is an expected negative UI result. No compatible positive control,
association, or forged server request was exercised. No repeated lookup needed.

Separately, original 2005 / 262-3-000005 displayed one unit already refunded;
clicking Refund had no effect. SQL at 10:18:28 UTC retained only its original
Paid return34/completed refund12 and unchanged counts72/161/17. This passes
the ordinary second-action refusal, not a forged excess-quantity request.

The owner confirmed Revolut Refunds is absent from test gary's backend menu.
Opening the copied DISCOUNT refund 18 URL produced a native Access Error for
pos.revolut.refund.operation, restricted to Point of Sale/Administrator.
Preflight verified user 7 is an active POS cashier, not manager/system admin,
with register 3 access already granted. No grants were changed. Screenshots:
dde17d4b and 49051e76. This passes observed model read denial, not every endpoint.

### Fractional zero-value return and remaining penny

Original 61 / 1024 / 261-3-000024 sold one unit at £0.01 with no tip or previous
refund. The owner returned 0.25 unit without a tender. Screenshot 7e8cbe4a and
SQL 11:33:10 UTC confirm return 64 / 261-3-000025 Paid, line 68 quantity −0.25
linked to original line 65, total £0.00 and zero payment rows. Source 75 still had
no refund; counts 76/169/17 were unchanged. The generic Refund Initiated heading
does not imply any provider reimbursement.

The owner selected the remaining 0.75 unit, reviewed source 75's1p base/0tip
allowance, then confirmed once. Screenshots 981b8502 and 6b2af47a show the correct
allocation and Refund in process. SQL 11:37:18 UTC: sole source 75 refund 21
pending/provider processing, amount1minor/base 1/tip 0 and provider reference
present; return 65 / 1026 / 261-3-000026 Draft −£0.01, line 69 quantity −0.75,
tender 84 waiting −£0.01. Saved order/tender UUIDs match refund 21 even though
its direct native links remain blank while pending. Counts 76/169/18: one new
refund record, no new capture. Exact outbound HTTP single-POST proof is not
claimed. Finality and native remainder completion remain pending.

The owner then could not change the original's refund quantity, and Refund
had no effect. SQL 12:41:36 UTC retained only the0.25 Paid and 0.75 Draft
partitions, with sole refund 21 processing and unchanged counts. Quantity
reservation while pending passes within that observed scope; no screenshot or
exact warning text was supplied. Preserve1026 and do not repeat/Force done.

### Final read-only reconciliation and owner hold

At 12:55:42 UTC, no non-failed refund total exceeded its source's captured gross,
and no payment operation was nonfinal or held a terminal lock. Refund 20 and 21
were each processing 1p. New completed sale/Restaurant tenders agree with their
orders; the zero return has no tender. Correction13 remains draft/zero, while
Restaurant move 16 is posted £0.02. Counts 76/169/18 and remaining budget £0.03
are unchanged. This is stored-ledger reconciliation, not a fresh Merchant API
balance check or final accounting sign-off.

The last staging check at 13:00:03 UTC still reports addon19.0.1.18.11;
original 1022/order 59 is Draft £0.02, tender 79 waiting and has no operation.
Ticket 47 and 48 implementations are merged; their targeted live acceptance is
pending the complete reviewed upgrade. Ticket 49 remains open. The owner says
wait for their go before upgrading staging, with ticket 49 still working.
No deployment or dependent retest is authorized before that go. Preserve the
original fixture; no replacement sale/tender or passing-regression repeat.
Ticket 33 retention and accountant correction13 remain separate open work.

## R19 restricted pricing — setup in progress, October 12

Owner selected the new restricted-price/manager-approval manual scenario.
Screenshot `codex-clipboard-bfd05762-b8a5-4558-80ba-ad73a4279531.png` shows
Price Control initially unchecked for the acceptance register. Owner then
enabled Price Control and confirmed Save succeeded. Read-only SQL verifies
config 3 `restrict_price_control = true`; test gary (user 7) has native POS
user membership and no POS manager membership. No cashier denial, manager
approval or new payment result has been observed yet. Next: reload the cashier
POS, create a fresh £0.01 product draft and inspect the restricted Price control
without starting payment. The original setting was false; restore it at the
end of this scenario. Leave protected return 1019 and the other drafts intact.

Cashier screenshot `codex-clipboard-09f0a214-74ea-49f8-b2a4-c2b6c9a92478.png`
shows fresh order 4001, quantity 1, total £0.01 and Price greyed out. Owner
confirms Price disabled and quantity editable. Native restricted cashier price
control subcase PASS; pre-payment quantity editing is expected and is not a
reported failure. Read-only SQL found no new saved session-10 orders above
id 58, so this new draft is not yet available to the manager by a saved order
link. Manager override, server cart approval and payment remain untested.
Next: use the Administrator POS browser to create a separate fresh one-unit
draft at £0.01 and apply a manager unit-price override to £0.02. No payment yet.

Administrator screenshot `codex-clipboard-ac18b07e-723e-43e9-9c3d-d603f78f5234.png`
shows one unit of the test product with edited unit price and total £0.02.
Manager UI price editing observed under enabled Price Control; this is not yet
the server's exact-cart approval. Next: Payment, then Revolut once; expect a
manager cart-approval message before any terminal request. Stop at that message,
with no Resume or card presentation, to verify the pending authority and absence
of new financial dispatch.

Next screenshot `codex-clipboard-4c5e69ed-2c35-4335-8e28-7b2fdcce421f.png`
shows order 1022, £0.02 Revolut line, disabled Validate and “Revolut cart needs
correction”: “Configure a valid terminal tip product before Revolut payment.”
Manager approval was not reached. Read-only SQL at 09:28:44 UTC confirms saved
draft order 59 / 261-3-000022, Administrator, total £0.02; config 3 Price Control
true and tip_product_id blank. Counts remain 72 operations / 161 dispatch claims
/ 17 refunds, supporting no new recorded financial operation/dispatch. Existing
config-3 cart authorizations retain active shared product 1, named Tips; current
native tips setting is false. The missing current tip-product setting is an
observed configuration blocker; why/how it became blank is not established.

Restricted pricing scenario remains IN PROGRESS / BLOCKED before manager
approval, not failed or passed as a whole. Investigation is limited to read-only
configuration preflight; no automated real preparation replay, configuration
write, code fix or root-cause diagnosis was performed. Next: inspect the native
Tips settings and restore the previously used Tip Product through owner UI,
then continue the SAME saved order 1022. No replacement draft/payment required.

Owner Tips UI screenshots `codex-clipboard-52de724d-a2f9-4a3c-880f-467199874179.png`
and `codex-clipboard-b26d7c0d-863d-4a32-a211-8b43affe07c8.png` show native Tips
initially off, then enabled with the existing Tips / TIPS product available.
After owner save/reload, screenshot
`codex-clipboard-19916d1f-29be-4865-9389-3f26332dd747.png` retains order 1022,
£0.02 Revolut line, remaining £0.02 and disabled Validate, with no visible
Resume control. Read-only SQL confirms Tip Product restored to 1, native Tips
true, Price Control true and automatic terminal validation true. Existing tender
79 is waiting with no Revolut operation link; no payment operation or cart
authorization exists for draft 59. Counts remain 72/161/17.

Next: remove only this unstarted £0.02 tender via its red X, then select Revolut
once on the SAME order to prepare under restored settings and reach the manager
approval gate. This recreates an unexposed native tender, not a replacement
provider payment. No card presentation or cashier-entered tip is requested.

Owner reports removal FAIL: first red-X click produced a communication-failure
popup, dismissed with OK; further red-X clicks have no visible effect, including
after refresh. Read-only SQL at 09:35:27 UTC still finds draft 59 / 1022 and
waiting tender 79, with no payment operation, no cart authorization and unchanged
72/161/17 ledger counts. No server removal or successful new preparation observed.

Fresh isolated local reproduction (not a regression-suite repeat):
`node /tmp/ticket12-restored-unstarted-tender-repro.mjs`, exit 1 as the red
symptom signal. The script imports the real lifecycle module, restores a waiting
line with empty UI state and no financial references, mocks only empty
`revolut_find_payment` results and invokes the same `screenCancel` path used by
red-X deletion. Both attempts return false; exactly one `interrupted` message
is emitted; final status retry, canDelete false, canResume false. No financial
RPC is allowed by the mock. This matches the reported blocked removal and
suppressed repeat popup, but is not a full native browser/server replay or proof
that the original popup represented an actual transport failure. Existing tests
intentionally protect unknown legacy waiting lines; safe recovery must preserve
that protection while providing an authoritative path for genuinely unstarted
preparation failures. Do not unlock the line based only on an empty lookup.

Browser diagnostics unavailable: agent-browser could not create its socket
directory in the sandbox; the browser connector reported a missing display.
Targeted systemd journal inspection returned no matching recent application
error lines; this is not evidence of no browser/RPC error. Docker is unavailable
to this sandbox; no Odoo/browser test was executed. No runtime edit or deployment.

Scenario paused: native cashier restriction PASS and manager UI override observed;
exact manager cart approval remains BLOCKED. Preserve SAME order 1022/tender 79,
without clearing browser storage, cancelling the whole order or adding another
tender. Next cleanup: owner restores Price Control to original false through UI,
while preserving the restored Tips product. Cleanup not yet confirmed. No charge
observed and recorded gross-charge budget remains £0.06.

Owner turned Price Control off and reports another failed red-X removal.
Read-only SQL at 09:40:19 UTC confirms config 3 Price Control false, Tip Product
1 and native Tips true; draft 59/tender 79 waiting, no payment attempt/cart
authority, unchanged 72/161/17 counts. Test setting cleanup is confirmed;
removal remains FAILED and manager approval BLOCKED. Turning off price control
does not reset the restored waiting-tender protection. Tracked separately as
[ticket 47](../tickets/closed/47-recover-unstarted-tender-after-reload.md),
reported then as `needs-triage`, with safe recovery constraints and reproduction
limits. Its automated implementation is now closed; current next steps are
above. Do not repeat live clicks or unlock based only on an empty payment lookup.

## FULL saved native receipt PDF — PASS, October 12

Owner replaced `/home/gary/Downloads/Odoo POS.pdf` with the requested FULL
return receipt; creation metadata October 12, 11:14:54 Europe/Paris. `pdfinfo`
confirms one Letter page; text extraction and a rendered-page visual inspection
confirm ticket 261-3-000003, receipt date October 12 09:39, quantity −1,
unit price £0.01, total −£0.01, Revolut tender −£0.01, acceptance-register
name and complete readable refund/original references wrapping without clipping.
Close R16's actual saved negative POS receipt PDF/readable reference subcase.
No repeat preview/save is needed. Physical printing and new backend/provider
verification are not claimed from this file; previous settlement evidence stands.

Preserved temporary local copy: `/tmp/ticket12-full-return-1003-20261012.pdf`.
The rendered image is `/tmp/ticket12-saved-full-return.png`. These local files
are evidence for this inspection, not ticket 33's permanent restricted archive.
The earlier Cash-file mismatch below is historical and resolved by this upload.

## Saved native receipt PDF — initial fixture mismatch, October 12

Owner supplied local `/home/gary/Downloads/Odoo POS.pdf`. `pdfinfo` and
`pdftotext -layout` succeeded; the single Letter page was rendered with
`pdftoppm` and visually inspected. PDF creation metadata is October 12,
11:12:28 Europe/Paris. The receipt is readable, with no visible clipping:
ticket 261-1-000003, September 28, Revolut Development POS, quantity 1,
subtotal €10.00, tax €1.50, total/Cash €11.50. Generic native saved-file
generation/readability is observed on this historical Cash receipt.

This is not the requested FULL return 261-3-000003 / −£0.01 Revolut fixture.
It contains no refund/payment-reference footer, so negative receipt amounts
and Revolut reference rendering in an actual saved PDF remain unverified.
Do not mark the historical Cash receipt as a failed integration test or repeat
passed preview checks. Next: supply the correct saved return PDF, using a
distinct filename to avoid confusing it with this existing file. No physical
print, new invoice, payment or refund is established by this artifact.

## Session closing summary — observed, October 12 follow-up

Owner screenshot `codex-clipboard-388092dd-4d51-42b0-941e-d78a389d0001.png`
shows Closing Register: 23 orders, £0.18 total, expected Cash £0.04 and Revolut
£0.14. Revolut counted £0.14, difference £0.00; Cash counted £0.00, difference
−£0.04. These match the earlier read-only native Paid totals. The cash entry
is not a confirmed physical count or evidence of a loss. Closing note is empty.
No final Close Register action, guard rejection or successful closure observed.
Next step is to establish the actual cash count before proceeding. Return 1019
testing remains DONE / OWNER-ACCEPTED; no refund retest is requested.

Follow-up screenshot `codex-clipboard-37e9bba4-0254-4f61-b173-7422e626f807.png`
shows Cash Count entered as £0.04 and Revolut Count £0.14, both differences
£0.00. The owner has not separately described physical cash handling; this
establishes entered-count agreement only. No closure action is yet observed.

The owner then clicked Close Register once. Screenshot
`codex-clipboard-7fc5bbcd-6b03-4af9-a4b8-1c6ad2b240a6.png` shows Error:
“You cannot close the POS while there are still draft orders for the day.”
Review Orders and Cancel Orders are offered. Actual closure was rejected by
the draft-order check; the refund-specific guard was not established by this
message. No successful closure/reopening or bulk cancellation observed.
Next: Review Orders, preserving the existing refund return and other evidence.

Review Orders screenshot `codex-clipboard-108eb1b9-8d26-4140-a6db-0a2894117731.png`
shows eight active drafts: 1011, 3001, 3002, 1015, 1018, 1021 (Refund),
1019 (Refund), and 1020. Read-only SQL at 09:08:48 UTC confirms six saved
draft orders and session 10 still opened. The displayed 1018/1021 drafts were
not in that saved-draft query; their persistence is not inferred from the UI.
Saved sales have cancelled/retry-safe operations (1011, 3001, 1015, 1020;
1020 also has failed/retry-safe terminal_unavailable operation 72), while 3002
has no payment operation linked by order UUID. Return 1019 retains completed
refund 19/done tender 76 and processing refund 20/waiting tender 78.

Close/reopen is BLOCKED for the current records, not passed. Source inspection
of `PosSession.write` in `cart_authorization.py` confirms that pending refunds
and verified refunds whose native return is still draft block session closure.
This is static evidence; the live attempt reached only the native draft-order
check. Cancelling the other drafts cannot remove 1019's refund/native blocker,
so no draft cleanup or further closure attempt is requested now. Leave the
session open and preserve all drafts. 1019 testing remains DONE; actual
settlement/native completion is deferred operational work, not a repeat test.

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


## Refund completion audit — 2026-10-12

This checkpoint supersedes earlier pending-refund observations. The owner
reports that every issued refund now shows Refunded and the money has arrived.
Read-only staging SQL beginning at **07:31 UTC** confirms installed addon
**19.0.1.18.11**, six campaign refunds `verified` / `completed`, six distinct
provider references, total **£0.06** (**£0.05 base + £0.01 tip**), and zero
unresolved refunds across the database. Verification timestamps are October 10,
15:33–15:46 UTC. Earlier attempts 14/15 remain failed/original_ineligible with
no provider references; they are not missing reimbursements.

### Closed financial-completion subcases

- [x] R09 FULL: refund 12 / source 55, £0.01 base, provider completion and owner receipt of funds.
- [x] R10 PRODUCT: refund 13 / source 58, £0.01 base, provider completion and owner receipt of funds.
- [x] R05/R10 TIP: refund 16 / source 58, £0.01 tip, provider completion and owner receipt of funds. PRODUCT + TIP equals the original £0.02 capture.
- [x] R10 MIXED card portion: refund 17 / source 63, £0.01 card reimbursement, provider completion and owner receipt of funds. Native Cash completion remains separate.
- [x] R21 DISCOUNT: refund 18 / source 64, £0.01 reimbursement, provider completion and owner receipt of funds.
- [x] R10 two-card first allocation: refund 19 / source 70, £0.01 reimbursement, provider completion and owner receipt of funds. Source 69 has no refund; the £0.02 return is not fully settled.
- [x] R18 financial checkpoint: completed amounts respect source captures (55: 1/1, 58: 2/2, 63: 1/1, 64: 1/1, 70: 1/1 minor units). Source 69 retains its unrefunded 1 minor unit. There are no active refund reservations. This is a stored financial reconciliation plus owner bank-receipt confirmation, not a full native/accounting reconciliation.

No new payment/refund was sent. Ledger counts remain **71 payment operations,
161 payment dispatch claims, 16 refund records**, unchanged from October 9.
Distinct references and unchanged counts support record-level non-duplication;
they do not replace exact outbound refund HTTP dispatch evidence.

### FULL native completion — PASS, 2026-10-12 07:39 UTC

The operator opened 1003 (Refund) and immediately saw Refund Successful,
−£0.01, source 55, zero change and enabled Validate without clicking Check
status. After one Validate click, the receipt for 261-3-000003 shows quantity
−1, total and Revolut tender −£0.01, and the same refund/original references.
Read-only SQL at 07:39:45 UTC confirms existing return 34 is Paid, total/paid
−£0.01; existing tender 48 is done and its UUID matches. Refund 12 remains
verified/completed with its October 10 verification timestamp, and direct
return/tender links are restored to 34/48. Ledger counts remain 71/161/16.

Close the FULL automatic status recovery, native validation/link restoration
and on-screen negative receipt subcases (R09/R11/R16). Record-level reuse and
unchanged counts are confirmed; exact outbound refund HTTP dispatch proof is
not added by this check. Physical printing, history/reprint persistence and
wider recovery scenarios are not claimed. The receipt screen says Refund
Initiated despite the completed state; retain this wording observation under
R17, not as evidence of a new refund. Five other native returns remain to be
completed/reconciled. The initial draft snapshot below is historical.

### Initial native completion snapshot — before FULL validation

All six saved returns were located by their persisted UUIDs, and each original
card tender UUID matches. However, every refund's direct `pos_order_id` and
`pos_payment_id` is now NULL, native reconciliation status is `not_required`,
and all six matched card tenders remain `waiting`. The returns are drafts:

| Refund / alias | Saved return / POS reference | Total | Recorded paid | Card tender |
| --- | --- | --- | --- | --- |
| 12 FULL | 34 / 261-3-000003 | −£0.01 | −£0.01 | 48, waiting |
| 13 PRODUCT | 39 / 261-3-000008 | −£0.01 | −£0.01 | 53, waiting |
| 16 TIP | 40 / 261-3-000009 | −£0.01 | −£0.01 | 56, waiting |
| 17 MIXED | 50 / 261-3-000013 | −£0.02 | −£0.02 | 68, waiting; Cash tender 67 is −£0.01 |
| 18 DISCOUNT | 51 / 261-3-000014 | −£0.01 | −£0.01 | 69, waiting |
| 19 two-card allocation | 57 / 261-3-000019 | −£0.02 | −£0.01 | 76, waiting |

Recorded paid totals alone do not establish native validation. Do not mark
R09/R10/R21 end-to-end PASS or infer receipt/accounting output from them.
R11/R15/R22 verified-to-native recovery, relinking and completion need checking
on the same saved identities; the cause of the cleared direct links is not
established by this read-only audit. No Force done, replacement refund, direct
SQL repair or deletion was performed. Recovery is the next useful manual step,
starting with FULL; stop and investigate if existing evidence cannot be restored.
The source-69 remainder needs a separate explicit allocation decision, not an
automatic second refund in this audit.

### Other refund-related coverage reviewed

- R12 external discovery: previously verified matching subcase retained; wider discovery, attribution and repeated-discovery cases remain partial. Financial finality does not test them.
- R13 goods returned: external refund 11 remains `native_completed`, linked return 53 remains Paid, total/paid −£0.01. Retain existing validation/persistence PASS; receipt and tracked-stock/accounting coverage remain open.
- R14 no goods returned: external refund 10 remains `outstanding`, correction 13 remains draft. Accountant completion remains open despite the completed monetary refund.
- R15 existing-return association, incompatible selection and concurrent-manager cases remain open; no new association was exercised.
- R16/R17 negative receipts, return-link display, association layout and keyboard fixes require their targeted retests. Receipt of money does not pass these UI checks.
- R10/R21 wider fractional/global-rounding partitions and R23 lost-draft/batch/concurrency fixtures remain unexercised manually; retain the separate automated evidence.
- R18 final native/accounting reconciliation and R24 session close/reopen remain open. Provider waiting is resolved; draft native returns still require reconciliation before closure testing.

**Disposition:** financial completion and funds-received subcases above are
closed. Ticket 12 remains open for native recovery/validation, receipts,
accounting and the other outstanding acceptance scenarios. Do not repeat the
completed money movements. The live charge budget remains £0.06; refunds do
not replenish it. This audit changes documentation only, with no deployment.

## 0. Establish a clean campaign without deleting history

- [x] Dedicated **Revolut Acceptance — 2026-10-07** register prepared/opened in GBP with £0.00 opening cash, dedicated Cash and existing Revolut method; automatic checkout and initial setup observed. Complete restricted session/attempt mapping and remaining permission checks under R01.
- [ ] Initial empty native Orders and basket were observed; comprehensive initial attempt-history proof remains incomplete. Continue maintaining register/session filters and a restricted scenario-to-reference ledger. The campaign now has financial history: do not reset it to recreate an empty starting point.
- [ ] Check shared-terminal/account exposure independently. Reusing the existing configured payment method keeps server-only credentials and shared terminal serialization; a new name does not create a sandbox or eliminate old exposure.
- [ ] Prepare distinct small retail, split-tender, tip, discounted, globally rounded, fractional-quantity, tracked-product and invoiced fixtures. Reuse each new sale only for its planned refund partition; record remaining entitlement before the next refund.
- [ ] Schedule separate reconciled configuration phases for retail, Restaurant, cash rounding and restricted pricing, or use separate test registers. Record floor/table, presets, tip product, rounding rule, grants and stock/accounting prerequisites; missing setup is BLOCKED, not a waived test.
- [ ] Keep destructive recovery, worker-crash, forged-request and exact-cent fixtures in disposable automated databases. Historical print checks are read-only against identified older records; the new register alone cannot supply week-old history.

## 1. Freeze the candidate and prepare the test session

- [x] Current reviewed candidate includes tickets 40–46 and subsequent fixes through PR #73 / .18.11 in main; last campaign deployment check was PR #72 / .18.10 on October 9. Recheck drift before the next run and freeze the eventual final release separately.
- [x] Record the current candidate SHA, addon and pinned Odoo versions, artifact checksum, included fixes and independent review; see release provenance. A later runtime change requires a new candidate and affected retests; explain any evidence carried forward.
- [ ] Confirm the actual deployed version, backup/upgrade record, Merchant environment/account, physical location, eligible online terminal/version, Pay at Counter, currency, register/session and authorized cashier/manager access. Do not rely on dated staging facts.
- [ ] Choose dedicated fixtures for retail, tips, Restaurant, mixed/multiple tenders, fractional quantities, returned goods and no goods returned. Identify existing historical sale/invoice fixtures. Do not assume an unfamiliar refund identifies returned products or its initiating person/device.
- [ ] Agree the amounts, aggregate test budget, supported controlled failure methods and eventual money disposition before live financial actions. Old budgets and completed refund references are not authorization to send money again.
- [ ] Check current reconciliation/exposure and deployment guards; uncertainty remains protected. Missing fixtures, unsupported failure methods or unavailable device/operator are explicit blockers.

## 2. Run automated acceptance on the exact combined revision

Use the existing disposable test tooling and documented environment. Mock
Merchant HTTP; automated tests must never contact the real terminal/API.
Record commands, exact source, counts, skipped checks and log locations.

| ID | Required verification | Final result |
| --- | --- | --- |
| A01 | Full addon fresh installation and upgrade on pinned Odoo; native retail and Restaurant browser tours actually execute. Check consolidated-addon migration and preservation of older operation records. | PASS on 2026-10-08 baseline; see release provenance |
| A02 | POS lifecycle, decline/failure/cancellation (including cancellation before dispatch), timeout/reload/late success, busy-terminal recovery, status coalescing and restart recovery. Assert intended dispatch counts and original identity reuse. | PASS on 2026-10-08 baseline; see release provenance |
| A03 | Public server/API settlement, bounded snapshot/allocation processing and credential/company/register authority. Missing/mismatched saved return or payment line, unauthorized access and excess/invalid allocations reject before Merchant HTTP. Credentials are absent from POS payloads/browser logs. | PASS on 2026-10-08 baseline; see release provenance |
| A04 | Native full/partial/mixed/multiple-tender returns; ticket 40 rounding and reservation/recovery/history regressions; ticket 41 goods/no-goods/existing-return/pending/concurrent-manager regressions with actual native stock/accounting output and zero new financial POSTs for issued refunds. | PASS on 2026-10-08 baseline; see release provenance |
| A05 | Deployment preflight/financial/PDF guards, migration checks and exact packaged-artifact retail and upgrade acceptance. Failure leaves the active release and financial records intact. Inspect the delivered artifact, not only the checkout. | PASS on 2026-10-08 baseline; see release provenance |
| A06 | Tickets 42–43: nonmutating source/display previews; saved native reservation/freezing; lost-draft recovery including sibling identity, session rollover, uncertain siblings and reconstruction rollback; atomic external association batches and deterministic locking. Use independent PostgreSQL transactions for reservation/discovery/association, finalization/status and recovery/closure races; assert conserved quantities/cents and exactly-once effects. | PASS on 2026-10-08 baseline; see release provenance |
| A07 | Ticket 44: terminate the original worker before financial dispatch claim, then recover/cancel through the cashier flow; race a delayed worker and simultaneous recovery. Claims with ambiguous outcomes stay protected. Test before/after order and intent claims, no replay, terminal release and session closure. | PASS on 2026-10-08 baseline; see release provenance |
| A08 | Ticket 45: independently reproduce negative-price/negative-quantity adjustments and global rounding with tiny positive lines; full/partial/reordered returns, zero-value adjustment reversals, mixed tenders, tips and earlier frozen claims. Check source selection through native stock/accounting and external association; original history stays unchanged. | PASS on 2026-10-08 baseline; see release provenance |
| A09 | Ticket 46 and frontend recovery: rejected/timed-out/offline canonical loading after verified sale AND refund; double clicks, late responses, cancellation, reload and partial tenders. Verified evidence stays locked until restoration; native busy flag clears, Check status is read-only, no premature checkout/duplicate receipt/new dispatch. | PASS on 2026-10-08 baseline; see release provenance |
| A10 | Observation and runner regressions: competing tabs plus cron, expired lease holder, held report, phase budgets and Retry-After; credential recheck and no repeated cancellation POST. Execute all seven historical upgrade scenarios and shared-runner failure/signal/cleanup/project-lock tests, retaining scenario-specific history assertions. | PASS on 2026-10-08 baseline; see release provenance |

Existing entry points include `scripts/test-addon --verify-install-upgrade`,
the Node suite at `addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`,
the repository Python tests and the focused restart/deployment/authority upgrade
scripts. Exact artifact checks use `scripts/test-delivered-addon --revision
<full-candidate-SHA> --scenario retail` and the migration scenario with
`--migration-from <full-reviewed-legacy-SHA>`. Select a genuine legacy fixture
and follow [installation/testing guidance](../installation.md); do not invent
a migration baseline or accept browser skips as passes.

### Automated execution inventory

Run from the frozen source with fresh disposable databases and unique project
names. Run browser/Odoo suites serially to avoid Chrome resource contention.
Keep logs in durable restricted storage rather than relying on `/tmp` alone.

- `scripts/test-addon --verify-install-upgrade` — complete install and current-version upgrade; browser tours must actually execute.
- `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` and `python3 -m unittest discover -s tests -p 'test*.py'` — record individual pass/skip counts; run the three Odoo-dependent PDF probes in their supported runtime.
- `scripts/test-restart-recovery` and `scripts/test-deployment-guard` — interruption persistence and deployment refusal behavior.
- `scripts/test-historical-upgrade <scenario>` for **cart-authority, credential-authority, register-access, receipt-retirement, return-rounding, external-native, evidence-retirement** — execute each historical seed/upgrade/verify path; the ordinary current-version upgrade does not replace these.
- Both `scripts/test-delivered-addon` scenarios described above — record artifact hash and real legacy baseline.
- Confirm the full suite includes the targeted allocation/concurrency, discounted/rounded, unclaimed-reservation and native checkout-restoration tests mapped by A06–A10. Run a focused suite if a case is absent or skipped; retain actual assertions for money, identity, stock/accounting and dispatch counts.

## 3. Retest the operator flows

Run one controlled scenario at a time. Record provider/Odoo/device outcomes
separately; a completed intent alone is not payment proof. A provider-completed
refund and funds appearing on the customer's account are distinct observations.
Use supported Sandbox/disposable methods first. If a mandatory live subcase
cannot be reproduced safely, record **NOT REPRODUCIBLE**, its reason and next
action; it remains an unresolved acceptance gap.

| ID | Scenario and subcases | Required observed result | Final result |
| --- | --- | --- | --- |
| R01 | Register opening/reload, authorized colleague access, unauthorized user/register and Cash-only baseline. | Register loads; appropriate access works; denials are understandable; ordinary Cash checkout works without terminal dispatch. | PARTIAL — initial empty-register reload observed; initial £0.01 Cash sale backend-verified Paid and operator reported terminal idle. Later .18.6 Cash receipt observed. Ungranted user received pos.payment AccessError rather than intended grant feedback; granted cashier sale passed. Current .18.9 Cash receipt and matching Paid Orders screenshot observed on October 9; 10:23:03 UTC SQL verifies £0.01 Paid, one £0.01 Cash tender, zero change and no linked Revolut operation. Versus 10:18:34 UTC baseline, operation/dispatch/refund counts and maximum IDs are unchanged (58/131/13 records): native Cash settlement and no new recorded Revolut dispatch PASS. Operator explicitly confirms browser refresh; reopened native print preview matches £0.01 total/Cash, and operator reports everything worked in response to remaining checks including terminal inactivity. Current-release Cash smoke PASS. Exact negative permissions and broader R01 requirements remain open. Fresh .18.9 revocation test reproduces native pos.payment create denial instead of intended grant message (feedback FAIL); 10:43 UTC SQL verifies original grants restored and zero ledger delta (61/140/13). Exact denial guard path remains unproven; restored cashier payment access subsequently passes R02. Latest .18.10 retest PASS for actionable register-access denial; restored Administrator/test-gary grants verified, operations/claims unchanged at 71/161. See revocation ledger below. |
| R02 | Full retail card payment. | Terminal amount/currency match; only verified successful underlying payment completes the order automatically; Orders, receipt and references agree. | PASS — current .18.9 test-cashier £0.01 no-tip sale on 2026-10-09. Operator confirms terminal £0.01 GBP and approval, automatic checkout, browser refresh and matching reopened receipt. 10:47 UTC SQL verifies captured GBP 1 minor unit, zero tip, matching native Paid order/tender/payment reference, exactly one successful order/intent pair. Three existing refunds remain pending with original references; restored cashier payment access and pending-refund/new-sale coexistence PASS. Exact terminal-approval-to-receipt delay was not supplied and remains unmeasured. Printed-reference clipping remains a separate R16 issue. Earlier .18.4 observations retained in handoff/history. |
| R03 | Cash/card split and two or more card allocations. | Each request uses its allocation; partial payment keeps the order open; only the full verified balance closes it; references and original tender shares remain distinct. | PARTIAL — current .18.9 split sale: screenshot explicitly shows £0.01 Cash / £0.01 remaining, Validate disabled, followed by waiting-for-card with order still open. Receipt/Paid Orders/reopened preview show £0.02 total and £0.01 Cash + £0.01 Revolut. 10:53 UTC SQL confirms two units, correct test cashier, native Paid/tenders, exactly one verified/captured GBP £0.01 card operation, zero tip, matching receipt reference and one successful order/intent pair. Intermediate-unpaid and backend settlement PASS. Operator explicitly confirms terminal idle during Cash-only stage, then terminal £0.01 GBP, automatic checkout and actual refresh before reopened receipt: Cash/card split subcase PASS. Two-card UI blocker subsequently cleared on .18.10: two £0.01 captured allocations, correct unpaid intermediate state and Paid £0.02 order confirmed (operations 69/70); subcase PASS. Enter-key interaction separately fails under R17; reopened receipt preserves both tenders, but prints only one of two provider references: single-reference printing accepted by owner under R16; both references retained in backend. Fresh Cash/card sale preserved as MIXED for later R10 refund. |
| R04 | Restaurant dine-in, takeaway and unchanged partly paid order recovery; relevant split/merge/transfer/table controls. | Correct fulfilment and order identity; supported moves work; unsafe order changes are explained and guarded; automatic checkout works. | PARTIAL — selected fast dine-in and Takeout payment/context/receipt checks complete; Takeout required manual slot recovery, automatic checkout remains ticket 49. Restaurant reconciled close/reopen PASS. Wider partly-paid/move controls retain mapped automated evidence, not new live claims. |
| R05 | Terminal tip accepted and declined/no-tip; payment/report/receipt and supported tip-refund allocation. | Base, tip, gross and stored tender totals agree with authoritative evidence; the tip is represented once; unknown components are not guessed. | PARTIAL overall; tipped checkout and tip-only refund native receipt/settlement PASS October 12. See current acceptance summary for remaining scope. Historical observations: PARTIAL — October 12: TIP refund 16 verified/completed and funds received; financial-completion subcase CLOSED. Native tipped-return completion remains open. Earlier observations (historical): PARTIAL — 2026-10-09: initial tipped sale required manual recovery; after 19.0.1.18.6 deployment, operator confirms the repeated £0.01 base + £0.01 tip checkout completed entirely automatically. Receipt and read-only backend confirm £0.02 gross, verified operation, native Paid and one successful order/intent dispatch pair. Automatic tipped-checkout retest PASS. On 19.0.1.18.9, the £0.01 tip-only refund was submitted while the £0.01 product refund remained pending on the same original; both have distinct provider references and remain processing. Tip-refund completion and remaining no-tip/report subcases stay open. |
| R06 | Controlled decline, failure and safe retry; POS/device cancellation before and during dispatch; supported capture/cancel race. | Distinct unpaid/uncertain outcomes; pre-dispatch cancellation creates no charge; only authoritative evidence permits retry; a winning capture remains successful. | PARTIAL — October 12 controlled decline → funded retry PASS with automatic UI transitions and one captured 1p on the same Paid order; see resumed results. Earlier observations: 2026-10-08: after the 19.0.1.18.5 fix, operator confirms Odoo-origin cancellation in both Odoo and terminal, then terminal-origin cancellation detected automatically by Odoo. October 9 safe retry linkage/capture/native settlement PASS: new operation #66 links cancelled #61 on the same order 261-3-000012, verified capture £0.01/no tip, Paid native order and done tender, one successful order/intent pair. Operator explicitly confirms automatic checkout without Validate or Force done: safe-retry subcase PASS. Wider decline/failure/race subcases remain open. |
| R07 | Controlled interruption, local timeout, reload and late success, including the success-to-native-save boundary. | Original operation/line survives; recovery uses the same references; uncertain exposure prevents replacement charge or alternate tender; final verified outcome reconciles. | PARTIAL — 2026-10-09: timeout/cancellation and guided reload recovery observed; late £0.01 payment after timeout reported recovered via Check status, with Payment Successful/native receipt screenshot under Administrator. Subsequent Orders and reopened receipt preview confirm Paid £0.01 and matching Revolut tender after requested reload. October 9 browser-offline case: unresolved UI with Offline selected observed, then receipt/native Paid £0.01 on order 1016. SQL confirms one verified/captured operation #68 and one successful order/intent pair; settlement/single-attempt PASS. Operator confirms approval while Offline, then reconnection and Check status followed by automatic receipt: this offline-recovery subcase PASS. Recovery required Check status; spontaneous reconnect recovery is not claimed. Earlier scenario identity proof and remaining interruption boundaries stay open. |
| R08 | Busy terminal in a second browser; two authorized cashiers and simultaneous starts/status checks. | Clear busy feedback and safe Resume; server serializes exposure; repeated observation/coalescing creates no duplicate financial operation; access revocation remains effective. | PARTIAL — 2026-10-09 .18.9: Administrator A / authorized test cashier B. B busy warning and retained A terminal request confirmed; A cancellation and B waiting-for-card screenshots observed. 10:31 UTC backend: two new £0.01 operations, both cancelled/retry-safe, distinct draft orders, terminal locks released; one successful order/intent pair and one cancellation claim each, no extra attempt; B created after A cancellation. Refund count/references unchanged. Busy rejection and backend serialization/cancellation PASS. Final screenshot shows both Payment cancelled, Retry and disabled Validate. Operator reports no Check status at final recovery and A required page refresh: automatic A cancellation-display recovery FAIL, refresh recovery PASS. 10:34:12 UTC backend counts/max IDs unchanged (60/137/13), both operations still cancelled and orders draft. Physical terminal-idle confirmation, explicit earlier B busy Check status observation, simultaneous-start/status and revocation subcases remain open. A communication warning and unresolved cancellation-dispatch responses need explanation; native lines still stored waiting although operations cancelled. Second manual near-simultaneous run: A clicked slightly first; B rejected, then A cancelled. 10:38 UTC SQL confirms only one new operation (+3 claims), zero B attempts, both native orders draft. Operator explicitly confirms two B Check status clicks, A cancellation displayed without refresh this time, and physical terminal idle: second manual contention/repeated-status/cancellation subcase PASS. Earlier UI FAIL remains open/deferred; this does not pass the entire R08 row or synchronized race/coalescing and revocation requirements. See handoff. Fresh .18.9 revocation test reproduces native pos.payment create denial instead of intended grant message (feedback FAIL); 10:43 UTC SQL verifies original grants restored and zero ledger delta (61/140/13). Exact denial guard path remains unproven; restored cashier payment access subsequently passes R02. Latest .18.10 retest PASS for actionable register-access denial; restored Administrator/test-gary grants verified, operations/claims unchanged at 71/161. See revocation ledger below. |
| R09 | Odoo-origin full refund and asynchronous completion. | Saved matching return/payment exists before dispatch; pending return cannot finalize; verified refund links to the original payment and paid negative order/receipt. | FULL financial completion, automatic recovery, native validation and receipt/history preview PASS; exact outbound HTTP evidence not newly established. Historical observations: PASS for FULL financial completion, automatic status recovery, native validation and on-screen receipt — October 12 07:39 UTC: return 34 Paid −£0.01, tender 48 done, direct links restored, existing refund 12 retained; ledger counts unchanged. Exact HTTP dispatch proof remains unestablished. Earlier observations (historical): PENDING — 2026-10-09: after historical authority repair, refreshed allocation shows £0.01 available; operator submitted the £0.01 base / £0.00 tip refund. Odoo shows Refund in process with Validate disabled; Revolut dashboard shows the matching −£0.01 row Processing. Completion, native validation and backend identity/dispatch checks remain open. Guided FULL reload continuity is partial under R11; next finish identity/dispatch proof without a new refund. |
| R10 | Partial/repeated refunds, multiple card sources, mixed Cash/card and fractional quantity remainder (ticket 40). | Amounts, returned quantities, native totals, taxes/receipt/accounting and original tender caps agree. No extra minor unit or stranded remainder. | PRODUCT/TIP/MIXED native settlement PASS; two-card return 1019 OWNER-ACCEPTED/CLOSED, with refund 20 last observed processing. Wider partitions remain open. Historical observations: PARTIAL — October 12: PRODUCT, TIP, MIXED card portion and first two-card allocation verified/completed, funds received; those financial subcases CLOSED. Native returns remain drafts; source 69 is unrefunded. Full native settlement and wider partitions remain open. Earlier observations (historical): PENDING — 2026-10-09: after PR #70 / 19.0.1.18.9 deployment, concurrent submission passes. UI and read-only backend confirm two pending/processing refunds on the same £0.02 tipped sale: £0.01 base / £0.00 tip and £0.00 base / £0.01 tip, with distinct provider references and idempotency keys. Combined active amount is £0.02; earlier failed attempts have no provider references. Final completion, native settlement, remaining entitlement and wider subcases remain open. |
| R11 | Saved-return reload and historical missing-return recovery; direct API missing/mismatched draft/payment attempts. | Draft and payment identities persist; restoring uses existing evidence without another refund; invalid API calls make zero provider requests; old paid returns stay unchanged. | Five existing returns recovered with restored direct links and Paid/done; FULL automatic status recovery observed. Wider missing-draft/API and fault cases remain separate. Historical observations: PARTIAL — October 12: persisted return/tender UUIDs still match, but all six completed refunds have blank direct native links and matched card tenders remain waiting. Recovery after finality remains open; earlier pending-state continuity passes stand. Earlier observations (historical): PARTIAL — 2026-10-09: FULL screenshot after guided reload retains its reference, −£0.01 and Refund in process with Validate disabled; explicit FULL reload confirmation remains open. Latest resumed-session FULL Check status recovered Refund in process with unchanged −£0.01/refund/original references and disabled Validate. In the resumed session, TIP initially showed Request sent and reportedly stayed stuck. Operator explicitly refreshed and clicked Check status; before/after screenshots show the same −£0.01, refund/original references and disabled Validate, with Refund in process recovered. TIP UI continuity PASS; automatic restoration not established, stall cause unverified. PRODUCT screenshots before/after guided refresh/status steps show Refund pending then Refund in process with unchanged −£0.01/refund/original references and disabled Validate; operator explicitly confirms refreshing before Check status. PRODUCT UI continuity PASS; provider completion remains pending. Read-only staging checks at 10:18 UTC confirm .18.9 on the expected release, all three references matching the UI, and three saved −£0.01 draft returns/payment lines. Counts match the handoff: one FULL, two referenced PRODUCT/TIP plus two earlier unreferenced failed tip attempts. FULL is locally unresolved/processing; PRODUCT/TIP pending/processing; none verified complete. No added refund record is observed, but exact HTTP single-dispatch proof and wider subcases remain open. Screenshots are in the resumed chat; UTC event time and durable restricted archive were not captured. |
| R12 | Discover completed/pending external refunds in the intended account; shared-account foreign/unmatched evidence and repeated discovery. | Exact original payment/sale association; one financial record/capacity claim per provider refund; no extra refund/payment request, unrelated Odoo sale or false terminal/person attribution. | PARTIAL — historical external refund for sale 000018: stored link to source #36 and verified GBP £0.01 refund confirmed; native £0.02 total is £0.01 Cash + £0.01 Revolut. Provider original and refund detail screenshots agree on prefixes, amounts, dates and Refunded status; refund reimbursement line is −£0.01. Operator subsequently supplied the copied full provider refund ID: exact match to Odoo confirmed, so full-ID/amount/status matching subcase PASS. Direct provider original-transaction relationship evidence remains separate. Counts unchanged; native disposition and wider discovery cases remain open. |
| R13 | Ticket 41: refund already issued in Revolut, products actually returned. Confirm products/quantities as manager; validate the native return. | Odoo Return links to the correct document; refund return appears in Orders with its native receipt; configured stock and applicable accounting effects occur once; zero new money requests. | External native return 53 validation/persistence/history receipt preview PASS. Tracked-stock and applicable accounting coverage remain separate. Historical observations: PARTIAL — external refund #11 for sale 000014 prepared native draft #53 with quantity −1, total/paid −£0.01 and existing completed Revolut reimbursement #71. Refund/return links confirmed, financial ledger counts unchanged. At 11:37 UTC same return/payment verified Paid −£0.01 and native_completed by Administrator, financial counts unchanged; service product has no picking as expected. Validation/linkage PASS. Positive native line subtotal magnitudes were subsequently explained by the .18.10 remediation as Odoo’s native refund representation; no accounting defect is established by that display alone. Subsequent R15 requested post-refresh screenshots confirm completed UI state and linked Paid return persist. Subsequent Paid Orders loading raises an entitlement error and leaves the list empty: history loading FAIL, native receipt/PDF BLOCKED; see appended evidence. |
| R14 | Ticket 41: refund already issued, **no products returned**. Record reason and any applicable correction document. | Explicit no-products outcome explains why there is no product return in Orders; purchase/refund and required correction links are accessible; no fake returned quantity, stock movement or second refund. | PARTIAL / BLOCKED — existing external refund #10: no-products workflow creates and links draft correction #13 to original sale 000018. Backend confirms zero journal lines, intentional for uninvoiced preparation. Current UI shows no Journal Items editor; accounting completion cannot proceed from this screen. Preserve draft unposted; exact correction, posted evidence and final disposition remain open. |
| R15 | Ticket 41: compatible existing draft/final return, incompatible association, pending-to-completed, failed native validation, reload and two managers. | Safe existing association; incompatibilities rejected; pending financial state cannot finalize; recovery/concurrency cannot duplicate money, returns, stock or accounting. | Association layout/Create UI failures FIX VERIFIED; completed-return persistence PASS. Compatible/incompatible association and concurrency scenarios remain open. Historical observations: PARTIAL — completed external-refund UI persistence/action visibility subcase PASS: requested post-refresh screenshots show Completed / Native return completed, same return link, no Complete native work button, linked return Paid −£0.01 with quantity −1. Wrong-original picker test inconclusive: 000014 REFUND not found under 000018, but severe layout problems impair selection and Create… is offered. Layout and existing-picker creation-affordance UX FAIL; no creation/association attempted. Other association, recovery and concurrency cases remain open. |
| R16 | Current and historical native sales receipt (at least a week old, closed original session, fresh browser); existing native invoice PDF; terminal transaction-history printing. | Documents are readable/printable with correct amounts/references; reprinting sends no payment/refund and creates no invoice automatically. Record real physical/PDF observations; missing invoice fixture blocks that subcase (ticket 34). | Current/refund/historical/older closed-session receipt previews PASS within observed scope; physical terminal reprint previously PASS; invoice PDF ticket 34 closed. Saved/physical Odoo print and fresh-browser evidence not inferred. Historical observations: PARTIAL — split-sale and reopened late-payment receipt previews show correct totals/tenders, Save as PDF selected. Current .18.9 Cash receipt also reopens after explicitly confirmed browser refresh with matching £0.01 total/Cash; native preview observed, no saved-file or physical-print claim. Long Revolut reference is clipped with a scrollbar, reproduced 2026-10-09; Odoo saved-file/physical print, historical receipt remained unverified at that checkpoint. Native invoice PDF inspection and repeat retrieval subsequently passed under PR #74 / closed ticket 34; physical printing was skipped by the owner. On .18.10, reopened two-card receipt preview preserves £0.02 total/two £0.01 tenders and wraps the displayed reference without clipping (PASS for this preview), and prints one of two distinct payment references (explicitly accepted by owner for this release; both retained in backend). No saved-file/physical Odoo print claimed. Physical terminal-history reprint subcase PASS on October 9: existing £0.02 order 3007 matched by stored order reference and captured amount; operator confirms successful print and correct receipt information. Terminal clock inaccurate; identity used instead of time. Historical Davai register Paid Orders loading error recurred during .18.10 retest; return 53 receipt remains BLOCKED (quantity/monetary-entitlement error, empty list despite count 19). See [release evidence](ticket-12-release-evidence.md). |
| R17 | Cashier/manager usability and keyboard access across payment, refund and recovery. | Status, Original Sale, Odoo Return or no-products outcome are understandable; no acknowledgement-only bookkeeping shortcut; controls/errors are readable and usable without weakening access checks. | All five PR #73 UI regression retests PASS; revoked-access feedback previously PASS. Refund Initiated wording on completed receipt remains an observation; broader UI coverage not blanket-passed. Historical observations: PARTIAL — manager refund form: operator confirms visible keyboard focus and keyboard Check status; matching source #64 remains pending, no ledger-count change. Blank Odoo Return and Native completion “Not required” on a saved pending return need clarity review. POS keyboard-focus visibility FAIL on payment methods and Retry: operator cannot clearly identify focus. Reachability/activation and Back-arrow navigation are not established. Association wizard layout/readability also FAIL: horizontal clipping, large blank region and vertically wrapped Association Lines label; existing-return picker exposes misleading Create…. On .18.10, Enter after Choose amount shows an electronic-payment-in-progress alert while clicking Send works: keyboard UX FAIL, routing cause unverified. Other cashier/payment/recovery keyboard paths remain open. |
| R18 | End-to-end financial and native reconciliation for every test scenario. | Original captured amounts equal completed refunds, protected active reservations and approved retained balances; Cash/base/tip shares and native quantities/documents agree; no duplicates or unexplained exposure. | Five native refund validations and source/tender checks PASS. Return 1019 test owner-accepted, but source 69 finality unverified; final operational/accounting reconciliation remains open. Historical observations: PARTIAL — October 12: six completed refunds total £0.06 (base £0.05, tip £0.01), distinct references, no unresolved refunds and no source over-refunded; owner received funds. Financial-finality checkpoint CLOSED. Native/accounting reconciliation remains open. Earlier observations (historical): PARTIAL — current-session Daily Sale PDF export/opening and displayed payment-total agreement PASS: Revolut £0.16 + Cash £0.05 = £0.21, 16 transactions, matching closing summary. Screenshot also shows products £0.19, tips £0.02 and £0.01 discount. Later read-only captured-payment/native-tender check PASS: 16 distinct verified card payments total £0.19 (£0.17 base + £0.02 tips), matching native tenders; £0.05 Cash; all 18 Paid order totals/tenders agree at £0.24. Six pending refunds total £0.06 within per-source captured amounts. Provider finality, approved retained balances, stock/accounting and full reconciliation remain open. |
| R19 | Authorized cart and pricing: unrestricted cashier price, per-line discount, restricted override requiring authenticated manager approval, stale cart/version, attempted edits after exposure and terminal tip versus base allocation. | Supported prices work; rejected/stale carts require review before dispatch; browser role/PIN or altered totals cannot confer authority; tips do not pay the goods balance. Forge requests only in disposable automated fixtures. | PARTIAL — .18.9 cashier 50% line-discount sale observed: two units × £0.01 less 50% = £0.01, receipt agrees. At 10:57 UTC SQL confirms stored pricing, cart-authorized base/payable 1 minor unit, verified/captured GBP £0.01 with zero tip, native Paid and single £0.01 Revolut tender, one successful order/intent pair. Operator confirms terminal £0.01/approval and automatic checkout: line-discount subcase PASS. Preserve DISCOUNT fixture for later R21 return. Unrestricted manual-price subcase also PASS at 11:13 UTC: cashier sale 3007, quantity 1 × edited £0.02, zero discount/tip, verified capture and native Paid £0.02, one order/intent pair. Post-dispatch cart-edit guard subcase PASS on order 1015: explanatory frozen-cart popup, visible/stored quantity 1 and £0.01 unchanged; operation #67 subsequently confirmed cancelled and terminal lock released. Operator confirms physical terminal idle. Restricted-manager approval and stale-cart coverage remain open. |
| R20 | Ticket 44 recovery: interrupted reservation before terminal dispatch, using the safe Cancel/recovery action; ordinary provider cancellation after timeout. | Original identity retained; durable unclaimed evidence allows safe release; claimed/uncertain requests remain protected; no repeated order/intent dispatch. Worker termination and precise claim races belong to A07, not uncontrolled staging process kills. | NOT RUN |
| R21 | Ticket 45 discounted and globally rounded sales returned fully and in partitions, including tiny-line and zero-value adjustment cases. | Every eligible return is usable; total refunds equal the original collected entitlement, with no negative capacity, extra cent or stranded remainder; native quantities/tax/accounting agree. Exact larger-value regressions use mocked fixtures. | October 12 fractional zero-return Paid and remaining-cent allocation/submission/pending reservation PASS within scope; provider finality/native remainder completion pending. Discounted full refund native Paid/done, original discount/quantity and receipt PASS. Wider globally rounded/fractional partitions remain open. Historical observations: PARTIAL — October 12: DISCOUNT refund 18 verified/completed and funds received; financial-completion subcase CLOSED. Return 51 remains draft with waiting card tender; native settlement and wider rounding cases remain open. Earlier observations (historical): PARTIAL — discounted full-return submission observed on source #64: £0.01 base / zero tip, saved quantity −2 and 50% discount, draft total/tender −£0.01, one pending/processing refund. Completion, native settlement and wider cases open. Positive stored line subtotal magnitudes were subsequently explained as native refund representation; see .18.10 remediation. |
| R22 | Ticket 46 verified payment AND refund followed by rejected, timed-out or offline checkout restoration; repeat Check status, double click and reload. | Busy state clears, original verified references survive, checkout remains blocked until canonical totals restore, and the same sale/return completes once without a new charge/refund. Precise fault injection is mandatory in A09; only supported controlled browser interruption on staging. | NOT RUN |
| R23 | Tickets 42–43 lost-draft recovery and external association: multiple verified siblings, partial/pending sibling, session rollover, incompatible batch, two managers and tracked lots. | Only complete compatible evidence rebuilds/binds the original return; no invented cash/lot data, partial batch or duplicate financial/native effect. Destructive missing-draft and concurrency setup use disposable tests; staging uses genuine eligible fixtures. | NOT RUN |
| R24 | Close and reopen the new register/session after reconciliation; repeat ordinary checkout setup. | Unresolved or verified-but-unsettled exposure blocks closure; reconciled closure has correct cash/card/accounting totals; next session starts clean without losing previous campaign evidence. No force-closing protected sessions. | Restaurant reconciled close/reopen PASS with posted 0.02 move and fresh empty session; original retail closure remains blocked. Final reconciliation and safe session close/reopen remain open. Return 1019 owner acceptance does not waive real pending-refund or unsettled-native closure guards. Historical observations: PARTIAL — October 12: no unresolved provider refunds remain, but six native returns are drafts. Reconciliation and actual close/reopen remain open; no session closure was attempted. Earlier observations (historical): PARTIAL — closing summary observed: 16 orders / £0.21, Cash £0.05 and Revolut £0.16. Operator stopped before final Close Register as instructed. Closure guard/rejection NOT EXERCISED; dialog alone is not a failure. Discard and preserve open session with pending refunds. Actual reconciled closure/reopen remain deferred. |

For R10's exact rounding regression, retain a **mocked/disposable** untaxed
1,234-minor-unit fixture: return 0.25 then 0.75, expecting 309 then 925.
Also cover reversed/multiple partitions and mixed tenders in automated tests.
This example does not authorize a £12.34 live charge. Any device amount must
use the separately agreed budget and supported fractional-quantity fixture.

For R14, the existing externally detected refund linked to sale 000018 is a
possible inspection fixture because the operator reported no products need
returning. Reconfirm its current state and manager intent before any native
correction; never use it to fabricate a product return or send another refund.
R13 requires a separate fixture with genuinely confirmed returned products.

### Operator execution order and result ledger

Run R01 first, then ordinary retail/split checkout (R02–R03), authorized pricing
and tips (R19/R05), supported failure/recovery cases (R06–R08/R20/R22), native
returns (R09–R11/R21), external dispositions/association (R12–R15/R23), and
Restaurant in its configured phase (R04). Printing/usability (R16–R17) span
these phases. Reconcile after each financial case and finish with R18/R24.
The live amount/cumulative budget must be agreed before starting R02 or any
other money-moving case.

For each row, expand every listed subcase into the ledger before execution:

| Campaign / case / subcase | Candidate / deployed revision / environment | Register / session / restricted fixture alias | Expected money requests and native effects | Observed result / amounts / references | Evidence / owner / next action |
| --- | --- | --- | --- | --- | --- |
| 2026-10-07 campaign / current checkpoint 2026-10-09 | .18.9 / PR #70; exact source in release provenance | Dedicated register; FULL, PRODUCT and TIP aliases in handoff | Existing-refund recovery: zero new refund dispatch | Three refunds pending; PRODUCT/TIP concurrent submission passes only | Operator + read-only backend evidence; complete recovery/finality and retain restricted mapping |
| 2026-10-07 campaign / R08 busy rejection, read-only observation and explicit Resume after release | .18.9; read-only baseline 2026-10-09 10:27:08 UTC | Existing register; distinct £0.01 orders A/B; Administrator and authorized test cashier confirmed | A: one order/intent pair then cancellation. B busy rejection and Check status: zero financial dispatch; explicit Resume after A cancellation: one order/intent pair then cancellation. Neither order paid; no card presented; existing refunds preserved | PARTIAL — busy rejection/retained terminal observed; backend 60 operations (+2), 137 claims (+6), 13 refunds unchanged at 10:31 UTC. Both operations cancelled; one order/intent/cancel claim each, cancellation claim responses unresolved. B created after A cancellation; draft native orders, stored lines waiting | Both cancelled UI states observed; A required refresh without Check status available: automatic UI recovery FAIL, refresh recovery PASS. 10:34 UTC counts/max IDs unchanged. Physical idle confirmation, explicit earlier busy Check status observation and A interruption/uncertain cancel-response explanation open. Simultaneous-start and revocation subcases remain separate |

Next R08 subcase executed on .18.9: manual near-simultaneous starts from two
existing authorized browser sessions, using distinct new £0.01 orders and no
card. Read-only baseline **2026-10-09 10:35:50 UTC**: 60 payment operations,
137 dispatch claims, 13 refunds, zero nonfinal payment operations. Expected:
one accepted terminal request, one busy rejection; two sequential Check status
observations on the rejected line create no request; cancel the accepted request
once, keep both orders unpaid. No precise race/fault injection on staging.
Result **PASS for this manual subcase**: operator confirms A clicked slightly first and owned the
terminal; screenshots show A waiting then cancelled, B busy-rejected throughout.
At 10:38:29 UTC, SQL confirms 61 operations (+1), 140 dispatch claims (+3),
13 refunds unchanged. Only A has an attempt, final cancelled/retry-safe with
released terminal; B has zero attempts and both native orders are draft. A has
one successful order/intent pair and one cancellation claim with unresolved
response outcome. Manual contention/non-duplication/cancellation subchecks PASS;
operator explicitly confirms two B status-check clicks, A cancellation displayed
without refreshing this time, and physical terminal idle. Exact simultaneity is not claimed. The earlier A automatic cancellation-display FAIL remains open;
owner deferred its investigation, now explicitly noted on ticket 12.

R01/R08 access-revocation subcase **PARTIAL** (results below): keep the test cashier's
existing POS browser logged in; prepare a new £0.01 draft without tender,
remove only its explicit register grant as Administrator, then attempt Revolut
start from the stale browser. Expected actionable register-grant denial before
provider dispatch. Restore the same grant regardless of denial-message result;
use Check status on B's earlier busy-rejected order to verify restored read
access without Resume/new dispatch. Preserve Administrator grant, native roles,
all orders/refunds and the open session. Read-only baseline **2026-10-09
10:40:26 UTC**: Administrator and the existing test cashier are granted; 61
payment operations, 140 dispatch claims, 13 refunds, zero nonfinal payments.
Expected ledger delta zero throughout. Operator screenshot shows cashier grant
removed and native pos.payment create-access denied under Revolut cart needs
correction, not the intended register-grant message: feedback **FAIL**, exact
register-check path not isolated. Second screenshot shows restored grant and
the same correction status. Check status did not relaunch payment, as expected;
restored server-read/start authority is not proved by this unchanged screen.
At **10:43:25 UTC**, SQL confirms both original grants restored, counts/max IDs
unchanged (61/140/13), zero nonfinal payment operations: grant restoration and
zero new recorded dispatch **PASS**. Physical terminal inactivity not explicitly
confirmed. No card presentation or live exposure was requested during revocation.

R02 / restored-access / PR #69 manual subcase **PASS** (exact UI delay unmeasured): a fresh £0.01
no-tip card sale by the authorized test cashier on .18.9 while FULL/PRODUCT/TIP
refunds remain pending. Use one new order and one Revolut tender; leave prior
rejected/cancelled drafts untouched. Expected one operation, one order/intent
pair, authoritative successful underlying payment, automatic native receipt,
post-refresh Paid order/receipt, and unchanged refund count/references. Observe
terminal £0.01/GBP, no tip, terminal approval and time to receipt. Read-only
baseline **2026-10-09 10:45:40 UTC**: grants restored, 61 operations, 140 dispatch
claims, 13 refunds, no nonfinal payments, three active refunds pending/processing.
Existing gross charge approval covers £0.01; spend £0.10 / remaining £0.15 before
this test, anticipated £0.11 / £0.14 only on confirmed success (uncertain charges
remain counted pending reconciliation). No second start after an ambiguous result.

R02 outcome at **10:47:56 UTC**: one new verified/captured GBP £0.01 payment,
zero tip, matching native Paid order/tender and receipt reference, correct test
cashier. Exactly one successful order/intent pair; counts now 62/142/13. All
three refunds remain pending/processing with unchanged references. Restored
cashier payment access and new sale while refunds pending **PASS**. Successful
receipt, Paid Orders and reopened preview observed; long-reference clipping
persists. Operator explicitly confirms terminal £0.01 GBP/approval, automatic
checkout and actual browser refresh before reopening the receipt: current R02
flow PASS. Exact approval-to-receipt delay was not supplied and is unmeasured. Confirmed spend £0.11, remaining £0.14.

R03 current-release Cash/card split subcase **PASS** (observed results below): test cashier,
fresh two-unit £0.02 test-product order; allocate £0.01 Cash first, capture the
unpaid intermediate screen with £0.01 remaining and idle terminal, then pay
only the £0.01 remainder by Revolut with no tip. Expect one operation and one
successful order/intent pair for GBP 1 minor unit, automatic checkout only after
verified full settlement, Paid native order with distinct £0.01 Cash / £0.01
Revolut tenders, matching receipt and post-refresh persistence. Preserve this
sale as the fresh mixed-tender-return fixture for a later R10 test; no refund is
requested now. Read-only baseline **2026-10-09 10:51:09 UTC**: 62 operations,
142 dispatch claims, 13 refunds, zero nonfinal payments; automatic validation
on, retail mode, cash rounding off. Card budget £0.14 before test, anticipated
£0.13 after verified £0.01 charge; Cash penny tracked separately. Two-card
amount-entry blocker and earlier UI/permission failures remain open.

R03 result at **10:53:26 UTC**: intermediate unpaid and waiting-for-card UI
captured; final receipts show correct £0.02 split. SQL confirms quantity 2,
£0.01 Cash and £0.01 Revolut, native Paid, card operation verified/captured
GBP 1 minor unit, zero tip, matching receipt reference, one successful
order/intent pair. Ledger 63/144/13; three existing refunds still pending.
Intermediate-unpaid and backend allocation/settlement PASS. Operator explicitly
confirms terminal idle during Cash-only stage, terminal £0.01 GBP, automatic
checkout and actual browser refresh before reopened receipt: split subcase PASS.
R03 remains partial due to the separate two-card UI blocker.
Spend now £0.12 / remaining £0.13; preserve MIXED for later mixed-tender return.

R19 **per-line discount**, **PASS** (other R19 subcases remain open): authorized non-admin cashier,
new two-unit line at £0.01 each, discount 50%, resulting £0.01 total; one no-tip
Revolut payment. Capture discounted basket, terminal amount/approval, automatic
checkout and receipt; backend verifies persisted 50% discount, quantity/unit
price, discounted canonical authorization, captured 1 minor unit and native
settlement once. Do not repeat refresh/reprint tests already passed. Verified
settings: manual_discount=true, restrict_price_control=false, cash_rounding=false,
auto_validate_terminal_payment=true. Baseline **2026-10-09 10:55:32 UTC**:
63 operations / 144 dispatch claims / 13 refunds; no active payment. Budget
£0.13 before / £0.12 after confirmed success. Preserve sale as DISCOUNT for a
later R21 return; mixed-tender return reuses MIXED. Owner requests no redundant
passed-case reruns; later tests must target distinct remaining requirements.

R19 result **10:57:34 UTC**: receipt plus SQL verify two £0.01 units,
50% discount, canonical base/payable £0.01, captured £0.01 GBP, tip 0,
native Paid and one Revolut tender. Receipt reference matches; one successful
order/intent pair; counts 64/146/13. Operator explicitly confirms terminal £0.01/approval and automatic completion:
line-discount subcase PASS; no repeat
basket screenshot required. Budget now £0.13 spent / £0.12 remaining. Preserve
DISCOUNT; other R19 subcases and discounted-return R21 remain open.

Use PASS, FAIL, BLOCKED or NOT REPRODUCIBLE per subcase; a mandatory gap remains
open. Automated proof and physical observations are separate columns/entries,
not interchangeable passes. No runtime change may silently retain all previous
campaign results: record the new candidate and rerun affected cases.

## 4. Check the release and public distribution

- [ ] Test fresh installation from the packaged addon using public instructions and a clean environment, without private checkout paths, undocumented infrastructure or credentials bundled in the artifact. Verify upgrade prerequisites and supported Odoo/Restaurant packaging against the final candidate.
- [ ] Verify complete operator/admin guidance: configuration and grants, server-only secrets/rotation, payment recovery, both refund origins/dispositions, printing, reconciliation, upgrades and troubleshooting. Reflect actual observations and compatibility limits.
- [ ] Verify the chosen license text, addon metadata and applicable third-party attribution/notices are included and consistent in the intended public distribution. Record missing files/decisions; do not silently select or change the license.
- [ ] Resolve [ticket 33](../tickets/needs-info/33-investigate-release-evidence-disclosure.md)'s private preservation, accountable custodian, mapping and recovery requirements before publishing evidence. Keep the old test history; use consistent aliases in public copies and retain authoritative originals privately.
- [ ] Review the **actual intended public artifact, documentation, screenshots, logs and selected Git history** for secrets, card/customer data and original transaction/device/local identifiers. Record the reviewed publication route; current-file cleanup alone does not establish clean history. Any required publication/history operation needs its own approved plan.
- [ ] Record final test-money disposition, unresolved issues/limitations, reviewed revision/artifact and owner go/no-go decision. Ticket 12 closes only when mandatory release and publication gaps are resolved; publication itself is a separate authorized action.

## 5. Record results without overwriting earlier evidence

Update the current handoff and this matrix in place when execution resumes;
keep revision/test details in release provenance. For every ID/subcase record: revision/environment, operator,
authorization, amount/currency, UTC observations, expected versus actual outcome,
stable restricted evidence links/aliases, intended versus actual mutation count,
native order/return/stock/accounting result, and PASS/FAIL/BLOCKED/NOT REPRODUCIBLE.
Pending refunds remain pending, with an owner and next reconciliation step.
Never declare a delayed or unavailable check passed.

Keep originals and authoritative mappings in the approved private archive;
public copies must follow ticket 33. Earlier local temporary screenshot/log paths
are not proof of durable preservation. New test outcomes must remain traceable
without copying secrets or raw customer/card data into this checklist.

**Automated baseline completed on 2026-10-08; live acceptance remains incomplete.**
Later runtime fixes have the focused and artifact checks recorded in release
provenance; final combined coverage still needs review. The handoff and this
table contain the current operator observations. PARTIAL or PENDING does not mean the entire scenario
passed. Publication, historical redaction and closure of other tickets are
not claimed.


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


## Checkpoint — stop routine manual repeats, 2026-10-09

Owner challenged repeated testing. The proposed revoked-register test is a
RETEST of an earlier feedback failure, not new coverage. Do not execute it now;
no grants were changed by the agent (preflight still showed Administrator and
test gary). Stop assigning routine repetitions while the owner addresses fixes.
Ticket 12 remains open; do not present the entire acceptance matrix as passed.

Remaining work is explicitly separated:

- Current/recent failures or usability follow-ups: historical register Paid
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
  appropriately authorized accountant; historical native invoice PDF needs an
  existing invoiced POS fixture (read-only check found none). Keep both open.
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

# Ticket 83 — preserved Community refund completion

Base: `feat/v18_rev` at `4b8b5cd`. Integration target: `feat/v18_rev`.
Task branch: `codex/83-deferred-community-refund`.

This is the original Community acceptance obligation. Use the preserved local
acceptance database and frozen Community `18.0.1.0.4` addon, rather than an
Enterprise trial or a newly created test refund. The [ticket](../tickets/closed/83-finish-deferred-v18-refund-return-session.md)
closed on 2026-11-02 after verified provider and native completion.

## Verified completion — 2026-11-02

The owner separately authorised restoration of the original credential and a
GET-only status check, then completion of the existing native return/session.
The original approved credential source was recovered from the earlier private
acceptance chat and restored only to its server-side temporary mount. All 162
deployed addon files matched frozen reviewed `334c8a8` / `18.0.1.0.4`.
A fresh private database dump and filestore archive were saved before the check.

Exactly one provider GET checked the original refund. The existing server
reconciliation method authenticated its identity, original sale, GBP amount and
refund type, then persisted **verified / completed**. The process rejected all
non-GET requests; a blocked POST probe verified that restriction before the GET.
The original refund's other split leg was already verified completed.

Native **Recover return** reopened the same saved return and original session.
Both tenders were done, GBP -0.01 each, with distinct canonical references and
zero due. Normal **Validate** produced the original GBP -0.02 return's receipt.
An independent database check confirmed the same return was paid with both
references matching the original refund operations. No direct record repair,
replacement return or financial replay was used.

Native **Close Register** showed two orders netting to GBP 0.00, zero Cash and
Revolut totals/counts, and zero differences. Closure completed on the same
session. Read-only SQL independently confirmed the return is now done, the
session is closed with a closing time, and its linked accounting move is posted:
**GBP 0.02 debit = GBP 0.02 credit**, across three accounting lines.

Before/after comparisons preserved all original collection, refund, dispatch,
order, order-line and tender record identities. Original financial amounts and
provider references match; native tenders gained their canonical verified
references through recovery. Counts remain 14 collection operations, eight
refund operations and 27 dispatch claims. Native closure created its usual
empty successor session in Opening Control, which was left unstarted with no
orders or payments. The original return stayed in its original closed session.

The normal worker's Merchant block and disabled cron were verified after the
operation. The worker was returned to its initial stopped state; the temporary
production credential and temporary browser operator-vault entry were removed,
and the isolated browser was closed. The remote credential source was unchanged.
No monitor, new collection, new refund, addon update or production deployment
was performed. No financial/native condition remains unresolved for ticket 83.

Restricted evidence remains alongside the original acceptance profile:
`ticket83-completion-20261102.json` contains exact mappings, before/after snapshot
paths and hashes, provider proof and backup locators. The private provider proof
records the one GET and verified result. Screenshots retain the recovered
return, native receipt and zero-difference closing preview. No live identities
or credentials are copied into this repository.

## Read-only checkpoint — 2026-11-02

The preserved private checkout and acceptance profile were located locally.
A fresh owner-only snapshot was taken using read-only SQL. All nine tables
exactly match the final 2026-10-26 snapshot, including every captured field:
sessions, orders, order lines, tenders, payment operations, refund operations,
dispatch claims, accounting moves and accounting move lines.

The original refund-to-return-to-session mapping was checked against that
checkpoint. Exact identities, snapshot paths and hashes are retained in the
custodian's private `ticket83-continuation-20261102.json` record, alongside the
original acceptance evidence; they are not copied into this repository.

| Item | Current local observation | What remains unverified |
| --- | --- | --- |
| Last GBP 0.01 refund | Pending; last recorded provider state processing; base GBP 0.01, tip zero | Current provider finality |
| Original split return | Draft, total GBP -0.02, recorded tender total GBP -0.02 | Both refund legs verified and native validation complete |
| Original session | Open, no closing time or accounting move | Native closure and balanced posting |
| Original Odoo worker | Stopped | Startup after credential restoration |
| Production credential mount | Temporary source file missing | Authorised restoration from the original approved source |
| Saved worker configuration | Merchant HTTP blocked; cron threads zero | Runtime enforcement when a worker is started |

Recorded tenders do not establish refund success. No provider request, worker
startup, credential restoration, refund submission, native validation or
session closure was performed for this checkpoint.

## Prepared continuation (executed under the authorisations above)

1. Obtain the owner's separate authorisation for restoring the original
   server-side credential and checking this existing refund through provider
   GETs only. Identify the original approved credential source privately before
   restoration; the recovered handoff does not identify that source precisely.
   Keep credentials out of chat, repository files and browser payloads.
2. Preserve a fresh database/filestore backup and verify the frozen addon and
   exact original record mapping against the private checkpoint. Do not upgrade
   or replace the acceptance database. Keep the normal worker's Merchant block
   enabled and cron disabled. Review any historical helper before use: the saved
   early refund-status helper targets older operations, not the final pending
   refund.
3. In a narrowly scoped process, reject financial POSTs and all provider methods
   other than GET. Check only the mapped existing refund in its original
   Merchant account. Save a sanitised outcome and restricted identity/amount
   proof. Use the existing refund reconciliation path to verify and persist
   success; a rollback-only observation does not persist reconciliation.
4. Branch on the verified result. Processing, unknown, unavailable access or
   inconsistent references leave the refund, return and session pending.
   A failed refund requires a recorded failure and owner disposition; it does
   not authorise another refund. Only verified success permits native recovery.
5. After authorisation for native completion and verified success, use
   **Point of Sale → Revolut Refunds → Recover return** on the original
   operation. Confirm that the same saved return and session reopen, both
   existing refund tenders retain their distinct original references, and their
   amounts match the split return. Use normal **Validate** once all tenders are
   verified. If the expected original return/session is unavailable, stop for
   review rather than creating a replacement. Do not press **Refund**, **Send**
   or **Force done**.
6. Review the same session's orders and tender totals, then close it through
   native controls under the authorised scope. Verify the session is closed,
   its linked accounting move is posted, debits equal credits, and its amounts
   reconcile to the original sales and returns. Preserve the original references
   and recorded counts; unexplained differences require review, not forced
   balancing or direct record edits.
7. Compare before/after evidence: no new collection, refund operation or dispatch
   claim; same original return/session and original amounts/references. Record
   the provider result, native return state, posted accounting totals and any
   unresolved condition privately. Verify the normal worker's Merchant block
   and disabled cron after the bounded work. Publish only a sanitised result
   and evidence locator, then update the ticket and index when closure is earned.

## Verification limits

The initial read-only snapshot alone did not verify provider status or native
completion. The subsequent authorised provider observation, native browser
actions and independent SQL checks above exercised those actual behaviours.
This is bounded completion of the original obligation, not a repeat of the
broader physical acceptance matrix. No addon code changed, so typechecking,
TDD and the full addon test suite were not run for this documentation-only
change. All 54 relative Markdown links in the affected documents, the five
completed acceptance criteria, ticket relocation and retained tracker marker
passed checks; `git diff --check` passed.

## Independent review

Standards: **0 findings**. The Community branch scope, private identity boundary,
separate authorisations and tracker closure follow repository guidance.

Spec: **0 findings**. All five acceptance criteria are supported; the reviewer
also confirmed the private before/after and provider-proof hashes match the
completion manifest. No replacement refund, collection or replay was introduced.

Total: **0 Standards / 0 Spec findings**; neither axis has an unresolved issue.

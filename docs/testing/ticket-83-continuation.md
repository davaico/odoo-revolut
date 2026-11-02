# Ticket 83 — preserved Community refund continuation

Base: `feat/v18_rev` at `4b8b5cd`. Integration target: `feat/v18_rev`.
Task branch: `codex/83-deferred-community-refund`.

This is the original Community acceptance obligation. Use the preserved local
acceptance database and frozen Community `18.0.1.0.4` addon, rather than an
Enterprise trial or a newly created test refund. The [ticket](../tickets/ready-for-human/83-finish-deferred-v18-refund-return-session.md)
stays open until verified completion or an explicit owner disposition.

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

## Guided continuation

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

The read-only snapshot comparison exercises preservation of the actual records.
It does not verify current provider status or native completion. No addon code
changed, so typechecking, TDD and the addon test suite were not run for this
documentation checkpoint. Existing synthetic tests cannot substitute for the
remaining provider and native-accounting evidence.

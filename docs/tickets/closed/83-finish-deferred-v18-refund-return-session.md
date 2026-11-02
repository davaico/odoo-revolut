# 83 — Finish the deferred Odoo 18 refund, return and session

**State:** closed

**Closed:** 2026-11-02

**Triage:** ready-for-human

**Work branch:** `feat/v18_rev` for documentation or any separately scoped fix.
This is an existing Community acceptance-record follow-up.

**Parent:** [63 — Perform controlled Odoo 18 terminal acceptance](../closed/63-v18-terminal-acceptance.md)

**Blocked by:** None among implementation tickets. This obligation was accepted
as non-blocking for the accepted Community release.

**External blockers:** Resolved. The preserved acceptance records were located,
the original refund was verified completed, and the existing return/session
were completed under separate owner authorisations on 2026-11-02.

## What to finish

Preserve the remaining original small refund, native return and session until
the provider's final outcome is verified. Once a successful refund is established,
resume that same return and close/post its existing session with balanced native
accounting. Keep transaction identities in restricted evidence.

The owner accepted this delay as a deferred, non-blocking obligation on
2026-10-26. Moving it out of the completed acceptance campaign does not mark the
financial/native work complete or grant permission for a new live operation.

## Acceptance criteria

- [x] The authorised operator identifies the original refund, return and session
  from restricted acceptance evidence, without copying live identifiers here.
- [x] Verify the provider's final outcome using the applicable existing access
  and authorisation. Keep processing/unknown outcomes pending; if the refund
  failed, record that failure and the required disposition rather than forcing
  native completion.
- [x] After verified success, reconcile the original operation and finish its
  existing return without issuing another refund or collecting more money.
- [x] Close/post the same session and verify balanced native accounting with
  original references and amounts preserved.
- [x] Record a sanitised result and evidence location, including any unresolved
  condition; close this ticket only when the obligation is completed or an
  explicit owner disposition supersedes it.

## Boundaries and evidence

No replacement refund, financial replay, forced completion, monitor or live
operation is authorised by this ticket's creation. The pending condition was
retained during the 2026-10-30 tracker review; no terminal/API call was made.
See the [acceptance handoff](../../testing/ticket-63-handoff.md) and the
[original owner disposition](../closed/63-v18-terminal-acceptance.md#owner-release-disposition--2026-10-26).

## Comments

### 2026-11-02 — Locate preserved records and prepare continuation

The original private checkout, acceptance profile and record mapping were
located. A read-only snapshot exactly matches the final 2026-10-26 checkpoint
across all nine captured financial/native tables. The original refund is still
locally pending/processing, its return is draft and its session remains open;
this is not a fresh provider observation.

The Odoo worker is stopped and its temporary production credential source file
is missing. Restoring authorised provider access and checking finality remain
necessary before native completion. No provider call or original-record mutation
was performed. Keep this ticket open and `ready-for-human`.

The [guided continuation and verification limits](../../testing/ticket-83-continuation.md)
record the next steps. Exact mappings, snapshot locations and hashes stay in
the custodian's private `ticket83-continuation-20261102.json` evidence record.

### 2026-11-02 — Complete the original obligation

The owner separately authorised credential restoration and a GET-only provider
check, then native completion of the existing return/session. One exact provider
GET established Completed for the final GBP 0.01 refund; the existing server
reconciliation method persisted verified success. Non-GET requests were blocked.

Normal **Recover return → Validate** completed the original GBP -0.02 split
return with its two verified GBP -0.01 tenders and distinct canonical references.
Normal **Close Register** closed the same session with zero counted differences.
Its linked accounting move is posted and balanced: GBP 0.02 debit and GBP 0.02
credit. Read-only database checks independently confirmed these native results.

Original collection/refund/dispatch/order/line/tender record identities and
financial amounts were preserved; no new refund or collection was issued.
Odoo created an empty successor session in Opening Control during native close;
it was left unstarted. The normal worker's Merchant HTTP block and disabled
cron were verified, then the worker was stopped again and the temporary
production credential removed. No monitor was created.

The [completion evidence](../../testing/ticket-83-continuation.md) records scope,
verification and private evidence locators. No refund/return/session condition
remains unresolved for this ticket. No addon change or deployment was needed.

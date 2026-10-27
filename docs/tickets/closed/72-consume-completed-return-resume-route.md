# 72 — Avoid a stale return-recovery warning on POS reload

**Work branch:** `codex/72-v18-return-resume` from `feat/v18_rev` at `6fd1757`.

**State:** closed

**Triage:** ready-for-agent

**Base and integration target:** latest sanitized `feat/v18_rev`; preserve the
original private acceptance checkout and never merge its old ancestry.

## Parent and context

Found during ticket 63's controlled Odoo 18 acceptance, after the ticket-70
replacement. Deployed source `2aeef4ba326b67f4c9361b6c8a024e71a167bcd3`, addon
`18.0.1.0.2`, Odoo `18.0.20261015`; addon contents match reviewed `a868add`.
This report contains no live operation identities or screenshots.

## Observed sequence

1. Recover a verified refund's existing draft using the manager Recover return
   action. POS opens with a `revolut_return_uuid` URL parameter.
2. Complete that same return through normal validation and reach its receipt.
3. Continue working on another unpaid sale in the same POS tab. Remove a
   safely cancelled tender as part of the separate ticket-68 reload check.
4. Refresh the POS tab. It opens ProductScreen and displays **Revolut return
   unavailable — Reopen the refund worklist and review its linked return and
   session before continuing.**
5. Dismiss the popup and reopen the unrelated sale. Its single unsent tender
   is present; no duplicate row or new financial request was observed.

The operator explicitly confirmed popup-after-refresh, followed by dismissal
and reopening the unrelated sale. Read-only browser inspection finds the old
resume parameter still present. Read-only database verification confirms that
its target is the already-paid mixed return in the still-open session. Both
completed refunds/returns remain intact. The separately removed cancelled
tender has a persisted retired disposition and its original operation history
is preserved. No financial operation/dispatch was added.

## Source evidence and limits

`static/src/app/revolut_return_resume.js` reads the query parameter on startup.
Its handled flag is in memory. A non-draft target triggers the observed dialog,
and this module does not consume the query parameter. These facts are
consistent with the observed completed-target reload warning; this is not yet
a portable automated reproduction or a reviewed fix. Do not claim data loss,
duplicate collection, failure of ticket 68, or Odoo 19 runtime verification.

## Expected behavior and investigation gate

- A completed return's consumed recovery navigation must not produce a
  misleading missing/unavailable warning during later ordinary POS reloads.
- Preserve meaningful errors for genuinely absent, wrong-session or otherwise
  invalid return targets; do not weaken refund verification or native guards.
- Preserve ordinary register parameters, unsent drafts and completed-return
  review/recovery navigation as appropriate.
- Before choosing a fix, reproduce using synthetic verified-refund/native
  records and a real browser reload, with provider HTTP forbidden. Verify that
  no collection/refund dispatch, extra tender or duplicate native effect occurs.
- Assess the maintained Odoo 19 path separately if the shared behavior applies.

The owner subsequently authorized fixing #72 and its final local retest, with
no additional money movement. Exact references and original screenshots remain in
the private ticket-63 evidence store. Published source/test changes must retain this sanitized scope.

## Resolution — 2026-10-23

Fixed in `fcb59c4` after the failing browser regression `da54b32`. Cleanup occurs
only after successful native synchronization of the matching completed return
in its own session. No financial/backend guards changed. Addon `18.0.1.0.3`.

Focused evidence: nine real native browser tests passed, 144 JavaScript checks
passed, no Standards/Spec review findings. Full and mixed completed-return
reloads pass; unfinished-return reload and invalid-link/login guards remain.
See [the focused verification record](../../testing/ticket-72-return-resume-reload.md).

The owner-authorized local update passed isolated restore/update rehearsal and
preserved every protected value across 68 rows in 17 financial/native/config
collections. All 162 deployed addon files match the frozen candidate. Final
original-instance browser smoke checks passed: two normal POS reloads, both
existing paid returns refreshed with their original tenders, no warning or new
financial/native effects. Merchant HTTP was blocked and remains blocked locally.
The original session and all original drafts remain open. Exact identities and
backup/snapshot artifacts stay in restricted acceptance records.

Exact recovery/validation/completion/reload was exercised with synthetic
records only; originals were reviewed, not financially revalidated. Ticket 63's
full physical/parity release gate and separate Odoo 19 ticket 71 remain open.

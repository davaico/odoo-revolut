# Ticket 63 — sanitized continuation handoff

Checkpoint: 2026-10-23. **Open / ready-for-human.** Base and integration target:
**feat/v18_rev**. Preserve the original private acceptance checkout and its data;
never merge its older ancestry. Read AGENTS.md and ADR 0002 before changes.

## Owner release disposition — 2026-10-26

The owner accepts the last GBP 0.01 refund's provider-processing delay and
defers its reconciliation, existing return completion and session posting.
This waiting item no longer blocks release preparation or release sign-off;
other release checks and approval remain separate. It is accepted outstanding
work, not a verified refund or completed native accounting result.

Keep the original refund, return and session pending until provider finality
is verified. Then resume the same return and close/post its session, checking
balanced accounting. No financial replay, forced completion, new collection,
monitor or live operation is authorized by this documentation disposition.
Earlier statements requiring this item to finish before sign-off are superseded.

## Latest checkpoint — 2026-10-26

See [refund completion and fix evidence](ticket-63-refund-completion-20261026.md).
All five prior pending refunds are provider Completed / locally verified.
Two native returns exposed a reference-loss recovery bug; ticket 73 is fixed,
reviewed and retested locally on addon **18.0.1.0.4**, immutable **334c8a8**.
All four returns from the fully refunded Restaurant sessions are now finalized;
both sessions are closed with balanced posted accounting and zero net card total.

The previously unsubmitted final GBP 0.01 split-leg refund was sent once and is
still processing. Its original return and session remain open. Reconcile that
same refund, finish the same return and close/post its session after finality.
Do not replay it, create another return or force completion. No new collection
occurred. Merchant HTTP is blocked and verified; cron is disabled. No monitor.

The fix is committed locally but not pushed. Earlier checkpoints below are
historical; they do not reopen completed tests or override this remaining scope.

## Latest same-day checkpoint (supersedes older operating boundaries below)

See [the additional acceptance results](ticket-63-finish-20261023.md). The owner
subsequently authorized disposal of the three original test drafts, original
register close/reopen and two separate GBP 0.05 live budgets. Original closure,
posting and reopening passed. Dine-in, timed Takeout, nonzero terminal tips,
split tip balance and pending-attempt browser reload passed. The first budget
used GBP 0.05; the second used GBP 0.03, leaving GBP 0.02 unused. No new payment
is needed for the completed checks. Physical Odoo printing is not applicable;
the owner has no printer. Native PDFs were generated and visually inspected.

Five newly submitted refunds remain unresolved across the two batches. Their
native returns remain drafts. One additional GBP 0.01 refund against the first
batch's other split source remains unsubmitted, blocked until the same return's
existing refund is reconciled. Do not replay any existing refund, force a return
paid or infer provider completion from a wait timeout. The owner deferred
waiting/monitoring; no automation was created. Merchant HTTP is again blocked
and the guard verification passed; cron stays disabled.

Isolated native document/restart checks, 76 selected tests and actual separate
cashier/manager access checks passed. Full detail and limitations are in the
linked report. The [reload investigation](ticket-67-busy-reload-disposition.md) dispositions
the strict immediate-Resume test assumption; only tests changed. The owner
selected recording distinct-card split and issuer-decline cases as untested
release limitations. No further card tests are planned. Broad release
acceptance remains open pending obligation disposition and native completion.

## Earlier checkpoint (historical)

The bounded Odoo 18 recovery campaign has passed. Both existing card refunds
are verified and their original native returns are now paid, with matching saved
receipts. The mixed return's approved manual Cash portion was completed; Cash
was fictional test bookkeeping, not a physical exchange. Do not recover or
validate those completed returns again as unfinished work.

The ticket-68 unsent-tender removal/repeated-reload check passed. Ticket 70's
existing-tender recovery is fixed and physically retested. Ticket 72's completed
return reload warning is fixed, independently reviewed and locally deployed as
**18.0.1.0.3**, frozen source **fcb59c4**. Its nine focused native browser tests and
144 JavaScript checks passed. Original normal-route reloads and saved paid-return
reviews passed without new provider attempts, dispatches, native records or
changed financial proof. Original register/drafts remain open and preserved.

Native accounting closure/posting/reopening also passed on a disposable populated
copy, including the fictional Cash difference. This did not close or cancel
anything in the original register. Refund duplicate/replay protection, access
and closing guards have bounded isolated evidence; original receipts/reprints
and X-report matching already passed. Do not repeat these as new manual batches.

See [ticket 72's focused verification](ticket-72-return-resume-reload.md) and the
[acceptance checklist](../tickets/ready-for-human/63-v18-terminal-acceptance.md).
Exact private operation references, screenshots, backups and authorizations stay
with the acceptance custodian; obtain them before touching protected records.

## Current continuation

The owner requested publication of #72 and resumption of necessary testing,
with no further money movement. The three reviewed #72 commits were pushed to
origin/feat/v18_rev through **4369c4d** and the remote tip was independently read
back. The local runtime remains the same frozen reviewed addon.

The resumed bounded batch PASSED all three existing regressions: lost native
paid-sync response, lost refund response followed by reload, and simultaneous
same-return refund dispatch. Two real browser tours retain original identities;
two racing refund RPCs create one operation and one mocked dispatch. All ran
against the frozen deployed addon in a fresh internal-only disposable database
with real Merchant HTTP blocked. No protected acceptance record participated.
The copy was removed. See [the focused results](ticket-63-final-no-money-recovery.md).

## Operating boundaries

Real Merchant requests remain blocked on the local acceptance worker, and cron
is disabled. Existing card collection/refund caps are fully consumed; refunds
do not replenish collection limits. New financial tests need fresh explicit
scope and budget. Do not press Send, initiate a new refund, use Force done,
repair live financial history, cancel original drafts or close the original
register under this handoff.

Today's bounded recovery evidence does not close the broad physical/parity
release gate or private parent ticket 50. Nonzero/split tips, Restaurant,
partial/tip-related refunds and remaining physical interruption cases remain
separate unpassed release scenarios. Odoo 19 ticket 71 is separate and open.
The older candidate's full-suite busy-reload failure remains retained privately;
later green candidates do not rewrite that historical result. No unattended
monitor or extra live financial scope is authorized.

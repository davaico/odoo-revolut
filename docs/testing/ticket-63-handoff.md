# Ticket 63 — sanitized continuation handoff

Checkpoint: 2026-10-23. **Open / ready-for-human.** Base and integration target:
**feat/v18_rev**. Preserve the original private acceptance checkout and its data;
never merge its older ancestry. Read AGENTS.md and ADR 0002 before changes.

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

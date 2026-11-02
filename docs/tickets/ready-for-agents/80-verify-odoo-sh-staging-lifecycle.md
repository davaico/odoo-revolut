# 80 — Install and verify the integration on Odoo.sh staging

**State:** claimed

**Triage:** ready-for-agent

**Work branch:** `codex/80-odoo-sh-staging`, based on
`staging/18-enterprise` at `fdfa74596f2445e0a54a1206cb28a052386cda01`.
Integrate back into `staging/18-enterprise`. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None locally.

**Completed prerequisite:** [78 — Make database copies safe](../closed/78-neutralize-revolut-database-copies.md).

**External blocker:** Observation of a running platform cron worker across restart.
Authenticated Odoo.sh access and usable builds are available. On 2026-11-02 the
owner clarified this environment is for deployment testing, not operational use.
Its recorded trial status is sufficient for this evaluation while the trial is
active; permanent Enterprise registration is not a prerequisite for this ticket.
Permanent live activation remains in ticket 82. Do not register a staging copy.

## What to build

Deliver a repeatable Enterprise/Odoo.sh staging installation and evidence that
the integration behaves correctly through worker restarts, scheduled recovery
and fresh database copies. Use the existing install/restart/reconciliation
fixtures where possible, and make only focused fixes needed for these hosted
behaviors. Record the exact candidate and hosted build used.

## Acceptance criteria

- [x] Verify and record project activation and database registration status for
  the owner's test-only evaluation, including trial limits. Permanent registration
  is deferred to live activation in ticket 82; never register a staging copy as
  another production database. Keep license material out of public evidence.
- [x] Install on staging and document repeatable setup after a rebuild, including
  the fact that production database copies replace staging-only configuration.
  Preserve existing native business data.
- [x] Exercise administrator/POS role boundaries and company/terminal isolation
  in the hosted setup using synthetic credentials and mocked provider traffic.
- [ ] Demonstrate credential availability to the required workers after restart
  and durable recovery of the same payment/refund attempts without duplicate
  dispatch. Do not rely on persistent custom background daemons.
- [x] Explicitly invoke or enable controlled payment/refund reconciliation jobs
  and verify their results. Cover delayed scheduling; do not assume one-minute
  cron execution or equate a green staging build with passed tests.
- [x] Rebuild/copy a controlled database and verify live-key removal, preserved
  financial history, production-request blocking and first-install-after-copy
  protection. No real Merchant API or terminal is contacted.
- [x] Provide the runbook for installation, restart, scheduled jobs and copies,
  plus exact evidence, failures and unresolved external gates. Redact credentials,
  private host details and financial references from public records.

## Verification evidence

See the [staging runbook](../../odoo-sh-staging.md) and
[exact evidence and failed runs](../../testing/ticket-80-odoo-sh-staging.md).
Build 40905864 on candidate `fdfa745` installed `.8`, passed 18 controlled
hosted sandbox tests and existing three-process payment recovery. A committed
partial refund was recovered through delayed job invocation and verified by a
fresh observer with zero-HTTP replay. Repeated native neutralization removed
synthetic live keys across two companies while retaining financial/native
history. Build 41044597 at the same candidate proved staging-only setup was
replaced, then passed populated-native first installation/preservation and the
unchanged first-install-after-neutralization guard fixture. The module remains
installed there; both addon jobs are inactive after mocked acceptance.

The HTTP restart succeeded after waking a worker. The platform cron restart
reported no running worker and aborted; explicit job invocation passed but is
not evidence of a running platform cron-worker restart. A later native scheduled
probe successfully resolved a synthetic Database credential four times, but a
bounded restart watcher still found no live cron worker. Production remains an
unregistered trial after an approved native validation attempt; the unaccepted
local change was rolled back. The owner's subsequent test-only clarification
makes permanent registration unnecessary for this evaluation. Keep this ticket
claimed/open for the remaining worker-restart criterion.
Ticket 79's UI/documentation changes are included in the candidate. Release
promotion and ticket 84 remain separate gates.

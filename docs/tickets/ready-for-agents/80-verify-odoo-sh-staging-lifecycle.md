# 80 — Install and verify the integration on Odoo.sh staging

**State:** open

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; integrate implementation there and validate the
candidate on `staging/18-enterprise`. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

**Blocked by:**
- [78 — Make database copies safe](78-neutralize-revolut-database-copies.md)

**External blockers:** Authenticated Odoo.sh access, a usable staging build and
the subscription/database registration information. Registration changes must
apply to the appropriate database, not automatically to a staging copy.

## What to build

Deliver a repeatable Enterprise/Odoo.sh staging installation and evidence that
the integration behaves correctly through worker restarts, scheduled recovery
and fresh database copies. Use the existing install/restart/reconciliation
fixtures where possible, and make only focused fixes needed for these hosted
behaviors. Record the exact candidate and hosted build used.

## Acceptance criteria

- [ ] Verify subscription and database registration status; complete the correct
  registration step where required without registering a staging copy as an
  additional production database. Keep license material out of public evidence.
- [ ] Install on staging and document repeatable setup after a rebuild, including
  the fact that production database copies replace staging-only configuration.
  Preserve existing native business data.
- [ ] Exercise administrator/POS role boundaries and company/terminal isolation
  in the hosted setup using synthetic credentials and mocked provider traffic.
- [ ] Demonstrate credential availability to the required workers after restart
  and durable recovery of the same payment/refund attempts without duplicate
  dispatch. Do not rely on persistent custom background daemons.
- [ ] Explicitly invoke or enable controlled payment/refund reconciliation jobs
  and verify their results. Cover delayed scheduling; do not assume one-minute
  cron execution or equate a green staging build with passed tests.
- [ ] Rebuild/copy a controlled database and verify live-key removal, preserved
  financial history, production-request blocking and first-install-after-copy
  protection. No real Merchant API or terminal is contacted.
- [ ] Provide the runbook for installation, restart, scheduled jobs and copies,
  plus exact evidence, failures and unresolved external gates. Redact credentials,
  private host details and financial references from public records.

## Verification evidence

Pending hosted work. Ticket 79 is not a prerequisite for these lifecycle
checks; the assembled release must include its UI/documentation changes later.

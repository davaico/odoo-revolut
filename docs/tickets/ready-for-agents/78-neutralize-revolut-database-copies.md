# 78 — Make database copies safe

**State:** open

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

**Blocked by:**
- [77 — Manage company credentials through Odoo](77-manage-company-revolut-credentials-in-odoo.md)

**Completed prerequisite:** [76 — Block real Revolut access on Odoo.sh test environments](../closed/76-block-live-revolut-on-odoo-sh-test-builds.md).

**External blockers:** None for local copy/neutralization fixtures. Actual
Odoo.sh copy verification belongs to ticket 80.

## What to build

Make copied databases safe to open and use for testing: clear live database
keys during Odoo neutralization and disable copied live-operation configuration,
while keeping historical transactions and uncertain attempts intact. Combine
this cleanup with the runtime guard so a copy stays safe even after key entry,
cron activation or installation of the addon after copying.

## Acceptance criteria

- [ ] Actual Odoo neutralization removes usable live database keys and disables
  copied live-operation configuration across all companies, without deleting
  reconciliation history, external references or pending-operation identity.
- [ ] Repeated neutralization is safe. ORM record-copy exclusions are not
  treated as a substitute for whole-database neutralization.
- [ ] With valid-looking environment keys or re-entered database keys, staging
  still rejects every production path, including privileged reconciliation and
  connection checks, before HTTP dispatch.
- [ ] A separate fixture installs the addon after the database was neutralized
  and proves the runtime guard works without prior addon cleanup execution.
- [ ] Copied pending payments/refunds remain explicitly uncertain or pending;
  cleanup cannot manufacture success, enable an unsafe retry or issue a
  replacement charge/refund.
- [ ] Use synthetic credentials and mocked HTTP at the existing public model
  boundaries after actual neutralization. Assert database results, visible
  restriction feedback and zero production dispatch.
- [ ] Documentation explains copy behavior, safe test configuration and the
  fact that re-entering a live key cannot enable production API access on staging.

## Verification evidence

Pending implementation. Record candidate identity, actual neutralization
execution and focused results, including first-install and repeat-copy cases.

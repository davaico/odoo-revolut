# 78 — Make database copies safe

**State:** closed

**Triage:** ready-for-agent

**Work branch:** `staging/18-enterprise`; base further task branches on its
latest reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](../ready-for-agents/75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None.

**Completed prerequisite:** [77 — Manage company credentials through Odoo](77-manage-company-revolut-credentials-in-odoo.md).

**Completed prerequisite:** [76 — Block real Revolut access on Odoo.sh test environments](76-block-live-revolut-on-odoo-sh-test-builds.md).

**External blockers:** None for local copy/neutralization fixtures. Actual
Odoo.sh copy verification belongs to ticket 80.

## What to build

Make copied databases safe to open and use for testing: clear live database
keys during Odoo neutralization and disable copied live-operation configuration,
while keeping historical transactions and uncertain attempts intact. Combine
this cleanup with the runtime guard so a copy stays safe even after key entry,
cron activation or installation of the addon after copying.

## Acceptance criteria

- [x] Actual Odoo neutralization removes usable live database keys and disables
  copied live-operation configuration across all companies, without deleting
  reconciliation history, external references or pending-operation identity.
- [x] Repeated neutralization is safe. ORM record-copy exclusions are not
  treated as a substitute for whole-database neutralization.
- [x] With valid-looking environment keys or re-entered database keys, staging
  still rejects every production path, including privileged reconciliation and
  connection checks, before HTTP dispatch.
- [x] A separate fixture installs the addon after the database was neutralized
  and proves the runtime guard works without prior addon cleanup execution.
- [x] Copied pending payments/refunds remain explicitly uncertain or pending;
  cleanup cannot manufacture success, enable an unsafe retry or issue a
  replacement charge/refund.
- [x] Use synthetic credentials and mocked HTTP at the existing public model
  boundaries after actual neutralization. Assert database results, visible
  restriction feedback and zero production dispatch.
- [x] Documentation explains copy behavior, safe test configuration and the
  fact that re-entering a live key cannot enable production API access on staging.

## Verification evidence

Branch migration, 2026-11-02: this completed implementation and its evidence
are now maintained on `staging/18-enterprise`. References to the former
`feat/v18_rev` base/integration below describe historical work only.

Implemented in `18.0.1.0.7`: application commit `7063c3f`, final test lifecycle
correction `bf97e8d`, based on `feat/v18_rev` at `f1bb895` and integrated back
there. No push to `18.0` or hosted deployment.

Actual whole-database neutralization passed across two companies and both
credential sources, including repeat execution and exact financial-history
preservation. Public payment/refund recovery, privileged reconciliation,
connection checks and reactivated cron cannot dispatch live HTTP. The separate
CLI fixture neutralizes native Odoo before the addon exists, then installs it
and proves both valid-looking key sources are blocked while sandbox works.

Verification: 3 focused cases passed on update and fresh installation; 45
payment regression cases passed after correcting post-install test scheduling;
814 full-addon cases completed with zero failures/errors, one optional `pos_hr`
skip and container exit 0;
146 JavaScript checks and 75 host checks passed (three PDF dependency skips).
Independent Standards and Spec reviews each found zero actionable issues.
See [the commands, candidate identity and evidence](../../testing/ticket-78-database-neutralization.md).
Actual Odoo.sh Enterprise copy/lifecycle verification remains ticket 80.

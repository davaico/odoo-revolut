# 10 — Install and upgrade a reviewed revision on staging

**Work branch:** `codex/10-staging-install-upgrade`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-human (at closure)

## What to build

An operator deploys an identified reviewed addon revision to the existing staging environment and verifies a fresh installation or safe upgrade.

## Acceptance criteria

- [x] Provide local deployment tooling; no GitHub deployment or provisioning changes. Source remains in this repository and is never edited directly on the VM.
- [x] Deploy an identified clean revision into a customer-specific release directory, preserving the existing addons_path and reporting the deployed revision.
- [x] Preflight active or uncertain financial operations and abort an unsafe upgrade. Quiesce checkout/dispatch so no new operation races the final check; later refund operations must participate in the same guard.
- [x] Back up the database and relevant deployment configuration; stop Odoo for installation/upgrade, use stop-after-init, no-http and workers=0, and restart only after a successful update. Report update or health-check failures clearly.
- [x] Document recovery that reconciles external financial activity before any database restoration. Never automatically restore stale payment state over newer provider activity.
- [x] Exercise tooling with mocked command failures and disposable install/upgrade checks, then perform an operator-controlled staging smoke check without terminal charges. Verify existing cash POS still works.
- [x] Document prerequisites, exact commands, secret configuration, revision identification and operator recovery steps. Leave infrastructure ownership in odoo-hosting.

## Verification evidence

- Local deployment tests cover dirty and unreviewed revisions, financial
  blockers, the post-stop race check, install and upgrade commands, immutable
  releases, backup/update/health failures, locking, cleanup, and revision
  reporting. On 2026-09-25, all 18 tests passed with 82% branch coverage across
  the two deployment scripts (81% for the remote helper).
- The shared financial-operation guard is covered in the Odoo addon suite.
- The disposable Odoo environment is the install/upgrade verification target:
  `./scripts/test-addon --verify-install-upgrade`. It passed on 2026-09-23,
  including fresh installation, the full addon suite, module upgrade, and
  retail and Restaurant POS startup checks.
- Staging install and upgrade evidence, 2026-09-25: final reviewed revision
  `b96aad6b226684ad479708cc877c901a87570ae7` was deployed from the immutable
  release at
  `/opt/odoo-releases/revolut/staging/b96aad6b226684ad479708cc877c901a87570ae7/pos_revolut`.
  The deployment configuration backup is
  `/var/backups/odoo-revolut-deploy/20260925T081740Z-b96aad6b2266`. Odoo was
  active, the HTTP login endpoint was healthy, the module state was `installed`,
  and recent Odoo logs contained no error, critical, or traceback entries. An
  initial one-shot HTTP probe reported a false failure during normal startup;
  the final reviewed deployer passed with bounded connection-refused retries.
- Operator-controlled cash smoke check passed on 2026-09-25. Operator:
  `Administrator`. UTC time: `2026-09-25 09:10:01`. Cash order reference:
  `261-1-000002`. The order was paid for `11.50 EUR` using `Cash`, the receipt
  showed payment successful, and the matching server record was in `paid`
  state. No Revolut payment method was selected and no terminal or Merchant API
  charge was initiated. The pre-existing draft refund `260-1-000001` remained
  separate from the smoke-test order.

## Blocked by

- 03 — Complete one verified Revolut terminal payment (closed)

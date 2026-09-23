# 10 — Install and upgrade a reviewed revision on staging

**Work branch:** `codex/10-staging-install-upgrade`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-human

## What to build

An operator deploys an identified reviewed addon revision to the existing staging environment and verifies a fresh installation or safe upgrade.

## Acceptance criteria

- [x] Provide local deployment tooling; no GitHub deployment or provisioning changes. Source remains in this repository and is never edited directly on the VM.
- [x] Deploy an identified clean revision into a customer-specific release directory, preserving the existing addons_path and reporting the deployed revision.
- [x] Preflight active or uncertain financial operations and abort an unsafe upgrade. Quiesce checkout/dispatch so no new operation races the final check; later refund operations must participate in the same guard.
- [x] Back up the database and relevant deployment configuration; stop Odoo for installation/upgrade, use stop-after-init, no-http and workers=0, and restart only after a successful update. Report update or health-check failures clearly.
- [x] Document recovery that reconciles external financial activity before any database restoration. Never automatically restore stale payment state over newer provider activity.
- [ ] Exercise tooling with mocked command failures and disposable install/upgrade checks, then perform an operator-controlled staging smoke check without terminal charges. Verify existing cash POS still works.
- [x] Document prerequisites, exact commands, secret configuration, revision identification and operator recovery steps. Leave infrastructure ownership in odoo-hosting.

## Verification evidence

- Local deployment tests cover dirty and unreviewed revisions, financial
  blockers, the post-stop race check, install and upgrade commands, immutable
  releases, backup/update/health failures, locking, cleanup, and revision
  reporting. On 2026-09-23, all 14 tests passed with 81% branch coverage across
  the two deployment scripts.
- The shared financial-operation guard is covered in the Odoo addon suite.
- The disposable Odoo environment is the install/upgrade verification target:
  `./scripts/test-addon --verify-install-upgrade`. It passed on 2026-09-23,
  including fresh installation, the full addon suite, module upgrade, and
  retail and Restaurant POS startup checks.
- Human gate: after this revision is reviewed and integrated, an operator must
  follow `docs/staging-deployment.md`, record the deployed SHA and configuration
  backup, complete the no-charge cash POS smoke check, and attach the operator,
  UTC time, and cash order reference here before closure.

## Blocked by

- 03 — Complete one verified Revolut terminal payment

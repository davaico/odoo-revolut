# 10 — Install and upgrade a reviewed revision on staging

**Work branch:** `codex/10-staging-install-upgrade`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** claimed

**Triage:** ready-for-agent

## What to build

An operator deploys an identified reviewed addon revision to the existing staging environment and verifies a fresh installation or safe upgrade.

## Acceptance criteria

- [ ] Provide local deployment tooling; no GitHub deployment or provisioning changes. Source remains in this repository and is never edited directly on the VM.
- [ ] Deploy an identified clean revision into a customer-specific release directory, preserving the existing addons_path and reporting the deployed revision.
- [ ] Preflight active or uncertain financial operations and abort an unsafe upgrade. Quiesce checkout/dispatch so no new operation races the final check; later refund operations must participate in the same guard.
- [ ] Back up the database and relevant deployment configuration; stop Odoo for installation/upgrade, use stop-after-init, no-http and workers=0, and restart only after a successful update. Report update or health-check failures clearly.
- [ ] Document recovery that reconciles external financial activity before any database restoration. Never automatically restore stale payment state over newer provider activity.
- [ ] Exercise tooling with mocked command failures and disposable install/upgrade checks, then perform an operator-controlled staging smoke check without terminal charges. Verify existing cash POS still works.
- [ ] Document prerequisites, exact commands, secret configuration, revision identification and operator recovery steps. Leave infrastructure ownership in odoo-hosting.

## Blocked by

- 03 — Complete one verified Revolut terminal payment

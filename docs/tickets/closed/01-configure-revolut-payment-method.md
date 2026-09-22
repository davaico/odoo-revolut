# 01 — Configure and verify a Revolut payment method

**Work branch:** `codex/01-configure-revolut-payment-method`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

A manager installs pos_revolut, configures a physical location, terminal and server-managed secret reference, and checks connectivity without initiating a payment.

## Acceptance criteria

- [x] Install and upgrade cleanly on Odoo Community 19.0.20260908. Standard retail POS works without requiring restaurant installation; restaurant POS also starts successfully.
- [x] Configure one terminal per Revolut payment method, scoped to its company. Managers can select sandbox or production, configure the location and terminal, and run a non-payment connection/terminal check.
- [x] Resolve credentials through a restricted server environment-variable namespace. Odoo stores only the secret reference. Document operator provisioning, encrypted storage responsibilities and rotation; never expose secret values in POS data, model reads, exceptions or logs.
- [x] Use fixed Revolut hosts and API version 2026-08-17. Check company and manager permissions on the server; reject arbitrary hosts and unrelated secret references.
- [x] Provide a reproducible disposable Odoo/PostgreSQL test environment matching the target version and an exact addon test command. Verify extension points against that version before applying frontend patches.
- [x] Automated tests mock connection checks, reject unauthorized/cross-company access and assert no secrets enter browser-visible data. All automated Merchant API traffic is mocked, with unexpected outbound calls failing the tests.
- [x] Document installation and configuration. Demonstrate install → configure → mocked terminal check in the manager UI. This slice does not charge a terminal.

## Blocked by

None (can start immediately).

## Verification evidence

Verified on 2026-09-22 with:

```bash
python3 -m compileall -q addons
git diff --check
./scripts/test-addon --verify-install-upgrade
```

The pinned image reported Odoo `19.0.20260908`. Sixteen addon test methods ran
on a clean install and again on upgrade (the Restaurant-specific case skips
until that optional addon is present). A Chrome tour configured the payment
method in the manager form, saved it, and completed a mocked non-payment
terminal check. Separate browser tours reached the retail product screen and,
after `pos_restaurant` was installed, the Restaurant floor screen. The Compose
runtime network is internal-only and all expected Revolut requests were mocked.
The project owner approved the checksum-pinned Chrome package on 2026-09-22 as
a test-only dependency for these browser acceptance tours.

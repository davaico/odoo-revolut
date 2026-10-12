# Contribute to POS Revolut

Contributions should improve the single `addons/pos_revolut` addon, its tests, or its public documentation. Start with a small change that explains the affected cashier or administrator behavior. Discuss changes to payment verification, credentials, retries, or refund allocation before implementing a broad redesign.

## Development setup

Use a full clone of the repository, Python 3.12, Node.js with its built-in test runner, Bash, Git, Docker Engine, and Docker Compose. The Linux test scripts also use standard utilities such as `realpath`; historical upgrade tests require `flock` and `setsid` from util-linux. The browser-test image downloads an amd64 Chrome package, so its documented runtime targets Linux amd64.

Run these commands from the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test addons/pos_revolut/static/tests/*.test.mjs
./scripts/test-addon
```

The Python suite checks the portable historical and delivered-artifact test runners. Native Odoo document and PDF checks belong to the addon suite and need its Odoo runtime. The Docker runner installs the addon on the pinned Odoo/PostgreSQL runtime, checks its HTTP guard and browser transport, runs the addon suite, and removes its disposable resources. Record any skipped checks and why they did not run.

No Merchant credential or physical terminal is needed. Compose supplies an explicitly fake credential. Building the image needs network access; the test runtime uses an internal network and blocks Merchant HTTP. Automated tests must mock Revolut requests and must never contact a real terminal or Merchant API.

Use a distinct disposable project name when running tests alongside another developer:

```bash
ODOO_REVOLUT_TEST_PROJECT=pos-revolut-my-change ./scripts/test-addon
```

The runner removes the selected Compose project's containers and volumes. Do not point it at a development or production database you need to preserve.

## Select the relevant checks

For a focused Odoo test, use the class name defined in the changed test file:

```bash
./scripts/test-addon --test-tags '/pos_revolut:TestRevolutPaymentMethod'
```

For installation and upgrade coverage:

```bash
./scripts/test-addon --verify-install-upgrade
```

The historical upgrade commands cover older cart authority, credential authority, register grants, receipts, refund evidence, external returns, and return rounding:

```bash
./scripts/test-cart-authority-upgrade
./scripts/test-credential-authority-upgrade
./scripts/test-register-access-upgrade
./scripts/test-receipt-retirement-upgrade
./scripts/test-evidence-retirement-upgrade
./scripts/test-external-native-upgrade
./scripts/test-return-rounding-upgrade
```

These commands extract earlier addon versions from Git and require a full clone of the repository's history. Do not silently skip missing historical revisions or replace their fixtures with the current implementation.

For recovery across Odoo process restarts and status polling across HTTP workers:

```bash
./scripts/test-restart-recovery
./scripts/test-status-poll-workers
```

The worker test verifies that duplicate polls share one provider observation and leave another HTTP worker available. Distinct operations can still occupy both workers; the test also checks that capacity limit. Provider responses are mocked and all resources are disposable.

`scripts/test-delivered-addon` tests the addon extracted from an exact committed revision. Its migration scenario also requires a retained two-addon historical revision. Replace the placeholders with full commit hashes from this repository:

```bash
./scripts/test-delivered-addon --revision REVIEWED_FULL_COMMIT_SHA --scenario retail
./scripts/test-delivered-addon --revision REVIEWED_FULL_COMMIT_SHA \
  --scenario migration --migration-from LEGACY_FULL_COMMIT_SHA
```

Run the narrowest checks that exercise the risky behavior. A successful installation does not prove payment recovery, concurrency, financial allocation, or physical-terminal behavior. Describe precisely what ran and what remains untested.

## Implementation rules

- Keep secrets and Merchant calls on the server. Never log credentials, raw provider responses, or cardholder data.
- Persist attempts and dispatch claims before financial requests. Reconcile uncertainty before allowing another charge or refund.
- Treat a completed payment intent as an interaction result. Verify the underlying payment and the authenticated report, including explicit zero-tip evidence.
- Preserve the original order, tender, credential, and provider references during retries and recovery.
- Keep refund allocations within original quantities, tender amounts, and base/tip capacities, including pending and uncertain reservations.
- Enforce backend-user register grants and manager permissions on the server; browser employee selection is not authorization.
- Follow existing Odoo conventions and keep changes scoped. See [the architecture guide](docs/architecture.md).

For payment changes, add meaningful mocked coverage for the affected success and failure paths, lost responses, duplicate submissions, or concurrency. Preserve native Odoo stock, accounting, receipt, and session behavior where the change touches those flows.

## Submit a pull request

Use a short imperative commit subject, such as `fix(pos): Preserve recovery after a lost response`. Explain the original problem, resulting behavior, payment-flow impact, tests performed, and any configuration, upgrade, or credential-rotation steps. Include a sanitized reproduction using synthetic records.

Public reports must not contain credentials, card/customer data, live transaction or device identifiers, private hostnames, or original operational logs. Follow [SECURITY.md](SECURITY.md) for suspected vulnerabilities, including its fallback if private reporting is unavailable. Do not test a vulnerability against somebody else's register or Merchant account.

The project is licensed under LGPL-3. Before contributing material from another project, identify its source and retain any required notices. Do not assume Git authorship alone establishes permission to relicense somebody else's work.

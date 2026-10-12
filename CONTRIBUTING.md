# Contributing

Keep changes focused on `addons/pos_revolut`, its tests or documentation. Read [Architecture](docs/architecture.md) before changing payment boundaries; discuss broad redesigns first.

## Development setup

Use a full Git clone, Python 3.12, Node.js with its built-in test runner, Bash, Docker Engine and Compose. Linux scripts also need `realpath`, `flock` and `setsid`. The browser image targets Linux amd64.

From the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test addons/pos_revolut/static/tests/*.test.mjs
./scripts/test-addon
```

Python tests cover the portable test runners. The Docker runner installs the addon, checks its HTTP guard/browser transport, runs Odoo tests (including document/PDF checks), and removes its disposable resources. Building the image needs network access; tests use an internal network, fake credentials and mocked Revolut HTTP. No terminal or Merchant account is needed.

**The runner deletes its selected Compose project's containers and volumes.** Never select a database you need to keep. For concurrent runs, choose a unique project:

```bash
ODOO_REVOLUT_TEST_PROJECT=pos-revolut-my-change ./scripts/test-addon
```

## Choose checks

Run the narrowest checks that exercise the changed behavior. Record skipped checks; installation alone does not verify recovery, concurrency or physical-terminal behavior.

```bash
# One Odoo test class
./scripts/test-addon --test-tags '/pos_revolut:TestRevolutPaymentMethod'

# Fresh installation and current-version upgrade
./scripts/test-addon --verify-install-upgrade

# Recovery across restarts and status polling across HTTP workers
./scripts/test-restart-recovery
./scripts/test-status-poll-workers
```

Historical upgrade runners require the full Git history. Keep their original fixtures; missing revisions must fail:

```bash
./scripts/test-cart-authority-upgrade
./scripts/test-credential-authority-upgrade
./scripts/test-register-access-upgrade
./scripts/test-receipt-retirement-upgrade
./scripts/test-evidence-retirement-upgrade
./scripts/test-external-native-upgrade
./scripts/test-return-rounding-upgrade
```

To test an exact committed addon, replace these placeholders with full repository commit hashes. Migration also needs a retained two-addon revision:

```bash
./scripts/test-delivered-addon --revision REVIEWED_FULL_COMMIT_SHA --scenario retail
./scripts/test-delivered-addon --revision REVIEWED_FULL_COMMIT_SHA \
  --scenario migration --migration-from LEGACY_FULL_COMMIT_SHA
```

## Payment changes

Preserve the [financial boundaries](AGENTS.md#financial-boundaries). Cover affected success/failure paths, lost responses, duplicate submissions and concurrency with mocked tests. Keep native Odoo stock, accounting, receipts and session behavior intact. Never log secrets, raw provider responses or cardholder data.

## Pull requests

Use short imperative commit subjects, such as `fix(pos): Preserve recovery after a lost response`. Explain the problem, resulting behavior, payment impact, checks run and any configuration, upgrade or credential-rotation steps. Use synthetic reproductions; follow [SECURITY.md](SECURITY.md) for private reports.

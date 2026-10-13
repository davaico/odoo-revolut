# Contributing

Keep integration code in `pos_revolut` and follow Odoo conventions. Keep changes focused on the addon, its tests or documentation. Read [Architecture](docs/architecture.md) before changing payment boundaries; discuss broad redesigns first.

## Development setup

Use a full Git clone, Python 3.12, Node.js with its built-in test runner, Bash, Docker Engine and Compose. Linux scripts also need `realpath`, `flock` and `setsid`. The browser image targets Linux amd64.

From the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test pos_revolut/static/tests/*.test.mjs
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

Preserve these financial boundaries:

- Keep credentials and authenticated Revolut calls on the server.
- Persist attempts and references before dispatch; reconcile uncertainty before retrying.
- Verify the underlying payment and base/tip amounts. A completed intent alone cannot authorize checkout.
- Preserve original order, tender and Merchant authority during recovery.
- Enforce company/register access and refund quantity, base and tip limits on the server.

Cover affected success/failure paths, lost responses, duplicate submissions and concurrency with mocked tests. Mock all Revolut HTTP and keep the Merchant network guard enabled. Use synthetic fixtures. Keep native Odoo stock, accounting, receipts and session behavior intact. Never log secrets, raw provider responses or cardholder data.

## Pull requests

Use short imperative commit subjects, such as `fix(pos): Preserve recovery after a lost response`. Explain the problem, resulting behavior, payment impact, checks run and any configuration, upgrade or credential-rotation steps. Use synthetic reproductions; follow [SECURITY.md](SECURITY.md) for private reports.

## Preparing an Odoo Apps release

Follow the [submission instructions](https://apps.odoo.com/apps/upload) and [Vendor Guidelines](https://apps.odoo.com/apps/vendor-guidelines). Repository cleanup alone does not complete the publication checks.

- Keep each addon in its own folder at the repository root. Publish Odoo 19 releases from a branch named exactly `19.0`, registered as `ssh://git@github.com/davaico/odoo-revolut.git#19.0`. A local preparation branch can have a descriptive name.
- Validate the manifest's name, release version, license and dependencies. Retain LGPL-3 and its license texts; omit `price` for a free module.
- Prepare an English `pos_revolut/static/description/index.html`, a PNG `icon.png`, a cover declared by `images`, and screenshots using synthetic data. Describe only implemented features, prerequisites and limitations, including the required Revolut service.
- Explain data sent to Revolut in the manifest, store description and application, with explicit agreement before transmission. Follow the store's restrictions on external links, image formats, HTML and JavaScript; a privacy policy is recommended.
- Keep installation and upgrade instructions available. The store can display module documentation from `doc/index.rst`; the repository's Markdown guides remain the maintainer documentation.
- Verify the exact candidate's installation, upgrades and affected behavior with mocked Revolut HTTP and the Merchant guard enabled. Review code and security findings; document skipped checks and obtain device acceptance separately before claiming production readiness.

Do not register or publish a repository, or push a preparation branch, without an explicit request.

# Contributing

Develop Odoo 18 changes on `feat/v18_rev` and validate hosted changes on
`staging/18-enterprise`. Target `18.0` only with a production-ready PR; it
automatically deploys production. Odoo 19 releases target `19.0`. Keep
equivalent payment and refund behavior across versions, adapting to each
version's native APIs and testing relevant fixes on both.
Keep integration code in `pos_revolut` and follow Odoo conventions. Read
[Architecture](docs/architecture.md) before changing payment boundaries.

## Development setup

Use Python 3.12, Node.js with its built-in test runner, Bash, Docker Engine and
Compose. Linux runners also need `realpath`, `flock` and `setsid`. The browser
image targets Linux amd64. From the repository root:

```bash
python3 -m unittest discover -s tests -v
node --test pos_revolut/static/tests/*.test.mjs
./scripts/test-addon
```

The Odoo 18 runner pins `18.0.20261015`, uses fake credentials, mocks Revolut
HTTP and enables the Merchant network guard. Tests must never contact a real
terminal or Merchant account. Building the image needs network access.

The runner deletes its selected Compose project's containers and volumes.
Select a unique disposable project; never use a database that must be retained:

```bash
ODOO_REVOLUT_TEST_PROJECT=pos-revolut-my-change ./scripts/test-addon
```

## Choose checks

Run the narrowest checks that exercise the change and record any skipped checks.
Installation alone does not establish recovery, concurrency or device behavior.
See [Validation](docs/validation.md) for recorded release coverage and limitations.

```bash
./scripts/test-addon --test-tags '/pos_revolut:TestRevolutPaymentMethod'
./scripts/test-addon --verify-install-upgrade
./scripts/test-restart-recovery
```

`--verify-install-upgrade` seeds an existing native Odoo 18 POS/Restaurant database,
installs the addon for the first time, and verifies native business records and
addon configuration again after updating the same candidate.

To test the exact committed addon, use a full commit hash from this branch:

```bash
./scripts/test-delivered-addon --odoo-major 18 --scenario retail --revision REVIEWED_FULL_COMMIT_SHA
./scripts/test-delivered-addon --odoo-major 18 --scenario populated --revision REVIEWED_FULL_COMMIT_SHA
```

Legacy Odoo 19 upgrade runners and fixtures are retained as development tools.
Their old baseline revisions are intentionally absent from this fresh history.
They require separately retained private baselines and the matching Odoo 19
addon. Do not restore the old history to this branch to make those checks pass.

## Payment changes

Keep credentials and authenticated API calls on the server. Persist attempts
and references before dispatch; reconcile uncertainty before retrying. Verify
successful underlying payments and base/tip amounts before checkout. Preserve
original Merchant, company, register, tender and refund relationships.

Cover affected failures, lost responses, duplicate submissions and concurrency
with mocked HTTP. Preserve native stock, accounting, receipts and session
behavior. Keep original production evidence in restricted storage; public
documentation and reproductions use synthetic data.

Use short imperative commit subjects. Explain payment-flow impact, checks,
configuration and deployment steps. Follow [SECURITY.md](SECURITY.md) for private
reports. Obtain separate authorization for deployment and live financial actions.

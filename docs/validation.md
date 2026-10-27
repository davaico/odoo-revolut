# Validation and limitations

The Odoo 18 release `18.0.1.0.4` was tested with Odoo Community
`18.0.20261015` and PostgreSQL `16.14`. Enterprise and other runtime builds
have not been verified.

## Recorded automated coverage

Application results apply to candidate
[`ed82c90`](https://github.com/davaico/odoo-revolut/commit/ed82c90c1eddfb1bf898a8978c99e2c874fd7d5b).
The subsequent move to root-level `pos_revolut/` preserved the application
and addon test files; only manifest description and image metadata changed.

| Check | Recorded result |
| --- | --- |
| Full addon suite, including POS, Restaurant and employee permissions | 784 passed, no failures, errors or skips |
| First installation into a populated native POS database | 59 passed; existing business records preserved |
| Same-version update and update from `18.0.1.0.3` | 59 passed in each run; configuration and financial evidence preserved |
| JavaScript payment state and refund allowance tests | 145 passed |
| Host tooling checks | 70 passed; three PDF checks skipped for unavailable host dependencies |
| PDF renderer checks in the supported runtime | All seven passed, covering the host PDF skips |

Runs use synthetic records, fake credentials, mocked provider responses and
blocked real Merchant HTTP. They cover payment outcomes, interruption and
recovery, full and partial refunds, duplicate prevention, tips, split tenders,
Restaurant workflows, permissions, receipts, stock and accounting. Counts
represent separate runs and must not be added as a coverage measure.

## Device and deployment limits

Automated results do not establish the behavior of a customer's database,
Merchant account, terminal or printer. Physical checks did not establish
split payments using two distinct cards, a genuine issuer decline or every
interruption variant. Physical printer output was not tested.

Before rollout, verify the intended installation, terminal setup, register
permissions, report access and native checkout under an agreed acceptance
plan. Keep financial evidence private. Reconcile pending payments and refunds
by their original references; never replay them to complete a test.

Follow [Installation](installation.md) and [Upgrading](upgrading.md) for setup
and backup requirements. [Contributing](../CONTRIBUTING.md#choose-checks)
documents reproducible checks for the exact revision being changed.

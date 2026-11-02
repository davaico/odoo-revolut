# Validation and limitations

The released Community `18.0.1.0.4` was tested with Odoo Community
`18.0.20261015` and PostgreSQL `16.14`. Its historical coverage is retained below.
The Enterprise/Odoo.sh `18.0.1.0.8` candidate has separate lifecycle evidence and
release validation in progress; it is not yet ready for promotion.

## Enterprise/Odoo.sh 18 candidate

Frozen source: `f8abaa3fcab1f1261ab04cc92bdf1bdc6d03d9ea`; exact addon tree:
`a6b87c19d9615ea07ff0b9dd86c82b4495f26e70`. This includes the corrected `.4`
baseline plus server environment protection, administrator-managed credentials,
copy neutralization and configuration guidance. Listing prose now acknowledges
the bounded hosted evidence. No payment runtime code changed during release
assembly.

Hosted staging build **41044597** used source `fdfa74596f2445e0a54a1206cb28a052386cda01`,
installed `.8`, Odoo `18.0+e` (Odoo `2982b5f`, Enterprise `631c5ab`). Mocked checks
exercised populated installation, credential access, neutralization/copy safety,
HTTP recovery and actual native cron-worker interruption/replacement for the same
payment/refund attempts. The platform-managed restart command and scheduling SLA
were not established. Production runtime files match the assembled candidate;
manifest prose and test fixtures differ. This attributes hosted results to the
actual build rather than claiming the assembled revision itself ran there.

Assembled-candidate populated installation/update, versioned `.4 -> .8` upgrade,
neutralized first installation and final full-addon results are pending. Current
portable checks: 146 JavaScript passes and 80 host tests with three existing
optional PDF dependency skips.

This reference project remains test-only. Mocked Community-image tests and bounded
Enterprise lifecycle evidence do not establish a client's terminal, entitlement,
production setup or live financial outcomes. Staging configuration is not promoted
with code. Follow [Release and activation](releasing.md) for explicit client setup,
module upgrade, bounded payment/refund acceptance and recovery.

Community 18/19 remain separately maintained. The held-response test-fixture
correction needs selective backporting and native recovery/full-suite evidence on
each line. Enterprise credential/hosting changes require deliberate adaptation
before adoption there. These tests do not certify either unchanged Community line
or Odoo 19 Enterprise/Odoo.sh.

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

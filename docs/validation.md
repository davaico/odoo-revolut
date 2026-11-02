# Validation and limitations

The released Community `18.0.1.0.4` was tested with Odoo Community
`18.0.20261015` and PostgreSQL `16.14`. Its historical coverage is retained below.
The Enterprise/Odoo.sh `18.0.1.0.8` candidate has separate lifecycle evidence and
release validation recorded below. Client activation remains a separate approved step.

## Enterprise/Odoo.sh 18 candidate

Frozen source: `3f2ff4a167f154fafe5ff886cb506a47145b0bae`; exact addon tree:
`57730fd0d5a81ea6a288081ac0eced63eb9e5b1b`. This includes the corrected `.4`
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
manifest/store-listing prose and test fixtures differ. This attributes hosted results to the
actual build rather than claiming the assembled revision itself ran there.

| Check | Result and source |
| --- | --- |
| Retained clean full-suite prerequisite | `fccfd12`: 816 cases, zero failures/errors, one optional `pos_hr` skip |
| Assembled-source full invocation | `3f2ff4a`: 816 cases, zero failures/errors, five skips (optional `pos_hr` plus four Chrome startup skips); not a clean fresh full run |
| Four exact skipped saved-refund browser cases | `3f2ff4a`: 4 passed, zero failures/errors/skips; original references and no duplicate dispatch verified |
| Populated native first installation and same-candidate update | `f8abaa3`: 31 focused tests in each phase; native history and 29 configuration/financial records preserved |
| Production `.4 -> .8` versioned upgrade | `f8abaa3`: native/financial history and environment authorities preserved; original-key GET-only recovery passed |
| Neutralized before addon installation | `f8abaa3`: both Production key sources blocked with zero HTTP/reservations; Sandbox usable |
| JavaScript and portable tooling | 146 JS passes; 80 host tests, zero failures/errors, three existing optional PDF dependency skips |

The final addon differs from `f8abaa3` only in store-listing prose. Compared with
`fccfd12`, runtime, manifest settings and automatically loaded tests are identical;
only manifest/store prose and two unimported standalone cron fixtures differ.
The retained clean-full evidence, assembled invocation, exact four-case completion
and install/upgrade checks form the release evidence. All ten previously affected
browser cases executed successfully on the final addon across its full/focused
runs. Counts describe separate runs and must not be added together.

The new full run's four Chrome startup skips coincided with a severe late shared-host
resource burst; root cause remains unestablished. Its rejected clean-run status is
preserved. A first invocation was deliberately interrupted before an aggregate to
include the final listing clarification. Neither run is presented as a clean full
pass. All provider traffic was mocked and real Merchant HTTP blocked. No payment
assertion or test timeout was changed.

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

## Recorded Community .4 coverage

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

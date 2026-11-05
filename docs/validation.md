# Validation and limitations

POS Revolut `18.0.1.0.8` adds Odoo 18 Enterprise/Odoo.sh credential and hosting
support to the established Odoo 18 feature baseline. Local automated checks use
Odoo Community `18.0.20261015` and PostgreSQL `16.14`. Separate hosted checks use
Odoo `18.0+e` on Odoo.sh. Results from one environment do not establish the full
behavior of the other.

## Current Odoo 18 coverage

| Check | Recorded result |
| --- | --- |
| Local full addon suite | 816 cases, zero failures/errors, one optional `pos_hr` characterization skip; no browser startup skips |
| Local browser coverage within that full run | 127 successful tour executions across 117 distinct cases |
| Focused hosted Enterprise selection | 19 mocked checks passed with zero failures/errors/skips, covering Database credentials, company/access boundaries, neutralization, direct scheduled recovery and blocked-stage connection feedback |
| Populated native first installation and same-candidate update | 31 focused tests in each phase; native business data and configuration/financial history preserved |
| Versioned `.4 → .8` upgrade | Environment authorities and financial history preserved; original-key payment/refund recovery verified with mocked status requests |
| Installation after database neutralization | Both Production credential sources blocked before provider HTTP or new reservations; Sandbox remains usable |
| JavaScript and portable tooling | 146 JavaScript checks passed; 80 tooling tests, zero failures/errors and three optional PDF-dependency skips |

These counts describe separate runs and must not be added together as a coverage
measure. The completed full run is distinct from earlier interrupted or failed
invocations; those earlier results are not treated as passes.

Tests use synthetic data and credentials, mocked provider responses and blocked
real Merchant HTTP. Coverage includes payment outcomes, interruption and recovery,
full/partial refunds, duplicate prevention, tips, split tenders, Restaurant flows,
permissions, receipts, stock and accounting. Credential tests exercise the real
Database/Environment resolver, restricted administration, source selection,
immutable rotation and historical-operation bindings.

Hosted lifecycle checks also exercised installation, copy neutralization,
HTTP-process recovery and native cron-worker interruption/replacement while
preserving the same payment/refund attempts. Those bounded checks used mocked
provider traffic. They do not establish a platform-managed restart command or
an Odoo.sh scheduling guarantee. The latest 19-case hosted selection is focused
coverage, not a full Enterprise-suite run or a fresh repetition of every earlier
lifecycle scenario.

## Earlier Community release coverage

The Community `18.0.1.0.4` release was tested with the same pinned Community and
PostgreSQL versions. Its recorded results remain useful historical coverage;
they are not a fresh run of the Enterprise/Odoo.sh changes.

| Check | Recorded result |
| --- | --- |
| Full addon suite, including POS, Restaurant and employee permissions | 784 passed, no failures, errors or skips |
| First installation into a populated native POS database | 59 passed; existing business records preserved |
| Same-version update and update from `18.0.1.0.3` | 59 passed in each run; configuration and financial evidence preserved |
| JavaScript payment state and refund allowance tests | 145 passed |
| Host tooling checks | 70 passed; three PDF checks skipped for unavailable host dependencies |
| PDF renderer checks in the supported runtime | All seven passed, covering the host PDF skips |

## Device and deployment limits

The integration has been validated by Revolut. The Enterprise/Odoo.sh checks
reported here use mocked provider traffic and do not establish a real Enterprise
terminal sale/refund acceptance pass, a customer's production readiness or Odoo
19 Enterprise compatibility.

Automated results do not establish the behavior of a customer's database,
Merchant account, terminal or printer. Recorded physical checks did not establish
split payments using two distinct cards, a genuine issuer decline or every
interruption variant. Physical printer output was not tested.

Before rollout, verify the intended installation, terminal/location and supported
currency, register permissions, payment-report access and native checkout under
an agreed acceptance plan. Complete a bounded real sale, partial refund and
remaining-balance refund with matching provider outcomes and Odoo records.
Staging configuration does not transfer automatically with code, and Production
Revolut traffic remains blocked on test builds and neutralized databases.

Keep financial evidence private. Reconcile pending payments and refunds by their
original references; never replay them to complete a test. Follow
[Installation](installation.md), [Upgrading](upgrading.md), the
[Odoo.sh guide](odoo-sh-staging.md) and [Deployment acceptance](releasing.md).
[Contributing](../CONTRIBUTING.md#choose-checks) describes reproducible automated
checks for the revision being changed.

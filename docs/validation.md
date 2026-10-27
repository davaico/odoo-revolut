# Release validation

## Odoo 19 — 19.0.1.18.16

The release was tested on **Odoo Community 19.0.20260908** and
**PostgreSQL 16.14** on 2026-10-26. Other Odoo builds and Enterprise were not
verified. These are targeted release checks, not a complete addon-suite result.

| Check | Result |
| --- | --- |
| Native payment/refund tests and browser tours | 112 tests passed, including nine selected tours |
| Native combo pricing | 19 tests passed |
| JavaScript state, refund refresh and allocation checks | 159 tests passed |
| Portable release-runner tests | 23 tests passed |
| Upgrade from 19.0.1.18.14 to 19.0.1.18.16 | Passed; 37 record snapshots preserved |

Payment and refund coverage includes the integration partner metadata, recovery
of already-verified refunds onto their original waiting tenders, and restoration
of verified references after native POS refresh. Checks cover one and two
refunds, pending recovery, repeated recovery, mixed Cash/card returns and
interrupted native checkout. Recovery preserves original references and does
not dispatch a replacement payment or refund. Pending or unresolved refunds
remain blocked; outstanding Cash requires explicit completion.

Combo pricing checks exercise native rounding when display order differs from
item ID order, including mixed tax rates and restricted manual pricing.

The upgrade rehearsal installed the earlier version in a disposable database,
seeded synthetic records, stopped the old process, updated the addon and
verified the retained records and recovery behavior. See
[Upgrading](upgrading.md) for deployment and rollback procedures and
[Contributing](../CONTRIBUTING.md#choose-checks) for test runners.

## Test boundaries

Native and browser checks used disposable databases, fake credentials, mocked
Revolut HTTP and the Merchant network guard. They did not use a real Merchant
account, production database or physical terminal. Synthetic results do not
establish the condition of a deployed database, live account or device.
Validate the intended installation and affected workflows before rollout;
physical-terminal acceptance is separate from automated testing.

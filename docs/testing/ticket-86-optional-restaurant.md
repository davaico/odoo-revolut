# T86 — Optional Restaurant verification

Verification on November 5, 2026 used disposable Docker databases, pinned Odoo
Community 18.0.20261015 and 19.0.20260908, PostgreSQL 16.14, and the repository's
Merchant HTTP blocker. Browser checks use Chromium. Provider replies and
financial references in these tests are synthetic.

## Source lanes

| Lane | Local branch | Development base | Upgrade baseline |
| --- | --- | --- | --- |
| Odoo 18 Enterprise | `codex/86-v18-enterprise` | `staging/18-enterprise` at `14fdbb1` | Published `18.0` at `0e515e9` |
| Odoo 18 Community | `codex/86-v18-community` | `feat/v18_rev` at `3f00804` | Community 18.0.1.0.4 at `a6dc7bd` |
| Odoo 19 | `codex/86-v19` | Published `19.0` at `c2b7d40` | Published `19.0` at `c2b7d40` and historical bridge at `30492a6` |

The Odoo 19 development branch starts from the reviewed release because both
checked `main` refs lack fixes in `19.0`. Enterprise integration and hosted
validation target `staging/18-enterprise`.

## Checks

| Lane and scenario | Exact archive revision | Result |
| --- | --- | --- |
| Odoo 18 Enterprise candidate, base-only retail | `3c6f7ea` | 115 tests passed. Native Restaurant and the companion were uninstalled. |
| Odoo 18 Enterprise candidate, paired Restaurant | `3c6f7ea` | 45 tests passed, including browser workflows, concurrency guards, timed Takeout and original refund policy. |
| Odoo 18 paired Restaurant refund follow-up | `91d4408` | All three refund browser tests passed, including a new half-quantity refund of 617 minor units linked to the original Restaurant payment. |
| Odoo 18 Enterprise candidate, populated first install and repeat update | `3c6f7ea` | Both browser smoke checks passed. The paired archive preserved native sale and invoice records and the candidate's committed payment/refund history. |
| Odoo 18 Enterprise candidate, combined release upgrade | `c2cdfe4` | Pass. Both retail and mixed databases preserved data through the initial and repeat upgrades. |
| Odoo 18, add Restaurant after retail install | `767c95c` | Retail and Restaurant browser checks passed. Adding native Restaurant installed the companion automatically. |
| Odoo 18, native Restaurant with base-only archive | `767c95c` | Pass. Blocked new Restaurant dispatch, verified the original pending Restaurant payment and allowed retail dispatch. |
| Odoo 18 Community candidate, combined release upgrade from 18.0.1.0.4 | `641f2c4` | Pass on retail and mixed databases. Four browser smoke tests passed after the repeat updates. |
| Odoo 19 base-only retail | `20080bd` | 100 tests passed. Native Restaurant and the companion were uninstalled. |
| Odoo 19 paired Restaurant | `3db3296` | 15 tests passed, including browser checkout and Restaurant guards. |
| Odoo 19 paired Restaurant refund follow-up | `12cec20` | All six Restaurant context tests passed, including full and half-quantity refunds linked to the original paid table orders. |
| Odoo 19, add Restaurant after retail install | `8bb7da7` | Retail and Restaurant browser checks passed. Adding native Restaurant installed the companion automatically. |
| Odoo 19, native Restaurant with base-only archive | `8bb7da7` | Pass. Blocked new Restaurant dispatch, verified the original pending Restaurant payment and allowed retail dispatch. |
| Odoo 19 combined release upgrade | `12ba3c0` | Pass. Both retail and mixed databases preserved data through the initial and repeat upgrades. |
| Odoo 19 legacy bridge upgrade | `20080bd` | Pass. The mixed database retired the legacy bridge and installed the new companion. Native Restaurant and the companion remained uninstalled on the retail database. Both databases preserved native records on repeat. |

The combined-release fixtures exercise explicit companion installation on
retail databases that inherited Restaurant and plain `-u pos_revolut` on
mixed databases with paired source available. Each fixture snapshots paid
orders, open orders, payment and refund references, authorization and dispatch
records, credential bindings, and register configuration. The mixed fixture
adds a Restaurant floor, table and preset. After the repeat upgrade, the
original pending sale reaches verified provider finality without a second
charge or payment-intent dispatch.

The targeted retail suites covered verified sale settlement, ordinary cash and
bank checkout, split tender, terminal tips, decline, failure, cancellation,
timeout, interrupted recovery, safe retry, and full and partial refunds. The
paired suites covered native Restaurant guards, valid table movement and timed
Takeout, including browser verification.

The missing-companion regression failed against each combined release, which
still supplied Restaurant support itself. It passed against split base-only
source with native Restaurant installed. The split base rejects new Restaurant
dispatch before provider contact and permits retail checkout. Existing exposed
orders retain conservative recovery behavior.

Local packaging checks validated version-matched paired archives and standalone
Store-style Git ZIPs at `91d4408`, `b6de816` and `12cec20`. Base ZIPs contain
only `pos_revolut`; matching companion ZIPs contain their own manifest and Store
description. Packaging tests reject missing and mismatched companions.

Odoo 18 JavaScript tests passed 146/146. Odoo 19 JavaScript tests passed 159/159.
The Enterprise Python tooling suite passed 83 tests with 3 optional skips, and
the Odoo 19 tooling suite passed 25 tests. The first parallel Chromium runs
hit host memory pressure. Exact-artifact browser runs above supersede those
partial runs where the corresponding scenario completed.

## Release gates

Hosted Enterprise validation and actual Odoo Apps-generated downloads remain
release gates. Local version-bump tests exercise the module loader path that a
hosted upgrade uses. No candidate was published or deployed to a hosted
environment, and no live terminal transaction was attempted.

# Single POS Revolut addon — 2026-10-05

The owner requested one Revolut addon and explicitly approved making Odoo's
standard `pos_restaurant` addon a dependency. Version `19.0.1.15.0` moves the
existing Restaurant guards and browser tour into `pos_revolut`, removes the
separate addon, and retires its module registration during upgrade. Retail
registers remain in retail mode. Payment and refund models are unchanged.

The original split was introduced in `e3013a8` on 2026-09-23 solely to keep
Restaurant optional, as recorded in closed ticket 07.

## Runtime verification

Tests used the pinned Odoo `19.0.20260908` Docker image, disposable databases,
Chromium, and the repository's Merchant HTTP blocker. No live deployment or
terminal operation occurred.

- `ODOO_REVOLUT_TEST_PROJECT=revolut-consolidation-fresh ./scripts/test-addon --delivered-scenario retail`
  passed 16 tests and exited 0. Restaurant was installed automatically;
  `pos_revolut_restaurant` was absent from the module table.
- `ODOO_REVOLUT_TEST_PROJECT=revolut-consolidation-migration ./scripts/test-addon --addons-dir ./addons --legacy-addons-dir /tmp/revolut-consolidation-legacy/addons --delivered-scenario migration`
  passed four groups of 16 tests and exited 0. The legacy directory came from
  a Git archive of `30492a67020acdfe34d7f560a9cf6d7fb20f6430`. Both a retail
  installation with the bridge uninstalled and a Restaurant installation with
  it installed upgraded successfully. Each then passed a repeat upgrade with
  only the consolidated addon available. All module-state assertions passed.

The selected tests exercise retail startup and cash/bank checkout, Restaurant
checkout and server authority checks, split/merge/transfer guards, permitted
empty-table movement, blocked post-payment tip adjustment, and bridge cleanup
with absent, uninstalled, installed, dependent, and pending module states.

An initial migration run exposed duplicate tour registration because Odoo's
asset resolver uses `registry._init_modules` even after the module record is
removed. The retirement hook now removes this asset-only addon from that set
and invalidates the asset cache. All four migration groups passed afterward.
The first fresh harness run also encountered a shell error because the running
script was edited; the finalized script was rerun successfully.

## Other checks

- `python3 -m unittest discover -s tests -p 'test*.py'`: 43 tests, 40 passed,
  three optional Docker tests skipped; the Odoo runtime checks above ran
  separately.
- `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`:
  79 passed, no failures or skips.
- A temporary working-tree archive containing only `addons/pos_revolut` passed
  the production extractor. The extracted addon contained the Restaurant
  dependency, guards, tour, retirement hook, and migration. This was a local
  snapshot check, not acceptance of an immutable reviewed release.
- Python compilation, JavaScript syntax, shell syntax, and `git diff --check`
  passed.

Before live deployment, commit and review the release and run the exact-artifact
checks in the staging runbook. The guarded deployer keeps legacy source through
the update, verifies retirement, then removes its managed symlink. Manual
installations must remove the old addon source after the successful offline
upgrade and reopen POS to load the new assets.

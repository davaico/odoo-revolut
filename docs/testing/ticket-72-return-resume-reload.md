# Ticket 72 — Consume completed Odoo 18 recovery navigation

Base and integration target: sanitized `feat/v18_rev` at `6fd1757`.
Task branch: `codex/72-v18-return-resume`. No private ancestry is merged.

## Reproduction and correction

The synthetic native browser regression was committed first in `da54b32`.
It recovers an existing waiting refund through the manager action, reloads the
same unfinished return, completes native validation, starts another order, and
reloads again. Unchanged production code fails with the exact **Revolut return
unavailable** dialog. First run failed behind the unexpected modal; the refined
observation fails immediately with its exact text (`build/ticket72/red-exact.log`).
All records and provider responses in these tests are synthetic.

Odoo 18's query-based adapter retained `revolut_return_uuid` after the native
return had completed. On reload, startup interpreted the same navigation as a
request to recover a draft, which the completed return no longer was. The fix
uses the existing successful native `postSyncAllOrders` lifecycle. After the
parent hook succeeds, it removes only that query parameter when the synchronized
order has the matching UUID, belongs to this session, and is paid/done/invoiced.
It replaces the existing history entry, preserving its state, other query
values, pathname and hash. Drafts, other orders and other sessions do not consume
it; synchronization failures cannot reach cleanup. Startup rejection and
cashier-login guards are unchanged. No backend payment/refund logic changed.

An already-stale tab from the pre-fix build needs one navigation to the normal
register URL after deployment. A direct missing, invalid or completed recovery
link still produces its meaningful warning; the fix does not silently authorize
invalid targets. Existing completed returns remain available through backend
review and saved receipts. No new validation or financial operation is needed
for this one-time old-tab reset.

## Focused verification

Pinned Odoo Community `18.0.20261015`, PostgreSQL 16.14, bundled Chrome 153,
disposable Compose project `revolut-ticket72`, internal-only network and global
Merchant HTTP guard. No protected acceptance data or real key is used.

- Exact primary red → green: one browser test failed before the fix, then passed.
- Final affected browser class: **9 tests, zero failures/errors**, including new
  standalone and mixed completed-return reloads, the existing unfinished-return
  reload/identity cases, missing-return and external-return paths, and historical
  reprints. Query duplicate values, hash, history state and history length are
  preserved while only the consumed parameter disappears. Invalid-target checks
  explicitly enter through native cashier login, retaining both URL and warning.
- Original saved return/tender identities, canonical references, native stock
  return and returned quantity checks pass. Payment/refund/dispatch counts do
  not increase during recovery/validation. Existing waiting cases allow only
  one mocked status GET; other paths allow no provider call.
- The first combined run had one fixture failure: the new invalid-target tour
  stopped at native cashier login. The tour was corrected to observe that gate,
  enter the register, then assert the warning. No production guard was weakened.
- JavaScript: **144 passed**, using `node --test --test-isolation=none
  addons/pos_revolut/static/tests/*.test.mjs`. Without that flag, this host's
  runner reports two file-level results; the expanded run is the case count.
- Changed Python/JavaScript parse and `git diff --check` pass. No standalone
  linter/typechecker configuration exists. The full addon suite was not repeated
  for this small browser-only correction; this is the explicitly bounded test
  campaign requested by the owner, not a new full parity/release claim.

Final browser log: `build/ticket72/focused-browser-final.log`; primary green:
`build/ticket72/green.log`; JavaScript: `build/ticket72/javascript-expanded.log`.
Ignored local logs are reproducibility evidence, not distributed addon assets.

```sh
docker compose --project-name revolut-ticket72 --file compose.yaml run --rm odoo \
  --database ticket72 --update pos_revolut \
  --test-tags /pos_revolut:TestExternalRefundManagerUi \
  --stop-after-init --workers 0 --max-cron-threads 0 --log-level test
```

The first run on a new database uses `--init pos_revolut`. Select
`/pos_revolut:TestExternalRefundManagerUi.test_completed_manager_return_reload_has_no_stale_recovery_warning`
for the primary regression.

## Maintained version boundary

Odoo 19's maintained source uses the native `/pos/ui/<config>/payment/<uuid>`
route and has no corresponding `revolut_return_resume.js` adapter to transplant.
This is a source assessment, not Odoo 19 runtime verification or a fix for the
separate waiting-refund recovery ticket 71. This correction targets Odoo 18 only.

## Independent review

A read-only agent reviewed the final diff against `6fd1757` and the final browser
log. Standards: no findings. Spec: no findings. It confirmed that awaited parent
synchronization prevents cleanup on failure, matching UUID/session/state gates
preserve unrelated navigation, and existing unfinished-return and invalid-link
behavior remains intact. This review did not access acceptance data or providers.

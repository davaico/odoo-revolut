# Ticket 79 — Configuration workflow verification

Validated locally on 2026-11-02. Starting Odoo 18 base: `feat/v18_rev` at
`bb1374899286e05978f6a34d20b5859e2ffdcae7`. The owner subsequently moved
Enterprise/Odoo.sh work to **`staging/18-enterprise`**; that is the final
integration target. After the full run, this task incorporated staging routing
commit `eff53ba`; its addon tree is identical to the tested implementation. The
owner then authorized integration and push to staging only. Community
`feat/v18_rev` and production `18.0` are outside this task's write scope.
Task branch: `codex/79-configuration-workflow`. Tested implementation:
`0fd1ae777efeb6b879f02c0c6d0ecf18ff3903c0`, addon `18.0.1.0.8`.

## Rendered observations and corrections

Inspected installed native forms in disposable Odoo Community `18.0.20261015`
with PostgreSQL `16.14`, using synthetic data. No hosted environment or real
Merchant account was used.

| Observed before editing | Correction verified in the rendered form |
| --- | --- |
| The Payment Method showed Terminal/Revolut selectors without their native labels. The addon inserted a nested group into the native inner group, squeezing its own controls into a narrow column. | Move only the Revolut section after the native payment-method group. **Integration** and **Integrate with** appear again and the Revolut fields use the sheet width. |
| The native Company field depends on multi-company visibility; the Revolut section did not identify the owning company. | Always show readonly **Revolut Company** in the manager-only section, with company/journal guidance. |
| **Revolut Secret Reference** did not clearly distinguish a permitted reference from a secret or terminal identifier. Location/environment fields had no explanatory help. | **Revolut Credential Reference** and inline guidance say to enter the approved reference, never the API key. Help distinguishes the company, environment and location/terminal UUIDs. |
| Authority forms/list used generic **Environment**, **Secret Reference**, **Source**, and **Secret Key** labels. Environment-backed creation did not explain that saving does not provision a variable. | **Revolut Environment**, **Credential Reference**, **Credential Source**, and **Merchant API Key**, with role/source/rotation help and provisioning guidance. Database key entry remains masked and disappears after save. |
| The installed authority action was under the native **Orders** menu, although installation instructions omitted that level. | Document **Point of Sale → Orders → Revolut Merchant Authorities**; preserve the existing menu placement. |

Temporary visual evidence: `/tmp/ticket79-before-method.png`,
`/tmp/ticket79-before-authority.png`, `/tmp/ticket79-before-database.png`,
`/tmp/ticket79-after-method.png`, `/tmp/ticket79-after-authority.png`.
The final Payment Method was inspected at 1280 × 1100 so every field and the
connection button were visible. These screenshots contain no real credentials.

## Behavior exercised

The existing native-form boundary is the ticket's requested test seam. The first
tracer tour failed with **Missing configuration label: Integration** on the
original layout (`/tmp/ticket79-red.log`); the same tracer passed after the
layout/help correction (`/tmp/ticket79-green.log`).

- System administrator: create Database and Environment variable authorities
  in their installed forms, verify labels/help and source-dependent key input,
  save immutable identities, rotate a Database authority without copying its
  reference/key, and use the original and rotated key in mocked connection
  checks. Original authority and method bindings remain unchanged until an
  explicit reconfiguration.
- Ordinary POS manager: remove system-administrator membership before the
  Payment Method tour, configure Sandbox/location/terminal/fulfilment/reference,
  save the exact values, and receive **Counter 1 is online** from mocked HTTP
  using the real credential resolver. A foreign-company reference is rejected
  visibly without exposing its synthetic key; restoring the permitted reference
  saves successfully. The administrator separately grants register access.
- Restricted users: existing RPC read/export, field visibility, unauthorized
  company/reference, connection failure and POS-data tests cover the unchanged
  credential boundary. No key or authority inventory is added to POS payloads.
- French: install native `fr_FR` translations, require the visible **Nouveau**
  control, then create/save the same Database authority. Addon strings use
  Odoo's normal translatable Python/XML sources and English fallback; literal
  references, environment values and UUIDs are unchanged. No translation catalog
  or general localization project was added.

## Commands and results

The temporary `/tmp/ticket79-runner/compose.yaml` is the repository Compose file
with its build/addon paths pointing to this worktree and an explicit internal
subnet `10.237.179.0/24` to avoid the exhausted default subnet pool. Pinned images,
synthetic environment key and `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1` are unchanged.
All provider HTTP is mocked; no real terminal request is allowed.

Focused invocation:

```bash
docker compose -p odoo-revolut-ticket79 -f /tmp/ticket79-runner/compose.yaml run --rm odoo \
  --database odoo_revolut_tests --update pos_revolut --stop-after-init --workers 0 \
  --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO \
  --test-tags /pos_revolut:TestRevolutManagerUi,/pos_revolut:TestRevolutPaymentMethod,/pos_revolut:TestRevolutCredentialAuthority,/pos_revolut:TestRevolutDatabaseCredentials
```

- Focused non-browser coverage: **39 tests passed** in the combined run. The
  combined run reported one browser readiness error and one browser-selector
  failure, so it was not green (`/tmp/ticket79-focused-final.log`). Host memory
  and swap were exhausted during the readiness timeout; this observation does
  not establish its cause. The selector targeted a dialog wrapper with no visible
  box; final tests target its visible body and native footer button.
- Final native UI rerun with `--test-tags /pos_revolut:TestRevolutManagerUi`:
  **3 tests passed**, zero failures/errors, exit 0 (`/tmp/ticket79-ui-final.log`).
  This includes the installed French translations and visible rejection checks.
- Full addon suite (same invocation, `--test-tags /pos_revolut` plus
  `--log-handler odoo.addons.pos_revolut:INFO`): **815 cases, two failures, zero
  errors, two skips, exit 1**. All three configuration UI cases passed again
  inside this full run. Skips were the optional `pos_hr` characterization and
  retail startup after a Chrome connection error.

  The two failures were unchanged browser cases:
  `TestRevolutRefundHistory.test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund`
  (receipt-screen timeout) and
  `TestRevolutTakeoutReadinessUi.test_captured_tender_finishes_after_native_scheduling_correction`
  (overall script timeout). The reviewed diff changes neither these tours nor
  the POS application/refund/checkout logic. The language test ran after both
  failures. No change-caused link or root cause has been established.

  The original attached client disconnected with status 130 while the Odoo
  container kept running. `/tmp/ticket79-full-container.log` captures that same
  container's complete output; `/tmp/ticket79-full-exit` records its actual exit
  status 1. This was one full suite invocation. Synthetic browser artifacts
  are retained in `/tmp/ticket79-browser-artifacts` and
  `/tmp/ticket79-browser-artifacts-late`.
- Isolated rerun of both failed cases, same database and addon bytes after the
  routing-only fast-forward to `eff53ba`: **two tests passed**, zero
  failures/errors, exit 0 (`/tmp/ticket79-recheck.log`). The original financial,
  native return and duplicate-operation assertions remain intact. Command:

  ```bash
  docker compose -p odoo-revolut-ticket79 -f /tmp/ticket79-runner/compose.yaml run -d --name odoo-revolut-ticket79-recheck odoo \
    --database odoo_revolut_tests --update pos_revolut --stop-after-init --workers 0 \
    --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO \
    --test-tags /pos_revolut:TestRevolutRefundHistory.test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund,/pos_revolut:TestRevolutTakeoutReadinessUi.test_captured_tender_finishes_after_native_scheduling_correction
  ```

  These isolated successes do **not** make the full run green. The follow-up
  remains [ticket 84](../tickets/needs-triage/84-investigate-checkout-browser-full-suite-failures.md)
  and a release-candidate validation gate under #81.
- Retail startup skipped by the full run: **one test passed**, zero
  failures/errors/skips, exit 0 (`/tmp/ticket79-retail-recheck.log`). Same
  invocation with container name `odoo-revolut-ticket79-retail-recheck` and
  `--test-tags /pos_revolut:TestRevolutRetailPosStarts.test_retail_pos_starts_with_addon_installed`.
  The full run's original browser skip remains recorded above.
- `node --test --test-isolation=none pos_revolut/static/tests/*.test.mjs`:
  **146 passed**, zero failures (`/tmp/ticket79-js.log`).
- `python3 -m unittest discover -s tests -v`: **75 run**, zero failures,
  three existing PDF dependency skips (`/tmp/ticket79-host.log`).
- `python3 -m compileall -q pos_revolut`, `node --check` on both changed tour
  files and `git diff --check`: passed. This repository has no configured static
  type checker; Python compilation and JavaScript syntax checks do not substitute
  for the exercised native UI behavior.

## Independent review

Standards: **0 remaining findings** for `bb13748...ee49512` and the incremental
`ee49512...0fd1ae7` test corrections. Existing Odoo structure, scoped help and
server-owned credential boundaries are preserved; no actionable baseline smells.

Spec: **0 remaining findings** for `bb13748...0fd1ae7`. The initial review caught
that activating a French locale alone did not load native translations. The final
test installs them and requires **Nouveau** before configuring the authority.
No implementation mismatch or scope creep remains.

## Rollout and limits

Update `pos_revolut` normally to load the changed views/field metadata and reload
the browser. Existing references, credential records and financial attempts are
unchanged. No key rotation or new configuration is required for this wording and
layout update; use the revised installation instructions for new setup or a
deliberate rotation.

This is local mocked Community 18 evidence. Hosted Enterprise/Odoo.sh lifecycle,
production acceptance and release-candidate assembly remain #80, #81 and #82.
The wording/layout change is relevant to the maintained Odoo 19 branch, but this
ticket changes and validates Odoo 18 only; Odoo 19 needs a separate branch-specific
adaptation and native UI check. This is not Odoo 19 compatibility evidence. No
production push or live financial operation was performed. Publishing to
`staging/18-enterprise` is the owner-authorized integration step; it does not
establish hosted acceptance.

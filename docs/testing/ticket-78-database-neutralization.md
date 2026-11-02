# Ticket 78 — Database copy safety

**Current maintenance target (2026-11-02):** `staging/18-enterprise`.
The original base and integration references below are historical; they do not
authorise further Enterprise work on the restored Community branch.

Local verification on 2026-11-02. Odoo 18 base/integration target:
`feat/v18_rev`, baseline `f1bb895ef32646ab4506eef05c7ca27c89dd11de`.
Application candidate: `7063c3f`; final test lifecycle correction: `bf97e8d`
(`18.0.1.0.7`), branch
`codex/78-safe-database-copies`.

## Behavior exercised

Actual Odoo `neutralize_database` executes the installed module's SQL hook
across two synthetic companies and both credential sources. Two executions
remove Production database keys, revoke Production authorities, archive live
methods and stop the addon crons. Sandbox keys and methods remain usable.
Terminal bindings retain their original identity and terminal integration.

Payment/refund fixtures create pending live attempts through public model
methods with mocked provider responses before neutralizing. Exact snapshots
preserve the unresolved payment, completed original sale, pending refund,
provider references, dispatch records, reservations and discovery evidence.
After repeated cleanup, valid-looking environment keys, unrevoked authorities,
unarchived methods and reactivated cron cannot cause production dispatch.
Public polling, cancellation, privileged reconciliation and connection checks
show the restriction. Retrying a pending return rediscovers the same pending
reservation with `retry_safe=False`. Sandbox discovery can still run.
Test-only SQL reactivation bypasses native open-session configuration freezes;
it represents reconfigured copied data and never changes financial evidence.

The independent runner `scripts/test-database-neutralization` installs native
POS/Restaurant, invokes the actual Odoo `neutralize` CLI and proves the addon
is uninstalled and its authority table absent. A fresh Odoo process installs
the addon. Public connection/payment checks reject newly entered database keys
and valid-looking environment keys with zero live HTTP or reservations. This
requires no earlier addon cleanup. Explicit sandbox setup succeeds. Both
fixtures check `staging`, `production` and missing `ODOO_STAGE` on neutralized
databases; existing stage-only regressions remain in the full addon suite.

## Commands and results

Pinned Odoo Community `18.0.20261015`, PostgreSQL `16.14`, synthetic credentials,
internal Compose networks and `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`. Only HTTP is
mocked; credential resolution, native model boundaries and neutralization are
real. There is no configured static type checker; Python compilation and Bash
syntax checks pass.

Temporary `/tmp/ticket78-runner/compose.yaml` uses the repository build context
and addon mount with internal subnet `10.237.178.0/24`; `compose-install.yaml`
uses `10.237.179.0/24`. Explicit internal subnets isolate the concurrent
fixtures. Repository network defaults are unchanged.

- Focused suite: **3 tests passed**, zero failures/errors on update
  (`/tmp/ticket78-focused.log`) and again on a **fresh installation** after
  moving the pending-payment case to post-install (`/tmp/ticket78-fresh-focused.log`).
  The helper asserts the addon is installed so its real SQL hook participates.
  The fresh run used the command below with `--database ticket78_fresh` and
  `--init pos_revolut` instead of the update arguments.

  ```bash
  docker compose --project-name odoo-revolut-ticket78 --file /tmp/ticket78-runner/compose.yaml run --rm odoo --database ticket78 --update pos_revolut --stop-after-init --workers 0 --max-cron-threads 0 --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO --test-tags /pos_revolut:TestRevolutNeutralization,/pos_revolut:TestRevolutPaymentCopies.test_neutralized_copy_preserves_payment_and_blocks_reactivation,/pos_revolut:TestRevolutRefund.test_neutralization_preserves_refund_identity_and_blocks_retry_and_cron
  ```

- First-install fixture: **passed**, exit 0. Log:
  `/tmp/ticket78-install.log` (final runner rerun in
  `/tmp/ticket78-install-final.log`).

  ```bash
  ODOO_REVOLUT_COMPOSE_FILE=/tmp/ticket78-runner/compose-install.yaml ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket78-install scripts/test-database-neutralization
  ```

- Payment fixture regression after the lifecycle correction: **45 tests passed**,
  zero failures/errors, exit 0. Log `/tmp/ticket78-payment-regression.log`.
  Same update command with `--database ticket78_fresh --test-tags
  /pos_revolut:TestRevolutPayment,/pos_revolut:TestRevolutPaymentCopies`.
- Full addon suite: **814 cases, zero failures/errors, one optional `pos_hr` skip,
  container exit 0**.
  Initial log `/tmp/ticket78-full.log`;
  complete container log `/tmp/ticket78-full-container.log`. The long-running
  command session disconnected (wrapper exit 130) while its Odoo container
  remained active. Continued the same run using `docker logs --follow` and
  `docker wait`; the final container exit is captured in `/tmp/ticket78-full-exit`.
  No suite restart or duplicated run was needed.

  ```bash
  docker compose --project-name odoo-revolut-ticket78 --file /tmp/ticket78-runner/compose.yaml run --rm odoo --database ticket78 --update pos_revolut --stop-after-init --workers 0 --max-cron-threads 0 --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO --log-handler odoo.tests:INFO --test-tags /pos_revolut
  ```

- `node --test --test-isolation=none pos_revolut/static/tests/*.test.mjs`:
  **146 passed**, zero failures. Log `/tmp/ticket78-js.log`.
- `python3 -m unittest discover -s tests -v`: **75 tests**, zero failures,
  three existing PDF dependency skips. Log `/tmp/ticket78-host.log`.
- `python3 -m compileall -q pos_revolut`,
  `bash -n scripts/test-database-neutralization` and `git diff --check`: passed.

Red/green: the first actual-neutralization test failed because usable live keys
remained (`/tmp/ticket78-red.log`); it passed after adding the SQL hook
(`/tmp/ticket78-green-cleanup.log`). The runtime regression then reproduced live
HTTP/allowed actions on a neutralized database labelled production or lacking
stage metadata (`/tmp/ticket78-red-guard.log`); the database-marker guard fixes
that behavior. Subsequent fixture corrections reactivated archived methods,
used privileged evidence creation, flushed deferred metadata writes and
allowed the unrelated sandbox discovery GETs without allowing live requests.
Inspection of pinned Odoo's module loader established that at-install tests run
before the module is marked installed. The copy payment case therefore runs
post-install using shared payment setup, and its helper asserts installed-module
participation. Fresh-install focused tests validate that correction. The full
run began on `7063c3f`; application code is identical in `bf97e8d`.
An initial first-install runner attempt encountered a local subnet collision;
the separate subnet resolved it.

## Standards

Independent review of `f1bb895...bf97e8d`: **0 findings**. Established Odoo SQL
hooks and model boundaries; no actionable standards violations or code smells.

## Spec

Independent review of `f1bb895...bf97e8d`: **0 findings**. Whole-database cleanup,
repeatability, immutable financial history, runtime restrictions, first-install
coverage and documentation satisfy the local ticket scope.

Standards: 0 findings. Spec: 0 findings.

## Limits and rollout

Update the addon normally before relying on its copy hook. For test copies use
Odoo's neutralization option/CLI, keep copied live attempts for reference and
create separate Sandbox authorities/methods/devices. Reconcile real uncertainty
in the original production environment. Raw PostgreSQL copies do not run Odoo
neutralization, and original backups still contain their original secrets.
No credential rotation is needed on the original production database.

This establishes local Community 18 behavior with mocked HTTP. Actual Odoo.sh
Enterprise copy/lifecycle verification remains ticket 80. No hosted deployment,
production branch push, live key use or financial request was performed.
Odoo 19 requires a separate version-branch change and verification.

# Ticket 77 — Company credential verification

Validated locally on 2026-10-30. Base: `bcc2f9395a931fae9f90e3d8979165ae2272e293`
from the latest reviewed `feat/v18_rev`. Final tested source:
`6fbea9d7a78e96a4684ef2679934c40079345f48` (`18.0.1.0.6`). Task branch:
`codex/77-company-credentials`; integration target: `feat/v18_rev`.

## Behavior exercised

System administrators create either environment-backed or database-backed
Merchant authorities and rotate to a new immutable authority/reference. POS
managers configure authorized references without authority/key access. Tests
exercise read, export, create, write and unlink restrictions through RPC,
manager/cashier field visibility and POS-loaded fields. Company/terminal tests
use two synthetic companies, three terminals and a manager allowed in both
companies. Foreign references and operation identifiers cannot redirect a key.

The real resolver authenticates mocked connection checks, payment preflight and
dispatch, final captured-payment verification, native sale completion, full and
partial refunds, report retrieval and scheduled payment/refund recovery. Pending
payments and historical refunds retain their original key after method rotation;
revocation rejects historical refund preflight without a replacement operation.
Database sources ignore competing same-named environment variables.

The historical-reconfiguration fixture bypasses native session closure only in
test setup to represent copied/legacy configuration changes. Normal Odoo prevents
closing an unresolved session or editing its methods. Refund allocation and
native checkout remain exercised through the public application interfaces.

## Test environment and commands

Pinned Odoo Community `18.0.20261015`, PostgreSQL `16.14`, internal Compose
networks, synthetic credentials and `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`.
Only provider HTTP is mocked; the credential resolver is not mocked.

The host's default Docker subnet pool was exhausted. `/tmp/ticket77-runner`
contains an unchanged copy of the repository scripts/docker context plus a
Compose copy with an explicit internal subnet. `ODOO_REVOLUT_ADDONS_DIR` mounts
the actual worktree read-only. Subnets: focused `10.237.77.0/24`, upgrade
`10.237.78.0/24`, full `10.237.79.0/24`. The temporary full runner additionally
enables test progress/statistics logging. No repository network defaults changed.

- Focused suite: **29 tests passed**, zero failures/errors, exit 0.

  ```bash
  source scripts/odoo-runtime
  ODOO_REVOLUT_ADDONS_DIR="$PWD" docker compose --project-name odoo-revolut-ticket77-focused-final --file /tmp/ticket77-runner/compose.yaml run --rm odoo --database odoo_revolut_tests --update pos_revolut --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO --test-tags /pos_revolut:TestRevolutDatabaseCredentials,/pos_revolut:TestRevolutDatabaseCredentialFlow,/pos_revolut:TestRevolutManagerUi,/pos_revolut:TestRevolutCredentialAuthority
  ```

  Log: `/tmp/ticket77-focused-pass.log`. The native configuration tours create
  and rotate a database authority, hide saved key input, retain the environment
  setup path and exercise manager configuration/connection with rejected key RPCs.
- Previous-revision upgrade: **passed**, exit 0.

  ```bash
  ODOO_REVOLUT_COMPOSE_FILE=/tmp/ticket77-runner/compose-upgrade.yaml ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket77-upgrade-final scripts/test-company-credential-upgrade
  ```

  Log: `/tmp/ticket77-upgrade-final.log`. Installs pinned `bcc2f93`, seeds
  environment authorities and completed/pending payment plus pending refund
  history, updates the addon in a fresh Odoo process, compares exact IDs and
  frozen fields, and polls payment/refund status using the original environment
  key. This ran against `0eaef44`; application code is unchanged through the final
  tested source above (subsequent changes corrected test fixtures only).
- Full addon suite: **811 cases, three failures, zero errors, one optional
  `pos_hr` skip**, exit 1. Log: `/tmp/ticket77-full.log`.

  ```bash
  ODOO_REVOLUT_ADDONS_DIR="$PWD" ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket77-full /tmp/ticket77-runner/scripts/test-addon-full
  ```

  All new credential cases passed. Existing checkout browser failures were
  `test_verified_card_first_rounds_only_the_remaining_cash` (overall script
  timeout), `test_verified_saved_refund_checkout_rejection_recovers_without_second_refund`
  (missing login control), and
  `test_verified_saved_refund_checkout_timeout_recovers_without_second_refund`
  (combined canonical-restoration assertion). **All three passed unchanged on
  isolated reruns**, zero failures/errors: two cases in `/tmp/ticket77-recheck.log`
  and the last in `/tmp/ticket77-recheck-timeout.log`. Exact tags are their names
  prefixed with `/pos_revolut:TestRevolutVerifiedCheckout.`. The first two used
  `test-addon-retain` with the same temporary Compose configuration; the last
  used a normal `--update pos_revolut` Odoo invocation on that retained database.

  Isolated rerun commands (the temporary `test-addon-retain` copy only omits
  exit cleanup so the third test can reuse the disposable database):

  ```bash
  ODOO_REVOLUT_ADDONS_DIR="$PWD" ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket77-recheck /tmp/ticket77-runner/scripts/test-addon-retain --test-tags /pos_revolut:TestRevolutVerifiedCheckout.test_verified_card_first_rounds_only_the_remaining_cash,/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_rejection_recovers_without_second_refund
  source scripts/odoo-runtime
  ODOO_REVOLUT_ADDONS_DIR="$PWD" docker compose --project-name odoo-revolut-ticket77-recheck --file /tmp/ticket77-runner/compose.yaml run --rm odoo --database odoo_revolut_tests --update pos_revolut --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO --test-tags /pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_timeout_recovers_without_second_refund
  ```

  The last assertion follows unchanged `pos.order.revolut_checkout_state` and
  does not invoke credential resolution. Its tour waits three seconds for a
  held response while restoration allows five seconds; the combined assertion
  does not identify which condition failed. Host load above 100 and full swap
  were observed during investigation, but root cause is **not established**.
  [Ticket 84](../tickets/needs-triage/84-investigate-checkout-browser-full-suite-failures.md)
  retains the follow-up. Isolated successes do not make the original full run
  green; obtain clean release-candidate evidence before release.
- `node --test --test-isolation=none pos_revolut/static/tests/*.test.mjs`:
  **146 passed**, zero failures. Log: `/tmp/ticket77-js.log`. Disabling process
  isolation exposes individual test counts on this host's Node 24 runner.
- `python3 -m unittest discover -s tests -v`: **75 run**, zero failures;
  three existing PDF dependency checks skipped. Log: `/tmp/ticket77-host.log`.
- Repeated `python3 -m compileall -q pos_revolut`, `git diff --check`,
  `bash -n scripts/test-company-credential-upgrade` and `node --check` on the
  changed tour: passed. There is no configured static type-checker in this repo.

Red/green evidence: the first database connection tracer failed on the absent
source field. SQL DEBUG and API DEBUG regressions reproduced key disclosure
before their fixes. Final logging tests exercise successful creation, duplicate
reference SQL errors, context-default keys and rejected writes without logging
keys; unrelated API logs remain enabled. Initial focused errors were fixture
setup issues (generic export permission/RPC shape, native closure guard, explicit
partial allocation and cron fixture permissions/extra HTTP response); they were
corrected without weakening production checks. An early full-suite run was
stopped after these fixture issues were found, before a final result.

## Standards

Independent review of `bcc2f93...6fbea9d`: no remaining documented-standard
violations or actionable baseline smells. The original documentation and RPC
logging findings were resolved. Server-side credential resolution and frozen
financial authorities remain in the established modules.

## Spec

Independent review of `bcc2f93...6fbea9d`: no outstanding spec findings. SQL/API
logging leaks and test isolation were corrected. Test follow-ups retain the real
resolver and original authority through recovery. No unrelated product scope.

Standards: 0 outstanding findings. Spec: 0 outstanding findings.

## Limits and rollout

This is local mocked Odoo Community 18 verification. It does not establish
Odoo.sh Enterprise lifecycle, copied-database cleanup or physical/live terminal
acceptance; those remain in tickets 78, 80 and 82. Odoo 19 requires its own
version-branch work. No hosted deployment, production branch update, live key
rotation or live financial request was performed.

Update the addon normally, then follow Installation's source/rotation procedure.
Existing authorities default to the environment source; no automatic key import
or authority replacement occurs. Database keys enter backups and masking is not
encryption. Keep original authorities/keys for historical reconciliation and
refunds. Do not release this slice alone before the copy/environment release gates.

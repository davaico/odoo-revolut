# 76 — Block real Revolut access on Odoo.sh test environments

**State:** closed

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](../ready-for-agents/75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None (can start immediately).

**External blockers:** None for local implementation and mocked verification.

## What to build

Make Odoo.sh staging and development reject real Revolut access consistently
through checkout, refunds, connection checks and scheduled reconciliation.
Users see an understandable restriction instead of a misleading terminal error.
Existing supported self-hosted production and sandbox workflows continue to work.

Keep the policy at the existing server-side application/transport boundary,
including the separate connection-check path. Any small consolidation needed to
apply the same policy belongs in this slice; no broad prefactoring project is
required. The policy must work before any database-copy cleanup exists and must
not depend on an absent secret or a disabled cron as its only protection.

## Acceptance criteria

- [x] Production Revolut HTTP is blocked before dispatch on staging/development
  for payment/refund creation, cancellation, status retrieval, connection checks
  and privileged payment/refund reconciliation.
- [x] Unrecognised Odoo.sh stages do not implicitly enable real operations.
  Supported self-hosted operation without Odoo.sh stage metadata remains
  explicit and functional; absence alone does not identify Odoo.sh production.
- [x] First installation after neutralization is protected even when valid-looking
  environment credentials exist. Browser input or ordinary configuration changes
  cannot bypass the server policy.
- [x] Blocking preserves original operation identities and uncertain states;
  it does not invent success, release reservations for an unsafe retry or send
  a replacement financial request.
- [x] Existing payment/refund/credential tests invoke real application methods
  with mocked HTTP and assert zero production dispatch for every blocked path.
  Allowed production/self-hosted and supported sandbox cases are also exercised
  with mocks, without contacting a real provider.
- [x] Focused UI checks cover understandable restriction feedback without keys
  or sensitive provider content; operating documentation explains the policy.

## Verification evidence

Implementation revision: `d0d5225` (`18.0.1.0.5`), based on
`a2dd13080e9e7027b330d63caf976ce6bb3145d3` from `feat/v18_rev`.
Task branch: `codex/76-block-live-revolut-test-builds`; integration target:
`feat/v18_rev`. No changes to `18.0` or hosted deployment.

The shared credential-resolution boundary protects normal Merchant HTTP and
the separate report transport; the connection check applies the same server
policy. Early application checks preserve existing attempts and show a typed,
sanitized restriction in POS. Cron searches exclude blocked environments before
their batch limits, including external refund discovery, while retaining live
identities, reservations, schedules and discovery evidence.

Local verification uses pinned Community `18.0.20261015`, PostgreSQL `16.14`,
mocked HTTP, `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1` and an internal Docker network.
The host's default subnet pool was exhausted: `/tmp/ticket76-test-addon` is a
temporary copy of `scripts/test-addon`, with the repository root fixed to this
worktree and an extra `--file /tmp/ticket76-compose.yaml` in its compose command.
That override only supplies `networks.default.ipam.config[0].subnet` as
`10.217.76.0/24`; no repository runner/network change was necessary.

Commands and results on 2026-10-30:

- Connection-policy red regression proved staging/dev/unknown/empty stages
  dispatched HTTP before the fix. The initial complete payment-method class
  then passed **15 tests**; the final suite also includes an allowed-stage matrix.
- A broader affected-class run exercised **139 tests**, with zero failures and
  one refund cron error. The error used a nonexistent refund environment field;
  corrected to use the original operation's frozen environment.
- Mixed-environment payment/refund batch regressions each failed before the
  pre-limit filters were added. The corrected cron and preservation run passed
  **5 tests**, zero failures/errors:

  ```bash
  ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket76 bash /tmp/ticket76-test-addon --test-tags /pos_revolut:TestRevolutRecoveryBatches.test_odoo_sh_blocked_live_attempts_do_not_starve_sandbox_payments,/pos_revolut:TestRevolutRecoveryBatches.test_odoo_sh_blocked_live_attempts_do_not_starve_sandbox_refunds,/pos_revolut:TestRevolutPayment.test_odoo_sh_preserves_production_attempt_during_poll_cancel_and_reconcile,/pos_revolut:TestRevolutRefund.test_background_reconciliation_and_reload_observe_late_completion,/pos_revolut:TestRevolutRefund.test_odoo_sh_preserves_pending_refund_and_discovery_evidence
  ```

- Native POS browser restriction check passed in the affected-class run:
  `TestRevolutVerifiedCheckout.test_odoo_sh_restriction_is_explained_without_terminal_or_secret_errors`.
  It asserts understandable sandbox/production guidance, no secret material,
  zero provider dispatch and no completed checkout.
- `node pos_revolut/static/tests/revolut_payment_state.test.mjs`: **143 passed**.
- `node pos_revolut/static/tests/refund_allowances.test.mjs`: **3 passed**.
- `python3 -m compileall -q pos_revolut`, `node --check` on both changed POS
  modules and the changed tour, and `git diff --check`: passed. No configured
  static type checker or lint command exists in this repository.
- Independent `/code-review` against `a2dd130...d0d5225`: **Standards 0 findings;
  Spec 0 findings**.
- The first full run was interrupted before its final summary. Its log recorded
  one existing declined-payment browser timeout at
  `TestRevolutVerifiedCheckout.test_declined_payment_can_retry_once_without_duplicate_charge`.
  Rerunning that exact test unchanged against the retained test database passed
  **1 test**, zero failures/errors (`/tmp/ticket76-decline-repro.log`). No assertion
  was relaxed and no speculative source fix was applied; the initial timeout's
  cause was not established.
- Clean full addon rerun: **796 tests, zero failures/errors, exit code 0** on
  the implementation revision. One optional `pos_hr` employee-list
  characterization was skipped (795 passed). Ran in detached
  container `odoo-revolut-ticket76-full`, using the same compose configuration,
  a fresh database, and the runner's normal init/test arguments. Progress and
  final statistics are enabled with `odoo.addons.pos_revolut.tests:INFO` and
  `odoo.tests.stats:INFO`; detached execution survives a chat interruption.
  `/tmp/ticket76-full-clean.log` retains the result. The previously timed-out
  declined-payment tour and the new Odoo.sh restriction tour both passed in
  this full run. Exact invocation after fresh DB startup and the Merchant HTTP
  guard check:

  ```bash
  docker compose --project-name odoo-revolut-ticket76 --file compose.yaml --file /tmp/ticket76-compose.yaml run --detach --name odoo-revolut-ticket76-full odoo --database odoo_revolut_tests --init pos_revolut --stop-after-init --workers 0 --test-tags /pos_revolut --log-level warn --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO --log-handler odoo.addons.pos_revolut.tests:INFO
  ```

Limits: mocked verification does not establish hosted Enterprise lifecycle or
live terminal acceptance. Those remain under #80/#82. This slice targets the
Odoo 18 branch; equivalent Odoo 19 changes require their version-branch work.
No credential rotation or database migration is needed; deploy/update the addon
and reload POS assets through the separately authorized release workflow.

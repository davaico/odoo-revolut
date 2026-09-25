# Ticket 10 staging health retry — TDD evidence

## Source and user journey

No separate plan file was used. The behavior was derived from the live staging
deployment: as an operator, I want the deployment health check to wait through
normal Odoo startup so a successful install is not reported as failed.

## RED and GREEN evidence

- RED: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_deploy_addon.TestRemoteDeploymentWorkflow.test_http_health_check_waits_for_odoo_startup`
  failed because the curl command had no retry flags.
- GREEN: the same command passed after adding bounded retries for connection
  refusal.
- Regression suite: `COVERAGE_FILE=/tmp/odoo-revolut-deploy-health.coverage PYTHONDONTWRITEBYTECODE=1 python3 -m coverage run --branch --include='scripts/deploy-addon,scripts/deploy-addon-remote' -m unittest discover -s tests -p 'test_deploy*.py'`
  passed all 18 tests.
- Coverage: the two deployment scripts reached 82% combined branch coverage;
  `scripts/deploy-addon-remote` reached 81%.

## Test specification

| What is guaranteed | Test | Type | Result |
|---|---|---|---|
| The HTTP health check retries a refused connection for a bounded startup window | `TestRemoteDeploymentWorkflow.test_http_health_check_waits_for_odoo_startup` | unit | PASS |
| A real service or HTTP failure still surfaces as a deployment error | `TestRemoteDeploymentWorkflow.test_health_failure_is_reported_after_successful_restart` | integration-style unit | PASS |
| Install, upgrade, backup, financial guards, immutable releases, and failure paths remain intact | `python3 -m unittest discover -s tests -p 'test_deploy*.py'` | regression | PASS |

## Merge evidence and known gap

The RED checkpoint is commit `74c8647`. The minimal GREEN fix and this report
are in the following commit. The remaining Ticket 10 gap is the operator-run,
no-charge cash POS smoke check recorded in the ticket.

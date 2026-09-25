# 11 — Verify the complete addon on the target Odoo version

**Work branch:** `codex/11-target-version-acceptance`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

The complete addon has repeatable acceptance evidence on the target Odoo version across retail, restaurant, recovery, reconciliation and refunds.

## Acceptance criteria

- [x] Run integrated model, frontend and browser acceptance against Odoo Community 19.0.20260908 with disposable databases and mocked Revolut HTTP. Existing per-ticket tests remain mandatory, not deferred to this ticket.
- [x] Cover fresh install/upgrade, retail without restaurant installed, restaurant checkout, split tender, decline/failure/cancellation, lost responses, late success and manager recovery.
- [x] Cover full/partial/allocated refunds, concurrent cashiers and refund requests, process crashes, stale reconciliation responses and an inactive browser.
- [x] Verify forged success and force-done paths cannot pay orders; company/session authorization and manager refund permissions are enforced; logs and browser data contain no secrets or sensitive cardholder data.
- [x] Exercise staging deployment guards with sale and refund operations. Confirm baseline cash checkout and unrelated payment methods retain normal behavior.
- [x] Publish exact test commands, results and remaining limits. CI may run reproducible checks and mocked tests only; unexpected real Merchant API access fails the suite.
- [x] Resolve integration defects before closure. Passing assets/build checks alone is not acceptance evidence, and mocked acceptance must not be described as live terminal certification.

## Verification evidence

On 2026-09-25, the assigned branch merged reviewed `origin/main` at `292a53b`,
which contains the closed 06, 09 and 10 implementations. All checks below ran
against disposable databases or local command mocks:

| Command | Result |
| --- | --- |
| `./scripts/test-addon --verify-install-upgrade` | Odoo Community package `19.0.20260908`: 129 tests passed on fresh install, 129 after addon upgrade, and 8 after Restaurant activation; zero failures/errors in every phase. |
| `./scripts/test-restart-recovery` | A committed pending payment recovered as verified in a second Odoo process; no charge replay. |
| `python3 -m unittest discover -s tests -p 'test_deploy_addon.py'` | 19 deployment tests passed, including sale and refund preflight blockers and the post-stop guard. |
| `bash -n scripts/test-addon scripts/test-restart-recovery` and `node --input-type=module --check < addons/pos_revolut/static/tests/tours/pos_revolut_acceptance.js` | Passed. Python test and guard files also passed `ast.parse`. |

The fresh-install phase runs retail without Restaurant installed. Browser tours
exercise verified payment, split Cash/Revolut payment, decline, failure,
cancellation, interruption, late success, manager configuration, full refund,
failed refund, lost refund response, ordinary Cash/Bank checkout, and Restaurant
table checkout after Restaurant activation. Model tests cover allocated partial
refunds, concurrent refund reservations and two distinct cashiers racing a
retry, process-crash points, stale reconciliation responses, scheduled recovery
without a browser, forged settlement, cross-company/session checks and
manager-only refund authority. The two-process check covers persisted restart
recovery. Deployment tests exercise both payment and refund blocker states.

Both disposable runners assert that unmocked `requests` calls to the sandbox or
production Merchant hosts raise before Odoo starts; the Compose network also
has no external route. A synthetic cardholder/PAN response was discarded from
the stored operation and POS model data. The full suite log was scanned for
those canaries and the test credential canary; none appeared.

## Remaining limits

All provider responses were mocked. No authenticated sandbox call, virtual or
physical terminal charge, or live refund was performed. The provisional
Merchant payload and actual terminal behavior remain subject to ticket 02 and
the controlled release evidence in ticket 12. The staging Cash smoke from
ticket 10 remains the only live checkout evidence; this ticket's payment and
refund deployment guards were exercised with disposable Odoo records and
mocked deployment commands. These results are not live terminal certification.

## Blocked by

- 06 — Resolve uncertain payments from a manager worklist
- 09 — Issue partial refunds across original payment allocations
- 10 — Install and upgrade a reviewed revision on staging

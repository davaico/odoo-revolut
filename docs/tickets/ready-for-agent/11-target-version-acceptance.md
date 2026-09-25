# 11 — Verify the complete addon on the target Odoo version

**Work branch:** `codex/11-target-version-acceptance`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-agent

## What to build

The complete addon has repeatable acceptance evidence on the target Odoo version across retail, restaurant, recovery, reconciliation and refunds.

## Acceptance criteria

- [ ] Run integrated model, frontend and browser acceptance against Odoo Community 19.0.20260908 with disposable databases and mocked Revolut HTTP. Existing per-ticket tests remain mandatory, not deferred to this ticket.
- [ ] Cover fresh install/upgrade, retail without restaurant installed, restaurant checkout, split tender, decline/failure/cancellation, lost responses, late success and manager recovery.
- [ ] Cover full/partial/allocated refunds, concurrent cashiers and refund requests, process crashes, stale reconciliation responses and an inactive browser.
- [ ] Verify forged success and force-done paths cannot pay orders; company/session authorization and manager refund permissions are enforced; logs and browser data contain no secrets or sensitive cardholder data.
- [ ] Exercise staging deployment guards with sale and refund operations. Confirm baseline cash checkout and unrelated payment methods retain normal behavior.
- [ ] Publish exact test commands, results and remaining limits. CI may run reproducible checks and mocked tests only; unexpected real Merchant API access fails the suite.
- [ ] Resolve integration defects before closure. Passing assets/build checks alone is not acceptance evidence, and mocked acceptance must not be described as live terminal certification.

## Blocked by

- 06 — Resolve uncertain payments from a manager worklist
- 09 — Issue partial refunds across original payment allocations
- 10 — Install and upgrade a reviewed revision on staging

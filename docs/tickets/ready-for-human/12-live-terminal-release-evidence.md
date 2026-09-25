# 12 — Validate real terminal payments and publish release evidence

**Work branch:** `codex/12-live-terminal-release-evidence`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-human

## What to build

Controlled real-terminal acceptance establishes whether the documented addon is ready for use, with traceable payment/refund evidence and complete operating instructions.

## Acceptance criteria

- [ ] Confirm the reviewed release includes completed corrections 16, 17 and 18, with recorded integrated mocked install, upgrade and Restaurant acceptance on the final combined revision, including verification of the delivered artifact, before starting live acceptance.
- [ ] Confirm the deployed revision, target Odoo version, merchant environment, location, eligible terminal and operator-authorized test amounts before financial tests. Use non-production testing where supported; separately obtain explicit authorization for any real-money operation.
- [ ] Validate successful full payment, split tender and retail/restaurant fulfilment using the confirmed contract. Demonstrate that only verified successful payment completes a fully paid order.
- [ ] Validate decline/failure/cancellation and interruption/late recovery with provider-supported controlled methods. Verify safe retry and duplicate prevention using actual provider transaction references; never deliberately create uncontrolled duplicate charges.
- [ ] Validate full and partial refunds through their asynchronous final outcome, preserving original and refund references. Reconcile all test charges and refunds.
- [ ] Record observed results, sanitized references, timestamps and any scenarios that cannot be reproduced. Unexecuted required acceptance scenarios remain open release gaps, not implied passes.
- [ ] Finalize fresh-install, configuration/secret rotation, cashier, manager reconciliation/refund, upgrade and troubleshooting instructions based on observed behavior.
- [ ] Close only after mandatory acceptance gaps and provider contract discrepancies are resolved. Keep credentials and sensitive cardholder data out of release evidence; no changes to hosting or parent issues.

## Blocked by

- 02 — Resolve the Revolut terminal contract and testing prerequisites
- 11 — Verify the complete addon on the target Odoo version
- 16 — Preserve uncertain refunds when original-sale recovery fails
- 17 — Deliver the Restaurant bridge with the reviewed addon release
- 18 — Isolate internal payment records by allowed company

## Release gate update — 2026-09-25

The owner approved the final audit corrections and required all three before
this ticket. The existing contract/access and target-version acceptance gates
remain in place. Ticket 02 can proceed independently while the software
corrections are implemented and verified.

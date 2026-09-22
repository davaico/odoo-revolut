# 06 — Resolve uncertain payments from a manager worklist

**Work branch:** `codex/06-manager-reconciliation-worklist`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `feat/project-definition` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**Status:** blocked

**Category:** Blocked

## What to build

POS managers inspect unresolved attempts and reconcile them with authoritative Revolut evidence, without bypassing payment verification.

## Acceptance criteria

- [ ] Provide a company-scoped manager worklist with original order/session, amount/currency, state, age, sanitized errors and available external references. Cashiers retain appropriate status visibility without manager resolution powers.
- [ ] Managers can request reconciliation and associate a missing external reference. Validate merchant/company, original order, amount, currency and existing ownership before accepting an association.
- [ ] Keep an audit trail of the actor, evidence reference, action, timestamp and resulting state. Never store raw sensitive provider payloads or credentials as evidence.
- [ ] No manual mark-paid or unsupported unlock action is available. Success requires server-verified payment; releasing a retry requires evidence that the prior operation cannot subsequently charge.
- [ ] If the outcome cannot be established, retain unresolved state and blocking, with an actionable support explanation rather than a guessed result.
- [ ] Tests cover valid lost-ID association, wrong amount/currency/order, cross-company access, reused references, unauthorized actions and inconclusive evidence. Demonstrate one unresolved attempt becoming verified through the worklist.
- [ ] Document the support procedure and the limits of manual intervention.

## Blocked by

- 05 — Recover payments after interruption or late success

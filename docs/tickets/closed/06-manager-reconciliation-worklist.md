# 06 — Resolve uncertain payments from a manager worklist

**Work branch:** `codex/06-manager-reconciliation-worklist`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

POS managers inspect unresolved attempts and reconcile them with authoritative Revolut evidence, without bypassing payment verification.

## Acceptance criteria

- [x] Provide a company-scoped manager worklist with original order/session, amount/currency, state, age, sanitized errors and available external references. Cashiers retain appropriate status visibility without manager resolution powers.
- [x] Managers can request reconciliation and associate a missing external reference. Validate merchant/company, original order, amount, currency and existing ownership before accepting an association.
- [x] Keep an audit trail of the actor, evidence reference, action, timestamp and resulting state. Never store raw sensitive provider payloads or credentials as evidence.
- [x] No manual mark-paid or unsupported unlock action is available. Success requires server-verified payment; releasing a retry requires evidence that the prior operation cannot subsequently charge.
- [x] If the outcome cannot be established, retain unresolved state and blocking, with an actionable support explanation rather than a guessed result.
- [x] Tests cover valid lost-ID association, wrong amount/currency/order, cross-company access, reused references, unauthorized actions and inconclusive evidence. Demonstrate one unresolved attempt becoming verified through the worklist.
- [x] Document the support procedure and the limits of manual intervention.

## Blocked by

- 05 — Recover payments after interruption or late success

## Verification evidence

Implemented on 2026-09-23 from reviewed `main` baseline `5fe365e`,
which includes closed blocker 05. The agreed test seam was Odoo manager model
actions and access rules. New attempts attach the original POS order and
payment-line UUIDs to Revolut order metadata. The manager worklist is scoped
to allowed companies, and association accepts only matching provider order
and intent evidence retrieved with the attempt's server-side Merchant
credential. Existing payment verification decides success and retry safety;
manager actions cannot mark a payment paid or clear a block.

A mocked lost create-order response was associated through a real manager
action and became verified only after a captured payment read. Tests also
rejected mismatched order/intent amount, currency, POS order, location and
terminal; reused references; cross-company access; and cashier actions.
An inconclusive provider read retained both blocking keys and recorded the
unresolved audit result. The worklist's sanitized error summary is selected
from fixed messages; unrecognized provider text is never displayed there. No automated test contacted Revolut.

Verification commands:

```bash
./scripts/test-addon --verify-install-upgrade
./scripts/test-restart-recovery
python3 -m unittest discover -s tests -v
python3 -m compileall -q addons/pos_revolut
git diff --check
```

The Odoo run reported **78 addon tests on clean install**, **78 on module
upgrade**, and **1 Restaurant startup browser test**, with zero failures or
errors. The two-process check reported `RESTART_SEED_OK` and
`RESTART_RECOVERY_OK`. Fourteen standalone tests and syntax checks passed.
No static typechecker is configured; Python compilation is not type checking.

Support steps and the limit for older attempts without POS UUID metadata are
in `docs/installation.md`. Upgrade the addon before using the worklist. No
credential rotation or live deployment was performed.

The two-axis code review identified one judgement-call duplication in
association guards and one partial worklist error-summary criterion. Both were
addressed with a shared guard and a tested sanitized error field.

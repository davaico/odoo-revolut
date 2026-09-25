# 03 — Complete one verified Revolut terminal payment

**Work branch:** `codex/03-verified-terminal-payment`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent

## What to build

A cashier selects Revolut for a full payment, sees progress, and gets automatic completion of the fully paid order only after the Odoo server verifies the actual payment succeeded.

## Acceptance criteria

- [x] Persist an operation linked to company, POS configuration/session, order UUID and payment-line UUID, with immutable amount/currency and external references. Duplicate starts return the same operation.
- [x] Persist and commit the operation and an atomic dispatch claim before HTTP dispatch; persist the result separately. Use explicitly owned transaction boundaries, never a commit on the caller’s ordinary Odoo transaction. Competing requests cannot dispatch the same action twice.
- [x] Create the Revolut order, verify the configured terminal is eligible, and push the intent. Convert decimal amounts into integer currency minor units using currency exponent rather than cash rounding. Use bounded HTTP timeouts and sanitized errors.
- [x] Poll through the Odoo server while checkout is active. Verify the underlying payment belongs to the expected order and matches amount and currency. Only captured/completed is success; intent completion and authorisation alone are insufficient.
- [x] Use Odoo 19 PaymentInterface and standard automatic terminal-payment validation. Save transaction references for support and reconciliation. Enable or clearly require automatic validation for the configured POS.
- [x] Guard the force-done UI path and enforce settlement during server order processing, rejecting forged client statuses, reused payment references and cross-company access. A verified payment cannot settle two orders.
- [x] Lost/malformed responses, unknown states and a crash after dispatch leave an unresolved operation. Block redispatch and conflicting charges on the affected order/terminal; do not automatically replay mutating requests. Keep unresolved status visible even before later recovery tickets.
- [x] Exercise the complete successful checkout with mocked HTTP and browser tests. Include double-click/concurrent start, currency conversion, intent-completed/payment-failed, reference mismatch, forged success and crash-after-dispatch tests. Document limitations until recovery is implemented.

## Blocked by

- 01 — Configure and verify a Revolut payment method

Ticket 01 closed on 2026-09-22; its implementation is the required baseline for
this ticket.

## Verification evidence

Implemented and reviewed on 2026-09-22 against Odoo Community
`19.0.20260908` and the provisional Revolut terminal contract recorded in this
repository. All Merchant API calls were mocked; no live terminal or financial
operation was used.

The verification run included:

```bash
python3 -m compileall -q addons
git diff --check
./scripts/test-addon --verify-install-upgrade
```

The full addon suite, mocked successful browser checkout, force-done guard,
clean install, module upgrade, retail POS startup and optional Restaurant POS
startup passed. Odoo emitted the known `websocket-client module is not
installed` browser-helper warning. Recovery, manager reconciliation, retries,
refunds, split tender and the unresolved retail fulfilment contract remain in
their follow-up tickets.

# 08 — Issue and reconcile a full Revolut refund

**Work branch:** `codex/08-full-revolut-refund`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent

## What to build

A POS manager returns a sale originally paid by one Revolut payment, with a linked refund that completes only after Revolut confirms it.

## Acceptance criteria

- [x] Use the normal Odoo return flow and enforce POS-manager authority on the server. Reject unrelated originals, cross-company references and unverified source payments.
- [x] Confirm the original Revolut order is eligible for refund. Persist an operation linked to the original payment and return, with immutable amount/currency and a stable idempotency key before dispatch.
- [x] Lock and reserve the refundable amount, including pending/uncertain operations. Repeated submissions reuse the same operation; never create a new key to bypass uncertainty.
- [x] Save the returned refund-order ID and original relationship. Acceptance alone remains pending; foreground and background reconciliation determine verified completion or failure.
- [x] Only a completed refund can complete its Revolut return payment line. Expose pending/failed/uncertain refunds and references to managers, including after reload, and do not silently substitute cash or another refund method.
- [x] Reuse the durable dispatch/recovery conventions and documented provider idempotency semantics; retain uncertainty where safe replay cannot be established.
- [x] Mocked model/browser tests cover full refund, duplicate submit, unauthorized user, failed refund, lost response, reload, late completion and simultaneous refund requests. Document the manager workflow.

## Blocked by

- 05 — Recover payments after interruption or late success

## Implementation

Implemented the full, single-payment manager return flow with an immutable
`pos.revolut.refund.operation` linked to the verified original payment and the
return UUID. Its committed dispatch claim reserves the original amount, carries
one stable idempotency key, and prevents concurrent or repeated submissions from
creating additional refunds. Charge/refund operations cannot share an order.

Original-line ownership, full quantities, prices, discounts, taxes, amount,
currency and manager authority are checked on the server. Only a matching
completed refund-order read can settle the negative POS payment. Pending,
failed and uncertain returns cannot be forced done or replaced with cash.

Foreground and scheduled read-only reconciliation support late completion and
lost-response recovery by exact merchant reference. Unknown associations remain
reserved; mutating requests are not replayed without established provider
retention guarantees. The manager worklist and POS retain original/refund
references. Reload restores the original sale-line relationships needed by
Odoo's normal return serialization.

See [manager workflow](../../installation.md#full-revolut-returns-pos-manager)
and [provider contract](../../revolut-refund-contract-2026-09-23.md).

## Standards

The independent review found no blocking implementation-standard violations or
actionable baseline code smells. It found one administrative inconsistency:
this ticket was claimed while the index still said Open. The index was corrected;
the final closure updates both the ticket and index together.

## Spec

The independent review found no missing or partial ticket requirements, scope
creep, or concrete incorrect behavior. Full single-payment returns remain the
boundary; partial and allocated refunds remain ticket 09.

Review totals: Standards 1 administrative finding, resolved; Spec 0 findings.
No remaining findings on either axis. Reviewed against baseline
`1d417dd9f97360f17a31664cafbf6a0626667fe2` after merging local reviewed `main` and
confirming blocker 05 was closed and implemented.

## Verification

On Odoo Community `19.0.20260908`, the final command
`./scripts/test-addon --verify-install-upgrade` passed **117 addon tests on
clean install**, **117 on upgrade**, and **7 Restaurant tests**, with zero
failures or errors. Browser tours exercised full refund, failed refund,
lost-response recovery after reload, duplicate status checks and late completion.
Model tests also exercised authorization, invalid/cross-company originals,
immutable details, cash-substitution and copied-reference rejection, scheduled
reconciliation, malformed recovery data and charge/refund exclusivity.
Independently committed transaction tests exercised simultaneous same-return and
competing-return requests, stale polling and process failure during dispatch.

The first full-refund model test and browser tour failed before their respective
implementations; the malformed-response and mixed-operation regressions were
also observed failing before correction. Focused tests were run during development.

Additional passing checks:

```bash
python3 -m unittest discover -s tests -v  # 14 deployment tests
python3 -m compileall -q addons/pos_revolut addons/pos_revolut_restaurant
node --check addons/pos_revolut/static/src/app/payment_revolut.js
node --check addons/pos_revolut/static/tests/tours/pos_revolut_acceptance.js
git diff --check
```

No static typechecker is configured; compilation/syntax checks are not type
checking. Coverage percentage was not measured. All Merchant API calls were
mocked in an isolated runtime without an external network route; no live
terminal or Merchant API operation was performed. Upgrade to `19.0.1.6.0` to
install the refund model, access rules, manager worklist and scheduled job.
No new credentials, credential rotation or payment-method fields are required.

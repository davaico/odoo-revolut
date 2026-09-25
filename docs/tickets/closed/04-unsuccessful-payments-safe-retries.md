# 04 — Handle unsuccessful payments and safe retries

**Work branch:** `codex/04-unsuccessful-payments-safe-retries`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

A cashier sees a distinct unsuccessful-payment outcome and can retry only when the previous attempt is conclusively safe to retry.

## Acceptance criteria

- [x] Display distinct declined, failed, cancelled, interrupted and timed-out outcomes without marking the sale paid. Separate provider-confirmed terminal outcomes from local transport failures.
- [x] Cancel only eligible pending intents and reconcile the result. Do not delete a payment line or report successful cancellation while cancellation is unresolved or payment may have succeeded.
- [x] Use a 60-second foreground waiting limit with approximately one-second status polling. On expiry, display unresolved status, preserve references and block a new charge; local timeout is not proof of provider failure.
- [x] Permit a new persisted attempt only after authoritative evidence makes retry safe. Keep prior attempts and references for audit; follow the confirmed provider rules for replacement orders/intents.
- [x] Handle cancel-versus-success races and repeated cancellation/start requests without duplicate financial operations. Keep the payment amount locked while an attempt is active.
- [x] Mocked model and browser tests cover decline, failure, cancellation, processing-time cancellation rejection, timeout, interruption, safe retry and cancellation races. Assert unsuccessful orders remain unpaid and unsafe retries perform no new dispatch.
- [x] Document cashier messages, retry eligibility and the unresolved-payment workflow.

## Blocked by

- 03 — Complete one verified Revolut terminal payment

## Verification evidence

Implemented on 2026-09-23 from reviewed integration baseline `a8f8ffb` after
confirming ticket 03 was closed. Test boundaries and the review baseline were
approved by the project owner. All Merchant API calls were mocked.

Focused verification exercised distinct failure outcomes, confirmed and rejected
cancellation, interruption and the 60-second foreground limit, duplicate requests,
amount/removal guards, explicit safe replacement attempts, and unsuccessful-sale
settlement rejection. Eight actual Chrome checkout tours passed. Three tests used
independent PostgreSQL transactions to exercise simultaneous retries and both
orderings of cancellation versus successful payment verification.

The Standards review found no actionable violations or smells. The Spec review
identified a cancellation/verification race and legacy retry eligibility; both
were fixed with failing-then-passing regression tests and re-reviewed with no
remaining findings. The legacy tests cover provider-confirmed failure and local
terminal-check failure with no mutating dispatch.

A separate disposable database installed the addon from `a8f8ffb`, stored a
cancelled attempt using its old schema, and upgraded to `19.0.1.2.0`. Its references
and audit history survived; status checking recognized the confirmed failure, and
repeated replacement requests created exactly one new attempt and dispatch pair.

Actual browser execution revealed that earlier warning-only runs had skipped
tours because `websocket-client` was absent. The owner approved the test-only
`python3-websocket` dependency. The runner now fails early if it is missing. The
test filestore survives install/upgrade containers and is removed on cleanup.
Cashier-only server configuration reads, Odoo payment-line UI initialization, and
previously unexercised manager-tour fixtures were corrected during verification.

Static checks: Python compilation, JavaScript syntax checks, XML parsing and
`git diff --check` passed. No static type-checker or linter is configured in this
Odoo repository; compilation is not reported as type checking. Fourteen deployment
tooling tests also passed. No production deployment or credential rotation was
performed; upgrade the module before using the new flow.

Final verification commands:

```bash
python3 -m compileall -q addons
node --check addons/pos_revolut/static/src/app/payment_revolut.js
node --check addons/pos_revolut/static/tests/tours/pos_revolut_acceptance.js
python3 -m unittest discover -s tests -v
./scripts/test-addon --verify-install-upgrade
git diff --check
```

The final complete run reported **56 addon tests on clean install** and **56 on
module upgrade**, with zero failures or errors in either phase, plus **1 passing
Restaurant POS startup browser test** after installing the optional module. This includes the actual manager-configuration tour,
retail POS startup, eight checkout tours and all three concurrent-RPC cases. Odoo
reported no test failures or errors. The expected Restaurant-only case is skipped
until the restaurant module is installed; Chrome child-process cleanup warnings
do not indicate skipped tours.

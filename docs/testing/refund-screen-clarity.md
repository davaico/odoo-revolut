# Refund screen clarity

## Request and scope — 2026-10-05

The operator could not tell whether a blank Pos Order meant the original
purchase was missing, or whether Outstanding meant a card refund was still
processing. The acknowledgement button cleared a review flag without creating
or checking any product, stock, cash or accounting work. The requested outcome
is a concise refund screen using ordinary sales language.

The list now shows Original Sale, Odoo Return, amount, Refund Status and Source.
The form keeps these business facts first, with technical references under
Details. Source distinguishes Odoo POS from Detected in Revolut without claiming
who initiated an observed refund. Refund titles include the amount and original
sale. Original-sale links remain directly accessible.

The acknowledgement button and native-reconciliation fields are absent from
the customer-facing refund views. Stored historical fields and their protected
backend action remain for compatibility. This release does not turn an
acknowledgement into proof that stock or accounting has been reconciled.

The existing refund/recovery operations retain their permission, persistence,
idempotency and financial verification checks. No product selection or return
quantity is guessed from a provider money refund. No real payment, refund or
product return is part of this change.

## Verification

Runtime candidate: `bcb02045931633436bbd419cce0f79722937bc7f`;
review base: `3dd7affc7c078c9dbaa88c562a59e43e9807c80e`.

- Full mocked installation on initial candidate `649f554`: **493 tests passed**.
- Full mocked upgrade on final candidate `bcb0204`: **493 tests passed**.
- Fresh installation of the final candidate with external-refund and native
  retail POS startup checks: **45 tests passed**.
- Node payment-state suite: **88 tests passed**, including the cancellation
  changes already merged into main. `git diff --check` passed.
- Independent Standards and Spec reviews: **zero remaining findings**. The
  initial Spec finding that an external refund hid Odoo Return was corrected;
  the final form shows that blank link and explains it explicitly.

Commands: `scripts/test-addon --verify-install-upgrade`,
`scripts/test-addon --test-tags
'/pos_revolut:TestExternalRefunds,/pos_revolut:TestRevolutRetailPosStarts'`,
and `node --test --test-reporter=tap --test-isolation=none
addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`.
Local logs: `/tmp/refund-screen-clarity-full.log`,
`/tmp/refund-screen-clarity-fresh.log`, `/tmp/refund-screen-clarity-node.log`.
Provider HTTP is mocked in automated tests.

Guarded staging deployment and live list/form inspection remain to be recorded.

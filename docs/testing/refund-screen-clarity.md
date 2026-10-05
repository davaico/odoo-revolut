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

## Staging rollout — 2026-10-05

PR #51 merged the reviewed change. The standard guarded upgrade deployed exact
runtime source `bcb02045931633436bbd419cce0f79722937bc7f` as **19.0.1.15.4**.
Configuration backup: `/var/backups/odoo-revolut-deploy/20261005T134700Z-bcb020459316`.
The active addon resolves to that immutable release; Odoo is active and
`/web/login` returns HTTP 200.

Read-only before/after SQL confirms seven refund records with identical ledger
fingerprint `961d377b434210d34d6685542a2c8f3f`, zero deployment blockers,
native return 24 still `paid` at **-£0.02**, and GBP register 2 still retail.
The module version is the only changed baseline value. Logs:
`/tmp/refund-screen-clarity-before.log`, `/tmp/refund-screen-clarity-after.log`,
`/tmp/refund-screen-clarity-deploy.log`.

Authenticated live UI inspection confirms the default list has six business
columns and seven completed rows, without Outstanding, native reconciliation
or acknowledgement controls. External refund 10 shows its readable title,
original sale 000018 link, £0.01, Completed, Detected in Revolut, a blank
Odoo Return and the explicit explanation that product quantities are unknown.
Its references remain readable under Details. Odoo refund 5 shows its original
sale and restored paid return 24 as separate links, without recovery/status
buttons for this completed record. Screenshot:
`/tmp/refund-screen-clarity-live.png`.

No acknowledgement, product return, financial POST or accounting adjustment
was performed. The unknown actor behind the external penny is not inferred.
The operator reported no products need returning. Removing a review label does
not manufacture native stock/accounting evidence. Future manager-confirmed
external native completion is separately specified in ticket 41.

Ticket 12 remains open for the remaining physical acceptance scenarios and
final test-money reconciliation; the restored receipt is already complete.

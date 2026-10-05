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

Pending scoped Odoo install/upgrade, existing refund regressions, independent
review, guarded staging upgrade and live list/form inspection.

# Payment vocabulary

Terms used by the Odoo POS–Revolut integration.

## Payments

**Authorized cart**: Sale contents and permitted pricing approved by the server.
_Avoid_: Browser total.

**Base payment allocation**: Cart balance assigned to one tender, excluding its terminal-selected tip.
_Avoid_: Gross card charge.

**Payment attempt**: Recorded collection of one allocation through a specific terminal and Merchant account, retaining its identity through recovery.
_Avoid_: Order.

**Payment intent**: Revolut terminal interaction; completion does not establish successful payment.
_Avoid_: Proof of payment.

**Uncertain outcome**: Payment or refund awaiting a confirmed provider outcome; its allocation remains reserved.
_Avoid_: Failed payment.

**Terminal-selected tip**: Extra amount chosen by the customer on the terminal before payment.
_Avoid_: Payment overage.

**Cashier-entered tip**: Tip entered in Odoo before terminal payment.
_Avoid_: Terminal-selected tip.

**External refund**: Refund initiated outside the addon; recording its Odoo return or accounting correction is separate work.
_Avoid_: New refund request.

## Documents

**Revolut payment receipt**: Card-payment receipt issued by Revolut.
_Avoid_: POS sales receipt.

**POS sales receipt**: Odoo record of the sale and tenders, possibly including Revolut references.
_Avoid_: Revolut payment receipt.

**Accounting invoice**: Accounting document for an invoiced sale; payment alone does not create it.
_Avoid_: Receipt.

**Reprint**: Another copy of an existing receipt, with no new financial transaction.
_Avoid_: Repayment, retry.

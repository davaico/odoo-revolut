# Odoo Revolut

This context covers Odoo Point of Sale payments and refunds through Revolut terminals, and the documents associated with those transactions.

## Language

**Authorized cart**:
The sale contents and permitted pricing approved by the Odoo server as the basis for collecting payment.
_Avoid_: Browser total, verified payment.

**Base payment allocation**:
The part of an authorized cart's balance assigned to one tender, excluding a separately verified terminal-selected tip.
_Avoid_: Gross card charge when referring to the goods balance.

**Payment attempt**:
A recorded effort to collect one allocation through a particular terminal and Merchant account, retaining its identity through interruption and reconciliation.
_Avoid_: Order when referring to the collection attempt.

**Payment intent**:
The Revolut terminal interaction associated with collecting a payment. Its completion is distinct from successful settlement of the underlying payment.
_Avoid_: Proof of payment.

**Uncertain outcome**:
A payment or refund whose final provider outcome has not been established. Its financial allocation remains reserved until reconciliation resolves it.
_Avoid_: Failed payment merely because waiting ended.

**Terminal-selected tip**:
An optional amount the customer chooses on the Revolut terminal before card payment, distinct from the base payment allocation.
_Avoid_: Payment overage, post-payment adjustment.

**Cashier-entered tip**:
A tip entered in Odoo before terminal payment starts. This is a native Odoo concept; the Revolut flow currently requires terminal-selected tips instead.
_Avoid_: Terminal-selected tip.

**External refund**:
A refund initiated outside this addon and later observed through Revolut. Its verified movement of money is distinct from the native Odoo return or accounting work needed to record it.
_Avoid_: New refund request when completing its native records.

**Revolut payment receipt**:
The customer-facing proof of a card payment issued by Revolut, including the terminal's printed or digital receipt.
_Avoid_: Accounting invoice, POS sales receipt.

**POS sales receipt**:
The Odoo document describing a POS sale and its payment tenders. A printed Revolut reference does not make it the original Revolut payment receipt.
_Avoid_: Revolut payment receipt, accounting invoice.

**Accounting invoice**:
The accounting document associated with an invoiced sale. A successful POS payment does not itself establish that an invoice exists.
_Avoid_: Terminal receipt, card-payment receipt.

**Reprint**:
Producing another copy of an existing transaction's receipt without initiating or changing its financial transaction.
_Avoid_: Repayment, retry.

# Odoo–Revolut

This context covers Odoo Point of Sale payments and refunds through Revolut terminals, and the customer documents associated with those transactions.

## Language

**Revolut payment receipt**:
The customer-facing proof of a card payment issued by Revolut, including the receipt printed by its terminal or supplied digitally. This is the document meant by the client's request to retrieve and reprint an older terminal transaction.
_Avoid_: Invoice, facture, POS sales receipt when referring to this document.

**POS sales receipt**:
The Odoo document describing a POS sale and its payment tenders. Including a Revolut payment reference does not make it the original Revolut payment receipt.
_Avoid_: Revolut payment receipt, accounting invoice.

**Accounting invoice**:
The accounting document associated with an invoiced sale, distinct from a POS sales receipt and a Revolut payment receipt. A successful POS payment does not by itself establish that an accounting invoice exists.
_Avoid_: Terminal receipt, card-payment receipt.

**Reprint**:
Producing another copy of an existing transaction's receipt without initiating another payment or changing the original financial transaction.
_Avoid_: Repayment, retry.

**Authorized cart**:
The sale contents and permitted pricing that the Odoo server has approved as the basis for collecting payment. A saved draft or a cashier browser total alone is not an authorized cart.
_Avoid_: Browser snapshot, verified payment when referring to approval of the cart

**Base payment allocation**:
The part of an authorized cart's balance assigned to one tender. A customer-selected terminal tip is separate from this allocation and cannot pay another part of the goods balance.
_Avoid_: Gross card charge when referring to the allocated cart balance

**Terminal-selected tip**:
An optional amount the customer explicitly chooses on the Revolut terminal before presenting payment. It is distinct from a cashier-entered Odoo tip and from a change to a payment after capture.
_Avoid_: Payment overage, post-payment adjustment

**Cashier-entered tip**:
An explicit tip entered in Odoo before a terminal payment starts. It is already part of the cart total, so recording it as payment metadata does not add another amount due.
_Avoid_: Terminal-selected tip

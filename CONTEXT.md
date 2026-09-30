# Odoo–Revolut

This context covers Odoo Point of Sale payments and refunds through Revolut terminals, and the customer documents associated with those transactions.

## Language

**Revolut payment receipt**:
The customer-facing proof of a card payment issued by Revolut, including the receipt printed by its terminal or supplied digitally. This is the document meant by the client's request to retrieve and reprint an older terminal transaction.
_Avoid_: Invoice, facture, POS sales receipt when referring to this document.

**Odoo-generated Revolut payment receipt**:
A customer-facing payment receipt produced by Odoo from verified Revolut payment data for a payment processed through this integration. It is distinct from Revolut's original terminal document and from Odoo's itemized POS sales receipt.
_Avoid_: Original Revolut receipt, accounting invoice.

**Odoo-generated Revolut refund receipt**:
A customer-facing document produced by Odoo for a verified completed refund through this integration, linked to its original payment. It records that refund independently of the original payment receipt, which remains available.
_Avoid_: Pending refund confirmation, accounting credit note, original Revolut receipt.

**POS sales receipt**:
The Odoo document describing a POS sale and its payment tenders. Including a Revolut payment reference does not make it the original Revolut payment receipt.
_Avoid_: Revolut payment receipt, accounting invoice.

**Accounting invoice**:
The accounting document associated with an invoiced sale, distinct from a POS sales receipt and a Revolut payment receipt. A successful POS payment does not by itself establish that an accounting invoice exists.
_Avoid_: Terminal receipt, card-payment receipt.

**Reprint**:
Producing another copy of an existing transaction's receipt without initiating another payment or changing the original financial transaction.
_Avoid_: Repayment, retry.

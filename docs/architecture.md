# Architecture

Odoo owns cart authorization, register access, credentials, financial requests and verification. The POS browser is untrusted. The terminal collects card payments and optional tips; Merchant secrets stay on the server.

## Payment lifecycle

1. Save the draft, check required pickup scheduling, and derive prices, taxes and tender amounts on the server.
2. Authorize the cart and reserve the selected base allocation.
3. Persist dispatch ownership, create a Revolut order and send a terminal payment intent.
4. Verify the underlying successful payment and authenticated report: gross, base and tip, including explicit zero-tip evidence. Intent completion alone is insufficient.
5. Apply the verified tender and tip to the original order. Complete native POS checkout when fully paid and validation requirements are satisfied.

Persisted attempts, references, dispatch claims and immutable financial snapshots distinguish undispatched requests from lost responses. Uncertain outcomes retain reservations; mutating requests are not automatically replayed. Concurrent status readers share the recorded observation.

Recovery retains the original company, register, Merchant authority, currency, amount, order and tender. Current configuration cannot redirect historical reconciliation. Backend-user register grants authorize interactive actions; employee selection only supplies attribution.

Pickup time remains editable outside financial identity. On Odoo 18, the addon supplies preset and pickup scheduling controls; native Odoo owns checkout validation; correcting scheduling after capture preserves the original payment and its recovery actions.

## Refund lifecycle

Reserve original quantities and tender capacity before requesting a refund. Completed, pending and uncertain allocations count against limits; base and tip remain separate. Only verified success settles the native negative tender.

External discovery records refunds against known payments but cannot infer returned goods. Managers complete or associate native returns, or record financial-only accounting corrections. These actions send no new refund.

## Source map

Paths below are relative to `pos_revolut`, the addon directory.

| Area | Files |
| --- | --- |
| Credentials and access | `models/merchant_credential.py`, `models/pos_config.py` |
| Cart and pricing | `models/cart_authorization.py`, `models/cart_pricing.py`, `models/financial_snapshot.py` |
| Configuration and dispatch | `models/pos_payment_method.py`, `models/revolut_payment_operation.py` |
| Payment observation and tips | `models/payment_observation.py`, `models/terminal_tip.py` |
| Refunds | `models/return_allocation.py`, `models/revolut_refund.py` |
| External refunds | `models/external_refund_discovery.py`, `models/external_refund_completion.py` |
| Native settlement | `models/pos_order.py` |
| POS interface | `static/src/app/payment_revolut.js`, `static/src/app/revolut_payment_state.js`, `static/src/app/restaurant_revolut.js` |
| Permissions and reconciliation | `security/`, `data/revolut_reconciliation_cron.xml` |
| Odoo and browser tests | `tests/`, `static/tests/` |

Root `tests/` covers test tooling; `scripts/` contains the runners. See [Contributing](../CONTRIBUTING.md) for commands.

## Vocabulary

| Term | Meaning |
| --- | --- |
| Authorized cart | Sale contents and permitted pricing approved by the server. |
| Base payment allocation | Cart balance assigned to one tender, excluding its terminal-selected tip. |
| Payment attempt | Recorded collection of one allocation through a specific terminal and Merchant account, retaining its identity through recovery. |
| Payment intent | Revolut terminal interaction; completion does not establish successful payment. |
| Uncertain outcome | Payment or refund awaiting a confirmed provider outcome; its allocation remains reserved. |
| Terminal-selected tip | Extra amount chosen by the customer on the terminal before payment. |
| Cashier-entered tip | Tip entered in Odoo before terminal payment. |
| External refund | Refund initiated outside the addon; recording its Odoo return or accounting correction is separate work. |
| Revolut payment receipt | Card-payment receipt issued by Revolut. |
| POS sales receipt | Odoo record of the sale and tenders, possibly including Revolut references. |
| Accounting invoice | Accounting document for an invoiced sale; payment alone does not create it. |
| Reprint | Another copy of an existing receipt, with no new financial transaction. |

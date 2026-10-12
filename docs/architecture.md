# How POS Revolut works

The browser is an untrusted POS client. Odoo owns cart authorization, register access, credentials, dispatch, financial verification, and refund reservations. The Revolut terminal collects the customer's card payment and optional tip. The browser never receives Merchant secrets or makes authenticated Merchant API calls.

## Payment lifecycle

1. Save the native draft and derive permitted prices, taxes, and tender amounts on the server.
2. Record an authorized cart and reserve the selected base allocation before dispatch.
3. Persist dispatch ownership, create a Revolut order, and push a terminal payment intent.
4. Observe the intent and underlying payment. A completed intent alone is not proof of payment.
5. Verify a successful final payment and an authenticated payment-report row proving the gross, base, and tip amounts, including an explicit zero tip.
6. Apply the verified tender and tip to the original order. Native POS completion still requires the full balance and its own validation rules.

Provider requests and local database updates cross failure boundaries. Persisted attempts, references, dispatch claims, and immutable financial snapshots let Odoo distinguish a safe undispatched retry from a request whose response was lost. Uncertain outcomes retain their reservation; mutating requests are not replayed automatically. Concurrent status readers share the recorded observation.

Each operation retains its original company, register, Merchant authority, currency, amount, order, and tender identity. Changing current configuration does not redirect historical reconciliation to a different Merchant account. Interactive operations require explicit backend-user register access; employee selection supplies attribution, not authorization.

## Refund lifecycle

Odoo refunds reserve quantities and original tender capacity before sending the request. Completed, pending, and uncertain reservations count toward the ceiling. Only a verified successful refund can settle its native negative tender. Base and terminal-tip components remain separate.

External refund discovery records provider evidence against known original payments. It cannot infer the returned goods from the amount. Managers separately complete or associate native returns, or record the required financial-only accounting correction. Discovery and reconciliation do not create another refund.

## Source map

All addon paths below are relative to `addons/pos_revolut`.

| Area | Main files |
| --- | --- |
| Credentials and register access | `models/merchant_credential.py`, `models/pos_config.py` |
| Cart preparation and pricing | `models/cart_authorization.py`, `models/cart_pricing.py`, `models/financial_snapshot.py` |
| Terminal configuration and dispatch | `models/pos_payment_method.py`, `models/revolut_payment_operation.py` |
| Payment observation and tips | `models/payment_observation.py`, `models/terminal_tip.py` |
| Refund allocation and verification | `models/return_allocation.py`, `models/revolut_refund.py` |
| External refunds and native completion | `models/external_refund_discovery.py`, `models/external_refund_completion.py` |
| Native settlement guards | `models/pos_order.py` |
| POS interface | `static/src/app/payment_revolut.js`, `static/src/app/revolut_payment_state.js`, `static/src/app/restaurant_revolut.js` |
| Permissions and background reconciliation | `security/`, `data/revolut_reconciliation_cron.xml` |
| Runtime and browser coverage | `tests/`, `static/tests/` |

Root `tests/` covers supporting tools; root `scripts/` provides test runners. [Contributing](../CONTRIBUTING.md) explains how to exercise these paths with provider HTTP blocked.

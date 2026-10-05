# Odoo–Revolut Terminal Integration

This repository is the single source of truth for an installable Odoo 19 Point of Sale addon connecting Odoo POS to a Revolut payment terminal through the Revolut Merchant API. The single `pos_revolut` addon includes terminal payments, refunds and Restaurant checkout guards. It depends on Odoo’s standard `pos_restaurant` addon; retail registers can continue to use retail mode.

## Cashier Experience

```text
Cashier selects Revolut in Odoo POS
                 ↓
Amount appears on the Revolut terminal
                 ↓
Customer completes the card payment
                 ↓
Odoo verifies the result and completes the sale
```

If the payment is declined, failed, cancelled, interrupted, or times out, the sale must remain unpaid. The cashier must receive a useful result and be able to retry without creating a duplicate charge.

## Repository Boundaries

The sibling `../odoo-hosting` repository creates and manages the Odoo development environment in which this addon will be installed and tested. It must not contain integration code. Product code, tests, installation instructions, and integration documentation belong here and must not be developed directly on an Odoo server.

## Required Capabilities

- Add a configurable Revolut payment method to Odoo POS.
- Send the correct amount and currency to a selected Revolut terminal.
- Track the terminal interaction and verify the underlying payment result.
- Complete the Odoo sale only for Revolut's successful final payment states.
- Keep unsuccessful or uncertain attempts unpaid and support safe retries.
- Save Revolut order, payment-intent, payment, and refund references needed for reconciliation.
- Support full and partial refunds without duplicate refund processing.
- Keep Merchant API credentials and all authenticated API calls on the Odoo server.
- Provide automated tests and instructions for installing the addon in a fresh Odoo environment.

## Integration Flow

The integration is server-to-server; both Odoo and the terminal require internet access. The terminal must be in Pay at Counter mode and assigned to the same physical Revolut location used for the order.

For each attempt, the Odoo server creates a Revolut order, finds an available terminal, pushes a payment intent, and polls the intent while it is pending or processing. A `completed` payment intent only means the terminal interaction finished—it does not prove that payment succeeded. Odoo must retrieve the related payment and wait for a final payment state. Only `captured` or `completed` completes the Odoo sale; `declined`, `failed`, and `cancelled` leave it unpaid. Timeouts and connection interruptions remain uncertain until reconciled against Revolut.

Amounts sent to Revolut use minor currency units. Each attempt must be persisted before polling, and retry logic must reconcile previous attempts to prevent duplicate charges. Refund requests must be linked to the original transaction and use a stable idempotency key where supported.

## Delivery and Acceptance

1. Prepare a dedicated Odoo 19 environment through `../odoo-hosting`.
2. Build the complete installable addon in this repository.
3. Install it into the development environment without moving its source of truth.
4. Validate successful, declined, cancelled, failed, interrupted, timed-out, and retried payments, plus transaction references and full/partial refunds.

The project is ready when the addon installs in a new Odoo environment, a cashier can complete an end-to-end terminal payment, unsuccessful payments remain unpaid, retries cannot duplicate charges, references are recorded, refunds work, and setup is documented here.

## Development Documents

- [Installation and configuration](docs/installation.md) covers administrator-managed register grants, secret provisioning, terminal setup, rotation, and the pinned disposable test environment.
- [Odoo 19 and Revolut API validation](docs/api-validation-2026-09-22.md) records the verified extension points, API operations, and remaining contract uncertainties that implementation must respect.
- [Revolut terminal contract and testing readiness](docs/revolut-terminal-contract-2026-09-22.md) reconciles the terminal guide with API version `2026-08-17`, records the sandbox route and idempotency limits, and names the external prerequisites that remain unresolved.
- [Development environment](docs/development-environment.md) describes the live staging target, repository boundaries, and the intended local development and deployment workflow.
- [Staging deployment and recovery](docs/staging-deployment.md) provides the reviewed-revision deployer, no-charge smoke check, and payment-safe recovery order.
- [Ticket 12 release evidence and operator checklist](docs/testing/ticket-12-release-evidence.md) records combined mocked acceptance and remaining physical-terminal and financial checks.

## Implementation References

### Revolut

- [Push payments to a Revolut Terminal](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
- [Merchant API reference (2026-08-17)](https://developer.revolut.com/docs/api/merchant/2026-08-17)

### Odoo 19

- [POS `PaymentInterface`](https://github.com/odoo/odoo/blob/19.0/addons/point_of_sale/static/src/app/utils/payment/payment_interface.js)
- [Official Stripe terminal frontend example](https://github.com/odoo/odoo/blob/19.0/addons/pos_stripe/static/src/app/payment_stripe.js)
- [Official Stripe terminal backend example](https://github.com/odoo/odoo/blob/19.0/addons/pos_stripe/models/pos_payment_method.py)

See [AGENTS.md](AGENTS.md) for development and security rules.

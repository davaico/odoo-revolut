# Odoo 19 / Revolut validation — 22 September 2026

Scope: official upstream source and documentation review. No authenticated API calls, terminal operations, staging inspection, or runtime tests were performed. Odoo references follow the moving `19.0` branch; compatibility with the deployed revision still needs testing.

## Odoo extension points confirmed

- Subclass `PaymentInterface`; implement `sendPaymentRequest(uuid)` and `sendPaymentCancel(order, uuid)`. Reversal is a separate optional operation, not the normal refund flow. Some interface comments retain obsolete snake_case names and an old registration import path. [Interface source](https://raw.githubusercontent.com/odoo/odoo/19.0/addons/point_of_sale/static/src/app/utils/payment/payment_interface.js).
- The working adapter imports `register_payment_method` from `@point_of_sale/app/services/pos_store`, calls server methods through `this.pos.data.call`, sets payment-line status with `setPaymentStatus`, and stores `transaction_id`. Negative payments have a separate refund path. Use its integration conventions, not Stripe-specific credential or capture behavior. [Stripe adapter](https://raw.githubusercontent.com/odoo/odoo/19.0/addons/pos_stripe/static/src/app/payment_stripe.js).
- Extend `pos.payment.method._get_payment_terminal_selection()` and `_load_pos_data_fields(self, config)`. Export only safe configuration fields to POS. [Backend example](https://raw.githubusercontent.com/odoo/odoo/19.0/addons/pos_stripe/models/pos_payment_method.py).
- Register frontend assets in `point_of_sale._assets_pos`. [Manifest](https://raw.githubusercontent.com/odoo/odoo/19.0/addons/pos_stripe/__manifest__.py).
- Automatic order validation requires successful payment, a fully paid order, `auto_validate_terminal_payment`, and no refund in progress. `sendForceDone` can mark a line done independently. Implementation consequence: guard Revolut's UI path and enforce verified settlement on the server; frontend status alone cannot authorize a sale. Cancellation must return success only when confirmed safe. [Payment screen](https://raw.githubusercontent.com/odoo/odoo/19.0/addons/point_of_sale/static/src/app/screens/payment_screen/payment_screen.js).

## Revolut contract confirmed

Use server-side Bearer authentication and explicitly pin `Revolut-Api-Version: 2026-08-17`.

| Operation | Endpoint / request |
| --- | --- |
| Create order | `POST /api/orders`; amount and currency |
| Discover terminals | `GET /api/terminals?operation_mode=pos&location_id=…` |
| Push intent | `POST /api/orders/{order_id}/payment-intents`; integer `amount`, `terminal_id` |
| Read intent | `GET /api/payment-intents/{id}` |
| Cancel intent | `POST /api/payment-intents/{id}/cancel`; pending only |
| Verify payment | `GET /api/payments/{payment_id}` |
| Refund | `POST /api/orders/{order_id}/refund`; amount, currency, stable `Idempotency-Key` |

Intent responses identify the intent, order, terminal, amount, currency and state; `payment_id` is optional until available. The published create-order and create-intent headers do not document idempotency keys. Absence of documentation is not proof of rejection, but we cannot rely on deduplication. [Versioned API reference](https://developer.revolut.com/docs/api/merchant/2026-08-17).

The terminal guide requires a physical location, matching terminal location, Pay at Counter mode, and terminal app 1.56+. Order fields include `channel: pos`, `location_id`, `capture_mode: manual`, `fulfilment_type: eat_in|take_away`, and `metadata.pos_partner_name`. Amounts use minor units. The terminal handles capture; intent completion does not establish payment success. Only payment `captured` or `completed` is success; transitional states require continued reconciliation. The guide suggests one-second polling and a bounded wait. It also requires encrypted credential storage; an ordinary plaintext Odoo field would not satisfy that guidance. [Terminal guide](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments).

Refunds require a completed original order and create a separate refund order linked by `related_order_id`. Store its ID and monitor completion; an accepted request is not a completed refund. Multiple partial refunds cannot exceed the original paid amount. [Refund guide](https://developer.revolut.com/docs/guides/merchant/operations/refunds).

## Remaining uncertainty and implementation consequences

1. The terminal guide includes `channel` and `fulfilment_type`, but the versioned create-order field list omits them. Use the terminal guide as the provisional contract; confirm acceptance with Revolut or a controlled integration test before claiming live compatibility. The linked downloadable schema could not be retrieved through the documentation browser.
2. Lost create-order/intent responses remain ambiguous. Persist and commit attempts before dispatch, serialize competing operations, and block new charges until reconciled. Do not invent an idempotency guarantee or assume an empty payment list means no active intent. Recovery when an intent ID is lost needs explicit design and testing; unresolved cases require manual reconciliation.
3. A follow-up review found that the terminal guide now documents sandbox push
   payments through a fixed virtual terminal and amount-driven simulated
   outcomes. The project has not authenticated to the sandbox or observed that
   behavior. See the
   [terminal contract and testing-readiness record](revolut-terminal-contract-2026-09-22.md)
   for the reconciled contract, remaining retail ambiguity and access gates.

Next implementation step: define the persisted attempt/reconciliation contract and mocked failure cases, then scaffold the addon using the verified Odoo hooks. Do not downgrade these remaining uncertainties to confirmed facts.

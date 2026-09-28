# Revolut Terminal contract — 22 September 2026

Scope: authoritative Revolut documentation, the official versioned OpenAPI
definition and authorized non-financial Sandbox probes. Documentation was
first reviewed on 22 September 2026; the observed-behavior and readiness record
was updated on 28 September 2026. Statements below distinguish
**documented**, **observed**, **owner-decided** and **unresolved** behavior.

## Sources

- [Push payments to Revolut Terminal](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
- [Merchant API reference, version 2026-08-17](https://developer.revolut.com/docs/api/merchant/2026-08-17)
- [Official 2026-08-17 OpenAPI definition](https://github.com/revolut-engineering/revolut-openapi/blob/master/json/merchant-2026-08-17.json)
- [Set up a test environment with Revolut Sandbox](https://developer.revolut.com/docs/guides/merchant/test-and-go-live/set-up-sandbox)
- [Get started with the Revolut Terminal](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/get-started)
- [Revolut Terminal additional features](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/additional-features)
- [Refund payments](https://developer.revolut.com/docs/guides/merchant/operations/refunds)

The OpenAPI filename pins the API contract version, but the linked repository
branch is moving. This record therefore also carries its review date.

## Evidence activity log

| Date | Activity and source | Outcome | Limitations |
| --- | --- | --- | --- |
| 2026-09-22 | Reviewed the official terminal guide, versioned Merchant API reference, official OpenAPI definition, sandbox guide and refund guide linked above | Established the documented contract, sandbox route and unresolved schema/retail conflicts recorded below | Documentation only; the OpenAPI repository branch can move after this review date |
| 2026-09-28 | Sandbox access and location setup, operated by Gary — tester | Confirmed Sandbox Merchant access, secure off-repository secret storage and creation of a `physical` Merchant location | No credential value is recorded; the Sandbox dashboard address workflow failed, so the location was created through the Merchant API |
| 2026-09-28 | Authenticated create-order probes using API version `2026-08-17` | `eat_in` and `take_away` were accepted; omitting fulfilment was rejected as invalid `SERVICE`; omitting `channel` was accepted by order creation | Runtime acceptance does not define the business meaning of retail, and the channel-omitted order was not used to claim terminal compatibility |
| 2026-09-28 | Two Sandbox virtual-terminal flows at documented success amounts `100` and `101` minor GBP units | Both intents stayed `pending`; each underlying payment appeared under its order and reached `failed` after approximately 8–9 seconds with no decline reason or bank message | The documented successful outcome was not observed; no real funds or physical terminal were involved |
| 2026-09-28 | Read-only payment reconciliation probes | `GET /api/orders/{order_id}/payments` exposed each failed payment even while its intent returned `payment_id: null`; direct payment retrieval confirmed `failed` | This establishes a diagnostic/reconciliation source, not an idempotency or replay guarantee |
| 2026-09-28 | Sandbox virtual-terminal and dashboard inspection | Terminal discovery returned the fixed virtual terminal online but with no reported operation mode or location; the Sandbox Merchant Devices page failed to load | The operator could not verify or change virtual-terminal location/Pay at Counter settings |
| 2026-09-28 | Provider clarification request | Revolut API Support acknowledged the request; a substantive answer is pending | The reply remains useful but no longer blocks the local contract record |

## Order payload contract and the remaining contradiction

The terminal guide documents this server-side order shape for push payments:

```json
{
  "amount": 2500,
  "currency": "GBP",
  "channel": "pos",
  "location_id": "<physical-location-uuid>",
  "fulfilment_type": "eat_in",
  "capture_mode": "manual",
  "metadata": {
    "pos_partner_name": "<pos-name>"
  }
}
```

**Documented:** the guide calls `channel: "pos"`, `location_id`,
`capture_mode: "manual"`, `fulfilment_type` and
`metadata.pos_partner_name` required for push payments. It lists only
`eat_in` and `take_away` for `fulfilment_type`. The versioned create-intent
operation independently says that the source order must have
`channel: "pos"` and a `location_id`. Amounts are integer minor units.

**Contradiction:** `Order-Creation-v7` in Revolut's official 2026-08-17
OpenAPI definition includes `location_id`, `capture_mode` and `metadata`, but
does not define either `channel` or `fulfilment_type`. Its only required fields
are `amount` and `currency`. The create-order operation also does not expose
those two fields in the rendered request-field list.

The resulting evidence by business context is:

| Context | Evidence-backed payload | Confidence |
| --- | --- | --- |
| Restaurant, eat-in | The guide's payload above with `fulfilment_type: "eat_in"` | Guide-documented and accepted by the controlled Sandbox create-order probe; absent from the versioned schema |
| Restaurant, takeaway | The same payload with `fulfilment_type: "take_away"` | Guide-documented and accepted by the controlled Sandbox create-order probe; absent from the versioned schema |
| Retail | Use `fulfilment_type: "eat_in"` as the project owner's interim mapping | Owner-decided and runtime-accepted; Revolut documents no retail-specific value, so this must not be represented as provider-confirmed semantics |

The probes reconcile the guide/schema discrepancy for this project: keep
sending `channel: "pos"` because the terminal guide and payment-intent
prerequisites require it, even though order creation accepted its omission.
Always send one of the two accepted fulfilment values. For retail, the owner has
chosen `eat_in` until Revolut publishes a distinct rule or corrects the API.
That decision enables controlled acceptance; it does not redefine Revolut's
published restaurant terminology.

## Terminal capture and success contract

**Documented:** standard push-payment orders use `capture_mode: "manual"`, but
the terminal guide says the terminal automatically handles capture or
cancellation according to the transaction outcome. This does not make an
ordinary terminal payment a merchant-managed pre-authorisation. The separate
pre-authorisation flow additionally sets
`authorisation_type: "pre_authorisation"` and leaves later capture management
to the merchant.

A `completed` payment intent proves only that checkout on the terminal
finished. It supplies a `payment_id`; the server must retrieve that payment and
continue reconciliation through transitional states. Only payment state
`captured` or `completed` is success. `declined`, `failed` and `cancelled` are
unsuccessful final outcomes. No Odoo sale may complete from intent state alone.

The guide suggests polling an intent every second with a bounded timeout in
its flow description, while its checklist uses 2–3 seconds and gives 90 seconds
as an example. Those values are recommendations, not a provider guarantee.
Timeout or a lost response remains uncertain until reconciled.

### Observed Sandbox state-propagation defect and reconciliation

Two controlled probes showed the same unexpected behavior. The virtual
terminal created an underlying payment almost immediately, and that payment
reached final state `failed`, but the related intent stayed `pending` with an
unchanged `updated_at` and `payment_id: null`. The failed payments had neither
`decline_reason` nor `bank_message`; the Business Sandbox UI described a
technical error.

The official `GET /api/orders/{order_id}/payments` endpoint returned the
underlying payment and its final state in both cases. This is useful defensive
evidence when an intent remains transitional, but it does not authorize blind
replay: one order can have multiple payment attempts, and the integration must
match persisted order, amount, currency and known timing/references before
applying an outcome. Empty or inconsistent results remain unresolved.

## Location, mode and device prerequisites

The documented production prerequisites are:

- an approved Revolut Merchant account and server-side Secret API key;
- Revolut Terminal app version 1.56 or higher;
- a `physical` location (online locations do not work for push payments);
- the order and terminal assigned to the same `location_id`;
- the terminal logged into the same Revolut Business account, online and
  connected to the internet;
- Pay at Counter enabled; terminal discovery filters
  `operation_mode=pos` and the matching `location_id`; and
- Merchant API requests pinned to `Revolut-Api-Version: 2026-08-17`.

The integration is server-to-server. Both Odoo and the terminal need internet
access; there is no Bluetooth or cable protocol between them.

## Controlled testing route

**Documented:** Revolut now explicitly supports this push-terminal flow in its
Merchant Sandbox. Sandbox and production accounts and credentials are
independent. A sandbox account can be registered and a Sandbox Merchant Secret
API key generated without affecting live operations. Requests use
`https://sandbox-merchant.revolut.com`.

Terminal discovery in sandbox returns one virtual terminal with ID
`11111111-0000-0000-0000-000000000000`. The terminal guide documents these
minor-unit outcomes:

| Amount | Simulated outcome |
| --- | --- |
| Any amount not matched below | Successful payment |
| `3500`, or `2000` through `2299` | Insufficient funds |
| `4000`, or `2300` through `2499` | Transaction not allowed for cardholder |
| `2500` through `2699` | Suspected fraud |

This is the documented non-financial route for controlled success and decline
tests, including order creation, virtual-terminal discovery, intent creation
and final payment-state verification. The 2026-09-28 probes successfully
exercised access, location creation, payload validation, terminal discovery,
intent creation, cancellation and final-payment retrieval. They did not
produce the documented successful outcome: both nominal-success amounts ended
as technical payment failures while their intents stayed pending.

The failure is reproducible and isolated to the Sandbox terminal path rather
than 3DS, manual capture or missing polling. No additional Sandbox payment
attempt should be made until Revolut corrects or explains the simulator.

Production evidence remains a separate later activity. Revolut recommends
testing both sandbox and production before rollout; no production request or
small-value charge is authorized by this document.

## Idempotency guarantees and limits

These operations must be treated separately:

| Operation | Published `Idempotency-Key` support | Documented guarantee and limits | Safe consequence |
| --- | --- | --- | --- |
| `POST /api/orders` | None in the endpoint headers or OpenAPI operation | No deduplication guarantee is published | Do not automatically replay after an ambiguous response |
| `POST /api/orders/{order_id}/payment-intents` | None in the endpoint headers or OpenAPI operation | No deduplication guarantee is published | Do not automatically replay after an ambiguous response; reconcile or require manual handling |
| `POST /api/orders/{order_id}/refund` | Optional | The shared header definition says a request is processed only once for retries or duplicates. The key may be any unique string and has a maximum length of 50 characters. | Persist one stable key before dispatch and reuse it for the same logical refund |

For refunds, Revolut does not document the retention period, namespace/scope,
or behavior when the same key is reused with a different payload. It also does
not document whether failures are cached. The optional header is therefore a
useful explicit guarantee within its stated bounds, not a substitute for
persisting and reconciling the returned refund order.

An absent header in the create-order or create-intent contract is not proof
that Revolut rejects it; it is proof that this integration cannot rely on it.
Neither a locally generated reference nor an HTTP `409` response creates an
undocumented replay guarantee.

## Sandbox access readiness and observed evidence

The repository contains no credential values. Current readiness is:

| Prerequisite | Readiness on 28 September 2026 | Responsible operator |
| --- | --- | --- |
| Merchant Sandbox account and Secret API key | Confirmed; secret stored securely outside the repository | Gary — tester |
| Sandbox physical location suitable for the virtual-terminal flow | Confirmed through Merchant API creation | Gary — tester |
| Sandbox virtual terminal | Returned online and accepted intents, but location/mode metadata were absent and the Devices page failed | Gary — tester |

Sandbox and production are separate. Ticket 2 records only the documented
production prerequisites: a production Merchant account and independent
credential, a matching physical location, Terminal app version 1.56 or later,
an online device and Pay at Counter mode. It does not assess a particular
production account or physical device.

## Scope closure and downstream handoff

Ticket 2 closes with the documented contract, observed Sandbox behavior,
owner-decided interim retail mapping and reproducible simulator limitation.
Physical-terminal setup, production terminal discovery and every real payment
or refund scenario are outside this record and remain ticket 12 work.

A later Revolut response about the Sandbox bug or retail terminology should
amend this record, but it does not reopen the completed local verification
slice automatically.

## Retry and cancellation implementation check — 23 September 2026

Rechecked the official terminal guide and API reference linked above. Only
pending intents are cancellable. The guide requires a new order after an intent
is cancelled; it permits retry after a final unsuccessful payment and a new
intent after a failed intent. This addon uses a fresh order and intent for every
safe replacement attempt, preserving the previous attempt and references.

Cancellation acknowledgements are followed by retrieval and payment verification
when a payment reference exists. Local transport failure and the 60-second POS
waiting limit do not authorize a replacement. No live calls were made.

# Revolut Terminal contract — 22 September 2026

Scope: authoritative Revolut documentation and the official versioned OpenAPI
definition, reviewed on 22 September 2026. No authenticated API request,
sandbox mutation, physical-terminal operation or financial operation was
performed. Consequently, every statement below is either **documented** or
**unresolved**; there is no observed provider behavior in this record.

## Sources

- [Push payments to Revolut Terminal](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
- [Merchant API reference, version 2026-08-17](https://developer.revolut.com/docs/api/merchant/2026-08-17)
- [Official 2026-08-17 OpenAPI definition](https://github.com/revolut-engineering/revolut-openapi/blob/master/json/merchant-2026-08-17.json)
- [Set up a test environment with Revolut Sandbox](https://developer.revolut.com/docs/guides/merchant/test-and-go-live/set-up-sandbox)
- [Refund payments](https://developer.revolut.com/docs/guides/merchant/operations/refunds)

The OpenAPI filename pins the API contract version, but the linked repository
branch is moving. This record therefore also carries its review date.

## Evidence activity log

| Date | Activity and source | Outcome | Limitations |
| --- | --- | --- | --- |
| 2026-09-22 | Reviewed the official terminal guide, versioned Merchant API reference, official OpenAPI definition, sandbox guide and refund guide linked above | Established the documented contract, sandbox route and unresolved schema/retail conflicts recorded below | Documentation only; the OpenAPI repository branch can move after this review date |
| 2026-09-22 | Provider clarification | None available or requested from this environment | No provider case or written answer exists to resolve the retail contract |
| 2026-09-22 | Controlled sandbox or terminal probe | Not performed | No assigned operator or confirmed Merchant access; no payload acceptance or outcome was observed |

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
| Restaurant, eat-in | The guide's payload above with `fulfilment_type: "eat_in"` | Guide-documented, not exercised; absent from the versioned schema |
| Restaurant, takeaway | The same payload with `fulfilment_type: "take_away"` | Guide-documented, not exercised; absent from the versioned schema |
| Retail | No authoritative retail `fulfilment_type` or omission rule was found | Unresolved; do not map retail to `eat_in` or `take_away` |

These restaurant payloads are the provisional mocked-development contract,
not evidence of runtime acceptance. A controlled sandbox probe or written
Revolut clarification must establish whether the 2026-08-17 endpoint accepts
the guide-only fields and what retail must send. Until then, production retail
compatibility must not be claimed.

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

This provides a non-financial route for controlled success and decline tests,
including order creation, virtual-terminal discovery, intent creation and
final payment-state verification. It also provides the appropriate place to
probe the guide/schema contradiction once an authorized sandbox operator and
credentials are available. The claims above are documentation findings only:
no sandbox account access, payload acceptance or simulated outcome was observed
during this review.

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

## Access readiness and observed evidence

The repository contains no credential values, named responsible operator or
evidence that the following external prerequisites are currently available:

| Prerequisite | Readiness on 22 September 2026 | Responsible operator |
| --- | --- | --- |
| Merchant Sandbox account and Secret API key | Unconfirmed | To be assigned |
| Sandbox physical location suitable for the virtual-terminal flow | Unconfirmed | To be assigned |
| Production Merchant access | Unconfirmed | To be assigned |
| Matching production physical location | Unconfirmed | To be assigned |
| Physical Terminal, app 1.56+, in Pay at Counter mode | Unconfirmed | To be assigned |

Ticket 01's mocked terminal check and the staging host's unauthenticated DNS/TLS
check do not establish any of these facts. No credentials should be added to
this record when an operator is assigned.

## External dependencies before ticket closure

This verification slice remains open pending all of the following:

1. Revolut clarification or an authorized sandbox probe for acceptance of
   `channel` and `fulfilment_type` on `POST /api/orders` with API version
   2026-08-17.
2. An authoritative retail rule: a valid retail value, or confirmation that
   `fulfilment_type` must be omitted. No restaurant value may be repurposed.
3. Assignment of a responsible operator and confirmation of Sandbox Merchant
   access for the non-financial contract probes.
4. For the later physical acceptance session, confirmation of production
   Merchant access, a matching physical location, and an eligible Terminal in
   Pay at Counter mode at app version 1.56 or higher.

Mocked development may proceed with the restaurant payloads clearly marked as
provisional, with retail behavior left unimplemented or explicitly blocked,
and with ambiguous create-order/create-intent outcomes never auto-replayed.

## Retry and cancellation implementation check — 23 September 2026

Rechecked the official terminal guide and API reference linked above. Only
pending intents are cancellable. The guide requires a new order after an intent
is cancelled; it permits retry after a final unsuccessful payment and a new
intent after a failed intent. This addon uses a fresh order and intent for every
safe replacement attempt, preserving the previous attempt and references.

Cancellation acknowledgements are followed by retrieval and payment verification
when a payment reference exists. Local transport failure and the 60-second POS
waiting limit do not authorize a replacement. No live calls were made.

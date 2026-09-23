# Refund contract — 23 September 2026

Official references reviewed for the mocked ticket 08 implementation:

- [Merchant API 2026-08-17](https://developer.revolut.com/docs/api/merchant)
- [Refund payments guide](https://developer.revolut.com/docs/guides/merchant/operations/refunds)

A refund requires a completed original order. POST
`/api/orders/{original_id}/refund` accepts minor-unit amount, currency and an
`Idempotency-Key`; it creates an order with `type: refund` and
`related_order_id` linking it to the original. The implementation persists its
amount, currency, original payment, return snapshot and key before dispatch.
It sends the key as `merchant_order_data.reference` as well as in the header.
A successful POST remains pending until GET of that refund order confirms
completion and matching identity, original relationship, amount and currency.

The current API documents deduplication with the key but does not establish a
retention window in the reviewed reference. We therefore do not replay a
mutating refund request after a lost response or process interruption, even
with the original key. Read-only recovery uses the order-list filter
`merchant_order_data_reference`, accepts only one exact reference match, then
retrieves and verifies the refund order. No match or ambiguity retains the
reservation and uncertainty. Provider retention/replay guarantees remain a
live-contract question for ticket 02, not an invented retry guarantee.

Mocked tests exercise these contracts; this is not live Merchant API or physical
terminal acceptance. Full single-payment returns are ticket 08's boundary;
partial and allocated refunds remain ticket 09.

# 69 — Apply durable tender removal to Odoo 19

**State:** open

**Category:** bug

**Triage:** needs-triage

**Work branch:** prospective Odoo 19 task branch based on maintained `main`.

**Base and integration target:** Odoo 19 `main`. Transplant only reviewed changes;
do not merge older private history into sanitized `feat/v18_rev`.

## Source finding

[Ticket 68](../closed/68-investigate-duplicate-revolut-line-after-reload.md)
reproduces an Odoo 18 draft reload restoring a removed cancelled tender alongside
an unsent allocation. A source assessment of maintained Odoo 19 found the same
missing durable-removal boundary. Native removal queues closure-local commands;
IndexedDB serialization omits those maps, and startup rereads saved server
orders. Ordinary safely cancelled addon removal falls through to native local
deletion. The existing recovery endpoint returns operation history even when
removal was requested, and cart-delta reconstruction omits recovered history
when the last native Revolut tender is gone.

These are source findings, not an Odoo 19 rendered reproduction or verified fix.
The [synthetic investigation](../../testing/ticket-68-draft-reload.md) records
native source locations and the Odoo 18 correction and testing boundaries.

## Acceptance criteria

- Reproduce the cancellation, removal, unsent allocation, zero/back edits and
  reload with native Odoo 19 browser persistence and mocked Merchant responses
  before choosing the correction. Capture UUIDs, saved identities and membership.
- Adapt durable, idempotent retirement using the existing server ownership and
  history guards. Keep uncertain/verified tenders protected and original
  operation/dispatch history intact. Send no collection during recovery.
- Preserve canonical saved amounts when a locally editable amount differs,
  including zero; support offline/lost retirement replies and repeat refresh.
- Finish the original cancelled foreground request without publishing a delayed
  result onto a removed tender. Preserve native cart deltas after retirement.
- Validate existing saved-unstarted recovery, cancellation, legitimate distinct
  tenders and split checkout; do not deduplicate by method and amount.
- Run narrow Odoo 19 regressions and the full suite, recording actual limitations.

## Dependencies and boundaries

The Odoo 18 investigation establishes a reusable synthetic scenario. An Odoo 19
failing reproduction is still required; no physical terminal or live requests
are needed. Apply the version's native APIs deliberately. Odoo 19 already uses
its `payment_ids` command map correctly: do not copy the Odoo 18-specific map-key
correction. This follow-up authorizes no deployment, live financial action or
mutation of protected acceptance records.

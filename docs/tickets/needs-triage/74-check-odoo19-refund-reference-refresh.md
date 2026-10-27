# 74 — Check Odoo 19 refund references after native refresh

**Work branch:** Odoo 19 `main` (separate from `feat/v18_rev`).

**State:** open

**Triage:** needs-triage

## Scope

Ticket 73 found that native related-record loading can erase restored refund
transaction references while retaining a successful browser recovery flag.
Odoo 19 has the same restored-flag fast path, but the exact native sequence has
not been reproduced on that version. Do not claim Odoo 19 is affected or fixed
solely from the Odoo 18 result.

## Acceptance criteria

- [ ] Reproduce or rule out the native saved-tender refresh sequence on Odoo 19.
- [ ] If reproduced, preserve verified references and payment status for every
  tender on a multi-refund return, without a new financial request.
- [ ] Keep server validation and order/tender identity guards intact.
- [ ] Run relevant mocked regressions and record evidence.

Coordinate with ticket 71's existing waiting-refund recovery work. This is a
separate version-maintenance check; it does not reopen passed V18 physical tests.

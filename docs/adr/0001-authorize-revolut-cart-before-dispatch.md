# Authorize a persisted Odoo cart and verify terminal-selected tips

Ticket 26 selects a validated native Odoo draft plus a server-owned immutable base-cart authorization and an atomic tender ledger. The customer selects an optional tip on the Revolut terminal before card payment; Odoo verifies that tip separately using the documented asynchronous `payments_report`, then projects it into the native order and gross tender once. Persistence enables checkout/recovery; permitted-input validation, Odoo tax calculation and provider tip evidence establish financial authority. The [implementation contract](../revolut-cart-authorization.md) records pinned-source evidence, state behavior and ticket 27 acceptance cases.

**Status:** accepted design, 2026-09-30; implementation belongs to ticket 27.

Owner decisions recorded in the ticket 26 chat:

- Terminal-selected tips are required and were the original intended tipping flow. This supersedes the initial assumption that Odoo pre-entry would suffice. Base cart remains frozen under exposure; a server-only append of a proven terminal tip is a separate projection, not a general edit or post-capture adjustment.
- Customers may choose explicit optional terminal tips within provider limits. The cashier 25%/authenticated-manager policy applies only to the separate Odoo-entered tip lane; it cannot prevent a customer selection after capture. Avoid double prompting/counting.
- Captured payments may remain awaiting report tip details, with bounded waiting, status/reload recovery and no second charge. Instant checkout/report availability is not assumed.
- Preserve unrestricted cashier prices. With native Price Control on, require authenticated Odoo POS manager approval for restricted overrides, including those entered by advanced POS employees. Browser employee/PIN/role values are not server approval.
- Native Restaurant post-payment tip adjustment remains unsupported for Revolut. It is distinct from the required terminal prompt during checkout.

A separate quote without a native draft would duplicate native persistence, shared recovery and settlement binding while requiring the same validation. An unchecked persisted total or signed browser snapshot would fail to establish authority. The selected approach keeps the draft and adds immutable versions. It deliberately adds authenticated manager approval to restricted POS HR overrides because native verification runs in the browser.

The full official OpenAPI schema documents `tip_amount` in payments-report CSV, not ordinary payment retrieval. The contract applies the documented all-payments report to terminal payments with exact identity/amount checks; this is an explicit inference that needs target-device release acceptance, not an invented synchronous field. Missing/ambiguous tip evidence remains exposed. Table-only moves stay operational context. Unknown outcomes retain reservations through expiry/reload/closure, and terminal tips never pay another base allocation.

No material design decision remains for ticket 27. This is an approved implementation contract, not remediation evidence. Ticket 27 must deliver the complete guarded checkout, tip projection, receipt/refund compatibility and regressions; deployment and physical-terminal acceptance remain separate.

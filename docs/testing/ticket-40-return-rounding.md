# Ticket 40 — Conserve partial-return rounding

Reviewed baseline: `3dd7affc7c078c9dbaa88c562a59e43e9807c80e` (fetched `origin/main`, 2026-10-05).
Branch: `codex/40-conserve-partial-refund-rounding`. Addon: `19.0.1.16.0`.

## Reproduction

The public manager refund RPC regression uses a real native sale, mocked Merchant HTTP, saved return drafts and `sync_from_ui` finalization. A fixed archive of reviewed main with the regression test refunds the first quarter for 309, finalizes it, then fails because source discovery offers 926 rather than the remaining 925. A first fixture using raw floating browser totals also exposed an unrounded stored total (-3.085 versus a -3.09 tender); the final regression uses the normal currency-rounded browser total. No live Merchant API or terminal is involved.

## Allocation contract

Each original line has a frozen monetary ceiling, with the existing base/tip and original cash-rounding decomposition retained. For a new return, subtract the quantities and cents belonging to earlier active return claims, then round the requested share of the remaining cents over the remaining quantity. Returning the entire residual quantity receives the entire residual entitlement. For 1234 cents, quarters receive 309, 308, 309 and 308. Three quarters first receive 926 and the last quarter 308. This residual rule is deliberate: a cumulative-entitlement subtraction can become negative after an earlier failed claim is released while a later dispatched target must remain fixed.

A claim records original line ID, quantity and base/tip cents. Reservation establishes it under the original-sale lock before financial dispatch. Each refund operation stores the same immutable whole-return allocation; multiple tenders consume it once by return UUID. Pending and uncertain operations retain their claims. When all operations for a return definitively fail, its claim stops consuming quantity and money; another already-dispatched claim keeps its original allocation. Saved drafts are provisional until an operation claims them; completed cash returns retain their native allocation. Existing source/tender/component ceilings and exact settlement equality remain enforced.

## Native documents and accounting

The persisted native return stores the server's per-line allocation and exact currency total. Product IDs, quantities, unit prices, discounts and tax IDs retain their original authority. Product line subtotals remain native input-derived amounts. Existing POS `appliedRounding` displays the difference between those product amounts and the authoritative total.

For accounting, the addon uses the pinned Odoo tax engine's `manual_total_excluded_currency` and `manual_tax_amounts` on existing product base lines. The conserved gross target minus native tax amounts supplies the accounting base; tax amounts and native tax-base evidence remain native. This creates no ordinary product, discount, extra refund or settlement tolerance. Native session accounting consumes these base lines. Credit notes carry a protected relation to their original POS return line and use the same native base, including untaxed lines: the pinned standard importer otherwise discards manual base evidence when its tax map is empty. Original collected cash rounding is already in entitlement, so credit notes do not round it a second time. The native closed-session invoice reversal has a separate rounding step: a private cursor/rounding/currency scope suppresses that step only while generating accounting lines for an allocated return. Ordinary invoices retain native rounding. The public regression first reproduced an unbalanced native reversal, then posted both return credit notes and the original rounded sale invoice successfully after the correction.

Per-line and global native tax rounding can produce different fractional-return tax amounts. Tests assert each pinned native mode's output, exact gross credit-note total and balanced accounting; they do not replace those tax policies with a new tax allocator. Conserved returns must be invoiced separately from ordinary orders. Subsequent manual reversals of these credit notes are outside the new projection path and have not been verified.

## Historical compatibility and recovery

No migration fabricates per-line evidence or rewrites completed/uncertain operations. Existing native completed totals and immutable return targets prove older single-line amounts. Missing/ambiguous multi-line targets, inconsistent evidence, or historical original line ceilings that do not establish the saved rounding total block new allocation. A manager must reconcile native/history evidence separately; keep the original financial records and references, and do not create replacement refunds to repair them. Known uncertain refund find/start/poll remains recoverable without another POST. Historical native document reads keep recorded totals even when new allocation is blocked.

External refunds continue to consume source balances without inventing product quantities or base/tip evidence. Existing unknown-component and investigation guards remain in force.

## Verification

Final commands, tested revision and results will be recorded after the full suite, actual upgrade and two-axis review complete. Python compilation checks syntax; this repository has no configured static typechecker.

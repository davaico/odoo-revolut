# Ticket 40 — Conserve partial-return rounding

Initial reproduction baseline: `3dd7affc7c078c9dbaa88c562a59e43e9807c80e` (fetched `origin/main`, 2026-10-05).
Integrated main: `7df76793d7bd772af69b1e3e5054c96d9c69b84b` (fetched again during verification, 2026-10-05). The merge preserves its refund-screen labels, display names and operator documentation.
Branch: `codex/40-conserve-partial-refund-rounding`. Addon: `19.0.1.16.0`.

## Reproduction

The public manager refund RPC regression uses a real native sale, mocked Merchant HTTP, saved return drafts and `sync_from_ui` finalization. A fixed archive of reviewed main with the regression test refunds the first quarter for 309, finalizes it, then fails because source discovery offers 926 rather than the remaining 925. A first fixture using raw floating browser totals also exposed an unrounded stored total (-3.085 versus a -3.09 tender); the final regression uses the normal currency-rounded browser total. No live Merchant API or terminal is involved.

## Allocation contract

Each original line has a frozen monetary ceiling, with the existing base/tip and original cash-rounding decomposition retained. For a new return, subtract the quantities and cents belonging to earlier active return claims, then round the requested share of the remaining cents over the remaining quantity. Returning the entire residual quantity receives the entire residual entitlement. For 1234 cents, quarters receive 309, 308, 309 and 308. Three quarters first receive 926 and the last quarter 308. This residual rule is deliberate: a cumulative-entitlement subtraction can become negative after an earlier failed claim is released while a later dispatched target must remain fixed.

A claim records original line ID, quantity and base/tip cents. Reservation establishes it under the original-sale lock before financial dispatch. Each refund operation stores the same immutable whole-return allocation; multiple tenders consume it once by return UUID. Pending and uncertain operations retain their claims. When all operations for a return definitively fail, its claim stops consuming quantity and money; another already-dispatched claim keeps its original allocation. Saved drafts are provisional until an operation claims them; completed cash returns retain their native allocation. Existing source/tender/component ceilings and exact settlement equality remain enforced.

## Native documents and accounting

The persisted native return stores the server's per-line allocation and exact currency total. Product IDs, quantities, unit prices, discounts and tax IDs retain their original authority. Product line subtotals remain native input-derived amounts. Existing POS `appliedRounding` displays the difference between those product amounts and the authoritative total.

Native POS serializes readonly fields when synchronizing orders. The server accepts empty or unchanged allocation echoes at that transport boundary, discards them before persistence, and rejects forged allocations. Direct `create`/`write` remains private. Pinned Odoo's `Monetary._filter_not_equal` skips a write if a cached raw amount rounds to the requested amount; freezing allocation invalidates that cache before explicitly writing the exact total. The public regression starts with a raw -3.085 draft, reloads -3.09 from storage, rejects a forged allocation and direct clearing, then finalizes an unchanged allocation echo.

For accounting, the addon uses the pinned Odoo tax engine's `manual_total_excluded_currency` and `manual_tax_amounts` on existing product base lines. The conserved gross target minus native tax amounts supplies the accounting base; tax amounts and native tax-base evidence remain native. This creates no ordinary product, discount, extra refund or settlement tolerance. Native session accounting consumes these base lines.

Credit notes carry a protected relation to their original POS return line and use the same native base, including untaxed lines: the pinned standard importer otherwise discards manual base evidence when its tax map is empty. Original collected cash rounding is already in entitlement, so credit notes do not round it a second time.

The native closed-session invoice reversal has a separate rounding step: a private cursor/rounding/currency scope suppresses that step only while generating accounting lines for an allocated return. Ordinary invoices retain native rounding. The public regression first reproduced an unbalanced native reversal, then posted both return credit notes and the original rounded sale invoice successfully after the correction.

Per-line and global native tax rounding can produce different fractional-return tax amounts. The public 20% tax-included test posts these credit notes:

| Native tax mode | Return | Conserved gross | Native tax | Accounting base |
| --- | --- | --- | --- | --- |
| Per line | First quarter | 3.09 | 0.52 | 2.57 |
| Global | First quarter | 3.09 | 0.51 | 2.58 |
| Either | Remaining three quarters | 9.25 | 1.54 | 7.71 |

Tests assert each pinned native mode's output, exact gross credit-note total and balanced accounting; they do not replace those tax policies with a new tax allocator. Conserved returns must be invoiced separately from ordinary orders. Subsequent manual reversals of these credit notes are outside the new projection path and have not been verified.

## Historical compatibility and recovery

No migration fabricates per-line evidence or rewrites completed/uncertain operations. Existing native completed totals and immutable return targets prove older single-line amounts. Missing/ambiguous multi-line targets, inconsistent evidence, or historical original line ceilings that do not establish the saved rounding total block new allocation. A manager must reconcile native/history evidence separately; keep the original financial records and references, and do not create replacement refunds to repair them. Known uncertain refund find/start/poll remains recoverable without another POST. Historical native document reads keep recorded totals even when new allocation is blocked.

External refunds continue to consume source balances without inventing product quantities or base/tip evidence. Existing unknown-component and investigation guards remain in force.

## Verification

Integrated runtime candidate: `7697af0c660356ff276236ca7a1ce2eeca050a59`. The focused three-test check below passed on pre-integration `517bb58`; final full-suite, history upgrades and host checks run on `7697af0`. All Odoo checks use pinned Odoo `19.0.20260908`, guarded Merchant HTTP and mocked provider responses. Commit `7867d52157d297faef88d431827314c80f924bda` then changes only the standalone receipt-upgrade comparison helper; product runtime and imported addon tests are identical to `7697af0`. The final ticket/evidence commit contains documentation changes only.

| Check | Command / scope | Result |
| --- | --- | --- |
| Public regression on reviewed main | Fixed `3dd7aff` archive plus quarter/remaining regression | Expected failure: source discovery offers 926 after finalized 309, instead of 925 |
| Allocation echo, raw draft persistence, ordinary checkout, 309/925 regression | `ODOO_REVOLUT_TEST_PROJECT=ticket40-transport ./scripts/test-addon --test-tags '/pos_revolut:TestReturnAllocation.test_native_readonly_allocation_echo_cannot_create_or_clear_authority,/pos_revolut:TestRevolutVerifiedCheckout.test_cash_and_bank_still_checkout_without_revolut_dispatch,/pos_revolut:TestRevolutTipRefund.test_quarter_then_remaining_return_conserves_native_refund_total'` | 3 tests, 0 failures/errors |
| Full clean install and upgrade | `./scripts/test-addon --verify-install-upgrade` | 508 install + 508 upgrade tests, 0 failures/errors in both; runner exit 0 |
| Reviewed-main financial-history upgrade | `./scripts/test-return-rounding-upgrade` | Passed; immutable financial values/references preserved, remaining 925, uncertain replay without HTTP |
| Receipt-era financial/document upgrade | `./scripts/test-receipt-retirement-upgrade` | Passed; exact stored financial values/relation IDs, preserved attachments and native PDF/repeated authenticated downloads |
| POS state tests | `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | 88 passed, no failures/skips |
| Tooling tests | `python3 -m unittest discover -s tests` | 40 passed, 3 skipped (43 total) |
| Syntax and patch checks | `python3 -m compileall -q addons/pos_revolut`; `bash -n` on changed runners and `scripts/test-addon`; `git diff --check` | Passed |

The complete addon suite includes refund lifecycle/recovery, allocation partitioning, source/tender/component caps, real concurrent transactions, affected external refunds, native receipts and browser checkout, posted session accounting and immediate/late credit notes. Focused runs before the final candidate also passed 136 refund/native/concurrency/external tests, four allocation tests, the real rounding receipt tour, odd terminal-tip conservation and the late-credit-note regression. The full suite is the final combined-candidate check. Python compilation checks syntax; this repository has no configured static typechecker. The three host tooling skips require Odoo for PDF parsing/rendering; actual native PDF parsing/rendering is exercised in the receipt-upgrade Docker runner.

An earlier verification run was also stopped when main advanced; its refund-screen changes were merged before restarting the full install/upgrade checks. Earlier full-suite runs exposed the ordinary POS empty-allocation echo and were stopped for correction; they are not acceptance evidence. The closed-session credit-note regression also failed before its correction, proving that native reversal accounting was exercised.

The receipt-era runner originally failed on both unchanged main and this branch: it removed the old Restaurant bridge before consolidation completed. The repaired runner retains the bridge during migration, matching the existing deployment procedure, then verifies the current-only runtime. Its exact preservation comparison excludes only `pos.order.write_date`, a technical timestamp also changed by unchanged main. Related records are compared by stored IDs rather than generated display names, because main's refund-screen change deliberately updates those labels. Monetary values, states, identities, financial dates, references and preserved PDF attachment checksums remain exact.

Local logs: `/tmp/ticket-40-baseline.log`, `/tmp/ticket-40-transport-green2.log`, `/tmp/ticket-40-full-integrated.log`, `/tmp/ticket-40-upgrade-integrated.log`, `/tmp/ticket-40-receipt-integrated-fixed.log`, `/tmp/ticket-40-node-integrated.log`, `/tmp/ticket-40-tools-integrated.log`. These files are temporary; the results and reproducible commands above are the durable record.

## Standards review

Independent review of `7df7679…7697af0` plus helper-only `7867d52`: **0 documented-standard violations; 0 actionable smell findings**. The exact monetary write follows existing Odoo ORM conventions, and the regression reloads persisted authority before asserting -3.09. The upgrade harness follows documented legacy-bridge deployment preparation. A stale ticket-index claim was corrected during review.

## Spec review

Independent review of `7df7679…7697af0` plus helper-only `7867d52`: **0 remaining findings; no scope creep**. The initial closed-session cash-rounding reversal finding was reproduced publicly and corrected. Locked allocations, unchanged/empty browser echoes, forged-value rejection and exact native persistence satisfy the reviewed ticket. Review preceded final verification; both 508-test phases subsequently passed and the ticket was closed.

## Completion and self-evaluation

Closed locally on 2026-10-05 after both full-suite phases returned success. No physical terminal, live refund or deployment was used. All acceptance criteria are checked in the closed ticket. Main was fetched again before closure and remained `7df7679`; the branch includes it.

Overall: **4.4/5** across five quality axes; no critical issues.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 4 | Public red/green reproductions, exact native/storage/accounting assertions, both full phases and history upgrades pass. Static typing is not configured; syntax checks cannot supply that additional assurance. |
| Completeness | 5 | Every ticket acceptance criterion has executed coverage, including durable claims, races, releases, multiple tenders, taxes, receipts and conservative history. |
| Clarity | 4 | Allocation contract, worked tax table and recovery procedure are recorded. The native accounting explanation still requires Odoo tax-engine familiarity. |
| Actionability | 5 | Committed branch/worktree, versioned addon, installation guidance and reproducible runners let a reviewer inspect and repeat the result. |
| Conciseness | 4 | The final user summary links this evidence; the durable record retains a lengthy focused command and diagnostic history for reproducibility. |

Optional improvements, ranked: (1) retain Docker logs as CI artifacts instead of temporary local files; (2) move pre-integration diagnostic details to an appendix if this record grows. Neither is required for ticket 40. Self-check: the assessment should match the user's requested local implementation, current-main integration and verification scope. Verdict: deliver the completed branch.

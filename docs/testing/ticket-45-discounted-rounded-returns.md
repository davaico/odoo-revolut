# Ticket 45 — Discounted and globally rounded returns

Implementation baseline: fetched `origin/main` / `main` `062409c`, 2026-10-06; a final remote fetch confirmed it remained unchanged.
Branch: `codex/45-refund-discounted-and-rounded-sales`.
Addon version: `19.0.1.18.0`.

## Public test seams and reproductions

The owner confirmed these seams: persisted public cart preparation, mocked terminal start/poll and report verification, finalized native sale, manager source selection, saved return, refund reservation/verification/recovery, and native completion including external association. Merchant HTTP is mocked in pinned Odoo `19.0.20260908`, with the environment's real Merchant HTTP guard enabled.

Two separate regressions reproduced the ticket against unchanged allocation behavior. A 10.00 goods line plus a -1.00 adjustment settled at 9.00; source selection rejected negative entitlement. Six 10.01 lines plus a final-UUID 0.01 line settled at 60.05 under five-cent global rounding; source selection rejected its negative last-line remainder. Both verified and finalized the original sale before failing; neither reached a refund POST. Log: `/tmp/ticket45-red3.log`. Fixture setup failures before these reproductions are not product evidence.

## Allocation and compatibility

Healthy nonnegative conserved ceilings keep their established distribution. Supported negative adjustments have zero separate entitlement; their effect reduces positive goods proportionally. If an independent rounding remainder is negative, cumulative integer rounding over positive weights conserves the original frozen payable and cannot manufacture negative capacity. If recorded line subtotals cancel or round to zero, native unrounded gross weights use the original product inputs only while tax and fiscal-position records have not changed since the frozen authorization. Changed historical tax inputs block this ambiguous fallback for manager reconciliation. No historical tax rate is guessed or financial record rewritten.

Return quantities are magnitudes, with each native line carrying the opposite sign to its linked original. Original products, prices, discounts and taxes remain unchanged. Terminal tips and base payment allocations remain separate, with source and original tender caps still enforced. Zero-entitlement native returns complete without any provider reimbursement or positive balancing tender.

Existing claims are validated against the original accepted ceilings as well as the corrected ones. Earlier actual cents and quantities are deducted once per return identity. When historical claims have already exhausted a line at an older ceiling, only remaining unclaimed entitlement is distributed over eligible remaining quantities. Saved claim JSON, native completed totals, provider references and surviving reservations are never rewritten. Ambiguous historical totals or missing multi-line allocation evidence remain blocked for manager reconciliation.

Native taxes keep the existing Odoo engine's evidence while the accepted allocation controls monetary totals. The discounted included-tax regression verifies actual stock restocking, a posted balanced credit note, unchanged product inputs and no duplicated native effects on replay. Browser tests exercise actual TicketScreen selection, positive reversal editing and verified native receipts.

## Verification

Runtime candidate: `00b46ed4840a8ec659f8b38f27f9cdaec06910e3`. The complete fresh-install and upgrade run exited successfully (status 0). The closure commit changes documentation only. No configured static typechecker exists; Python/JavaScript compilation checks syntax only.

| Check | Result | Reproduction |
| --- | --- | --- |
| Separate original public failures | Both failed after verified native sale, before any refund POST | `/tmp/ticket45-red3.log` |
| Focused public return workflows | 15 tests passed | `/pos_revolut:TestDiscountedRoundedReturns`; `/tmp/ticket45-matrix3.log` |
| Final native tax/precision fallback | Taxed and untaxed sub-minor cases passed, 2 tests | `/tmp/ticket45-tax-small-green.log` |
| Native POS browser flows | 2 tests passed: full negative-quantity return and remaining zero-value adjustment | `/pos_revolut:TestNativeAdjustmentBrowser`; `/tmp/ticket45-native-ui.log` |
| Complete fresh installation | 591 tests, zero failures or errors | `ODOO_REVOLUT_TEST_PROJECT=revolut-ticket45-full ./scripts/test-addon --verify-install-upgrade`; `/tmp/ticket45-full.log` |
| Complete addon upgrade | 591 tests, zero failures or errors | Same command and log; both phases use the identical runtime candidate |
| Payment state tests | 99 passed | `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` |
| Tooling tests | 57 run, 54 passed, 3 existing optional PDF probes skipped | `python3 -m unittest discover -s tests` |
| Syntax and patch checks | Passed | `python3 -m compileall -q addons/pos_revolut`; changed JavaScript `node --check`; `git diff --check` |

Additional public regressions first reproduced zero-return rejection and an invalid zero-rounded per-line basis before their corrections. Initial setup issues and stale fixture expectations are diagnostic history, not acceptance evidence. All financial HTTP calls are mocked; no live terminal, refund or deployment occurred.

## Standards

Independent review of `062409c...00b46ed`: no documented-standard breaches or actionable baseline smells. Server authority, immutable claims, native extension conventions, provider mocks and repository boundaries are preserved. Preserving original return prices justifies bypassing native repricing for negative-original reversals.

## Spec

Independent review of the same immutable candidate: no actionable implementation gap or scope creep. Conservation, frozen history, quantity signs, zero-value completion, tender caps and external association match the ticket. At review time, real concurrency acceptance remained pending; the new overlapping-claim regression itself uses sequential interleaving. Both complete runs now pass the actual concurrent refund and external-native reservation/association tests (`TestRevolutRefundConcurrency`, `TestExternalNativeConcurrency`, `TestExternalRefundConcurrency`), resolving that verification limitation.

Review summary: Standards 0 findings; Spec 0 findings. No worst issue on either axis.

## Final self-evaluation

Overall: 4.6/5; no substantive gap against ticket 45.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 4/5 | Both complete phases pass, and original failures were reproduced independently. UUID/tax fixtures are representative rather than exhaustive; broaden generated partition cases if allocation rules expand. |
| Completeness | 5/5 | All ticket criteria have focused or complete-suite evidence, including real concurrency, native browser completion, immutable history and external association. |
| Clarity | 4/5 | Operator actions are explicit in installation guidance; the historical-allocation explanation remains dense. Split that technical paragraph when extending compatibility rules. |
| Actionability | 5/5 | Committed implementation, reproducible commands, clean independent reviews and upgrade guidance are available on the ticket branch. |
| Conciseness | 5/5 | One verification matrix links detailed evidence; the final handoff names the branch, results and record. |

Improvements, by impact: broaden generated allocation examples when rules change; separate historical compatibility explanations when extending them. No critical issue or axis at 3 or below. Self-check: the owner can verify the claimed results and review the complete committed change. Verdict: deliver as-is.

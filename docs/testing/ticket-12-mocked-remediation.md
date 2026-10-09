# Ticket 12 mocked remediation

This follow-up covers the five reported failures and six observations from the
October 9 handoff. Work starts at `aa40425852c95fd0652560e7b3884cb335182540`,
which matched upstream `main` when checked. PRs 68–71 and the earlier deferred
cancellation fix are already included. The local addon version is 19.0.1.18.10.
This is local verification, not deployment or renewed live acceptance.

All Odoo runs use disposable, separately named Docker projects with the
repository's internal network and Merchant HTTP guard. Provider responses are
mocked. Existing staging payments, pending refunds, finalized return 53,
correction draft 13, and historical failed attempts 14/15 are untouched.
No migration rewrites financial history, permissions change, or staging
deployment/restart is included. The existing manual evidence files remain
owner-edited and ticket 12 remains open.

## Return subtotal investigation

The reported positive persisted subtotals reproduce on a native external penny
return. In pinned Odoo `19.0.20260908`, this is the native `is_refund=True`
representation: `pos.order.line._compute_amount_line_all()` multiplies negative
quantity by the refund sign, storing a positive subtotal. Native margin applies
the sign again; `report.pos.order` derives it from quantity and price. Tax and
invoice preparation use their own refund signs. Negating stored subtotals alone
would therefore be an incorrect fix, especially for native margin.

Public-action tests now persist and reload both the external penny return and
the two-unit, 50%-discounted penny return using the native refund flag. They
verify negative quantity/order totals, positive stored line magnitudes, negative
report totals and negative native margin. The external case also validates a
posted credit note of 0.01, positive revenue reversal and balanced journal
entries, without another provider call. The existing taxed stock-return test
continues to check tax reversal, credit-note balance and stock behavior.

Older synthetic return fixtures omitted `is_refund`, which explains why those
fixtures used negative line subtotals. The new cases explicitly cover the
native representation seen in the manual evidence. This finding does not edit
the reported historical returns or claim their individual accounting entries
were inspected. No accounting failure was established by the reproduced
positive subtotal alone; no stored-sign change is made.

## Scoped changes

| Handoff item | Local disposition |
| --- | --- |
| R08 cancellation recovery | Restore the observed status after native draft synchronization overwrites a line with an older waiting status; retain operation identity and recovery actions. This reproduces a failure mechanism, not the unrecorded timing of the historical incident. |
| R11 refund status recovery | Apply the same synchronization recovery to pending refunds; processing remains pending and Check status observes the existing operation. |
| R01/R08 revoked access | Check the current session/register grant during discovery before saving an unsaved payment line; show actionable register-access feedback. Native ACLs remain enforced. |
| R16 printed references | Wrap Revolut ticket text at narrow receipt widths, retaining every reference character and leaving other terminals' ticket formatting alone. |
| R10/R17 allowance hints | Label terminal-tip allowance explicitly and show remaining base excluding tips for the selected source and other allocations. Source balances are not deducted twice; unknown card components are conservative. |
| R03 two-card allocation | Add Choose amount beside Revolut. It creates an editable native pending line; the cashier enters the allocation and presses Send. The ordinary full-balance button retains automatic dispatch. |
| R10 Cash entry | Explain that manual refund tenders require a negative amount; keep native cash arithmetic unchanged. |
| R17 pending worklist | Resolve a display-only return link by UUID/company/register under existing access rules and show native completion still pending. Do not mutate settlement links/status. |
| R13/R17 quantity editor | Put Return now beside the product with room for entry and distinguish Purchased/Already returned columns. |
| R14 correction editor | Native Journal Items is restricted to the accounting group. Disposable view tests reproduce its absence for a POS manager and presence for an authorized accountant. Add handoff guidance; reuse the existing draft under an authorized accountant without widening grants. |

## Verification

Focused red/green regressions and follow-up checks:

| Check | Result |
| --- | --- |
| Complete clean-install addon suite | 619 passed, zero failures/errors; `ODOO_REVOLUT_TEST_PROJECT=ticket12-complete ./scripts/test-addon`. |
| Exact external and discounted penny returns | 2 passed; persisted native subtotals, negative reports/margins, and posted external credit-note reversal checked. |
| Native stale synchronization browser regressions | Both failed against the baseline, then 2 passed for cancellation and pending-refund recovery. |
| Shared register access suite | 27 passed, including revoked unsaved-order discovery. |
| Worklist and accounting disposition suites | 14 passed, including display-only recovery and accounting-group view visibility. |
| Supported two-card browser flow | Failed with missing Choose amount UI, then passed with 12.33 and 0.01 allocations, separate references and automatic completion. |
| Receipt print-width browser regressions | Overflow reproduced before fix; ordinary and mixed-tender receipts passed at 58 mm and 80 mm. |
| JavaScript suites | 125 passed, no skips: 122 payment-state and 3 allowance cases. |
| Host tooling suite | 65 run: 62 passed, 3 skipped for missing host Odoo dependencies. |
| PDF probes in supported isolated runtime | All 7 passed, including the three host-skipped probes. |
| Standards review | No documented-standard violations or actionable smells. |
| Specification review | No actionable omissions, scope creep or implementation errors. |

No static typechecker is configured; Python compilation, JavaScript syntax,
XML parsing and whitespace checks supplement behavioral tests.

Working logs are under `/tmp/ticket12-*`, including `subtotal-final`,
`sync-green`, `access-green`, `split-ui-green`, `print-green`,
`print-split-green`, `node-final`, `host-final`, `pdf-runtime` and `complete` (all `.log`).
These temporary logs are not the durable live-evidence archive.

Manual follow-up after a separately authorized deployment should exercise
two-browser cancellation, pending-refund recovery, revoked-register feedback,
receipt printing, source-specific allowance hints and the supported two-card
entry. Use the existing return/refund identities and correction draft; do not
recreate them for acceptance. Physical-terminal behavior remains a separate
release gate.

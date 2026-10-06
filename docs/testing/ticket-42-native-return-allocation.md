# Native return allocation and recovery — ticket 42

The candidate starts from reviewed `origin/main` / `ca668a9` on
`codex/42-deepen-native-return-allocation`. All financial requests in tests are
mocked on Odoo Community `19.0.20260908`; the isolated Docker network and Merchant
HTTP guard prevent live terminal/API calls.

## Interface responsibilities

`ReturnAllocation` retains the existing explicit workflow operations and adds
`display_target(order)`, `freeze_native_return(order)` and
`recover(refund, destination_session)`.

- Source previews, reservation and native settlement share `ReturnDecision` for
  conserved per-line base/tip amounts and `RefundCapacity` for source and whole
  return gross/base/tip limits. Existing manual-tender limits stay in settlement.
  A corrupt source component outside its original capacity now rejects picker
  discovery instead of displaying a clamped balance as usable evidence.
- Display selection moved out of the native order hook. It only reads evidence,
  preserves recorded historical totals, and neither locks nor freezes. Native
  price recomputation uses that advisory operation.
- Freezing reads and independently validates saved native contents, locks the
  original sale, checks quantities and accepted transport totals, then persists
  per-line amounts and the exact total. The projection writer no longer invokes
  price recomputation. The native saved-order hook computes taxes afterward.
- Reservation still checks an existing attempt before requiring a saved draft.
  New claims bind unchanged submitted evidence to a saved native return and its
  exact payment. The caller's dedicated transaction commits before dispatch.
- Recovery owns sibling discovery, existing recovery locks, access/session
  validation, original-sale identity, frozen target/line/component checks,
  source/return capacities, and exact payment-link checks. Every active sibling
  with the return identity counts, including associated external evidence.
  Failed siblings release their claim; uncertain siblings reject recovery.
- Recovery returns checked original contents and exact verified card tenders in
  a scoped evidence object. Reading it on another cursor, after commit/rollback,
  or after leaving the recovery scope is rejected. Its contents are projection
  data, never an entitlement accepted by a later reservation or freeze.
- The manager caller chooses the destination session, keeps its savepoint,
  reconstructs native lines/taxes/payments and opens the normal POS action.
  Odoo still owns product tracking, stock, invoices, receipts and accounting.
  Missing cash reimbursement or lost lot/serial evidence is not invented.

The existing recovery acquisition order remains session → return UUID → refund
rows in ID order → original sale. Reservation and checkout keep their existing
orders and lifetimes. No provider contract, schema, browser request, unrelated
lock order or external-association protocol changes here. Ticket 43 owns the
remaining association migration and lock consolidation.

## Verification

Public test seams are the ticket's source-picker/refund RPCs, manager recovery,
native synchronization/completion, native receipt data and posted accounting.
No existing tests were removed and no private-helper tests were added.

- Source component regression: baseline fails with `UserError not raised` for
  a balanced 308-base/1-tip reimbursement against a source with no tip capacity.
  SQL only seeds legacy inconsistent facts that immutable normal writes forbid.
- Recovery regressions: baseline register suite passed 14 tests, including
  inconsistent component/source/sibling evidence and a genuine native missing
  invoice journal failure. That failure occurs after draft creation; rollback
  removes partial native data and preserves already verified reimbursement.
- First candidate native run exercised 96 tests and exposed two tax-rounding
  failures after removing the projection writer's recomputation. Moving native
  tax projection to the caller's saved-order hook fixed both rounding modes.
- Corrected native run: 80 tests passed, including allocation, refund lifecycle,
  register recovery and the taxed partial-return credit-note test.

The first compatibility run exercised 90 tests; only the partial-reservation
concurrency fixture failed during native draft saving. Its submitted .501 quantity
was rounded by Odoo's two-decimal quantity field to .50, while its submitted total
remained 618 cents. The fixture now uses .50/617 and .51/629, asserts both saved
quantities and totals remain unchanged, and only then races both reservations.
This preserves a real competing request rather than an early evidence rejection.

The native lost-draft completion regression passes on the candidate: public
picker → saved quarter return → reservation → verification → historical lost
draft → manager recovery → native checkout creates one done .25 stock return
and one posted balanced 3.09 credit note. Receipt total stays −3.09, repeated
recovery/checkout retains all native identities, and the .75 remainder is 925
cents. Recovery/completion issues no provider request.

Initial independent review against `ca668a9`: Standards reports no hard
violations and one optional duplicated eligibility predicate; Spec reports zero
findings. The shared native-return qualification predicate resolves that smell,
while authoritative normalization/checking remains independent of display.

Final runtime is `b717438fd0108eb280b7a870569d2ed24f511216`.

| Check | Command | Result |
| --- | --- | --- |
| Native allocation/refund/recovery and tax rounding | `scripts/test-addon --test-tags /pos_revolut:TestRevolutTipRefund.test_taxed_partial_returns_preserve_native_tax_and_credit_note_totals,/pos_revolut:TestReturnAllocation,/pos_revolut:TestRevolutRefund,/pos_revolut:TestRevolutRegisterRefund` | 80 passed |
| Native lost odd-cent completion | `scripts/test-addon --test-tags /pos_revolut:TestRevolutRegisterRefund.test_lost_odd_cent_return_native_checkout_projects_effects_once` | 1 passed, including stock/receipt/posted credit note/replay |
| External compatibility, concurrent reservations and session closure | `scripts/test-addon --test-tags /pos_revolut:TestExternalRefunds,/pos_revolut:TestExternalNativeAssociation,/pos_revolut:TestExternalNativeReturns,/pos_revolut:TestExternalNativeStock,/pos_revolut:TestExternalNativeConcurrency,/pos_revolut:TestRevolutRefundConcurrency,/pos_revolut:TestRefundSessionClose` | 90 passed |
| Complete addon install and upgrade | `ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-42-full scripts/test-addon --verify-install-upgrade` | Install: 552 passed; upgrade: 552 passed, zero failures/errors |
| Payment-state lifecycle | `node --test --test-isolation=none addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | 88 passed, zero skipped |
| Host tooling | `python3 -m unittest discover -s tests -v` | 43 run: 40 passed, 3 opt-in PDF runtime checks skipped |
| Syntax and whitespace | `python3 -m compileall -q addons/pos_revolut`; `git diff --check` | Passed |

Logs in `/tmp/ticket42-native-green2.log`, `/tmp/ticket42-compatibility2.log`,
`/tmp/ticket42-full.log`, `/tmp/ticket42-node.log` and `/tmp/ticket42-host.log`
are ephemeral. The full suite covers native browser, PDF/accounting, Restaurant,
refund/recovery and real PostgreSQL concurrency behavior; the three opt-in host
PDF skips are separate. This repo has no configured static typechecker.
Compilation checks syntax, not financial behavior. Old-to-new history runners
were not repeated because this slice adds no schema, migration or manifest entry;
historical replay/ambiguous evidence fixtures and the current install/upgrade
suite exercise the affected behavior.

## Standards

Independent refreshed review of `git diff ca668a9...b717438`: no documented
standard breaches and no actionable baseline smells. The shared qualification
predicate resolved the initial optional duplicated-code judgment.

## Spec

Independent refreshed review against ticket 42: no missing requirements, scope
creep or incorrect implementation identified. The public odd-cent recovery
workflow and corrected valid concurrency contenders strengthen required coverage.

Review totals: Standards 0; Spec 0; neither axis has an outstanding finding.

No staging deployment, credentials, live device or real money operation is part
of this ticket. Physical/financial acceptance remains ticket 12.

The full runner exited successfully on 2026-10-06. The final closure commit only
updates ticket/evidence documentation; runtime remains the reviewed and tested
`b717438`. Local integration follows the tracker workflow; remote publishing is
a separate action.


## Shared historical runner retest — 2026-10-06

At the owner's request, fetched remote main `4e55a21` (PR 57 shared historical
upgrade runner) and merged it with ticket 42 as `d96d5f4`. The assigned ticket
branch was updated from that main. Comparison with `1168168` confirms the addon
models and POS static code are unchanged; this retest checks the actual new
runner and its historical fixtures against the integrated candidate.

All commands below exited 0 on pinned Odoo `19.0.20260908`. Each historical
scenario used `ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-42-retest-<scenario>` for
isolated resources. Expected provider calls remain mocked and Merchant HTTP
remains blocked.

| Shared runner command | Verified result |
| --- | --- |
| `scripts/test-historical-upgrade return-rounding` | Immutable history, remaining 925 cents and uncertain replay references preserved without HTTP |
| `scripts/test-historical-upgrade external-native` | Exact financial history, one native completion and protected pending capacity; zero HTTP |
| `scripts/test-historical-upgrade cart-authority` | Six historical states preserved, no invented authority/tip evidence, historical native refund verified |
| `scripts/test-historical-upgrade credential-authority` | Legacy attempt fails closed, administrator attestation and GET-only recovery work |
| `scripts/test-historical-upgrade register-access` | No implicit grants, late success reconciled, original order recoverable after explicit grant |
| `scripts/test-historical-upgrade evidence-retirement` | Removed page/ACL and denied RPC; immutable financial evidence and server resolution retained |
| `scripts/test-historical-upgrade receipt-retirement` | Financial/document values unchanged; actual QWeb invoice PDF and repeated authenticated downloads verified |

The runner's focused CLI suite passed all **10 tests**:
`python3 -m unittest discover -s tests -p test_historical_upgrade_runner.py -v`.
`bash -n` passed for the shared runner and all seven wrapper commands.

Fresh affected native verification passed **112 tests**, with zero failures or
errors, using the isolated `odoo-revolut-42-retest-native` project:

```bash
scripts/test-addon --test-tags /pos_revolut:TestReturnAllocation,/pos_revolut:TestRevolutRefund,/pos_revolut:TestRevolutTipRefund,/pos_revolut:TestRevolutRegisterRefund,/pos_revolut:TestRevolutRefundConcurrency,/pos_revolut:TestRefundSessionClose
```

This exercises source allocation, frozen residual cents, full/partial refund
lifecycle, lost-draft recovery, native stock/accounting projection, real competing
reservations and session closure. No addon corrections were needed. The earlier
552-install/552-upgrade results remain their original evidence; those full phases
were not repeated because the integration changes only runner infrastructure and
historical verification fixtures, while all affected native and historical paths
were freshly exercised here.

Logs are ephemeral under `/tmp/ticket42-shared-<scenario>.log`,
`/tmp/ticket42-shared-native.log` and `/tmp/ticket42-shared-cli.log`.

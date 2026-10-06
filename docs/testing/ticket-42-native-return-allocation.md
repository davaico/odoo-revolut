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

Final compatibility, complete install/upgrade and review results are recorded
below when completed. Python compilation and whitespace checks pass; this repo
has no configured static typechecker. Syntax checks are not financial proof.

No staging deployment, credentials, live device or real money operation is part
of this ticket. Physical/financial acceptance remains ticket 12.

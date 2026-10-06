# Return lock compatibility — ticket 43

Reviewed against the accepted baseline `57e9a67`. The participating acquisition
orders were inspected before adopting the target order. This audit identifies
ordering conflicts in the protocols; it does not claim an observed production
deadlock. PostgreSQL race tests are recorded with the ticket's runtime evidence.

## Authoritative acquisition

`ReturnAllocation.acquire_many` owns the common order:

1. Sessions in ID order.
2. `(company_id, order_uuid)` identities in sorted order.
3. Original sale and already-persisted affected native order rows in ID order.
4. Original payment operations, including charge attempts found by the native
   identity before native linkage, in ID order.
5. Refund records for those sources and explicitly selected refunds in ID order.

`acquire` is the single-workflow adapter. Pointer discovery selects records to
lock; it supplies no accepted monetary/state evidence. Record updates force stale
repeatable-read contenders to retry with a fresh cursor. Participating session,
order, line, payment-operation and refund evidence is invalidated after locking
and authoritative callers independently validate it. An explicit refund set
includes the selected association batch even before it has a native identity.
Multiple-record adapters acquire complete stage sets rather than interleaving
one full protocol per record.

Reservation, native settlement, monetary freezing, manager recovery and external
association use this module acquisition. Allocation owns capacities and frozen
base/tip evidence. The native association caller supplies confirmed product/lot
selection and exact reimbursement bindings, then retains Odoo construction,
stock, receipt, invoice and accounting completion. Caller savepoints, retries,
commits and provider dispatch remain outside allocation. Advisory picker/display
operations still perform no locks or mutations.

## Neighboring protocols and compatibility decisions

| Participant | Baseline order / concern | Final responsibility |
| --- | --- | --- |
| Native `pos.order` mutation | Exposure inspection acquired UUID/payment rows before native order SQL; a source sale mutation could invert sale → source. Creation watched only after native INSERT. | `acquire_native_mutation` locks complete old/new session and identity sets, native rows and original sales before exposure inspection or native SQL. `acquire_native_creation` chooses the UUID and acquires from confirmed incoming line identities before INSERT. Empty native `_refund()` construction remains supported. |
| Native `pos.payment` mutation | Payment creation first inserted; subsequent watch acquired financial locks. Reassignment initially watched only the old order. | The parent command parser discovers all old/new owners of linked, replaced, updated or deleted existing tenders before acquiring any session/identity; creation includes those owners before insertion. The mutation scope watches the complete owner set before child SQL. Existing exact proof, access and immutable-evidence checks remain. |
| Native `pos.order.line` and custom attributes | Line insertion could precede original-sale discovery; changing a refunded original could introduce a later sale lock. | Parent command acquisition includes previous native owners for line LINK/SET/UPDATE/DELETE/UNLINK, including the fixed nested lot/serial and custom-attribute relations inside line CREATE/UPDATE contents, before acquiring any session/identity; `acquire_native_line_mutation` discovers new refunded line identities before line SQL; the outer mutation scope checks original contents and settled-return immutability. Direct native line creation/mutation also discovers nested lot/attribute owners before acquisition. Lot/serial and custom-attribute creation watches the receiving native order before INSERT, and reassignment watches old/new owners together before SQL. These hooks continue through the same immutable-content watched-order scope. |
| Cart preparation and approval | Session → UUID followed by charge-row reads and native tender corrections. | Module native acquisition runs before cart authority and native tender mutation. Expected cart version, manager approval, register and immutable authority checks remain caller behavior. |
| Payment status / terminal-tip projection | UUID → payment row → verified-tip projection → native order mutation could then request the session. | `acquire_payment_observation` acquires session → identity → native sale → sources/refunds before applying payment evidence. The fenced observation adapter does so before checking its token. Tip projection therefore reaches native hooks with its earlier locks already held. |
| Refund status application | Odoo UUID (or external source-sale UUID) → refund row, without the session/original/source locks used by finalization. | `acquire_refund_status` uses the full order for bound refunds. Provider detail recording and final-state application read the refreshed record afterward. Unbound external refunds use the financial suffix below. |
| Matched external discovery | Source payment row → existing/new refund, with amounts checked before acquiring the source row. | `acquire_discovery` acquires all sources named by visible refund parent references and their refunds in ID order before unordered provider candidates are processed. A refund whose list parent is omitted conservatively locks the complete scan source set, preserving the existing detail GET and its order; per-candidate processing rereads source amount/currency under the retained source lock, then finds/applies existing refund evidence. It never subsequently requests a native session, UUID or sale lock. |
| Financial-only external disposition | Manager completion locks plus subsequent native account-move lock. | Existing manager, origin, source and register checks remain; module refund-status acquisition runs before account-move construction/validation. Native accounting locks follow the financial suffix, without requesting earlier native POS locks. |
| Session closure | Session → sorted charge/refund UUIDs; status checks could use cached financial evidence. | `acquire_session_closure` includes all native session orders, bound native returns and their original sales, then acquires all sessions, identities, original sales, charge/source rows and refunds together and refreshes evidence before the existing unsettled-payment/refund guards. Native closure/accounting stays in Odoo. |

The source/refund-only suffix is deliberately compatible: a contender holding
it never waits for a session, return identity or sale row. It can delay native
allocation, but cannot close a cycle through an earlier stage. Discovery's
credential-row lock serializes one scan; native allocation does not request
that credential-row lock. Unmatched/ambiguous discovery evidence remains a
preserved blocking ledger with no invented native return or product allocation.

Bounded POS transport preflight, native construction lifecycle hooks, register
checks and unrelated-order/reference rejection remain in their existing
adapters. Lock consolidation does not grant authorization or convert a pending,
failed or uncertain reimbursement into a verified native tender.

## Verification from the neighboring-hook audit

`ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-lock-hooks scripts/test-addon
--test-tags /pos_revolut:TestRefundSessionClose,/pos_revolut:TestRevolutVerifiedCheckout.test_cash_and_bank_still_checkout_without_revolut_dispatch`
passed **10 tests**, zero failures/errors. This includes actual ordinary native
cash/bank checkout and session guards; Merchant HTTP is mocked/blocked by the
isolated runner. Log: `/tmp/ticket43-lock-hooks.log` (ephemeral).

Syntax compilation and `git diff --check` passed after the adapter edits.
The later discovery/observation verification passed **84 tests**, zero
failures/errors:

`ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-discovery-observation scripts/test-addon
--test-tags /pos_revolut:TestExternalRefunds,/pos_revolut:TestExternalRefundConcurrency,/pos_revolut:TestRevolutPaymentObservation,/pos_revolut:TestRevolutTerminalTip`

This exercises discovery, independent PostgreSQL discovery/refund contention,
fenced payment observation and verified terminal-tip native projection. Log:
`/tmp/ticket43-discovery-observation.log` (ephemeral). The corrected affected
native run also passed **49 tests**, zero failures/errors; its complete command
and allocation/association/stock/accounting coverage are recorded in the main
ticket evidence. Final closure-set expansion includes native session orders
before accounting and is covered by the subsequent full checks recorded there.
This repository has no configured static typechecker.

After limiting discovery acquisition to visible parent references, the focused
discovery suites passed **46 tests**, zero failures/errors:

`ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-discovery-bounded scripts/test-addon
--test-tags /pos_revolut:TestExternalRefunds,/pos_revolut:TestExternalRefundConcurrency`

Log: `/tmp/ticket43-discovery-bounded.log` (ephemeral). This includes omitted
parent detail resolution and independent discovery/reservation transactions.

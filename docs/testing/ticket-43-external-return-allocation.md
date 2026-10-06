# External return allocation and shared locking — ticket 43

The implementation starts from user-confirmed `main` / `57e9a67` on
`codex/43-deepen-external-return-allocation`, in the repository's designated
worktree area. Ticket 42 is closed and present in that baseline. Tests run on
pinned Odoo Community `19.0.20260908` with PostgreSQL, mocked provider HTTP and
the isolated network/Merchant guard. No deployment or live device is involved.

## Interface responsibilities

`ReturnAllocation.associate(refunds, bindings, ...)` accepts the entire selected
batch with an existing native return or confirmed original product selection.
It acquires the session, native identity, original sale/native rows, original
payment operations and refund records before native construction, then reads
fresh evidence. The manager adapters keep their savepoint/mutation scope and
native Odoo product/lot helpers; they supply no private allocation arithmetic or
lock protocol. The association batch context-variable bypass is removed.

The operation validates unique refund/payment bindings, one original sale,
register/company/currency authority, immutable contents, original quantities,
frozen per-line base/tip evidence and source/whole-return capacities before
persisting any binding. Already-issued money counts once: source capacity
replaces the selected batch's existing unknown components with its explicit
components instead of adding imported gross reimbursement again. Unclassified
siblings on a tipped source remain protected and require component confirmation.

Draft preparation and resume retain exact native order/payment identities.
Pending evidence can protect a draft but cannot complete it; failed/uncertain
money cannot become a verified tender. Exact authoritative completed evidence
remains required. Compatible historical completed returns retain their actual
stock/accounting records. Financial-only correction, historical acknowledgement,
manual-tender ceilings, native stock, receipts, lots/serials and invoicing remain
in their existing Odoo flows.

The shared acquisition implementation is also used by reservation, settlement,
monetary freezing and manager recovery. Native parent commands discover complete
previous-owner sets for existing line/payment relations before any stage,
including link/set commands; child mutations retain normal native access and
immutable-proof checks. Participating payment/refund observation, discovery,
ancillary native mutation and session closure are documented in
[ticket-43-lock-orders.md](ticket-43-lock-orders.md).

Pointer discovery only selects locks. Participating evidence is flushed and
invalidated under locks, then independently checked. Locks remain owned by the
caller transaction. Source picker and total display remain nonlocking and
nonmutating. Savepoints, conflict retries, commits and provider dispatch stay
caller-owned. Recovery evidence is still scoped to its cursor and expires on
scope exit/commit/rollback; projection data is never accepted as authority in a
later transaction.

Native freezing watches/acquires the order before clearing a fractional
Monetary cache, preserving the existing exact-cent projection workaround.
Already-watched orders reuse the same mutation savepoint's retained locks;
changes that introduce owners/identities still acquire complete affected sets.

## Regression evidence

The terminal-tip sibling regression fails on the accepted baseline with
`UserError not raised`. On the candidate, the manager action rejects the
unknown component without creating a return or moving money.

The status/finalization contention test also fails on immutable `57e9a67`:
only one public action waits on the independent PostgreSQL session lock instead
of both. On the candidate, both actions contend at that boundary; after
successful provider evidence, resume/finalization create one native return and
one completed stock movement. Earlier discovery-race failures were fixture/event
coordination issues, not claimed runtime regressions.

Initial native verification exposed empty native `_refund()` construction and
fractional total projection regressions from the new acquisition hooks. Empty
construction remains supported, lock acquisition now precedes the precise
Monetary cache reset, and participating invalidation preserves unrelated native
accounting caches. The corrected affected native run passes.

Historical verification first completes a real invoiced storable return through
the manager interface, then removes only the addon association/allocation
metadata absent in an older release. Genuine done pickings/moves, posted credit
note and its lines, and existing payment IDs remain. Public association and
replay retain all of those IDs and counts, the exact posted 12.34 credit note,
verified provider evidence and reimbursement references, with zero HTTP.

The batch rollback test makes the final member's historical payment reference
unrelated. The manager rejects the batch, leaves every refund/payment link
unbound, and preserves all existing native records and effects.

## Verification

| Check | Actual result |
| --- | --- |
| Unknown sibling tip regression on baseline | 1 expected failure, `UserError not raised` |
| Corrected allocation/external association/stock/manager recovery | 49 passed |
| Refund/tip/financial-only/association/concurrency/session compatibility | 147 passed |
| Discovery/payment observation/terminal-tip compatibility | 84 passed |
| Bounded discovery and existing discovery concurrency | 46 passed |
| Initial manager PostgreSQL concurrency suite | 6 passed |
| Explicit discovery/reservation and status-application/finalization races | 2 passed |
| Immutable baseline status-application lock regression | 1 expected failure: only one session waiter |
| Failing manager association batch | 1 passed |
| Historical actual stock and posted-credit-note association | 1 passed |
| Payment-state JavaScript lifecycle | 88 passed, zero skipped |
| Host tooling | 53 run: 50 passed, 3 opt-in PDF-runtime checks skipped |
| Python syntax and Git whitespace | Passed |

The final complete candidate and refreshed review results are recorded below
when their checks finish. No static typechecker is configured in this repository;
`compileall` checks syntax and is not evidence of financial correctness.

Narrow logs are ephemeral under `/tmp/ticket43-native2.log`,
`/tmp/ticket43-compat.log`, `/tmp/ticket43-discovery-observation.log`,
`/tmp/ticket43-discovery-bounded.log`, `/tmp/ticket43-concurrency.log`,
`/tmp/ticket43-new-races.log`, `/tmp/ticket43-status-baseline.log`,
`/tmp/ticket43-batch.log`, `/tmp/ticket43-history.log`,
`/tmp/ticket43-node.log` and `/tmp/ticket43-host.log`.

No schema/manifest/migration or provider contract changes are introduced.
Old-release history runner checks and final full install/upgrade results will be
reported separately; live acceptance remains ticket 12.

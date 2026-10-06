# External return allocation and shared locking — ticket 43

The implementation starts from user-confirmed `main` / `57e9a67` on
`codex/43-deepen-external-return-allocation`, in the repository's designated
worktree area. Ticket 42 is closed and present in that baseline. Tests run on
pinned Odoo Community `19.0.20260908` with PostgreSQL, mocked provider HTTP and
the isolated network/Merchant guard. No deployment or live device is involved.

Worktree: `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/43-external-return-allocation`.
The final runtime candidate is `c183c2ff772596ff44d1e099ad7fb600336d809e`;
subsequent ticket closure and verification edits change documentation only.

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

The discovery/reservation scenario starts from a 1,234-cent original charge.
Public discovery imports an already-issued 617-cent reimbursement while a native
full claim is in preflight. The stale full claim is rejected without POST; a new
617-cent native claim dispatches exactly once and replay reuses its reference.
The combined claims consume exactly 1,234 cents, and the next competing claim
is rejected. This exercises the existing provider path through the shared
allocation interface.

For already-issued money, manager product confirmation prepares the draft,
pending evidence prevents finalization, and verified evidence allows native
completion. Partial storable returns move only the selected quantity; repeated
validation preserves one stock movement. Invoiced returns produce the exact
native credit note. Manager association and resume send no financial requests.

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
| Native line/payment LINK/SET ownership contention | 1 test, all 4 independent-transaction subcases passed |
| Immutable baseline status-application lock regression | 1 expected failure: only one session waiter |
| Failing manager association batch | 1 passed |
| Historical actual stock and posted-credit-note association | 1 passed |
| Payment-state JavaScript lifecycle | 88 passed, zero skipped |
| Host tooling | 53 run: 50 passed, 3 opt-in PDF-runtime checks skipped |
| Historical external-native upgrade | Passed: exact financial history, one native completion, pending capacity protection, zero HTTP |
| Historical return-rounding upgrade | Passed: immutable history, remaining 925 cents, uncertain replay without HTTP |
| Full fresh install | 561 passed, zero failures/errors |
| Full current-version upgrade | 561 passed, zero failures/errors; combined runner exited 0 |
| Python syntax and Git whitespace | Passed |

No static typechecker is configured in this repository;
`compileall` checks syntax and is not evidence of financial correctness.

Narrow logs are ephemeral under `/tmp/ticket43-native2.log`,
`/tmp/ticket43-compat.log`, `/tmp/ticket43-discovery-observation.log`,
`/tmp/ticket43-discovery-bounded.log`, `/tmp/ticket43-concurrency.log`,
`/tmp/ticket43-new-races.log`, `/tmp/ticket43-status-baseline.log`,
`/tmp/ticket43-batch.log`, `/tmp/ticket43-history.log`,
`/tmp/ticket43-owner-transfer.log`, `/tmp/ticket43-node.log` and
`/tmp/ticket43-host.log`. The historical upgrade logs are
`/tmp/ticket43-history-upgrade.log` and `/tmp/ticket43-rounding-upgrade.log`;
the full install/upgrade log is `/tmp/ticket43-full.log`.

## Reproduction

Run from the worktree above. Each Odoo command uses an isolated Compose project
and removes its database/volumes when finished:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-full scripts/test-addon --verify-install-upgrade
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-history-upgrade scripts/test-historical-upgrade external-native
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-rounding-upgrade scripts/test-historical-upgrade return-rounding
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-native scripts/test-addon --test-tags '/pos_revolut:TestExternalNativeReturns,/pos_revolut:TestExternalNativeAssociation,/pos_revolut:TestExternalNativeStock,/pos_revolut:TestReturnAllocation,/pos_revolut:TestRevolutRegisterRefund'
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-43-concurrency scripts/test-addon --test-tags '/pos_revolut:TestExternalNativeConcurrency'
node --test --test-isolation=none addons/pos_revolut/static/tests/revolut_payment_state.test.mjs
python3 -m unittest discover -s tests -v
python3 -m compileall -q addons/pos_revolut
git diff --check
```

The native concurrency class includes nine independent-transaction tests. Only
serialization conflicts are retried; a PostgreSQL deadlock fails the test.

## Standards

Independent review of `git diff 57e9a67...c183c2f` found no documented-standard
violations. Two initial heuristic findings were addressed: the redundant
acquisition middleman was removed and repeated manager authority validation was
shared.

One minor heuristic finding remains: possible Duplicated Code in
`return_allocation.py`'s `_native_line_auxiliary_owners` and
`_native_command_identities`. Their UPDATE/DELETE/UNLINK/LINK/SET identifier
collection has the same shape. A private shared parser could reduce duplication;
the distinct fixed-schema owner collectors and bounded database lookups are
retained for this change. The reviewer found no concrete locking regression.

## Spec

Independent review of the same candidate found no remaining specification
findings or scope creep. Both initial P2 findings were addressed: complete
previous-owner discovery for parent commands now has four LINK/SET contention
subcases, and historical association now asserts genuine completed stock and
posted credit-note identities and counts through association/replay.

Dedicated nested-command transfer races could extend coverage; the reviewer
found their fixed relation discovery and hooks consistent with the acquisition
protocol and did not identify a material acceptance gap.

Review totals: Standards — 0 documented violations, 1 minor optional duplication
heuristic; Spec — 0 remaining findings.

No schema/manifest/migration or provider contract changes are introduced.
The two affected old-release history scenarios were rerun; unrelated historical
migration scenarios were not rerun because this change introduces no schema or
migration changes. Host PDF-runtime checks remain opt-in and are reported as
skipped above. Live acceptance remains ticket 12.

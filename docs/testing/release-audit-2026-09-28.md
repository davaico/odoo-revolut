# Integrated payment safety audit — 2026-09-28

Reviewed and tested revision: `9bc9a0af448a2e34703d4484c3e9b7d84a2250be`
(`main`, POS Revolut `19.0.1.7.1`). Runtime: Odoo Community
`19.0.20260908`, PostgreSQL `16.14`.

**Result: existing automated acceptance passes, but the code is not ready for
release.** Additional adversarial and failure-path review found one high-priority
payment-verification bypass and three authorization/recovery defects. Resolve
these before ticket 12; passing the existing suite does not cover these cases.

This was an audit, not a fix implementation. No product code, ticket status,
deployment, credentials or provider transactions were changed. All provider
responses were mocked or outbound traffic was blocked. Synthetic security
fixtures were rolled back; disposable test environments were cleaned up.

## Findings

### 1. P1 — Payment verification can be bypassed through inherited order methods

Location: `addons/pos_revolut/models/pos_order.py:177–182`.

The addon checks payment/refund settlement inside `_process_order`, which
protects normal POS synchronization. It does not enforce the same invariant
through the inherited public order/payment mutation methods. Odoo's POS-role
permissions allow creation of orders and tenders; `add_payment` and
`action_pos_order_paid` can complete an order without entering this check.

In the actual pinned Odoo runtime, a synthetic non-manager, non-superuser user
with the POS-user role created a Revolut tender with a fabricated done status
and transaction reference, then marked the order paid. Assertions confirmed
`state == 'paid'`, no linked Revolut operation and zero provider operations.
All HTTP requests were blocked. Calls exercised the ORM/public methods under
that user's permissions; this was not an HTTP/browser exploit test.

Impact: an authenticated cashier can record a sale as paid by Revolut without
receiving verified payment. This is a fraud-relevant server-side enforcement
gap, not merely a bypass of a visual button. No unauthorized provider charge
or actual financial loss was caused by the test.

Correction: enforce the verification and immutable-association invariants at
the model mutation/finalization boundaries reachable through public methods,
including direct create/write paths and payment changes after settlement.
Cover both payments and returns while preserving legitimate draft saves and
normal non-Revolut workflows. Add non-superuser public-entry-point regressions;
testing `_process_order` alone is insufficient.

### 2. P2 — Public order-lock helper bypasses internal-model permissions

Location: `addons/pos_revolut/models/revolut_payment_operation.py:146–157`.

`lock_order(company_id, order_uuid)` is a public model method and directly
inserts/updates `pos_revolut_order_lock` using SQL. It does not check the caller's
role, active companies or model mutation permissions. Record rules added by
ticket 18 protect ORM reads; they do not protect this SQL path.

The same non-superuser POS-role user successfully called it for a company
outside their allowed companies. A protected internal lock row was created
and observed using the audit's privileged fixture environment, then rolled
back. Existing authorization tests deny ordinary ORM create/write operations
but do not exercise this helper.

Impact: unauthorized cross-company mutation of coordination records. This
does not demonstrate a charge, settlement, secret leak or deletion of financial
evidence. Correction: make transaction-lock internals private and unavailable
to RPC, or explicitly enforce the appropriate authorization before SQL; retain
the intended trusted internal callers. Test the public-method boundary as well
as ORM ACLs and record rules.

### 3. P2 — A failed initial lookup can strand an undispatched POS payment

Location: `addons/pos_revolut/static/src/app/revolut_payment_state.js:186–188`
and `:212–215`.

The lifecycle sets `revolutStarted` before the read-only operation lookup. If
that lookup fails before any start call, later status checks treat the retained
flag as evidence of a potentially dispatched payment. Even when the lookup
subsequently returns no operation, the line remains interrupted. Deletion,
amount editing, alternative tender and checkout remain blocked; cancellation
cannot clear it. There is no server operation for a manager to reconcile.

Reproduced against the production lifecycle module for both a payment and a
refund: the first find call throws, two subsequent finds return false, and a
cancel is attempted. Assertions prove zero start calls and continued exposure
guards. This was a controlled adapter reproduction, not a new browser tour.

Correction: distinguish preparation/discovery from an attempted financial
start. Recover safely when no start was attempted, while retaining protection
for lost start responses, prior exposure and surviving references. Add initial
lookup failure and timeout regressions for payments and refunds. Ticket 16's
protection for an already-started refund must remain intact.

### 4. P2 — Malformed provider state can abort a reconciliation batch

Locations: `revolut_payment_operation.py:264,293` and
`revolut_refund.py:248`, under `addons/pos_revolut/models/`.

A response whose outer JSON value is a dictionary but whose `state` is a list
or object passes the HTTP adapter's shape check. Set membership then raises
`TypeError`, which public polling does not catch. Both reconciliation loops
call polling without isolating an operation failure, so later healthy operations
are not processed in that batch. For malformed intent/refund states, the first
operation also remains due and can repeatedly block subsequent recovery.

The reproduction executes AST-extracted, unchanged production outcome,
polling, validation and cron methods with ORM/HTTP test doubles. Six malformed
cases reproduce the exception and skipped healthy operation; three unknown
string controls proceed and verify the healthy operation. The malformed
underlying-payment variant aborts the current batch, but its preceding valid
intent observation advances the due time, so repeated starvation was not
established for that variant. This reproduction did not run inside the Odoo
ORM scheduler: the disposable container had finished before that extra check.

Impact: error handling and recovery availability; no false verification or
financial replay demonstrated. This contradicts the malformed-response and
backoff behavior described in `docs/installation.md:140–143,217–222`.

Correction: validate response-field types before applying evidence, route
invalid data through the existing unresolved/backoff behavior, and isolate
operation failures with deliberate transaction handling. Test a malformed
first operation followed by a healthy second operation, repeated scheduling,
and preserved finality/no-replay protections. Do not blindly swallow database
errors.

## Fresh verification results

All commands below completed successfully against the reviewed revision.
Repeated install/upgrade counts are executions, not additional unique tests.

| Verification | Result |
| --- | --- |
| `./scripts/test-addon --verify-install-upgrade` | 150 fresh-install tests, 150 upgrade tests, 8 Restaurant tests; zero failures/errors |
| `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | 12 passed |
| `python3 -m unittest discover -s tests -p 'test*.py'` | 29 passed |
| `./scripts/test-restart-recovery` | Passed across two Odoo processes |
| `./scripts/test-deployment-guard` | Passed against actual disposable payment/refund records |
| `./scripts/test-delivered-addon --revision 9bc9a0af448a2e34703d4484c3e9b7d84a2250be --scenario retail` | 2 retail tests, then 8 Restaurant tests after later installation; zero failures/errors |
| Same artifact command with `--scenario migration` | 8 base-only migration tests, then 8 bridge update tests; zero failures/errors |
| Syntax/structure checks | 30 Python files parsed, 6 JavaScript files syntax-checked, 6 XML files parsed, both shell runners checked |

Both artifact scenarios used the same two-addon archive, SHA-256
`6c3122354f8f6ade668a4a415fcdb6bfe99010d8dddf9db537cc6fcac79f2a90`.
Only the extracted addons were mounted for artifact acceptance. The runtime
network was internal, and the Merchant HTTP guard was verified by the runners.
Browser transport was available; there were no logged tour-skipping warnings.
Logs contain Chrome crashpad cleanup and Odoo configuration warnings, without
test failures. No repository typechecker, linter or coverage percentage was
claimed by this audit.

## Safeguards that held within the exercised paths

- Credentials remain in server environment variables; browser code contains
  no Merchant credential or direct provider request. API hosts are fixed.
- Payment starts persist operations and claim mutating calls before dispatch;
  crashes and uncertain responses do not automatically replay mutations.
- Normal POS settlement validates the underlying payment, identity, reference,
  amount, currency, session and cart. Intent completion alone is insufficient.
  Finding 1 identifies the alternate entry points missing those checks.
- Existing race tests cover cancellation versus capture, stale observations,
  concurrent safe retry, delayed acknowledgements and manager audit failures.
- Return allocation owns original-sale locking, quantity and monetary limits,
  allocation reservations and normal settlement checks; concurrent refund and
  mixed-tender regressions pass.
- Ticket 16's lost refund-response/original-sale-read recovery, ticket 17's
  delivered Restaurant bridge, and ticket 18's direct scalar-read company
  isolation pass their existing tests on the combined revision. Finding 2 is
  a separate public-method mutation path beyond those read rules.

## Release disposition and evidence

The ticket index matches the stated status: 01, 03–11 and 13–18 are closed;
only 02 and 12 are open. That administrative status does not resolve the new
findings above. Recommended implementation order is 1, then 2, then 3 and 4;
all should be addressed before ticket 12. Ticket 02's provider/access work can
continue independently. No tickets were created or reopened by this audit.

The integrated mocked prerequisite for ticket 12 was exercised on this
revision, but release readiness remains blocked by these findings and the
external contract/live acceptance work. Retail payload compatibility, actual
Merchant behavior and physical terminal behavior remain unverified. This is
a bounded code and runtime review, not a guarantee against every attack or
possible interleaving, and not an infrastructure penetration test.

Local execution evidence (temporary files, not portable repository fixtures):

- `/tmp/revolut-audit-20260928/`: full-suite, artifact retail/migration,
  lifecycle, deployment unit, restart and deployment-guard logs.
- `/tmp/revolut-audit-20260928-direct-settlement.log`: successful actual-Odoo
  security reproduction and rollback confirmation.
- `/tmp/revolut-predispatch-repro.mjs`: production lifecycle reproduction;
  output in `/tmp/revolut-audit-20260928/predispatch-repro.log`.
- `/tmp/revolut-audit-20260928-provider-repro.py` and corresponding `.txt`:
  production Python control-flow reproduction, with stub limitations above.

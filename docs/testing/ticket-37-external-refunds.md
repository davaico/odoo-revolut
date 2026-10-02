# Ticket 37 — Discover and reconcile external refunds

Date: 2026-10-02. Branch: `codex/37-reconcile-external-terminal-refunds`.
Candidate addon: `19.0.1.13.0`.
Reviewed main baseline: `62bf951250335840d2cd6c6af8487ed4344fdcbe`.
The implementation branch was created from fetched `origin/main`; a later fetch
confirmed the baseline was still current.

The candidate records external Revolut refunds against their original Odoo
payments automatically, including payments from closed sessions. Import uses
Merchant GET requests only. It reserves active or uncertain amounts without
inventing a POS return, tender UUID, browser financial snapshot, product quantity,
cash reimbursement or accounting entry. Native reconciliation remains separate
manager work.

Final verification passed: 430 tests on fresh install, 431 on upgrade and nine
Restaurant bridge tests, all with zero failures/errors. The terminal-tip
regression was added after the install process had loaded its test list; it
also passed separately on fresh install and was included in the full upgrade.

## Implementation and exercised boundaries

The existing scheduled refund reconciliation invokes discovery. Each ordinary
run scans one eligible historical Merchant credential and one bounded interval,
using the original company, environment and credential authority. Merchant order
lists use `limit=100`; individual authoritative refund reads validate full
provider identity, original relationship, amount, currency and state. A list's
completed status or an original payment's `refunded_amount` cannot verify a
processing refund.

Persisted time intervals split full pages and restart complete history after the
normal queue drains. Recent intervals can advance during long scans. Failed or
unsplittable saturated intervals remain in a separate retry queue; every tenth
scan retries that queue. This retains blocking evidence while allowing later
windows and delayed old refunds to become visible. A malformed entry or failed
refund detail does not prevent other candidates in the same bounded read from
being processed.

One provider refund has one financial record. Discovery recognizes existing
Odoo operations by provider ID or the merchant reference, including a reference
present only in the authoritative detail after an Odoo POST response was lost.
An unidentified refund matching an uncertain Odoo attempt produces investigation
evidence instead of a second reservation. Credential locking and the original
source-row serialization boundary preserve this identity under concurrent
workers and restart scans.

External processing and unresolved refunds reserve their amounts. Conflicting
or unverified evidence can additionally block the source's whole remaining
balance. Verified failed or cancelled refunds release capacity. Provider totals
and individual records are not added twice. Original-payment pre-dispatch checks
now require a valid integer `refunded_amount`, including legacy sources; omission,
invalid types and discrepancies cannot silently authorize another POST. The
mocked GET-to-POST race retains uncertainty when the provider rejects a refund
after an intervening terminal refund. Odoo's locks do not lock physical terminal
actions.

A fully validated provider refund with no integration original in any company,
credential or state remains visible as `unrelated_source` evidence without
blocking integration balances or deployment. A missing/truncated parent,
unverified original, foreign credential, malformed identity or invalid detail
still requires blocking investigation.

The manager worklist displays provenance, original sale and separate native
reconciliation status. A manager can acknowledge completed external refunds as
handled separately; acknowledgement changes only its audit fields. Current
register grants and native visibility rules govern financial records and
investigation evidence. Pending evidence cannot finalize a native return.
No custom Revolut receipt feature is introduced.

## Mocked regression coverage

`addons/pos_revolut/tests/test_external_refunds.py` contains 33 regressions:

- Closed-session discovery of the reported processing-refund symptom, without
  a browser return or provider mutation; full/partial refunds, late completion,
  verified failure and cancellation, unknown states and exact capacity.
- Mixed cash/card sales and multiple original card allocations; no invented
  native return, accounting entries or product quantities.
- Report-verified terminal-tip originals: external totals reduce total capacity
  while unknown base/tip capacity stays unavailable, even after native-work
  acknowledgement; a new allocation fails before any provider request.
- Duplicate pages, source/refund identity conflicts, malformed amounts,
  currencies and references, interrupted detail reads and continued progress.
- Saturated-page subdivision, deferred exact-window retries, interrupted history
  windows, fresh interval progress and delayed old visibility despite saturation.
- Existing Odoo reference recovery, detail-only reference recovery, ambiguous
  lost-response attempts and a provider-enforced GET-to-POST race.
- Merchant/company isolation, unrelated historical refunds, known unverified
  originals, manager acknowledgement, cashier denial and revoked-register access.
- Independently committed concurrent discovery workers and a subsequent restart
  scan yielding one provider record and one reservation.

All provider calls in these tests are mocked. The repository's disposable Odoo
runner verifies its outbound Merchant HTTP guard. Tests use pinned Odoo Community
`19.0.20260908`; no test contacts a real terminal or Merchant account.

## Red/green evidence and final verification

The first tracer failed before discovery was registered: cron left the
closed-session processing refund absent from Odoo. `/tmp/ticket37-red.log`
records one selected test, one failure and zero errors. This exercises the
reported behavior, rather than relying on an addon build.

Lost-response reference regressions also failed before the scanner joined
references from the authoritative detail and preserved ambiguous Odoo attempts:
`/tmp/ticket37-dedup-red.log` records two selected tests and two failures.
The unrelated-source boundary was separately exercised in
`/tmp/ticket37-scope-red-valid.log` (two tests, one failure and one error before
the new evidence fields/classification). `/tmp/ticket37-scope-red.log` selected
zero tests and is not validation evidence.

| Check | Recorded result | Evidence |
| --- | --- | --- |
| Intermediate affected refund/recovery suites, fresh install | 112 tests, zero failures/errors | `/tmp/ticket37-focused.log` |
| Same affected suites, upgrade | 112 tests, zero failures/errors | `/tmp/ticket37-focused.log` |
| Intermediate external discovery suite, install and upgrade | 30 tests each, zero failures/errors | `/tmp/ticket37-external-final.log` |
| Restaurant bridge after each intermediate upgrade run | 9 tests, zero failures/errors | Both logs above |
| First full-suite attempt | 428 tests, zero failures and one register-refund fixture error; superseded by the passing final run | `/tmp/ticket37-full.log` |
| Corrected register-refund regression | One test, zero failures/errors | `/tmp/ticket37-register-refund.log` |
| Final external discovery suite, install | 32 tests, zero failures/errors | `/tmp/ticket37-scope-green.log` |
| Supplemental terminal-tip boundary, fresh install | One test, zero failures/errors | `/tmp/ticket37-tip.log` |
| Host deployment/PDF unit suite | 40 tests run, 3 renderer cases skipped | `/tmp/ticket37-python-final.log` |
| JavaScript payment-state runner | One selected test file passed | `/tmp/ticket37-js-final.log` |
| Final complete candidate, fresh install | 430 tests, zero failures/errors | `/tmp/ticket37-full-final-upgrade.log` |
| Final complete candidate, upgrade | 431 tests, zero failures/errors | `/tmp/ticket37-full-final-upgrade.log` |
| Restaurant bridge after final upgrade | Nine tests, zero failures/errors | `/tmp/ticket37-full-final-upgrade.log` |

Earlier focused upgrade failures exposed shared committed concurrency fixtures
being selected by another test's Merchant mock. Fixtures now use distinct
credential references and unschedule their discovery/refund reconciliation on
cleanup; ordinary transactional discovery fixtures explicitly make their own
credential due. This changes test isolation, not provider or deployment behavior.

There is no configured static typechecker. Python compilation, XML parsing,
JavaScript/shell syntax and whitespace checks are the applicable static checks;
they do not establish financial correctness. The final runtime results include
both source-scope regressions and the terminal-tip boundary test.

## Preserved upgrade and deployment contracts

The existing upgrade runners remain available and retain their original scope.
Results below are from candidate verification logs; historical receipt and
restart evidence is not substituted for a current run.

| Runner | Recorded result | Evidence |
| --- | --- | --- |
| `scripts/test-credential-authority-upgrade` | Passed: legacy attempt remains closed to unapproved credentials; administrator attestation and GET-only recovery preserved | `/tmp/ticket37-credential-upgrade.log` |
| `scripts/test-register-access-upgrade` | Passed: no implicit grants, late reconciliation and explicit regrant recovery preserved | `/tmp/ticket37-register-upgrade.log` |
| `scripts/test-cart-authority-upgrade` | Passed: six historical states preserved, no invented authority/tip proof, legacy refund verified | `/tmp/ticket37-cart-upgrade.log` |
| `scripts/test-deployment-guard` | Passed against payments, Odoo/external refunds and blocking discovery evidence | `/tmp/ticket37-deployment-guard.log` |

The deployment preflight checks active/uncertain external financial operations
and blocking discovery evidence in addition to existing operations. A completed
external refund may still have outstanding native reconciliation work; that
manager acknowledgement is separate from the provider financial final state.
Authoritatively unrelated-source evidence remains visible without becoming a
financial deployment blocker.

The separate historical receipt-retirement and payment restart scripts were
not rerun for this refund change. The full suite exercises native printing,
refund recovery and concurrent reconciliation; the affected historical
credential, register and cart-authority upgrade runners above were rerun.

## Code review

Standards review found no documented-standard breaches. A duplicated conversion
from provider refund state to local state was retained as a nonblocking style
observation; it follows the existing poll path without introducing a new
abstraction. Spec review found no remaining correctness or scope finding after
the deferred-window and unrelated-source fixes. Both reviews used the working
diff from reviewed main `62bf951` and the ticket's acceptance criteria.

## Dated live gate — no rollout evidence claimed

The [2026-10-02 investigation](refund-investigation-2026-10-02.md) is preserved
as historical evidence. This implementation work made no live Merchant request,
terminal operation, staging database repair or deployment. Its dated states must
be rechecked by the authorized operator before rollout.

- Source **36**, sale `261-2-000018`: preserve the sole existing card refund
  `6abf7eec-9d7d-ac78-89ab-0e6c57b0d535`, related to provider original
  `6abe3521-47d8-afea-b076-25566d3fef64`. At the checkpoint it was processing,
  amount £0.01, and absent from local refund records. The sale's separate £0.01
  Cash tender is not reimbursed by this card refund.
- Source **16**, sale `261-2-000011`: preserve existing local operation **6**,
  provider refund `6abe5180-d2fa-a57f-876c-6e12bfeb14cf`, related to provider
  original `6abbb955-4853-a1c7-9164-afb3fe751e0d`. Retain its reservation and
  original return **1012**. Its processing state blocked normal staging
  deployment at the checkpoint.

Ticket 12/operator work must reconcile current states under those references,
verify the reviewed offline upgrade is eligible, observe discovery without a
replacement refund and retain existing Odoo return identity. Product returns,
cash adjustments and accounting corrections remain explicit manager actions.

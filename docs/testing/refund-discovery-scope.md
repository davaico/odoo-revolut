# Shared Merchant refund discovery correction

## Observed failure — 2026-10-05

Deployment of the saved-return protection stopped because the financial
preflight found 15 unresolved discovery evidence records. The count was not
15 pending refunds. The scanner examines the entire approved Merchant account,
including orders created outside this Odoo integration.

Read-only provider checks found eight unfamiliar records at three locations
different from Davai's frozen integration location. Another record dated
2026-09-22 has an authenticated list parent absent from all integration
payments; its full detail omits that field. The operator does not recognize
these transactions. No cash/card classification is inferred from that fact.
Payment-list GETs returned empty arrays for these nine orders; that alone is
not treated as proof of their origin or permission to clear an investigation.

Six records concern real integration originals: sources 36, 17, 14, 11, 10
and 4. Their historical credential binding is absent. Independent GETs through
the already approved Merchant authority verified the frozen original order,
successful payment ID, amount, currency and Davai location for every source.
That missing binding is an upgrade reconciliation requirement, not a reason
to make future credential assignment implicit.

Local red regressions reproduced three defects at the existing discovery cron
boundary: missing list parents were never retrieved from full details; omitted
detail parents erased valid authenticated list relationships; and final
unlinked records at other Merchant locations blocked this integration globally.

## Corrected boundaries

Discovery complements omitted relationship fields using authenticated list and
detail observations, after validating identity, type, amount, currency and
provider state. A present null, malformed or conflicting detail parent is not
overwritten by a list parent. Full details are read once per candidate.

Known original references are associated before considering location. Missing
credential authority, unverified originals, financial ambiguity and known Odoo
refund references remain protected. There is no automatic legacy attestation.

A final unlinked observation can be retained with reason
`outside_integration_location` when its canonical provider location is absent
from every frozen integration operation and every configured payment method
using the same Merchant reference/environment, including archived methods and
unbound historical attempts. Known refund provider IDs or merchant refund keys
prevent this exclusion. Missing, invalid or integration locations and
intermediate/unknown outcomes remain blocking. Subsequent discovery rechecks
the scope and can reopen evidence when a location enters the integration.

This classification isolates integration scope; it does not claim that no money
moved at another POS. No product return, native payment, cash adjustment or
accounting document is invented. Evidence remains visible and is not deleted
or marked resolved merely because its location is outside the integration.

Before every new refund POST, the original provider payment must still report
a valid refunded amount exactly equal to its verified local refund ledger.
An unassociated external refund affecting that original therefore prevents
dispatch even when account-wide evidence is excluded by location. The saved
native return/payment requirement remains in force.

## Verification and repair

Candidate version: `19.0.1.15.2`, based on merged main `34b59ef`.
Final verification passed for exact source `01718690f355081c635c959d99d1a4e65a61e75e`.
The release archive SHA256 is
`d6fdb78e6245db5362886007129aef44b52cdbbfcbe45a422042485837efb060`.
This initial archive was not deployed; the continued historical scan
revealed the metadata-only follow-up below. Live discovery evidence is repaired only through validated GET
reconciliation; historical authority uses the existing administrator action
after independent original/payment verification. No live financial POST is
authorized or required for this correction.


| Check | Result | Evidence |
| --- | --- | --- |
| Full isolated install and upgrade | 489 tests each, zero failures/errors | `/tmp/discovery-release-isolated.log` |
| External refund regressions | 43 tests, zero failures/errors; includes known ID/key conflicts with omitted parents | `/tmp/discovery-reference-green.log` |
| Exact archive retail acceptance | 16 tests, zero failures/errors | `/tmp/discovery-artifact-retail.log` |
| Exact archive migration from deployed `30492a6` | Four groups of 16 tests, zero failures/errors | `/tmp/discovery-artifact-migration-resumed.log` |
| Financial deployment guard | Passed for payments, Odoo/external refunds and discovery evidence | `/tmp/discovery-guard-final.log` |
| POS lifecycle | 79 tests passed with test isolation disabled so individual cases execute | `/tmp/discovery-node-tap.log` |
| Deployment tooling unit suite | 40 passed; 3 optional Docker tests skipped; actual Docker guard executed separately | `/tmp/discovery-scripts-isolated.log` |
| Old deployed runtime bootstrap rehearsal | Six checks passed with mocked GETs; stored flags, conflicting references, external-only import and POST rejection exercised | `/tmp/discovery-bootstrap-old-rehearsal.log` |
| Staging rollback-only rehearsal | 19 current observations validated using 57 GETs; no native changes or financial POST | `/tmp/discovery-bootstrap-live-dry.log` |

The full suite uses an isolated worktree pinned to the reviewed source. The
earlier interrupted run on the shared checkout is not counted as release proof.
All automated Merchant requests were mocked and no live terminal was contacted
by those tests.

## Standards review

Independent review of `34b59ef...0171869`: zero remaining findings.

## Spec review

Independent review of `34b59ef...0171869`: zero remaining findings. The initial
known-reference exclusion finding was reproduced in six failing subcases and
corrected before final verification.

## Reconciliation bootstrap boundary

The old release blocks deployment on the records affected by the scope bug.
The one-time repair therefore uses exactly the six reviewed same-schema model
methods in an isolated Odoo shell process, with native protected recomputation
and an HTTP guard at `requests.sessions.Session.request` allowing only Merchant
order GETs. Running HTTP workers and installed module files are not patched.
The payload SHA256 is
`fe100985f572c24fc94348e8a4ba350c04aa98f607b733b861963585fbdbaeec`.

For every stored observation, a fresh full-order GET and authenticated list
window preserve list-only original/refund references; exact amount, currency
and existing parent observations must agree. Native counts and every existing
Odoo-origin refund identity/state must remain unchanged. Any remaining blocker
rolls back the whole repair. The first staging rehearsal rolled back all
changes. Before committing, take a database/filestore backup, briefly pause the
refund cron with its original active state persisted, and restore that state
on failure or immediately after guarded rollout. The normal deployment guard
is never weakened or bypassed.


## Oversized foreign metadata follow-up — 2026-10-05

The first committing repair correctly stopped and rolled back when continued
history discovery found evidence 490. The original refund cron state was
restored automatically. A full-order GET reports a final foreign-location
refund with positive integer metadata beyond the Odoo 32-bit ledger field;
the retained observation has amount zero because it cannot store that value.
The reported number is not treated as proof of an actual card payment/refund.

Full-detail metadata comparison now accepts positive strict integers without
applying the ledger storage bound. Matching original payments still enforce
their paid ceiling before financial imports; unknown canonical-parent
overflow remains blocking. Local, missing or invalid locations, nonfinal
states and known original/refund identities all stay protected. No financial
amount is ever derived from a zero evidence placeholder.

Final candidate: **19.0.1.15.3**, exact source
`0bc84ecf2d8fb22a94b80465eaae8943c299f9e7`. Release archive SHA256:
`1839fff5bd93ba3c8130b29c3bd95f89dea462b88d4fb9fe921b601ccfdf625d`.

| Final check | Result | Evidence |
| --- | --- | --- |
| Full isolated install and upgrade | 490 tests each, zero failures/errors | `/tmp/discovery-release-overflow-final.log` |
| Complete discovery class | 44 tests, zero failures/errors; oversized foreign regression first failed on prior code | `/tmp/discovery-overflow-red.log`, `/tmp/discovery-overflow-green.log` |
| Exact archive retail acceptance | 16 tests, zero failures/errors | `/tmp/discovery-overflow-artifact-retail.log` |
| Exact archive migration from deployed `30492a6` | Four groups of 16 tests, zero failures/errors | `/tmp/discovery-overflow-artifact-migration.log` |
| Updated bootstrap against deployed runtime | 12 checks, mocked GETs only; overflow placeholders at local/nonfinal/known-original/known-refund cases rejected | `/tmp/discovery-bootstrap-overflow-old-rehearsal.log` |
| Final staging rollback-only rehearsal | 30 observations validated with 90 GETs; native counts and Odoo-origin refund ledger preserved | `/tmp/discovery-bootstrap-overflow-live-dry.log` |

The previously passed 79 POS lifecycle cases, tooling unit checks and actual
Docker financial deployment guard remain applicable: their code and assets,
including evidence flag computation, are identical in the final candidate.

Independent Standards review: zero findings against `fb15b8f...0bc84ec`.
Independent Spec review: zero findings against `fb15b8f...0bc84ec`.

The final exact-commit reconciliation payload SHA256 is
`58c618eff623587749f9e2abb4991fef56da39e805c69f8d2dd3d3e359fd1541`.
Its bootstrap accepts a stored zero placeholder only when a fresh strict
integer exceeds the field limit and the exact reviewed reconciler classifies
the row as unresolved `outside_integration_location`. No amount is rewritten.
All other mismatches or remaining blockers roll back the transaction.

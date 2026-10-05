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
Final test, independent review and deployment results will be added after
completion. Live discovery evidence is repaired only through validated GET
reconciliation; historical authority uses the existing administrator action
after independent original/payment verification. No live financial POST is
authorized or required for this correction.

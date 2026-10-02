# Ticket 33 — Release evidence classification and publication decision

## Decision — 2026-10-02

The exact claim, **shared release evidence exposes production payment
identifiers and transaction lineage**, remains **needs-review**. The repository
contains reference-shaped values and detailed relationship mappings described
as production observations. Unauthorized disclosure is not established: the
repository is private, its owner authorizes Davai members, and neither an
authoritative alias ledger nor a restricted-store access record is available.
Confidence is high in the presence of the documented lineage and the owner
decision, but limited in identifier provenance and historical readership.

The owner requires **consistent aliases in shared release documentation**;
original references and authoritative mappings must stay restricted. The owner
confirms that no separate private evidence archive is established and requests
a plan backed by existing Odoo transaction/audit records. Public publication
must wait for preservation, aliasing and verification of the material intended
for publication. This is a publication gate, not evidence of a public incident.

Ticket 33 moves to **needs-info**, remaining open for the specific preservation
and provenance facts below. This investigation changes the prospective evidence
policy and prepares a plan; it does not redact existing financial evidence.

## Scope and provenance

- Assessed source: fetched `origin/main`, full revision
  `d1124f4c0c0736e4a0af73bb10418346d722328d`, on the assigned branch
  `codex/33-investigate-release-evidence-disclosure` in `../worktree/ticket-33`.
  The branch was clean and fast-forwarded before investigation. The original
  scan's older revision is not the assessed implementation.
- Source claim: ticket 33, scan input 6, finding
  `csf_918febafe9d4bea5889ada41`. The canceled scan had partial coverage.
- Local source/document reads and Git history only for transaction provenance;
  no live Merchant request, terminal action or production database query.
- Read-only GitHub metadata on 2026-10-02: `gh repo view
  davaico/Odoo-Revolut --json visibility,viewerPermission` returned `PRIVATE`
  and `ADMIN`. Paginated collaborator metadata returned three `admin` and
  three `write` entries; repository-team metadata returned no entries. Only
  aggregate role counts were retained, without names or provider identifiers.
  These are current access observations, not a historical access audit or
  proof of collaborators' Davai membership.
- Owner answers in this chat on 2026-10-02: current authorized readers are
  Davai members; the objective is open source; internal actions remain with
  Davai; use consistent aliases and restrict originals/mappings; plan an
  Odoo-backed private archive because none is established yet. The earlier
  owner clarification says the owner does not know whether values are original
  or anonymized. No later answer establishes that provenance.

## Inventory without live values

Locations below refer to the assessed revision. UUID shape is an inventory
aid, not proof of production origin or sensitive-data classification.

| Class | Evidence location | Classification and handling |
| --- | --- | --- |
| Merchant secret, access token, PAN, PIN, sensitive cardholder data | Operator chronology, server-only credential section, lines 155–192; release checklist, per-attempt policy, lines 271–274 | Credentials/card data must never enter shared records. The reviewed entries describe private key entry and omitted payload/card data; they contain an environment-variable name and encrypted-file paths, not a key value. No leak of these data classes is established by this claim. This is not an exhaustive secret scan of Git history. |
| Production physical location and terminal UUIDs | Operator chronology, discovery section, lines 194–217; release checklist preflight, lines 198–200 | Device/location identifiers, not authentication credentials. Alias both consistently before publication; retain their association with Merchant environment/account privately. |
| Merchant order, payment intent and underlying payment references | Operator chronology, full-payment section, lines 340–391, and subsequent payment/retry entries | Transaction identifiers with distinct meanings. Preserve order → intent → final payment and attempt relationships privately; publish separate typed aliases, including stable equality when a reference recurs. |
| Refund order and original-order/source links | Operator chronology, refund section, lines 393–486; partial-allocation and later reconciliation entries; final-state table, lines 11–39 | Financial lineage, not credentials. Preserve refund → original payment/order, allocation, reservation and outcome relationships. A refund-order identifier is not interchangeable with the original payment identifier. |
| POS sale/return and tender UUIDs; local operation, order, session and configuration IDs; receipt/display numbers | Operator chronology, payment/refund tables and retry/reload/split scenarios | Local correlation identifiers. Replace original local IDs and display references consistently too; UUID-only redaction leaves cross-system joins intact. Preserve sale → tender → attempt → provider and return → refund → original links. |
| Account/company/register names, secret-reference names/paths, currency, amounts, timestamps, states and version/checksum information | Both ticket 12 records and linked staging/acceptance records | Operational metadata, not automatically a secret. Review names, paths and precise time/amount combinations for correlation before sharing. Scenario amounts, relative timing, final states and software revisions can retain test meaning without publishing original references. |
| Published simulator identifiers and synthetic fixture identifiers | Terminal contract, controlled testing route; mocked test evidence | Distinguish documented Sandbox constants and synthetic fixtures from production evidence; do not classify every UUID in the repository as a live transaction. Scan/finding IDs are investigation provenance, not Merchant IDs. |

At the assessed revision, a local UUID-pattern inventory found **122 occurrences
and 86 distinct values within** `ticket-12-operator-observations.md`; the release
checklist contained two occurrences/two distinct values. These are per-file
counts, not a count of payments or an assertion that all values are original.
Other UUID-bearing Markdown includes the terminal contract, investigation
records and tickets with scan IDs. A cleanup must classify these hits rather
than replace all UUIDs indiscriminately. Neither new record copies live values.

## Original references versus aliases

The strongest documentary evidence for originals is the operator chronology:
the discovery section describes production GET results; the full-payment
section says provider IDs, Odoo metadata and receipt references match; the
refund section links provider `related_order_id` to the original; the later
final-state table matches displayed Merchant ID prefixes. Git history includes
the original observation commit `5ad3839` and publication commit `9babccc`,
then dated reconciliation updates. This establishes recorded provenance claims
and persistence in Git, not independent confirmation of the raw values.

The record calls these fields non-sensitive, and the earlier release policy
allowed “sanitized” UUIDs or aliases without defining a mandatory transformation.
No alias ledger or explicit transformation statement was found in the reviewed
records. Format, repetition and a matching narrative cannot establish whether
an author substituted aliases. Treat the cited values as **potential originals**
until a Davai custodian checks them against existing authoritative Odoo/provider
records inside the private archive. That check must not return originals here
or initiate a live API operation.

## Audience and boundary

The surface at issue is repository documentation and Git history, not a public
POS API or credential-bearing runtime payload. The source is operator-authored
release evidence. The possible boundary crossing is financial/device lineage
reaching readers outside Davai's authorized evidence audience.

Current repository visibility and the owner's Davai-only readership statement
defeat an assumption of current public disclosure. The owner statement supplies
current audience authorization; the metadata supplies visibility/role evidence.
Neither establishes the historical reader set or cached copies/forks. No existing separate restricted archive
or audience was verified. Proposed archive readers are designated Davai
reconciliation custodians and system administrators, subject to owner approval
and recorded access verification; future public repository readers receive only
the approved alias representation. GitHub repository roles do not grant Odoo
or Merchant permissions.

## Concrete misuse paths and counterevidence

| Path | Required controls/preconditions and assessment |
| --- | --- |
| Correlate a sale, its retries and refunds | A reader of the current records can join local and provider references, amounts, times and device association. This is the supported availability consequence. Unauthorized access to that lineage remains conditional on provenance and audience; customer identity or card details are not demonstrated. |
| Call the Merchant API with a published UUID | The shipped `_revolut_api_request` resolves frozen company/environment credential authority and sends a server-held Bearer secret (`pos_payment_method.py:607–670`). An identifier or secret-reference name does not supply that credential. No unauthenticated Merchant misuse is demonstrated or tested. |
| Find/poll/cancel through Odoo | Requires an authenticated POS user, readable payment method and allowed company; public polling validates the operation ID and sale/tender UUID pair (`pos_payment_method.py:491–535,854–962`). Known references reduce the knowledge requirement, but do not grant a login. Ticket 30 independently demonstrated register-rule bypass for an already authenticated same-company user; ticket 35 owns its correction. Do not describe current recovery as enforcing register/creator ownership. Cancellation additionally polls and requires a still-pending intent before POST; older verified/retry-safe operations cannot simply be canceled by knowing their IDs. |
| Refund or associate provider references | Refund entrypoints require POS-manager and company/method access (`revolut_refund.py:139–164,222–244`), plus source/return allocation and frozen Merchant credential authority. Association/reconciliation requires manager and record/company access (`revolut_reconciliation.py:99–105,133–177`). A historic capture may retain refundable balance; age alone does not make it immutable. Current live balances and pending states were not inspected. No extra financial authority follows from possession of UUIDs. |
| Download an old payment/refund receipt | The route requires authenticated `user`; `_operation` enforces POS role, allowed company and readable linked sale(s), then verified evidence (`controllers/receipt.py:9–23`, `models/revolut_receipt.py:14–43`). A repository reader has no demonstrated receipt access merely from an operation ID. |

Supporting evidence: production-described references, detailed joins, ambiguous
old policy and planned wider readership. Counterevidence: private visibility,
owner-authorized Davai audience, no credential/card-data disclosure established
in the cited entries, server-held authentication and role/company controls. Separate register-access
findings must not be inferred solely from UUID availability or dismissed here.
No production exploitation, public disclosure or credential compromise is
established. No new dynamic security claim is made.

## Preservation and aliasing plan — execution remains separate

1. **Preserve first.** A designated Davai custodian creates an access-controlled,
   backed-up private archive outside the future public repository. Preserve
   the original dated records and their source revisions/checksums, linked to
   existing Odoo payment/refund operations and reconciliation audits. Odoo
   remains the transaction authority; it may not contain every historical
   screenshot or observation, so retain those originals separately. Record
   archive location, owner, authorized reader roles and restore verification
   privately, with only a non-sensitive archive handle in shared docs.
2. **Create one restricted mapping.** Assign non-derivable typed aliases such
   as `terminal-A`, `sale-A`, `attempt-A`, `provider-order-A`,
   `provider-intent-A`, `provider-payment-A`, `return-A` and `refund-A`.
   These examples are invented and have no live mapping. Keep alias → original,
   environment/account, local IDs, original evidence locations and financial
   links in the archive. Do not publish UUID prefixes, raw hashes of IDs, or
   a mapping key in Git. Keep attempts, split tenders and partial refunds
   distinct while preserving repeated-reference equality across documents.
3. **Prepare a separate scoped cleanup.** Start with the two ticket 12 evidence
   files; inspect the linked ticket 12/22/23/27/28 records and staging docs for
   repeated identifiers, local display numbers, account/device metadata and
   screenshots. Use the restricted mapping to make consistent replacements.
   Preserve scenario amounts/states, ordering, release limitations and all
   financial reconciliation obligations. Keep sensitive real transaction
   joins restricted; shared alias relationships may explain the test scenario.
4. **Verify without financial requests.** Privately confirm that every alias
   resolves to its preserved original and that refund totals/source allocations,
   retry chains and outstanding dispositions remain recoverable. Check the
   complete proposed public artifact for originals, prefixes and screenshots;
   confirm it contains no mapping or private archive export. Require owner
   approval of the remaining operational metadata and archive access before
   publication. A passing software test does not prove these access facts.
5. **Treat history separately.** A current-file edit leaves earlier originals
   in Git. Assess all history/refs, attachments and previously shared copies
   intended for publication. Present a separately justified publication/history
   proposal to the owner after originals are preserved; no deletion or history
   rewrite is authorized by this investigation. A private current-file cleanup
   alone cannot clear the public-publication gate. No credential rotation or
   repository access change is warranted solely by this identifier claim.

## Targeted needs-info handoff

The owner policy is resolved; no blanket safe/unsafe decision is needed. To
complete the remaining factual assessment, a Davai evidence custodian supplies:

- A classification attestation that the cited device, provider, POS and local
  references are originals or aliases, with a private mapping/provenance check.
  If unknown, preserve and alias them as potential originals before publication.
- The private archive handle, accountable custodian, approved reader roles and
  read/restore verification. The store is currently a plan, not an existing
  verified restriction. Do not put raw values or a sensitive location here.
- If retrospective unauthorized disclosure is being asserted, the relevant
  historical readership/sharing facts. The owner has already authorized the
  current Davai audience; no repeated current-audience answer is required.
  Metadata counts alone do not establish that a reader was unauthorized.

Once those facts exist, reassess the exact claim and route any necessary cleanup
as separately approved work. Ticket 12's old-payment/refund reconciliation stays
open and retains its authoritative evidence throughout.

## Verification

This is a documentation/access decision with no runtime or type-interface
change. No new test seam is introduced, so TDD and typechecking are not
applicable. Verification results and the independent Standards/Spec review are
recorded in ticket 33; software checks do not resolve the factual gaps above.

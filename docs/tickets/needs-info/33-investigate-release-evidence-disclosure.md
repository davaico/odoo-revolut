# 33 — Determine whether release evidence exposes restricted identifiers

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/33-investigate-release-evidence-disclosure`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-33`

Work in this worktree on the assigned branch; update from reviewed main before resuming. The local investigation is recorded below; remaining evidence facts require the targeted needs-info handoff.

**State:** open

**Triage:** needs-info

**Work type:** Investigation

## What to build

A clear classification and access decision for production transaction evidence, with a safe preservation/redaction plan if repository readers exceed its authorized audience.

## Source and scope

Shared release records contain device and transaction identifiers with cross-system lineage. Existing wording permits sanitized UUIDs or aliases and is ambiguous about mandatory aliasing. Triage did not establish secret/PAN/PIN disclosure, actual repository readership, or whether the cited identifiers are sanitized.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 6: `csf_918febafe9d4bea5889ada41` — Shared release evidence exposes production payment identifiers and transaction lineage

## Acceptance criteria

- [x] Inventory the cited identifier classes and relationship mappings without copying raw live values into a new ticket or report. Distinguish credentials/cardholder data from terminal identifiers, transaction references and operational metadata.
- [ ] Establish whether values are original production references or deliberate aliases, the repository's authorized audience, and the restricted evidence store's audience. Use minimal read-only metadata or an owner answer; do not assume the repository is public.
- [x] Resolve the ambiguous evidence policy with the owner: which values may be shared and which mappings must remain restricted. Preserve the operational ability to reconcile old payments and refunds.
- [x] Assess any concrete misuse path separately from mere identifier availability, including role/UUID requirements and whether cited operations remain mutable. Do not query the live Merchant API to establish this.
- [x] Return a verdict for the exact disclosure claim with supporting and defeating evidence and remaining gaps. No secret leak or authorization bypass may be inferred solely from a UUID.
- [x] If action is required, prepare a scoped aliasing/redaction and restricted-mapping plan covering current docs and any separately justified history action. Do not delete evidence, rewrite history, rotate credentials or change repository access during this investigation.
- [x] Record a self-contained sanitized decision and evidence provenance. Missing access/classification facts require a targeted needs-info handoff rather than a blanket safe/unsafe judgment.

## Blocked by

No code dependency. Administrator-assisted sample provenance checks are complete;
private retention, custodian and recovery arrangements remain unverified. See
the follow-up and investigation handoff.

## External prerequisites

Local source/configuration and safe mocked investigation can start immediately. Actual host, access-policy or owner facts may be needed for a conclusive result; missing facts are not assumed.

## Out of scope

No publication of raw identifiers, repository-history rewrite, secret rotation or unrelated documentation cleanup.

## Release and integration relationship

Resolve evidence policy before further sharing of release material; any necessary cleanup is separately approved and preserves ticket 12's financial reconciliation evidence.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

## Owner clarification — 2026-09-30

The owner confirms that the repository is currently private and is intended to become open source. They do not know whether the recorded payment and terminal identifiers are original or anonymized. Resolve this investigation before public publication; planned publication is not evidence that public disclosure has already occurred. Establish identifier provenance and the authorized current readership. If provenance cannot be established, propose consistent aliases and a restricted authoritative mapping before publication, preserving reconciliation evidence. No history rewrite or credential rotation is authorized by these facts.


## Owner decisions — 2026-10-02

Current authorized repository readers are Davai members. The objective remains
open-source publication; internal actions stay with Davai. Shared release docs
must use consistent aliases, keeping original references and authoritative
mappings restricted. No separate private evidence archive is established;
the owner requests a plan backed by existing Odoo transaction/audit records.
These answers resolve sharing policy, but do not establish that existing UUIDs
are original or transformed, or verify a future archive's access controls.

## Investigation result — 2026-10-02

[Sanitized classification, exact-claim assessment and preservation plan](../../testing/ticket-33-release-evidence-disclosure.md)
assesses fetched main `d1124f4c0c0736e4a0af73bb10418346d722328d`.
Read-only GitHub metadata confirms private visibility, three admin and three
write collaborator entries, and no repository-team entries; no names or live
transaction values were copied. Metadata roles do not prove Davai membership
or financial-evidence authorization.

The exact disclosure claim remains **needs-review**: the records describe
production identifiers and cross-system relationships, but unauthorized
readership and original-versus-alias provenance are not established. No public
incident, credential/card-data leak or authorization bypass is inferred from
UUID availability. The related authenticated register-rule weakness remains
owned by ticket 35. No Merchant API or production database request was made.

Six acceptance criteria are complete; the provenance/audience criterion remains
open. Move to **needs-info** pending a Davai custodian's private provenance
attestation and archive handle/approved reader roles/read-and-restore
verification. The owner has established the current authorized Davai audience;
historical readership facts are needed only for a retrospective disclosure claim.
Public publication requires the preservation and aliasing plan to be executed
and the intended published history/material reviewed. No evidence deletion,
history rewrite, credential rotation or access change is performed or authorized
by this record. Ticket 12 reconciliation evidence is preserved.

## Verification

- `git diff --check`: passed.
- All 69 local Markdown link targets in the four changed documents resolve;
  the new sanitized report contains no UUIDs; the inventory counts reproduce;
  `ready-for-agents/.gitkeep` remains present.
- `python3 -m unittest discover -s tests -v`: 39 tests, 36 passed and three
  Odoo-dependent PDF cases explicitly skipped on the host.
- `node --test addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`:
  passed (one test-file entry).
- `ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket33-validation scripts/test-addon`:
  passed, exit 0; pinned Odoo package `19.0.20260908`, **375 tests, zero failures,
  zero errors**. Internal networking and the Merchant HTTP guard were enabled;
  the guard verification ran before the suite. The disposable project was
  cleaned up by the script. Local run log: `/tmp/ticket33-addon-tests.log`.
  This is fresh-install mocked addon acceptance, not a live disclosure check,
  upgrade/Restaurant matrix or completion of the host PDF skips.
- No new runtime/type interface or test seam: TDD/typechecking do not apply to
  this documentation investigation. Checks do not prove identifier provenance,
  historical readership or archive access.

## Independent code review — 2026-10-02

Pinned baseline: `d1124f4c0c0736e4a0af73bb10418346d722328d`.
Reviewed implementation commit: `7e29c59`, using
`git diff d1124f4c0c0736e4a0af73bb10418346d722328d...HEAD`.
Separate read-only subagents reviewed the two axes under the code-review skill.

### Standards

Zero findings. Scope, preservation of reconciliation evidence, ticket placement,
index update and documentation style follow repository guidance; no applicable
baseline code smell was found. Pending verification entries must be finalized.

### Spec

Zero findings. The inventory, owner decision, misuse-path assessment, exact-claim
verdict, preservation plan and sanitized provenance satisfy the investigation
requirements. The remaining factual criterion is deliberately unchecked under
the required targeted needs-info handoff; no prohibited cleanup or live
financial operation was introduced.

Review summary: Standards 0, Spec 0; no issue on either axis. Provenance and
archive verification remain factual prerequisites, not a software-test result.


## Comments

### Guided owner follow-up — 2026-10-02

The user confirms administrator access to current Odoo records and clarifies
that all Davai team members may read the private evidence. Davai is developing
the addon, rather than operating Odoo as its own POS. Their boss will have access
to everything; proposed archive responsibility remains tentative.

The administrator opened the recorded full-retail test sale, its payment,
production payment-method configuration and linked refund. Local comparisons
with the operator chronology establish exact matches for payment/order
references, location/terminal identifiers, refund/original-order references and
return/payment-line UUIDs. Only these comparison outcomes are recorded; no live
values or supplied screenshots are copied into this ticket. No agent Merchant
API or production database query was made. These are sample provenance checks,
not classification of all recorded identifiers or a secret/history scan.

The existing private repository is the current evidence location. It may remain
private with a separate sanitized public repository, or it may itself become
public after separately reviewed sanitization/history handling. The user has
not decided; a fresh public history is provisional, and no history rewrite,
access change or public creation is authorized by this discussion. Original
transaction/device references already exist in the checked records, so future
publication review covers those as well as credentials under the existing
mandatory-alias policy. The private mapping must remain recoverable whichever
route is chosen.

No maintained backup with a tested restore procedure is confirmed. The user
is unsure and thinks one may not exist; do not record that as verified absence.
Keep needs-info for permanent private preservation, accountable custodianship
and recovery evidence. The completed comparisons and whole-Davai readership
answer do not need to be asked again. Publication planning may wait until release;
this investigation does not require a new archive application or Odoo feature.

Follow-up base: fetched main `0ddde9a9b431f5e7d1c9ac83f98c5033a6274dfd`.
Documentation verification: `git diff --check` passed, all 51 local Markdown
link targets in the three changed files resolve, no UUIDs were added, the
original operator chronology is unchanged, and the ready folder placeholder is
preserved. These narrow checks cover this documentation-only change. Earlier
mocked software results remain historical evidence; no runtime code changed,
so runtime/type tests were not repeated for this follow-up.

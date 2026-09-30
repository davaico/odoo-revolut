# 33 — Determine whether release evidence exposes restricted identifiers

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/33-investigate-release-evidence-disclosure`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-33`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Investigation

## What to build

A clear classification and access decision for production transaction evidence, with a safe preservation/redaction plan if repository readers exceed its authorized audience.

## Source and scope

Shared release records contain device and transaction identifiers with cross-system lineage. Existing wording permits sanitized UUIDs or aliases and is ambiguous about mandatory aliasing. Triage did not establish secret/PAN/PIN disclosure, actual repository readership, or whether the cited identifiers are sanitized.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 6: `csf_918febafe9d4bea5889ada41` — Shared release evidence exposes production payment identifiers and transaction lineage

## Acceptance criteria

- [ ] Inventory the cited identifier classes and relationship mappings without copying raw live values into a new ticket or report. Distinguish credentials/cardholder data from terminal identifiers, transaction references and operational metadata.
- [ ] Establish whether values are original production references or deliberate aliases, the repository's authorized audience, and the restricted evidence store's audience. Use minimal read-only metadata or an owner answer; do not assume the repository is public.
- [ ] Resolve the ambiguous evidence policy with the owner: which values may be shared and which mappings must remain restricted. Preserve the operational ability to reconcile old payments and refunds.
- [ ] Assess any concrete misuse path separately from mere identifier availability, including role/UUID requirements and whether cited operations remain mutable. Do not query the live Merchant API to establish this.
- [ ] Return a verdict for the exact disclosure claim with supporting and defeating evidence and remaining gaps. No secret leak or authorization bypass may be inferred solely from a UUID.
- [ ] If action is required, prepare a scoped aliasing/redaction and restricted-mapping plan covering current docs and any separately justified history action. Do not delete evidence, rewrite history, rotate credentials or change repository access during this investigation.
- [ ] Record a self-contained sanitized decision and evidence provenance. Missing access/classification facts require a targeted needs-info handoff rather than a blanket safe/unsafe judgment.

## Blocked by

None (can start immediately).

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

# 28 — Bind Revolut credential authority to the owning company

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/28-bind-merchant-credentials-to-company`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-28`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** closed

**Triage:** ready-for-agent at closure

**Work type:** Remediation

## What to build

A company-scoped POS manager can use only the Merchant credentials authorized for that company, including connection checks, payments, refunds and recovery, without exposing credential values.

## Source and scope

Two confirmed findings show that a manager-editable environment-variable reference is restricted only by its name pattern. The owner's supported setup requires isolation between separate companies sharing an Odoo server. Exploitation requires a co-resident foreign credential and knowledge of the reference/provider identifiers; the actual staging credential inventory was not inspected.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 3: `csf_80f049f2c08527348e7c02a1` — POS manager can route requests through another company’s Revolut credential
- Scan input 26: `csf_5563e82d2fa05c79f4d2223a` — A POS manager can select another company's Revolut credential

## Acceptance criteria

- [x] Introduce or reuse a server-administrator-owned company/merchant credential authorization binding using existing Odoo conventions. Tenant POS managers cannot create, reassign or bypass that authority mapping; avoid an unnecessary secret-management framework.
- [x] Enforce the binding on configuration create/write/copy/import and at every credential use, including manager connection checks, payment start, refund dispatch, manual reconciliation and cron/restart recovery. Checking a namespace or the payment-method record's company alone is insufficient.
- [x] Changing allowed-company context, selecting a known foreign reference, supplying a foreign terminal/location, or reusing historical operation references never selects another company's Merchant authority. Keep provider origins fixed.
- [x] Define explicit migration for existing methods and persisted operations without trusting potentially misassigned existing references. Unmapped or inconsistent records fail closed with an actionable administrator remedy, preserve financial evidence/reservations, and never trigger replacement financial mutations.
- [x] Preserve authorized same-company configuration, ordinary cashier checkout, manager refunds, credential rotation and reconciliation of historical operations. New configuration does not silently change the merchant account used to resolve an existing financial attempt.
- [x] With two companies, separate mocked credentials, restricted managers and an administrator, exercise actual configuration and public server entrypoints. Assert rejection before any unauthorized HTTP request, including read-only connection checks; include valid controls and cross-company context/direct-ID variants.
- [x] Demonstrate that secret values and unauthorized reference inventories do not appear in browser payloads, errors, reports or logs. No real credential needs to be displayed or copied into evidence.
- [x] Record affected install/upgrade, checkout/refund/reconciliation and restart checks, independent Standards/Spec review and explicit security-fix verification. Document administrator provisioning/migration and precise remaining deployment steps.

## Blocked by

None (can start immediately).

## External prerequisites

None for local mocked implementation once declared design blockers are resolved. Deployment and live acceptance remain separate.

## Out of scope

No live secret enumeration/rotation, arbitrary foreign-order refunds, hosting redesign or broad POS access rewrite.

## Release and integration relationship

The fix and migration/recovery evidence must be considered before ticket 12's final release acceptance. Coordinate overlapping adapter changes with ticket 27; this is not a logical dependency.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

## Completion — 2026-10-01

The requested implementation was already integrated into reviewed `main` when
this work resumed at `57af76b26f8b1e4e126a24153ff57b480ea0180d` (also the local
`origin/main`). Original implementation `5033eb7` and administrator-attestation
correction `d52a407` remain present. This completion audit adds no runtime code.
The originally assigned worktree is now on the separate ticket 12 refund branch;
the audit and tracker update were therefore completed on the clean current
`main` branch without changing that worktree or its branch.

[Verification evidence](../../testing/ticket-28-credential-authority-evidence.md)
records the original real-Odoo mocked tests, upgrade and restart results,
follow-up administrator regression and migration acceptance, and this audit's
independent Standards/Spec and security-fix verification. Both source findings
are assessed **fixed** at the current revision. The Standards review has no
hard violations and one optional duplication suggestion; Spec has no actionable
findings. Today's 75 JavaScript lifecycle tests, Python/XML syntax and shell
checks passed. A fresh Odoo rerun was attempted but could not start because
Docker's daemon socket is unavailable and no local Odoo runtime is installed;
previous Odoo results are historical evidence, not new passes.

All implementation criteria are accepted against that combined evidence.
Administrator provisioning and fail-closed migration are documented in
`docs/installation.md`. Ticket 12 retains final combined-runtime, physical-device
and outstanding financial acceptance. This closure neither deploys an addon
nor authorizes a new live payment, refund or credential change.

## Owner-requested re-audit and corrections — 2026-10-01

The owner's follow-up requested fresh verification, correction of odd behavior
and implementation provenance. The original code was committed at 13:11:45
Europe/Paris on 1 October (`5033eb7`), followed by the first administrator ACL
correction at 13:49:04 (`d52a407`). The **T12** chat shows the agent initiating
ticket 28 as a release gate without an explicit request in that chat; reversing
the ticket closure after the owner's objection left the committed code intact.
This follow-up is authorized directly by the owner's request.

Fresh mocked Odoo execution found and reproduced two additional defects:
administrators without a POS role could not read historical attempts for
attestation, and an administrator saving an unchanged legacy method could
silently provision its old reference. Both are corrected in candidate
`19.0.1.10.3`. Connection and adapter HTTP now disable and reject redirects,
and shell instructions explicitly commit reviewed attestation. Test fixtures
now exercise the intended authorization boundary and public checkout behavior
without relying on unrelated configuration blockers, invalid fresh records or
stale caches. No production rounding logic changed.

The [updated evidence](../../testing/ticket-28-credential-authority-evidence.md)
distinguishes reproduced failures, corrections and fresh checks from the earlier
historical/static audit. Focused authority/recovery, upgrade from pre-authority
code, restart recovery and corrected browser/tip tests passed. Independent
Standards and Spec re-reviews found no actionable implementation findings.
Deployment and live acceptance remain with ticket 12.

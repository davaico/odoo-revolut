# 28 — Bind Revolut credential authority to the owning company

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/28-bind-merchant-credentials-to-company`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-28`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Remediation

## What to build

A company-scoped POS manager can use only the Merchant credentials authorized for that company, including connection checks, payments, refunds and recovery, without exposing credential values.

## Source and scope

Two confirmed findings show that a manager-editable environment-variable reference is restricted only by its name pattern. The owner's supported setup requires isolation between separate companies sharing an Odoo server. Exploitation requires a co-resident foreign credential and knowledge of the reference/provider identifiers; the actual staging credential inventory was not inspected.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 3: `csf_80f049f2c08527348e7c02a1` — POS manager can route requests through another company’s Revolut credential
- Scan input 26: `csf_5563e82d2fa05c79f4d2223a` — A POS manager can select another company's Revolut credential

## Acceptance criteria

- [ ] Introduce or reuse a server-administrator-owned company/merchant credential authorization binding using existing Odoo conventions. Tenant POS managers cannot create, reassign or bypass that authority mapping; avoid an unnecessary secret-management framework.
- [ ] Enforce the binding on configuration create/write/copy/import and at every credential use, including manager connection checks, payment start, refund dispatch, manual reconciliation and cron/restart recovery. Checking a namespace or the payment-method record's company alone is insufficient.
- [ ] Changing allowed-company context, selecting a known foreign reference, supplying a foreign terminal/location, or reusing historical operation references never selects another company's Merchant authority. Keep provider origins fixed.
- [ ] Define explicit migration for existing methods and persisted operations without trusting potentially misassigned existing references. Unmapped or inconsistent records fail closed with an actionable administrator remedy, preserve financial evidence/reservations, and never trigger replacement financial mutations.
- [ ] Preserve authorized same-company configuration, ordinary cashier checkout, manager refunds, credential rotation and reconciliation of historical operations. New configuration does not silently change the merchant account used to resolve an existing financial attempt.
- [ ] With two companies, separate mocked credentials, restricted managers and an administrator, exercise actual configuration and public server entrypoints. Assert rejection before any unauthorized HTTP request, including read-only connection checks; include valid controls and cross-company context/direct-ID variants.
- [ ] Demonstrate that secret values and unauthorized reference inventories do not appear in browser payloads, errors, reports or logs. No real credential needs to be displayed or copied into evidence.
- [ ] Record affected install/upgrade, checkout/refund/reconciliation and restart checks, independent Standards/Spec review and explicit security-fix verification. Document administrator provisioning/migration and precise remaining deployment steps.

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



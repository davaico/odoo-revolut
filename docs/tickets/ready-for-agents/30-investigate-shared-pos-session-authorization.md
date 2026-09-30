# 30 — Determine authorized access to shared POS sessions

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/30-investigate-shared-pos-session-authorization`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-30`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Investigation

## What to build

A precise access matrix showing which cashiers may initiate or recover payments on shared registers, with evidence that the addon either respects or bypasses the intended Odoo boundary.

## Source and scope

The addon checks an open same-company session with the selected method, but no explicit per-cashier register entitlement is visible. Native Odoo rules were not inspected in triage. The owner prefers explicitly authorized sessions while allowing common employee POS, and existing tests intentionally permit two cashiers to coalesce a retry.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 7: `csf_07cbc859664310f0ebdc4d36` — POS user can trigger another session's Revolut terminal
- Scan input 25: `csf_157cf1168e2a1b99dde24367` — A cashier can initiate terminal payments for another open POS session

## Acceptance criteria

- [ ] Inspect the exact pinned Odoo session/configuration record rules, groups, employee access and shared-POS semantics. Distinguish backend user, POS employee, session opener and authorized register user; do not equate them by assumption.
- [ ] Build an access matrix covering authorized same-register colleagues, explicitly unauthorized same-company register users, cross-company users and managers, including legitimate handoff/reload.
- [ ] Where policy remains undecided, present the smallest concrete choice to the owner with existing Odoo behavior and a recommended shared-register model. Do not invent exclusive ownership or silently authorize every same-company cashier.
- [ ] Use disposable pinned Odoo with mocked provider I/O to exercise direct start, find/recovery, poll, timeout and cancel entrypoints under allowed and forbidden users. Separate method-not-in-session rejection from an actual forbidden-user test.
- [ ] Document how an attacker could obtain any required operation/UUID identifiers; fresh-start reachability and existing-operation takeover have different preconditions.
- [ ] Assign a verdict to each original finding separately, with concrete native/addon controls and proof gaps. A missing creator-identity comparison is not by itself a vulnerability.
- [ ] If a bypass is demonstrated, propose the narrowest server-owned authorization boundary and compatibility tests for shared cashiers; retain a reproduction for a later remediation ticket. Do not implement permission changes in this ticket.
- [ ] Record revision, exact commands and mocked results. Missing required owner/access information leaves a specific needs-info handoff, not a false closure.

## Blocked by

None (can start immediately).

## External prerequisites

Local source/configuration and safe mocked investigation can start immediately. Actual host, access-policy or owner facts may be needed for a conclusive result; missing facts are not assumed.

## Out of scope

No blanket session-opener-only rule, credential change or generic Odoo access redesign.

## Release and integration relationship

This investigation can run alongside amount/credential work. If it establishes a new session authority requirement, coordinate the resulting remediation without retroactively assuming those independent fixes solve it.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

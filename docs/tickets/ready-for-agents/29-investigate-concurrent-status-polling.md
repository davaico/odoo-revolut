# 29 — Determine the impact of concurrent payment status polling

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/29-investigate-concurrent-status-polling`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-29`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Investigation

## What to build

An evidence-backed verdict on whether concurrent authorized status checks can violate the supported availability boundary, with a scoped remediation proposal if needed.

## Source and scope

Code allows eligible concurrent foreground polls to make independent provider reads. There is a pre-I/O legacy-state observation lock, but its transaction commits before HTTP and does not reserve the poll. The reported worker/quota exhaustion depends on unverified infrastructure and provider limits.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 4: `csf_95a9d6200acbce5037818172` — Cashier can flood Odoo workers and Revolut API with concurrent status checks

## Acceptance criteria

- [ ] Trace foreground, explicit Check status, cancellation's pre-check and scheduled reconciliation for the same operation; distinguish state-update locks from an in-flight provider-read claim.
- [ ] Inspect available pinned hosting/proxy/Odoo limit configuration read-only, recording what is guaranteed versus unknown. Do not infer a deployed limit from an example or local workstation.
- [ ] Build a bounded mocked parallel-call check with controlled pending operation and barriers. Record maximum simultaneous and total provider reads and worker behavior; exercise both foreground and cron overlap without real provider traffic or a resource-exhaustion test.
- [ ] Include legitimate multi-browser/shared-cashier status checks, terminal success, malformed/failed reads and late success as controls. Determine whether a proposed cadence or lease would delay financial reconciliation or permit stale success.
- [ ] Return confirmed, not_actionable or needs_review for the exact source claim, with evidence and the minimal unresolved fact. A visible fan-out alone does not prove a production outage or exhausted provider quota.
- [ ] If warranted, specify a narrow shared poll lease/cadence including crash/expiry, stale snapshot behavior, fairness and tests. Do not implement it in this investigation or broaden into global rate-limiting infrastructure.
- [ ] Retain a self-contained evidence artifact and linked source ID. If external facts remain essential, mark the investigation needs-info with a concrete human request rather than closing it as safe.

## Blocked by

None (can start immediately).

## External prerequisites

Local source/configuration and safe mocked investigation can start immediately. Actual host, access-policy or owner facts may be needed for a conclusive result; missing facts are not assumed.

## Out of scope

No live stress tests, real Merchant calls or automatic poll-behavior changes.

## Release and integration relationship

Resolve applicability before relying on an availability claim for final release; any demonstrated defect needs separate approved remediation.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.



# 29 — Determine the impact of concurrent payment status polling

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/29-investigate-concurrent-status-polling`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-29`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** closed

**Triage:** ready-for-agent at closure

**Work type:** Investigation

## What to build

An evidence-backed verdict on whether concurrent authorized status checks can violate the supported availability boundary, with a scoped remediation proposal if needed.

## Source and scope

Code allows eligible concurrent foreground polls to make independent provider reads. There is a pre-I/O legacy-state observation lock, but its transaction commits before HTTP and does not reserve the poll. The reported worker/quota exhaustion depends on unverified infrastructure and provider limits.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 4: `csf_95a9d6200acbce5037818172` — Cashier can flood Odoo workers and Revolut API with concurrent status checks

## Acceptance criteria

- [x] Trace foreground, explicit Check status, cancellation's pre-check and scheduled reconciliation for the same operation; distinguish state-update locks from an in-flight provider-read claim.
- [x] Inspect available pinned hosting/proxy/Odoo limit configuration read-only, recording what is guaranteed versus unknown. Do not infer a deployed limit from an example or local workstation.
- [x] Build a bounded mocked parallel-call check with controlled pending operation and barriers. Record maximum simultaneous and total provider reads and worker behavior; exercise both foreground and cron overlap without real provider traffic or a resource-exhaustion test.
- [x] Include legitimate multi-browser/shared-cashier status checks, terminal success, malformed/failed reads and late success as controls. Determine whether a proposed cadence or lease would delay financial reconciliation or permit stale success.
- [x] Return confirmed, not_actionable or needs_review for the exact source claim, with evidence and the minimal unresolved fact. A visible fan-out alone does not prove a production outage or exhausted provider quota.
- [x] If warranted, specify a narrow shared poll lease/cadence including crash/expiry, stale snapshot behavior, fairness and tests. Do not implement it in this investigation or broaden into global rate-limiting infrastructure.
- [x] Retain a self-contained evidence artifact and linked source ID. If external facts remain essential, mark the investigation needs-info with a concrete human request rather than closing it as safe.

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

## Initial investigation handoff — 2026-10-02 (superseded below)

Verdict for `csf_95a9d6200acbce5037818172`: **needs_review**. Three authorized
same-operation provider reads run simultaneously; the bounded foreground,
shared-cashier browser, cancellation and cron cases and financial controls are
recorded in [the self-contained evidence](../../testing/ticket-29-concurrent-status-polling.md).
No outage or Merchant quota exhaustion was demonstrated. The investigation
adds only mocked characterization tests and documentation; no poll lease or
runtime behavior change was implemented.

Assessed runtime: reviewed main `dad0e1515ee7b936834906f810f50999f3e33da9`,
fast-forwarded into the assigned branch before work. Focused concurrency file:
30 tests passed, including six new checks. Final full acceptance passed
362 install, 362 upgrade and nine Restaurant tests; lifecycle passed 75 tests
and the deployment guard passed. Standards and Spec reviews report zero
findings. Retained
[machine-readable counts](../../testing/ticket-29-poll-observations.jsonl)
exclude setup traffic and contain no real transaction identifiers.

The owner has no known capacity/quota facts and authorized using a recommendation.
Proposed assessment target: two active cashiers with up to two tabs each;
shared per-operation observation with approximately one-second cadence. This
is a recommendation, not proof of deployment capacity or a checkout SLA.

**Human request:** provide redacted effective Odoo worker/request/time/memory
settings and service overrides; applicable Cloudflare or actual proxy
admission/rate rules; and the Merchant endpoint/account quota and retry policy.
The evidence artifact names the configuration locations, relevant options and
Revolut API Support contact. These facts are still essential to decide the exact
availability/quota claim, so this ticket remains open under needs-info instead
of closing it as safe. The artifact specifies a narrow lease/cadence proposal,
crash/expiry fencing, cancellation freshness, fairness limits and required
regressions for separate approved remediation.

## Completed investigation — 2026-10-02

The assigned branch was fast-forwarded to fetched reviewed main
`3dfe7bd691a3b89b806e5e03ef1bfd9d600394b7` before follow-up work. The owner
supplied the effective host limits, Revolut's reply and the unfiltered
Cloudflare dashboard. No required human fact remains missing for the scoped
contention verdict: two HTTP workers/one cron worker are effective, no zone
rate-limit or custom rule is configured, and Revolut imposes no explicit
endpoint/account quotas but may return 429 with server-generated `Retry-After`.
The evidence distinguishes read-only verified settings from owner-forwarded
support/dashboard observations and from unknown automatic DDoS thresholds.

Verdict for `csf_95a9d6200acbce5037818172`: **confirmed duplicate-read HTTP
worker contention under controlled slow provider responses**. In the actual
two-worker disposable Odoo server, cashier one's two tabs hold both workers on
the same pending operation. Cashier two's two polls and an unrelated
authenticated RPC cannot progress until release. The unrelated read takes
2.090344 seconds during the two-second hold, compared with 0.017291 seconds
before and 0.109142 seconds with only one provider read held. All four polls
return pending, making four mocked intent GETs and no financial POST. Separate
sessions and the one-held/before/after controls isolate worker admission from
session locks. Scheduled jobs are quiesced only in this fixture; existing
transaction tests preserve cron/cancellation overlap and late-success controls.

[The complete evidence](../../testing/ticket-29-concurrent-status-polling.md)
and [machine-readable HTTP-worker observation](../../testing/ticket-29-http-worker-observation.json)
retain the runnable fixture, baseline, counts, limits and verification history.
No live stress test, Merchant request, sustained exhaustion or production outage
is claimed. Fixed Merchant quota exhaustion is not demonstrated; unpublished
gateway throttling remains possible. No checkout SLA or general four-tab
capacity guarantee follows from this bounded test.

Final verification passed the actual two-worker probe, 431 install/431 upgrade
checks, nine Restaurant checks, 75 lifecycle tests and 40 host unit checks
(three environment-dependent skips). Both full-suite phases reproduced all
seven original characterization records. The initial full install's receipt UI
timeout is preserved in the evidence; that test passed in isolation and the
final complete rerun passed without browser-start failures. Independent
Standards and Spec review of the completion patch reported zero findings.

This closes the investigation **without changing runtime behavior**.
[Ticket 38](38-coalesce-concurrent-payment-status-polls.md)
records the separate coalescing/cadence/crash-fencing and 429 recovery work.
At investigation closure it was under needs-triage pending owner approval;
its subsequent approved implementation and verification are recorded there.
Investigation closure is not a
contention fix or release acceptance; ticket 12's rollout/device work stays open.

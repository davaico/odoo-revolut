# 38 — Coalesce concurrent payment status polls

**Work branch:** `codex/38-coalesce-payment-status-polls`

**State:** claimed

**Triage:** ready-for-agent

**Work type:** Approved implementation (owner request, 2026-10-02).

## Problem and intended behavior

[Ticket 29](../closed/29-investigate-concurrent-status-polling.md) investigates
source claim `csf_95a9d6200acbce5037818172`. Eligible callers for the same
pending operation can independently read Revolut while occupying separate Odoo
HTTP workers. The effective target has two HTTP workers, and the proposed
deployment supports two cashiers with up to two tabs each. Financial evidence
locks do not reserve the provider observation.

Use one server-owned, persisted observation claim per payment operation so
redundant callers promptly receive the latest safe snapshot instead of blocking
another HTTP worker on the same external read. Reconciliation must continue
after a browser disappears, an error, or a worker crash. Do not change financial
dispatch idempotency or treat cached pending evidence as permission to settle,
retry or cancel.

## Source and design evidence

[The investigation](../../testing/ticket-29-concurrent-status-polling.md)
records the source ID, pinned revisions, mocked concurrency controls, effective
host settings, Cloudflare rule observation, Revolut's support reply and a narrow
lease/cadence proposal. No fixed Merchant endpoint/account quota was supplied;
unpublished gateway thresholds may return 429 with `Retry-After` in seconds.
Coalescing does not guarantee account-wide admission or sufficient capacity
for simultaneous observations of different operations.

## Acceptance criteria

- [ ] Preserve the existing register/company/credential authority checks before
  claim acquisition or cached result access. Do not expose new credential data.
- [ ] Atomically claim an operation-specific token with a fixed expiry in a
  short owned transaction, committing before HTTP. Foreground, Check status,
  cron, manager reconciliation and cancellation pre-checks share the claim.
  Cover intent/payment reads and subsequent authenticated tip/report/order
  reconciliation; retain separate financial-dispatch/report-creation claims.
- [ ] Losing callers return the latest persisted snapshot promptly, with
  server-owned freshness/in-progress and bounded next-check advice. They make
  no duplicate provider read, wait in no worker, renew no lease and postpone no
  cron due time. Persisted verified evidence remains authoritative; incomplete
  evidence never permits settlement, safe retry or payment-line removal.
- [ ] Apply approximately one-second cadence between observation starts using
  a controlled clock. Set explicit bounded provider phases and justify the
  lease margin. Requests' per-read timeout is not an absolute RPC deadline.
  Document any remaining physical HTTP overlap after expiry rather than
  promising single-flight without actual deadline/cancellation enforcement.
- [ ] Fence every apply/release with the original token. Expired or crashed
  holders cannot overwrite newer observations or release a successor's claim.
  Foreground and cron can resume without caller affinity or sliding expiry.
- [ ] Cancellation dispatch requires fresh eligible provider evidence and its
  existing unique dispatch claim. A busy/stale check sends no cancel POST;
  post-cancellation recovery stays eligible without replaying financial calls.
- [ ] Keep malformed, timeout, 503 and 429 outcomes unresolved. Respect valid
  `Retry-After` seconds without blocking a worker or silently caching successful
  financial evidence. Test invalid header handling, deferred observation and
  late capture. Do not infer a numeric Merchant quota or account-wide limiter.
- [ ] Cover two cashiers/four tabs, same-operation overlap with cron and cancel,
  exact HTTP counts, final caches, cadence boundaries, crash before/after HTTP,
  expiry/fencing, no renewal by losers, distinct-operation independence,
  authenticated tip/report evidence and existing financial race controls.
- [ ] Reuse the local two-HTTP-worker probe: a duplicate call must leave a worker
  available for the unrelated authorized RPC while the first provider read is
  held. Report observation/recovery delay and retain the two distinct-operation
  capacity limitation. Run focused and full mocked install/upgrade/Restaurant
  acceptance; real terminals and Merchant calls remain excluded.

## Dependency and approval gates

Investigation 29 must be closed with a scoped verdict and reproduction before
implementation. The owner must approve this remediation and the proposed
cadence/expiry/reconciliation-delay tradeoff. This ticket's presence does not
grant that approval, change a release gate, or authorize deployment.

## Out of scope

Global rate-limiting infrastructure, Cloudflare rule changes, HTTP-worker
provisioning, live stress tests, payment dispatch redesign and production
deployment. Ticket 12 retains separately authorized rollout and device testing.

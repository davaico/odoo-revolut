# Ticket 38 — Coalesced payment observations

Implementation starts from fetched `origin/main` at `12ad4bf` on
`codex/38-coalesce-payment-status-polls`. The owner approved implementation on
2026-10-02 and confirmed the public status/cancel RPCs, manager/cron entry points
and local two-worker probe as test seams. Ticket 29 is closed. No deployment,
real terminal interaction or live Merchant request is part of this work.

## Behavior and authority

One persisted operation-specific observation token owns the existing intent,
payment and authenticated tip/report/order evidence pipeline. It is committed
in a short independent transaction before provider I/O. The same observation
boundary covers foreground polling, Check status, manager reconciliation,
cron and cancellation's fresh precheck and immediate recovery. Financial
order/intent/cancel dispatch claims and the report-creation claim stay separate.

Register, company, UUID ownership and frozen credential authority are checked
before claiming or returning a cached observation. A missing historical
credential retains the blocked attempt and administrator remedy without
interrupting the rest of cron's batch. Final cached evidence requires credential
authority. Tokens and credentials are absent from browser snapshots; operation
observation fields cannot be supplied through ORM create/write.

Losing callers read the latest persisted snapshot. They perform no provider
request, do not wait for the winner, and change neither lease expiry nor cron
due time. Snapshots include `observation_in_progress`, `observation_fresh`,
`observation_finished_at`, and `next_check_seconds` (1–60 for non-final results,
0 for verified/retry-safe finals). Freshness is specific to the RPC that finished
the observation; subsequent caches have `observation_fresh: false`. Final
financial evidence stays authoritative regardless of cache freshness. Pending,
intent completion and partial tip evidence never authorize settlement or retry.

Every provider evidence application and lease release compares the original
token and its unexpired lease under the existing financial lock order. A late
or expired holder cannot overwrite a successor or release its token. A crash
leaves a durable fixed lease; foreground or cron can acquire it at expiry.
No browser, worker or cashier affinity and no sliding renewal is required.

Cancellation holds the shared lease across its fresh precheck, unique cancel
claim, POST and immediate recovery. The dispatch transaction rechecks the token,
expiry, phase budget and eligible pending evidence. Busy/cadence-cached checks
send no POST. Recovery bypasses a second cadence gate under the same lease;
an uncertain cancellation never replays its financial request.

## Cadence, budgets and recovery delay

Observation starts are at least one second apart, measured with a controllable
UTC clock that retains subsecond precision. Normal foreground deferral adds at
most the remaining one-second cadence; cron retains its existing minute schedule
and outcome backoffs. Losing callers never move that schedule.

The lease is fixed at 60 seconds. Intent plus payment have a cooperative
20-second elapsed budget; authenticated report status/create, file and order
have a cooperative 30-second elapsed budget. The whole observation has a
50-second elapsed budget, leaving ten seconds for local transactions and
scheduling before lease expiry. Cancellation's two observation passes and POST
share that overall budget. Each request's connect/read timeout is at most ten
seconds and is reduced to the remaining phase budget. Budget/lease checks occur
before and after calls and while consuming report chunks. Report bodies retain
their existing byte, row and cell bounds.

These checks **do not enforce an absolute RPC or physical HTTP deadline**.
Requests' connect/read timeout is not a total-body deadline, and a blocked read
cannot be forcibly cancelled by the cooperative checks. A stalled old request
can therefore physically overlap a new request after lease expiry. Fencing
protects persisted evidence in that case; strict physical single-flight is not
claimed. Worker crashes can add up to the remaining 60-second lease before
foreground recovery, or that interval plus cron's minute schedule and existing
outcome backoff when only cron is active.

Malformed, timeout, 503 and 429 results remain unresolved. A 429 `Retry-After`
containing integer seconds (optional surrounding whitespace, up to ten digits
and PostgreSQL integer range) persists an observation-not-before timestamp.
Invalid, negative, fractional, date-form or oversized values fall back to the
existing unresolved outcome policy. Neither a deferred foreground check nor
cron sleeps in a worker; advice is capped at 60 seconds, while the actual
provider deferral is preserved. Deferred observations cannot hide a successful
payment: once eligible, authenticated late capture still verifies the original
references without redispatch. No numeric Merchant quota or account-wide
limiter is inferred.

## Two-worker measurement

Run `scripts/investigate-status-poll-workers --coalesced`. The historical
investigation mode remains available without that flag. The probe uses two
HTTP workers, one quiesced cron worker, two explicitly authorized cashiers and
four independent authenticated browser sessions. All provider waits are
bounded mocks; the network is internal and Merchant HTTP guard is enabled.

The measured four-tab shared-operation scenario made **one provider GET**.
Three duplicate RPCs returned in 0.116, 0.184 and 0.154 seconds while the
winner's read was held. An unrelated authorized RPC completed in 0.011 seconds
while that read remained held. The next shared-operation provider start was
1.122 seconds after the earlier start. No financial POST occurred.

Two distinct operations still made two concurrent held GETs in the two workers.
The unrelated RPC then took 2.055 seconds across a deliberate 2.000-second hold.
Coalescing therefore solves duplicate-operation contention without guaranteeing
capacity for different operations or account-wide admission. These are local
fixture measurements, not production latency or Merchant quota guarantees.

## Verification

The first concurrency tracer failed against the unchanged addon because its
persisted observation contract was absent. It passed after implementation.
Precise cadence boundary, deferred/error recovery, fencing/crash and authenticated
report tests exercise the approved public interfaces with real owned cursors
and mocked transport. Existing payment, tip and financial-race fixtures advance
the controlled clock when explicitly asking for a new observation; cache
comparisons preserve all financial fields and require non-fresh metadata.

Final commands and results are recorded below after execution. There is no
configured static type checker in this Odoo repository; Python compilation,
JavaScript syntax/unit checks, shell checks and the actual Odoo runtime tests
provide the applicable validation.

# 21 — Keep reconciliation progressing after malformed provider responses

**Work branch:** `codex/21-isolate-reconciliation-failures`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-21`

**Parallel work:** Only T20 and T21 run in parallel; coordinate shared-file edits and check for conflicts before merging.

**State:** closed

**Triage:** ready-for-agent

**Priority:** P2

## What to build

Unexpected provider response data leaves the affected payment or refund
safely unresolved with a scheduled retry, while other due operations continue
to reconcile. Cashier checks, manager checks and scheduled recovery use the
same validated evidence rules without falsely completing a sale or repeating
a financial mutation.

## Observed problem

The integrated audit on 2026-09-28 at revision `9bc9a0a` reproduced a provider
state containing a list or object escaping polling as an uncaught type error.
The reconciliation loop then skipped later healthy operations. For malformed
intent/refund states, the earliest operation remained due and could repeatedly
abort the batch. The malformed underlying-payment case aborted its current
batch, but the preceding valid intent observation advanced its next due time.
No false verification, financial replay or attacker control of provider
responses was demonstrated.

## Acceptance criteria

- [x] Validate provider evidence types before applying payment-intent, underlying-payment and refund outcomes. Lists, objects, missing states and unsupported values cannot escape as unhandled shape/type errors or be interpreted as final success/failure. Retain identity, relationship, amount and currency checks, and validate malformed evidence through the existing outcome owner.
- [x] Malformed or inconclusive evidence preserves references, dispatch claims, financial blocks and refund reservations. Apply the documented unresolved state and bounded retry/backoff behavior; a later valid read can recover the same operation without a new mutating request or idempotency identity.
- [x] An operation-specific provider/parsing failure cannot prevent a later healthy due payment or refund from being reconciled in the same scheduled run. A persistently malformed oldest operation receives deliberate scheduling and cannot repeatedly monopolize the batch. Preserve bounded batch size and valid terminal outcomes.
- [x] Isolate recoverable failures with transaction-aware handling. Roll back or end a failed transaction before continuing; do not broadly suppress database errors, falsely report successful recovery, erase committed provider evidence or regress a verified outcome. Define how transient concurrency conflicts are rescheduled without financial replay.
- [x] Cashier and manager status checks report a sanitized, actionable unresolved result for malformed provider evidence. Scheduled failures remain diagnosable without logging credentials or sensitive provider payloads. Preserve manager audit guarantees and existing behavior for transport interruptions and unknown string states.
- [x] Add actual pinned-Odoo regression tests for payment and refund cron entry points with at least two due operations: malformed evidence for the first, valid successful evidence for the second. Cover intent and underlying-payment variants separately, repeated runs/backoff, both list/object states, unknown/missing states, eventual valid recovery and zero mutating requests during reconciliation.
- [x] Verify transaction isolation and durable results using production transaction ownership, including an operation-local failure and a successful later operation. Preserve stale-poll/cancellation finality, restart recovery and manager reconciliation regressions. In-memory or AST-extracted test doubles alone do not satisfy this ticket.
- [x] Record the reviewed revision and focused polling, scheduled recovery, concurrency and restart test results; update failure/backoff guidance if needed. All provider calls are mocked or blocked and no live terminal access is required.

## Blocked by

- None. Existing payment/refund reconciliation foundations are implemented. Tickets 02, 19 and 20 do not gate this mocked correction.

## Release gate

Blocks ticket 12. Integrate and review this correction before live acceptance.

## Scope and execution

Addresses audit finding 4. Keep payment outcome rules under their existing
owner, provider I/O outside locked evidence application, and explicit refund
semantics. Local validation/transaction prefactoring is allowed where needed;
this is not a new job-queue framework or automatic mutation-retry mechanism.

The declared work branch has been created from the committed ticket baseline.
Update it from reviewed main before implementation without overwriting existing
work. Use an isolated worktree for concurrent work.

## Verification evidence

Implementation started from freshly fetched, reviewed main
`5081551d77a5db6d62b84965f5c115bd8f3cb236`, including ticket 19. The assigned
branch was fast-forwarded in its existing isolated worktree without overwriting
work. Ticket 20's separate worktree remains untouched; its manifest uses
`19.0.1.7.3`, so this schema update uses `19.0.1.7.4`.

The original audit used unchanged methods with ORM/HTTP doubles. The correction
now has actual pinned-Odoo regressions, using committed fixtures and ordinary
registry cursors without registry test mode. Red runs reproduced a list intent
state, an object refund state, and a genuine PostgreSQL serialization failure
aborting the scheduled action. Further red tests caught malformed intent
payment references releasing retry safety and intent observations resetting
backoff before a failed underlying-payment read.

Focused verification on 2026-09-28, with all provider calls mocked and Merchant
HTTP blocked:

- `TestRevolutRecoveryBatches`: 17 passed, zero failures/errors. Payment and
  refund cron entry points include malformed-first/healthy-second cases,
  list/object/missing/unknown/numeric/boolean states, repeated bounded
  scheduling, later valid recovery, batch limits, GET-only requests, real
  transaction rollback, exhausted serialization/deadlock conflicts, an
  unsuppressed unexpected constraint error, and sanitized cashier/manager
  checks with manager audit preservation.
- Affected payment, refund, manager reconciliation, retry concurrency and
  refund concurrency classes: 114 passed with the first 14 new regressions;
  the final 17-test class passed separately after adding manager refund and
  batch-limit coverage.
- `./scripts/test-restart-recovery`: passed across two independent Odoo
  processes (`RESTART_RECOVERY_OK`).
- Node POS state test file passed; deployment-tool unittest suite: 29 passed.
- Python compilation and `git diff --check` passed. No typechecker is
  configured in this dynamic Odoo repository; compilation is a syntax check,
  while pinned-runtime tests exercise the changed behavior.

Both independent review axes identified the same mixed-history scheduling
gap: a malformed payment read after a transport failure inherited the
transport delay instead of the documented five minutes. A new pinned-Odoo
regression reproduced that gap before the correction. At
`0f2b6b5110e470b436168ee60c64761b734fd00c`, unknown evidence always waits
300 seconds regardless of its retained transport counter. All 18 focused
recovery tests passed, including interruption → malformed evidence → valid
recovery. Restart recovery passed again on this corrected revision. The first
full run was stopped when review identified the gap; final full verification
uses the corrected, stable revision instead.

## Standards review

No remaining Standards findings on `0f2b6b5`.

The earlier finding is resolved: unknown evidence now always schedules a
300-second delay, independently of retained transport failures. The added
regression exercises transport interruption, malformed underlying-payment
evidence, and valid recovery through the existing mocked reconciliation path.

No additional documented-standard breaches or actionable baseline smells
found. No tests executed during this review.

## Spec review

The backoff finding is resolved at `0f2b6b5`: unknown evidence now always
schedules a 300-second delay, independently of prior transport failures. The
new pinned-Odoo regression covers interruption → malformed underlying
payment → valid recovery.

No remaining actionable Spec findings or scope creep identified.

Review totals: Standards 0 remaining findings (worst issue: none); Spec 0
remaining findings (worst issue: none).

## Final verification

Reviewed and tested implementation:
`0f2b6b5110e470b436168ee60c64761b734fd00c`.
Final evidence/closure changes contain documentation only. Odoo is the pinned
Community package `19.0.20260908`; the addon is `19.0.1.7.4`.

| Verification | Result |
| --- | --- |
| `./scripts/test-addon --test-tags /pos_revolut:TestRevolutRecoveryBatches` | 18 passed, zero failures/errors |
| `./scripts/test-addon --verify-install-upgrade` | 203 fresh-install tests, 203 upgrade tests, 8 Restaurant tests; zero failures/errors; exit 0 |
| `./scripts/test-restart-recovery` on the reviewed revision | `RESTART_RECOVERY_OK`; independent processes; exit 0 |
| `node --test addons/pos_revolut/static/tests/*.test.mjs` | POS state test file passed, zero failures |
| `python3 -m unittest discover -s tests` | 29 deployment-tool tests passed |
| Python compilation; `git diff --check` | Passed; no configured typechecker |

The full suite includes existing stale foreground/scheduled polling,
cancellation finality, manager association/audit rollback, retry concurrency,
refund concurrency, partial allocations and POS settlement regressions. The
new tests explicitly inject PostgreSQL `40001` and `40P01` errors inside owned
transactions, observe closed failed cursors and durable results from fresh
cursors, and prove unrelated constraint errors are not suppressed. Provider
traffic is mocked or blocked, with GET-only assertions during reconciliation.

Local main and `origin/main` were rechecked at `5081551`. Ticket 20's independent
implementation is not included in this revision. Before ticket 12, integrate
the separately reviewed corrections and perform its combined release checks.
This ticket changes no staging environment or Merchant credentials. Its
installation guidance documents the required stopped-service module upgrade,
new refund counter, failure scheduling and manager/cashier recovery actions.

## Quality self-check

Agent self-evaluation: 4.6/5 across five axes; no critical issues.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 5 | Actual pinned-Odoo red/green runs, full install/upgrade and restart results support the recorded behavior. |
| Completeness | 5 | All acceptance criteria have runtime evidence, operating guidance and independent standards/spec review. |
| Clarity | 4 | The long ticket preserves the audit and red/green history; the final verification table provides the current results first for future reviewers. |
| Actionability | 5 | Reviewed commits, reproducible test commands, the upgrade version and recovery procedure are recorded. |
| Conciseness | 4 | Real transaction fixtures make the 593-line regression file substantial; reuse its setup if further recovery cases are added. |

Improvements: use the final verification table for current results, and reuse
the committed-cursor fixtures rather than duplicating them in future tests.
Self-check: the task delivers the requested implementation and commit with
reviewed, reproducible evidence. Deliver as-is.

## Triage decision

2026-09-28: The owner approved this three-ticket breakdown and direct
publication as ready-for-agent. All three corrections are independently
actionable with mocked provider calls and block ticket 12. Recommended priority
is 19, then 20, then 21; this is not a dependency chain.

# Ticket 29: concurrent status polling investigation

Assessment date: 2026-10-02. Exact source claim:
`csf_95a9d6200acbce5037818172`, scan input 4, **Cashier can flood Odoo workers
and Revolut API with concurrent status checks**. Parent scan
`95c73550-ed81-4cfe-9e81-b6f2be355a38` was cancelled with partial coverage.

## Verdict and remaining evidence

**`needs_review`**. Three authorized calls for the same pending operation can
simultaneously enter independent provider reads. They occupy three local
request threads until the mocked provider is released. State locks protect
financial evidence but do not coalesce these reads. This establishes duplicate
work and a plausible availability concern, not a deployed outage, exhausted
Merchant quota, or a demonstrated breach of the supported capacity.

Ticket 29 remains **open / needs-info**. The minimum unresolved fact for the
outage claim is the effective supported deployment's admission/capacity boundary
under slow provider reads. The independent quota claim needs the applicable
Merchant account/endpoint limits. Neither can be inferred from local thread
counts, a provisioning template, or Business API limits.

The owner said on 2026-10-02 that these capacity facts were unknown and asked
for a recommendation. Proposed support target: two active cashiers, up to two
tabs each; one in-flight observation per operation, shared across all callers;
approximately one-second cadence while actively observing. These are proposed
requirements, not observed traffic or an accepted deployment guarantee. A
normal coalesced observation should add at most one cadence interval plus the
provider latency. Existing asynchronous tip-report availability and minute
cron scheduling prevent promising a one-second checkout or recovery SLA.

No production behavior, financial dispatch, hosting configuration, or release
gate changed. No live terminal, Merchant traffic, stress test or host inspection
was performed. The source claim remains open, including under ticket 12.

## Revisions and reproducible scope

- Assigned branch: `codex/29-investigate-concurrent-status-polling`, in
  `../worktree/ticket-29`; clean assigned worktree fast-forwarded from `080f3fb`
  to reviewed local main **`dad0e1515ee7b936834906f810f50999f3e33da9`** before
  claiming work. This supersedes scanned revision `1d549c1` for this assessment.
- Runtime addon code is unchanged from that baseline. Six characterization
  tests and their bounded helper extend the existing independently committed
  transaction fixture in
  [test_revolut_retry_concurrency.py](../../addons/pos_revolut/tests/test_revolut_retry_concurrency.py).
  Its tested SHA-256 is
  `dcd59e8760d9425d2635104f7b66725bbe0be8bdc5901f90e611ffddd34ae7e0`.
- Pinned Odoo package: `19.0.20260908`; PostgreSQL `16.14-bookworm`, digest
  `64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8`.
  Built test image: `sha256:853784cf282363067d5a0efe825bc079e00fce89f89b1bff2ebae00fc576ce6d`.
- Runtime network is Compose `internal: true`; Merchant request interception
  is verified by the runner before loading Odoo. Every expected provider call
  uses mocked `requests.request`, including report CSV/order evidence. The
  only secret fixture is a test-only environment value. Identifiers in the
  experiment are randomly generated; no credentials or real transactions are
  recorded in its evidence.

## Call paths and the actual locking boundary

| Caller | Entry and behavior | Shared admission guarantee |
| --- | --- | --- |
| Foreground wait | `RevolutPaymentState.request()` deduplicates a request within one owner instance; `waitForResult()` performs sequential server polls with a one-second wait and a 60-second browser deadline | Per-browser owner only; another tab can create another owner |
| Explicit Check status | Same state-machine request with `checkOnly`; discovers an existing operation and calls `revolut_poll_payment` immediately, then follows the same loop | No cross-browser/provider claim; no new charge |
| Cancellation pre-check | `revolut_cancel_payment()` calls `revolut_poll_payment` before eligibility; its POST is uniquely claimed, and a second poll follows cancellation | Cancellation POST claim is not a read claim |
| Scheduled reconciliation | `_cron_reconcile_payments()` selects up to 50 due attempts, then invokes the same poll method sequentially; cron XML schedules it every minute | No per-operation claim shared with foreground; cron-job serialization does not serialize browser reads |
| Manager Check status | `action_revolut_reconcile()` also calls the same poll method and separately audits committed evidence | Same observation locks; no separate read admission |

Source anchors: [browser state machine](../../addons/pos_revolut/static/src/app/revolut_payment_state.js)
(`request`, `waitForResult`, `operationCall`),
[server payment method](../../addons/pos_revolut/models/pos_payment_method.py)
(`_read_revolut_operation_owned`, `_apply_revolut_observation_owned`,
`revolut_poll_payment`, `revolut_cancel_payment`),
[operation model](../../addons/pos_revolut/models/revolut_payment_operation.py)
(`_apply_payment_observation`, `_cron_reconcile_payments`),
[cron XML](../../addons/pos_revolut/data/revolut_reconciliation_cron.xml), and
[manager reconciliation](../../addons/pos_revolut/models/revolut_reconciliation.py).

The poll first reads owned references, then applies `legacy_final` using the
order lock and `SELECT ... FOR UPDATE`. The owned transaction **commits before
HTTP**. Pending attempts do not change state or reserve a provider read during
that pre-check. Each successful or failed read later takes another observation
lock to apply its evidence. Local serialization retries replay evidence
application only, not HTTP. Verified or retry-safe final snapshots short-circuit
subsequent polls. Missing references do not dispatch replacement payments.

The native authorized-cart path additionally reconciles captured payments using
authenticated tip reports. Its existing 60-second report-creation claim is
separate from ordinary intent/payment reads. Concurrent reads of an existing
report/file/order remain possible. The probe counts those requests separately
in its sequential success control; it does not extrapolate a report fan-out
measurement from the pending-intent experiment.

HTTP uses `timeout=10` for each call and rejects redirects. This is a Requests
connection/read timeout, **not an absolute ten-second RPC deadline**. One poll
can make intent, payment, report and order requests sequentially. The browser
deadline also does not cancel an already executing server RPC. See
[Requests timeout semantics](https://requests.readthedocs.io/en/latest/user/quickstart/#timeouts).

## Read-only hosting and provider evidence

Hosting source inspected at clean sibling HEAD
`1f2aa0287f919a95a2268705f639ba616c8c8788`; historical provisioning baseline is
`d5c8aba5af2a3673d0b9e4a1cc686fa01cbeab1c`. No Terraform state, secrets,
private host files or deployed dashboard rules were read.

| Pinned source | What it establishes | What remains unknown |
| --- | --- | --- |
| `odoo-hosting/infrastructure/hetzner/bootstrap.sh:70–86` (baseline :69–85) | Provisioning emits loopback HTTP 8069/evented 8072, `proxy_mode=True`, `workers=2`, `max_cron_threads=1` | Effective process/worker count, command-line overrides and current config |
| `odoo-hosting/infrastructure/hetzner/main.tf:27–50` | Optional Access policy; tunnel routes HTTP and websocket; database-manager path blocked | Effective external Access/WAF/rate/concurrency rules |
| `odoo-hosting/customers/revolut.staging.json:8,14–17` | Target profile disables Access, pins Odoo/cloudflared, selects server type | Actual deployed policy and resource capacity |
| `odoo-hosting/operations/configure.py:20–38,52–60` | Addon/monitoring/service configuration | No new request concurrency controls here |
| Integration [development environment](../development-environment.md) and [deployment runbook](../staging-deployment.md) | Historical provisioning facts; offline upgrade uses `--workers=0` | Offline upgrade settings are not live HTTP limits |

Searches of tracked provisioning/operations/scripts/docs found no explicit
`limit_time_*`, `limit_memory_*`, `MemoryMax`, `TasksMax`, `CPUQuota`, `limit_req`
or `limit_conn` configuration. Absence in this searched source does not prove
absence in deployment, defaults or Cloudflare. The local test runner uses
`--workers=0` and Python threads with real database transactions, not two
deployed Odoo HTTP worker processes. Three blocked fixture threads cannot prove
how a deployed proxy would admit or queue those three calls.

An additional offline read of `odoo.tools.config` in the pinned test image
(`docker run --rm --network none --entrypoint python3 ...`) returned these
package defaults, before loading any deployed configuration or CLI arguments:

| Option | Package default |
| --- | ---: |
| `workers` | 0 |
| `max_cron_threads` | 2 |
| `db_maxconn` | 64 |
| `limit_request` | 65536 |
| `limit_time_cpu` | 60 seconds |
| `limit_time_real` | 120 seconds |
| `limit_time_real_cron` | -1 sentinel |
| `limit_memory_soft` | 2147483648 bytes |
| `limit_memory_hard` | 2684354560 bytes |

These are verified package defaults, not deployed values or a capacity test.
In particular, the provisioning template intentionally overrides workers and
cron threads. The administrator must compare the installed package, configuration,
command line and service limits; no omitted option is interpreted as unlimited.

Official [terminal push-payments guidance](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
recommends approximately one-second polling and verifying the underlying final
payment. The guide also contains differing checklist cadence examples; it does
not establish an account quota. The
[versioned Merchant reference](https://developer.revolut.com/docs/api/merchant/2026-08-17)
retrieved on 2026-10-02 had no text matches for `rate limit` or `429`; this is
not proof of unlimited service. The published
[Manage Accounts usage limit](https://developer.revolut.com/docs/guides/manage-accounts/api-usage-and-testing/usage-and-limits)
is Business API guidance and cannot be applied to Merchant intent/payment/report
endpoints without provider confirmation.

## Bounded experiment and controls

The existing transaction fixture starts one authorized native-cart operation
with mocked terminal discovery/order/intent creation. Counters reset after
start. Three callers share one real POS cashier identity and operation. A fourth
observer thread joins a barrier only when all three provider-read callbacks
have entered; it checks `active == 3`, then releases each complete call in a fixed sequence. Barriers/events have
ten-second bounds; the existing worker join has a twenty-second bound. No
unbounded loops, traffic generation or exhaustion measurement is included.

The overlap case substitutes cancellation's public pre-check and the actual
single-item cron selector for two callers. First-wave pending snapshots are
fixed before the cancellation outcome; the uniquely claimed cancellation then
receives a cancelled second read. Response release is sequenced through caller-completion events to isolate
provider-read admission from state-application conflict retries; the existing
race controls independently test stale evidence under concurrent application.

Retained machine-readable results:
[ticket-29-poll-observations.jsonl](ticket-29-poll-observations.jsonl).
Counts below exclude setup and final snapshot-only discovery.

| Scenario | Maximum simultaneous reads | Total provider GETs | All provider calls | Final result |
| --- | ---: | ---: | ---: | --- |
| Foreground + Check status + shared-cashier browser | 3 | 3 | 3 | Pending; no safe retry |
| Foreground + cancellation pre-check + cron | 3 | 4 | 5 | Cancelled; retry safe; exactly one cancel POST |
| Three HTTP 503 failures | 3 | 3 | 3 | Unresolved; no safe retry |
| Three malformed intent responses | 3 | 3 | 3 | Unresolved; no safe retry |
| Three request timeouts | 3 | 3 | 3 | Unresolved; no safe retry |
| Late capture after concurrent timeouts and explicit local timeout | Sequential recovery | 4 | 5 | Verified only with payment + zero-tip report + order evidence |

All three request threads are blocked inside the first-wave HTTP mock at the
barrier; all exit after release, with zero active reads remaining and no worker
errors in the final run. Success reconciliation makes one non-financial report
creation POST. Afterwards three parallel verified callers make **zero** extra
provider requests. Rechecking the cancelled final operation also makes zero
extra requests. No scenario sends a new charge during status reconciliation.

Existing controls in the same test file verify that a delayed cron pending
snapshot cannot downgrade foreground success, a stale cancellation response
cannot downgrade success, cancellation cannot release an attempt while payment
verification is pending, and interrupted payment evidence recovers its original
reference without another charge. These pass with the new experiments.

## Narrow remediation proposal, requiring separate approved implementation

Duplicate pending observations warrant a per-operation coalescing proposal even
while outage severity is unresolved. This investigation implements none of it.

1. After normal authorization, atomically claim a persisted operation-specific
   poll token and fixed expiry using the existing short owned transaction.
   Foreground, Check status, cron, manager checks and cancellation pre-checks
   must use the same claim. Release database locks before HTTP. Retain distinct
   financial-dispatch and report-creation claims.
2. Enforce a one-second minimum between actual observation starts. Losing
   callers return a fresh persisted snapshot with observation timestamp,
   freshness/in-progress information and bounded next-check advice; they do not
   wait in another worker, extend the lease, move cron due time, or make HTTP.
   Non-final cached pending/unresolved evidence cannot authorize checkout,
   retry, line removal or cancellation dispatch. Already persisted verified
   evidence remains valid; cached intent completion alone never means success.
3. Cancellation requires a newly completed eligible observation under the
   shared claim, followed by the existing unique cancellation dispatch claim.
   A busy/stale pre-check returns without a cancellation POST and offers a
   later check. It must not use a cached pending result as fresh eligibility.
   Post-cancellation reconciliation must remain eligible, without replaying
   the POST, even if normal cadence has not elapsed.
4. Initial proposed lease: 25 seconds for the bounded intent/payment observation
   phase, with an actual absolute 20-second phase deadline; settle exact margins
   using local mocked latency checks. Requests' current timeout alone cannot
   enforce that deadline. Report reconciliation needs its own bounded phase
   and existing claim; do not put a multi-request report wait under an
   undersized intent lease. Expiry releases a crashed holder without manual
   reset. Every apply/release must fence on the original token, so an expired
   holder cannot overwrite newer evidence or release a successor's claim.
   Physical HTTP overlap can still occur after expiry if an old call has not
   stopped; do not promise strict single-flight across crashed/stalled workers
   without cancellation/deadline enforcement.
5. No sliding expiry and no caller affinity: foreground and cron can both win
   an expired/free claim; winner applies evidence for everyone. Losers cannot
   renew it. This avoids pinning reconciliation to a disappearing browser and
   makes other operations independent, but does not promise strict FIFO or
   reserved cron priority. A crashed holder may add up to the lease interval
   before another active caller retries; cron-only recovery also includes its
   existing minute schedule. Error backoff must not silently turn today's
   explicit foreground checks into minutes of cached waiting. Do not change
   that policy without a separately accepted reconciliation-delay budget.
6. Required tests: same-cashier/multiple-user foreground sharing; cron and
   cancellation overlap; exact HTTP counts; one-second boundary; crash before
   and after HTTP; expiry and token fencing; slow/stalled responses; no lease
   extension by losers; legitimate callers observing a winner's result; final
   success/failure cache; malformed/timeout recovery and late capture; original
   references and reservations; authenticated tip evidence and report expiry.
   Reuse the current stale-cron/cancellation controls. Measure added observation
   delay using a controlled clock. Cached losers still use brief HTTP/DB work,
   so this is not a global authenticated-request admission or account-wide
   quota guarantee across distinct operations.

## Concrete human evidence request and where to find it

Ask the deployment administrator for a redacted, read-only record of:

- `/etc/odoo/odoo.conf`: `workers`, `max_cron_threads`, `db_maxconn`,
  `limit_request`, `limit_time_cpu`, `limit_time_real`, `limit_time_real_cron`,
  `limit_memory_soft`, `limit_memory_hard`; record omitted options as defaults
  requiring resolution against the installed package. Do not export passwords.
- `odoo.service` and `/etc/systemd/system/odoo.service.d/` overrides: effective
  `ExecStart`/CLI settings, process count and service CPU/memory/task limits.
  Review locally and supply only relevant redacted values. `limit_request`
  recycles a worker after a count of requests; it is not a per-cashier rate cap.
- Cloudflare dashboard for the target hostname: [Security rules](https://developers.cloudflare.com/waf/rate-limiting-rules/create-zone-dashboard/)
  for zone rules, and account WAF rate-limiting rulesets if applicable; supply
  effective rules matching authenticated POS RPCs, their thresholds and actions; Access
  policy alone is not a concurrency limit. Include any additional nginx/proxy
  `limit_req`/`limit_conn` rules if that proxy actually exists. Do not assume one
  exists from generic Odoo examples.

Ask [Revolut API Support](https://developer.revolut.com/docs/guides/merchant/introduction#support)
(`api-requests@revolut.com`) for the Merchant account/environment limits on
intent GETs, payment GETs, report creation/status/files and order reads: request
window, burst/concurrency scope, shared-account scope and 429/retry guidance.
No support message was sent by this investigation. The owner can ask through
their existing Merchant support channel without supplying API keys here.

Compare those facts with the proposed two-cashier/four-tab target and a chosen
maximum acceptable observation delay. Reclassify the exact claim only then;
do not close it as safe based on successful mocked financial controls.

## Verification

Commands run from the assigned worktree with project isolation:

```bash
env ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket29 ./scripts/test-addon \
  --test-tags '/pos_revolut:TestRevolutRetryConcurrency'
env ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket29 ./scripts/test-addon \
  --verify-install-upgrade
node --test --test-isolation=none \
  addons/pos_revolut/static/tests/revolut_payment_state.test.mjs
./scripts/test-deployment-guard
python3 -m py_compile addons/pos_revolut/tests/test_revolut_retry_concurrency.py
git diff --check
```

Focused final run: **30 tests passed**, zero failures/errors, including six new
characterization tests. All seven observation records above were retained from
that run. First exploratory run failed because the test-only report router
cannot handle an unhashable malformed state; its aborted operation also polluted
the later cron selector. The malformed fixture now uses an unknown scalar state
and missing order identity. A fresh 29-test run and final 30-test run passed.
The first full run passed 362 install tests, but its upgrade phase hit one
`SerializationFailure` while the three mocked responses were released together.
The direct threaded fixture does not exercise Odoo's outer HTTP transaction
retry adapter. This is retained evidence of local transaction contention, not
proof of an HTTP-worker outage. The final probe keeps three HTTP reads in flight
at its barrier and releases complete calls sequentially, preserving its admission
measurement while isolating response-application races. No runtime payment fix
was made; the independent existing stale-success race tests remain unchanged.

Node lifecycle: **75 tests passed**, none failed/cancelled/skipped. Python
compilation and whitespace checks pass. No typechecker configuration exists in
this repository; syntax compilation is not a typecheck or behavioral proof.
Deployment guard passed against disposable payment/refund records. An initial
sandbox Docker-access denial was resolved through the authorized local runner;
it was not a deployment mutation or test failure. Final full-suite rerun:
**362 install tests and 362 upgrade tests passed**, zero failures/errors.
**Nine Restaurant bridge tests passed**, zero failures/errors. The runner
exited successfully and removed its disposable database/volume.

## Standards

Independent Standards review: **0 findings**. The existing transaction-fixture
style, mocked provider boundary, secret-free evidence, ticket move/index rules
and preserved `ready-for-agents/.gitkeep` conform to repository guidance. The
follow-up event review confirmed matching thread/event keys, completion signals
in `finally`, release cleanup and bounded waits. No runtime change was required.

## Spec

Independent Spec review: **0 findings**. The probe covers three simultaneous
provider reads and foreground/cron/cancellation overlap while sequenced response
completion isolates admission from state-application conflict handling. Existing
late/stale-success races remain independent controls. The evidence retains the
transaction failure, distinguishes local threads from deployed workers, and
records the unknown capacity/quota facts, recommendation and separate proposal.

Review summary: Standards 0 findings; Spec 0 findings. Both reviews require
recording the final acceptance results before submission.


Final logs: focused `/tmp/ticket29-narrow-final.log`, full
`/tmp/ticket29-full-final.log`, expanded lifecycle
`/tmp/ticket29-node-expanded.log`, and deployment guard
`/tmp/ticket29-deployment.log`. Local temporary log paths are supporting session
records; the durable findings, observed counts, source identity, commands and
limitations are retained in this artifact and the linked JSONL file.

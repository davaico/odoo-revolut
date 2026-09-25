# 15 — Deepen payment outcome application

**Work branch:** `codex/15-deepen-payment-outcome-application`

**State:** closed

**Triage:** ready-for-agent

## What to build

Preserve the same durable payment result across cashier polling, cancellation, timeout, scheduled reconciliation, and manager association while concentrating finality, retry safety, reference updates, reconciliation scheduling, and release rules behind the payment-operation seam. Cashiers and managers must observe the authoritative outcome despite competing or delayed observations.

## Approved design decisions

The owner confirmed these decisions during the architecture discussion:

- **Q1 — Callers report observations; the module determines consequences.**
  The payment outcome module checks the kind and content of each observation
  against the current stored operation before deciding state, retry safety,
  reference updates, order and terminal release, and reconciliation scheduling.
  Identity, relationship, amount, and currency checks needed to establish an
  outcome belong behind this seam. Callers supply evidence rather than raw
  persistence instructions or flags that prescribe those consequences.
  An intent-only cancellation cannot release an attempt when a concurrent
  request has already recorded a payment awaiting verification.
- **Q2 — Keep provider requests outside the outcome module.** Existing callers
  fetch evidence through the existing external adapter. The outcome module
  then locks and rereads the operation before applying the observation; it
  does not hold an outcome-update lock while waiting for provider requests.
  Mismatched or insufficient evidence cannot establish a successful outcome
  or authorize a retry. Preserve the existing provider request sequencing and
  claim-before-dispatch workflow.
- **Q3 — Preserve distinct transaction lifetimes.** Polling, cancellation,
  timeout, and scheduled reconciliation retain their dedicated committed
  outcome transactions. Manager reference association and its audit record
  share the manager request transaction: both succeed or both roll back.
  Manager status reconciliation is different: it calls independently committed
  polling before recording its audit, so a later audit failure must not erase
  an already verified payment. Share outcome rules across these transaction
  adapters without introducing unconditional commits into the module.
- **Q4 — Include dispatch-result application.** Creation and cancellation
  acknowledgements use the module's outcome rules as well as polling results.
  Record valid dispatch acknowledgements and references while checking whether
  their accompanying state is still applicable to the locked operation. A
  delayed acknowledgement must not regress a newer authoritative outcome or
  overwrite an established reference. Preserve dispatch claims, provider
  calls, and request sequencing outside the module; recording dispatch success
  alone does not establish payment success or safe retry.

## Acceptance criteria

- [x] Concentrate payment outcome application so callers no longer select persistence flags or repeat lock-and-finality protocols to enforce the same transition rules. A file move alone does not satisfy this criterion.
- [x] Only a verified successful underlying payment can authorize sale completion. Intent completion alone remains insufficient, and intent-only failure cannot release an attempt whose payment still awaits verification.
- [x] Authoritative final outcomes survive stale polling, timeout, cancellation, and scheduled reconciliation. Order and terminal protection are released only when the existing evidence rules permit it.
- [x] Preserve durable claim-before-dispatch behavior and current reconciliation timing. Ambiguous creation or cancellation remains recoverable without replaying a financial mutation; safe replacement attempts retain their history.
- [x] Manager association retains authorization, reference ownership checks, audit evidence, and final-state protection while using the same owner for applicable outcome rules. Association alone cannot establish a verified payment.
- [x] Failure recording a manager association audit rolls back the reference association. A manager reconciliation audit failure leaves an independently committed verified payment intact. Exercise both guarantees through the real manager workflows and database transactions.
- [x] Dispatch acknowledgements pass through the shared outcome rules. A controlled delayed-acknowledgement test preserves valid dispatch evidence and references without regressing a newer authoritative state, releasing protection incorrectly, or authorizing a duplicate dispatch.
- [x] Keep payment and refund outcome rules distinct. Retain the current external adapter seam, production transaction semantics, browser-facing results, and stored operation/reference compatibility.
- [x] Preserve real-path database concurrency tests for stale foreground/background polling, stale cancellation, and cancellation during payment verification, alongside manager-association tests. Any changed dispatch tests must exercise the production claim path rather than reproduce its SQL or algorithm.
- [x] Demonstrate a stale observation arriving after verified success and an uncertain payment resolved through manager association and reconciliation, with correct POS recovery and references. Record focused test results and the transition knowledge removed from callers; all provider calls remain mocked.

## Blocked by

- None. Existing recovery, manager reconciliation, and target-version acceptance foundations are complete; this ticket does not depend on the other architecture tickets.
- No external blocker for mocked development. Coordinate overlapping payment-model and test edits at integration without making them artificial blockers.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown and requested triage.
Ready for an agent: the workflow, preservation constraints, and verification
criteria are specified; there are no unmet ticket or external blockers for
mocked development. Claim the work and update its existing work branch from the latest
reviewed main before implementation. Use a separate worktree for concurrent work.

## Verification evidence

Implemented on `codex/15-deepen-payment-outcome-application` against reviewed
`main` in a separate worktree. Provider requests remain in the existing payment
adapter and were mocked in all automated tests; no real terminal or Merchant API
request was made.

The payment operation now locks and rereads the attempt before applying an
observation. It owns finality, retry safety, reference validation and updates,
release of order and terminal protection, local outcome and reconciliation
scheduling. The cashier and cron callers no longer write provider-selected
state dictionaries or pass release and intent-only persistence flags. Dispatch
acknowledgements use the same owner and preserve valid claim evidence without
regressing a manager-verified result. Manager association supplies provider
order and intent evidence to that owner; its reference update and audit remain
atomic in one request transaction. Manager status polling commits independently,
and its audit uses a fresh transaction after polling so a stale request snapshot
cannot cause a serialization failure or erase a verified payment.

Focused Odoo results on `19.0.20260908`:

- `TestRevolutRetryConcurrency`: 22 passed in the focused run. Includes
  stale scheduled and foreground polling, stale cancellation, cancellation
  during payment verification, provisional polls and local timeouts before
  claims and during order and intent dispatch, a stale missing-reference poll
  after manager association, dispatch crash recovery, delayed acknowledgement
  after manager association and reconciliation, order-only manager association
  during order acknowledgement, before intent claim, and during intent dispatch,
  and both audit failure transaction guarantees.
- `TestRevolutReconciliation`: 7 passed.
- `TestRevolutPayment`: 31 passed.
- Full `scripts/test-addon`: 143 passed, 0 failed and 0 errors, including
  browser tours. `python3 -m compileall` and `git diff --check` passed.

The in-flight poll and timeout tests first failed on the review-discovered
races. Missing-reference observations now leave the locked operation intact; a
valid acknowledgement after local timeout resumes its original dispatch claim
and restores reconciliation scheduling without overriding manager-linked or
verified results. The two before-claim tests showed that local timeout must
leave an in-progress server request claimable. A separate stale-poll test
first showed that manager reconciliation was delayed; it now preserves the
manager-scheduled time.

The delayed acknowledgement test recovers the same operation through the POS
lookup, preserves its order, intent, and payment references and released locks,
and observes only the original order POST. No replacement intent is dispatched.
Order-only manager association now checks ownership only for references it was
given, and preserves a matching creation sequence already claimed by the server.
No credential or deployment configuration changed.

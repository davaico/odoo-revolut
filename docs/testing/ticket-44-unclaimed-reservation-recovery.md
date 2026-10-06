# Ticket 44 — Recover unclaimed payment reservations

## Scope and proof

Branch `codex/44-recover-unclaimed-payment-reservations` starts from fetched
main `b672985386f907e19e898f9df3befdf978462303`. Addon version is
`19.0.1.17.1`. Final tested runtime is
`15575ffb1abc7df9d6e018ba6e7913cfb0865e79`. The owner agreed the existing cashier start/status/cancel APIs,
mocked Merchant HTTP boundary, native order/session workflows and independent
worker races as the test seams.

Explicit cashier cancellation examines the current attempt under the existing
session/order/native-order/payment locks and the fenced observation lease.
It records a safe `cancelled` outcome with `provider_state=not_dispatched` only
in either of these states:

- `created`, with no dispatch claim and no provider references;
- `order_created`, with exactly one completed, succeeded `create_order` claim
  whose reference matches the saved order, and no intent or payment reference.

No provider lookup supplies this proof. A claimed order or intent remains
uncertain even if the stopped worker had not yet sent its HTTP request. The
change sends no new provider call, replays no financial step and preserves
original identity, authorization, amount/currency, order reference and claims.
The final safe outcome prevents a delayed worker from acquiring its next claim.
The cashier can retry the retained line (with a unique successor attempt), or
remove it and select another tender. Polls, timeouts, manager and scheduled
reconciliation do not release reservations automatically.

## Regression evidence

Both independent-transaction regressions first failed on the baseline: a
permanently stopped discovery worker and a worker stopped before the intent
claim each returned `unresolved` after ordinary cashier cancellation. The
before-order regression subsequently passed with the first implementation.
Manager guidance also failed before correction, incorrectly calling a safely
cancelled reservation blocked because references were absent.

The first full run caught seven existing shared-register cancellation regressions:
an ineligible local `cancel_unclaimed` check marked an unresolved observation as
failed, preventing valid provider cancellation after a timeout. The correction
treats the local eligibility check as no provider evidence. Fresh intent reads,
observation fencing/budgets and cancellation dispatch claims still decide
provider cancellation. All 73 affected recovery/register/reconciliation tests
then passed before the full install/upgrade rerun.

The concurrency tests use independently committed Odoo cursors, real financial
locks and mocked HTTP. They stop the original worker permanently at discovery
and before the intent claim, then cancel and explicitly retry. Delayed-worker
races pause before each claim while two granted cashiers, status polling,
manager reconciliation and cron recover the original attempt. Cached concurrent
observations follow the existing bounded check-again contract. A separate
simultaneous two-cashier cancellation proves one original safe outcome and no
provider request, followed by exactly one replacement order/intent pair. Negative controls
stop immediately after order/intent claims and after their responses, preserve
reservations, reject a competing terminal payment and block session closure.
Cancellation during in-flight dispatch retains the reservation and valid later
acknowledgement; existing timeout and late-success controls remain covered.

Two native browser tests exercise original draft persistence/authorization,
lost start response, read-only status, native payment-line deletion, safe
cancellation, replacement Revolut payment and automatic settlement of the same
unchanged cart. They verify the successful underlying payment and zero-tip
report through mocked HTTP, the matching native payment references, terminal
availability through successful replacement and native `close_session_from_ui`.
HttpCase shares a rollback cursor across requests, so a specific test-only
worker-stop exception is caught at its RPC boundary to lose the start response
without erasing the committed fixture. The independent-cursor regressions prove
actual reservation durability with an uncaught terminated start request.

No real Merchant API, terminal, staging environment or live payment is used.
The pinned test image blocks unmocked Merchant HTTP and runs on an internal
Docker network. Operator instructions are in `docs/installation.md`.

## Verification

There is no configured static typechecker; Python compilation and JavaScript
syntax checks are reported as syntax checks, not payment verification.

| Check | Result | Command / log |
| --- | --- | --- |
| Full addon upgrade | 573 tests; 0 failures/errors; runner exit 0 | Same install/upgrade command; `/tmp/ticket44-full-final.log` |
| Full fresh installation | 573 tests; 0 failures/errors | `ODOO_REVOLUT_TEST_PROJECT=ticket44-full-final ./scripts/test-addon --verify-install-upgrade`; `/tmp/ticket44-full-final.log` |
| Final affected recovery, register access and reconciliation | 73 tests; 0 failures/errors | `ODOO_REVOLUT_TEST_PROJECT=ticket44-cancel-fix ./scripts/test-addon --test-tags '/pos_revolut:TestSharedPosSessionAccess,/pos_revolut:TestRevolutRetryConcurrency,/pos_revolut:TestRevolutReconciliation'`; `/tmp/ticket44-cancel-fix.log` |
| Simultaneous cashier cancellation | 1 test; 0 failures/errors | `ODOO_REVOLUT_TEST_PROJECT=ticket44-two-cashiers ./scripts/test-addon --test-tags '/pos_revolut:TestRevolutRetryConcurrency.test_two_cashiers_cancel_the_same_stopped_reservation_once'`; `/tmp/ticket44-two-cashiers.log` |
| Native recovery and closure | 2 tests; 0 failures/errors | `ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket44-native ./scripts/test-addon --test-tags '/pos_revolut:TestRevolutVerifiedCheckout.test_cashier_recovers_worker_stopped_before_order_claim,/pos_revolut:TestRevolutVerifiedCheckout.test_cashier_recovers_worker_stopped_before_intent_claim'`; `/tmp/ticket44-native-final.log` |
| Complete POS lifecycle suite | 99 passed; 0 failures/skips | `node --test --test-isolation=none addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`; `/tmp/ticket44-node.log` |
| Complete host tooling suite | 57 run; 54 passed, 3 PDF dependency skips | `python3 -m unittest discover -s tests -v`; `/tmp/ticket44-host.log` |
| Syntax and whitespace | Passed | Python `compileall` for models and changed tests, `node --check` for new tour, `git diff --check` |

The original red logs are `/tmp/ticket44-red.log` and
`/tmp/ticket44-intent-red.log`; the manager guidance regression is in
`/tmp/ticket44-recovery-focused.log`. Logs are ephemeral; commands, outcomes
and pinned revision are retained here. Fresh installation completed at
13:48:20 UTC and upgrade at 14:00:16 UTC on 2026-10-06. Both ran the
complete addon suite, including native browser workflows, and the runner
exited successfully. The superseded initial full run stopped after exposing
the seven cancellation regressions; its log is `/tmp/ticket44-full.log`.

## Standards

Independent review of `git diff b672985...55a1c62`, plus supplemental test
ranges `55a1c62...10704a1`, `10704a1...0d20681` and
`0d20681...15575ff`: no documented-standard
violations or actionable baseline smells. The change follows existing financial
locking, observation, addon and local-tracker conventions.

## Spec

Independent review of the same ranges: no actionable missing, incorrect or
out-of-scope behavior. The final supplementary review includes simultaneous
cashier cancellation. Both native regressions subsequently passed actual
checkout and native session closure; no live-terminal acceptance is claimed.

Review totals: Standards **0 findings**; Spec **0 findings**.


## Self-evaluation

Overall **4.6/5** across the five delivery axes; no critical issues.

| Axis | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 5 | Independent committed-worker regressions, native workflows and both 573-test runtime runs support the claims; the HttpCase cursor limitation is explicit. |
| Completeness | 5 | Every acceptance criterion has coverage, including both preclaim windows, claimed uncertainty, delayed workers, simultaneous cashiers, checkout and session closure. |
| Clarity | 4 | Proof and limits are separated, but long test selectors make the verification table dense; named test groups would improve scanning. |
| Actionability | 5 | Committed branch, reproduction commands, closed ticket and operator guidance give a concrete review and recovery path. |
| Conciseness | 4 | The report repeats some coverage from the ticket; the short handoff should link this evidence instead of repeating it. |

Top improvements: shorten future verification tables with named command blocks;
keep the final user handoff concise and link this report. Self-check: the owner
can compare every claimed outcome with a command and pinned revision; the
scores reflect completed automated scope, with no live-device claim.

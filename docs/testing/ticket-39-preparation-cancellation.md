# Ticket 39 — Cancellation before payment dispatch

## Revision and test seams

Implementation and reviewed runtime: `d3a1db2913c80cd811061ef63da069dbef88160f`
on `codex/39-cancel-payment-before-dispatch`, based on freshly fetched main
`f9249c589194d7a27b411ef82dc51aa8dcd13966`.

The ticket establishes the existing public `RevolutPaymentState` lifecycle
and native POS checkout/cancellation as the test seams. Controlled tests use
the production state machine with deferred adapter preparation and a fake
clock. Browser tours hold real draft-save, cart-authorization and canonical
refresh transport results, then invoke native line deletion while preparation
is pending. The native deletion path calls `screenCancel`; after preparation
settles, it releases busy ownership and removes the undispatched line.

Saving or authorizing a draft is not financial dispatch. The new guard checks
the pending cancellation before clearing predecessor evidence or starting a
payment. Fresh cancellation retains truthful undispatched history. Cancelling
preparation of a retry leaves the safely failed prior snapshot and operation
reference intact and avoids cancelling that historical operation. Check-only
requests and reload remain read-only; a subsequent explicit request can start
one payment. Possible dispatch still requires the existing authoritative
cancellation and reconciliation paths.

## Red/green evidence

- The new deferred-preparation screen regression failed against the baseline:
  its call sequence contained `revolut_start_payment` after cancellation,
  instead of only `revolut_find_payment`. With the guard, the request returns
  false and cancellation returns true at fake time zero; neither financial
  start, provider cancellation nor timeout marking occurs.
- The retry regression initially failed after adding only the preparation
  guard: cancellation still called `revolut_cancel_payment` on the old declined
  operation. The scoped final-snapshot shortcut removes that historical
  mutation. Both regressions now pass.
- Nine added lifecycle cases cover successful cancelled preparation, prior
  attempt preservation, fresh/retry preparation rejection, review-required
  results, timeout/late success, repeated cancellation, reload, check-only and
  coalesced explicit resume. A resumed retry submits its prior operation ID.

## Verification

All Revolut HTTP calls are mocked. Each new native test rejects any Merchant
HTTP call and asserts that no payment operation was created. The disposable
Docker runtime also blocks unmocked Merchant HTTP and uses an internal network.
The tours retain the saved authorized order and settle the same order with
Cash after cancellation. No terminal, staging deployment or live financial
operation is involved.

| Check | Result | Command / log |
| --- | --- | --- |
| Focused native cancellation | 5 passed; 0 failures/errors | `ODOO_REVOLUT_TEST_PROJECT=ticket39-focused ./scripts/test-addon --test-tags '/pos_revolut:TestRevolutVerifiedCheckout.test_cancel_payment_while_draft_persistence_is_pending,/pos_revolut:TestRevolutVerifiedCheckout.test_cancel_payment_while_authorization_is_pending,/pos_revolut:TestRevolutVerifiedCheckout.test_cancel_payment_while_canonical_refresh_is_pending,/pos_revolut:TestRevolutVerifiedCheckout.test_pending_cancellation_preserves_unpaid_order,/pos_revolut:TestRevolutVerifiedCheckout.test_cancel_racing_with_capture_preserves_successful_payment'`; `/tmp/ticket39-focused.log` |
| Full lifecycle suite | 88 passed; 0 failures/skips | `node --test --test-isolation=none addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`; `/tmp/ticket39-node-final.log` |
| Host tooling suite | 43 run; 40 passed; 3 PDF runtime skips | `python3 -m unittest discover -s tests -v`; `/tmp/ticket39-host-final.log` |
| Full addon fresh install | 493 tests; 0 failures/errors | `ODOO_REVOLUT_TEST_PROJECT=ticket39-full ./scripts/test-addon --verify-install-upgrade`; `/tmp/ticket39-full.log` |
| Full addon upgrade | 493 tests; 0 failures/errors; runner exit 0 | Same combined command and log |
| Syntax and whitespace | Passed | `node --check` on changed production JS and tour, `python3 -m py_compile addons/pos_revolut/tests/test_ui.py`, `git diff --check` |

The focused run used the working tree that became the runtime commit above;
the full lifecycle, host and addon runs use that committed runtime. There is
no configured static typechecker. Syntax checks are not represented as
typechecking or proof of payment behavior. Logs in `/tmp` are ephemeral;
commands, counts and revision are recorded here for durable evidence.

## Standards

Independent review of
`git diff f9249c589194d7a27b411ef82dc51aa8dcd13966...d3a1db2913c80cd811061ef63da069dbef88160f`:
no documented-standard violations or actionable baseline smells found.

The change follows the existing lifecycle state conventions and keeps
cancellation within the addon. It preserves the prior final attempt and its
references, consistent with `AGENTS.md` and the terminal contract. Credentials
and provider verification remain server responsibilities. Native tests use
mocked provider HTTP; tracker metadata preserves the agent-ready folder and
its `.gitkeep`. No new abstraction or unrelated production change was added.

## Spec

Independent review at the same revision: no actionable Spec findings.

The change checks cancellation after preparation and before dispatch, settles
both promises without a dependency cycle, retains a safely failed predecessor,
and leaves post-dispatch reconciliation intact. Tests cover all three native
preparation awaits, failure/timeout, late results, repeated cancellation,
check-only/reload and explicit resume. No scope creep was identified. Existing
capture-race, uncertain-start and refund guards remain covered. The reviewer
independently reran all 88 lifecycle tests with zero failures or skips.

Review totals: Standards **0 findings**; Spec **0 findings**.

## Agent self-evaluation

Overall **4.6/5**; no critical issues or outstanding implementation work.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 5 | Exact committed runtime passed 88 lifecycle cases and 493 Odoo tests on both install and upgrade; independent reviewers found no issues. Host PDF dependency skips are explicitly reported. |
| Completeness | 5 | All ticket acceptance criteria are covered, including native preparation stages, retry evidence, delayed failures/results, safe removal/resume and post-dispatch controls. |
| Clarity | 4 | Test names describe observable behavior; the long focused selector in the verification table is cumbersome to scan. If more selectors are added, move that command into a separate code block. |
| Actionability | 5 | Fix and regression tests are committed on the requested branch from current main; reproducible commands, reviewed revision and results are recorded here. |
| Conciseness | 4 | The report retains detailed red/green and review evidence. Keep the completion message short and link this report rather than repeating it. |

Improvements, by impact: separate the focused command if its selector list grows;
keep the user-facing completion concise. Neither requires a production change.
Self-check: the committed fix and this report let the user inspect and reproduce
the result. No live-terminal acceptance is claimed; that remains ticket 12.

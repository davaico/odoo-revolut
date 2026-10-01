# Ticket 22 — Terminal-busy recovery

## Candidate and contract

Branch: `codex/22-recover-terminal-busy-rejection`, based on main
`2a7a7ebbeb1b5a5d49df142dd45abd7e3ccbfa23`, including fetched `origin/main`
`96d7c48`. Addon version: `19.0.1.7.6`.

Reviewed implementation: `78b42b852790ddd27cb0a49b954e5983567f30cd`.

Only the server's direct `revolut_start_payment` result can establish a
terminal-busy rejection before operation creation or dispatch. The result
contains `start_rejected=terminal_busy`, `dispatched=false`, and the requesting
order UUID, payment-line UUID and predecessor operation ID. Existing-attempt,
refund, prior-attempt, cart and completed-order checks run first. The temporary
order lock is rolled back; no operation or provider request is created.

The lifecycle accepts that proof only for the matching direct payment start,
with no operation or provider references. Transport exceptions, busy wording,
missing responses, empty lookup results, mismatched identities and late replies
after a timeout cannot clear an uncertain start. A rejected replacement retains
its safe predecessor. Discovered operations override the rejection history.

The same unpaid line can be edited or removed. **Resume** explicitly starts
after release; **Check status** never starts or replaces a financial request.
Both actions use native Odoo payment-response handling and coalesce repeated
clicks. Reload keeps order/payment-line identity and definite rejection history.
Installation guidance records the upgrade and POS reload requirement. No
configuration or credential changes are required.

## Test seams and evidence

The ticket pre-agrees the public server RPC, controlled lifecycle and actual
Odoo POS adapter seams. Provider HTTP is mocked; the disposable Docker runtime
blocks unmocked Merchant requests and has no external network route.

- Lifecycle TDD reproduced unsafe/unresolved busy handling, a status check
  starting again, a lost replacement predecessor, and suppressed repeated busy
  feedback before each correction. The single lifecycle file now passes
  **43 tests**, including unknown-start, discovered-operation, timeout,
  processing and refund controls.
- Server TDD reproduced the old busy exception through a real public start RPC.
  The final focused payment/retry/refund/concurrency run passed **96 tests**,
  zero failures and errors. Independent committed transactions cover three
  concurrent busy requests with no operation/provider call, cancellation,
  read-only discovery after release and two explicit starts coalescing to one
  operation and one order/intent pair. Replacement predecessor/replay tests
  also pass.
- The two new real Odoo browser tours passed, zero failures and errors. They
  reserve the terminal with an independent order through the public start RPC,
  then use native POS actions for rejection, repeated clicks, status checks,
  cancellation, reload, explicit resume and verified checkout, or safe removal
  and cash checkout. Order/payment-line identities and provider mutation counts
  are checked. The recovery tour fails on unchanged main at the original busy
  exception/incorrect dialog. These mocked tours use one Chrome instance and
  independent order IDs; they do not replace the live two-browser retest.
- Node syntax checks, XML parsing, Python compilation and `git diff --check`
  passed. This repository has no configured typechecker, linter or coverage
  measurement; syntax checks are not claimed as type checking.

- Full `ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket22-full
  ./scripts/test-addon --verify-install-upgrade` on reviewed implementation
  `78b42b8` exited **0**: **212 tests on fresh install**, **212 on upgrade** and
  **8 Restaurant tests**, each with zero failures and errors. The browser tours
  ran in the pinned Odoo/Chrome runtime with websocket support verified.
- `python3 -m unittest discover -s tests -v` passed **29 deployment tests**.
  `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` passed
  all **43 lifecycle tests** again after the candidate commit.
- A final fetch confirmed `origin/main` remains
  `96d7c48f2c7e88d3224a7f75ef802b8d5f161023`; both it and local `main`
  `2a7a7eb` are ancestors of the reviewed candidate.

Verification: runtime installation/build **PASS**; tests **PASS**; syntax/XML
checks **PASS**; independent diff review **PASS**; no secrets or cardholder data
added to the public response or frontend. Types, lint and coverage measurement
are **not configured**, so no type, lint or coverage result is claimed. Local
implementation is verified; live release acceptance remains gated below.

Local runner logs: `/tmp/ticket22-full.log`,
`/tmp/ticket22-lifecycle-final.log`, `/tmp/ticket22-deployment-tests.log`,
`/tmp/ticket22-server-final.log`, `/tmp/ticket22-ui-green.log` and
`/tmp/ticket22-ui-baseline-red.log`. These disposable logs are supplementary;
the committed regressions and results above are the retained evidence.

## Standards

Independent standards review of `78b42b8` found **no hard violations**. The
changed code preserves the documented server trust boundary, conservative
handling of uncertain starts, idempotent dispatch and verified-payment checkout.
New server and browser regressions mock provider HTTP. The physical two-browser
acceptance criterion remains explicitly open, consistent with the tracker and
live-validation gate.

No actionable baseline smells were found. Lifecycle state stays in the existing
recovery module; adapter and template changes follow established Odoo patch
patterns. Standards: **0 findings**.

## Spec

Independent spec review of `78b42b8` found **no substantive implementation
mismatch, scope creep or incorrect behavior**. The direct rejection proof
checks order, payment-line and predecessor identity; status checks cannot start
payments; uncertain starts, discovered operations and refunds retain their
guards. The reviewer independently reran all **43 lifecycle tests** successfully.

One acceptance requirement remains intentionally partial: **“Record a reviewed
candidate and repeat the independent-browser no-card scenario.”** The physical
two-browser retest has not occurred. The ticket and evidence distinguish the
one-browser POS tours and independent server transactions from live acceptance.
Deployment/retest remains gated by reconciliation of unresolved operations and
pending refund reservations. This does not block the authorized local
implementation.

Review totals: Standards **0 findings**; Spec **0 implementation findings,
1 outstanding live acceptance requirement**.

## Live validation gate

Ticket 22 is open under **ready-for-human** until the reviewed candidate is
retested with two independent browsers and the physical terminal. Deployment/retest
requires reconciliation of unresolved financial operations; pending refund
reservations must not be bypassed. This implementation performs no live
deployment, terminal interaction, payment or refund.

After reconciliation, repeat ticket 12 L07 without presenting a card: leave
the first order waiting, start the second order and observe clear busy/no-start
feedback, repeat status checks and Resume while busy, cancel the first request,
then check status and explicitly Resume the second. Confirm unchanged order and
payment-line UUIDs, no second operation before release, and exactly one intended
new operation after Resume. Cancel and reconcile that operation before leaving
the terminal. Record revision, timestamps, final provider evidence and mutation
counts before closing this ticket and the corresponding ticket 12 gate.

## Agent self-evaluation

Overall **4.4/5**, with no critical issues.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 5 | Reviewed implementation passed the full install/upgrade/Restaurant suites, independent review and explicit no-duplicate-mutation assertions; live acceptance is not claimed. |
| Completeness | 4 | All five local criteria are exercised. The requested physical two-browser no-card retest remains outstanding behind reconciliation; perform the recorded checklist before closure. |
| Clarity | 4 | The server proof and native screen option must be followed across the existing model/lifecycle/adapter seam; the contract and recovery actions are recorded together above. |
| Actionability | 5 | A committed candidate, upgrade version, test commands, review reports and gated live checklist are available on the assigned branch. |
| Conciseness | 4 | The ticket, installation guide and evidence repeat the release gate for their different readers; the completion response can link here and stay brief. |

Improvements, by impact: execute and record the physical retest after financial
reconciliation; keep subsequent status reports concise and link this evidence.
Self-check: the user can review and run the local correction directly, with
the remaining live requirement clearly assigned to human validation.

## Final live result — 2026-10-01

The reviewed `97fcc2b` release was deployed to staging, and the operator
completed a controlled two-browser, no-card terminal-busy recovery. The
second browser received the definitive busy/no-dispatch message while the
first request held the terminal; no second-order operation existed. After
provider cancellation of the first request, one second-browser Check status
created no operation. One explicit Resume on the same visible line created
exactly one new £0.01 GBP operation and displayed it on the terminal. The
operator presented no card and cancelled that operation. The ledger recorded
both requests provider-cancelled and retry-safe, with no remaining order or
terminal lock. The earlier ambiguous run included several operator Resume
clicks and is superseded by this controlled count. The busy response's line
UUID was not captured independently before dispatch; same-line UI use and
the mocked browser identity regression support the identity criterion.
[Ticket 22](../tickets/closed/22-recover-terminal-busy-rejection.md) is closed;
ticket 23's real-card automatic-status retests remain outstanding.

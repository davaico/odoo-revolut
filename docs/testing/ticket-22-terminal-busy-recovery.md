# Ticket 22 — Terminal-busy recovery

## Candidate and contract

Branch: `codex/22-recover-terminal-busy-rejection`, based on main
`2a7a7ebbeb1b5a5d49df142dd45abd7e3ccbfa23`, including fetched `origin/main`
`96d7c48`. Addon version: `19.0.1.7.6`.

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

Full install/upgrade and independent code review results will be recorded
after the candidate is committed.

## Live validation gate

Ticket 22 remains claimed and open until the reviewed candidate is retested
with two independent browsers and the physical terminal. Deployment/retest
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

# Ticket 20 — Undispatched POS recovery

## Reviewed revision and seams

Implementation: `b6834e1b781d71d641e6f4ece2155decb9a02e64` on
`codex/20-recover-undispatched-pos-lines`, based on reviewed main
`5081551d77a5db6d62b84965f5c115bd8f3cb236`.

The ticket specifies two test seams: the public `RevolutPaymentState`
lifecycle and the actual Odoo POS adapter/browser flow. Controlled lifecycle
tests use the existing adapter and clock boundaries. Browser tours fail the
first read-only POS lookup at the RPC transport boundary, then exercise normal
POS retry, allocation, deletion, tender selection, reload and settlement.
All provider requests are mocked; the disposable runtime blocks unmocked
Merchant HTTP calls and has no external network route.

`revolutUndispatched` records known lifecycle history before a first financial
start. An empty server lookup cannot establish this history. A start attempt,
discovered operation, surviving reference or older saved waiting/retry status
without that history retains the existing guards. `revolutDiscovering` guards
read-only preparation while it is active and clears on restoration. Both
payment and refund responses require a verified server snapshot before Odoo
may treat them as successful. Refund authorization and original-tender balance
rules remain enforced on the server.

## Verification

- Controlled lifecycle: `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`
  passed **27 tests** on the reviewed revision. The 15 additions cover rejected
  and timed-out discovery independently for payments/refunds, late replies,
  same-line coalescing, cancellation during lookup and refund balance
  preparation, discovered-operation recovery, lost start responses, legacy
  reload state and surviving references. The 12 existing controls remain green.
- Focused Odoo browser/refund run: **9 passed, 0 failures, 0 errors**. It covered
  the four new payment/refund recovery and alternative-tender tours, ticket
  16's lost refund response/original-sale read failure, late payment success
  after reload, ordinary cash/bank checkout, pending cancellation and the
  missing-active-refund-allocation settlement rejection. The full suite below
  repeats these regressions on the exact reviewed commit.
- Full `./scripts/test-addon --verify-install-upgrade` on the exact reviewed
  commit passed **189 tests on fresh install** and **189 tests on upgrade**,
  each with 0 failures and 0 errors. Its subsequent Restaurant process received
  a termination signal while preparing assets, before a Restaurant result was
  available; this partial command is not claimed as a complete successful run.
- The remaining Restaurant check was completed with
  `./scripts/test-addon --verify-install-upgrade --test-tags '/pos_revolut:TestRevolutRetailPosStarts'`
  in a separate disposable project on the same commit: **1 retail startup test
  after install**, **1 after upgrade**, and **8 Restaurant tests** passed, all
  with 0 failures and 0 errors. Browser transport was verified and no tour was
  skipped for missing websocket support.
- `node --check` passed on the changed lifecycle, adapter and new browser tour;
  Python compilation of `test_ui.py` and `git diff --check` passed. This vanilla
  JavaScript/Odoo repository has no configured typechecker.

The alternative refund tour starts with an original split cash/Revolut sale.
It removes the undispatched Revolut return line and refunds an eligible cash
portion without a refund dispatch. A return of an entirely Revolut-paid sale
cannot be substituted with cash; that server rule was preserved.

## Standards

Hard documented violations: **none found**. The change respects `AGENTS.md`'s
explicit payment-state and mocked-provider requirements, the shared contract's
unresolved-money protection and the existing lifecycle/Odoo-adapter split.

One minor judgement call: possible duplicated code where discovery assigns
`revolutStarted = true` and `revolutUndispatched = false` immediately before
`remember()`, which also sets those fields. Retained deliberately: discovery
records exposure before `remember()` may reject a stale snapshot. No new
abstraction is needed for these two defensive assignments.

The independent standards reviewer found no unsafe dispatch in the new
cancellation path and reran all 27 lifecycle tests successfully. Cancellation
shares the outstanding discovery promise and checks its stop flag after
lookup, source discovery and allocation selection; timed-out replies cannot
resume an abandoned continuation.

## Spec

The independent ticket-spec reviewer found **no substantive spec findings**
and no scope creep on `b6834e1`. Discovery recovery, stable identity,
coalescing, timeout/late-response handling, cancellation races and verified-only
success are implemented. Refund preparation dismissal and ticket 16's
uncertain-refund protections remain intact. Browser tours cover recovery after
reload and safe alternative tender with mocked provider calls.

Review totals: Standards **0 hard violations, 1 minor duplication observation**;
Spec **0 findings**. The reviewed implementation and its verification evidence
satisfy ticket 20; final ticket/index changes are documentation only.

## Agent self-evaluation

Overall **4.6/5** across the five quality axes; no critical issues.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 5 | Exact reviewed code passed 27 lifecycle tests and the full install/upgrade suites; the interrupted process is distinguished from the successful Restaurant rerun. |
| Completeness | 5 | Both discovery failures recover, uncertain starts remain guarded, actual browser settlement and eligible alternative tender are exercised, guidance and ticket state are updated. |
| Clarity | 4 | The review identified two duplicated exposure assignments around `remember()`'s stale-result filter. If that transition is extended, consider centralizing it while preserving the guard. |
| Actionability | 5 | The implementation is committed on the assigned branch, based on latest main, with commands, reviewed revision, recovery guidance and verification results recorded. |
| Conciseness | 4 | Key test counts appear in both this detailed report and the closed ticket. The user-facing completion message should link the report and keep only the essential result. |

Improvements, by impact: reconsider the duplicated exposure transition during
future lifecycle changes; keep the completion response short and link this
report for detail. Neither requires more changes to this correction.

Self-check: the user should be able to verify the correction directly from the
committed code and this evidence; no live terminal acceptance is claimed.

# 63 — Perform controlled Odoo 18 terminal acceptance

**Work branch:** `feat/v18_rev`.

**State:** open

**Triage:** ready-for-human

**Base and integration target:** latest sanitized `feat/v18_rev`, not `main`.
Read root AGENTS.md and ADR 0002 before implementation or review.

## Purpose and evidence boundary

Establish physical-terminal release evidence for Odoo Community 18, including
payment verification, native completion, recovery, tips, Restaurant and refunds.
Keep Odoo 18 acceptance separate from the maintained Odoo 19 campaign.

This is the sanitized continuation of the existing private acceptance ticket.
The checkpoint below summarizes recorded operator observations and bounded
verification as of 2026-10-23. Exact completion/reload regressions use synthetic
records; protected completed records are reviewed without financial revalidation.
Exact candidate artifacts, approvals, transaction mappings and originals remain
with the acceptance custodian. Obtain that private context before operating the
existing environment. Do not import old private Git ancestry or publish its
evidence. This ticket does not itself authorize deployment or financial actions.

## Acceptance criteria

- [x] Record the reviewed candidate, runtime/addon version, environment,
  terminal/location, operator and preserved records in restricted evidence.
- [x] Record explicit deployment and financial authorization for the bounded
  campaign, with separate Odoo 18 scope and limits.
- [ ] Complete all environment, installation, retained-data and safe recovery
  prerequisites for the candidate ultimately proposed for release.
- [ ] Complete required single and split collection checks, native automatic
  completion, references and customer documents without duplicate collection.
- [ ] Complete required unsuccessful-payment, interruption and recovery
  checks, including uncertain outcomes and safe retry.
- [ ] Verify zero/nonzero terminal-selected tips, report finality, native
  projection, split balance and documents on the physical terminal.
- [ ] Verify dine-in and timed Takeout checkout and approved recovery.
- [ ] Verify full/partial and tip-related refunds, provider finality, native
  return completion and accounting reconciliation.
- [ ] Verify receipts, PDFs/printing, session closure, posting and reopening.
- [x] Preserve completed observations, failures and remaining obligations in
  restricted evidence; provide concrete fix/retest handoffs for failed gates.
- [ ] Close only after required physical checks and obligation dispositions
  are complete. Keep parent scope ticket 50 independently open in its private
  tracker; do not infer Odoo 19 acceptance from this campaign.

Aggregate criteria stay open when only a bounded subcase has passed.

## Completed bounded checks — 2026-10-23

- [x] Identify the deployed replacement candidate and reopen the same local
  environment while preserving records and the frozen addon.
- [x] Recover the original verified zero-tip card payment and automatically
  complete its original native sale once without recollecting.
- [x] Complete a Cash control sale with the terminal idle and no increase in
  Revolut operations or financial dispatches.
- [x] Complete a Cash/card sale with the correct split, zero tip/change,
  saved references and a native receipt.
- [x] Observe POS cancellation, terminal cancellation and unavailable-terminal
  rejection. Isolated cancelled-order reloads do not start another request.
- [x] Verify authenticated zero-tip evidence, historical POS receipts/browser
  PDFs and the session X report against the bounded sales.
- [x] Verify both original-linked card refunds reached provider Completed /
  local verified. This establishes financial finality only.
- [x] Observe manager reference navigation and a reconciliation audit row on
  an already verified payment. Uncertain-payment reconciliation remains open.
- [x] Preserve failure reports for the unsent-tender reload defect and native
  completed-refund recovery defect in sanitized tickets 68 and 70.

- [x] Resume three high-risk synthetic checks on the frozen deployed addon:
  lost paid-sync response, lost refund response/reload, and simultaneous
  same-return refund dispatch. All passed with mocked/blocked Merchant HTTP;
  protected records untouched. See [the result](../../testing/ticket-63-final-no-money-recovery.md).

## Next checks and blockers

- [x] Resolve [70 — completed-refund native recovery](../closed/70-recover-verified-refund-with-unprojected-native-tender.md)
  with mocked regressions and a reviewed correction. The owner-authorized local
  deployment is complete on addon `18.0.1.0.2`, immutable source `2aeef4b`;
  existing financial/native evidence is preserved.
- [x] Complete the same two original native returns on the reviewed correction,
  preserving their refund/tender identities and receipts without card redispatch.
  Both are paid; the mixed return's approved manual Cash portion was completed
  as fictional test bookkeeping. Do not repeat this completed step.
- [x] Retest the bounded unsent-tender removal/repeated-reload sequence on the
  reviewed [ticket 68 fix](../closed/68-investigate-duplicate-revolut-line-after-reload.md),
  preserving the original cancelled-operation history and one unsent tender.
- [x] Fix and retest [ticket 72](../closed/72-consume-completed-return-resume-route.md):
  nine native browser tests and 144 JavaScript checks passed; local 18.0.1.0.3
  deployment and no-money original-record smoke/preservation verified.
- [x] Exercise native accounting close/posting/reopen on a disposable populated
  copy only, including fictional Cash difference; original register/drafts
  remain open. This does not complete original-register closure.
- [x] Resolve or explicitly disposition the earlier candidate's full-suite
  busy-reload failure retained in private ticket 67. The later ticket-68
  candidate has a separate green full run; it does not rewrite earlier results.
- [ ] Complete outstanding decline/transport/interruption, two-card split,
  nonzero/split tips, Restaurant, partial/tip returns, browser credential-boundary,
  physical/terminal documents, colleague recovery and session checks.
- [ ] Agree fresh scope before additional card collection/refund scenarios:
  existing campaign card limits are fully used. Refunds do not replenish them.
- [ ] Reconcile native stock/accounting and manual Cash obligations, then
  record the release decision. Do not mark this gate green from mocked tests.

## Continuation

Use the [short agent handoff](../../testing/ticket-63-handoff.md). Preserve the
original financial/native identities; do not replace completed refunds, use
Force done or repair live records by bypassing verification/allocation checks.
Keep credentials on the server and mock all Merchant HTTP in automated tests.
The [Odoo 19 durable-removal follow-up](../closed/69-port-durable-tender-removal-to-odoo-19.md)
remains separate maintenance work under ADR 0002.


## Same-day additional acceptance checkpoint

See [2026-10-23 additional checks](../../testing/ticket-63-finish-20261023.md)
for the current result; earlier outstanding lists above are historical.

- [x] Original drafts disposed with explicit approval; original register
  closed, posted balanced accounting and reopened with zero cash.
- [x] Live Dine-in and scheduled Takeout completed, including missing-slot
  rejection without dispatch, UTC/local pickup persistence and receipt.
- [x] Live nonzero terminal tip and split-tip remaining balance verified;
  pending-attempt browser reload preserved identity without duplicate send.
- [x] Native document PDFs rendered and visually checked; no physical Odoo
  printer exists in the owner's setup, so that hardware check is not applicable.
- [x] Isolated process restart, 76 selected tests and authenticated cashier/
  manager recovery/credential boundary checks passed within documented scope.
- [x] Fresh financial scope recorded: two separate GBP 0.05 budgets, GBP 0.08
  total collected across them. Latest budget has GBP 0.02 unused.
- [ ] Five new refunds still unresolved; finish original native returns and
  remaining GBP 0.01 split-source refund only after verified reconciliation.
  Waiting/monitoring explicitly deferred by owner; no automation.
- [x] Disposition the historical busy-reload test through a reproduced stale
  snapshot and safe Check-status recovery. See [ticket 67 evidence](../../testing/ticket-67-busy-reload-disposition.md); the historical failure is retained.
- [x] Owner disposition: record remaining physical coverage limits (actual issuer decline, distinct-card
  split; other unobserved interruption variants remain explicit limitations).
  The owner selected recording issuer-decline/distinct-card cases as untested.
  Do not represent mocked cases
  as physical passes or require recollection of already covered scenarios.

Merchant HTTP is blocked again and the guard passed. These results do not close
the refund/native accounting or overall release gate.


## Refund continuation — 2026-10-26

- [x] Reconcile all five older refunds to provider Completed / local verified.
- [x] Resolve [73](../closed/73-restore-refund-reference-after-native-refresh.md),
  deploy local 18.0.1.0.4 / `334c8a8`, and retest both affected original returns
  through normal validation with preserved references and no financial replay.
- [x] Finalize the four Restaurant returns and close/post both fully refunded
  sessions with balanced GBP 0.03 debit/credit and zero net card totals.
- [x] Submit the remaining authorized GBP 0.01 split-leg refund exactly once.
- [ ] Reconcile that last refund (still processing), finish its existing split
  return, close/post the remaining session and record final release decision.

## Owner release disposition — 2026-10-26

- [x] Accept the last GBP 0.01 refund's processing delay and defer its existing
  return/session completion as non-blocking follow-up. This item no longer
  gates release preparation or release sign-off; other release checks and
  approval remain separate.
- [ ] After provider finality is verified, reconcile the original refund,
  finish the same native return and close/post its session with balanced
  accounting. The financial/native work remains pending, not passed.

This owner disposition supersedes the preceding requirement to finish that
item before the release decision. It does not authorize a new refund, forced
completion, live operation or monitor. Ticket 63 remains open for final release
sign-off; the pending provider delay alone is no longer its release blocker.

See [full evidence and test limitations](../../testing/ticket-63-refund-completion-20261026.md).
Earlier outstanding lists are superseded by this checkpoint. No additional
physical test is required beyond the previously recorded owner dispositions.

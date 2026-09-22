# 04 — Handle unsuccessful payments and safe retries

**Work branch:** `codex/04-unsuccessful-payments-safe-retries`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**Status:** blocked

**Category:** Blocked

## What to build

A cashier sees a distinct unsuccessful-payment outcome and can retry only when the previous attempt is conclusively safe to retry.

## Acceptance criteria

- [ ] Display distinct declined, failed, cancelled, interrupted and timed-out outcomes without marking the sale paid. Separate provider-confirmed terminal outcomes from local transport failures.
- [ ] Cancel only eligible pending intents and reconcile the result. Do not delete a payment line or report successful cancellation while cancellation is unresolved or payment may have succeeded.
- [ ] Use a 60-second foreground waiting limit with approximately one-second status polling. On expiry, display unresolved status, preserve references and block a new charge; local timeout is not proof of provider failure.
- [ ] Permit a new persisted attempt only after authoritative evidence makes retry safe. Keep prior attempts and references for audit; follow the confirmed provider rules for replacement orders/intents.
- [ ] Handle cancel-versus-success races and repeated cancellation/start requests without duplicate financial operations. Keep the payment amount locked while an attempt is active.
- [ ] Mocked model and browser tests cover decline, failure, cancellation, processing-time cancellation rejection, timeout, interruption, safe retry and cancellation races. Assert unsuccessful orders remain unpaid and unsafe retries perform no new dispatch.
- [ ] Document cashier messages, retry eligibility and the unresolved-payment workflow.

## Blocked by

- 03 — Complete one verified Revolut terminal payment

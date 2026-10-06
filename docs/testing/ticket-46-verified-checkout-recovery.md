# Ticket 46 — Recover verified checkout restoration

Base: local `main` at `a3f5e5e5fe8fcc8a7a40f96ca94d54792cfa40d9`.
Branch: `codex/46-recover-verified-checkout-refresh`.
Addon: `19.0.1.18.1`. All provider calls below are mocked in the pinned
Odoo `19.0.20260908` test environment; no live terminal or deployment is involved.

## Behavior

The final server financial snapshot remains verified independently of a
browser checkout restoration. Native payment response handling requires both
verification and successful restoration. Failed or hung restoration leaves a
locked, unpaid line with **Check status**, preserves its original identity and
references, and blocks manual and automatic checkout. The global native busy
flag is released on request completion or failure.

Check status on a verified operation retries only canonical Odoo checkout
restoration with a fresh 60-second deadline. It skips provider lookup, polling,
starting, cancellation and timeout-marking RPCs. Concurrent clicks and
cancellation share the same restoration. Late timed-out responses cannot merge
checkout data, references or receipts. A queued cancellation after completion
does not complete the checkout again. Reload cannot turn the server's saved
`done` status into browser success while canonical restoration is outstanding.

Normal settlement remains responsible for cart authority, amount and currency,
tip projection, return entitlement and tender allocations. Restoring a partial
payment does not pay the remaining balance. Receipt references are reapplied
once through the existing native receipt guard.

## Reproduction and checks

The first focused rejection tests failed on both sale and refund with the
canonical-refresh exception and an unhandled promise rejection. After the
fix, repeated failures resolve false, preserve the verified snapshot, and a
read-only retry succeeds. A further cancellation test reproduced two native
completion callbacks from a stale cancellation; the completion guard reduces
that to one.

Four real native POS tours interrupt `revolut_checkout_state` after server
verification: authorized payment and saved refund, each rejected and timed out.
They assert native busy release, visible recovery, exact evidence, blocked
manual Validate, double-click coalescing and canonical restoration before
receipt navigation. Successful settlement preserves the original native order
and payment line, exact +/-12.34 amount, currency and references. The payment
rejection tour also reloads the saved order without deleting browser storage.
Server assertions require one charge (two provider POSTs) or one refund (three
total POSTs including the original sale), and exactly one settled native order.

The initial four-tour run passed three cases and exposed the reload merge
edge case; the corrected reload tour passed separately. Logs:
`/tmp/ticket46-native.log`, `/tmp/ticket46-native-reload.log`.

| Check | Result |
| --- | --- |
| Focused payment state suite | 107 passed, no skips (`/tmp/ticket46-state.log`) |
| Python tooling suite | 57 run, 54 passed, 3 optional skips (`/tmp/ticket46-tooling.log`) |
| Native recovery tours | Four passed across the initial and reload reruns |
| Full Odoo install and upgrade suite | Running (`/tmp/ticket46-full.log`) |
| Syntax and patch checks | Python compileall, changed JavaScript `node --check`, `git diff --check` passed |
| Standards and Spec review | Pending |

This repository has no static typechecker configuration for these Odoo
JavaScript modules. Syntax checks and real native browser execution cover the
changed integration boundary.

## Delivery

Upgrade `pos_revolut` and reload POS assets through the usual deployment
procedure. There is no schema, configuration or credential change. The
[operator guidance](../installation.md) describes the same-line Check status
action. Physical-terminal and release acceptance remain with ticket 12.

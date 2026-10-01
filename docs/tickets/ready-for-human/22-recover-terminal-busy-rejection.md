# 22 — Recover a POS line after a terminal-busy rejection

**Work branch:** `codex/22-recover-terminal-busy-rejection`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-22`

**State:** open

**Triage:** ready-for-human

**Priority:** P2

## Observed problem

Live ticket-12 testing on 2026-09-29 at deployed revision `76209bb` used two
independent Chrome instances under one account and configured terminal. Order
`1008` waited for a card. Incognito order `2001` attempted a one-penny payment.
At 13:37:35 UTC the server rejected it before operation creation/dispatch:
**An existing Revolut payment blocks this order or terminal.**

The server guard passed. The Incognito POS instead displayed communication
interruption and warned that payment may have succeeded. After cancellation
of the first request and release of the terminal lock, Check status left
`2001` unresolved and checkout disabled. At 13:42:07 UTC there was no operation
or saved order for `2001` and no second financial dispatch. This is a recovery
defect, not evidence of duplicate charging.

The frontend marks the line started before the start RPC and maps its
rejection to interrupted handling. Subsequent discovery returning no operation
cannot clear that history. Ticket 20 addressed initial read-only discovery
failure; this report covers a definitive rejection of the financial start.

## Acceptance criteria

- [x] Return and recognize an authoritative pre-dispatch terminal-busy result with clear busy feedback. An arbitrary RPC/transport exception, message-string match or empty lookup alone cannot establish safe non-dispatch.
- [x] A definitively rejected line can be safely removed or explicitly resumed after terminal release, retaining order/payment-line identity. Check status must not automatically dispatch a new financial request.
- [x] Preserve independent-browser serialization: repeated busy requests create no operation/financial dispatch; an explicit start after release creates exactly one intended operation.
- [x] Keep guards for lost/uncertain start responses, discovered operations, processing payments and refunds. Missing lookup results cannot authorize retry or checkout when financial dispatch may have occurred.
- [x] Cover rejection, status lookup, recovery, repeated clicks and restored state through lifecycle and actual Odoo POS-adapter regressions with mocked financial calls; keep unknown-start and refund controls green.
- [ ] Record a reviewed candidate and repeat the independent-browser no-card scenario: clear feedback, safe recovery after cancellation, stable identity and no duplicate mutation.

## Blocked by

None for local diagnosis/mocked implementation; lifecycle and server terminal
lock are present on reviewed main.

## Live validation gates

- The five previously pending test refunds are now shown Refunded in the
  operator's Revolut screenshot, with Odoo completion operator-reported on
  2026-10-01. Before deployment/retest, verify all five local operations and
  any other financial blockers read-only; retain the deployment guard.

## Release gate

Blocks closure of ticket 12. Work may start locally; the reviewed fix and
live recovery retest remain outstanding.

## Verification evidence

Local implementation and mocked verification are recorded in
[terminal-busy recovery evidence](../../testing/ticket-22-terminal-busy-recovery.md).
Reviewed implementation: `78b42b852790ddd27cb0a49b954e5983567f30cd`, addon
`19.0.1.7.6`. Standards review found no findings; spec review found no
implementation mismatch and retained the outstanding live acceptance criterion.
Full install and upgrade each passed 212 tests; 8 Restaurant, 43 lifecycle and
29 deployment tests also passed. All financial requests were mocked or blocked.
The first five criteria are exercised by lifecycle, actual Odoo adapter and
independently committed server-RPC tests. The physical two-browser retest in the
last criterion remains gated; these local checks do not claim live acceptance.

See [operator observations](../../testing/ticket-12-operator-observations.md),
section **L07 independent-browser terminal contention**. First-request
cancellation and empty provider payment list were verified at 13:40:33 UTC.
Subsequent stuck Check status and zero second operation were verified at
13:42:07 UTC.

A temporary Node characterization of the deployed module reproduces lookup
returning no operation, start rejecting with the observed busy message, then
another empty lookup. Both requests return false; interrupted persists and
retry/deletion remain unavailable. The recoverability assertion fails in
milliseconds. Native status transitions and server exception are fixtures,
not a captured RPC trace; the chronology records the command and limits.
All local calls are mocked. Convert the characterization into a regression
at the trusted rejection seam when implementing the fix.

## Comments

2026-09-29: Recorded during controlled acceptance and published with its
evidence checkpoint. Incognito can be closed after preserving this failure;
the original POS and pending returns remain open.

2026-09-29: Triaged as ready-for-agent after the owner moved this ticket to
`ready-for-agents/`. The problem, safe recovery contract and mocked regression
criteria are defined; local work can start without a live terminal. Live
validation remains gated as recorded above.

2026-09-29: Implemented and independently reviewed on the assigned branch,
current with fetched remote and local main. Local mocked criteria pass; moved
to `ready-for-human` for financial reconciliation and the physical two-browser
no-card retest. The ticket remains open and continues to block ticket 12's
release acceptance. No live deployment or financial operation was performed.

2026-09-30: The operator reports receiving five separate £0.01 Revolut credits,
but Odoo still lists all five refund operations as Pending. A fresh Odoo status
check of refund `5` still reported provider `processing`; refund `1` showed the
same stored provider state. Cardholder receipt does not establish each Merchant
refund's final API outcome or clear the staging deployment gate. The reviewed
terminal-busy fix remains undeployed and its independent-browser no-card retest
remains unchecked until the refund operations are reconciled safely. See
[ticket 12's refund checkpoint](12-live-terminal-release-evidence.md).

2026-10-01: The operator reports Odoo Completed, and the supplied Revolut
Merchant screenshot shows the five matching £0.01 refund orders as Refunded.
This supersedes the pending-refund observation above. The reviewed fix is
still undeployed; perform the read-only financial/deployment preflight, then
repeat the independent-browser no-card busy/recovery scenario on the deployed
candidate. This refund evidence does not check the remaining live criterion.

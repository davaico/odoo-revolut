# 05 — Recover payments after interruption or late success

**Work branch:** `codex/05-recover-interrupted-payments`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** open

**Triage:** ready-for-agent

## What to build

Cashiers recover the same payment after reload or interruption, while Odoo continues reconciliation without an open browser and records late success safely.

## Acceptance criteria

- [ ] Restore attempts using stable order/payment-line UUIDs after browser reload, reconnection or server restart; do not create a replacement operation merely because local browser state was lost.
- [ ] Add scheduled reconciliation in bounded batches, with backoff for provider/network errors. Foreground and background reconciliation share locking and monotonic outcome rules so stale responses cannot regress a verified result.
- [ ] Continue checking uncertain/transitional payments when the POS is closed. Never replay an ambiguous order/intent creation; lost external IDs remain unresolved until authoritative association is possible.
- [ ] Record late success immediately. When the unchanged original order is reopened and fully paid, restore the successful line and use normal finalization. Do not finalize edited/transferred financial content or background-create a replacement sale.
- [ ] Prevent removal, alternative tender or another terminal from bypassing an unresolved financial operation on the same order. Keep terminal/order blocking scoped and release it only when evidence makes that safe.
- [ ] Tests exercise browser reload, closed browser, server restart, crash at each dispatch/result boundary, foreground/background races and late success after order edits. Assert exactly one financial dispatch and correct recovered references.
- [ ] Document recovery timing, pending-operation visibility and when manager reconciliation is required.

## Blocked by

- 04 — Handle unsuccessful payments and safe retries

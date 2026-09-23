# 05 — Recover payments after interruption or late success

**Work branch:** `codex/05-recover-interrupted-payments`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent (at closure)

## What to build

Cashiers recover the same payment after reload or interruption, while Odoo continues reconciliation without an open browser and records late success safely.

## Acceptance criteria

- [x] Restore attempts using stable order/payment-line UUIDs after browser reload, reconnection or server restart; do not create a replacement operation merely because local browser state was lost.
- [x] Add scheduled reconciliation in bounded batches, with backoff for provider/network errors. Foreground and background reconciliation share locking and monotonic outcome rules so stale responses cannot regress a verified result.
- [x] Continue checking uncertain/transitional payments when the POS is closed. Never replay an ambiguous order/intent creation; lost external IDs remain unresolved until authoritative association is possible.
- [x] Record late success immediately. When the unchanged original order is reopened and fully paid, restore the successful line and use normal finalization. Do not finalize edited/transferred financial content or background-create a replacement sale.
- [x] Prevent removal, alternative tender or another terminal from bypassing an unresolved financial operation on the same order. Keep terminal/order blocking scoped and release it only when evidence makes that safe.
- [x] Tests exercise browser reload, closed browser, server restart, crash at each dispatch/result boundary, foreground/background races and late success after order edits. Assert exactly one financial dispatch and correct recovered references.
- [x] Document recovery timing, pending-operation visibility and when manager reconciliation is required.

## Blocked by

- 04 — Handle unsuccessful payments and safe retries

## Verification evidence

Implemented on 2026-09-23 from reviewed `main` baseline `a42e508`, after
confirming ticket 04 was closed. The project owner approved the POS RPC,
settlement, browser tour and scheduled-action test boundaries, and that review
baseline. All Merchant API requests in automated checks were mocked.

The scheduled action checks at most 50 due operations per run and backs off
provider/network errors. A browser reload, closed-browser reconciliation and a
fresh Odoo process recover the original operation and references without a new
order or intent dispatch. Committed-transaction tests simulate crashes before
and after creation dispatches, after payment verification, and after cancellation;
they also exercise a foreground/background race. An ambiguous creation with a
missing external ID remains blocked for authoritative association.

Late success restores the verified POS line and uses normal settlement only for
the unchanged original financial contents. Edited orders and pre-upgrade
attempts without a saved cart snapshot require manager reconciliation. The
scheduled job never creates a replacement sale. Recovery timing, visibility,
and support instructions are in `docs/installation.md`.

The Standards review found no hard implementation violation. The Spec review
identified the legacy settlement gap and incomplete restart/crash coverage;
these were fixed with a failing-then-passing settlement regression, committed
transaction crash tests, and a separate two-process Odoo test.

Final verification commands:

```bash
./scripts/test-addon --verify-install-upgrade
./scripts/test-restart-recovery
python3 -m unittest discover -s tests -v
python3 -m compileall -q addons
node --check addons/pos_revolut/static/src/app/payment_revolut.js
node --check addons/pos_revolut/static/tests/tours/pos_revolut_acceptance.js
bash -n scripts/test-restart-recovery
git diff --check
```

The complete Odoo run reported **70 addon tests on clean install**, **70 on
module upgrade**, and **1 Restaurant POS startup browser test**, all with zero
failures or errors. The restart test reported `RESTART_SEED_OK` and
`RESTART_RECOVERY_OK` from separate Odoo processes. Fourteen deployment tooling
tests and the static syntax checks passed. No static typechecker or linter is
configured; Python compilation is not reported as type checking. No production
deployment or credential rotation was performed. Upgrade the module before
using the new flow; existing credentials remain server-side.

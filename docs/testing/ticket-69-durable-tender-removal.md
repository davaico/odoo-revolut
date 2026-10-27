# Ticket 69 — Durable tender removal on Odoo 19

Base: maintained Odoo 19 `main`, `e783d6f`. Runtime candidate: `8269e90fb6e26f2ca394ca09bb8e2535cd839cad`. Work branch:
`codex/69-v19-durable-tender-removal`. Addon version: `19.0.1.18.21`.
The Odoo 18 correction `44da485` was adapted as a scoped change; its history
was not merged. All records and provider responses below are disposable,
synthetic fixtures. The protected manual-acceptance environment was untouched.

## Native failing reproduction

The regression starts a terminal payment, cancels it, removes the cancelled
tender, creates an unsent Choose amount allocation, edits its amount to zero
and back, then refreshes the actual Odoo 19 browser. A second minimized case
omits amount editing. Both failed on unchanged runtime `e783d6f`: one pending
allocation before refresh became two model members and two rendered rows.
The extra UUID and saved native ID matched the original cancelled tender;
the pending allocation kept its distinct UUID and temporary local ID.

The native deletion command is in memory, outside IndexedDB serialization.
The server still retains the cancelled tender until native deletion is synced,
so startup merges it back. Explicit sync is the control. No new provider
collection was created. The retained failing output is the ignored synthetic
`build/ticket69/red-reload.log` (two failures, zero errors, exit 1).
The initial test adaptation failure (`red-harness.log`) used an Odoo 18-only
probe method; it is not counted as defect reproduction.

## Correction and Odoo 19 adaptation

Saved sale-tender removal now completes durable, idempotent server retirement
before hiding the native line. Explicit removal can retire server-proven
retry-safe attempt history; ordinary recovery still exposes that history.
Unknown, pending and verified attempts remain protected, and original operation
and dispatch evidence remains intact. Ownership, company, register, currency,
UUID, saved amount, native references and history checks remain in force.
A saved zero-value unstarted tender is removable, but cannot be resumed.

Removal obtains the canonical saved amount instead of trusting an editable
local amount. Offline and lost replies retain the original local identity and
support repeated retirement or status recovery. The original cancelled
foreground request finishes before removal, without repeating its dismissed
dialog onto a removed tender. Native cart deltas still reconstruct original
cart contents when recovered history remains after the final tender is gone.
Odoo 19's existing `payment_ids` command-map acknowledgment remains unchanged.

Odoo 19 required an additional cache correction, demonstrated by the actual
second refresh. First startup preserved the local pending child in memory but
cached the parent's empty server tender list. On the second refresh the child
still existed in the model/cache, while its parent membership was missing.
Targeted cache probes distinguished this from navigation or a delayed write.
After final startup recovery, the addon now uses native
`synchronizeLocalDataInIndexedDB()` when an unsynced Revolut tender belongs to
a draft. This persists restored relationships without a server save or financial
request. Regression assertions verify cached parent/child membership as well as
both actual refreshes. Temporary diagnostic logging was removed.

## Verification

The native browser cases cover the original sequence, minimized sequence,
explicit-save control, repeated refresh, offline retirement, lost committed
replies and saved allocations edited to zero before removal. After removing
the final tender, the native quantity API changes the original cart line to two;
server reads verify its original UUID/native ID, quantity two, total 24.68 and
an empty unpaid tender list. The mocked provider assertions retain the original
cancelled operation and three dispatch claims, with exactly three original
POSTs (order, intent, cancellation), no captured payment and no new collection.

Public server-interface regressions cover idempotent safe-history retirement,
non-resumable saved zero amounts, pending/verified protection, and distinct
same-method/same-amount tenders retaining their own UUIDs. A controlled-clock
lifecycle regression fails on baseline code because retirement precedes the
cancelled foreground request; it passes with the correction and asserts that
the dismissed cancellation error does not recur.

| Check | Result |
| --- | --- |
| Native original/minimal/explicit-save cases, two refreshes and cart deltas | 3 passed, zero failures/errors; `reload-green.log` |
| Server authority, retirement and concurrency | 52 passed, zero failures/errors; `authority-green.log` |
| Remaining transport/zero/recovery/split compatibility | 10 passed, zero failures/errors; `compatibility-green.log` |
| Host JavaScript | 145 passed; `host-js.log` |
| Host Python | 65 run, 3 PDF checks skipped; `host-python.log` |
| Full Odoo 19 addon suite | 687 tests reported, zero failures/errors, exit 0; `full19.log` |
| Python compilation, changed JavaScript syntax and whitespace | Passed |
| Standards review | 0 findings on `e783d6f...8269e90` |
| Spec review | 0 findings on `e783d6f...8269e90` |

The complete fresh-install run finished on 2026-10-23 at 11:10:44 Europe/Paris
(09:10:44 UTC), with the runner exiting 0 and removing its disposable project.
Focused tests used actual addon updates on the baseline-installed database.
The default module selection omits optional `pos_hr`; its employee-list
characterization calls `skipTest` when unavailable. The warn-level full runner
reports tests/failures/errors rather than a separate skip count, so 687 is the
reported test total, not a claim that every optional case ran. Browser transport
was verified before the run; no browser skip or startup failure was reported.

No standalone static typechecker, linter or coverage pipeline is configured;
syntax checks are not typechecking or payment proof. The three host PDF tests
require the supported Odoo image and are distinct from addon-suite results.

The disposable Compose project uses pinned Odoo package `19.0.20260908`,
Chrome `153.0.8010.52`. Focused runs used image
`sha256:af9ca186cfdc8e9eb70b998ea25c77b131ae1232f06148e98ceadbca4aa17b0b`;
the normal runner rebuilt its cached Dockerfile as
`sha256:42594cb2d56aaa3790302a3dd0677fd561084e581899669d8da407df6d3bb6b1`, the existing Merchant HTTP guard and an internal-only
network. Expected HTTP is mocked; accidental Merchant requests fail. Reproduce
with `scripts/test-addon --test-tags '<class or method tags>'`, or run the full
selection using `scripts/test-addon`, with a unique
`ODOO_REVOLUT_TEST_PROJECT`. Host commands:

```sh
node --test --test-isolation=none addons/pos_revolut/static/tests/*.test.mjs
python3 -m unittest discover -s tests -v
```

No schema migration, new configuration or credential rotation is needed.
Deployment and physical-terminal acceptance remain separate work.

The immutable full-run addon archive is `build/ticket69/full-source.tar`, SHA256
`d63448d9a8d86e8005d2f0eda5fa3d19cb07c978d81777b3c8d8234b932574f6`.
The full run uses `--addons-dir build/ticket69/full-source/addons` and project
`ticket69-full`. Its first launch exhausted Docker's predefined network address
pool before any tests started; removing only the ticket's completed focused
project freed capacity. No unrelated containers or networks were removed.

## Standards

Independent read-only review of `e783d6f...8269e90` found no documented-standard
breaches or actionable Fowler baseline smells. Integration code and regression
tests stay inside the addon. Removal reuses existing server ownership checks,
native mutation locks, retry-safe operation checks and retirement records;
payment history and pending/verified protection remain intact. The frontend
uses native Odoo conventions, and cart/cache changes address the same refresh
failure. Tests mock Merchant HTTP and exercise the actual native boundary.
Standards: **0 findings; no worst issue**.

## Spec

Independent read-only review found no actionable mismatch with the approved
brief: durable idempotent retirement, canonical saved amounts, protected unsafe
and verified tenders, preserved operation history, cancelled foreground completion,
repeated refresh and cart deltas are covered. The additional IndexedDB persistence
addresses the specified repeated-refresh behavior; Odoo 19's payment-command map
remains unchanged. No unrequested scope expansion was found. Full-suite validation
was pending at review time and is recorded separately above.
Spec: **0 findings; no worst issue**.

# Ticket 68 — Draft tender reload

Base and integration target: sanitized `feat/v18_rev`. The owner selected its
existing checkout and starting revision `3f318e3280b8e29a4711c480ea1a9306968fee31`
as the review baseline. All evidence below uses disposable synthetic records
and mocked Merchant HTTP. No manual-acceptance runtime or protected history is
changed, and no live financial request is authorized by this work.

## Reproduction and cause

The original native-browser sequence starts and cancels a terminal request,
removes that safely cancelled tender, creates an unsent Choose amount
allocation, edits zero/back, then refreshes without explicitly syncing the draft.
The failing regression reports two native model members and two rendered rows.
The new pending allocation keeps its UUID and temporary client ID. The extra
row has the original cancelled tender's UUID and saved native ID.

A read-only server probe establishes that the old tender still exists before
reload. Its deletion is only in Odoo 18's in-memory command map, under
`pos.order.delete["payment_ids_<order-id>"]`. IndexedDB contains the new
allocation but does not preserve that command map. Startup loads local records
and then merges the saved server tenders, bringing the cancelled tender back.
There is no new provider collection. Explicit draft sync before refresh avoids
the duplicate. Omitting zero/back edits still reproduces it: those edits are not
load-bearing. The minimal case retains saved cancellation, local removal, a new
allocation and refresh; removing the local/server membership disagreement or
refresh eliminates the extra-row symptom.

The first red run is `build/ticket68/local-repro.log`; the minimised standard
browser run is `minimal-standard-retry.log`; `removal-probe-red.log` records the
matching UUIDs, saved identity, queued deletion and server membership. These
ignored files contain synthetic data only. Browser startup/debugger timeouts
during severe host memory pressure are infrastructure failures, not green tests.

## Correction

Saved sale-tender deletion uses the existing bounded recovery/retirement
workflow before hiding the line. Explicit removal may retire matching,
server-proven retry-safe operation history. Ordinary recovery still returns
that history; uncertain or verified operations cannot be removed through this
path. Session/register, company, currency, UUID, method, saved amount, native
references and operation-history checks remain in force. Server retirement
fences stale preparation and records a durable disposition. A repeated request
after a lost reply returns that disposition without another financial action.

The frontend acknowledges only the exact completed Odoo 18 deletion command,
leaving other pending changes intact. It waits for the original cancelled
foreground request before retirement so its delayed result cannot reopen an
acknowledged cancellation dialog. Failed retirement keeps the original line
and permits explicit recovery; local edited amounts do not redefine saved
tender identity. A saved zero-value unstarted tender can be retired without
making it eligible to start payment.

After the last Revolut tender is retired, native draft sync still sends cart
line deltas. Cart reconstruction therefore includes saved recovered-tender
history, preserving existing product lines when no native Revolut tender
remains. No migration, new configuration or credential rotation is required.
Addon version: `18.0.1.0.2`. Deployment and physical acceptance remain separate work.

## Verification

The native browser regression covers the reported cancellation and zero/back
sequence, the minimised case, explicit-sync control, two real refreshes, row and
model identities, saved membership, offline removal, lost committed replies and
explicit allocation removal. Python checks retain the original cancelled
operation and its three dispatch claims (order, intent, cancellation), with no
capture, extra operation or paid sale. Additional server cases cover idempotent
retry-safe retirement, pending history that must stay protected, and zero-value
retirement. Existing recovery and multiple-tender checks are included in the passing runs below.

| Check | Result |
| --- | --- |
| Original/minimal/repeated refresh, offline/lost removal and cart authority | 44 passed, zero failures/errors; `green-drained.log` |
| Final canonical-amount compatibility: edited zero, interrupted removal, saved-unstarted recovery, multiple cards and Cash/card split | 7 passed, zero failures/errors; `compatibility-final.log` |
| Complete immutable Odoo 18 addon suite | **771 passed, 1 skipped, zero failures/errors**, exit 0, no OOM or Chrome startup failure; `full18.log`, `full18-state.json`, `full18-evidence.json` |
| Final host Python | 70 passed, 3 PDF checks skipped; `host-python-final.log` |
| Final host JavaScript | 144 passed; `host-js-final.log` |
| Python compilation, JavaScript syntax and whitespace | Passed; no static typechecker is configured |

The full selection contains 772 tests. Its one skip is
`TestSharedPosSessionAccess.test_employee_list_does_not_restrict_backend_user_rpc`:
optional `pos_hr` is not installed for this employee-list characterization.
There were no Chrome transport/startup skips; all ticket 68 browser regressions
and the required recovery/compatibility paths ran.

The completed full run used source `44da485b8c65e2e01eb850e027b41cfdeed2992a`,
addon `18.0.1.0.2`, pinned Odoo package `18.0.20261015`, guarded browser image
`sha256:673b13e859bd6e5e4cfd28f2edc2ca6da41ab5942695d1abf373d056e9c59067`,
and an internal-only disposable network. Its last result was recorded at
08:19:31 UTC on 2026-10-23; container shutdown completed with exit 0.
The immutable addon archive SHA256 is
`5c7fe2c293dfd854a06f9656336251e2e17598dfc967d92de4556ba6a4ed27e5`.

The earlier full attempt was interrupted without a final summary and is retained
as `full18-interrupted.log`; it is not counted as a pass. The completed rerun used
a fresh disposable database and a detached container, with the same full
`/pos_revolut` test selection and Merchant guard as `scripts/test-addon`, adding
only test progress logging. The named container was inspected after exit before
cleanup. It survived chat interruptions independently of the calling shell.

Reproduce the complete test selection with `./scripts/test-addon` from the
reviewed source, using a unique `ODOO_REVOLUT_TEST_PROJECT`. For the individual
JavaScript tests on the host's Node 24, use
`node --test --test-isolation=none addons/pos_revolut/static/tests/*.test.mjs`;
the default isolated runner reported only file wrappers. Existing recovery,
cancellation and distinct-tender compatibility checks also passed in the full
run. These mocked results close the implementation investigation; physical
acceptance and deployment remain separate.

## Odoo 19 assessment

The maintained `main` addon and pinned Odoo 19 image
`odoo-revolut-test:19.0.20260908-chrome153` have the same missing durable-removal
boundary. Native `PosOrder.removePaymentline()` calls local deletion; pending
commands live in closure-local maps. `serializeForIndexedDB()` serializes raw
fields and UI state without those maps. Startup restores local records and
then rereads server orders. Native serialization explicitly accounts for
server reads relinking removed records, but does not make deletion durable
across reload.

The Odoo 19 addon likewise sends ordinary safely cancelled removal through the
native local path, returns existing operation history even for requested
removal, and omits retired history from the cart-delta reconstruction condition.
An equivalent correction needs its own native browser regression and adapted
Odoo 19 APIs. The Odoo 18 command-map key change must not be copied: Odoo 19
already uses the different `payment_ids` map layout correctly. This is a source
assessment, not an Odoo 19 rendered reproduction, test pass or backport. The adapted work is tracked in
[ticket 69](../tickets/ready-for-agents/69-port-durable-tender-removal-to-odoo-19.md).
No old private history has been merged into the sanitized branch.

## Standards

Independent read-only review of `git diff 3f318e3...44da485` found no documented
standard violations or actionable baseline smells. The final canonical-amount
read, original-order handling, bounded retirement, history guards and exact
command acknowledgment were reviewed. Full-suite results were pending.

## Spec

Independent read-only review found no remaining specification findings. Its
initial compatibility-validation finding was resolved by the recorded native
recovery, cancellation, zero-edit and multiple-tender checks. Odoo 19 source
assessment meets this ticket's deliberate-assessment requirement; an adapted
backport and its rendered verification remain separate maintenance work.
Standards: 0 findings; Spec: 0 findings; neither axis has a worst issue.

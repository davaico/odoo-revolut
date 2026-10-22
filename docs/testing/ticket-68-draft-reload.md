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
retirement. Existing recovery and multiple-tender checks remain required.

The focused original/minimal/repeated-refresh, offline/lost-response and
cart-authority run passed: **44 tests, zero failures/errors**, recorded in
`build/ticket68/green-drained.log`. The final canonical-amount compatibility run passed **7 tests, zero
failures/errors** (`compatibility-final.log`): edited-zero removal, offline and
lost retirement replies, saved-unstarted removal and lost-response recovery,
multiple-card checkout and Cash/card split checkout. The prior compatibility
selection passed the other saved-unstarted Resume/offline lookup, ordinary
cancellation and server zero-tender tests; its then-failing zero-edit removal
is corrected and passes in the final selection. The full addon suite remains
in progress.
Host Python: 73 tests, 3 PDF checks skipped. JavaScript: 144 passed with
`node --test --test-isolation=none addons/pos_revolut/static/tests/*.test.mjs`.
The host Node 24 default isolated run reported only file wrappers; the explicit
non-isolated run verifies the individual tests. No static typechecker is
configured; Python compilation, JavaScript syntax and whitespace are checked.

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
assessment, not an Odoo 19 rendered reproduction, test pass or backport. No old
private history has been merged into the sanitized branch.

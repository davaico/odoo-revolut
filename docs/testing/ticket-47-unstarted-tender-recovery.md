# Ticket 47 — Recover a saved unstarted tender

Base: `dad1f2177f7168655560c6986d85f377821eded9`.
Branch: `codex/47-recover-unstarted-tender-after-reload`.
Addon: `19.0.1.18.12`. Tests use pinned Odoo `19.0.20260908`, disposable
PostgreSQL and native Chrome; the test environment blocks real Merchant HTTP.
No staging record, deployment or live financial operation is involved.

## Recovery authority

**Check status** on an exact saved draft sale/tender can establish unstarted
authority after an empty operation lookup. The server independently checks
access, register, original open session, ownership, amount, currency, native
references and retained operation/refund history. Lookup absence and browser
flags cannot authorize recovery. An existing attempt is returned for recovery;
it is never converted into an unstarted tender.

Recovery shares the existing session/order/native mutation serialization.
It records a server-owned tender disposition and advances the recovery revision,
revoking unused cart authority or advancing an exposed split cart's admission
revision without changing its frozen prices. Delayed preparation with an old
recovery revision and delayed start with an old admission fail before dispatch.
An explicit **Resume** prepares the current cart on the same saved tender;
manager approval remains required where native Price Control requires it.

Removal classifies and deletes the exact native tender in one server transaction.
Its retired UUID cannot be recreated or admitted. Native tender deletion also
retires saved positive Revolut sale tenders, including pre-fix drafts without
an earlier recovery marker. A competing successful start retains its operation
and prevents deletion. Saved sale/tender identities with terminal status,
financial references or admitted allocations remain fixed before the first
recovery marker, including after an amount is corrected to zero. Native
deletion checks unknown status and refund evidence as well as charge history.
Surviving financial references cannot be cleared by stale native sync even when
no operation link was saved. The browser acknowledges only the exact already-applied
native deletion; other queued mutations remain intact.

Repeat clicks share in-flight recovery/removal work. Offline, denied and timed-out
actions retain guards and show feedback. Late replies cannot unlock a timed-out
line. Idle native sync invalidates browser recovery evidence so the cashier
checks current server authority again. Recovery and retirement issue no provider
requests. Retained operations and dispatch evidence cannot be deleted through
the ORM. Direct SQL changes and databases with lost financial history are outside
the classification's trusted boundary and need audited reconciliation.

## Reproduction

The first server tracer failed with the absent recovery RPC, then passed after
implementation (`/tmp/ticket47-server-red.log`, `/tmp/ticket47-server-green.log`).
The native baseline reproduced missing-Tip-Product rejection after draft save,
then failed to expose Resume after configuration restoration and a fresh browser
launch on the same saved tender (`/tmp/ticket47-native-red.log`).

The initial native implementation passed Resume and offline recovery but exposed
a redundant native deletion: cash settlement attempted to delete the server's
already-retired tender again. The corrected browser acknowledgement is exercised
by actual cash settlement, beyond the lifecycle tests.

Independent Spec review found gaps in raw legacy identity/reference preservation
and native deletion classification. Focused regressions reproduced the accepted
identity mutations, erased transaction/reference fields and waiting-cancellation
deletion. The fixes protect the original identity, retain financial proof and
share the locked no-start classification between recovery and native removal.
Tests also cover loss of the actual committed removal response: the local line
stays guarded, Check status reads its retired disposition, and an idempotent
removal retry permits cash settlement without another provider request.

Two deliberately malformed legacy fixtures initially remained in their shared
order between subcases, blocking later fixture creation. Each subcase now
explicitly rolls back its fixture after assertions; the two corrected regressions
pass (`/tmp/ticket47-fixture-green.log`). The first full attempt exposed a separate
authorization regression: retention errors preceded unlink access checks.
It was stopped and is not acceptance evidence (`/tmp/ticket47-full.log`). The
corrected guards check access first, then retain history; the existing cashier/
manager financial-internals test passes (`/tmp/ticket47-auth-green.log`).

The next full attempt exposed native refund compatibility: whole-record proof
snapshots blocked checked association of new or existing refund tenders, and
sale identity guards included legacy returns and untouched draft fixtures.
That run was stopped and is not acceptance evidence
(`/tmp/ticket47-verified-full.log`). Existing raw references now retain their
nonempty values and record existence; already-linked financial proof remains
complete. New checked projection records and added canonical links still pass
final native validation. Canonical returns and untouched tenders with no
terminal status, references or admission retain their earlier behavior. A saved
terminal status cannot be erased to bypass identity protection; its focused
regression failed before the correction (`/tmp/ticket47-status-clear-red.log`).
Both reviewers confirmed the compatibility correction.

The existing opposing-parent transfer test used waiting Revolut tenders while
expecting successful reassignment. Its payment cases now require protected
identity rejection without deadlock; separate ordinary tenders retain successful
transfer coverage. Safe historical cancellation remains supported: native
removal may retire a tender only when every retained charge attempt is
authoritatively retry-safe, matches original ownership and has no native
references or refund history. The recovery RPC still returns its existing
operation rather than calling it unstarted. Retiring that old UUID obtains a
fresh cart version before a replacement tender can start.

## Standards review

Zero documented-standard violations. One optional P3 maintenance suggestion
remains: the browser classification and retirement paths repeat some proof
checks and guard resets. Their distinct lifecycle transitions are retained in
the existing project style; the reviewer found no behavior defect. The shared
server classifier and the final fixture/ACL corrections introduce no new
standards concerns.

## Spec review

Zero remaining findings. The independent review's three initial findings about
raw identity, orphan references and native deletion classification were fixed
and re-reviewed. The reviewer also confirmed the lost-response instructions,
isolated legacy fixtures and ACL correction. No scope creep was found.

Final review totals: Standards zero hard violations and one optional suggestion;
Spec zero remaining findings. Reviews are static; the automated verification
below supplies runtime evidence.

## Ticket 12 handoff

After the reviewed upgrade and POS asset reload, keep staging order 1022/tender
79 in session 10/register 3, with Tips product 1 configured. Open the original
sale and choose **Check status**. If the server proves it unstarted, choose
**Resume** on that same tender for the remaining manager-cart-approval scenario.
Re-enable the intended Price Control policy for that acceptance check; recovery
does not approve the overridden price. Preserve the original order/tender and
the £0.06 gross live charge budget. Recovery itself needs no terminal charge.
Deployment, manager acceptance and any live payment belong to ticket 12.

Automated removal coverage uses disposable records. Do not remove or replace
the staging fixture, clear browser storage, cancel its whole order or repair it
with SQL. Existing uncertain history stays protected and requires reconciliation.

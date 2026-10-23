# Ticket 63 — sanitized continuation handoff

Checkpoint: 2026-10-23. **Open / ready-for-human.**
Base and integration target: latest sanitized **`feat/v18_rev`**.
Read root AGENTS.md, ADR 0002 and the
[updated checklist](../tickets/ready-for-human/63-v18-terminal-acceptance.md).

## What is complete

Recorded bounded acceptance includes original-payment recovery with one native
completion, Cash control and Cash/card sales, zero-tip evidence, POS/terminal
cancellation, unavailable-terminal rejection, cancelled-order reloads, POS
receipt PDFs, session X totals and manager navigation/audit checks. These are
individual observations, not a completed physical release matrix.

Both issued card refunds are now financially completed and verified. Their
original native returns remain draft. The mixed return still needs its
previously approved manual Cash portion; do not send another card refund.

## Resume in order

1. Check ongoing [ticket 70](../tickets/needs-triage/70-recover-verified-refund-with-unprojected-native-tender.md)
   work before implementing. Recovery currently raises “The verified refund
   payment link does not match its original allocation.” The matching saved
   tender exists but lacks final native projection/references. The standalone
   failure was reproduced through the actual action with provider HTTP
   forbidden and rollback; the mixed case is operator/UI-confirmed. Require
   mocked coverage of both, idempotent resumption and rejection of contradictory
   evidence. Preserve identities and financial authority checks.
2. After a reviewed correction and authorized deployment, resume the same
   standalone return, then the same mixed return with its approved Cash
   balance. Validate each once and verify receipts, references, stock and
   accounting effects with no financial redispatch or duplicate native records.
3. Physically retest [ticket 68](../tickets/closed/68-investigate-duplicate-revolut-line-after-reload.md)'s
   cancelled-tender removal / new unsent allocation / refresh sequence.
   Implementation is closed on this branch: addon `18.0.1.0.2`, fix `44da485`,
   full mocked suite 771 passed / 1 optional skip / no failures or errors.
   See its [validation record](ticket-68-draft-reload.md). This newer fix was
   not deployed in the last acceptance observation (running addon `18.0.1.0.1`).
4. Continue the checklist's remaining physical scenarios and reconcile all
   obligations before closure. Preserve the earlier candidate's full-suite
   busy-reload failure in private ticket 67; the later green run belongs to
   the newer ticket-68 candidate. Track Odoo 19 parity separately in
   [ticket 69](../tickets/needs-triage/69-port-durable-tender-removal-to-odoo-19.md).

## Operating boundaries

Exact runtime/artifact identity, access details, transaction mappings, original
screenshots/PDFs and authorizations remain in restricted local acceptance
records. Obtain them from the owner before touching the live environment;
do not guess order IDs from screenshots or substitute a moving branch tip for
the deployed artifact. Preserve other agents' checkouts and unfinished work.

Existing card collection and refund limits are fully consumed. Refunds do not
replenish collection limits. New financial scenarios need fresh scope; the
mixed return's already approved Cash portion needs no repeated approval.
Guide the operator in several clear manual steps. No unattended monitor is
scheduled. This publication authorizes no deployment, new payment/refund,
Force done, live database repair or history deletion. Automated tests use
mocked Merchant HTTP only. Keep the full physical gate and parent scope open.

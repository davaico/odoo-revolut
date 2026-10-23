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

1. The reviewed [ticket 70 correction](../tickets/closed/70-recover-verified-refund-with-unprojected-native-tender.md)
   is implemented and deployed to local acceptance on addon `18.0.1.0.2`,
   immutable source `2aeef4b`. Its full mocked suite reports 778 tests with no
   failures/errors and one optional employee-list skip. Read the
   [deployment/preservation evidence](ticket-70-existing-waiting-refund-recovery.md#authorized-local-acceptance-deployment--2026-10-23).
2. Refresh Odoo, then use **Recover return** on the existing standalone refund,
   followed by the existing mixed refund. The agent performed no recovery or
   validation during deployment. Retain the same return/tender/refund identities;
   explicitly complete only the mixed return's already approved manual Cash
   balance, then validate each return once. Verify receipts, references, stock
   and accounting effects with no financial redispatch or duplicate records.
3. Physically retest [ticket 68](../tickets/closed/68-investigate-duplicate-revolut-line-after-reload.md)'s
   cancelled-tender removal / new unsent allocation / refresh sequence.
   Implementation is closed on this branch: addon `18.0.1.0.2`, fix `44da485`,
   full mocked suite 771 passed / 1 optional skip / no failures or errors.
   See its [validation record](ticket-68-draft-reload.md). This fix is included
   in the newly deployed `18.0.1.0.2` artifact; physical reload retesting remains
   open.
4. Continue the checklist's remaining physical scenarios and reconcile all
   obligations before closure. Preserve the earlier candidate's full-suite
   busy-reload failure in private ticket 67; the later green run belongs to
   the newer ticket-68 candidate. Track Odoo 19 parity separately in
   [ticket 69](../tickets/closed/69-port-durable-tender-removal-to-odoo-19.md).

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
scheduled. The owner separately authorized the recorded local deployment,
which is now complete. No new payment/refund, Force done, live database repair or history
deletion is authorized by this handoff. Automated tests use
mocked Merchant HTTP only. Keep the full physical gate and parent scope open.

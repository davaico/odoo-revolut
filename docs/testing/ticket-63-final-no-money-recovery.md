# Ticket 63 — focused no-money recovery and race checks

On 2026-10-23 the owner requested pushing the reviewed ticket-72 fix and
resuming necessary testing without more money movement. The three #72 commits
were pushed to origin/feat/v18_rev through `4369c4d`; the remote tip was read back
and matched exactly. This record adds no integration implementation changes.

## Selected risks and results

All **three selected tests passed, zero failures/errors**:

1. `TestRevolutVerifiedCheckout.test_lost_paid_sync_response_reopens_original_verified_checkout`:
   lose the native response after the paid record was saved, retry native sync,
   reload, and retain the original verified order/tender/reference without
   collecting again or creating a duplicate native payment.
2. `TestRevolutVerifiedCheckout.test_lost_refund_response_recovers_after_reload_without_second_refund`:
   lose the refund response, reload, recover the same refund and paid native
   return with the original tender and canonical references.
3. `TestRevolutRefundConcurrency.test_simultaneous_same_return_dispatches_one_refund`:
   two concurrent public RPCs in separate committed transactions return the same
   refund-operation identity and produce exactly one mocked refund POST.

The two recovery cases use real native browser tours, not just direct-method
assertions. The concurrency case exercises the reservation/dispatch boundary
with actual separate database cursors. These were selected for duplicate-charge,
refund and native-record risk rather than repeating saved-receipt checks.

## Runtime and boundaries

Frozen deployed addon source `fcb59c4`, version `18.0.1.0.3`, addon tree
`5f66efa252b2215a38c41f8ebc8b99e889769d9a`. Pinned Odoo Community
`18.0.20261015`, PostgreSQL 16.14 and Chrome 153. Disposable project
`revolut-ticket63-final-safety`, fresh synthetic database, internal-only network,
no published ports or real production key. Provider responses were mocked;
global Merchant HTTP blocking rejects unmocked real Merchant calls.

Only these three existing regressions were selected; the test logger reports
three post-install tests passed. The full suite was not repeated and this is
not a full physical release/parity claim.

Log: ignored `build/ticket63-final-safety/focused.log`. Reproduce using
`compose.yaml` with the frozen addon mounted through `ODOO_REVOLUT_ADDONS_DIR`,
`--init pos_revolut` on a fresh database, `--workers 0 --max-cron-threads 0`, and
these comma-separated `--test-tags`:

```text
/pos_revolut:TestRevolutVerifiedCheckout.test_lost_paid_sync_response_reopens_original_verified_checkout,/pos_revolut:TestRevolutVerifiedCheckout.test_lost_refund_response_recovers_after_reload_without_second_refund,/pos_revolut:TestRevolutRefundConcurrency.test_simultaneous_same_return_dispatches_one_refund
```

The disposable database/container/network/volume were removed after the run.
The protected acceptance instance was not used for these tests, and its real
Merchant HTTP block remains enabled and verified. Original financial/native
campaign snapshots were checked separately for preservation. No money moved.
No new live payment/refund attempt was made, and no original draft was cancelled
or session closed.
The broader physical release gate and separate Odoo 19 work remain open.

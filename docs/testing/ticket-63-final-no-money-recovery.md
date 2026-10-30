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

## Supplemental earlier bounded evidence — recovered 2026-10-30

The original private chronology contains the following earlier 2026-10-23
checks. These are separate from the three `fcb59c4` regressions above and are
not new test runs. They preceded ticket 72's `.3` deployment and used the
then-deployed `.2` candidate. They must not be attributed to the later corrected `ed82c90`
release candidate. Exact per-check frozen artifacts and original record
mappings remain with the acceptance custodian; this table preserves the tested
boundaries and limitations without publishing private records.

| Check | Recorded result | Boundary and limitation |
| --- | --- | --- |
| Existing operator/public-user authority | Four allowed and eight denied checks in a read-only, HTTP-blocked transaction | Covers existing-user public server-method access, not an internal colleague's browser login or all POS employee roles. |
| Cashier/manager register grants | Twenty public-method probes across excluded, granted and revoked states on a disposable populated copy | Granted managers reopen the same existing paid returns; cashiers cannot recover refunds, and excluded/revoked users are denied. This is server authorization evidence, not a physical colleague workflow. |
| Completed-refund replay and excessive returns | Eight sequential public refund-start probes: exact replays return the original operation, changed replay details are refused, and fresh excessive returns are rejected | Excessive returns were rejected by original-quantity conservation; this does not prove that a later refund-capacity branch executed. These probes are sequential, distinct from the later concurrency test above. |
| Closing-state and native immutability guards | Twenty-seven public closing-state probes: 24 refusals and three allowed controls, plus two native paid-to-draft refusals | Allowed transitions do not establish actual accounting posting or reopening. The separate native accounting and original-register results are recorded in the handoff and finish-up report. |

These server-method probes recorded zero provider/HTTP calls. Mutable fixtures
were confined to disposable copies, and original financial/native records and
user/grant configuration were checked for preservation. Copy resources were
removed. Failed fixture/harness attempts remain in private evidence; successful
retries do not relabel those attempts as passing.

### Bounded browser and device observations

- During observed POS bootstrap and backend Check Connection, browser traffic
  used local Odoo RPCs, with no Merchant-host browser requests or Revolut key
  fields in the inspected responses. Native Odoo access-token fields were
  classified separately. This does not establish every payment/refund-time
  browser boundary; raw response bodies were not retained as project or hosting
  evidence.
- Terminal payment/refund receipt and reprint results were confirmed by the
  operator. No photos or receipt files were supplied for independent inspection,
  and exact zero-tip-line presentation was not established. These observations
  do not establish physical Odoo POS printing.
- Check Connection initially reported online after the terminal was powered
  off, then later reported offline. Neither the delay nor its cause was measured,
  and no raw provider response was retained for diagnosis. Treat the observed
  status as provider-reported information, not proof of instantaneous physical
  reachability. This is a historical limitation, not a diagnosed new regression
  or release blocker.
- The chronology distinguishes explicit operator Retry/ambiguous navigation
  from automatic redispatch. Recorded cancelled/no-capture outcomes do not
  establish an open automatic-send defect.

The accepted Community 18 campaign subsequently closed in
[ticket 63](../tickets/closed/63-v18-terminal-acceptance.md). Its only retained
financial/native obligation is [ticket 83](../tickets/ready-for-human/83-finish-deferred-v18-refund-return-session.md).
These additions authorise no new test, live request or replay.

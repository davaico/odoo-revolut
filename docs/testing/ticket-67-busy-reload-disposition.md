# Ticket 67 — busy reload test disposition

2026-10-23; base and integration target `feat/v18_rev`.

## Finding

The immediate-Resume assumption in the native browser tour is too strict.
Reload can retain an earlier in-flight local payment snapshot even after the
current browser received a definitive busy rejection. In that state the addon
correctly requires Check status before offering Resume. The server then proves
the same saved tender was not dispatched; Resume becomes available without a
new financial start. No production behavior change is needed for this case.

The original historical failure remains retained privately: its full suite
reported 762 passes and one failure, missing Resume after reload. Its exact
cause cannot be proven because the original persisted browser flags were not
captured. The equivalent symptom and supported recovery below bound that
observation; later green runs do not rewrite the historical result.

## Diagnosis and retained evidence

All new runs used disposable internal-only Docker projects, mocked Merchant
responses and the global real-Merchant HTTP block. Original acceptance records
and credentials were not accessed. Ignored diagnostic material lives under
`build/ticket67-diagnosis/`.

- `baseline-old.log`: unchanged historical candidate, one selected test passed.
- `repeat-old.log`: twelve instrumented repetitions on that candidate passed.
  Pre-refresh/reopen snapshots retained the same order/tender identities and
  safe undispatched flags. These passes alone are not a diagnosis.
- `ordered-old.log`: first ordering probe produced one failed expectation and
  one pass. It did not verify the actual stored flags and did not reproduce
  the intended stale snapshot reliably; this unsuccessful probe is retained.
- `ordered-current-attempt2.log`: both probes passed, but disk inspection
  showed different snapshots. One retained actual in-flight state and recovered
  through Check status; the other retained undispatched state and showed Resume.
- `ordered-current-attempt3.log`: both fixtures verified an actual persisted
  in-flight snapshot (`waiting`, started/starting true, undispatched false).
  The old immediate-Resume assertion reproduced the exact missing-selector
  timeout. The paired Check-status recovery passed, including the existing
  same-identity, single accepted payment and provider-call-count assertions.
  Its intentional result was one failed strict assertion and one passed
  supported recovery, exit 1.

The native runtime debounces IndexedDB writes by 200 ms and ignores JSONuiState
when deciding whether unchanged native record values need another write.
The historical log places refresh about 96 ms after the final busy response.
These facts support the persistence-ordering explanation; the missing original
disk snapshot prevents a definitive retrospective attribution.

The controlled fixture saves actual in-flight state through native persistence,
evicting only its synthetic cached tender first so the native deduplication
cannot retain a different snapshot. It blocks subsequent local writes until
reload and verifies the stored flags. It does not invent financial state, add
a blind delay, bypass server recovery or permit an additional financial start.

Current frozen production candidate: `fcb59c4`, addon `18.0.1.0.3`. Its
`paymentActions` and `restorePaymentLine` functions match the historical
candidate byte-for-byte. Diagnostic instrumentation stays in the ignored build
directory; no debug logging was added to tracked addon code.

## Regression correction

The existing tour now accepts either Resume or Check status after reload.
If reconciliation is needed, it clicks Check status once, then still requires
Resume, server-confirmed unstarted recovery, unchanged tender identity and
no additional start RPC. The existing terminal lock, repeated read-only
checks, double-Resume and one-payment assertions remain.

A second native browser test deterministically retains the in-flight snapshot
and requires Check status before recovery. Only tour/test code changes; no
payment implementation changes. This is not a full-suite or physical release
claim.

## Final verification

The corrected original reload and deterministic in-flight reload tests first
passed together: **2 tests, zero failures/errors, exit 0**, `regression.log`.
The final shared-helper verification added the existing cash-alternative case:
**3 tests, zero failures/errors, exit 0**, `final-three.log`.

Reproduce with `scripts/test-addon --test-tags` and these comma-separated tags:

```text
/pos_revolut:TestRevolutVerifiedCheckout.test_terminal_busy_recovers_after_release_and_reload_without_duplicate_charge,/pos_revolut:TestRevolutVerifiedCheckout.test_terminal_busy_inflight_snapshot_reconciles_after_reload_without_duplicate_charge,/pos_revolut:TestRevolutVerifiedCheckout.test_terminal_busy_line_can_be_removed_for_cash_without_second_dispatch
```

JavaScript and Python syntax checks and `git diff --check` passed. No
`[DEBUG-t67]` instrumentation remains in tracked addon source. Independent
Docker queries after final cleanup found no `t67-busy` containers, networks
or volumes. No original live container was changed. No commit or push was
performed. There is no ticket-67 counterpart in the sanitized tracker; this
report records the disposition without importing private ticket ancestry.

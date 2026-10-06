# 46 — Recover checkout refresh after payment verification

**Work branch:** `codex/46-recover-verified-checkout-refresh`

**State:** closed

**Triage:** ready-for-agent

**Severity:** P2

## What to build

When the connection fails after Revolut verification but before the browser restores canonical checkout data, the cashier sees a recoverable state and can finish the same sale or return after reconnecting. The payment remains verified, no new financial request is sent, and the global terminal-busy flag cannot remain stranded.

## Source and evidence

Full integration review of main `597a59ae0f8e489773e02f7776bda7001beb5741`, 2026-10-06. The exact state module was exercised with the pinned native payment-screen lifecycle: verified-result handling requested canonical checkout data, failed, retried inside its exception handler and failed again. The request rejected with an unhandled rejection, the line remained waiting, and the global terminal-busy flag stayed true. Native cleanup occurs only after that awaited request resolves. Check status is only offered in the retry state, while the verified snapshot prevents delete-driven cancellation.

Reload remains a recovery route; this finding does not establish duplicate payment or loss of financial evidence. The approved interruption/reconnection workflow requires recovery of the original verified payment without a replacement operation.

## Acceptance criteria

- [x] Reproduce rejected and timed-out canonical checkout restoration after verification for an authorized payment and a saved refund, through the native payment screen.
- [x] Represent authoritative financial verification separately from successful browser restoration. A false callback result alone is insufficient while native response handling treats every verified snapshot as successful.
- [x] Preserve operation identity and verified references while exposing an actionable, bounded, read-only restoration retry. Reconnection permits completion without requiring browser storage deletion or another financial dispatch.
- [x] Clear native terminal-busy state reliably on failure, timeout and completion. Other eligible orders can use the terminal once server-side financial rules permit it.
- [x] Do not automatically validate until canonical totals, terminal-selected tips and refund targets are restored and normal server settlement checks succeed. Preserve partial-payment and multiple-allocation behavior.
- [x] Handle repeated failures, double clicks, cancellation/navigation races and reload without unhandled promise rejections, duplicate receipt references or regression of verified evidence.
- [x] Complete the original sale or native return exactly once after successful restoration, with the correct amount, currency and references. Include a native browser regression as well as focused state-module tests.
- [x] Mock all provider calls and assert no new charge/refund is issued during restoration. Document the visible recovery action if operator guidance changes.

## Blocked by

None. Can start immediately against the current integration baseline. It can use ordinary positive, unrounded fixtures and does not depend on either other review ticket.

## Scope limits

No force-done bypass, replay of successful financial operations, new provider behavior, live testing, deployment or broad frontend rewrite.

## Approval and publication — 2026-10-06

The owner approved the three-ticket breakdown and explicitly requested direct
publication as ready-for-agent. This ticket was claimed for implementation on 2026-10-06. Its
work branch is an implementation assignment, not a branch created by this
publication. Recheck the current implementation before starting; review
evidence describes the pinned main revision above. Implementation has not started as part of this publication. Deployment and
live financial operations remain outside this ticket's automated work.


## Implementation and closure — 2026-10-06

Closed on runtime `c29f957`, based on local main
`a3f5e5e5fe8fcc8a7a40f96ca94d54792cfa40d9`. Financial verification now remains
separate from browser restoration. Failed, timed-out or incomplete canonical
loading preserves the same verified operation and exposes bounded read-only
Check status recovery while releasing native terminal busy state. Native
completion requires restored canonical checkout data and normal settlement.

Complete mocked acceptance passed **597 fresh-install tests and 597 upgrade
tests**, zero failures or errors. Six native recovery tours cover rejected,
timed-out and offline loading for authorized payments and saved refunds,
including repeated clicks, blocked manual checkout and reload. The 107 focused
state checks cover cancellation and late-response races; 54 tooling checks
pass, with three existing optional PDF checks skipped. Standards and final
Spec reviews each report zero findings. The initial Spec finding was
reproduced in native sale/refund flows and corrected before final acceptance.

[Verification evidence](../../testing/ticket-46-verified-checkout-recovery.md)
records commands, reproductions, results and the fixed runtime snapshot.
[Operator guidance](../../installation.md) explains same-line recovery.
Upgrade the addon and reload POS assets; no schema, configuration or credential
change is required. Deployment and live release acceptance remain separate.

# Ticket 63 — additional acceptance checks, 2026-10-23

Base and integration target: `feat/v18_rev`, following ADR 0002. This is a
bounded evidence checkpoint, not release approval or closure of ticket 63.
Exact live references, account details and original-record evidence remain
private. No ticket is moved by this report.

## Frozen candidate and isolation

The no-money checks used frozen deployed source
`fcb59c40921eaf347fbf5f36583e7b0cefb3f878`, addon `18.0.1.0.3`, addon tree
`5f66efa252b2215a38c41f8ebc8b99e889769d9a`, pinned Odoo Community
`18.0.20261015`. Each disposable Compose project used an internal-only network,
no published ports, synthetic data and credentials, and the global Merchant
HTTP block. Provider behavior was mocked; original acceptance records did not
participate in these synthetic tests.

Before running documents and restart recovery, the current addon, their helper
scripts, runners and Compose configuration were compared with the frozen
candidate: no differences. The addon was archived from that commit and mounted
read-only. This also checks the runners' assumption that their checkout's helper
scripts match the mounted addon.

Ignored evidence is under `build/ticket63-finish-20261023/`. Initial restart and
targeted starts exhausted Docker's default network address pools before tests
ran. Their failed startup logs remain retained. Sequential reruns succeeded;
no unrelated network was removed to make room. Disposable project cleanup was
verified after successful completion.

## Native documents — passed

`scripts/test-native-documents` completed with exit 0 using project
`t63-finish-documents-20261023` and the frozen addon override. Evidence:
`documents.log`, `documents/`, and `documents-sha256.txt` in the ignored folder.

The native seed closed sessions, reopened a register, created later invoices,
conserved partial credit notes and a taxable terminal tip. Real QWeb PDFs and
repeated authenticated native downloads passed assertions; historical reads
and repeated retrieval preserved financial evidence and did not call the
provider. The four native one-page PDFs were rendered and visually inspected:

- Synthetic USD invoice 12.34.
- Its partial credit notes 3.09 and 9.25, conserving the original total.
- Synthetic taxable-tip invoice 100.09.

All four pages were readable with no clipping or overlap. This establishes
native PDF generation and retrieval, not physical printer output.

## Process restart recovery — passed

`scripts/test-restart-recovery` completed with exit 0 using project
`t63-finish-restart-20261023` and the same frozen addon. Evidence:
`restart-attempt2.log`; `restart.log` retains the initial infrastructure failure.

Across three Odoo processes, zero-tip and nonzero-tip captured payments stayed
reserved while report evidence was pending. Recovery preserved the same
authority, ledger and provider references, projected exact tips once, and
performed no financial replay. Final repeated observation used only mocked
GETs and left checkout completion to the cashier.

Independent Docker label queries found no remaining containers, networks or
volumes for either the document or restart project after cleanup.

## Targeted Restaurant, refund and stock checks — passed

`scripts/test-addon --addons-dir <frozen-deployed-addons> --test-tags <tags>`
completed with exit 0 in project `t63-finish-targeted-20261023`.
`targeted-attempt2.log` reports **76 tests, zero failures and zero errors**.
The exact selected tags were:

```text
/pos_revolut:TestRevolutRestaurantPosStarts,/pos_revolut:TestRevolutTakeoutReadinessUi,/pos_revolut:TestTakeoutScheduling,/pos_revolut:TestRevolutTipRefund,/pos_revolut:TestDiscountedRoundedReturns,/pos_revolut:TestExternalNativeStock,/pos_revolut:TestRefundSessionClose.test_completed_refund_on_unfinalized_return_blocks_session_closing
```

These exercise native browser Restaurant/readiness flows, scheduling and
timezones, partial/tip refunds, discounted/rounded returns, native stock and
accounting effects, and refusal to close with a completed refund whose native
return remains unfinished. The full suite was not repeated. This selection
does not diagnose the older candidate's intermittent busy-reload failure.

## Original register and hardware scope

After the owner authorized draft disposition, the original register's drafts
were cancelled through the native browser workflow. Native closure posted its
five paid orders and produced a balanced session accounting move with debit and
credit GBP 0.04 each. The register then reopened with zero opening cash. Exact
record identities and proof remain private; this is distinct from the earlier
successful disposable-copy lifecycle check.

The owner confirmed there is no Odoo POS printer in the intended setup, so
physical Odoo printer acceptance is not applicable. Previously completed
terminal receipt checks remain separate evidence.

## Live continuation — provider finality still outstanding

The owner approved a fresh GBP 0.05 total collection budget including tips,
with refunds limited to those new captures. All GBP 0.05 was captured and
verified in three distinct payment operations; no further collection is allowed.

- Restaurant Dine In/table checkout: GBP 0.02 base plus a terminal-selected
  GBP 0.01 tip. Operator confirmed the GBP 0.03 device total and success.
  Odoo automatically completed the original sale with one tip line and a
  matching receipt.
- Retail split: two GBP 0.01, zero-tip card payments on one GBP 0.02 sale.
  Operator used the same physical card for both. After the first capture,
  the sale remained draft with exactly GBP 0.01 due. The second attempt
  exceeded the foreground wait while the provider reported pending; the
  operator saw approval. Later direct original-intent/order GETs confirmed
  completed intent and captured underlying payment. Native Check status
  recovered that same attempt and automatically paid the sale, with two
  distinct original tenders. No replacement charge or Force done occurred.
  This covers two card tenders, not two different physical cards.
- Restaurant partial return: GBP 0.01 base, zero tip, dispatched once.
- Separate Restaurant remaining return: GBP 0.01 base plus GBP 0.01 tip,
  dispatched once against the same original capture. The allocation UI
  correctly showed only GBP 0.02 remaining after the earlier reservation.
- Split-sale return: GBP 0.01 dispatched once against the second original
  card source. Adding the final source is blocked by the native unresolved-
  refund guard until this first allocation is reconciled.

At this checkpoint, three requests total GBP 0.04 and remain provider
processing; GBP 0.01 is still unrequested. Their three native return orders
remain draft. Do not confuse the source history's refunded-quantity label
with provider completion. Preserve all original refund identities, reconcile
first, then allocate the remaining GBP 0.01 to its other original payment.
Finish native returns and session accounting only after verified finality.

Rapid automated keypad input was grouped by native Odoo input handling;
normal 300 ms spaced input set the split tender correctly. No wrong amount
was dispatched and no implementation change was made.

The original campaign's nine payment operations, two refunds and seventeen
dispatch claims preserve compared financial fields and provider references.
Comparison normalized ORM False/nullable integer defaults and SQL timestamps;
native foreign-key IDs were excluded because current database IDs differed
from the older handoff before this work. Private database backup, before/after
snapshots, receipts and comparison proof are retained by the custodian.

Physical Odoo printing is not applicable. At this first checkpoint, live timed
Takeout and split nonzero tips were outstanding; the continuation below supplies
that evidence. Distinct-card use and every physical failure scenario are not
established by these passes. The historical full-suite busy-reload
issue remains undispositioned. Ticket 63 and overall release acceptance remain
open; this result is not a full parity/release claim.

## Owner deferral and safe stopping point

After the final GET-only check still returned processing for all three refunds,
the owner said these take a day or two and deferred waiting/monitoring. No
automation was created. The normal local worker's Merchant HTTP block was
restored and verified; cron remains disabled. Native return completion and
final GBP 0.01 split-source refund remain outstanding, with their authorization
and original identities preserved. No collection budget remained at that checkpoint; a fresh bounded budget was
authorized for the continuation below.

For a future continuation, first reconcile the existing three refunds using
GET-only status calls, recover and complete the same native returns, and only
then issue the still-unrequested GBP 0.01 against its original split source.
Do not replay any existing refund or force a native return paid. The owner’s
deferral is not evidence that those financial/native acceptance checks passed.


## Same-day continuation — timed Takeout and split tip

The owner subsequently authorized a separate GBP 0.05 total charge budget,
including tips, with refunds limited to these new captures. GBP 0.03 was used;
GBP 0.02 remains unused. No additional payment is necessary for these results.

A dedicated Restaurant register exercised timed Takeout through the native UI.
With no pickup slot selected, checkout was blocked and no payment operation or
dispatch claim was created. Selecting tomorrow's 10:00 Europe/Paris slot
persisted the equivalent 08:00 UTC time. The first split tender requested
GBP 0.01 base. A browser reload while that attempt was pending retained the
same attempt and pickup time and exposed Check status without another send.
The owner approved GBP 0.02 including a GBP 0.01 terminal tip. Provider and
Odoo evidence confirmed capture, one tip line and exactly GBP 0.01 still due.
The second GBP 0.01 zero-tip leg was separately approved and verified. The
native sale automatically became paid at GBP 0.03, with matching total paid,
one terminal-tip line and the correct scheduled pickup on its receipt.

Two separate native returns were submitted against their respective original
captures: GBP 0.02 (base 0.01 plus tip 0.01) and GBP 0.01 (base only). Both are
pending; neither native return is forced paid. The allocation picker reserved
the first source's full amount and disabled it for the second return. Waiting
and monitoring remain deferred by the owner's instruction. These submissions
establish allocation and reservation, not completed-refund accounting.

## Authenticated access checks

A separate isolated browser test against the same frozen candidate passed:
one expanded HttpCase, zero failures/errors. Actual cashier and separate POS
manager logins recovered the same pending payment. Lookup, poll, checkout
recovery and POS bootstrap responses contained neither the synthetic token nor
its environment reference. Credential authority reads were denied to both
ordinary roles; restricted configuration reads were denied to the cashier.
Revoking the manager's access denied lookup, poll and checkout recovery without
provider calls. Existing native manager reconciliation and revoked-worklist
tours passed. Financial POST count stayed unchanged.

The initial run exposed a test-harness argument-count mistake, corrected before
the successful run; no product source changed. This evidence covers a colleague
with POS manager access, not a second ordinary cashier's complete checkout.
Refund payloads and a complete network capture were not covered by this check.
Sanitized detailed results and logs are retained in ignored local evidence.

At the final financial checkpoint, both new payment operations are verified
(captures GBP 0.02 with tip 0.01, and GBP 0.01 without tip). All five new refunds
across today's two live batches remain pending. New native returns remain drafts.
The local worker's Merchant HTTP block was restored and its verification script
exited 0. Cron remains disabled. No further card input is needed for these checks.


## Historical busy-reload disposition

The [ticket 67 investigation](ticket-67-busy-reload-disposition.md) reproduces
the old missing-Resume symptom with a verified stale in-flight local snapshot.
Check status then safely recovers the same undispatched tender before Resume,
with no new start during reconciliation. The test's immediate-Resume assertion
was too strict; the correction and deterministic regression change test code
only. Original historical attribution remains uncertain because its persisted
flags were not captured. The old failing result remains retained.


## Owner disposition of remaining physical cases

The owner explicitly selected “record these as untested release limitations”
for a split paid using two different physical cards and a genuine issuer-declined
payment. Neither is marked passed. Same-card split, Cash/card split and mocked
failure coverage remain separate evidence. No additional card tests or charges
are planned. Other unobserved physical interruption variants remain limitations
rather than implied passes. This scope disposition does not assert refund
finality or complete the outstanding native accounting obligations.

Final reload verification passed all three selected native browser tests:
corrected busy reload, deterministic stale-snapshot recovery and busy-to-Cash
alternative. Zero failures/errors, exit 0; syntax and diff checks passed.
Disposable diagnostic resources were removed and cleanup verified. No production
payment code changed, and no commit or push was performed in this continuation.

# Refund investigation — 2026-10-02

## Verdict

Two different original card payments have one processing refund each. There is
no observed duplicate refund or refund exceeding an original payment. The
terminal-created refund is missing from Odoo because the integration reconciles
only Odoo-created refund operations; it has no external refund importer. This
gap exists in both the deployed revision and current repository source.

Processing itself is consistent with the live provider state. Neither processing
refund is verified completed. Do not recreate either refund or substitute cash
for its uncertain card outcome.

## Scope and evidence

Read-only checks ran around 10:34–10:39 UTC (12:34–12:39 Europe/Paris).
The target hostname, VM serial and pinned SSH identity matched the documented
staging host. No addon, service, configuration, database or provider financial
operation was changed. The user explicitly approved server-side credential use
for Merchant GET requests after automatic review initially rejected reading the
service environment. The credential remained on the server; collected output
was restricted to transaction references, amounts and states, with no card or
customer payloads.

- Staging addon: `19.0.1.10.2`, release
  `25e096d74ca62ac7f39558e0257f609be85185d7`.
- Repository: `238924b6999a502777025cd0ff484d09298ebfc3`, addon `19.0.1.10.3`.
- Diff of `revolut_refund.py`, `return_allocation.py` and
  `revolut_refund_views.xml` between those revisions: empty.
- Staging service: active. Odoo refund cron: active, zero failure count,
  last call `2026-10-02 10:38:54 UTC`. Pending operation 6 had a recent
  write and near-term next reconciliation. The scheduler is progressing.
- Odoo database and visible unfiltered Refunds list agree: **six records,
  five Completed and one Pending**. The visible list pager reads `1-6 / 6`.
  Only one of the six is pending. Whether the user's earlier “one line” meant
  one pending operation or a different view is not established; the current
  visible list has all six without a search filter.
- Merchant API version: `2026-08-17`. A GET order list, filtered to Davai
  and creation since September 22, returned 48 orders, below the requested
  page size of 100, without continuation metadata. Individual GETs verified
  all eight listed refund orders and all thirteen Odoo-verified card sources.
  One older USD refund has no integration source and is excluded from GBP totals.

The initial list query with `limit=1000` returned HTTP 400. The corrected
documented `limit=100` query succeeded; an API parameter error was not counted
as reconciliation evidence.

## The two processing refunds

| Refund | Created UTC / Paris | Original Revolut payment | Odoo sale / source | Provider / Odoo |
| --- | --- | --- | --- | --- |
| `6abe5180-d2fa-a57f-876c-6e12bfeb14cf` | Oct 1 12:26:40 / 14:26:40 | `6abbb955-4853-a1c7-9164-afb3fe751e0d` | `261-2-000011`, source 16 | `processing`, payment `refund_started` / operation 6 Pending |
| `6abf7eec-9d7d-ac78-89ab-0e6c57b0d535` | Oct 2 09:52:44 / 11:52:44 | `6abe3521-47d8-afea-b076-25566d3fef64` | `261-2-000018`, source 36 | `processing`, payment `refund_started` / no refund operation |

Each refund is exactly one GBP minor unit (£0.01). Both originals are
`completed`, amount 1, currency GBP and `refunded_amount=1`. Thus the provider
already includes these processing refunds in the original's refunded amount;
that field alone is not evidence of completed customer reimbursement.

The newer refund has no Odoo merchant reference, no local refund record and an
exact `related_order_id` match to source 36. This supports the colleague's
reported terminal initiation. The checked payload does not establish the
human operator's identity.

Sale `261-2-000018` (database ID 18, **Davai GBP Terminal Test - 000018**)
totals £0.02: £0.01 Cash and £0.01 Revolut. The terminal refund covers only
the Revolut tender. No persisted Odoo return lines link to this sale; its
state remains `paid`. A provider refund cannot establish a product return,
cash reimbursement, inventory correction or accounting credit automatically.

Sale `261-2-000011` (database ID 12) totals £0.02 paid through two separate
one-penny Revolut payments. Source 17's refund (operation 5) is completed;
source 16's refund (operation 6) is still processing. Both refer to the same
browser return UUID recorded for return 1012, but neither is linked to a
persisted native return order yet. This matches the earlier checkpoint's
instruction to retain and resume that existing return after verification.

The screenshot's Oct 1 2:26 PM timestamp corresponds to Paris time; its Oct 2
11:52 AM timestamp does too. No fixed settlement deadline is inferred.

## All Odoo-verified Revolut sources

Amounts below are GBP minor units. Refunds are associated using full provider
IDs, not card suffixes or neighboring screenshot rows.

| Source | Odoo sale | Captured | Provider refunded amount | Child refund / state / local operation |
| --- | --- | ---: | ---: | --- |
| 4 | `261-2-000001` | 1 | 1 | `6abb863a` completed / 1 |
| 10 | `261-2-000004` | 1 | 1 | `6abb9ae7` completed / 2 |
| 11 | `261-2-000006` | 3 | 1 | `6abb9ef4` completed / 3 |
| 14 | `261-2-000009` | 1 | 1 | `6abbb3a9` completed / 4 |
| 16 | `261-2-000011` | 1 | 1 | `6abe5180` processing / 6 |
| 17 | `261-2-000011` | 1 | 1 | `6abbbc70` completed / 5 |
| 19 | `261-2-000013` | 1 | 0 | None |
| 20 | `261-2-000014` | 1 | 0 | None |
| 27 | `263-2-000004` | 1 | 0 | None |
| 35 | `261-2-000017` | 1 | 0 | None |
| 36 | `261-2-000018` | 1 | 1 | `6abf7eec` processing / missing |
| 38 | `261-2-000019` | 1 | 0 | None |
| 39 | `261-2-000019` | 1 | 0 | None |

Total card captures: £0.15. Completed refunds: £0.05. Processing refunds:
£0.02. Remaining provider refund capacity: £0.08. These are gross principal
amounts, excluding processing fees, cash tenders and older non-integration
transactions. £0.02 processing is not described as settled money.

For every verified source, associated nonfailed refund amounts were no greater
than the captured amount. Odoo locally accounts for only £0.06 of the £0.07
completed/processing provider refunds. Its local remaining card balance is
therefore overstated by £0.01.

## Root cause and safeguards

`views/revolut_refund_views.xml:35` lists local
`pos.revolut.refund.operation` records. `models/return_allocation.py:377`
creates them when Odoo reserves a return. The refund cron at
`models/revolut_refund.py:108` searches only existing dispatching, pending or
unresolved operations. Lost-response recovery at line 347 searches by an
existing local idempotency reference. None of these paths imports a refund
created outside Odoo. A completed original payment also stops normal payment
polling; it is not periodically inspected for later external refunds.

Local reservations lock the original payment and count all nonfailed refund
states toward its cap (`return_allocation.py:329–353`). Same-line duplicate
requests reuse the existing record. Uncertainty retains the reservation and
never authorizes reposting. Separate original-quantity and base/tip checks
also apply. These controls prevent unlimited refunds through Odoo alone.

Before refund POST, Odoo GETs the original and compares `refunded_amount`
with locally verified refunds (`revolut_refund.py:201–209`). A mismatch
blocks dispatch as `failed` / `original_ineligible`. For source 36 the live
provider value is 1 while the local verified sum is 0; the check would reject
another Odoo refund. No real duplicate request was attempted to verify this;
the mismatch behavior was exercised with mocked HTTP instead.

Limits of this guard:

- The allocation picker reads local data only, so it can show stale availability.
- Legacy sources accept an omitted `refunded_amount` by substituting the
  local verified sum. New explicitly allocated sources require an integer.
- An external refund arriving between original GET and refund POST cannot be
  serialized by Odoo's database lock. Provider enforcement remains necessary.
- If a provider did not include a processing external refund in the original's
  refunded amount, the current flow would not separately discover that pending
  refund. **Today's live originals do include it.**

Revolut's [refund guide](https://developer.revolut.com/docs/guides/merchant/operations/refunds)
documents asynchronous refund processing and the total refund ceiling. Its
[terminal refund guidance](https://help.revolut.com/business/help/merchant-accounts/revolut-terminal/transactions-with-revolut-terminal/refund-a-payment-received-via-revolut-terminal/)
also states cumulative refunds cannot exceed the original transaction. Those
documents and the observed ledger support a finite ceiling; provider enforcement
under a simultaneous live terminal/API race was not tested.

## Reproduction and verification

The read-only live diagnostic fed `/tmp/refund_readonly_remote.py` to Python
over pinned SSH. It compared whitelisted Merchant GET responses with Odoo
SELECTs in explicit READ ONLY transactions. It returned **exit 1** with:

```json
{"verdict":"EXTERNAL_REFUND_MISSING_IN_ODOO","missing_refund_ids":["6abf7eec-9d7d-ac78-89ab-0e6c57b0d535"]}
```

Output was captured locally at `/tmp/refund-live-readonly-20261002.jsonl`.
The minimal symptom is one provider refund linked to a verified Odoo source
without a corresponding local refund record. Removing unrelated historical
transactions does not change this result. The live mismatch remains unresolved;
this investigation did not implement or deploy an importer.

Existing refund, refund concurrency and tip refund suites ran against fresh
disposable Odoo `19.0.20260908` with mocked HTTP and external network isolation:

```bash
ODOO_REVOLUT_TEST_PROJECT=refund-debug scripts/test-addon \
  --test-tags '/pos_revolut:TestRevolutRefund,/pos_revolut:TestRevolutRefundConcurrency,/pos_revolut:TestRevolutTipRefund'
```

**61 tests, zero failures/errors.** Five additional tests in a temporary copied
addon exercised full/partial external refunded-amount mismatches, the legacy
missing-field fallback, local-only source discovery, and the absence of a
separate external-pending query. **Five tests, zero failures/errors.** These
are behavioral characterizations, including reproduced gaps, not five fixes.
Logs: `/tmp/refund-debug-test.log`, `/tmp/refund-debug-probes-test.log`.
Disposable Docker projects were removed. No test contacted a real provider.

## Follow-up

[Ticket 37](../tickets/ready-for-agents/37-reconcile-external-terminal-refunds.md)
tracks the external-refund visibility and reconciliation gap. On 2026-10-02,
the owner approved automatic discovery and recording, with product returns and
cash adjustments handled separately by a manager. The ticket is now
`ready-for-agent` with an implementation brief; no runtime fix is claimed.
The initial uncommitted report used number 35 from an older checkout. This was
corrected to 37 after checking other worktrees and branch ticket inventories:
35 covers shared-register authorization and 36 covers custom-receipt removal.
Keep the two existing refunds under their existing provider references. Once
operation 6 is verified, resume the original browser return 1012 rather than
creating a replacement refund. The external refund needs a deliberate local
reconciliation workflow that records money movement without inventing returned
products or issuing money a second time. Pending operation 6 still blocks the
normal staging deployment preflight.

## Deliverable self-check

Using the agent-self-evaluation skill: accuracy 4/5 (live ID/state matching and
66 passing mocked checks; no provider race test), completeness 4/5 (all verified
sources reconciled; provider processing-time explanation remains unverified),
clarity 4/5 (two-row mapping leads the operational findings; the full evidence
is lengthy), actionability 4/5 (exact sales and triaged remediation; no supported
external-import action currently exists), conciseness 4/5 (short user-facing
answer backed by this longer evidence). Overall 4.0/5. Highest-impact next step
is implementation of the approved idempotent external-refund reconciliation
workflow. The verdict distinguishes observed states,
mocked safeguards and untested provider behavior so the user can assess it.

# Ticket 24 — Financial snapshot processing bounds

Implementation candidate: `604962a41d74552a497f661baa66b45c8db72113`.
Reviewed base: `ffae23dcfcf71dc61293404e3c7183b3fe70e750`.
Branch: `codex/24-bound-financial-snapshot-processing`.
Addon version: `19.0.1.7.7`. Local verification date: 2026-09-30.

## Boundary and limits

The shared private model normalizer delegates to `models/financial_snapshot.py`.
Payment starts, manager return discovery/reservation and final payment/refund
comparisons all use this boundary. It validates optional totals and Restaurant
identifiers before their callers convert them. Original-return identifiers are
included in the aggregate budget before being retained.

| Resource | Limit |
| --- | --- |
| Cart lines | 1–1,000, counted before normalization traversal |
| Numeric input | 64 ASCII characters; finite decimal/scientific notation |
| Precision / exponent | 28 significant digits / −324…324 |
| Fixed-point output | 354 characters, including sign/point (up to 352 fractional places for positive values) |
| Quantity / unit price | Inclusive signed range ±1,000,000,000 |
| Discount | Inclusive signed range ±1,000,000 |
| Optional total | Inclusive signed range ±1,000,000,000,000 |
| Line UUID | Unique, nonempty text, at most 128 characters |
| Record ID | Integer 0…2,147,483,647; nonzero product/original return ID |
| Taxes | At most 100 per line, checked before and after command unwrapping |
| Retained snapshot | 262,144 default ASCII JSON bytes, including collection separators and original return IDs |

These magnitudes retain existing negative prices/backend discounts without
introducing new POS discount policy. Fractional and negative return quantities,
17-digit float artifacts, signed zero, ordinary prices, scientific notation and
`5e-324` remain canonical. Precision matches the previous Decimal context.
Rejected values are never rounded, clamped or truncated to fit a bound. Current
fixtures require no higher caps; customer-specific extreme catalog/UoM settings
have not been verified. Default ASCII JSON accounts for Unicode escape growth.
Each temporary encoded line has independently bounded scalars/collections; the
aggregate budget is charged before appending it, with no oversized final encoding.

Known financial settlement paths check count before relationship discovery and
native Odoo's earlier raw-line traversal. Generic cash relationship discovery
uses slices of at most 1,000 lines and retains at most 1,000 original IDs per
lookup, so a forged refund flag cannot hide a financial relationship. It rejects
an oversized cart as soon as it finds a Revolut original, including a reference
in a later batch, before numeric normalization. Classification of unknown cash
relationships remains proportional to native input size; it is not a constant
cost limit for all Odoo carts. Unrelated cash-only carts are outside these
snapshot limits and a 1,001-line cash checkout remains valid.

Pinned Odoo's `related_models/serialization.js:179` exports an **unset** scalar
as `false`, while numeric zero remains zero. `PosOrderline.getDiscount()` and
the addon payment-start adapter use zero for an unset discount. Final native
charge/refund settlement therefore maps exactly `discount is False` to zero
before numeric validation. The private helper defaults to strict validation;
payment starts, refund starts and source discovery retain that default.
`None`, empty text/collections and other malformed values remain invalid.
This transport rule preserves comparison with existing canonical zero evidence;
it neither changes stored snapshots nor permits a nonzero discount to match zero.

## Bounded red/green and RPC evidence

The ticket pre-agrees public server entrypoints, controlled lifecycle and native
POS adapter seams. All Odoo runs use package `19.0.20260908`, the repository's
Chrome 153 test image, a disposable database, mocked provider I/O, a verified
Merchant HTTP guard and an internal Docker network. No hosting change, live
Merchant request, terminal operation or destructive load test was performed.

Exact reviewed-main models with candidate regression tests reproduced the issue
through `odoo.service.model.call_kw` → `revolut_start_payment` as an ordinary
internal POS cashier, with a configured open session and test credential.
A **209-byte** snapshot containing quantity `1e1000`, unit price `1e-1000` and
discount `1e1000` was accepted and retained as **3,186 ASCII JSON bytes**. The
regression failed because no `snapshot_invalid` rejection was returned.
Exponents were capped at 1,000; no worker exhaustion was attempted.

Separately, the exact pinned RPC dispatcher successfully invoked the old public
helper for cashier, manager, non-POS internal user and portal user. Four rejection
subtests failed on reviewed main. After the correction, the removed public name
raises `AttributeError`; the private name raises `AccessError` for all four roles.
This is database-backed Odoo dispatcher evidence, not a claim of unauthenticated
access or a separate end-to-end HTTP transport test.

The same cashier trigger now returns an identity-bound `snapshot_invalid`,
`dispatched=false` response. It creates no attempt, provider request or retained
coordination lock. The order-lock-protected absence check refuses that proof if
any earlier payment/refund evidence or predecessor exists for the order.
Exceptions, lost responses, empty lookups and mismatched rejection identities
remain insufficient for removal or financial retry.

## Regression evidence

- The initial two security regressions passed in pinned Odoo after the fix.
- Focused payment/refund/settlement/mutation and native refund recovery tests:
  **130 passed** before the native transport follow-up, zero failures/errors.
  Representation limits are checked before Decimal parsing and fixed-point
  width before formatting; a sentinel oversized list rejects before iteration.
  All affected fields have positive/negative exponent, length, precision,
  malformed/nonfinite and magnitude boundary controls.
- Three final focused tests passed after the last settlement preflight change:
  an exact **262,144-byte** snapshot is accepted; **262,145 bytes** is rejected
  with zero provider calls. Taxes, escaped UUIDs and original return IDs contribute
  to this budget. Known financial settlement is bounded; a cash-only 1,001-line
  order still checks out through native Odoo without provider calls.
- Public manager refund tests reject invalid starts/discovery without reservations,
  correct a fractional return on the same payment line, verify the resulting
  refund, and preserve an uncertain reservation after an invalid replay.
- Literal persisted payment/refund snapshots still settle without being rewritten:
  normal floats, scientific text, discount 20, fractional/negative quantities,
  sorted tax commands and original return links remain comparable. Invalid
  settlement retains verified state, references and reservations.
- The final native zero-discount follow-up passed **154 affected tests**, zero
  failures/errors, including every native checkout tour, strict supplied-input
  controls, malformed settlement inputs and both new transport compatibility
  controls. Literal canonical zero evidence matches native `False` only at
  settlement; references and verified charge/refund state remain intact.
- Three actual POS tours cover payment correction/reload/read-only status/explicit
  resume, rejected-line removal and cash checkout, and refund correction/reload/
  reselection/verified completion. Provider mutation counts establish one intended
  workflow after correction and none for rejected or cash-substituted starts.
  A refund reload tour initially exposed a test wait race: original-sale loading
  preceded the tracked RPC. Awaiting the real lifecycle request fixed the tour;
  a delayed-original-loading regression preserves the guard while it is pending.
- Lifecycle command `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`:
  **65 passed**, zero failures/skips, including lost-response/uncertain-attempt,
  refund, predecessor and identity-mismatch controls.
- `python3 -m unittest discover -s tests -v`: **29 passed**.
- `./scripts/test-restart-recovery`: exit **0**, `RESTART_RECOVERY_OK` across
  two Odoo processes with persisted payment/refund evidence.
- Python compilation, JavaScript syntax checks and `git diff --check`: **PASS**.
  No typechecker, linter or coverage measurement is configured; these syntax
  checks are not represented as typechecking or coverage.

The first full run at `d301d3a` passed 232 install, 232 upgrade and eight
Restaurant tests. The reviewed follow-up at `1c5d1e5` then failed 14 of 233
fresh-install tests: checkout tours could not settle Odoo's unset/false discount
after the stricter supplied-discount rule. Those failures are not counted as
passes. Two capped public charge/refund settlement regressions reproduced the
same issue before the narrow native transport correction. The final full
command at `604962a` returned **0**, with **234 fresh-install**, **234 upgrade**
and **8 Restaurant** tests, each with zero failures/errors. The result markers
were recorded at **10:22:56**, **10:25:37** and **10:26:35 UTC**, respectively,
on 2026-09-30. No browser-skip warnings occurred. The command was:

```bash
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket24-release ./scripts/test-addon --verify-install-upgrade
```

Restart recovery, the 65 lifecycle tests and 29 deployment tests also passed on
the final source. The image was `odoo-revolut-test:19.0.20260908-chrome153`,
observed ID `sha256:5cadadc4ec76e53eccebe03f8367a67b5c240ebd04554f34c50f3abbacc2757c`.
The final tracker/evidence commit changes documentation only; addon and
deployment/test tooling must match `604962a` when reusing these results.

## Standards

Independent review through `604962a` found no documented-standard violations or
actionable baseline smells. The addon boundary, Odoo entrypoints, mocked HTTP,
canonical triage labels and folder layout are preserved. Private ORM delegation
is appropriate; tax count checks cover distinct command-wrapping stages.
Standards findings: **0**.

## Spec

Independent review found two concrete implementation issues: supplied malformed
falsy discounts bypassed validation, and unknown cash-return discovery retained
an unbounded original-ID list. Strict default discount validation and bounded
discovery batches corrected both; pinned public regressions passed red/green.
The final native unset-discount compatibility rule is documented above.
Review through `604962a` found zero remaining source/test findings or scope creep.
The native transport exception enables only final charge/refund comparison and
does not weaken strict starts/discovery or stored evidence. Spec findings: **0**.

## Security verification and limitations

A fresh independent bypass/regression review found one cash-only compatibility
regression before candidate commit. Public checkout reproduced its rejection;
the narrowed preflight then passed the cash control while retaining original-return
and financial settlement guards. No further concrete surviving expansion bypass
or regression was found. A fresh independent verifier reviewed immutable
`604962a` against the triage base, checked the capped baseline/green assertions
and final runtime logs, inspected the exact pinned native serializer and
independently reran all 65 lifecycle tests. The verification result was:

```json
{"results": [{"id": "ticket-24", "status": "fixed"}]}
```

`ticket-24` is the local ticket identifier, not an invented Security finding ID.
The verdict covers the reproduced input-amplification boundary and unnecessary
authenticated helper dispatch. Evidence includes numeric/collection/aggregate
bounds, zero-dispatch/no-reservation rejection, safe correction, preserved
uncertainty, literal persisted comparisons, native POS tours, final install/
upgrade/Restaurant results and recovery across two processes.

Input amplification and authenticated helper dispatch are demonstrated. Actual
worker exhaustion, deployed outage severity, deployment worker controls and live
financial behavior remain unverified. This finding has no supplied scan finding
ID or original scanned revision; neither is invented here. Historical out-of-bound
financial evidence is retained and requires reconciliation, never silent rewriting
or exception-based retry.

Main's completed ticket 22 correction is included in the tested base. Ticket 23
is still a separate open branch; this report does not claim its integration or live
acceptance. Ticket 12 retains its outstanding integration, reconciliation, staging
and physical-terminal gates. Its historical dated evidence remains unchanged.

## Self-evaluation

Overall: **4.4/5** across five quality axes. No critical issues; deliver as-is.

| Axis | Score | Evidence and remaining improvement |
| --- | --- | --- |
| Accuracy | 4 | Exact pinned dispatcher, serializer, source and runtime results are recorded; deployment outage impact remains deliberately unmeasured. Measure deployment controls separately if that impact is later investigated. |
| Completeness | 5 | All nine local acceptance criteria have implementation, positive/adversarial coverage and independent verification. Human release work stays in ticket 12. |
| Clarity | 4 | Limits, recovery rules, compatibility and limitations are explicit; the historical run narrative adds reading time. A combined-release summary can link this detailed record. |
| Actionability | 5 | The branch, immutable source, runnable commands, operator upgrade/recovery guidance and separate release gate are recorded. |
| Conciseness | 4 | The user handoff links one evidence file; this file retains several corrective runs for provenance. Keep the future integration handoff focused on its final candidate and affected results. |

Top improvements: record the combined integration candidate in ticket 12;
link this detailed history from a short release summary. Both are later release
work, not missing local remediation.
Self-check: the requested branch implementation, tests, reviews and commit are
reviewable; the user can distinguish local completion from human release work.

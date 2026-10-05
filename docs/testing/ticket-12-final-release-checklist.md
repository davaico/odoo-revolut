# Ticket 12 — Final release and open-source checklist

Requested by the owner on **2026-10-05**: return here to retest the complete
integration before release. This is the current checklist for
[ticket 12](../tickets/ready-for-human/12-live-terminal-release-evidence.md).
It adds ticket 41's external-refund completion and retains the earlier
[release evidence](ticket-12-release-evidence.md),
[operator observations](ticket-12-operator-observations.md) and
[refund-screen verification](refund-screen-clarity.md).

All checks below start **NOT RUN for the final candidate**. Prior passes keep
their dates, revisions and limitations. They are useful baselines, not erased
or silently reused as current acceptance. Do not mark a broad row passed when
only one listed subcase passed. Record each subcase separately.

## 1. Freeze the candidate and prepare the test session

- [ ] Ticket 41 implementation is reviewed/merged; include the merged ticket 40 rounding correction and all intervening reviewed fixes. Record remaining implementation defects. Independent preparation can proceed before this gate is complete.
- [ ] Record the full candidate SHA, addon and pinned Odoo versions, artifact checksum, included fixes and independent review. A later runtime change requires a new candidate and affected retests; explain any evidence carried forward.
- [ ] Confirm the actual deployed version, backup/upgrade record, Merchant environment/account, physical location, eligible online terminal/version, Pay at Counter, currency, register/session and authorized cashier/manager access. Do not rely on dated staging facts.
- [ ] Choose dedicated fixtures for retail, tips, Restaurant, mixed/multiple tenders, fractional quantities, returned goods and no goods returned. Identify existing historical sale/invoice fixtures. Do not assume an unfamiliar refund identifies returned products or its initiating person/device.
- [ ] Agree the amounts, aggregate test budget, supported controlled failure methods and eventual money disposition before live financial actions. Old budgets and completed refund references are not authorization to send money again.
- [ ] Check current reconciliation/exposure and deployment guards; uncertainty remains protected. Missing fixtures, unsupported failure methods or unavailable device/operator are explicit blockers.

## 2. Run automated acceptance on the exact combined revision

Use the existing disposable test tooling and documented environment. Mock
Merchant HTTP; automated tests must never contact the real terminal/API.
Record commands, exact source, counts, skipped checks and log locations.

| ID | Required verification | Final result |
| --- | --- | --- |
| A01 | Full addon fresh installation and upgrade on pinned Odoo; native retail and Restaurant browser tours actually execute. Check consolidated-addon migration and preservation of older operation records. | NOT RUN |
| A02 | POS lifecycle, decline/failure/cancellation (including cancellation before dispatch), timeout/reload/late success, busy-terminal recovery, status coalescing and restart recovery. Assert intended dispatch counts and original identity reuse. | NOT RUN |
| A03 | Public server/API settlement, bounded snapshot/allocation processing and credential/company/register authority. Missing/mismatched saved return or payment line, unauthorized access and excess/invalid allocations reject before Merchant HTTP. Credentials are absent from POS payloads/browser logs. | NOT RUN |
| A04 | Native full/partial/mixed/multiple-tender returns; ticket 40 rounding and reservation/recovery/history regressions; ticket 41 goods/no-goods/existing-return/pending/concurrent-manager regressions with actual native stock/accounting output and zero new financial POSTs for issued refunds. | NOT RUN |
| A05 | Deployment preflight/financial/PDF guards, migration checks and exact packaged-artifact retail and upgrade acceptance. Failure leaves the active release and financial records intact. Inspect the delivered artifact, not only the checkout. | NOT RUN |

Existing entry points include `scripts/test-addon --verify-install-upgrade`,
the Node suite at `addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`,
the repository Python tests and the focused restart/deployment/authority upgrade
scripts. Exact artifact checks use `scripts/test-delivered-addon --revision
<full-candidate-SHA> --scenario retail` and the migration scenario with
`--migration-from <full-reviewed-legacy-SHA>`. Select a genuine legacy fixture
and follow [installation/testing guidance](../installation.md); do not invent
a migration baseline or accept browser skips as passes.

## 3. Retest the operator flows

Run one controlled scenario at a time. Record provider/Odoo/device outcomes
separately; a completed intent alone is not payment proof. A provider-completed
refund and funds appearing on the customer's account are distinct observations.
Use supported Sandbox/disposable methods first. If a mandatory live subcase
cannot be reproduced safely, record **NOT REPRODUCIBLE**, its reason and next
action; it remains an unresolved acceptance gap.

| ID | Scenario and subcases | Required observed result | Final result |
| --- | --- | --- | --- |
| R01 | Register opening/reload, authorized colleague access, unauthorized user/register and Cash-only baseline. | Register loads; appropriate access works; denials are understandable; ordinary Cash checkout works without terminal dispatch. | NOT RUN |
| R02 | Full retail card payment. | Terminal amount/currency match; only verified successful underlying payment completes the order automatically; Orders, receipt and references agree. | NOT RUN |
| R03 | Cash/card split and two or more card allocations. | Each request uses its allocation; partial payment keeps the order open; only the full verified balance closes it; references and original tender shares remain distinct. | NOT RUN |
| R04 | Restaurant dine-in, takeaway and unchanged partly paid order recovery; relevant split/merge/transfer/table controls. | Correct fulfilment and order identity; supported moves work; unsafe order changes are explained and guarded; automatic checkout works. | NOT RUN |
| R05 | Terminal tip accepted and declined/no-tip; payment/report/receipt and supported tip-refund allocation. | Base, tip, gross and stored tender totals agree with authoritative evidence; the tip is represented once; unknown components are not guessed. | NOT RUN |
| R06 | Controlled decline, failure and safe retry; POS/device cancellation before and during dispatch; supported capture/cancel race. | Distinct unpaid/uncertain outcomes; pre-dispatch cancellation creates no charge; only authoritative evidence permits retry; a winning capture remains successful. | NOT RUN |
| R07 | Controlled interruption, local timeout, reload and late success, including the success-to-native-save boundary. | Original operation/line survives; recovery uses the same references; uncertain exposure prevents replacement charge or alternate tender; final verified outcome reconciles. | NOT RUN |
| R08 | Busy terminal in a second browser; two authorized cashiers and simultaneous starts/status checks. | Clear busy feedback and safe Resume; server serializes exposure; repeated observation/coalescing creates no duplicate financial operation; access revocation remains effective. | NOT RUN |
| R09 | Odoo-origin full refund and asynchronous completion. | Saved matching return/payment exists before dispatch; pending return cannot finalize; verified refund links to the original payment and paid negative order/receipt. | NOT RUN |
| R10 | Partial/repeated refunds, multiple card sources, mixed Cash/card and fractional quantity remainder (ticket 40). | Amounts, returned quantities, native totals, taxes/receipt/accounting and original tender caps agree. No extra minor unit or stranded remainder. | NOT RUN |
| R11 | Saved-return reload and historical missing-return recovery; direct API missing/mismatched draft/payment attempts. | Draft and payment identities persist; restoring uses existing evidence without another refund; invalid API calls make zero provider requests; old paid returns stay unchanged. | NOT RUN |
| R12 | Discover completed/pending external refunds in the intended account; shared-account foreign/unmatched evidence and repeated discovery. | Exact original payment/sale association; one financial record/capacity claim per provider refund; no extra refund/payment request, unrelated Odoo sale or false terminal/person attribution. | NOT RUN |
| R13 | Ticket 41: refund already issued in Revolut, products actually returned. Confirm products/quantities as manager; validate the native return. | Odoo Return links to the correct document; refund return appears in Orders with its native receipt; configured stock and applicable accounting effects occur once; zero new money requests. | NOT RUN |
| R14 | Ticket 41: refund already issued, **no products returned**. Record reason and any applicable correction document. | Explicit no-products outcome explains why there is no product return in Orders; purchase/refund and required correction links are accessible; no fake returned quantity, stock movement or second refund. | NOT RUN |
| R15 | Ticket 41: compatible existing draft/final return, incompatible association, pending-to-completed, failed native validation, reload and two managers. | Safe existing association; incompatibilities rejected; pending financial state cannot finalize; recovery/concurrency cannot duplicate money, returns, stock or accounting. | NOT RUN |
| R16 | Current and historical native sales receipt (at least a week old, closed original session, fresh browser); existing native invoice PDF; terminal transaction-history printing. | Documents are readable/printable with correct amounts/references; reprinting sends no payment/refund and creates no invoice automatically. Record real physical/PDF observations; missing invoice fixture blocks that subcase (ticket 34). | NOT RUN |
| R17 | Cashier/manager usability and keyboard access across payment, refund and recovery. | Status, Original Sale, Odoo Return or no-products outcome are understandable; no acknowledgement-only bookkeeping shortcut; controls/errors are readable and usable without weakening access checks. | NOT RUN |
| R18 | End-to-end financial and native reconciliation for every test scenario. | Original captured amounts equal completed refunds, protected active reservations and approved retained balances; Cash/base/tip shares and native quantities/documents agree; no duplicates or unexplained exposure. | NOT RUN |

For R10's exact rounding regression, retain a **mocked/disposable** untaxed
1,234-minor-unit fixture: return 0.25 then 0.75, expecting 309 then 925.
Also cover reversed/multiple partitions and mixed tenders in automated tests.
This example does not authorize a £12.34 live charge. Any device amount must
use the separately agreed budget and supported fractional-quantity fixture.

For R14, the existing externally detected refund linked to sale 000018 is a
possible inspection fixture because the operator reported no products need
returning. Reconfirm its current state and manager intent before any native
correction; never use it to fabricate a product return or send another refund.
R13 requires a separate fixture with genuinely confirmed returned products.

## 4. Check the release and public distribution

- [ ] Test fresh installation from the packaged addon using public instructions and a clean environment, without private checkout paths, undocumented infrastructure or credentials bundled in the artifact. Verify upgrade prerequisites and supported Odoo/Restaurant packaging against the final candidate.
- [ ] Verify complete operator/admin guidance: configuration and grants, server-only secrets/rotation, payment recovery, both refund origins/dispositions, printing, reconciliation, upgrades and troubleshooting. Reflect actual observations and compatibility limits.
- [ ] Verify the chosen license text, addon metadata and applicable third-party attribution/notices are included and consistent in the intended public distribution. Record missing files/decisions; do not silently select or change the license.
- [ ] Resolve [ticket 33](../tickets/needs-info/33-investigate-release-evidence-disclosure.md)'s private preservation, accountable custodian, mapping and recovery requirements before publishing evidence. Keep the old test history; use consistent aliases in public copies and retain authoritative originals privately.
- [ ] Review the **actual intended public artifact, documentation, screenshots, logs and selected Git history** for secrets, card/customer data and original transaction/device/local identifiers. Record the reviewed publication route; current-file cleanup alone does not establish clean history. Any required publication/history operation needs its own approved plan.
- [ ] Record final test-money disposition, unresolved issues/limitations, reviewed revision/artifact and owner go/no-go decision. Ticket 12 closes only when mandatory release and publication gaps are resolved; publication itself is a separate authorized action.

## 5. Record results without overwriting earlier evidence

Create a dated final-candidate section in the existing evidence record when
execution resumes. For every ID/subcase record: revision/environment, operator,
authorization, amount/currency, UTC observations, expected versus actual outcome,
stable restricted evidence links/aliases, intended versus actual mutation count,
native order/return/stock/accounting result, and PASS/FAIL/BLOCKED/NOT REPRODUCIBLE.
Pending refunds remain pending, with an owner and next reconciliation step.
Never declare a delayed or unavailable check passed.

Keep originals and authoritative mappings in the approved private archive;
public copies must follow ticket 33. Earlier local temporary screenshot/log paths
are not proof of durable preservation. New test outcomes must remain traceable
without copying secrets or raw customer/card data into this checklist.

**Checklist preparation is complete; execution is not started.** This update
does not run tests, change live financial/native records, deploy, make the
repository public, redact historical evidence or close other tickets.

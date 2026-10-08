# Ticket 12 — Final release and open-source checklist

Fresh campaign requested by the owner on **2026-10-07**: retest the complete
integration from scratch on a dedicated register, including implementation
through tickets 42–46. This supersedes the 2026-10-05 preparation scope without
erasing its historical evidence. Parent: [ticket 12](../tickets/ready-for-human/12-live-terminal-release-evidence.md).

All checks started **NOT RUN for this campaign**. Automated A01–A10 acceptance
completed on 2026-10-08; live R01–R24 remain NOT RUN. The
[guided retest](ticket-12-fresh-retest-2026-10-08.md) records the frozen final
candidate, commands, counts, logs and the exact source-equivalence basis for
carried-forward broader results after a test-only restart-verifier correction.
Earlier [release evidence](ticket-12-release-evidence.md),
[operator observations](ticket-12-operator-observations.md) and
[refund-screen verification](refund-screen-clarity.md) retain their original
dates/revisions. Record every subcase separately; an earlier pass or a broad
row with one successful subcase is not current acceptance.

## 0. Establish a clean campaign without deleting history

- [ ] Use **Revolut Acceptance — 2026-10-07**, verify the intended GBP currency, journals/pricelist, Cash and configured Revolut method, automatic verified checkout and explicitly approved register users. Record config/session identifiers and opening cash. No sample orders or copied financial history.
- [ ] Confirm zero campaign sales, returns and payment attempts before R01. Save backend filters for this register/session and maintain a restricted scenario-to-reference ledger. Keep old registers, orders, refunds and audit records unchanged.
- [ ] Check shared-terminal/account exposure independently. Reusing the existing configured payment method keeps server-only credentials and shared terminal serialization; a new name does not create a sandbox or eliminate old exposure.
- [ ] Prepare distinct small retail, split-tender, tip, discounted, globally rounded, fractional-quantity, tracked-product and invoiced fixtures. Reuse each new sale only for its planned refund partition; record remaining entitlement before the next refund.
- [ ] Schedule separate reconciled configuration phases for retail, Restaurant, cash rounding and restricted pricing, or use separate test registers. Record floor/table, presets, tip product, rounding rule, grants and stock/accounting prerequisites; missing setup is BLOCKED, not a waived test.
- [ ] Keep destructive recovery, worker-crash, forged-request and exact-cent fixtures in disposable automated databases. Historical print checks are read-only against identified older records; the new register alone cannot supply week-old history.

## 1. Freeze the candidate and prepare the test session

- [ ] Confirm reviewed tickets 40–46 and the observation/frontend/upgrade-runner refactors are included. Preparation baseline: `bfc100b840fd11c2ff761022d741623622600a83`, addon `19.0.1.18.1`; select and freeze the actual final candidate. Record any later fixes and affected retests.
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
| A01 | Full addon fresh installation and upgrade on pinned Odoo; native retail and Restaurant browser tours actually execute. Check consolidated-addon migration and preservation of older operation records. | PASS — 2026-10-08; provenance in guided retest |
| A02 | POS lifecycle, decline/failure/cancellation (including cancellation before dispatch), timeout/reload/late success, busy-terminal recovery, status coalescing and restart recovery. Assert intended dispatch counts and original identity reuse. | PASS — 2026-10-08; provenance in guided retest |
| A03 | Public server/API settlement, bounded snapshot/allocation processing and credential/company/register authority. Missing/mismatched saved return or payment line, unauthorized access and excess/invalid allocations reject before Merchant HTTP. Credentials are absent from POS payloads/browser logs. | PASS — 2026-10-08; provenance in guided retest |
| A04 | Native full/partial/mixed/multiple-tender returns; ticket 40 rounding and reservation/recovery/history regressions; ticket 41 goods/no-goods/existing-return/pending/concurrent-manager regressions with actual native stock/accounting output and zero new financial POSTs for issued refunds. | PASS — 2026-10-08; provenance in guided retest |
| A05 | Deployment preflight/financial/PDF guards, migration checks and exact packaged-artifact retail and upgrade acceptance. Failure leaves the active release and financial records intact. Inspect the delivered artifact, not only the checkout. | PASS — 2026-10-08; provenance in guided retest |
| A06 | Tickets 42–43: nonmutating source/display previews; saved native reservation/freezing; lost-draft recovery including sibling identity, session rollover, uncertain siblings and reconstruction rollback; atomic external association batches and deterministic locking. Use independent PostgreSQL transactions for reservation/discovery/association, finalization/status and recovery/closure races; assert conserved quantities/cents and exactly-once effects. | PASS — 2026-10-08; provenance in guided retest |
| A07 | Ticket 44: terminate the original worker before financial dispatch claim, then recover/cancel through the cashier flow; race a delayed worker and simultaneous recovery. Claims with ambiguous outcomes stay protected. Test before/after order and intent claims, no replay, terminal release and session closure. | PASS — 2026-10-08; provenance in guided retest |
| A08 | Ticket 45: independently reproduce negative-price/negative-quantity adjustments and global rounding with tiny positive lines; full/partial/reordered returns, zero-value adjustment reversals, mixed tenders, tips and earlier frozen claims. Check source selection through native stock/accounting and external association; original history stays unchanged. | PASS — 2026-10-08; provenance in guided retest |
| A09 | Ticket 46 and frontend recovery: rejected/timed-out/offline canonical loading after verified sale AND refund; double clicks, late responses, cancellation, reload and partial tenders. Verified evidence stays locked until restoration; native busy flag clears, Check status is read-only, no premature checkout/duplicate receipt/new dispatch. | PASS — 2026-10-08; provenance in guided retest |
| A10 | Observation and runner regressions: competing tabs plus cron, expired lease holder, held report, phase budgets and Retry-After; credential recheck and no repeated cancellation POST. Execute all seven historical upgrade scenarios and shared-runner failure/signal/cleanup/project-lock tests, retaining scenario-specific history assertions. | PASS — 2026-10-08; provenance in guided retest |

Existing entry points include `scripts/test-addon --verify-install-upgrade`,
the Node suite at `addons/pos_revolut/static/tests/revolut_payment_state.test.mjs`,
the repository Python tests and the focused restart/deployment/authority upgrade
scripts. Exact artifact checks use `scripts/test-delivered-addon --revision
<full-candidate-SHA> --scenario retail` and the migration scenario with
`--migration-from <full-reviewed-legacy-SHA>`. Select a genuine legacy fixture
and follow [installation/testing guidance](../installation.md); do not invent
a migration baseline or accept browser skips as passes.

### Automated execution inventory

Run from the frozen source with fresh disposable databases and unique project
names. Run browser/Odoo suites serially to avoid Chrome resource contention.
Keep logs in durable restricted storage rather than relying on `/tmp` alone.

- `scripts/test-addon --verify-install-upgrade` — complete install and current-version upgrade; browser tours must actually execute.
- `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` and `python3 -m unittest discover -s tests -p 'test*.py'` — record individual pass/skip counts; run the three Odoo-dependent PDF probes in their supported runtime.
- `scripts/test-restart-recovery` and `scripts/test-deployment-guard` — interruption persistence and deployment refusal behavior.
- `scripts/test-historical-upgrade <scenario>` for **cart-authority, credential-authority, register-access, receipt-retirement, return-rounding, external-native, evidence-retirement** — execute each historical seed/upgrade/verify path; the ordinary current-version upgrade does not replace these.
- Both `scripts/test-delivered-addon` scenarios described above — record artifact hash and real legacy baseline.
- Confirm the full suite includes the targeted allocation/concurrency, discounted/rounded, unclaimed-reservation and native checkout-restoration tests mapped by A06–A10. Run a focused suite if a case is absent or skipped; retain actual assertions for money, identity, stock/accounting and dispatch counts.

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
| R02 | Full retail card payment. | Terminal amount/currency match; only verified successful underlying payment completes the order automatically; Orders, receipt and references agree. | PARTIAL — granted-cashier £0.01 zero-tip checkout reported successful on 19.0.1.18.4; receipt, verified/Paid native payment and post-refresh persistence confirmed. Exact timing and separately reported terminal amount/currency remain unrecorded; see [release evidence](ticket-12-release-evidence.md). |
| R03 | Cash/card split and two or more card allocations. | Each request uses its allocation; partial payment keeps the order open; only the full verified balance closes it; references and original tender shares remain distinct. | PARTIAL — £0.02 Cash/Revolut split reported successful, receipt and native £0.01/£0.01 shares verified. Intermediate unpaid screen not separately captured. Live two-card subcase blocked on first-allocation amount entry before native automatic dispatch; see [release evidence](ticket-12-release-evidence.md). |
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
| R19 | Authorized cart and pricing: unrestricted cashier price, per-line discount, restricted override requiring authenticated manager approval, stale cart/version, attempted edits after exposure and terminal tip versus base allocation. | Supported prices work; rejected/stale carts require review before dispatch; browser role/PIN or altered totals cannot confer authority; tips do not pay the goods balance. Forge requests only in disposable automated fixtures. | NOT RUN |
| R20 | Ticket 44 recovery: interrupted reservation before terminal dispatch, using the safe Cancel/recovery action; ordinary provider cancellation after timeout. | Original identity retained; durable unclaimed evidence allows safe release; claimed/uncertain requests remain protected; no repeated order/intent dispatch. Worker termination and precise claim races belong to A07, not uncontrolled staging process kills. | NOT RUN |
| R21 | Ticket 45 discounted and globally rounded sales returned fully and in partitions, including tiny-line and zero-value adjustment cases. | Every eligible return is usable; total refunds equal the original collected entitlement, with no negative capacity, extra cent or stranded remainder; native quantities/tax/accounting agree. Exact larger-value regressions use mocked fixtures. | NOT RUN |
| R22 | Ticket 46 verified payment AND refund followed by rejected, timed-out or offline checkout restoration; repeat Check status, double click and reload. | Busy state clears, original verified references survive, checkout remains blocked until canonical totals restore, and the same sale/return completes once without a new charge/refund. Precise fault injection is mandatory in A09; only supported controlled browser interruption on staging. | NOT RUN |
| R23 | Tickets 42–43 lost-draft recovery and external association: multiple verified siblings, partial/pending sibling, session rollover, incompatible batch, two managers and tracked lots. | Only complete compatible evidence rebuilds/binds the original return; no invented cash/lot data, partial batch or duplicate financial/native effect. Destructive missing-draft and concurrency setup use disposable tests; staging uses genuine eligible fixtures. | NOT RUN |
| R24 | Close and reopen the new register/session after reconciliation; repeat ordinary checkout setup. | Unresolved or verified-but-unsettled exposure blocks closure; reconciled closure has correct cash/card/accounting totals; next session starts clean without losing previous campaign evidence. No force-closing protected sessions. | NOT RUN |

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

### Operator execution order and result ledger

Run R01 first, then ordinary retail/split checkout (R02–R03), authorized pricing
and tips (R19/R05), supported failure/recovery cases (R06–R08/R20/R22), native
returns (R09–R11/R21), external dispositions/association (R12–R15/R23), and
Restaurant in its configured phase (R04). Printing/usability (R16–R17) span
these phases. Reconcile after each financial case and finish with R18/R24.
The live amount/cumulative budget must be agreed before starting R02 or any
other money-moving case.

For each row, expand every listed subcase into the ledger before execution:

| Campaign / case / subcase | Candidate / deployed revision / environment | Register / session / restricted fixture alias | Expected money requests and native effects | Observed result / amounts / references | Evidence / owner / next action |
| --- | --- | --- | --- | --- | --- |
| 2026-10-07 / awaiting execution | NOT VERIFIED | Dedicated register setup recorded in ticket 12 | Define before each case | NOT RUN | Record durable restricted evidence |

Use PASS, FAIL, BLOCKED or NOT REPRODUCIBLE per subcase; a mandatory gap remains
open. Automated proof and physical observations are separate columns/entries,
not interchangeable passes. No runtime change may silently retain all previous
campaign results: record the new candidate and rerun affected cases.

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

**Automated acceptance completed on 2026-10-08; live scenarios remain NOT RUN.**
The dated guided retest records actual automated results. Register setup is
recorded separately in ticket 12. No live payment/refund tests, deployment,
publication, historical redaction or closure of other tickets is claimed.

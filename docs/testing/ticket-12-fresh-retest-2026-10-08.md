# Ticket 12 — Guided fresh retest, 2026-10-08

Use this guide to execute the [fresh campaign checklist](ticket-12-final-release-checklist.md)
one phase at a time. The checklist remains the complete acceptance matrix;
record every subcase separately. Previous campaigns remain historical evidence.
Ticket 12 stays open until its financial, device, native-document and publication
gates are satisfied.

## Current financial authorization

On 2026-10-08 the owner approved a maximum **£0.25** budget and said not all
tests need to be refunded. Treat this conservatively as the aggregate gross
card-charge cap for the new campaign, not a per-test amount or a net amount
after refunds. Refunds do not replenish the cap. No new campaign card charge
has been made in this session; operator-at-terminal availability remains
unconfirmed.

Prefer £0.01 card allocations where the configured fixture supports them.
Plan larger partial/rounding/tip fixtures within the remaining cap before
dispatch. Count a pending or uncertain attempt against the available budget
until its outcome is definitive; include any terminal tip in the gross amount.
Record retained charges and their approved disposition in final reconciliation.
A fixture needing more than the remaining budget is BLOCKED, not permission
to exceed the cap or to waive that scenario.

## Candidate and automated checkpoint

- Final frozen candidate: `693937ee3b7a78991a33cc714e0d47a4c70c3663`.
- Full-suite baseline: `8adc68f255e4ea1830831f571e22f5b3f41875e4` (current `main` at campaign start).
- Addon: `19.0.1.18.1`; pinned Odoo: `19.0.20260908`.
- Final single-addon Git archive SHA-256: `8c06d9653970add7d3c1adc8235249df7d8587e7504c70e2793e6cb31ae45102`.
- Original baseline archive SHA-256: `c21d5daa92542a5b78daa9b6748732e56dca7dc59da792dbe5c02b2855c32b8f`.
- Genuine two-addon migration baseline: `30492a67020acdfe34d7f560a9cf6d7fb20f6430`, previously exercised in [consolidation verification](single-addon-consolidation.md).
- Local logs and frozen archive: `build/ticket12-2026-10-08/` (ignored by Git).
  These are local working copies; permanent restricted preservation and its
  custodian remain ticket 33 work.
- No deployment or live financial action is part of these automated checks.

| Check | Fresh result | Local log |
| --- | --- | --- |
| POS lifecycle | PASS: 107 tests, zero failures or skips | `pos-lifecycle.log` |
| Python tooling | PASS across runtimes: 54 local passes; three local PDF skips executed successfully in Odoo below | `tooling.log`, `pdf-probes.log` |
| Full fresh install, including native browser tours | PASS on baseline: 597 tests reported, zero failures/errors; employee case covered by the separate profile below | `install-upgrade.log` |
| Full current-version upgrade, including native browser tours | PASS on baseline: 597 tests reported, zero failures/errors; runner exit 0 | `install-upgrade.log` |
| Supported-runtime PDF probes | PASS: all seven, including the three local skips | `pdf-probes.log` |
| Employee-enabled shared-register authorization | PASS: 46 tests, zero failures/errors; employee-list case actually executed | `employee-access.log` |
| Three-process restart recovery | PASS on final candidate: original authority/references, zero/nonzero tips once, no new financial POSTs; exit 0. Original baseline FAIL retained. | `restart.log`, `restart-corrected.log`, `restart-final.log` |
| Deployment financial guards | PASS: actual disposable payment/refund/external-evidence blockers clear only after settlement | `deployment-guard.log` |
| Seven real historical upgrades | PASS: all seven seed/upgrade/preservation checks, exit 0 | `historical-<scenario>.log` |
| Exact delivered artifact: retail | PASS on final candidate: 16 tests, zero failures/errors, exit 0 | `artifact-retail-final.log` |
| Exact delivered artifact: legacy retail and Restaurant migration | PASS on final candidate: four groups of 16 tests, zero failures/errors, exit 0 | `artifact-migration-final.log` |

### Restart correction and carried-forward evidence

The original three-process check failed because it compared the entire fresh
provider response with cached responses. Ticket 38 explicitly defines
`observation_fresh` as specific to the completing RPC: fresh `true`, cached
`false`. The corrected verifier asserts that distinction and exact equality
for every other field. Exact zero/nonzero tips, original references, native
projection, five GETs/no POSTs and two dispatch claims remain strict. Both
independent reviews accepted the correction; the original failure is retained.

Only `addons/pos_revolut/tests/restart_verify.py` differs between the baseline
and final candidate. Production addon files, ordinary Odoo/Node/Python tests,
Docker configuration and runtime runners are byte-for-byte unchanged. The
fixture is executed by the dedicated restart runner, not imported by the
normal addon suite. Full-suite, lifecycle, tooling/PDF, employee, deployment
guard and historical results therefore carry forward with this explained
scope. The affected restart and both packaged-artifact checks are run on the
final candidate separately; no new 597-test run on that SHA is claimed.

The source comparison used:

```bash
git diff --exit-code 8adc68f255e4ea1830831f571e22f5b3f41875e4 \
  693937ee3b7a78991a33cc714e0d47a4c70c3663 -- addons scripts tests docker compose.yaml \
  ':(exclude)addons/pos_revolut/tests/restart_verify.py'
```

Result-bearing documentation is committed after testing; the frozen addon
candidate and its archive remain the identities above.

Automated acceptance A01–A10 is complete with this provenance. Standards and
Spec review found no remaining findings. All live R01–R24 results remain NOT
RUN, deployed-source/device readiness is unverified, and tickets 33/34 retain
their separate release gates. No live charge, refund or deployment occurred.

Automated Merchant calls are mocked. The disposable runtime uses an internal
network and verifies its unmocked-Merchant-HTTP blocker. A successful build,
Node suite or mocked suite does not establish physical-device acceptance.
Do not mark A01–A10 passed until their relevant runtime assertions actually run.

## 1. Automated tests first

The agent runs these checks; the operator does not need to repeat a completed
check on the same frozen candidate. Run from this repository. Keep browser
suites serial, use fresh disposable databases, and retain each exit status,
test count and skipped case with its log. Stop progression into live acceptance
if there is a failure or a required skipped test.

```bash
node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs
python3 -m unittest discover -s tests -p 'test*.py'
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-t12-20261008-full \
  scripts/test-addon --verify-install-upgrade
scripts/test-restart-recovery
scripts/test-deployment-guard
```

The full baseline execution mounted its frozen Git export with `--addons-dir
build/ticket12-2026-10-08/addons`; the final export is under
`build/ticket12-2026-10-08/final/addons`. Without that flag, the runner tests the current
checkout; confirm it matches the chosen candidate before using the commands.
The full Odoo suite includes permissions, public server boundaries, mocked
payment/refund finality, real PostgreSQL concurrency, stock/accounting and
native retail/Restaurant recovery tours, including tickets 42–46. Check the
summary and browser-skip diagnostics rather than assuming an earlier count.

Run the three skipped PDF checks inside the pinned Odoo image, mounting this
repository read-only so `tests/test_pdf_probe.py` can load the deployment
probe from `scripts/deploy-addon-remote`:

```bash
docker compose --project-name odoo-revolut-t12-20261008-pdf run --rm --no-deps \
  --volume "$PWD:/opt/revolut-repository:ro" \
  --workdir /opt/revolut-repository --entrypoint python3 odoo \
  -m unittest discover -s tests -p test_pdf_probe.py -v
docker compose --project-name odoo-revolut-t12-20261008-pdf down --volumes --remove-orphans
```

Run the employee-enabled authorization profile separately, using a new
disposable project. The full suite can skip its employee-list case when
`pos_hr` is absent; native employee/PIN selection must not bypass backend-user
grants. Build/verify the pinned image and Merchant blocker first, as in the full
runner, then execute:

```bash
docker compose --project-name odoo-revolut-t12-20261008-employees up --detach --wait db
docker compose --project-name odoo-revolut-t12-20261008-employees run --rm odoo \
  --database ticket12_employee_access --stop-after-init --workers 0 --max-cron-threads 0 \
  --log-level warn --log-handler odoo.tests.result:INFO --init pos_revolut,pos_hr \
  --test-tags /pos_revolut:TestSharedPosSessionAccess,/pos_revolut:TestRevolutRegisterRefund,/pos_revolut:TestRevolutRegisterWorklists
docker compose --project-name odoo-revolut-t12-20261008-employees down --volumes --remove-orphans
```

Then execute all seven scenarios. Each runner installs its real historical
revision, seeds history, upgrades to the current candidate and verifies
preservation across separate Odoo processes. A same-version module update
does not replace these checks.

```bash
scripts/test-historical-upgrade cart-authority
scripts/test-historical-upgrade credential-authority
scripts/test-historical-upgrade register-access
scripts/test-historical-upgrade receipt-retirement
scripts/test-historical-upgrade return-rounding
scripts/test-historical-upgrade external-native
scripts/test-historical-upgrade evidence-retirement
```

Finally test what will actually be delivered:

```bash
scripts/test-delivered-addon \
  --revision 693937ee3b7a78991a33cc714e0d47a4c70c3663 --scenario retail
scripts/test-delivered-addon \
  --revision 693937ee3b7a78991a33cc714e0d47a4c70c3663 --scenario migration \
  --migration-from 30492a67020acdfe34d7f560a9cf6d7fb20f6430
```

## 2. Verify staging and the register before using the terminal

Begin only after reviewing the automated results. Verify the deployed source
and checksum match the tested candidate using the [staging runbook](../staging-deployment.md).
If they differ, record the difference and complete the authorized upgrade and
its checks before accepting live results. Record the current device/account,
Merchant environment, location, currency, terminal eligibility and Pay at
Counter setup. Use the current £0.25 authorization above, plan each allocation
within its remaining cap, and confirm the operator is at the terminal before
financial tests. Earlier campaign budgets remain historical.

Start **R01** in **Revolut Acceptance — 2026-10-07**:

1. Open Point of Sale and select this register's **Continue Selling**.
2. Confirm GBP, the configured Revolut method and dedicated Cash method, the
   expected product category, retail mode and automatic terminal checkout.
3. In the backend, filter Orders and Sessions to this register. Record its
   current session and opening cash privately. Verify there are no completed
   campaign sales, returns or attempts; an empty ongoing ticket is expected.
4. Reload POS. It must reopen the same session and preserve its state.
5. Test explicitly granted users and an ungranted user in separate browser
   sessions. Yesterday's setup granted only Administrator; a real colleague
   or negative permission case needs its own recorded user setup. A shared
   employee PIN does not grant a backend user register access.
6. Complete one agreed small **Cash** sale. Verify the native receipt and
   backend paid order, correct currency/total and no new Revolut operation or
   terminal interaction. Account for this sale's cash in the campaign ledger.

Report the session, access-case results, Cash total, receipt/order outcome and
whether the terminal stayed idle. Keep raw identifiers in the private ledger.
Shared-terminal exposure must be checked separately from this new register.

## 3. Ordinary retail payments

Execute **R02**, then every **R03** subcase with separately agreed amounts:

1. Make a new simple sale. Choose Revolut and compare the terminal amount and
   currency with the selected payment line before presenting the card.
2. Complete the card payment. Odoo must automatically reach the receipt only
   after underlying-payment verification. Compare POS, backend paid order,
   native receipt and Merchant outcome; retain the original references privately.
3. Make a Cash/Revolut split sale. The terminal must receive only the card
   allocation. The order must remain open while its balance is unpaid.
4. Make a sale with two distinct Revolut payment allocations. After the first,
   the remainder stays due; after the last verified allocation, checkout occurs
   once. Record each source and remaining refund entitlement separately.

Reconcile after each case. Reserve new sales as fixtures for the planned full,
partial and mixed-tender refunds; do not refund historical sales again.

## 4. Pricing, tips, failure and recovery

Prepare each configuration phase with a reconciled/closed session or a separate
test register. The initial retail register has no tips, cash rounding or
restricted-price setup; missing prerequisites mean BLOCKED.

- **R19:** test allowed price/discount changes, manager approval for restricted
  overrides and stale-cart review. Changes after financial exposure must be
  guarded. Forged requests belong to the disposable automated suite.
- **R05:** with a configured GBP tip product, test accepted tip and no-tip.
  Compare base, tip and gross on the order, receipt and provider evidence.
- **R06:** use supported controlled decline, failure and cancellation methods,
  including cancellation during preparation. The order stays unpaid or guarded;
  retry is available only when the previous outcome is definitively safe.
- **R07/R20/R22:** use supported browser interruption/reload and status recovery.
  Preserve the original payment/refund identity; Check status must not send a
  replacement charge/refund. Verified evidence remains protected until canonical
  checkout restores. Exact worker kills and injected RPC failures run in A07/A09.
- **R08:** use two authorized browsers for busy-terminal feedback, competing
  starts and status checks. Record clear recovery and exactly one financial
  operation; do not resolve uncertainty by forcing another payment method.

Expand all listed subcases in the matrix. An unsupported device failure or race
is NOT REPRODUCIBLE with a reason and follow-up, not a pass inferred from mocks.

## 5. Odoo refunds and conservation

As a POS manager, use **Orders → original sale → Refund**, select the intended
products/quantities and choose the original tender. The addon saves the matching
return/payment before requesting a Revolut refund. Record both the provider
refund outcome and native return outcome; they are separate checks.

- **R09:** full refund, including pending-to-verified progression. Pending
  evidence cannot validate the return; the verified result links to the original
  payment and one paid negative order with a native receipt.
- **R10:** partial/repeated refunds, multiple card sources, Cash/card shares
  and fractional quantities. Check remaining entitlement before every partition.
- **R11:** reload the saved return and resume with existing references. Use
  genuine eligible missing-return fixtures for restoration; forced deletions and
  mismatched public requests stay in disposable tests.
- **R21:** discounted and rounded fixtures, partition order, tiny positive
  lines and zero-value adjustments. Compare collected total, refunds, taxes,
  quantities and actual native stock/accounting. The exact 309/925-cent fixture
  is automated; it does not authorize a £12.34 device charge.

If a refund is pending or uncertain, retain its allocation and use Check status.
Do not repeat the reimbursement to obtain a nicer receipt. Customer funds
arrival and the provider's final refund state need separate observations.

## 6. Refunds already issued in Revolut

Use separate agreed fixtures for **R12–R15/R23**. First discover/reconcile the
external refund in the manager worklist; verify exact original-sale association,
one record per provider refund and remaining capacity. Discovery and native
completion must send zero new financial requests.

Open **Point of Sale → Revolut Refunds → Complete native work**:

- Products returned: confirm actual products, quantities and any tracked lots;
  review the native draft, then validate the confirmed return. Check Orders,
  receipt, stock and accounting once.
- No products returned: record the actual reason, prepare/review the appropriate
  native accounting correction, post it through the normal accounting workflow,
  then select it to complete reconciliation. Verify there is no invented goods
  return or stock movement.
- Existing return: select the compatible return and every external refund's exact
  payment allocation. Test incompatibility rejection and all-or-nothing binding.
- Pending, failed validation, reload and two-manager cases: preserve references,
  safely continue existing work and verify no duplicated return, stock effect,
  correction or reimbursement. Destructive sibling/rollover/concurrency fixtures
  are mandatory automated coverage; staging uses genuinely eligible records.

An unfamiliar external refund amount does not establish which goods were
returned or who/device initiated it. Reconfirm any historical inspection
fixture before native financial work; never issue another refund for it.

## 7. Restaurant, printing and usability

Configure the Restaurant phase before **R04**. Record floor/table, dine-in and
takeaway presets, grants and tip setup. Exercise table checkout, supported
split/merge/transfer, and unchanged partly paid recovery. Unsafe changes must
be explained and guarded; final verified balance still triggers one checkout.

Throughout the campaign, execute **R16/R17**:

- Print a current and at-least-week-old native POS receipt, including a closed
  original session from a fresh browser. Use older records read-only.
- Download and physically check an existing native invoice PDF for ticket 34.
  A missing invoice fixture blocks that subcase; automatic invoicing is not required.
- Check terminal transaction-history printing separately. Reprinting must not
  charge, refund or automatically create an invoice.
- Navigate the actual payment, refund and recovery controls with the keyboard.
  Check readable amounts/errors and understandable Original Sale, Odoo Return
  or no-products outcomes, under the intended cashier/manager permissions.

## 8. Reconcile and close the campaign

For **R18**, reconcile every new sale and return against original provider and
Odoo sources, including Cash, base/tip shares, completed refunds, protected
pending allocations and approved retained amounts. Confirm original identities,
native quantities/documents, no duplicate movement and no unexplained exposure.

For **R24**, test protected-session closure refusal using the controlled fixtures,
then close the fully reconciled dedicated session normally. Verify cash/card
totals and native accounting. Reopen and confirm clean new-session checkout
without losing the previous campaign's records. Never force-close uncertainty.

Finish operating/configuration instructions from observations, native PDF
acceptance (34) and private preservation/publication review (33). Record the
owner's release/publication decision separately. No automated or narrow live
pass closes these outstanding gates.

Use the checklist's publication section to review the actual intended public
artifact, documents, screenshots, logs and selected Git history. Verify license
text and third-party notices, and confirm the private archive's custodian,
reference mapping and recovery before publishing anything.

For every subcase retain: candidate and deployed source, setup, expected and
actual amount/state, Odoo/native/provider outcomes, dispatch counts where
observable, private reference mapping, and **PASS / FAIL / BLOCKED / NOT
REPRODUCIBLE / NOT RUN**. Do not collapse partial cases into a whole-row pass.

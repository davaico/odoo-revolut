# Ticket 27 implementation verification

2026-10-01. Local remediation evidence for the server-authorized base cart and terminal-selected tip contract. The live POS was not changed, exercised or deployed to.

## Revision and environment

- Reviewed design/runtime baseline: `719bae93390c3a326673af2d0e6b89aea0a84b65`.
- Initial runtime candidate: `b25082d5cdc3030ffe1acf7e1ecf463f0b59bd70`; review repairs: `4397ac1af5aebb1739a0c2790887d5277ec6af8e`; final tested runtime: `88c88a5da9636d644bd66048ce654efa31fd53c8`.
- Addon Git trees at that revision: `pos_revolut` = `d649d6812d554794c59d14c032b17e2060e26014`; `pos_revolut_restaurant` = `c468b70473ae1d5da927780c6b8a12a7a2e2fb3d`. Later ticket/evidence changes must retain these trees.
- Addon version: `19.0.1.9.0`; Odoo Community package `19.0.20260908`, repository Chrome 153 test image and pinned PostgreSQL 16.14 image.
- Final combined-run test image, as recorded by its build log: `sha256:168d539cb321c3b7f54821d0a8cca2ff077c77786f9f2bffe66d58a72ff2e952`. Earlier focused checks used the same pinned Odoo/Chrome Dockerfile; the prior inspected image was `sha256:ceea43280375efa7d2aae189fbbb24df7db5cbecfda52b0a0c2fb970744a6898`.
- The native-source extraction used for pricing/UI inspection is `/tmp/ticket27-odoo-source.tar`, SHA-256 `86bd4b041e11f3b4a4b439d1e01e0453924e7c05097cadba9c8ca76482c39780`.
- All Docker checks use disposable databases, the internal Compose network, test-only secret values, mocked provider HTTP and the Merchant HTTP guard. No automated test contacts a terminal or real Merchant API.
- The implementation inspection used the official versioned Merchant OpenAPI at `https://developer.revolut.com/docs/api/merchant/2026-08-17.yaml`, downloaded again on 2026-10-01: SHA-256 `36ca61bf2714a60a8d27ea22ad80e94d55f3698fe613ddecf81ebe17992be743`. This later download differs from ticket 26's recorded September 30 snapshot (`09d3403087c53c97b00abe2cf6708e6bc8df0d5708683b9351b5ba38f5bd6b88`). The report implementation uses the documented asynchronous report-run and authenticated CSV fields; it does not assume an undocumented synchronous tip property.

## Implemented boundaries

Preparation prices a saved native draft with server-permitted native pricing, taxes, fiscal position, attributes, combos and discounts. Restricted price deviations require an authenticated POS manager's approval of the exact immutable cart version. The public start RPC requires that version and tender revision, matches the named payment slot and reserves its base under the shared durable order lock before either financial POST. Verified and uncertain base allocations remain consumed; a refund cannot create new sale capacity.

The captured payment alone cannot complete an authorized sale. Explicit authenticated report evidence, including numeric zero tip, must match the payment, order, currency and location. Missing, late, interrupted or expired reports retain the original operation and base reservation. Only checked report evidence projects one aggregate native tip line and gross tender. The original product, tax policy, rounding and precision stay attached to the authority; incompatible reconfiguration blocks reconciliation or another allocation until restored.

Native settlement independently checks the frozen base, projected tip, gross tender and operation proof. Full and partial returns reserve original base and tip separately, preserve exact collected rounding, and produce gross receipts and credit notes. Historic operations retain their references and legacy refund behavior without invented authorization or tip evidence.

## Focused regression evidence

These bounded checks preceded the final combined suite. Counts are individual runs, not a summed coverage claim.

| Command / check | Result and local log |
| --- | --- |
| `scripts/test-addon --test-tags '/pos_revolut:TestRevolutCartPricing,/pos_revolut:TestRevolutPayment,/pos_revolut:TestRevolutConcurrentStart,/pos_revolut:TestRevolutOrderSettlement,/pos_revolut:TestRevolutAuthorization,/pos_revolut:TestRevolutRetryConcurrency,/pos_revolut:TestRevolutRecoveryBatches,/pos_revolut:TestRevolutReconciliation'` | 137 tests, zero failures/errors; `/tmp/ticket27-regressions-green.log`. Native pricing parity plus existing payment and settlement behavior. |
| Authority/rounding class | 17 tests, zero failures/errors; `/tmp/ticket27-rounding-authority.log`. Direct old RPC, missing/forged/stale/foreign authority, bounded tender input, cash corrections, sequential cards, explicit zero and global rounding. |
| Report plus independent-cursor concurrency classes | 27 tests, zero failures/errors; `/tmp/ticket27-report-final3.log`. Report bounds/identity/expiry, zero- and three-decimal currencies, nine allocation/report/approval/settlement/session/cash races. |
| Tip refund plus legacy refund, receipt and refund concurrency classes | 71 tests, zero failures/errors; `/tmp/ticket27-refund-final-71.log`. Explicit base/tip component capacities and posted 10.03 sale invoice/full-return credit note. |
| Pricing plus frozen tip-policy classes | 36 tests, zero failures/errors; `/tmp/ticket27-frozen-tip3.log`. Product replacement during report waiting and sequential payments retains one original tip and correct full-return decomposition; incompatible tax/precision changes remain unresolved. |
| Native nonzero-tip report/reload browser | One test passed; `/tmp/ticket27-tip-browser-green.log`. Report delay, interruption, reload, one projection, 14.34 gross tender/printable receipt, one operation, two financial POSTs and one report POST. |
| Native invalid-cart correction/reload browser | One test passed; `/tmp/ticket27-snapshot-native.log`. No dispatch on rejection/read-only checks, original identities retained, one explicit corrected start and verified checkout. |
| Native unsaved globally rounded full return browser | One test passed; `/tmp/ticket27-rounded-return-green.log`. Original goods 10.02, approved base 10.00 and collected tip 0.03; explicit full return refunds exactly 1003 minor units with one refund POST and automatically completes a -10.03 native receipt and zero due. |
| `scripts/test-cart-authority-upgrade` | Passed; `/tmp/ticket27-history-upgrade.log`. Actual old-runtime upgrade, six history classes, immutable references, no invented authority/tip proof or HTTP during upgrade, legacy receipts/refunds and explicit safe retry. |
| `scripts/test-restart-recovery` | Passed across three processes; `/tmp/ticket27-three-process-restart.log`. Two zero/nonzero-tip carts, pending capture/report persistence, frozen edits/allocation rejection, original references and once-only projection, no financial replay. |
| Restaurant table ownership direct mutation | One test passed; `/tmp/ticket27-restaurant-authority.log`. Same-configuration table move allowed; foreign-configuration move rejected and rolled back without provider requests. |
| Fresh Restaurant tagged suite | Nine tests, zero failures/errors; `/tmp/ticket27-restaurant-fixtures.log`. Native Dine In/Takeout configuration, table ownership, merge/transfer guards, checkout and browser startup. |
| Incompatible policy before later base dispatch | One test passed; `/tmp/ticket27-later-policy2.log`. Reducing checked price precision after a verified partial payment rejects the remaining allocation without another operation or provider call. |
| `scripts/test-deployment-guard` | Passed; `/tmp/ticket27-deployment-guard.log`. Pending payment and refund independently block deployment; settled legacy records retain existing guard behavior. |
| `python3 -m unittest discover -s tests -v` | 29 tests passed; `/tmp/ticket27-script-tests.log`. Deployment-tool mocks only. |
| `node --test --test-isolation=none addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | 73 tests passed, none failed/cancelled/skipped; `/tmp/ticket27-node-expanded-final.log`. The default isolated wrapper also passes but reports one test file. |
| Current native receipt rendering/retry | One test passed; `/tmp/ticket27-receipt-final.log`. Explicit zero-tip report proof, rendered transaction references and no extra financial call on receipt retry. |
| Native invalid-refund correction and discovery recovery | Two tests passed; `/tmp/ticket27-refund-snapshot-green.log`. Deliberately corrupted quantity restored on the same native return, original identities retained after reload and no unverified replay. |
| Native terminal-busy recovery | Two tests passed; `/tmp/ticket27-busy-authority.log`. Busy blocker uses the public saved-cart authorization flow; read-only checks, reload and cash alternative preserve operation and provider mutation counts. |

## Committed artifact acceptance

Both commands use exact revision `88c88a5da9636d644bd66048ce654efa31fd53c8` and extracted addon archive SHA-256 `57b4d37759f3806045a7a4d6c36b885105a248e046bfb4508781b3959b004422`.

The final combined command on that revision was `ODOO_REVOLUT_TEST_PROJECT=ticket27-final-full scripts/test-addon --verify-install-upgrade`. It exited **0**: fresh installation **340 tests**, repeated module upgrade **340 tests**, and Restaurant **9 tests**, each with **0 failed, 0 errors**. Results are recorded at 10:22:48, 10:28:46 and 10:29:24 UTC in `/tmp/ticket27-final-full.log`. The upgrade run also logged three native Odoo bus/websocket exceptions about opening a read/write test cursor from a readonly one; these remain visible in the log. They did not produce test failures or test-result errors, and the native payment/reload/receipt checks completed successfully.

| Command | Result |
| --- | --- |
| `ODOO_REVOLUT_TEST_PROJECT=ticket27-delivered-retail-final scripts/test-delivered-addon --revision 88c88a5da9636d644bd66048ce654efa31fd53c8 --scenario retail` | Exit 0; retail two browser checks and nine Restaurant checks, zero failures/errors. Fresh retail has no Restaurant bridge; installing Restaurant auto-installs the delivered bridge. `/tmp/ticket27-delivered-retail-final.log`. |
| `ODOO_REVOLUT_TEST_PROJECT=ticket27-delivered-migration-final scripts/test-delivered-addon --revision 88c88a5da9636d644bd66048ce654efa31fd53c8 --scenario migration` | Exit 0; nine Restaurant checks on migration and again after update, zero failures/errors. Upgrades a base-only Restaurant installation with the bridge absent to both delivered addons installed. `/tmp/ticket27-delivered-migration-final.log`. |

An interruption stopped the first combined/artifact runners before completion. Their logs are preserved with `interrupted` suffixes and are not passing evidence. The final commands restarted from fresh disposable databases. The first completed full run at `84fe62f` found nine browser failures (340 tests, no backend errors); `/tmp/ticket27-full-regressions-red.log` retains that failing evidence. All nine received focused passing controls before the final combined rerun. These repairs include actual receipt-reference restoration after canonical refresh, explicit original-order refund fields in zero-tip mocks, and terminal-busy fixtures obtaining real saved-cart authority.

## Independent reviews

Independent Standards and Spec reviews of the initial candidate both found mutable tip-product policy; Spec also found exposed foreign-table movement, and Standards found a historical tracker paragraph presented as current. Repairs freeze the checked tip policy, validate table ownership on direct native writes and date the historical tracker narrative. Additional browser regressions exposed and repaired startup status merging and exact unsaved-return rounding. Initial delivered runs found missing native preset configuration and an undefined test mock; the fixtures were repaired and actual guard/no-mutation assertions retained. The explicit-tip return fixture now supplies the documented original-order `refunded_amount: 0`, preserving the production evidence requirement.

### Standards

Independent broader review: two actionable initial findings, both repaired. Bounded committed follow-ups on `4397ac1`, `84fe62f` and `88c88a5`: zero documented-standard violations and zero actionable Fowler smell findings. UUID comparison preserves logical payment identity across reactive wrappers. Fixture changes supply native permitted configuration and explicit provider evidence; they do not weaken validation. Server trust, idempotency and mocked-provider rules remain satisfied. Focused lifecycle checks exercise the actual risky behavior.

### Spec

Independent broader review: two actionable initial findings, both repaired. Bounded committed follow-ups: zero new actionable findings or scope creep. Frozen tip product/tax/precision policy closes contract clauses 184–187; direct table ownership closes clause 115. Startup recovery and server-derived unsaved-return totals preserve clauses 128 and 185–187. The native full-return and Restaurant regressions pass on the final candidate.

Both independent reviewers also checked the final documentation-only closure: no actionable findings. They confirmed recorded 340/340/9 results, exact archive/runtime hashes, historical/current distinctions, resolved relative links, the preserved ready-folder `.gitkeep`, and the separate integration/device gate.

## Explicit source-claim verification

The ticket-requested `codex-security:verify-fix` assessment ran independently in read-only mode against committed `88c88a5`, using the original source/control/sink boundary and focused exploit/legitimate controls. All five verdicts concern this local source revision; they do not claim deployment or physical-terminal validation.

| Source ID | Verdict | Specific boundary and proof |
| --- | --- | --- |
| `csf_0b4fc44391fd910988783f68` | **fixed** | `cart_pricing._revolut_price_cart` derives native permitted base; `cart_authorization._admit` binds exact slot/revisions and cumulative capacity before operation creation and `POST /api/orders`. Oversized/old-RPC controls make zero provider mutations; cash/card rounding controls succeed. |
| `csf_d02ef7b60758186e1139e6f3` | **fixed** | Public start takes canonical server authority rather than browser snapshot; owned creation rechecks identity. Private cursor-bound authority creation/mutation and read-only ACLs prevent client minting. Context-forgery and unbound-amount controls reject without operation or POST; ordinary cashier dispatch passes. |
| `csf_409b8b3f2ce2176b4e36c4bf` | **fixed** | Exact original draft/session/config/company/currency/table binding, immutable version and authenticated manager approval precede admission. Stale/foreign/expired/price-label-spoof paths reject; exact legitimate approval, approval/edit race and Restaurant ownership controls pass. |
| `csf_e23e164c7c609f0b17ad9500` | **fixed** | Shared updated order lock and fresh-cursor retries serialize preparation, native mutation, allocation and observation. Verified/unsafe base and other tenders stay consumed; neither tip nor refund replenishes sale capacity. Nine independent-cursor race controls assert bounded totals and POST counts. |
| `csf_56ed0a276c5e664ceff5ac60` | **fixed** | Exact base admission rejects off-cart excess. Authenticated report identity, explicit zero/nonzero tip and captured gross equality independently permit only proven tip projection under frozen policy. Changed-policy later dispatch makes no call/reservation. Native global-rounded sale/refund proves one exact 1003-minor refund and automatic -10.03 receipt. |

All local acceptance gates are complete on the final tested runtime. Subsequent closure/evidence edits change documentation only and retain both tested addon Git trees.

No configured static typechecker exists. Python compilation, changed JavaScript syntax, whitespace and local document links are checked alongside runtime validation; these checks alone are not payment proof.

Target-device report units/identity and latency, terminal zero/nonzero tip popup behavior and final release acceptance remain ticket 12's human/device gate. This ticket does not edit ticket 12 or authorize a deployment.

## Deliverable self-evaluation

Overall **4.0/5** across five independent quality axes; no critical issues. This evaluates the local implementation and its evidence, not the separate physical-device release gate.

| Axis | Score | Evidence and improvement |
| --- | --- | --- |
| Accuracy | 4/5 | Final committed runtime passed both 340-test phases, Restaurant and exact-archive checks; all five source traces were independently verified. Native bus test-cursor exceptions are disclosed rather than described as a completely clean log. A future harness cleanup could remove that diagnostic noise. |
| Completeness | 4/5 | All nine ticket criteria include positive and rejection controls, historical migration, three-process restart, native rounded refunds and genuine cursor races. Some earlier focused rows identify a class rather than reproducing its complete command; retain copyable commands for each bounded run in future evidence. |
| Clarity | 4/5 | Current results, historical failures, source verdicts and release limits are separated. The complete coordinated slice spans many models; a short developer guide to authority/report/refund entry points would make future onboarding easier. |
| Actionability | 4/5 | Configuration and migration instructions, exact revision/archive hash and reproducible combined/artifact commands are available on the committed work branch. Local `/tmp` logs are less portable than the durable result table; archive them with the eventual release evidence. |
| Conciseness | 4/5 | Focused counts are not inflated into summed coverage, and the final result is explicit. Baseline, historical repairs and final boundaries repeat some detail; retain that audit trail here while keeping the user-facing result short. |

Top improvements: archive raw logs with release evidence; provide a concise entry-point guide for subsequent maintainers; preserve exact bounded commands in future test records. None is an unfinished acceptance criterion. Self-check: the user should agree that the requested worktree implementation is complete and tested, while live POS and physical release acceptance remain untouched. Verdict: deliver the committed local slice.

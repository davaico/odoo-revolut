# Ticket 12 — Release provenance

Updated **2026-10-12**. For manual testing, read the
[current handoff](ticket-12-fresh-retest-2026-10-08.md); for acceptance criteria,
use the [checklist](ticket-12-final-release-checklist.md). This file records
release/test provenance, not a second operator timeline.

## October 12 later continuation — saved PDF, closure and new recovery finding

The owner supplied an actual saved native FULL return PDF, inspected by text
extraction and rendered-page visual review: 261-3-000003, quantity −1, total
and Revolut tender −£0.01, readable wrapped refund/original references, one page.
One session-close attempt was rejected for active drafts; successful closure
and reopening are not claimed. Return 1019 remains owner-accepted as a test,
with pending settlement/native work preserved operationally.

[Ticket 47](../tickets/needs-triage/47-recover-unstarted-tender-after-reload.md)
records a new unstarted-tender removal failure after preparation rejection and
reload. A fresh local reproduction imports the actual lifecycle module with
mocked empty payment lookups: two false removals, one interrupted message,
locked/no Resume. This is not a full native Odoo/browser test. At 09:40:19 UTC,
read-only staging SQL confirms order 1022 remains draft, tender 79 waiting,
no payment attempt/cart authorization, counts 72/161/17, Price Control false
after owner cleanup and restored Tips product 1. No charge was recorded in this
new scenario; gross-charge budget remains £0.06. Runtime files were not edited
or deployed, and completed regression suites were not repeated during this
later continuation. Owner UI settings changes and one closure attempt are
separate from the earlier agent read-only audit below.

## October 12 agent follow-up — fresh checks and limits

Fresh local runs on worktree HEAD `3669539`: **125 JavaScript passed**;
**65 Python discovered, 62 passed and 3 skipped** (supported-image PDF cases).
Focused Odoo integration rerun did **not start**: Docker daemon unavailable.
Do not count that attempt as a pass. Existing PR #73 Odoo/artifact evidence below
remains prior evidence. Local Git comparison found no runtime/test differences
between this HEAD and deployed main `557f8a8bc6935ef94d6f1c45d83be4c2f7a48078`.

Read-only staging audit at 08:48–08:50 UTC confirmed installed .18.11, unchanged
72/161/17 operation/dispatch/refund counts, five Paid campaign returns, matching
links, and no duplicate refund references or allocations over captured amounts.
Native Paid totals: £0.18 = £0.14 card + £0.04 cash. Completed refund 19 on draft
1019 explains the extra £0.01 financial refund not yet in Paid-order totals.
Refund 20 remains processing; correction 13 remains draft with zero journal items.
No financial calls, session closure, staging writes or deployment were performed.
See the [authoritative summary](ticket-12-final-release-checklist.md#current-acceptance-summary--october-12-owner-handoff)
for commands, temporary log paths, coverage mapping and remaining human work.

The earlier audit below is a historical snapshot **before refund 20 was created**;
its zero-unresolved statement does not describe the current database.

## October 12 read-only refund verification

Staging SQL verified installed `pos_revolut` **19.0.1.18.11** and completed
refunds 12/13/16/17/18/19, total £0.06, with six distinct provider references and
zero unresolved refunds. The owner confirms receipt of funds. Saved native
returns remain drafts; completion is not claimed. See the
[October 12 refund audit](ticket-12-final-release-checklist.md#refund-completion-audit--2026-10-12). This is database evidence, not a fresh deployed-file hash check,
provider API call or native checkout test. No runtime changes were made.

## Latest deployment evidence — PR #73 / .18.11

[PR #73](https://github.com/davaico/odoo-revolut/pull/73) records deployment of
main `557f8a8bc6935ef94d6f1c45d83be4c2f7a48078`, including fix commit
`7d553c1db3fc628d8371214f05475f81c3930e09`, addon **19.0.1.18.11**.
Its deployment record reports all 118 deployed file hashes matched, the
installed version and active service verified, local/public login health checks
passed, and financial records preserved by the guarded upgrade. This is
provenance from the merged PR, not a new inspection during evidence publication.

The PR reports 621 addon tests, 125 JavaScript tests, and 65 Python-script tests
with three existing skips. The exact main archive passed retail installation
and all four migration checks. These automated checks do not pass the remaining
manual usability retests. The manual campaign results below were observed
through .18.10. PR #74 independently closed native invoice PDF ticket 34.

## Previous campaign deployment verification — PR #72

Read-only verification on **2026-10-09** confirms installed addon
**19.0.1.18.10**, active Odoo service, and release directory
`/opt/odoo-releases/revolut/staging/d232c57b797b898aef57d5139290f11699d4678c/pos_revolut`.
The campaign baseline was merge `93b06c2` ([PR #72](https://github.com/davaico/Odoo-Revolut/pull/72)).
This recheck verified path/version/service, not a complete deployed-file comparison.
See [mocked remediation](ticket-12-mocked-remediation.md) for the newer automated
verification scope. Earlier live failures remain historical observations pending
retest or the documented diagnosis; previous live passes retain their original
version scope. The subsequent two-card split and other manual results are recorded in the handoff.

## Previous deployed release — PR #70

| Item | Verified value |
| --- | --- |
| PR | [#70 — allow multiple pending refunds on one payment](https://github.com/davaico/odoo-revolut/pull/70), merged |
| Addon / Odoo | **19.0.1.18.9** / **19.0.20260908** |
| Tested/deployed source | `ab9a430d85225b7dc295e6f30305785478b1b9cd` |
| Merge on main | `170190d3ab12b04da2ee7a157b5be31bb1d31e88` |
| Archive SHA-256 | `febb59a94081f5374075c73c9fc0c97adbeab24f2f2ba5c80c1d4bcba234a817` |
| Environment | Staging, database `revolut_staging` |
| Release directory | `/opt/odoo-releases/revolut/staging/ab9a430d85225b7dc295e6f30305785478b1b9cd/pos_revolut` |
| Backup | `/var/backups/odoo-revolut-deploy/20261009T094746Z-ab9a430d8522` |
| Deployment verification | 110 source files matched, installed version matched, service active, HTTP 200; 1,253 existing financial records preserved |

Built on merged [PR #69](https://github.com/davaico/odoo-revolut/pull/69),
which separates API-refund processing from physical terminal availability.
No merge conflict occurred; its browser regression passed in the combined
release. PR #70 validates previously referenced pending refunds when they
explain the provider's refund aggregate, keeps reservations/finality strict,
and removes the misleading base-field hint. No manual server-source patch.

Read-only recheck on **2026-10-09 at 10:18 UTC** confirmed the same release
symlink, installed addon version **19.0.1.18.9** and active Odoo service. This
recheck did not repeat the archive checksum/source-file comparison, call the
provider, or mutate staging. Refund/native-record observations are in the
current handoff and R11 checklist entry.

## Previous .18.9 release verification

All automated provider calls were mocked; these are not live-device passes.

| Check | Result | Local log under `build/ticket12-2026-10-09/` |
| --- | --- | --- |
| Tip-refund and refund-concurrency suites, repeated partial-refund case, PR #69 pending-refund/new-sale browser regression | 29 passed, zero failures/errors | `t12-combined-refunds.log` |
| Frontend lifecycle (`node --test --test-isolation=none`) | 116 passed | `t12-combined-node.log` |
| Exact committed artifact retail | 16 passed | `t12-pending-artifact-retail.log` |
| Exact artifact migration: legacy retail and Restaurant, install and upgrade | 16 + 16 + 16 + 16 passed | `t12-pending-artifact-migration.log` |
| Independent Standards and Spec reviews | Both passed, no remaining findings | PR #70 |
| Deployment / independent source and health verification | Passed | `t12-pending-refunds-deploy.log`, `t12-pending-refunds-deployed-verification.log` |

Archive: `build/ticket12-2026-10-09/pos-revolut-ab9a430.tar.gz`.
Legacy migration baseline: `30492a67020acdfe34d7f560a9cf6d7fb20f6430`.
Coverage includes base-then-tip while both pending, three pending refunds on
one original, mixed verified/pending baseline, component/gross caps, replay,
wrong prior identity/parent/type/amount/currency/state, missing reference,
timeout, unexplained aggregate and provider completion during observation
without granting local finality. The core regression failed before the fix.

The full A01–A10 baseline below predates these runtime fixes. Only the affected
suites and artifact checks above are claimed on .18.9. Reassess full combined
coverage at final release freeze; do not present the older 597-test runs as
executed on this SHA.

## Automated campaign baseline — 2026-10-08

Full-suite source: `8adc68f255e4ea1830831f571e22f5b3f41875e4`.
Corrected restart-verifier candidate: `693937ee3b7a78991a33cc714e0d47a4c70c3663`
(addon .18.1), archive SHA-256
`8c06d9653970add7d3c1adc8235249df7d8587e7504c70e2793e6cb31ae45102`.
Logs under `build/ticket12-2026-10-08/`.

| Check | Fresh result | Local log |
| --- | --- | --- |
| POS lifecycle | PASS: 107 tests, zero failures or skips | `pos-lifecycle.log` |
| Python tooling | PASS across runtimes: 54 local passes; three local PDF skips executed successfully in Odoo below | `tooling.log`, `pdf-probes.log` |
| Full fresh install, including native browser tours | PASS on baseline: 597 tests reported, zero failures/errors; employee case covered by the separate authorization profile | `install-upgrade.log` |
| Full current-version upgrade, including native browser tours | PASS on baseline: 597 tests reported, zero failures/errors; runner exit 0 | `install-upgrade.log` |
| Supported-runtime PDF probes | PASS: all seven, including the three local skips | `pdf-probes.log` |
| Employee-enabled shared-register authorization | PASS: 46 tests, zero failures/errors; employee-list case actually executed | `employee-access.log` |
| Three-process restart recovery | PASS on corrected baseline candidate: original authority/references, zero/nonzero tips once, no new financial POSTs; exit 0. Original baseline FAIL retained. | `restart.log`, `restart-corrected.log`, `restart-final.log` |
| Deployment financial guards | PASS: actual disposable payment/refund/external-evidence blockers clear only after settlement | `deployment-guard.log` |
| Seven real historical upgrades | PASS: all seven seed/upgrade/preservation checks, exit 0 | `historical-<scenario>.log` |
| Exact delivered artifact: retail | PASS on corrected baseline candidate: 16 tests, zero failures/errors, exit 0 | `artifact-retail-final.log` |
| Exact delivered artifact: legacy retail and Restaurant migration | PASS on corrected baseline candidate: four groups of 16 tests, zero failures/errors, exit 0 | `artifact-migration-final.log` |

The original restart verifier wrongly compared the RPC-specific
`observation_fresh` flag across fresh and cached responses. Only
`addons/pos_revolut/tests/restart_verify.py` changed between the two baseline
SHAs. All production files, other tests and runtime runners were unchanged;
full-suite results carried forward on that basis, while restart and both
artifact scenarios reran on the corrected candidate. Exact references, tips,
five GETs/no POSTs and two dispatch claims remained strict. This carry-forward
applies to those baseline SHAs, not automatically to later runtime releases.

## Historical evidence and preservation

At the owner's request, superseded daily timelines and local-only release
instructions were condensed on October 9. Original tracked chronology remains
in commit `170190d3ab12b04da2ee7a157b5be31bb1d31e88`:

- [Earlier release evidence](https://github.com/davaico/odoo-revolut/blob/170190d3ab12b04da2ee7a157b5be31bb1d31e88/docs/testing/ticket-12-release-evidence.md)
- [Earlier operator observations](https://github.com/davaico/odoo-revolut/blob/170190d3ab12b04da2ee7a157b5be31bb1d31e88/docs/testing/ticket-12-operator-observations.md)
- [Earlier guided retest](https://github.com/davaico/odoo-revolut/blob/170190d3ab12b04da2ee7a157b5be31bb1d31e88/docs/testing/ticket-12-fresh-retest-2026-10-08.md)

Use `git show <commit>:<path>` if needed. Consult old chronology only for a
specific evidence question, not to find the next test. Current handoff retains
unresolved historical financial/native obligations. No database or Git history
was deleted. Git history and ignored/temporary artifacts do not fulfill ticket
33's permanent private archive, custodian or publication-review requirements.

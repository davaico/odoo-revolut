# Ticket 12 — Release provenance

Updated **2026-10-09**. For manual testing, read the
[current handoff](ticket-12-fresh-retest-2026-10-08.md); for acceptance criteria,
use the [checklist](ticket-12-final-release-checklist.md). This file records
release/test provenance, not a second operator timeline.

## Current deployed release

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

## Current release verification

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

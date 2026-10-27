# Final corrected V18 release candidate — 2026-10-26

**READY** for publication under the already accepted physical-test limitations.
No remaining release blockers were found. Nothing was pushed, published or deployed.
This report supersedes the previous BLOCKED verdict; its original failures remain preserved.

## Exact version tested

| Identity | Frozen value |
| --- | --- |
| Release branch | `feat/v18_rev` |
| Full source revision | `ed82c90c1eddfb1bf898a8978c99e2c874fd7d5b` |
| Addon | `pos_revolut`, `18.0.1.0.4` |
| Addon Git tree | `800f4d0eb43b9bed7fbea6ed940b3d472e0f4021` |
| Previous commit included | `9786f8b7c7561dc4e992016b767246b799852a09` — fixed partner metadata |
| Odoo Community | `18.0.20261015` |
| Immutable runtime image | `sha256:f389e806005a7130c777b86c0d3cdcf873610390db72c01f1e1dc4b9f7a35959` |
| Addon archive SHA256 | `e5e0620e3401f4c9a4862f056658225fd1a5a2e2c2b88902d92b929cb4234bde` |
| Source archive SHA256 | `83266551781299d6331785b0552c48e811834a56ba70a12437bca0d6801f8360` |

All 234 regular extracted source files matched the source archive. Tests used the
frozen source and image, read-only addon mounts, synthetic credentials and records,
internal Docker networks, no published ports, disabled cron and the real-Merchant
HTTP rejection guard. No production or original acceptance database was accessed;
no real payment or refund was attempted. All four owned validation projects have
zero remaining containers, networks and volumes.

Repository instructions, ADR 0002 and the latest ticket-63 acceptance handoff were
read. The owner's explicit `feat/v18_rev` target takes precedence over the older
`feat/v18` workflow wording. Pre-existing unrelated working changes were preserved.

## Implemented corrections

Commit `ed82c90` changes two test files only:

- The saved-refund recovery browser tests now dismiss the normal checkout-recovery
  popup with **OK** before selecting **Check status**. Both returns complete with
  the original references and one refund. Original completion, identity,
  provider-call and duplicate-prevention assertions remain intact.
- The optional employee-permissions fixture configures its dedicated register
  before opening it, following native Odoo's restriction. Its employee-selection,
  backend-grant, denied-user, no-HTTP and colleague recovery assertions now run
  with `pos_hr` actually installed.

No production payment behavior, test assertions or timeout limits were weakened.
The popup was a missing test interaction; these runs establish no product defect
for that dialog.

## Results on the corrected candidate

Counts are separate runs, not additive coverage. No line-coverage percentage was collected.

| Check | Result |
| --- | --- |
| Focused permission class and both refund-recovery cases | **29 passed**, zero failures/errors/skips, exit 0 |
| Fresh database installation and full `/pos_revolut` suite | **784 passed**, zero failures/errors/skips, exit 0 |
| First addon installation into populated POS/Restaurant/HR database | **PASS**, 59 passed, zero failures/errors/skips |
| Existing `.4 → .4` addon update | **PASS**, 59 passed, zero failures/errors/skips |
| Historical `.3 → .4` addon update | **PASS**, 59 passed, zero failures/errors/skips |
| Record preservation and independent audit | **PASS**, six before/after comparisons and six verifier markers |
| Host Python runner/deployment/PDF checks | **70 passed**, 3 host dependency skips, 73 reported, exit 0 |
| Renderer checks in supported image, network disabled | **7 passed**; covers the three host dependency skips |
| JavaScript payment-state / refund allowances | **142 + 3 passed** |
| Python compilation and correction whitespace check | **PASS** |

The fresh full run installed `pos_revolut`, `pos_restaurant` and `pos_hr` and
completed 2026-10-26 at 15:53:38 UTC. Its 784 tests cover payments, declines,
failures, cancellations, timeout/interruption recovery, full/partial refunds,
duplicate prevention/concurrency, zero/nonzero tips, split tenders, Restaurant
workflows, permissions, receipts, tax/rounding, native stock effects and accounting.
Both formerly failing refund tours and the formerly broken HR fixture passed.

The populated lanes begin with native POS, Restaurant and HR installed and saved
customer, product, register, paid sale and posted accounting history before addon
installation. Each lane preserved exact IDs and tracked values for **13 native
records across 12 models**, and updates preserved **29 configuration/financial
records across 13 models**. These include verified and unresolved payments,
refunds, provider references, dispatch claims, reservations, cart authorities,
external evidence and access grants. Read-only recovery retains original identities
without another financial POST. The independent audit compares actual post-install
and post-update reads with pre-operation snapshots; only known Many2many membership
lists are normalized for ordering. These are representative committed fixtures,
not a byte-for-byte comparison of the entire database.

The historical baseline is `fcb59c40921eaf347fbf5f36583e7b0cefb3f878`, version
`18.0.1.0.3`. All three selected runs explicitly execute the HR permission method;
none skips it.

## Preserved failed and interrupted attempts

- The [original report](final-v18-rc-20261026.md) and original evidence remain:
  the old candidate had two refund-tour failures and an HR fixture error. The
  popup-only follow-up passed before the permanent correction was authorized.
- The corrected candidate's first full attempt is **INCOMPLETE/FAILED**, container
  exit **255**, 721 methods started, no final suite aggregate. It recorded a Chrome
  navigation timeout in `TestRevolutRefundHistory.test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund`
  and `StopIteration` while checking a mocked report POST in
  `TestRevolutTerminalTip.test_report_uses_bounded_columns_time_and_authenticated_fixed_paths`.
  Six browser methods skipped when Chrome's debug port did not start in time.
  Host memory/swap were exhausted and Docker then restarted externally; the
  container was not marked OOM-killed. This context does not prove the precise
  cause of every observed error. Logs, screenshots, state and cleanup evidence
  remain in `evidence/full/` with their failed status.
- The serial replacement run used **the same source, image and timeout limits**
  and passed all **784**, including every affected method, with no skips. The
  failed attempt has not been relabelled as passing.
- An earlier setup mistake mounted an empty source directory after a failed local
  Git operation; no addon tests ran. Its startup logs and explanation remain in
  `evidence/full-startup-failed/`. Source-manifest validation was added before
  subsequent Docker startup. It is counted as neither a product failure nor a pass.

## Skips and accepted limitations

- The successful full suite and populated selected suites have **no skips**.
  Three host PDF checks skip unavailable host renderer/parser dependencies;
  all seven renderer checks pass in the supported image with networking disabled.
- Previously accepted physical limitations remain: splitting with two distinct
  physical cards, a genuine issuer decline, and other unobserved physical
  interruption variants. The intended setup has no printer, so physical Odoo
  printer acceptance remains not applicable. Service-product hardware fixtures
  do not establish physical stock movements. No new real-money tests were run.
- The pending penny refund and deferred existing return/session completion remain
  **accepted non-blocking follow-up**. No provider recheck, forced reconciliation
  or financial replay was performed.
- Earlier standalone restart/preflight/native-PDF visual checks in the original
  report were not rerun as separate scripts on this revision. Their evidence
  stays attributed to the original candidate. The corrected full suite includes
  native receipt/document/accounting and recovery behavior checks.

**Remaining blockers: none within the agreed release scope.**

## Evidence

Evidence root in the primary repository: `build/v18-rc-corrected-20261026/`.

- [Frozen manifest](../../build/v18-rc-corrected-20261026/manifest.json)
- [Full passing suite](../../build/v18-rc-corrected-20261026/evidence/full-quiet/result.json)
- [Full log](../../build/v18-rc-corrected-20261026/evidence/full-quiet/tests.log)
- [Targeted results](../../build/v18-rc-corrected-20261026/evidence/targeted/result.json)
- [Populated summary](../../build/v18-rc-corrected-20261026/evidence/populated/summary.json)
- [Independent preservation audit](../../build/v18-rc-corrected-20261026/evidence/populated/independent-audit.json)
- [Auxiliary results](../../build/v18-rc-corrected-20261026/evidence/auxiliary/results.json)
- [Retained interrupted result](../../build/v18-rc-corrected-20261026/evidence/full/interrupted-result.json)
- [Cleanup proof](../../build/v18-rc-corrected-20261026/evidence/final-cleanup.json)
- [Self-check](../../build/v18-rc-corrected-20261026/evidence/self-evaluation.json)

[Evidence archive](../../build/v18-rc-corrected-20261026/evidence-ed82c90c1eddfb1bf898a8978c99e2c874fd7d5b.tar.gz):
291 payload files, all packaged checksums verified; SHA256
`ae37c1e019f15287acdd9c33fe2dbcbba6115d3e7f33c82d8312fe75dd83083e`.
The archive includes immutable source/addon archives, harnesses, commands, raw
passing/failed logs, snapshots and runtime/cleanup state. Extracted source copies
are omitted. Run browser lanes serially using the retained pinned runtime and
mocked provider configuration. Do not reuse original acceptance data.

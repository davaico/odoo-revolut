# Ticket 81 — Enterprise 18 release candidate

Work branch: `codex/81-release-validation`. Reviewed base and integration target:
`staging/18-enterprise` at `d5d13d3943c7eadff4a0bdd44d0d1bdc19e8fc49`.
Production PR target: `18.0`; never merge or push directly there in this ticket.

## Identity and scope

Frozen candidate: `3f2ff4a167f154fafe5ff886cb506a47145b0bae`, addon
`18.0.1.0.8`, addon Git tree `57730fd0d5a81ea6a288081ac0eced63eb9e5b1b`.
Exact addon archive SHA256:
`3a3a55dc545a19114238a994b8ab3136c689770843758c5d155305f298beed6e`.
Release metadata corrects the manifest/store listing's obsolete Enterprise-verification text;
no payment runtime behavior changes in #81. Subsequent evidence/runbook changes
outside the addon preserve this tested tree.

Production base: `2814e8f6d24cccfa99fccbe0ea6e08c1bfb646b6`, version `.4`.
The corrected `.4` commit `ed82c90` is an ancestor of staging. Its former
`addons/pos_revolut` tree differs from production's root addon only in manifest
and store-description metadata/assets. The approved changes assembled above are
T76 environment guard (`.5`), T77 credential authority/storage/log redaction
(`.6`), T78 neutralization (`.7`), T79 configuration (`.8`), and T80/T84 fixtures.
No Community restoration commit is included.

The production PR comes directly from `staging/18-enterprise`, the maintained
Enterprise development branch, into `18.0`. The completed task was fast-forwarded
from reviewed staging base `d5d13d3` through `fbf944f`, preserving its full history.
This includes campaign documentation, local tickets and historical testing
records alongside the approved addon and tools.

An initial release projection used a `codex/` branch to omit those development
records from the production diff. The owner clarified that staging is the dev
branch and the PR must originate there. PR #95 was closed unmerged and replaced
by PR #96. The correction changes branch routing and documentation only; the
addon tree remains the exact validated `57730fd0d5a81ea6a288081ac0eced63eb9e5b1b`.

## Hosted evidence applicability

Hosted build **41044597**, source `fdfa74596f2445e0a54a1206cb28a052386cda01`,
installed `.8`, Odoo `18.0+e` (Odoo `2982b5f`, Enterprise `631c5ab`), is the
accepted T80 lifecycle build. See [the detailed evidence](ticket-80-odoo-sh-staging.md).
It exercised populated first installation, runtime access boundaries, installed
copy cleanup, neutralized first install and payment/refund recovery, including
actual native cron-worker death/replacement with mocked HTTP. The separate
platform-managed restart command/scheduling limitation remains.

Between that hosted revision and the assembled candidate, models, views,
security, data, hooks and production POS assets are unchanged. Addon differences
are manifest/store-listing descriptions, T84's test-only held-response correction/delayed
regression and T80's two standalone native-worker fixtures (executed on that
hosted build from hash-checked temporary files). T84's full-suite source
`fccfd12` differs from this candidate only in those two standalone files and
manifest/store-listing prose. Neither standalone file is imported by `tests/__init__.py`.
There is no material production runtime difference requiring a new hosted
lifecycle run. This is an explicit byte-comparison assessment, not a claim that
`3f2ff4a` itself was hosted. Reopen hosted validation for any later runtime change.

The reference project remains a test-only trial. No paid production activation
or client hosting follows from this release. Client build/version, configuration,
entitlement and bounded live acceptance belong to ticket 82.

## Validation

Current results: 146 JavaScript checks passed; 80 host tests passed with three
existing PDF dependency skips. Python compilation and whitespace checks pass.
No configured static type checker exists. No new executable feature or test seam
is introduced in this ticket, so no new TDD test is needed.

Completed on source `f8abaa3fcab1f1261ab04cc92bdf1bdc6d03d9ea` with zero assertion failures. The final frozen candidate changes only store-description prose in the addon; runtime and fixtures are identical:

| Lane | Result |
| --- | --- |
| Fresh installation into populated native POS/Restaurant data | 31 focused tests, zero failures/errors; all 13 native records across 12 models preserved |
| Same-candidate `.8 -> .8` update | 31 focused tests, zero failures/errors; native data and 29 configuration/financial records across 13 models preserved |
| Versioned production `.4 -> .8` update | Native and 29-record financial snapshots preserved; five additional environment-authority/history records preserved; original-key GET-only payment/refund recovery passed |
| Neutralized before addon installation | Addon tables proven absent before installation; both Production key sources blocked with zero HTTP/reservations; Sandbox usable |

Versioned baseline archive SHA256:
`af18270de1c01eb03dd219a05ef49c5134648464e8b85d71bcdc2ea54eea812e`.
Focused tags: `/pos_revolut:TestRevolutPaymentMethod`,
`/pos_revolut:TestRevolutDatabaseCredentials`,
`/pos_revolut:TestRevolutDatabaseCredentialFlow`,
`/pos_revolut:TestRevolutNeutralization`.

The selected install/update cases exercise the real credential resolver and
mock only provider HTTP. Existing `native_install_*`, `candidate_update_*`,
`company_credential_upgrade_*` and `neutralized_install_verify.py` fixtures ran
in separate Odoo processes. The `.4` versioned lane seeds both native and actual
authorized-cart payment/refund histories before the upgrade; it adds the existing
environment-credential fixture before switching the read-only addon mount to the
candidate. Exact record IDs, fields, references, claims, reservations, grants and
original-key GET-only recovery were verified afterward.

The first orchestration process stopped at the versioned lane's resource
admission check before creating that database; it did not fail an Odoo test.
The populated lane was not repeated. A continuation retained those artifacts
and completed only the remaining versioned and neutralized lanes. Task-owned
acceptance containers, volumes and networks were removed. Original admission
records and logs remain alongside the successful continuation.

A first full-suite invocation on `f8abaa3` was deliberately interrupted after
167 seconds to include the remaining store-listing clarification in one frozen
final addon. Docker exit 130, no aggregate result, no OOM kill; it is incomplete,
not a passing or failing completed suite. Its logs/resources/result remain in
`full-interrupted-metadata/`. The final full-addon invocation uses `3f2ff4a`.
No financial assertion, fixture deadline or runtime behavior changed.

The assembled-source full invocation completed **816 cases, zero failures/errors**,
Docker exit 0, in 1,537 seconds. It had **five skips**: the allowed optional
`pos_hr` characterization and four saved-refund browser cases whose Chrome
DevTools port failed to start. The release verifier rejected this run as a clean
full-suite gate (supervisor exit 1). Its result remains resource-skipped evidence;
it is not relabelled as an entirely passing fresh full run.

The four exact browser methods then executed unchanged on `3f2ff4a` in a fresh
disposable database: **4 passed, zero failures/errors/skips**, Docker and verifier
exit 0, 106.52 seconds. Offline loader, rejected checkout, timeout recovery and
delayed canonical response all completed their real server/browser assertions,
including original refund identity and no duplicate dispatch. Together with the
seven affected cases that executed in the full run, all ten T84-affected browser
cases have successful execution evidence on this exact final addon.

T84's clean 816-case full-suite prerequisite remains attributed to `fccfd12`,
not this new run. `full-suite-equivalence.json` proves every other addon path and
mode unchanged: manifest settings match after excluding description prose;
`tests/__init__.py`, runtime and automatically loaded tests match byte-for-byte.
Only manifest/store prose and the two unimported standalone cron fixtures differ.
Ticket 81 explicitly retains T84's satisfied full-suite gate and asks to revalidate
material differences. The preserved clean baseline, this assembled-source full
run, the four-case completion and new install/upgrade/copy checks meet that scope.
Independent Spec review confirmed this interpretation before closure. No skip,
assertion, test deadline or payment guarantee was weakened to obtain acceptance.

The late host-resource burst is observed context, not an established Chrome
root cause. Sampled available RAM fell to about 140 MiB, load exceeded 38 and
memory full-pressure avg10 exceeded 26 percent. Odoo's recorded peak was about
1.07 GiB, below its 1.5 GiB cap, with zero sampled container swap and no OOM kill.
The last database snapshot reported about 0.62 GiB peak, zero swap/OOM events.
Sampling aimed at five-second intervals but has gaps during the host burst.
A focused success does not repaint the resource-skipped full run green; no
product fix was inferred or applied. Admission checks cannot guarantee a shared
host remains quiet throughout execution.

Transient artifact root: `/tmp/ticket81-validation/`. Candidate and `.4` baseline
come from `git archive`, mounted read-only. Pinned derived image:
`sha256:a138d2204f1249d295f99df82bd399706e7494e45d5a674b4e977ad8858b1c05`,
Odoo Community `18.0.20261015`, repository-pinned PostgreSQL `16.14`, internal
network `10.237.181.0/24`, synthetic credentials, mocked provider traffic and
`ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`. No real terminal or Merchant API is used.
Acceptance-lane resource limits disable container swap (Odoo 3 GiB/4 CPUs,
database 1.5 GiB/2 CPUs). After the listing clarification, the shared host held
near 2 GiB available and the replacement supervisor initially waited at its
3 GiB admission gate without starting a test. The final full run uses limits
above T84's measured peaks: Odoo 1.5 GiB/4 CPUs and PostgreSQL 0.75 GiB/2 CPUs,
with memory-plus-swap equal to memory, at least 2 GiB host admission, load at
most 8 and memory full-pressure avg10 below 1 percent. This is a recorded
resource-budget adjustment, not a timeout/assertion change; any OOM or test
failure remains a failed run.
The initially exhausted shared host was reported to the owner; no Odoo test was
started until capacity was freed and the recorded admission check passed.

## Reproduction and retained artifacts

`git archive` exported the addon at each recorded revision. The 174-file
`candidate-files.json` inventory verifies every frozen and projected file against
`3f2ff4a`; final Git-tree equality also checks tracked paths and modes.
`populated-commands.json` retains the completed first lane;
`acceptance-commands.json` retains the versioned/neutralized continuation.
Each phase has its actual `.log` and `.exit`; `versioned-snapshots.log` contains
the synthetic pre-upgrade record snapshots checked afterward. All shell phases
run through `odoo shell --no-http --max-cron-threads 0` in fresh processes.

The final full command, with `ODOO_REVOLUT_ADDONS_DIR` selecting the frozen source:

```bash
docker compose -p odoo-revolut-ticket81-full \
  -f /tmp/ticket81-validation/compose-full.yaml run --detach --no-deps \
  --name odoo-revolut-ticket81-full odoo --database odoo_revolut_tests \
  --init pos_revolut --stop-after-init --workers 0 --log-level warn \
  --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO \
  --log-handler odoo.addons.pos_revolut:INFO --test-tags /pos_revolut
```

`full-command.json`, `full-admission.json`, `full-result.json`, `full.log`,
`full-resources.jsonl`, database resource/state snapshots and cleanup logs retain
actual execution evidence. `compose-full.yaml` pins the image, read-only mount,
internal network and final resource limits; no image was rebuilt or pulled.
The focused command uses the same runtime/options in project
`odoo-revolut-ticket81-focused` with `--test-tags` set to these comma-joined names:

- `/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_offline_loader_recovers_without_second_refund`
- `/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_rejection_recovers_without_second_refund`
- `/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_timeout_recovers_without_second_refund`
- `/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_waits_for_delayed_canonical_response`

`focused-*` and `focused.log` retain its command, admission, result, resources and
cleanup. The copied supervisor retains its original “full suite” log label; its
actual argv, four-case aggregate and per-method browser successes identify this
as the focused run, not a second full-suite invocation. An initial temporary
runner-generation syntax error started no container or test and was corrected.
Portable logs are retained separately. Counts describe separate runs and are
not added together. The three host PDF dependency skips do not imply the
supported-runtime document checks were skipped in the full suite.

## Maintained Community impact

Production 18 and restored Community 18 (`4b8b5cd`) have identical addon tree
`b5a29021233889695d9bd6b391292461bdf7d4fb`, version `.4`. Neither Community
branch is modified by this work. Odoo 19 remains independently released at
`c2b7d40ea39d373a0ad9f9d4e11cd5bb9ddf1b7e`, version `19.0.1.18.16`.
Its T74 evidence covers `.14 -> .16`, 112 targeted native/browser checks, 159 JS
checks and 23 portable checks; its earlier failing full run remains historical.
No Odoo 19 Enterprise/Odoo.sh certification is in scope.

Both Community lines retain the same short held-response test race. Applicable
shared fixture corrections need selective backports plus each version's native
recovery tests and full-suite evidence before claiming the corrected fixture on
that line. T77 storage/logging and T79 UI changes need deliberate version-specific
adaptation if adopted; T76/T78 hosted/copy protections are not certified on the
unchanged Community branches. Do not merge the divergent branches wholesale.
These are explicit maintained-line follow-up gates, not evidence of equivalent
verification from this Enterprise 18 run.

## Activation and recovery handoff

[The public checklist](../releasing.md) covers release approval, backups/module
upgrade, correct company/register/terminal, credential source and retention,
configuration that is not automatically promoted, one small client payment/refund,
verified final outcomes, original-attempt recovery and cashier enablement only
after acceptance. Accepted earlier hardware limitations remain; unrelated historic
transactions and deferred ticket 83 are not reopened.

## Standards

Independent final review of `d5d13d3...c733222` and public projection
`2814e8f...53ab3ae`: **0 actionable findings**. Exact addon identity, scoped public
files, original-authority recovery and deferred cashier grants conform to the
repository guidance. No concealed failure or unsupported compatibility claim.

## Spec

Independent final review of the same ranges: **0 findings**. The retained clean
full prerequisite plus byte-equivalence proof, assembled execution and all four
unchanged browser completions satisfy #81's material-revalidation requirement.
Upgrade, hosted applicability, Community gates, activation and recovery are
covered. The resource-skipped full run remains explicitly distinguished.

Closing tracker/reference changes were reviewed separately; their stale blocker
wording was corrected. No outstanding closing-delta findings remain.

Standards: 0 findings. Spec: 0 findings.

## Production PR and disposition

[PR #96](https://github.com/davaico/odoo-revolut/pull/96) is open and ready for
review, from `staging/18-enterprise` into `18.0`, whose revision remains
`2814e8f6d24cccfa99fccbe0ea6e08c1bfb646b6`. Its addon tree is exactly the frozen
`57730fd0d5a81ea6a288081ac0eced63eb9e5b1b`. Its description covers payment impact,
every test limitation, credentials/configuration, module upgrade and recovery.
Staging configuration is explicitly not promoted automatically with code.

Ticket 81 is closed and its completed work is integrated into the Enterprise dev
branch. Base: reviewed staging `d5d13d3`; integration target:
`staging/18-enterprise`, fast-forwarded through `fbf944f` before this documentation
correction. Earlier reviews retain their recorded ranges; the branch correction
adds the retained development records to the PR without changing addon code.
Narrow verification checks documentation links, ancestry and exact addon-tree
equality; payment tests are not rerun for this branch/documentation-only change.

The owner's “Don't merge” instruction applies to the production PR. PR #96 stays
unmerged; superseded [PR #95](https://github.com/davaico/odoo-revolut/pull/95) is
closed and unmerged. Production `18.0`, client databases and live financial state
remain unchanged. Ticket 82 retains separate client activation requirements.

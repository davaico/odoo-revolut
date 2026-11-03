# Ticket 82 — Pre-payment setup and browser checks

Date: 2026-11-02. Work branch: `codex/82-live-test-checkpoint`, based on
reviewed `staging/18-enterprise` at `4330188446d96aca4f517522fd86165d24fa2254`.
Integration target: `staging/18-enterprise`. Live acceptance remains open.

## Current handoff — 3 November 2026

The owner requested publishing all Enterprise/Odoo.sh work and this checkpoint
in PR #96, ready for the owner to merge into `18.0`. This supersedes the earlier
local-only restriction for preparing the PR. The merge remains with the owner;
no real payment or refund is authorized by PR preparation.

The implementation is the tested **18.0.1.0.8** addon tree
`7538c06c385716864f9a9d302b1c453caf63e89a` from `4a56e8e`. Subsequent checkpoint
changes are documentation only. The completed local suite has **816 tests,
zero failures/errors and one optional skip**; the focused mocked hosted selection
has **19 passing checks**. Details, earlier failures and limitations appear below.

The owner clarified that Odoo.sh's Production database is the team's test trial.
Marketplace publication is a separate concern: the owner accepts the colleague's
confirmation that marketplace auto-scanning is disabled. The publisher account
belongs to that colleague; its settings were not independently inspected.
The public Odoo Apps listing observed on 3 November still serves **18.0.1.0.4**.
An active Odoo.sh push webhook was independently observed; merging into `18.0`
must still be treated as deployment to the team's Production-stage trial.

Ready for the owner's reviewed trial promotion, with the existing safeguards
unchanged. This does not close T82 or establish real terminal acceptance.
After promotion, verify the installed addon identity and complete the authority,
register/operator, terminal/currency and agreed-amount prerequisites before any
financial action. Keep marketplace scans/publication paused until acceptance
and separate release approval. Private keys, identifiers, raw logs, screenshots
and prepared setup files remain outside Git.

Final preparation review: **Standards 0 findings; Spec 0 findings** against
`18.0@2814e8f6`, including the final documentation update. Implementation ancestry
for T76–81 and the T82 correction, all 174 addon bytes/version, changed-document
links, whitespace and exclusion of the private location identifier passed.
No new runtime test was needed for this documentation-only update; the full
regression retains its exact addon-tree attribution.

## Candidate and environments

The owner requested automatic setup and non-financial checks, stopping before
card participation. They selected Davai as company/location, terminal
**Test Guzman** or **Davai**, and EUR if supported, with the previous GBP
restriction retained as a possibility. No collection/refund amount is approved.

- Production build **40905690**, branch `18.0` at `2814e8f6`, opens normally.
  Settings reports **Odoo 18.0+e (Enterprise Edition)** and database expiry
  **3 December 2026**. Restricted parameter inspection confirmed reason `trial`,
  expiry value `2026-12-03 10:43:31` and no `database.is_neutralized` row.
  POS Revolut is available but uninstalled on this older source.
- The empty Production trial company's name/currency were changed to
  **Davai / EUR** and verified after reload. No accounting or POS transaction
  was created. This confirms Odoo configuration, not Merchant EUR support.
- Staging build **41044597** reports the neutralized banner, installed addon
  **18.0.1.0.8**, and Odoo Enterprise 18. The initial browser checks used the
  runtime behind source `4330188`. Existing T80/T81 evidence keeps its original
  scope and source attribution.
- Correction `4a56e8ee18e27bd1214a645016750f70cf25ad62` was independently reviewed
  and pushed to `origin/staging/18-enterprise`. Odoo.sh subsequently reported
  that source successful on the same build, and the corrected public action was
  exercised in the hosted browser. Addon Git tree:
  `7538c06c385716864f9a9d302b1c453caf63e89a`.

No Enterprise registration, activation/subscription code, plan purchase,
expiry change, Production code deployment or PR merge was performed.

## Browser checks

| Check | Observation |
| --- | --- |
| Installation/version | Installed `.8` confirmed through developer-mode Module Info; Upgrade/Uninstall controls present. No reinstall needed. |
| Native register | Existing Clothes Shop session retained. Its methods were Card, Customer Account and Cash; automatic terminal validation was enabled and Revolut backend-user grants were empty. |
| Existing authorities | Only revoked Sandbox fixtures were present before the new keyless test. No usable Merchant authority was available. |
| Bank journal prerequisite | Selecting Terminal without a journal hides the native provider selector and shows an install-terminal hint. Selecting Bank exposes Integrate with → Revolut. This is native behavior, not an addon defect. |
| Revolut fields/help | Company, environment, location/terminal UUIDs, fulfilment, credential reference and Check Connection were visible. The form requests a reference, never a Merchant API key. |
| Invalid namespace | Save rejected `T82_INVALID_REFERENCE` with the required `ODOO_REVOLUT_SECRET_` namespace message. |
| Invalid location | Save rejected a non-UUID location with the explicit location/terminal UUID validation message. |
| Production access guard | A saved, unassigned, keyless Production fixture was blocked before credential resolution/HTTP. The initial generic RPC dialog exposed the presentation defect below. |
| Corrected guard dialog | After Staging deployment, the same archived fixture showed native **Invalid Operation** with the complete Production-access restriction, without opening technical details. |
| Scheduled actions | Both Revolut reconciliation jobs were installed and inactive. Each completed a manual browser invocation without an error; both remained inactive. This is a smoke check, not fresh pending-operation recovery or platform scheduling proof. |
| Cleanup | The new method was archived and its keyless Environment authority revoked. Neither was attached to a register. Existing session/history was preserved. |

The fixture used explicitly synthetic UUIDs and reference
`ODOO_REVOLUT_SECRET_T82_GUARD_ONLY`, with no API key. It created no payment or
refund attempt. No genuine Merchant credential was copied into Staging.

## Public error correction and native tests

Odoo serializes the custom `RevolutEnvironmentError` with its addon-specific
class name. The web client displayed a generic RPC error instead of the normal
Odoo user-error dialog. The restriction itself remained effective.

The correction catches only this exception at
`action_revolut_check_connection()` and raises native `UserError` with the same
message. Internal typed exceptions, the guard, credential binding and financial
dispatch/recovery behavior are unchanged.

- Red: the existing blocked-stage test failed in all five stage subcases when
  asserting the native serialized exception name; one selected method,
  five failures, zero errors, exit 1.
- Green: the complete `TestRevolutPaymentMethod` class passed: **16 tests,
  zero failures/errors**, exit 0. The regression retains its zero-HTTP assertion.
- Independent Standards and Spec reviews of `8886b8c...4a56e8e`: **0 / 0 findings**.
- AST syntax and whitespace checks passed. No static type checker is configured.

Native checks used pinned Odoo Community `18.0.20261015` image
`a138d2204f1249d295f99df82bd399706e7494e45d5a674b4e977ad8858b1c05`, synthetic
credentials, an internal Docker network and the Merchant HTTP guard. Disposable
focused-test resources were removed. Logs are retained locally as
`/tmp/t82-regression-red.log` and `/tmp/t82-regression-green.log`.

## Full regression invocation

One full `/pos_revolut` invocation used an immutable snapshot of the corrected
addon, the same pinned runtime and blocked Merchant HTTP. It was stopped at
the owner's explicit checkpoint request: **interrupted/incomplete**, exit 137,
`OOMKilled=false`, after 1,713.73 seconds. There is no aggregate pass.

Before interruption, the log recorded 797 test-start markers, two browser
failures, one browser error and nine skips (eight Chrome startup skips and the
optional `pos_hr` characterization). The observed red cases were:

- `TestRevolutVerifiedCheckout.test_cancelled_payment_then_minimal_unsent_allocation_reload`
  — browser script timeout.
- `TestRevolutVerifiedCheckout.test_declined_payment_can_retry_once_without_duplicate_charge`
  — WebSocket timeout error.
- `TestRevolutVerifiedCheckout.test_delayed_native_preparation_cannot_start_after_same_tender_recovery`
  — receipt-step timeout.

Shared-host pressure coincided with these results: available RAM reached
174,684 KiB, one-minute load reached 103.11 and full memory-pressure `avg10`
reached 39.63 percent. The test container had no OOM/swap event and peaked at
1,231,302,656 bytes. This does not establish the failures' root cause. No
timeout/assertion was changed, and no full or focused retry was started.

All 174 frozen addon files match `4a56e8e` byte for byte, with no missing/extra
paths. Own test containers, networks and volumes were removed and their absence
verified. Retained artifacts include the partial log, source inventory, command,
admission checks, resource observations, exact skipped/red cases and cleanup.
Local results do not establish hosted lifecycle or live payment acceptance.
Resolve the observed failures/skips before treating this candidate's release
validation as complete.

## Remaining setup gates at the pause

- The Revolut portal recognizes the owner's account but requires its passcode.
  The login was left for the owner to complete directly; no passcode or new key
  was requested in chat. Merchant EUR support and exact device/location UUIDs
  remain unverified. An approved usable Merchant credential source is required.
- The Odoo.sh web terminal remained at **Loading terminal session** after a
  bounded reload; the displayed SSH fallback timed out. The focused hosted
  shell test selection was therefore not rerun. Prior T80 worker/copy evidence
  remains historical; manual job smoke checks do not replace it.
- Browser access disconnected, then temporarily recovered. A manual Production
  backup was requested with comment **T82 before Revolut installation — Davai
  EUR, no payments**. The last observed status was **A backup operation is in
  progress**; completion/download/restoration were not verified. Browser access
  became unavailable again at the pause. No Production addon installation or
  code promotion was completed.
- Finish validation and the reviewed release path, then deliberately configure
  the Production authority, terminal method, bank journal, register, suitable
  untaxed tip product, authorized operator and reconciliation jobs. Do not
  promote synthetic test references or weaken Staging guards.
- Before any money moves, confirm supported currency, online terminal, operator,
  sale amount and partial/remaining refund amounts with the owner. Then verify
  underlying payment/refund finality and matching native orders/accounting.

## Historical paused checkpoint

The owner explicitly requested stopping and resuming later. No further tests,
deployment, registration, credential changes or financial operations should run
until that request is resumed. T82 remains open; PR #96 remains unmerged.

Artifacts are copied into ignored local
`build/ticket82-checkpoint-20261102/`, including `full-suite/pause-checkpoint.json`,
the partial full-suite log and browser screenshots. The original `/tmp` copies
also remain. Screenshots contain private build context and must not be published
as repository evidence. The code fix is already on `origin/staging/18-enterprise`;
this checkpoint documentation is committed locally for the next continuation.

## Resumed checks — 2 November 2026

The owner resumed the work with the same pre-payment boundary and explicitly
required **no new commits or pushes**. Repository changes remain uncommitted
locally; private evidence is retained outside Git. Production promotion, PR
merge and live financial operations remain outstanding.

A read-only GitHub check confirmed PR #96 open and unmerged, from
`staging/18-enterprise@4a56e8e` into `18.0@2814e8f6`. Its existing description
still contains the earlier paused result; no PR metadata was changed during
this continuation. Use this local evidence update when refreshing it after
the owner's deferred push/release review.

- Recreated the Chrome group **T82 pre-payment**. The Production branch still
  reports `2814e8f6`; Staging reports `4a56e8e` on build **41044597**.
- The requested manual Production backup is now listed as completed at
  **2026-11-02 16:47:38 UTC**, with the original T82 comment and download/restore
  options. This establishes backup completion, not a tested restoration.
- Opening the observed Staging terminal frame directly restored shell access;
  the embedded project view remained at its loading message. Read-only checks
  confirmed `ODOO_STAGE=staging`, addon **18.0.1.0.8**, neutralization enabled,
  both Revolut reconciliation jobs inactive, method 11 archived and its keyless
  Environment authority 8 revoked. The inspection transaction was rolled back.
- Hosted source revisions: addon `4a56e8ee18e27bd1214a645016750f70cf25ad62`,
  Odoo `2982b5f44af03fae6a9888f20632c1cc19f623ba`, Enterprise
  `631c5aba59f5cc1e98b72747ee81641a767927fc`.
- Repeated precisely the three previously red browser cases and eight Chrome
  startup skips using unchanged code, assertions and timeouts: **11 tests,
  zero failures/errors/skips**, exit 0, 167.63 seconds. All eleven tours and
  their backend assertions passed. The same pinned runtime used a 2 GiB
  container cap; sampled available host RAM stayed above 4.83 GiB, one-minute
  load below 1.47 and full memory-pressure `avg10` below 0.14 percent. These results
  support a resource-sensitive failure explanation without proving its cause.
  The prior interrupted result remains recorded above.
- The final local full-suite invocation completed: **816 tests, zero failures/
  errors, one optional `pos_hr` skip**, exit 0. The completed result is recorded
  separately below; it does not repaint the interrupted invocation as a pass.
- The owner completed Revolut Business sign-in directly in the browser during
  the resumed work. No passcode or API key was entered or requested in chat.
  The **Test Guzman** business account contains the requested **Davai** location;
  its UUID was captured from the visible location-detail URL into an ignored,
  restricted local setup record. The **Devices** action displayed **You don't
  have access**; terminal identity and supported currency remain unverified.
  Merchant API settings show an existing masked token; it was not revealed,
  copied, regenerated or provisioned into Odoo. Production still needs the
  reviewed candidate before its Revolut configuration can be completed. Odoo's
  EUR setting and GBP prices in the portal do not establish terminal EUR support.
  The owner explicitly deferred terminal verification until tomorrow. Do not
  repeat it or enable the terminal/POS as part of this continuation.

Restricted artifacts are retained in ignored local
`build/ticket82-checkpoint-20261102/resume-focused/`; browser screenshots remain
private. No real payment or refund was sent to Revolut by these checks.

### Focused hosted selection

On Staging build **41044597**, ran native `odoo.tests.loader.run_suite()` with
`OdooSuite` from an Odoo shell, without module installation/update or a source
change. The shell process set `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1` and loaded
the repository's `docker/sitecustomize.py`; credentials and provider responses
were synthetic/mocked. The platform stage and neutralization were preserved.

The selection contains all ten `TestRevolutDatabaseCredentials` cases, all four
`TestRevolutDatabaseCredentialFlow` cases, `TestRevolutNeutralization`, the three
scheduled reconciliation cases from `TestRevolutPayment`, and the blocked-stage
connection-check serialization regression from `TestRevolutPaymentMethod`.

The initial invocation recorded **19 tests, zero failures, one error, zero
skips**, exit 1. The guard test failed during fixture creation: its default
`ODOO_REVOLUT_SECRET_TEST_TERMINAL` already belonged to a historical revoked
Sandbox authority. Creating a Production method under that same reference was
correctly rejected before the connection-check assertion. This was a fixture
collision on the populated build, not a demonstrated runtime guard failure.

The repeat isolated only that instance's payment-method factory reference with
a fresh `ODOO_REVOLUT_SECRET_T82_HOSTED_GUARD_` suffix. No shipped code, assertion,
timeout, credential rule or environment guard changed. The isolated singleton
passed, followed by the combined selection: **19 tests, zero failures/errors/
skips**, exit 0. Counts of payment methods, authorities, companies, users, native
orders, payment operations and refund operations matched before/after native
class cleanup. These counts do not independently prove equality of every field.
The shell's inspection transaction was rolled back.

A fresh post-test shell confirmed neutralization still enabled, both jobs
inactive, the original keyless fixture archived, authority 8 revoked and zero
remaining temporary guard authorities. No existing authority was repurposed or
unrevoked to accommodate the test.
An independent process with the same environment confirmed the repository's
`_reject_merchant_requests` wrapper was loaded.

Hosted logs remain at `/tmp/t82-resume-hosted.log`,
`/tmp/t82-resume-hosted-guard.log` and `/tmp/t82-resume-hosted-isolated.log`.
Private screenshots are retained outside Git in the local checkpoint directory.
This exercises mocked HTTP and direct cron recovery; it does not establish
fresh worker-restart, platform scheduling, backup restoration or live financial
acceptance. Existing T80 lifecycle evidence retains its original scope.

### Completed local full regression

One fresh full `/pos_revolut` invocation on the same pinned Odoo Community 18
runtime completed in **1,704.81 seconds**, Docker exit **0**, `OOMKilled=false`:
**816 tests, zero failures/errors**. Its only skip was
`TestSharedPosSessionAccess.test_employee_list_does_not_restrict_backend_user_rpc`
with reason **Run with pos_hr installed for employee-list characterization**.
There were no Chrome skips. The log records **127 successful browser tour
executions across 117 distinct test cases**, including all three previously
red cases and all eight previously skipped browser cases. No addon, assertion
or timeout change was needed.

All **174** frozen addon files match `4a56e8e` byte for byte, with no missing or
extra files. The run used synthetic credentials, blocked Merchant HTTP, a
read-only addon snapshot, a fresh disposable database and an internal network.
Odoo/PostgreSQL caps were 2 GiB/768 MiB and 4/2 CPUs, with no swap beyond the
memory limits. Samples recorded at least 4.03 GiB host RAM available, maximum
one-minute load 3.81, maximum full memory-pressure `avg10` 0.14 percent and
sampled Odoo peak 936,300,544 bytes. Resource observations do not establish the
root cause of the previous failing/interrupted run.

The first monitoring process ended with status 143 for an unknown reason.
Monitoring reattached to the **same** test container; the test was not restarted.
The largest sampling gap was 107.67 seconds, so this is not an uninterrupted
resource trace. The final Docker exit and full aggregate were captured
independently. All task-owned containers, networks and volumes were removed
and verified absent; the watchdog exited. No test work remains running.

Read-only private artifacts are retained in ignored local
`build/ticket82-checkpoint-20261102/resume-full/`, including
`final-summary.json`, `full-result.json`, the full log, source inventory,
commands, resource observations and cleanup evidence. Local Community results
and the 19 mocked hosted cases do not establish live Enterprise terminal
acceptance. T82 remains open for the deferred terminal/currency checks,
reviewed Production deployment and credential setup, agreed financial amounts,
real sale, partial/remaining refunds and matching native/accounting completion.

Independent review of this continuation's local documentation delta against
`24f2801`: **Standards 0 findings; Spec 0 findings**. Whitespace and local
documentation links passed. `HEAD` remains `24f2801`; only this report is
modified in the tracked working tree. No new commit, push, PR metadata update,
merge or Production deployment was performed.

## Terminal and currency lookup — 3 November 2026

The owner resumed terminal/currency verification and retained the local-only,
no-commit/no-push boundary, stopping before any real payment or refund. This
supersedes the previous day's deferral of the terminal lookup, without approving
a deployment, credential provisioning or financial operation.

The owner completed fresh Revolut sign-in directly in Chrome. In the selected
**Test Guzman** business, **Merchant → More → Devices** again displayed **You
don't have access**, with the instruction to contact the account administrator.
No permission change or alternative route around that restriction was attempted.

**Merchant → More → Settings → Locations → Davai** opens the same location as
the previous checkpoint. Its visible detail panel contains address and opening
hours, with no terminal inventory or currency setting. The private location UUID
remains outside Git. The account name, location name, Odoo EUR setting and portal
GBP display do not prove a terminal's supported collection currency.

Consequently the terminal UUID, Davai assignment, online status, Pay at Counter
mode and EUR/GBP support remain **unverified**. Resume with an account that can
view Devices, or with the owner checking the terminal's details directly. Do not
start a payment to discover currency support. Reviewed Production deployment
and a usable server-side Merchant authority remain separate setup gates.

No Merchant token was revealed, copied, regenerated or saved; no device or Odoo
configuration changed; no real payment/refund was started. No code changed, so
the completed regression results above retain their scope and were not rerun.
Restricted screenshots are retained locally in ignored
`build/ticket82-checkpoint-20261103/`, including `devices-access-denied.png`.
This report remains the only tracked modification, uncommitted on
`codex/82-live-test-checkpoint`; integration target `staging/18-enterprise`.

## Other setup preflight — 3 November 2026

The owner deferred terminal verification again and requested all remaining
automatable work within the **local-only, no-commit/no-push, no-payment/refund**
boundary. Hosted inspection in this continuation was read-only; terminal lookup
was not repeated and no configuration was saved.

Fresh browser observations:

- Production `18.0` still reports `2814e8f6`. The database opens, About reports
  **Odoo 18.0+e (Enterprise Edition)** and expiry **3 December 2026**, and its
  company form shows **Davai / EUR**. This is not terminal currency verification.
- Production POS Revolut still offers **Activate**. Point of Sale, Restaurant
  and Invoicing also offered Activate in the Apps inventory. No application was
  installed, and the old Production addon was not used for live setup.
- The manual backup dated **2026-11-02 16:47:38 UTC**, with the original T82
  comment, remains listed with download/restore controls. Automatic daily and
  remote backups dated **2026-11-02 19:18:14 UTC** are also listed. No backup
  was downloaded or restored; restoration remains unverified.
- Staging still reports `4a56e8e` on build **41044597**, with the neutralized
  banner and deletion date **2 December 2026**. Its sole visible register,
  **Clothes Shop**, retains an open session and an empty **Revolut backend
  users** field. The settings show Card, Customer Account and Cash, automatic
  terminal validation enabled, and Tips disabled. The tip-product value was
  not visible, so this does not establish its configuration. The session was
  not closed or used, and its synthetic history was preserved.

Compared all **174** local addon files with `4a56e8e`: exact byte match, no
missing/extra files apart from excluded Python cache files. Addon tree remains
`7538c06c385716864f9a9d302b1c453caf63e89a`. No code changed, so the completed
816-test local suite and 19 mocked hosted cases were not repeated. This lookup
does not add fresh cron scheduling, worker restart or database-copy evidence.

Prepared the remaining configuration **locally only**, with unresolved values
explicitly unset:

| Item | Prepared value or gate |
| --- | --- |
| Company and currency | Davai; EUR preferred, collection currency unverified |
| Merchant and location | Test Guzman business; Davai location UUID retained privately |
| Register and journal | Proposed new Davai T82 register and Revolut Davai bank journal, after reviewed installation; no records created |
| Credential authority | Proposed unique `ODOO_REVOLUT_SECRET_DAVAI_T82_20261103` reference, Database source, Production environment, Davai company; no key included or authority created; check uniqueness before use |
| Terminal | UUID, online status and mode unset; verification deferred |
| Checkout | Automatic terminal validation enabled; restaurant Add tips after payment disabled; select/validate an untaxed tip product and Product Price precision before use |
| Operators | No identities or grants applied; select the intended till user/supervisor and approve access before saving grants |
| Reconciliation | Jobs remain unconfigured in the prepared setup; enable deliberately on the approved operational installation after reviewing unresolved attempts and cron user |
| Financial amounts | Sale, partial refund and remaining refund amounts unset; no authorization inferred |

The private setup file has `apply_allowed=false` and `ready_for_payment=false`;
it is a preparation record, not an executable deployment script. A local
PR-description draft includes the completed regressions and outstanding live
gates; GitHub PR #96 was not edited. These files and screenshots are ignored,
restricted artifacts under `build/ticket82-checkpoint-20261103/`:
`davai-setup-prepared.json`, `setup-source-check.json` and
`pr-96-description-draft.md`.

Further operational setup requires the reviewed candidate deployed and installed
on the intended Production-stage trial, a usable approved Merchant authority,
the deferred terminal/currency verification and the intended operator. None of
those gates can be completed solely through local changes. Do not upload code
directly to the server, enable test-copy Production access, promote synthetic
fixtures, or install the older Production source to bypass the release step.
No Enterprise registration, credential/permission change, deployment, commit,
push, PR update or financial operation was performed in this continuation.

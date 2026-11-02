# Ticket 80 — Odoo.sh staging lifecycle evidence

Verification recorded on 2026-11-02; external gates remain open. Base and integration target:
`staging/18-enterprise` at `fdfa74596f2445e0a54a1206cb28a052386cda01`.
Work branch: `codex/80-odoo-sh-staging`. Addon candidate: `18.0.1.0.8`,
unchanged application/test bytes from that base. No production deployment.

## Hosted identity and installation

Authenticated Odoo.sh access succeeded through the existing GitHub session.
Staging build **40905864** reports the exact candidate above; its web shell
confirms `ODOO_STAGE=staging`. Runtime is Odoo **18.0+e**, Ubuntu 24.04.
Odoo revision: `2982b5f44af03fae6a9888f20632c1cc19f623ba`.
Enterprise revision: `631c5aba59f5cc1e98b72747ee81641a767927fc`.
Private host/database details and credentials are omitted here.

The database displayed the neutralized banner before installation. Apps had
only the initial Apps/Settings launcher; POS Revolut was available but inactive.
Removed the Apps filter, searched Revolut and activated it. After the native
server reload, both the Apps Upgrade/Uninstall controls and a fresh Odoo shell
confirmed installed version `18.0.1.0.8`. The shell confirmed the neutralized
parameter remained true. Post-install native counts were two partners, one
product, no POS orders and no accounting moves; these counts are **not** a
pre/post populated-data preservation test.

Direct SSH timed out. The branch's embedded terminal remained loading; opening
its observed webshell endpoint directly supplied a working terminal. Hosted
commands used the platform's existing configuration/addon paths, not Docker.

## Registration gate

**Scope clarification, 2026-11-02:** The owner confirmed this project is only for
deployment testing, not operational use. The active trial is sufficient for the
current evaluation. Permanent registration is not a ticket 80 blocker; record
the verified trial status and expiry instead. Earlier registration attempts
below remain historical evidence. Ticket 82 retains appropriate registration
before live financial use in a future identified client environment. The owner
will not activate a paid Enterprise production plan on the current test project
or operate client hosting. The deliverable is the addon for clients. This does
not establish permanent entitlement or
extend either project or database trial limits. Official reference:
[Odoo.sh trial scope and limits](https://www.odoo.sh/faq).
The five-file scope clarification passed Standards and Spec reviews with zero
findings, relative Markdown-link checks and `git diff --check`. No application
code changed or application tests were rerun for this clarification.

Staging Settings shows Enterprise edition and expiration **2026-11-30**.
Production Home says registration is available after installing the first app.
No subscription code was entered and no database binding was changed. The owner
was given the production-only first-app/registration instructions. Subscription
activation and the intended production binding remain externally unverified;
an expiration date is not sufficient proof. A later read-only production check
showed Contacts installed, the first-app message absent, and expiration
**2026-12-03**. No staging copy was registered.
The project Settings already contains a masked Subscription Code; only its
presence was recorded. This does not establish the production database's
binding or distinguish trial/project entitlement from active registration.

After the owner connected the browser, a read-only shell on production build
**40905690** established `ODOO_STAGE=production`, no neutralization, no configured
`database.enterprise_code`, expiration reason **trial**, and expiration
**2026-12-03 10:43:31**. The database remains unregistered. The installed
Enterprise Home template hides its registration panel until 30 trial days
remain; at this check it had 31 days. Thus the absent banner and installed
Contacts app do not prove registration. No expiration value was changed to
force the panel to appear.

Automatic approval review rejected the proposed submission of the existing
project subscription code to Odoo's registration service from production,
because the broader ticket request did not explicitly authorize that sensitive
transfer and production state change. The command was rejected before execution.
Explicit approval for that exact operation was requested. No code was submitted
before the owner approved it in the subsequent continuation below.

### Approved registration attempt

The owner explicitly approved submitting the existing project code to Odoo's
registration service for the intended production database. Used a hidden
`getpass` prompt in the production Odoo shell; no code was placed in a command,
printed, committed or copied into a staging database. Confirmed the project's
password input held a non-mask value before diagnosing the response.

Called native `publisher_warranty.contract.update_notification(cron_mode=False)`
after setting the code within the shell transaction. The method returned true,
but registration did **not** succeed: expiration reason remained `trial`, date
remained **2026-12-03 10:43:31**, and the response did not indicate another linked
database. Rolled back rather than retaining an unaccepted code. A second
rollback-only call to native `_get_sys_logs()` classified the response without
printing it: `enterprise_info` present, returned Enterprise code absent,
expiration reason absent, unchanged date, no linked-database indication and
zero messages. Native update defaults an absent reason to `trial`; a true return
only establishes completion of the notification call, not accepted registration.

No purchase, renewal, upsell quotation acceptance, resource-allocation change
or financial operation was performed. These observations do not establish the
owner's existing subscription price or entitlement. The project activation code
may differ from the required Enterprise contract code; the response does not
establish why this code was unaccepted. The owner will ask the subscription
holder to confirm or register the intended production database privately.

A separate final read-only shell confirmed production, no neutralization,
`enterprise_code_configured=false`, reason `trial` and the unchanged expiration
date. Retained `/tmp/ticket80-production-registration-result.jpg` outside Git;
it shows safe status flags with private build context, not the code. Both
Standards and Spec continuation reviews reported zero new findings. Relative
documentation links and `git diff --check` passed; no addon code changed or
application test suite was rerun for this documentation-only continuation.

### Environment boundary clarification

Addon installation, focused permissions/credential tests, mocked payment/refund
recovery, HTTP restart, scheduled credential probes, neutralization and populated
first-install checks were performed on **Staging** builds 40905864/41044597.
The **Production** build 40905690 was used for registration-status inspection
and the explicitly approved registration/diagnostic attempts above, both rolled
back. No addon production deployment or live Revolut operation was performed.
That registration investigation was unnecessary for the clarified test-only
goal. Further addon acceptance stays on Staging; the test project's Production
database is only the source for fresh staging copies, not a client live database.
This six-file client/environment clarification passed independent Standards and
Spec reviews with zero findings, relative-link checks and `git diff --check`.
It changed documentation only; no application tests or hosted mutations were
needed or performed for the clarification.

## Hosted focused tests

Commands and controlled setup are in the [runbook](../odoo-sh-staging.md).
The subprocess network guard and synthetic credentials were used. Tests mock
provider traffic; no real Merchant API or terminal is part of these checks.

| Run | Result and interpretation |
| --- | --- |
| `/tmp/ticket80-focused.log` | Exit 1; 17 selected tests, zero failures, two errors (Odoo stats: 27 including setup). The two pre-copy Production payment/refund fixtures could not construct their source transaction on an already neutralized staging database. The intended runtime guard rejected them before HTTP. This run remains failed. |
| `/tmp/ticket80-sandbox.log` | Exit 1; 18 selected tests, one failure, zero errors (stats: 26). Pending database-key payment/partial-refund recovery hit `SerializationFailure` in native cron `_try_lock`; a concurrent transaction updated the cron row. |
| `/tmp/ticket80-controlled.log` | Exit 0; same 18 selected tests, zero failures/errors (stats: 26). Deactivated only the two addon crons, committed that setup, then reran the same selection. Fixtures invoke both jobs explicitly through `method_direct_trigger()`. No assertion or timeout changed. |

The passing selection exercises administrator-only database-key RPC/export,
company/terminal isolation, source exclusivity, immutable rotation, full/partial
refunds using the original key, payment/refund job invocation, payment network
backoff and lost-intent duplicate prevention. The neutralization case runs the
real framework SQL hook twice across two companies/both credential sources,
checking removed Production keys, revoked authorities, archived methods,
inactive jobs and usable Sandbox configuration.

Cron isolation resolved this observed test conflict; it does not establish that
all hosted concurrency behavior is covered. The module creates cron records on
first installation after neutralization, so those new records required an
explicit state check. The runbook includes that step.

## Payment restart recovery

Created an isolated synthetic US/USD company, native generic chart and warehouse.
Created a Sandbox **Database** authority with reference
`ODOO_REVOLUT_SECRET_TEST_TERMINAL` and a fake key. Asserted that reference was
absent from the process environment before seeding. No persistent shell export,
custom daemon or server source modification was used.

Executed the existing `restart_seed.py`, `restart_wait.py` and
`restart_verify.py` in separate Odoo shells. Logs:
`/tmp/ticket80-seed.log`, `/tmp/ticket80-wait.log`,
`/tmp/ticket80-verify.log`. All three exited zero with their expected markers.
The seed commits two actual authorized carts and exactly four mocked financial
POSTs. The delayed second phase retains captured zero/nonzero-tip payments as
pending while the report is processing, rejects another charge/cart edit and
makes no financial POST. The final phase authenticates explicit tip reports,
projects once, retains the same authority/attempt/ledger/provider references
and makes no POST, including repeated start/poll calls. Native orders remain
draft until cashier completion as designed.

Initial `odoosh-restart http` and `odoosh-restart cron` attempts reported no live
workers and aborted. Those attempts do **not** prove a restart. Reloaded the
staging module page to wake HTTP, then `odoosh-restart http` confirmed all HTTP
workers stopped and would respawn on request before the final fresh-process
verification. A running platform cron-worker restart has not been demonstrated;
controlled job execution is established by the focused tests above.

### Subsequent platform scheduler observation

On build 41044597, created a temporary native `ir.cron` action named
`Ticket 80 controlled credential worker probe`, using a new Sandbox Database
authority with a synthetic key and no provider calls. Its code resolved that
exact authority through `_resolve_secret()` and incremented a durable counter
only when the fake key matched. The reference was absent from the setup shell's
environment. Scheduled it using native `_trigger()`; no shell manually invoked
the action. A fresh observer confirmed one execution with last call
**2026-11-02 11:30:09 UTC**.

Two initial setup attempts rolled back because the action used an assertion
opcode rejected by native safe evaluation. Changing its newline construction
did not resolve that rejection. Correcting this test-only action to an explicit
conditional allowed normal scheduling; no application code or safety boundary
was changed.

The direct cron restart still reported no live worker. Added a bounded
45-second observation window to the synthetic action and watched for a worker
using the supported `odoosh-restart cron` command, at five-second intervals
for 36 attempts. The watcher reported
`T80_PLATFORM_CRON_NOT_AVAILABLE_WITHIN_180_SECONDS`. A fresh observer then
reported **four** successful credential reads, zero cron failures and last call
**11:33:55 UTC**. Thus platform-triggered credential access is demonstrated,
but a successful platform cron restart is still not observed. This probe does
not replace the financial recovery checks above.

`T80_PROBE_CLEANUP_OK` confirmed the final counter remained four, the probe
was inactive, its synthetic authority was revoked, both addon jobs were inactive
and addon `18.0.1.0.8` remained installed. Removed the observation-window code
from the inactive probe. Retained `/tmp/ticket80-platform-cron-probe.jpg`
outside Git; it contains private build context and must not be published
unredacted. No custom background daemon or application source change was used.

## Refund restart and delayed job

Completed the zero-tip synthetic original through native
`action_pos_order_paid()`, saved a 6.17 partial return with `sync_from_ui`, and
started its refund through `revolut_start_refund` with an explicit base allocation.
The successful seed asserted exactly one original-order GET and one refund POST,
both mocked and using the original Database authority. The attempt/checkpoint
was committed before the next process. Log: `/tmp/ticket80-refund-start.log`,
exit 0, `T80_REFUND_SEED_OK`.

Two earlier ad hoc setup runs failed: a `Command.clear()` tax command was
rejected by the financial snapshot interface, then an assumed native order name
did not match Odoo's assigned name. Before the successful start, asserted that
the same saved return was still draft and that no refund attempt existed for
its original payment. No financial assertion or application code was changed.
Failed logs: `/tmp/ticket80-refund-seed.log` and
`/tmp/ticket80-refund-seed-corrected.log`.

After a successful HTTP restart, a new shell loaded that pending refund with
the environment key still absent. Set its next reconciliation one hour ahead,
committed and explicitly invoked the refund cron: no request for that refund
was made and it stayed pending. Set its schedule two hours in the past and
committed; invoked the same job with a GET-only mock returning its completed
provider record. The synthetic timestamp exercises overdue scheduling; it is
not a claim of two hours' elapsed wall time.

The immediate observer incorrectly retained its earlier repeatable-read
snapshot: `invalidate_all()` alone does not begin a new database transaction.
That ad hoc run exited 1 at its pending/verified assertion
(`/tmp/ticket80-refund-recovery.log`). A separate fresh shell then confirmed
the cron's committed **verified** result, same provider/original/attempt IDs,
617 minor units and original Database authority. Repeated public start and poll
returned that same verified attempt with **zero HTTP**, and only one refund
record exists for its original payment. `/tmp/ticket80-refund-fresh.log` exited
0 with `T80_REFUND_FRESH_OK`. The failed observer remains recorded; no rewind,
replacement refund or relaxed assertion was used.

## Installed-copy neutralization

On the controlled staging database, created two synthetic Production Database
authorities/methods in different companies. Snapshotted the existing Sandbox
payment/refund attempts, financial/provider identities, native orders, lines
and tenders. Invoked the real framework neutralization helper twice. Both
executions removed the synthetic live keys, revoked their authorities, archived
their methods and disabled both crons. Exact financial/native snapshots stayed
equal; the Sandbox database key remained available. Production connection checks
raised the runtime restriction with **zero HTTP**.

`/tmp/ticket80-copy-cleanup.log`, exit 0, `T80_COPY_CLEANUP_OK`.
Local screenshot `/tmp/ticket80-copy-cleanup.jpg` retains the executed shell
excerpt and marker outside Git. This hosted history was generated as Sandbox;
the local pre-copy fixtures establish preservation of unresolved Production
history separately. No live history was created by bypassing staging protection.

## Platform rebuild and populated first installation

Requested and confirmed a rebuild of the controlled staging branch. New build
**41044597** completed on the same `fdfa745` candidate. Its shell confirmed
`staging`, a true neutralized parameter, `pos_revolut` uninstalled and no
Merchant-authority table. The previous synthetic company and restart checkpoint
were absent. This demonstrates replacement of staging-only setup by the fresh
production copy; it does not claim that staging-only attempts survive rebuilding.
Retained the pre-install neutralized marker before installing the addon.

Installed native POS/Restaurant with `--init=point_of_sale,pos_restaurant`, then
ran the existing `native_install_seed.py`. It commits a synthetic company,
manager, customer, product, register, paid native sale and posted invoice,
retaining exact snapshots. Installed the candidate with `--init=pos_revolut`.
A separate shell running `native_install_verify.py` preserved every snapshotted
native value, including POS sale lines/tenders and posted invoice lines.
All commands exited zero. Logs: `/tmp/ticket80-native-install.log`,
`/tmp/ticket80-native-seed.log`, `/tmp/ticket80-reinstall.log` and
`/tmp/ticket80-native-verify.log` on build 41044597.

Next ran the unchanged `neutralized_install_verify.py` in another process:
**passed**, exit 0, `NEUTRALIZED_FIRST_INSTALL_VERIFIED`. Both newly entered
Production Database keys and valid-looking environment keys were blocked with
zero HTTP/reservations, while mocked Sandbox discovery succeeded. This used the
real pre-install marker established before the authority table existed, not an
addon neutralization hook retrospectively applied to installed records. Log:
`/tmp/ticket80-first-install-guard.log`.

For those shell fixtures, the invocation was:

```bash
ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1 PYTHONPATH=/home/odoo/src/user/docker \
  odoo-bin shell --no-http --max-cron-threads=0 --shell-interface=python \
  --log-level=error < /home/odoo/src/user/pos_revolut/tests/FIXTURE.py
```

The two installation commands used the same guard/environment and
`odoo-bin --no-http --workers=0 --max-cron-threads=0 --stop-after-init`, with
the respective `--init` argument above. These commands run in dependency order,
each in a fresh process on the selected staging database.

The rebuilt Odoo and Enterprise Git revisions matched those recorded for build
40905864. The final shell rechecked installed `.8`, neutralization and both addon cron
states. Left the rebuilt staging database installed, with native fixture history
preserved and both Revolut jobs **inactive**. The first-install guard's synthetic
keys/methods were rollback-only. Screenshot:
`/tmp/ticket80-rebuilt-verification.jpg` (outside Git). Hosted logs/screenshots
can contain private build context; do not publish them unredacted.

## Local regression and review

Pinned Odoo Community `18.0.20261015`, PostgreSQL `16.14`, candidate `fdfa745`,
internal Compose network `10.237.180.0/24`, project
`odoo-revolut-ticket80-local`. Real Merchant HTTP blocked; synthetic credentials
and mocked provider responses only. These results support the hosted checks;
they do not establish Enterprise/platform behavior by themselves.

- Host tooling: **75 tests, zero failures/errors, three PDF-dependency skips**,
  exit 0. `/tmp/ticket80-local/host.log`.
- JavaScript: **146 passed**, zero failures/skips, exit 0.
  `/tmp/ticket80-local/js.log`.
- Full addon suite: **815 cases, two failures, zero errors, two skips**, actual
  container exit **1**. `/tmp/ticket80-local/full.log`,
  `/tmp/ticket80-local/full-exit`; retained browser artifacts in
  `/tmp/ticket80-local/browser-artifacts`.
- Existing restart fixture: **passed**, exit 0 across three Odoo processes,
  including the original environment-key source, stable identities, zero/nonzero
  tip report recovery and no financial replay. `/tmp/ticket80-local/restart.log`
  and `/tmp/ticket80-local/restart-exit`; temporary runner preserves the source
  assertions and uses internal subnet `10.237.181.0/24`. Disposable projects
  were cleaned; logs/artifacts remain. No additional local first-install runner
  was needed after the hosted fixture passed.

Exact local command record: `/tmp/ticket80-local/commands.txt`. Full suite:

```bash
docker compose -p odoo-revolut-ticket80-local -f /tmp/ticket80-local/compose.yaml \
  run -d --name odoo-revolut-ticket80-local-full odoo \
  --database ticket80 --init pos_revolut --stop-after-init --workers 0 \
  --max-cron-threads 0 --log-level warn \
  --log-handler odoo.tests.result:INFO --log-handler odoo.tests.stats:INFO \
  --log-handler odoo.addons.pos_revolut:INFO --test-tags /pos_revolut
```

Host tooling ran `python3 -m unittest discover -s tests -v`; JavaScript ran
`node --test --test-isolation=none pos_revolut/static/tests/*.test.mjs`.

The full run failed the existing
`TestRevolutVerifiedCheckout.test_terminal_busy_inflight_snapshot_reconciles_after_reload_without_duplicate_charge`
at its initial Start PoS control, before the financial scenario, and
`test_verified_payment_checkout_timeout_recovers_without_second_charge` waiting
for the Check status modal (step 12/25). One optional `pos_hr` skip and a Chrome
debugger-startup skip in
`test_terminal_busy_line_can_be_removed_for_cash_without_second_dispatch`
were recorded. Host memory/swap saturation was observed, but cause remains
unestablished. No assertion/timeout was relaxed and this run remains red;
[ticket 84](../tickets/needs-triage/84-investigate-checkout-browser-full-suite-failures.md)
retains the release gate.

No configured type checker applies to these documentation-only changes.
`git diff --check` and relative Markdown-link checks passed. Independent
Standards and Spec reviews compared `fdfa745...2064957`: Standards found zero
documented-standard violations/baseline smells; Spec found one minor
overstatement of native stock preservation, corrected above to the actual POS
and invoice snapshots. Also narrowed the concurrency observation to a
transaction, without claiming an identified worker. Follow-up reviews of
`fdfa745...1a6c751` confirmed **zero remaining Standards findings and zero
remaining Spec findings**.

The registration/scheduler continuation changed documentation only. Relative
Markdown-link checks and `git diff --check` passed; no application tests were
rerun after the full-suite run above. Independent final Standards and Spec
reviews of `fdfa745...2fff881` plus the four-file continuation diff reported
**zero new findings** on each axis. At that review, registration and cron restart
remained unchecked; the owner's later test-only clarification resolves the
registration requirement as recorded above.

## Unresolved gates

The database remains a confirmed unregistered trial; its verified status is
accepted for the owner's current test-only scope. Permanent registration is
outside this test project's scope; any future ticket 82 activation belongs to an
identified client environment rather than blocking this evaluation. A running platform
cron-worker restart was unavailable; successful platform-scheduled credential
reads, manual financial cron invocation and HTTP restart coverage do not close
that gap. Ticket 80 stays claimed/open. This report does not authorize promotion
to `18.0` or resolve ticket 84.

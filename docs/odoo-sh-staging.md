# Odoo.sh staging lifecycle

Enterprise work starts from and returns to `staging/18-enterprise`. Keep
`18.0` for the reviewed production release: pushing there deploys production.
Use this runbook with [Installation](installation.md), not instead of it.
Record results separately with the exact source revision, addon version, build,
commands, results and limitations. See [Validation](validation.md).

## Identify the database and registration gate

In Odoo.sh, select the staging branch and record its exact Git revision, build
identifier, Odoo/Enterprise revision and date. Open **Connect** from that build;
verify the neutralized database banner before installing or configuring it.
The build's green status establishes successful startup, not addon test success.

In its web shell, check only the necessary values; never dump the environment
or all system parameters:

```bash
printenv ODOO_STAGE
git -C /home/odoo/src/user rev-parse HEAD
git -C /home/odoo/src/odoo rev-parse HEAD
git -C /home/odoo/src/enterprise rev-parse HEAD
```

The stage must be `staging`. Do not override the platform stage or clear
`database.is_neutralized`. Check **Settings → About** for Enterprise edition and
expiration. An expiration date alone does not confirm the subscription's
production database binding.

For a test-only evaluation, an active trial is sufficient: record its status and
expiry without treating permanent registration as a staging-test prerequisite.
The owner's current project is used only for trial testing of the reusable
addon; no permanent activation code or client rollout is required for delivery.
The production registration instructions below apply only to a future operational
deployment, not this test campaign.
Odoo.sh trial projects are time-limited and may be deleted after expiry; retain
test evidence outside the build. Continued hosting beyond the trial and actual
operational deployment require the appropriate entitlement. Keep a reference
test project separate from client hosting. Real terminal payment/refund testing
on the existing Odoo.sh Enterprise trial is tracked separately in
[T82](tickets/ready-for-human/82-activate-odoo-sh-and-check-payment-refund.md),
using the appropriate operational trial database without bypassing stage or
neutralization guards. No second Enterprise installation is assumed. A branch labelled Production can still be
the source of a temporary test project; that label does not mean live business use.

Perform addon installation, permission, payment/refund, restart, reconciliation
and copy acceptance on **Staging**, using synthetic data and mocked provider
traffic. A reference test project's **Production** branch can supply the source
database for staging copies. Do not deploy or configure the addon there merely
to finish staging acceptance.

The subscription owner checks registration on the intended **production**
database when permanent activation is needed. If its Home page requires a first
app, the owner installs an intended standard app before entering the subscription
code in the registration banner.
Do not deploy Revolut to production to unblock staging registration. If the
subscription is already attached elsewhere, resolve the intended production
identity with the owner before unlinking it. Never register the staging copy
as another active production database. Keep subscription codes and database
identifiers in restricted records.

Browser access and project-level subscription configuration do not prove database
registration. A restricted read-only shell check can report whether
`database.enterprise_code` is populated, plus `database.expiration_reason` and
`database.expiration_date`, without exposing the code. A `trial` reason and an
absent code mean registration is still incomplete. The Enterprise Home panel
can be hidden while more than 30 trial days remain; do not alter expiry values
to make it appear. When permanent activation is needed, have the owner complete
registration, or obtain explicit authorization to send the existing project code
to Odoo's registration service
for the intended production database. Do not include that code in commands,
logs or repository evidence.

## Install and repeat after a rebuild

1. Close test POS sessions and retain any staging evidence needed before a
   rebuild. Use the reviewed candidate on the staging branch.
2. In **Apps**, remove the default **Apps** filter, search **Revolut**, and
   activate **POS Revolut**. Native POS and Restaurant dependencies install with
   it. Refresh after the server reload; confirm **Upgrade/Uninstall** controls
   and the installed version against the identified release candidate.
3. Inspect the original companies, customers, products and financial documents
   against a pre-install baseline. Do not replace the database with demo data
   or count a fresh empty database as populated-data preservation evidence.
4. Create a dedicated synthetic company/register and a **Sandbox**, **Database**
   Merchant authority for controlled tests. Follow the installation guide for
   journals, register grants, automatic validation, Tip Product and terminal
   bindings. Use synthetic UUIDs and fake keys with provider HTTP mocked.
5. Deactivate the two addon scheduled actions before controlled test runs;
   invoke only the required jobs explicitly under the mock. First installation
   after neutralization can create active addon crons from module data, so
   inspect their actual state rather than assuming neutralization disabled
   records which did not yet exist.

A staging push/rebuild starts from a fresh production copy. Staging-only
installation, company setup, keys, grants, jobs and fixture attempts disappear
unless present in that source. Repeat setup for every new build. Copying and
restarting are different checks: a restart must retain the same database and
attempts; a rebuild need not retain records created only on staging.

## Mocked acceptance and controlled jobs

The repository's existing Odoo test selection covers administrator-only
credential RPC/export, company/terminal boundaries, original-key recovery after
rotation, full/partial refunds and payment cron backoff/lost responses. Run it
only on a controlled staging database, with no simultaneous module update.
The repository network guard rejects any unmocked Merchant HTTP in the test
process; its shell environment is not configuration for running Odoo workers.

```bash
ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1 \
ODOO_REVOLUT_SECRET_TEST_TERMINAL=test-only-not-a-credential \
PYTHONPATH=/home/odoo/src/user/docker \
odoo-bin --no-http --workers=0 --max-cron-threads=0 --stop-after-init \
  --update=pos_revolut \
  --test-tags='/pos_revolut:TestRevolutDatabaseCredentials,/pos_revolut:TestRevolutDatabaseCredentialFlow,/pos_revolut:TestRevolutNeutralization,/pos_revolut:TestRevolutPayment.test_scheduled_reconciliation_verifies_payment_without_browser,/pos_revolut:TestRevolutPayment.test_scheduled_network_error_backs_off_without_new_dispatch,/pos_revolut:TestRevolutPayment.test_scheduled_reconciliation_never_replays_lost_intent_creation' \
  --log-level=warn --log-handler=odoo.tests.result:INFO \
  --log-handler=odoo.tests.stats:INFO > /tmp/ticket80-controlled.log 2>&1
```

Inspect the exit status, final test summary and failures, not just module load.
Keep the two crons inactive during this selection: its fixtures call
`method_direct_trigger()` themselves. A live cron worker can conflict with those
transactions. This does not justify removing cron locks or weakening assertions.

The copy-payment/refund fixtures that first create mocked **Production**
transactions belong on an isolated source database before neutralization. They
cannot seed those transactions on an already guarded staging database. Preserve
such failures as fixture limitations; never bypass the runtime guard to make
them pass. The whole-database key cleanup test above can run on staging.

For manual controlled runs, the job XML IDs are
`pos_revolut.ir_cron_reconcile_payments` and
`pos_revolut.ir_cron_reconcile_refunds`. From an Odoo shell, invoke
`env.ref(XML_ID).method_direct_trigger()` only while provider calls are mocked.
Check attempt state, original credential/provider references, reservations,
dispatch counts and the next reconciliation time before and after each run.
Exercise an overdue pending attempt, a repeated invocation, a provider error
and a later successful observation. A job firing without an eligible attempt
does not demonstrate recovery.

Odoo.sh may schedule staging jobs only a few times a day and may terminate
workers. The module's one-minute interval is not a hosted timing guarantee.
Delayed verification must retain uncertainty and prevent replacement dispatch.
Do not install a custom background daemon or change financial assertions/timeouts
to make scheduling appear successful.

## Restarts and copies

Use the platform's web shell if SSH is unavailable. `odoosh-restart --help`
lists the supported services; restart staging HTTP and cron separately:

```bash
odoosh-restart http
odoosh-restart cron
```

Inspect the command's message. An absent worker makes the command abort; an
exit status alone does not establish a restart. Load a staging page to wake an
HTTP worker, then restart it and load another page to confirm service recovery.
If the platform has no live cron worker, record that limit separately from
explicit `method_direct_trigger()` coverage.

For bounded native cron-worker interruption/replacement coverage, use
`pos_revolut/tests/cron_restart_fixture.py` with `cron_restart_worker.py` on a
disposable staging build. These standalone fixtures do not change addon code
or create a persistent service. Keep both addon cron records globally inactive
throughout: provider mocks are process-local and must not race a platform job.
Quiesce administrative edits while seeding: the fixture snapshots and restores
existing group implications, user memberships and shared product taxes affected
by native company/chart/product setup, including when setup fails after a commit.
The launcher uses native `PreforkServer.worker_spawn(WorkerCron, ...)`, startup,
`process_work`, signals and shutdown. Only scheduler selection is replaced
inside the test process, dispatching the actual inactive addon actions through
`method_direct_trigger()` under their configured cron user.

Copy the two new files and unchanged `restart_seed.py`, `restart_wait.py` and
`restart_verify.py` from the reviewed repository into a temporary source
directory. Verify their hashes; do not edit installed application files. Each
of the following snippets runs in a separate Odoo shell with
`ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`,
`PYTHONPATH=/home/odoo/src/user/docker`, `--no-http --max-cron-threads=0
--shell-interface=python --log-level=error`. Use a new result directory and
retain each process's actual exit status and log.

```python
# Process one: same committed attempts, Database key, no environment export.
import sys
sys.path.insert(0, '/tmp/ticket80-native-cron-src')
from cron_restart_fixture import seed
seed(env, '/tmp/ticket80-native-cron-run')
```

```python
# Process two: hard total budget; native worker death and replacement.
import sys
sys.path.insert(0, '/tmp/ticket80-native-cron-src')
from cron_restart_worker import run
run(env, '/tmp/ticket80-native-cron-run', timeout=200)
```

```python
# Process three: new transaction, exact durable identities and zero-HTTP replay.
import sys
sys.path.insert(0, '/tmp/ticket80-native-cron-src')
from cron_restart_fixture import verify
verify(env, '/tmp/ticket80-native-cron-run')
```

The seed reuses existing restart carts and explicit tip reports, then starts a
617-minor-unit partial refund against the verified zero-tip source. The remaining
payment has a 300-minor-unit tip awaiting final report evidence. A failed seed
must retain its checkpoint; never reseed financial dispatches to hide a failure.
The fixture can resume its inspected committed source and saved return without
repeating dispatches. After a failed worker run, retain its markers and inspect
which original attempts are still pending before deciding how to resume. Do not
reset verified financial evidence or create replacement attempts to obtain a pass.

The supervisor kills a PID-bound native worker during a mocked GET, then starts
a different native worker. Recovery must respect the original payment's real
60-second observation lease: the early cron call makes zero HTTP and the test
waits for actual expiry without editing lease fields or constants. It separately
interrupts and recovers the partial refund. Provider mocks reject every POST,
unexpected host/path and wrong synthetic Authorization value. A hard timeout
cleans up the test's process group. Check lifecycle markers, fresh financial
identities/counts and replay assertions; do not treat worker startup as a pass.
This proves the bounded native-worker lifecycle on the hosted database, not a
successful platform-managed `odoosh-restart cron` command or its scheduling SLA.

Use `restart_seed.py`, `restart_wait.py` and `restart_verify.py` under
`pos_revolut/tests/` for committed payment recovery across fresh Odoo shells.
For database-source coverage, create the synthetic Sandbox authority for
`ODOO_REVOLUT_SECRET_TEST_TERMINAL` with source **Database** before seeding,
without exporting that variable. Run these fixtures in an isolated synthetic
company with a native chart, warehouse and register setup. Each phase must
complete before the next starts. Retain its marker and unchanged attempt IDs;
the final fixture checks original references, tips, dispatch counts and replay.
Record refund restart coverage separately; these three files cover payments.

The adapter commits financial observations through owned cursors. An observing
shell can retain an older repeatable-read transaction even after
`env.invalidate_all()`. Commit intentional fixture setup first; after the
operation, use a new Odoo shell/transaction to inspect its durable result.
The existing restart fixtures end the old observing transaction with rollback
before invalidating caches. Never dispatch again merely to refresh a display.

For a database-copy check, distinguish these cases:

- A platform staging rebuild: verify a fresh production copy, neutralized flag,
  lost staging-only setup and repeatable first installation.
- A controlled source with the addon installed: retain synthetic pending
  payment/refund snapshots, apply Odoo neutralization twice, and compare their
  financial history while checking all companies' Production key cleanup,
  revoked authorities, archived methods and disabled jobs.
- A copy neutralized **before** addon installation: retain proof the addon was
  absent, then install and verify new Production keys of both sources still
  cannot dispatch. `scripts/test-database-neutralization` is the disposable
  local fixture; report local evidence separately from hosted evidence.

Never neutralize the production database. Do not infer history preservation
from a platform rebuild whose production source contains no addon history.
Copied live attempts stay uncertain and must be reconciled in production by
their original references. Use distinct Sandbox configuration for test traffic.

## Evidence and handoff

Retain build IDs/revisions, exact commands/tags, before/after snapshots, test
summaries, service restarts, cron invocation results and copy provenance.
Separate passed checks, failed runs, unexercised behavior and external gates.
Redact keys, subscription material, private host details and financial references
from repository records. Leave both addon jobs inactive after mocked acceptance
unless a separate controlled scheduling check requires them.

Official platform references, checked 2026-11-02:
[build/copy behavior](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/builds.html),
[shell commands](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/branches.html),
[worker and scheduling restrictions](https://www.odoo.sh/faq), and
[production subscription registration](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/create.html#register-the-subscription).

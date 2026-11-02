# Odoo.sh staging lifecycle

Enterprise work starts from and returns to `staging/18-enterprise`. Keep
`18.0` for the reviewed production release: pushing there deploys production.
Use this runbook with [Installation](installation.md), not instead of it.
Record results separately in [ticket 80's evidence](testing/ticket-80-odoo-sh-staging.md).

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

The subscription owner checks registration on the intended **production**
database. If its Home page requires a first app, the owner installs an intended
standard app before entering the subscription code in the registration banner.
Do not deploy Revolut to production to unblock staging registration. If the
subscription is already attached elsewhere, resolve the intended production
identity with the owner before unlinking it. Never register the staging copy
as another active production database. Keep subscription codes and database
identifiers in restricted records.

## Install and repeat after a rebuild

1. Close test POS sessions and retain any staging evidence needed before a
   rebuild. Use the reviewed candidate on the staging branch.
2. In **Apps**, remove the default **Apps** filter, search **Revolut**, and
   activate **POS Revolut**. Native POS and Restaurant dependencies install with
   it. Refresh after the server reload; confirm **Upgrade/Uninstall** controls
   and installed version `18.0.1.0.8` for the ticket 80 candidate.
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

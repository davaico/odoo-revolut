# Staging deployment and recovery

This runbook deploys a reviewed POS Revolut revision to the existing
`revolut` staging instance. It does not provision infrastructure, change
GitHub, or edit addon source on the VM. Infrastructure, backup storage,
tailnet access, and service ownership remain in `../odoo-hosting`.

## Safety model

`scripts/deploy-addon` creates the addon archive from an exact Git commit, not
from working-tree files. It requires a clean checkout and proves that the SHA
is contained in an explicit reviewed ref (`origin/main` by default). The target
verifies the archive checksum and installs it at:

```text
/opt/odoo-releases/revolut/staging/REVISION/pos_revolut
```

The existing `/opt/odoo-hosting/addons` entry in `addons_path` is never
rewritten. Its `pos_revolut` child is an atomic symlink to the selected release.
The deployer refuses to replace a normal file or directory at that path.

Before changing code, the deployer:

1. refuses active or uncertain Revolut financial operations;
2. runs the existing encrypted database and filestore backup service;
3. copies `/etc/odoo/odoo.conf` and the `odoo.service.d` drop-ins into a
   root-only local configuration snapshot;
4. stops Odoo, which quiesces checkout and every payment/refund dispatch;
5. repeats the financial-operation check after Odoo is fully stopped; and
6. leaves Odoo stopped if that final check, extraction, module update, or any
   earlier stopped-service step fails.

Financial operation models participate through the shared
`pos.revolut.financial.operation.mixin`. Its stored `deployment_blocking`
field is discovered generically by the deployment preflight. Future refund
operation models must inherit this mixin and define only states that cannot
change the provider's financial position as terminal. During the first upgrade
from a revision without the mixin, the deployer uses the known payment-state
fallback.

The offline install/update always uses `--stop-after-init --no-http
--workers=0`. Odoo is started only after that command succeeds. The deployer
then verifies the systemd service and the local `/web/login` endpoint. A failed
health check is reported as a deployment failure, although the service may
already be running and must be inspected.

## Prerequisites

- Use a trusted workstation with this repository and `git`, `ssh`, and `scp`.
- Fetch the current reviewed integration ref. Do not deploy an unreviewed
  feature-branch SHA.
- Use the approved root SSH target from the company tailnet inventory. The VM
  intentionally has no public SSH port.
- Confirm the staging profile is still `revolut` / `staging`, database
  `revolut_staging`, and Odoo package `19.0.20260908` in
  `../odoo-hosting/customers/revolut.staging.json`.
- Confirm `odoo-backup.service` is installed and the latest isolated restore
  check is successful. Repair backup infrastructure in `odoo-hosting`, not in
  this repository.
- Ensure no cashier is starting a checkout. The script performs authoritative
  preflight checks, but the maintenance window should still be announced.

## Server-only secret configuration

The deployer never accepts, transfers, or prints a Revolut secret. Provision it
through the staging host's root-only secret mechanism before installation. For
the native systemd layout, an operator may create a private environment file on
the VM:

```bash
install -d -o root -g root -m 0700 /etc/odoo-revolut
umask 077
${EDITOR:?Set EDITOR} /etc/odoo-revolut/revolut.env
chmod 0600 /etc/odoo-revolut/revolut.env
```

The file contains only the referenced environment variable and its value; do
not paste the value into a command, ticket, log, or this repository:

```text
ODOO_REVOLUT_SECRET_MAIN_TERMINAL=replace-in-editor
```

Add this reference through the existing Odoo systemd override management:

```ini
[Service]
EnvironmentFile=/etc/odoo-revolut/revolut.env
```

Then run `systemctl daemon-reload`. Configuration management for that override
belongs to `odoo-hosting`. In Odoo, store only the variable name
`ODOO_REVOLUT_SECRET_MAIN_TERMINAL` in the payment method.

## Install or upgrade an exact reviewed revision

From this repository:

```bash
git fetch origin
git status --short
REVISION="$(git rev-parse origin/main)"
git show --no-patch --format=fuller "$REVISION"
STAGING_SSH_TARGET="root@approved-tailnet-hostname"
```

`git status --short` must be empty. For the first installation, run:

```bash
./scripts/deploy-addon deploy \
  --revision "$REVISION" \
  --reviewed-ref origin/main \
  --ssh-target "$STAGING_SSH_TARGET" \
  --database revolut_staging \
  --customer revolut \
  --environment staging \
  --mode install
```

For an existing installation, use the same command with `--mode upgrade`.
Success output includes the exact revision, immutable release path, and the
configuration-backup path. Record all three in the change record. The uploaded
temporary archive is removed whether deployment succeeds or fails.

## Operator-controlled no-charge smoke check

The deployer itself never calls Revolut and cannot initiate a terminal charge.
After it succeeds, an operator performs this staging-only check:

1. Confirm the reported SHA equals the approved change and that the Apps view
   shows **POS Revolut** installed.
2. Open the existing retail POS configuration and start a session with only the
   already verified cash payment path needed for this check.
3. Create one ordinary staging order, pay the full total with **Cash**, and
   validate it. Record the POS order reference. This proves existing cash POS
   checkout still works after the addon install/upgrade.
4. Open the Revolut payment-method form and confirm its non-secret environment,
   terminal, location, fulfilment, and secret-reference name are present. Do
   not start a Revolut payment, push a payment intent, or use a physical
   terminal during this smoke check.
5. Inspect `journalctl -u odoo --since "15 minutes ago"` for addon loading,
   update, or traceback errors. Never copy environment values or authorization
   headers into the change record.

Record the operator, UTC time, revision, cash order reference, result, and any
follow-up. Real virtual- or physical-terminal charges belong to Ticket 12, not
this deployment check.

## Failure and recovery

The command names the failed phase. Before Odoo is stopped, a preflight or
backup failure leaves the existing service untouched. After Odoo is stopped,
any final preflight, extraction, update, or activation failure deliberately
leaves it stopped. An HTTP health failure occurs after restart and requires
checking both service state and logs.

Start with non-destructive evidence collection:

```bash
systemctl status odoo odoo-backup.service --no-pager
journalctl -u odoo -u odoo-backup.service --since "30 minutes ago" --no-pager
readlink -f /opt/odoo-hosting/addons/pos_revolut
```

Do not restore the database merely because deployment failed. First reconcile
every Revolut order, payment intent, payment, and refund reference that could
have changed at the provider after the backup. A local timeout, interrupted
request, or missing response is not proof that no charge/refund occurred. Keep
Odoo stopped while an uncertain operation is reconciled, and record the final
provider state against the current database before deciding on recovery.

Prefer a reviewed forward fix. Repointing the release symlink is safe only when
the database schema and data remain compatible with the previous code; rerun
the same offline module update and health checks before restarting. Never
automatically restore a database or overwrite current payment state with a
stale backup.

If database restoration is genuinely required, preserve the failed VM and all
evidence, complete provider reconciliation first, and follow the isolated
replacement-VM procedure in `../odoo-hosting/docs/OPERATIONS.md`. Restore under
a new database name, neutralize external integrations, review it without live
traffic, and use a separately approved cutover. The deployment tool performs
no automatic database restore or infrastructure mutation.

# Upgrade POS Revolut on Odoo 18

These steps cover Odoo 18 Community and Enterprise, including Odoo.sh. The
`18.0.1.0.8` update adds administrator-managed Database credentials, Odoo.sh
stage and neutralization safeguards, and clearer Payment Method configuration.
The `18.0.1.0.9` update moves Restaurant support to the optional
`pos_revolut_restaurant_integration` addon.
An addon upgrade is required to load the new fields, views and data; deploying
code alone is insufficient. This is not a migration between Odoo major versions
and does not import payment history from another integration.

## Prepare the database

1. Inventory unresolved payments, refunds and unfinished native returns. Preserve
   their references and the original Merchant credential authorities.
2. Back up the database, filestore, addon and configuration. Verify restoration;
   keep secret values and live financial evidence in restricted storage.
3. Test the reviewed release on a neutralized disposable copy. Production
   credentials and live access must remain disabled there; use separate Sandbox
   configuration for test operations. See [Odoo.sh](odoo-sh-staging.md) for hosted
   copy and rebuild behavior.
4. Close active POS sessions and arrange a maintenance window before changing
   payment methods or upgrading the operational database.

## Upgrade on Odoo.sh

1. If standard Restaurant is installed, include both matching addon directories
   in the project, even if all registers are in retail mode. Deploy the reviewed
   source to the test branch and upgrade **POS Revolut** in **Apps**. Verify
   that the upgrade installed the companion when Restaurant was present. Check
   the installed versions and the results below before promoting the same code
   to the operational branch through your normal deployment process.
2. Upgrade the module in the operational database using the supported Odoo.sh
   deployment/module-update process. Verify the installed version after the
   upgrade; a successful branch build alone does not establish completion.
3. Reload POS assets and verify workers are running the new code. Staging-only
   database configuration is not promoted with code, so explicitly verify the
   operational authority, payment method, register access and reconciliation
   jobs. Follow [Release and activation](releasing.md) before enabling cashiers.

## Upgrade on a self-hosted server

1. Stop all Odoo workers. Put the reviewed `pos_revolut` directory on the
   configured `addons_path`. If standard Restaurant is installed, include the
   matching `pos_revolut_restaurant_integration` directory, even if all registers
   are in retail mode. Preserve the service's existing runtime environment.
2. If Restaurant is installed, update the base and install the companion in the
   same offline command:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --update pos_revolut --init pos_revolut_restaurant_integration \
     --stop-after-init --no-http --workers=0
   ```

   If the companion is already installed, use
   `--update pos_revolut,pos_revolut_restaurant_integration` in place of the
   `--update` and `--init` options above. Without Restaurant, use only
   `--update pos_revolut`.

3. Restart all workers and reload POS assets.

For the guarded deployer, choose `--package restaurant` whenever standard
Restaurant is installed. Choose `--package retail` for a base-only database.
Retain the reviewed package and its source revision for rollback.

If an update fails, keep POS activity stopped. Restore the matching previous
addon release, database and filestore together. Reconcile any later provider or
native financial operations before restoring.

## Verify configuration and credentials

Confirm the installed addon versions, credential authorities, register grants,
reconciliation jobs, terminal connectivity and original financial references
including unresolved attempts before permitting further payments. Check Connection verifies terminal discovery,
not payment-report permissions or a completed sale. Follow the bounded
payment/refund acceptance steps in [Release and activation](releasing.md).

Existing authorities retain the **Environment variable** source when upgrading
to the version that adds database credentials. The update preserves their
company/environment/reference bindings and the authority IDs frozen on payment
and refund history. It does not copy environment keys into the database or
silently select a replacement authority. Keep the original variables available
on all workers, including workers running scheduled reconciliation.

For an explicit move to Database storage, create a new authority/reference as
described in [Installation](installation.md#authorize-credentials). Retain the
old environment authority and variable for pending and historical operations.
Database-backed keys are included in database backups; masking does not encrypt
them. The same backup and database-copy access controls apply as on production.

Production Revolut access is intentionally blocked on Odoo.sh staging/development
and neutralized databases, including when an old Environment variable authority
still resolves a valid key. Neutralization also clears Production database keys,
revokes Production authorities, archives live methods and disables reconciliation
jobs. Preserve original live attempts in the operational database; never enable
test traffic by altering the platform stage or clearing neutralization.

Never uninstall the addon, delete uncertain attempts or force a payment paid to
make an upgrade pass. Retain the original order and tender during recovery.
Changing this repository's branch or history does not migrate database records.
See [Installation](installation.md) and the [User guide](user-guide.md).

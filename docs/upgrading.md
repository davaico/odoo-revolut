# Upgrade POS Revolut on Odoo 18

These steps cover Odoo 18 Community and Enterprise, including Odoo.sh. The
`18.0.1.0.8` update adds administrator-managed Database credentials, Odoo.sh
stage and neutralization safeguards, and clearer Payment Method configuration.
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

1. Deploy the reviewed addon to the test branch and upgrade **POS Revolut** in
   **Apps**. Verify the installed version and the checks below before promoting
   the same code to the operational branch through your normal deployment
   process.
2. Upgrade the module in the operational database using the supported Odoo.sh
   deployment/module-update process. Verify the installed version after the
   upgrade; a successful branch build alone does not establish completion.
3. Reload POS assets and verify workers are running the new code. Staging-only
   database configuration is not promoted with code, so explicitly verify the
   operational authority, payment method, register access and reconciliation
   jobs. Follow [Release and activation](releasing.md) before enabling cashiers.

## Upgrade on a self-hosted server

1. Stop all Odoo workers. Install the reviewed `pos_revolut` directory,
   preserving the configured `addons_path` and existing runtime environment.
2. Update using the service's configuration and environment:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --update pos_revolut --stop-after-init --no-http --workers=0
   ```

3. Restart all workers and reload POS assets.

## Verify configuration and credentials

Confirm the installed addon version, credential authorities, register grants,
reconciliation jobs, terminal connectivity and existing unresolved attempts
before permitting further payments. Check Connection verifies terminal discovery,
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

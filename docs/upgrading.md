# Upgrade POS Revolut on Odoo 18

This branch supports initial installation into an existing native Odoo 18
database and updates of this Odoo 18 candidate. It does not import payment
history from an Odoo 19 installation or another integration.

Before updating, inventory unresolved transactions, back up the database,
filestore, addon and configuration, and verify restoration. Rehearse on a
disposable copy with real provider traffic disabled. Keep POS activity and Odoo
workers stopped during the maintenance window.

## Update to the optional Restaurant companion

1. If standard Restaurant is installed in the database, put both matching
   addon directories on `addons_path`, including for databases whose registers
   are all in retail mode. Run the update and install the companion in the
   same offline command:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --update pos_revolut --init pos_revolut_restaurant_integration \
     --stop-after-init --no-http --workers=0
   ```

   If the companion is already installed, update both modules together with
   `--update pos_revolut,pos_revolut_restaurant_integration`. On a database
   without Restaurant, update only `pos_revolut`.
2. Confirm the installed module versions, reload the POS assets, and check
   the original register settings and financial references before reopening.
   Existing orders and unresolved attempts retain their original identities.
   If an update fails, keep POS activity stopped. Restore the matching
   previous addon release, database and filestore together only while
   financial activity is still stopped. Reconcile any later provider or
   native financial operations before a restore.

For the guarded self-hosted deployer, choose `--package restaurant` whenever
standard Restaurant is installed, including existing retail registers that
inherited it. Choose `--package retail` for a base-only database. Retain the
reviewed package and its source revision for rollback.

The new companion uses a different technical name from the retired
`pos_revolut_restaurant` bridge. On a supported direct upgrade from that
historical release, keep the old bridge source available until its migration
retires it, then remove the old source.

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

The disposable Odoo 18 regression runner
`./scripts/test-company-credential-upgrade` installs pinned revision
`bcc2f9395a931fae9f90e3d8979165ae2272e293`, seeds an environment authority with
completed/pending payment and pending refund history, updates to the working
candidate and checks unchanged bindings and GET-only mocked recovery. Use a
unique disposable `ODOO_REVOLUT_TEST_PROJECT`; the runner removes that project's
containers and volumes. It does not contact Revolut or validate a live device.

Never uninstall the addon, delete uncertain attempts or force a payment paid to
make an upgrade pass. Retain the original order and tender during recovery.
Changing this repository's branch or history does not migrate database records.
See [Installation](installation.md) and the [User guide](user-guide.md).

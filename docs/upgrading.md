# Upgrade POS Revolut on Odoo 18

This branch supports initial installation into an existing native Odoo 18
database and updates of this Odoo 18 candidate. It does not import payment
history from an Odoo 19 installation or another integration.

1. Inventory unresolved payments, refunds and unfinished native returns. Preserve
   their references and the original Merchant credential authorities.
2. Back up the database, filestore, addon and configuration. Verify restoration;
   keep secret values and live financial evidence in restricted storage.
3. Test the reviewed candidate on a disposable copy with provider traffic disabled.
   See [Contributing](../CONTRIBUTING.md#choose-checks).
4. Stop all Odoo workers. Install the reviewed `pos_revolut` directory,
   preserving the configured `addons_path` and existing runtime environment.
5. Update using the service's configuration and environment:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --update pos_revolut --stop-after-init --no-http --workers=0
   ```

6. Restart all workers and reload POS assets. Verify credential authorities,
   register grants, cron jobs, terminal connectivity and existing unresolved
   attempts before permitting further payments.

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

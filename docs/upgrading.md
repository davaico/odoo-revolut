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

Never uninstall the addon, delete uncertain attempts or force a payment paid to
make an upgrade pass. Retain the original order and tender during recovery.
Changing this repository's branch or history does not migrate database records.
See [Installation](installation.md) and the [User guide](user-guide.md).

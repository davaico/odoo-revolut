# Install and configure POS Revolut

These instructions cover a new installation. For an existing database, read [Upgrading](upgrading.md) first. The current tested runtime is Odoo Community `19.0.20260908` with PostgreSQL `16.14`; final release acceptance and publication approval remain pending.

## Requirements

- An Odoo server you administer, with outbound HTTPS and the standard POS and Restaurant addons available.
- A Revolut Merchant account, its Merchant secret, a physical location ID, and a terminal ID belonging to that location.
- An online terminal in **Pay at Counter** mode.
- Credential access to terminal operations and Merchant `payments_report` creation, polling, and download. **Check Connection** does not test all these capabilities.
- A normal working Odoo POS configuration, journal, currency, and accounting setup.

The addon calls the fixed Sandbox or Production Merchant host using API version `2026-08-17`. Sandbox credentials and devices are separate from Production. Sandbox simulation does not establish that a production terminal is ready.

## Install the addon

1. Obtain the reviewed release and place its `addons/pos_revolut` directory on the server. Add its parent directory to Odoo's `addons_path`, preserving the existing paths.
2. Take database and filestore backups. Stop the Odoo service and run the module installation with the same configuration and service environment used by Odoo:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --init pos_revolut --stop-after-init --no-http --workers=0
   ```

3. Confirm installation succeeded, restart Odoo, and open the Apps list. **POS Revolut** should be installed. Odoo installs `point_of_sale` and `pos_restaurant` as dependencies; there is no separate Revolut Restaurant addon. Retail registers can remain in retail mode.

The path and database name above are placeholders. Use your deployment's Odoo executable and configuration. Native invoice PDFs also need a working server PDF renderer compatible with your Odoo installation; the addon does not install it.

## Provision the Merchant secret

Inject the Merchant secret into every Odoo worker through your deployment's secret store. Give the variable a name beginning with `ODOO_REVOLUT_SECRET_`, containing only uppercase letters, digits, and underscores, for example `ODOO_REVOLUT_SECRET_REGISTER_1`.

Store the **value** only in the server secret store. Do not put it in this repository, Odoo fields, `odoo.conf`, command arguments, browser code, or support logs. If an environment file is used, keep it outside the repository with restricted ownership and mode `0600`.

As a system administrator, verify which Merchant account and company own the secret. Open **Point of Sale → Revolut Merchant Authorities** and create a record for that company, Sandbox or Production environment, and variable name. This authorizes the reference; it does not store the secret. POS managers can select only an authorized reference for their company. Creating a new Revolut payment method as a system administrator can also provision its authority, so treat that action as the same ownership decision. Editing an existing method never provisions authority automatically.

## Configure the register

1. Open **Point of Sale → Configuration → Payment Methods**. Create a bank payment method for the intended company.
2. Set **Integration** to **Terminal**, and **Integrate with** to **Revolut**.
3. Set **Revolut Environment**, **Revolut Location ID**, **Revolut Terminal ID**, and **Revolut Secret Reference**. The reference is the variable's name, never its value. Use one configured terminal for this method.
4. Set **Revolut Fulfilment**. Retail uses **Eat In** as the current interim mapping. Restaurant checkout derives **Eat In** or **Take Away** from the table and Dine In/Takeout preset. Delivery and unknown no-table presets are guarded.
5. Save and select **Check Connection**. It performs terminal discovery and verifies the selected terminal is online; it sends no payment.
6. Add the method to the intended POS configuration. Keep **Automatically validate terminal payments** enabled.
7. Configure Odoo's **Tip Product**, even if customers will leave no tip. Its taxes and Product Price precision must represent collected currency minor units exactly; the standard untaxed tip product is supported. Enable or disable the terminal's customer tip prompt as needed.
8. Disable Restaurant **Add tips after payment**. Remove native Odoo-entered tips before starting Revolut payment; the customer selects any tip on the terminal.
9. As a system administrator, open **Point of Sale → Configuration → Point of Sale**, open the register, and set **Revolut register access → Revolut backend users**. Add every backend till user and supervisor who needs this register. Managers and administrators acting as managers need an explicit grant too.
10. Keep the **Reconcile Revolut POS payments** and **Reconcile Revolut POS refunds** scheduled actions enabled. Reopen POS to load its assets.

Register grants start empty. Employee switching and PINs do not grant backend access. Removing a user blocks their next interactive Revolut request but does not cancel an existing payment; scheduled reconciliation continues.

For timed Takeout, configure the preset's pickup calendar and select an available pickup date/time before payment. A missing pickup time blocks new collection before provider dispatch. If a day has no slots, choose another day in Odoo's scheduling picker. See [Restaurant orders](user-guide.md#restaurant-orders) for captured-payment recovery.

## Verify and maintain the setup

First check ordinary POS operation, terminal discovery, account/location/currency agreement, permissions, and payment-report availability. Perform financial acceptance only with the account owner's approved amounts and a reconciliation plan. A connection check or passing mocked tests cannot substitute for the actual device checks.

After an authorized test, verify the native sale, provider payment, tip, receipt, and refund outcome as applicable. Retain sensitive evidence privately. Use [the user guide](user-guide.md) for uncertain results; do not repeat a charge just because checkout is waiting.

For rotation within the same Merchant account, replace the value behind the existing variable, restart every Odoo worker, check connectivity, then revoke the old key. For a different Merchant account or variable name, provision and authorize a new reference first. Historical attempts retain their original credential authority: keep that reference available while old payments or refunds still require reconciliation. An authority cannot be reassigned to another company or environment.

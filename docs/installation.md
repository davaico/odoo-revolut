# Install POS Revolut

For an existing database, use [Upgrading](upgrading.md). Tested runtime: Odoo Community `18.0.20261015` and PostgreSQL `16.14`.

## Requirements

- An administered Odoo server with outbound HTTPS, standard Odoo Community 18 POS/Restaurant addons and working journal, currency and accounting configuration.
- A Revolut Merchant account, secret, location ID and terminal belonging to that location.
- An online terminal in **Pay at Counter** mode.
- Access to terminal operations and Merchant `payments_report` creation, polling and download. **Check Connection** does not verify all these permissions.

The addon uses fixed Sandbox/Production Merchant hosts and API version `2026-08-17`. Their credentials and devices are separate; sandbox simulation does not prove production readiness.

## Install

1. Place the reviewed `pos_revolut` directory on the server. Add its parent to `addons_path`, preserving existing entries. The module lives under `addons/`; when using a full clone, add the repository’s `addons` directory to `addons_path`.
2. Back up the database and filestore, stop Odoo, then install using the service's configuration and environment. Replace the placeholders:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --init pos_revolut --stop-after-init --no-http --workers=0
   ```

3. After success, restart Odoo and confirm **POS Revolut** is installed. Dependencies `point_of_sale` and `pos_restaurant` install automatically; retail registers can remain in retail mode.

Invoice PDFs require a working Odoo-compatible server PDF renderer, installed separately.

## Authorize credentials

Inject the Merchant secret into every Odoo worker using the deployment secret store. Name its variable with prefix `ODOO_REVOLUT_SECRET_` and uppercase letters, digits and underscores, for example `ODOO_REVOLUT_SECRET_REGISTER_1`.

Keep the value out of Git, Odoo fields, `odoo.conf`, command arguments, browser code and logs. Any environment file must be outside the repository with restricted ownership and mode `0600`.

As system administrator, verify the owning Merchant account/company. Under **Point of Sale → Revolut Merchant Authorities**, authorize the company, environment and variable name. POS managers select an authorized reference, never the secret value. Creating a new Revolut method as administrator can also provision authority; editing an existing method cannot.

## Configure a register

1. Under **Point of Sale → Configuration → Payment Methods**, create a bank method for the company. Set **Integration → Terminal** and **Integrate with → Revolut**.
2. Set **Revolut Environment**, **Location ID**, **Terminal ID** and **Secret Reference** (the variable name). Use one terminal per method.
3. Set **Revolut Fulfilment**. Retail currently uses **Eat In**. Restaurant derives **Eat In/Take Away** from its table and Dine In/Takeout preset; delivery and unknown no-table presets are guarded.
4. Save and select **Check Connection** to discover the terminal and verify it is online. This sends no payment.
5. Add the method to the register; enable **Automatically validate terminal payments**.
6. Configure **Tip Product**, even with tips disabled. Its taxes and Product Price precision must represent currency minor units exactly; the standard untaxed product is supported. Configure the terminal's tip prompt as needed.
7. Disable Restaurant **Add tips after payment**. Remove Odoo-entered tips before collection; Revolut supports terminal-selected tips.
8. As system administrator, open the register under **Configuration → Point of Sale**. In **Revolut register access → Revolut backend users**, add each till user and supervisor, including managers/administrators who operate it.
9. Enable scheduled actions **Reconcile Revolut POS payments** and **Reconcile Revolut POS refunds**. Reopen POS to load assets.

Register grants start empty; employee PINs do not grant access. Removing a user blocks their next interactive request without cancelling existing payments or scheduled reconciliation.

On Odoo 18, this addon provides the Dine In/Takeout preset and pickup scheduling controls. For timed Takeout, configure the pickup calendar and select an available date/time before payment. Choose another day if no slots remain. See [Restaurant orders](user-guide.md#restaurant-orders) for recovery after capture.

## Verify and maintain

Check ordinary POS operation, terminal discovery, account/location/currency agreement, register permissions and payment-report access. Financial acceptance needs the account owner's approved amounts and a reconciliation plan. Mocked tests and connection checks cannot replace device checks.

Verify the native sale, provider payment, tip, receipt and refund as applicable; retain evidence privately. Follow the [user guide](user-guide.md) if results are uncertain.

For key rotation within the same Merchant account, replace the existing variable's value, restart every worker, check connectivity, then revoke the old key. For a new account or variable name, authorize a new reference first. Keep historical references available for reconciliation/refunds; authorities cannot move across companies or environments.

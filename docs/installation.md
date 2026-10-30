# Install POS Revolut

For an existing database, use [Upgrading](upgrading.md). Tested runtime: Odoo Community `18.0.20261015` and PostgreSQL `16.14`.

## Requirements

- An administered Odoo server with outbound HTTPS, standard Odoo Community 18 POS/Restaurant addons and working journal, currency and accounting configuration.
- A Revolut Merchant account, secret, location ID and terminal belonging to that location.
- An online terminal in **Pay at Counter** mode.
- Access to terminal operations and Merchant `payments_report` creation, polling and download. **Check Connection** does not verify all these permissions.

The addon uses fixed Sandbox/Production Merchant hosts and API version `2026-08-17`. Their credentials and devices are separate; sandbox simulation does not prove production readiness.

## Odoo.sh test environments

Production Revolut HTTP is disabled when the server's `ODOO_STAGE` is present
and is anything other than exactly `production`. This includes `staging`, `dev`,
empty values and unknown internal stages. Odoo.sh documents this variable in its
[platform FAQ](https://www.odoo.sh/faq). Sandbox remains available on these builds
with sandbox credentials and devices.

The server enforces this policy for payments, refunds, cancellation, status
checks, **Check Connection**, payment reports and scheduled reconciliation.
It applies on first installation, including installation into a neutralized
database with valid environment credentials, without requiring database-copy
cleanup or disabled scheduled actions. POS settings, RPC context and changing
the current method to Sandbox cannot turn an original Production attempt into
a sandbox transaction.

Blocked operations retain their original references, uncertain states and
reservations. Reconcile live attempts in the production environment; a staging
restriction does not prove that a payment failed or a refund was cancelled.
POS and manager actions explain the restriction, while scheduled jobs skip
blocked live operations without changing their evidence. Do not change or
remove the platform's stage variable to enable testing against live terminals.

On a supported self-hosted server without `ODOO_STAGE`, the configured
Sandbox/Production behavior continues to work. Absence of that variable is
self-hosted compatibility, rather than evidence of Odoo.sh production. A present
`production` value permits configured production access; ordinary credential,
company and register checks still apply. No secret rotation is required for
this policy change.

## Install

1. Place the reviewed `pos_revolut` directory on the server. Add its parent to `addons_path`, preserving existing entries. The module lives at the repository root; when using a full clone, add the repository root to `addons_path`.
2. Back up the database and filestore, stop Odoo, then install using the service's configuration and environment. Replace the placeholders:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --init pos_revolut --stop-after-init --no-http --workers=0
   ```

3. After success, restart Odoo and confirm **POS Revolut** is installed. Dependencies `point_of_sale` and `pos_restaurant` install automatically; retail registers can remain in retail mode.

Invoice PDFs require a working Odoo-compatible server PDF renderer, installed separately.

## Authorize credentials

As system administrator, verify the owning Merchant account/company. Under
**Point of Sale → Revolut Merchant Authorities**, create an authority with its
company, Sandbox/Production environment, source and unique reference. References
use the `ODOO_REVOLUT_SECRET_` prefix followed by uppercase letters, digits and
underscores, for example `ODOO_REVOLUT_SECRET_REGISTER_1`.

Choose one source:

- **Environment variable**: inject the Merchant secret into every Odoo worker
  using the deployment secret store. The authority reference is the variable
  name. Keep its value out of Odoo fields, `odoo.conf` and command arguments.
  Any environment file must be outside the repository with restricted ownership
  and mode `0600`. Existing environment-backed authorities keep this source
  after an addon update.
- **Database**: enter the Merchant key in the administrator-only password field
  when creating the authority. The reference identifies this stored key; it
  does not require an environment variable. The saved form hides the key.

Only system administrators can read, export or change authority records through
Odoo, including direct RPC. POS managers configure the authorized reference on
the payment method without reading its key; cashiers and POS-loaded data receive
neither the key nor the authority inventory. Share the approved reference with
the relevant POS manager. Creating a new Revolut method as administrator can
also provision an environment authority; editing an existing method cannot.

The configured source is exclusive: a missing or revoked database key never
falls back to an environment variable, another authority or another company.
Keep keys out of Git, logs and POS browser code for either source. Database keys
are stored in the Odoo database and included in database backups; password
masking is not encryption. Protect database access, backups and copied databases.
System administrators are trusted across all companies in their database.
Unrelated customers must use separate databases.

## Configure a register

1. Under **Point of Sale → Configuration → Payment Methods**, create a bank method for the company. Set **Integration → Terminal** and **Integrate with → Revolut**.
2. Set **Revolut Environment**, **Location ID**, **Terminal ID** and **Secret Reference** (the approved authority reference). Use one terminal per method.
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

To rotate a key, open its authority as system administrator and select **Rotate Credential**.
This opens a new authority for the same company, environment and source, with an
empty reference and key. Give it a new unique reference. For Database, enter the
new key; for Environment variable, provision the new variable on every worker
and restart them. Save the new authority before giving its reference to the POS
manager. Close the POS session before changing its payment method, then run
**Check Connection** and reopen POS.

Rotation does not update payment methods automatically, alter the old authority
or redirect historical payments/refunds. Company, environment, reference, source
and database key are immutable after creation. Preserve the original authority
and its working key while pending payments, reconciliation or refunds may still
need it. Changing an environment variable's value also changes what historical
attempts using that variable resolve, so use a new variable/reference for safe
rotation. Mark the old authority **Revoked** only after handling its outstanding
operations and deciding how to support future refunds, then revoke the key with
Revolut. A missing or revoked historical key fails safely; it never authorizes
a replacement charge or refund under the new key.

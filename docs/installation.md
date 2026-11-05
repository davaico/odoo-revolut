# Install POS Revolut

This Odoo 18 addon provides configuration for Community installations and
Enterprise installations, including Odoo.sh. For an existing installation, use
[Upgrading](upgrading.md). See [Validation](validation.md) for the tested runtime
and the limits of mocked Enterprise/Odoo.sh checks, and complete the
[release checklist](releasing.md) before enabling live cashier use.

## Requirements

- An administered Odoo 18 Community or Enterprise installation with outbound HTTPS, standard Point of Sale and working journal, currency and accounting configuration. Odoo.sh installations require project administration access and the appropriate Odoo subscription.
- A Revolut Merchant account, secret, location ID and terminal belonging to that location.
- An online terminal in **Pay at Counter** mode.
- Access to terminal operations and Merchant `payments_report` creation, polling and download. **Check Connection** does not verify all these permissions.

The addon uses fixed Sandbox/Production Merchant hosts and API version `2026-08-17`. Their credentials and devices are separate; sandbox simulation does not prove production readiness.

## Odoo.sh test environments

For hosted installation, credential setup, scheduled jobs and database copies,
use the [Odoo.sh guide](odoo-sh-staging.md).

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
`production` value permits configured production access only on a database that
has not been neutralized; ordinary credential,
company and register checks still apply. No secret rotation is required for
this policy change.

## Database copies and neutralization

Use Odoo's **neutralize** option when restoring or duplicating a database for
testing. For an offline self-hosted copy, stop its Odoo workers and run the
[Odoo neutralization command](https://www.odoo.com/documentation/18.0/developer/reference/cli.html#neutralize-neutralize-a-database)
with the copied database's configuration and the addon on `addons_path`:

```bash
odoo neutralize --config /path/to/copy.conf --database COPIED_DATABASE
```

When the addon is installed, Odoo runs its `data/neutralize.sql` hook. Across
all companies this erases Production database keys, revokes Production
Merchant authorities (including environment-backed authorities), archives
Production Revolut methods and disables the two Revolut reconciliation jobs.
Repeating neutralization is safe. Sandbox authorities and methods remain
available; Odoo's base neutralization also disables scheduled actions.

Cleanup preserves payment/refund history, original credential bindings,
provider references, dispatch records, pending reservations and reconciliation
evidence. A copied uncertain payment remains uncertain; cleanup cannot mark it
paid, cancel it, or permit a replacement charge/refund. Reconcile the original
live attempt in production. Archiving retains the Revolut terminal integration
and never converts the method to a manually confirmable payment method.

The runtime guard also rejects Production access whenever Odoo marks the
database neutralized, including a self-hosted copy without `ODOO_STAGE`, a
server labelled `production`, and an addon installed **after** neutralization.
Re-entering a live database key, supplying a valid live environment key,
unarchiving a method or reactivating cron cannot enable live API access on
staging or a neutralized database. Database cleanup cannot erase keys from the
server environment, so keep live keys out of test-server configuration too.

For testing, create a separate **Sandbox** authority and method with sandbox
credentials and devices, configure a test register and deliberately enable the
reconciliation jobs if needed. Keep copied Production records for reference;
do not repurpose their authority or transaction identity for sandbox tests.
A raw PostgreSQL copy or backup restore without Odoo neutralization does not
execute cleanup; ORM `copy=False` exclusions do not protect database copies.
Protect the original backups, which still contain their original keys.

## Install on Odoo.sh

1. Add the reviewed `pos_revolut/` addon at the root of your Odoo.sh project's
   repository and deploy it to a test branch first. Keep API keys out of the
   repository. Back up the database and filestore before installing into an
   existing database.
2. In the intended database, open **Apps**, update the Apps list if necessary,
   search for **POS Revolut**, and install it. Confirm the installed addon version;
   a successful code build does not install the module by itself.
3. As system administrator, create a **Database** Merchant authority using the
   instructions below, then configure a Sandbox payment method for the test
   database. Live Production connections are intentionally blocked on staging,
   development and neutralized copies.
4. Before deploying to the operational database, follow the
   [release checklist](releasing.md). Code promotion does not copy staging-only
   database configuration. Configure the operational company, credentials,
   payment method, register access and reconciliation jobs there explicitly.

## Install on a self-hosted server

1. Place the reviewed `pos_revolut` directory on the server. Add its parent to `addons_path`, preserving existing entries. The module lives at the repository root; when using a full clone, add the repository root to `addons_path`.
2. Back up the database and filestore, stop Odoo, then install using the service's configuration and environment. Replace the placeholders:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --init pos_revolut --stop-after-init --no-http --workers=0
   ```

3. Restart Odoo and confirm **POS Revolut** is installed. Odoo installs standard
   Point of Sale as needed. For a retail shop, leave **Is a Bar/Restaurant**
   unchecked in the register's settings.

### Restaurant registers

Make both `pos_revolut` and the matching `pos_revolut_restaurant_integration`
directory available on `addons_path`. Use the same source release for both.
If the POS Revolut Store download contains only the base addon, obtain the
free companion from the corresponding source release. Install Odoo Restaurant
and the companion before using Revolut in Restaurant mode. For a new setup,
Odoo can auto-install the companion when both dependencies are present and
one is newly installed. You can also install it explicitly:

```bash
odoo --config /path/to/odoo.conf --database DATABASE_NAME \
  --init pos_revolut_restaurant_integration --stop-after-init --no-http --workers=0
```

In Apps, remove the default **Apps** filter to check the companion's state.
Confirm that it is installed, then enable Restaurant mode on the register
and reopen POS. For an existing POS Revolut database, follow the coordinated
procedure in [Upgrading](upgrading.md).

Invoice PDFs require a working Odoo-compatible server PDF renderer, installed separately.

## Authorize credentials

As system administrator, verify the owning Merchant account/company. Under
**Point of Sale → Orders → Revolut Merchant Authorities**, create an authority with its
**Company**, **Revolut Environment** (Sandbox/Production), **Credential Source**
and unique **Credential Reference**. References
use the `ODOO_REVOLUT_SECRET_` prefix followed by uppercase letters, digits and
underscores, for example `ODOO_REVOLUT_SECRET_REGISTER_1`.

Choose one source:

- **Database**: enter the Merchant key in the administrator-only **Merchant API Key** password field
  when creating the authority. The reference identifies this stored key; it
  does not require an environment variable. The saved form hides the key.
  This is the recommended source on Odoo.sh.
- **Environment variable**: on deployments that support persistent secret
  injection, provide the Merchant secret to every Odoo HTTP and cron worker.
  The authority reference is the variable name. Keep its value out of Odoo
  fields, `odoo.conf` and command arguments. Any environment file must be outside
  the repository with restricted ownership and mode `0600`. Existing
  environment-backed authorities keep this source after an addon update.

Only system administrators can read, export or change authority records through
Odoo, including direct RPC. POS managers configure the authorized reference on
the payment method without reading its key; cashiers and POS-loaded data receive
neither the key nor the authority inventory. Share the approved company, environment, reference, location UUID and terminal
UUID with the relevant POS manager through an approved private channel. A reference
is a name for an authority; it is not the API key or a terminal selector. Creating a new Revolut method as administrator can
also provision an environment authority; editing an existing method cannot.

The configured source is exclusive: a missing or revoked database key never
falls back to an environment variable, another authority or another company.
Keep keys out of Git, logs and POS browser code for either source. Database keys
are stored in the Odoo database and included in database backups; password
masking is not encryption. Protect database access, backups and copied databases.
System administrators are trusted across all companies in their database.
Unrelated customers must use separate databases.

On Odoo.sh, use **Database** to avoid requiring custom worker environment
variables. Saving an Environment variable
authority does not provision a key. An `export` in an interactive Odoo.sh shell
only changes that shell and its children; it does not configure running HTTP
or cron workers or survive a rebuild. Do not put keys in branch files or assume
that `odoo.conf` creates environment variables. Use Environment variable only
with a deployment-supported secret mechanism verified on every worker after
restart/rebuild. Odoo.sh recycles workers and restricts staging/development
resources and scheduled actions; see its [platform FAQ](https://www.odoo.sh/faq).
Production connections remain blocked on test builds and neutralized databases,
including for Database keys; use a separate Sandbox authority for testing.

## Configure a register

A POS manager can configure a permitted reference and check the connection; only
a system administrator can administer Merchant authorities or enter/rotate keys.
System administrators who configure methods also need POS manager access. First
obtain the approved configuration from the administrator, then:

1. Select the owning company in Odoo's company switcher before creating a method. Under **Point of Sale → Configuration → Payment Methods**, choose **New**, give it a recognizable name and select that company's bank **Journal**. The readonly **Revolut Company** must match the authority and the register. In a multi-company session, verify the method's company rather than assuming every selected company can use every reference.
2. Set **Integration → Terminal** and **Integrate with → Revolut**. In the **Revolut** section, set **Revolut Environment** to the authority's environment. Copy its approved **Revolut Credential Reference** exactly, including `ODOO_REVOLUT_SECRET_`; enter no API key here. Enter **Revolut Location ID** and **Revolut Terminal ID** as UUIDs from the same Merchant account/environment, with the terminal belonging to that location. These are not an Odoo shop ID, terminal name or serial number. Use one terminal per method; different terminals may share an authorized Merchant credential within the same company/environment.
3. Set **Revolut Fulfilment**. Retail currently uses **Eat In**. Restaurant derives **Eat In/Take Away** from its table and Dine In/Takeout preset; delivery and unknown no-table presets are guarded.
4. Save and select **Check Connection**. Expect **Revolut terminal connected** and the terminal name/ID followed by **is online**. This checks the configured location/terminal using the server-owned key and sends no payment. It does not establish payment/report permissions or financial readiness.
5. Add the method to the register; enable **Automatically validate terminal payments**.
6. Configure **Tip Product**, even with tips disabled. Its taxes and Product Price precision must represent currency minor units exactly; the standard untaxed product is supported. Configure the terminal's tip prompt as needed.
7. Disable Restaurant **Add tips after payment**. Remove Odoo-entered tips before collection; Revolut supports terminal-selected tips.
8. As system administrator, open the register under **Configuration → Point of Sale**. In **Revolut register access → Revolut backend users**, add each till user and supervisor, including managers/administrators who operate it.
9. Enable scheduled actions **Reconcile Revolut POS payments** and **Reconcile Revolut POS refunds**. Reopen POS to load assets.

Register grants start empty; employee PINs do not grant access. Removing a user blocks their next interactive request without cancelling existing payments or scheduled reconciliation.

On Odoo 18, this addon provides the Dine In/Takeout preset and pickup scheduling controls. For timed Takeout, configure the pickup calendar and select an available date/time before payment. Choose another day if no slots remain. See [Restaurant orders](user-guide.md#restaurant-orders) for recovery after capture.

If saving reports that the credential authority is not configured, ask the
administrator to check the exact company, environment and reference; do not
paste a key or a foreign company's reference. If the server credential is
unavailable, the administrator checks the selected source, including every
worker for an environment key. For a missing/offline terminal, verify its UUID,
location and Pay at Counter mode. An Odoo.sh/neutralization restriction requires
a Sandbox configuration, not changing the platform stage flag. Close active POS
sessions before changing methods and reload POS after configuration changes.

The labels above are the English Odoo 18 labels. Odoo translates native labels
according to the user's language; Revolut labels/help use Odoo's normal
translation mechanism and fall back to English where no translation exists.
Field references and UUIDs are literal identifiers in every UI language: do not
translate or retype their meaning.

## Verify and maintain

Check ordinary POS operation, terminal discovery, account/location/currency agreement, register permissions and payment-report access. Financial acceptance needs the account owner's approved amounts and a reconciliation plan. Mocked tests and connection checks cannot replace device checks.

Verify the native sale, provider payment, tip, receipt and refund as applicable; retain evidence privately. Follow the [user guide](user-guide.md) if results are uncertain.

To rotate a key, open **Point of Sale → Orders → Revolut Merchant Authorities** and its authority as system administrator and select **Rotate Credential**.
This opens a new authority for the same company, environment and source, with an
empty reference and key. Give it a new unique reference. For Database, enter the
new key; for Environment variable, provision the new variable on every worker
and restart them. Save the new authority before giving its reference to the POS
manager. Close the POS session before changing its payment method, update **Revolut Credential Reference** on each affected method, then run
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

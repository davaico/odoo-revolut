# Install and operate POS Revolut on Odoo.sh

POS Revolut supports Odoo 18 Enterprise on Odoo.sh with administrator-managed
Database credentials. Use this guide with [Installation](installation.md),
[Upgrading](upgrading.md) and [Validation](validation.md).

## Install on a test database first

1. Add the reviewed root-level `pos_revolut/` addon to the Odoo.sh repository
   and deploy it to a Staging or Development build. Keep existing repository
   content and addons intact.
2. Open that build's database. Confirm the intended Odoo 18 Enterprise edition,
   platform stage and neutralized-copy status. A green build establishes startup;
   it does not prove that the addon is installed or its payment flows are verified.
3. Under **Apps**, find **POS Revolut** and install it. Confirm the installed
   addon version. An existing installation needs a module upgrade when deploying
   a newer addon version. Retail requires only standard Point of Sale. If
   standard Restaurant is installed, include the matching
   `pos_revolut_restaurant_integration/` directory in the project and verify
   that the companion is installed after the upgrade.
4. Configure a separate Sandbox authority, payment method and register as
   described below. Preserve copied Production records for reference.

Use a valid Enterprise subscription or an appropriate active trial according
to your hosting agreement. Manage subscription registration on the intended
operational database through Odoo's normal process; never register a test copy
as another production database or expose subscription codes in support reports.

## Store the Merchant key through Odoo

As a system administrator, open **Point of Sale → Orders → Revolut Merchant
Authorities**. Create an authority for the correct company and Revolut
environment, choose **Credential Source → Database**, enter a unique
`ODOO_REVOLUT_SECRET_` reference and the **Merchant API Key**, then save.
The reference names the authority; it is not an environment variable requirement
when using Database storage.

Only system administrators administer keys. POS managers use the approved
reference on their payment methods, and the POS browser receives no key. Database
keys are stored in the database and its backups; masking is not encryption.
Restrict database and backup access accordingly.

The **Environment variable** source remains available for deployments that
support persistent secret injection into every Odoo worker. An interactive
shell `export` changes only that shell and its children; it does not provision
running HTTP/cron workers or survive a rebuild. Saving an Environment authority
does not create the corresponding variable. Prefer Database storage on Odoo.sh
rather than putting keys in Git, `odoo.conf` or command arguments.

Existing environment-backed authorities retain their source after an upgrade.
To change sources, create a new authority/reference and update the relevant
payment method deliberately. Keep the original authority and key available for
unresolved operations and historical refunds. See
[credential rotation](installation.md#verify-and-maintain).

## Test-environment restrictions

Production Revolut access is blocked whenever Odoo.sh supplies an `ODOO_STAGE`
value other than exactly `production`, or Odoo marks the database neutralized.
This covers payments, refunds, cancellation, status/report retrieval, connection
checks and scheduled reconciliation. The protection also applies when the addon
is installed after the database was neutralized, or someone enters a new key.

Use separate Sandbox credentials and compatible Sandbox devices on test builds.
Configure a Sandbox payment method with the matching company, authority,
location and terminal; complete the remaining
[register setup](installation.md#configure-a-register). A blocked Production
**Check Connection** on Staging is expected. Do not override the platform stage,
clear neutralization or repurpose a copied Production authority to enable live
traffic. Reconcile original Production transactions on the operational database.

## Copies and rebuilds

When the installed addon is neutralized with a database copy, it clears
Production database keys, revokes Production authorities of both credential
sources, archives Production Revolut methods and disables its reconciliation
jobs across all companies. It preserves transaction history, original references
and uncertain outcomes. Copied uncertain attempts must not become replacement
payments or refunds.

A fresh Staging rebuild can replace settings created only on Staging. Repeat
the installation and Sandbox setup checks on each new copy; keep any setup notes
free of secrets. A worker restart retains the database and differs from a fresh
copy. After a restart, verify configuration and recover the same unresolved
attempts without resending financial operations.

Keep original backups protected because they retain their original keys.
For self-hosted copies or restores, follow
[Database copies and neutralization](installation.md#database-copies-and-neutralization).

## Reconciliation and production setup

The addon installs **Reconcile Revolut POS payments** and **Reconcile Revolut
POS refunds**. Test copies can have scheduled actions disabled. Enable only the
jobs needed for the intended Sandbox setup and verify their results on eligible
attempts. A job that runs with no pending work does not demonstrate recovery.
Odoo.sh worker and scheduling restrictions mean the configured one-minute
interval is not a timing guarantee; delayed jobs must retain the original
uncertain attempt rather than trigger a replacement financial operation.

Before operational use, back up and test recovery, deploy the reviewed version,
and install or upgrade it on the intended Production database. Staging settings
are not promoted with code. Configure the Production Merchant authority,
company/currency, journal, terminal and approved register operators separately.
Enable the reconciliation jobs deliberately and complete the bounded
[payment/refund acceptance checklist](releasing.md) before enabling cashiers.

## Platform references

- [Odoo.sh builds and database copies](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/builds.html)
- [Odoo.sh branch operations](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/branches.html)
- [Worker and scheduling restrictions](https://www.odoo.sh/faq)
- [Production subscription registration](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/create.html#register-the-subscription)

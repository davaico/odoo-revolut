# Install and configure POS Revolut

This release adds configuration and a non-payment terminal check. It does not
create Revolut orders, payment intents, payments, or refunds.

## Requirements

- Odoo Community `19.0.20260908`
- PostgreSQL 16
- the standard Odoo `point_of_sale` addon
- outbound HTTPS from the Odoo server to the selected fixed Revolut host
- a Revolut Merchant secret key, location UUID, and terminal UUID

`pos_restaurant` is optional. The addon depends only on `point_of_sale`, so a
retail installation does not install Restaurant.

## Provision the secret

The addon never stores a Merchant secret in Odoo. A Point of Sale manager stores
only the name of an environment variable. That name must begin with
`ODOO_REVOLUT_SECRET_` and contain only uppercase letters, digits, and
underscores, for example:

```text
ODOO_REVOLUT_SECRET_MAIN_TERMINAL
```

The operator is responsible for injecting that variable into every Odoo worker
from the deployment's encrypted secret store. If an environment file is used,
keep it outside this repository, owned by the Odoo service administrator, mode
`0600`, and on encrypted storage. Never put the value in `odoo.conf`, an Odoo
field, a command line, source control, or support logs.

For rotation, replace the value behind the same reference, restart every Odoo
worker so it receives the new environment, run **Check Connection**, and only
then revoke the old key. If a new reference is required, provision it first,
change the payment method, verify it, and then remove the old reference.

Sandbox and production credentials are independent. The addon maps the selected
environment to these hosts; managers cannot enter a custom host:

| Environment | Host |
| --- | --- |
| Sandbox | `https://sandbox-merchant.revolut.com` |
| Production | `https://merchant.revolut.com` |

Every request sends `Revolut-Api-Version: 2026-08-17`.

## Install or upgrade

Copy `addons/pos_revolut` into a directory on the Odoo `addons_path`, restart
Odoo, and install the module from Apps. The equivalent non-interactive install
is:

```bash
odoo --database DATABASE_NAME --init pos_revolut \
  --stop-after-init --no-http --workers=0
```

For an upgrade, replace `--init` with `--update`. Take the normal database and
filestore backups before upgrading.

## Configure and check a terminal

As a Point of Sale administrator:

1. Open **Point of Sale → Configuration → Payment Methods**.
2. Create or open a bank payment method for the intended company.
3. Set **Integration** to **Terminal** and **Integrate with** to **Revolut**.
4. Select **Sandbox** or **Production**.
5. Enter the Revolut location UUID and the single terminal UUID assigned to this
   payment method.
6. Enter the environment-variable name, not its value, in **Revolut Secret
   Reference** and save.
7. Select **Check Connection**.

The check performs only `GET /api/terminals` with the location and
`operation_mode=pos`. It reports success only when the configured terminal is
returned as online. It never initiates a payment. Non-managers and users outside
the payment method's company are rejected on the server.

## Disposable verification environment

The root `compose.yaml` pins the official Odoo image containing package
`19.0.20260908` and PostgreSQL 16.14 by digest. The test image adds a fixed
Google Chrome package whose SHA-256 is verified during the build. Its runtime
network is internal, so an unexpected outbound Merchant API call fails.
Automated tests patch every expected Revolut request.

Run the addon suite on a fresh database:

```bash
./scripts/test-addon
```

Run the install, addon tests, manager configuration browser tour, module
upgrade, and retail/Restaurant POS startup tours:

```bash
./scripts/test-addon --verify-install-upgrade
```

The script verifies the Odoo package version before starting and removes its
disposable containers, network, database, and filestore when it exits.

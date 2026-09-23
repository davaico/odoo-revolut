# Install and configure POS Revolut

This release supports one full Revolut terminal payment per POS order. Odoo
persists and claims the operation before each mutating Merchant API request,
pushes the amount to the configured terminal, polls through the Odoo server,
and completes the sale only after the underlying Revolut payment is verified as
`captured` or `completed`.

## Requirements

- Odoo Community `19.0.20260908`
- PostgreSQL 16
- the standard Odoo `point_of_sale` addon
- outbound HTTPS from the Odoo server to the selected fixed Revolut host
- a Revolut Merchant secret key, location UUID, and terminal UUID
- a restaurant fulfilment selection supported by the published terminal guide:
  `eat_in` or `take_away`

`pos_restaurant` is optional at the module level. However, live retail payments
are currently blocked because Revolut has not published or confirmed a retail
`fulfilment_type`. Do not map a retail sale to a restaurant value. Mocked and
controlled testing must select the actual `eat_in` or `take_away` context.

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

For the existing managed staging environment, do not copy working-tree files or
run these commands by hand. Use the reviewed-revision deployment tool and its
financial-operation guard in the [staging deployment and recovery
runbook](staging-deployment.md).

## Configure and check a terminal

As a Point of Sale administrator:

1. Open **Point of Sale → Configuration → Payment Methods**.
2. Create or open a bank payment method for the intended company.
3. Set **Integration** to **Terminal** and **Integrate with** to **Revolut**.
4. Select **Sandbox** or **Production**.
5. Enter the Revolut location UUID and the single terminal UUID assigned to this
   payment method.
6. Select the restaurant fulfilment that this payment method represents.
7. Enter the environment-variable name, not its value, in **Revolut Secret
   Reference** and save.
8. Select **Check Connection**.
9. Add the payment method to the intended POS configuration and keep
   **Automatically validate terminal payments** enabled. The server rejects a
   payment start when this standard Odoo setting is disabled.

The check performs only `GET /api/terminals` with the location and
`operation_mode=pos`. It reports success only when the configured terminal is
returned as online. It never initiates a payment. Non-managers and users outside
the payment method's company are rejected on the server.

## Payment behavior and current limitations

When the cashier selects Revolut, the browser sends only the order UUID,
payment-line UUID, amount, currency, session, and payment-method identifier to
Odoo. The Merchant credential, terminal ID, location, fulfilment and all
Merchant API calls stay on the Odoo server. Odoo uses bounded 10-second HTTP
requests and converts the amount using the currency exponent, independently of
POS cash rounding.

The successful flow is:

1. persist the immutable local operation;
2. verify that the configured terminal is online, at the expected location and
   in Pay at Counter mode;
3. durably claim and create the Revolut order;
4. durably claim and create the terminal payment intent;
5. poll the intent, then the underlying payment; and
6. let Odoo's standard automatic terminal-payment validation complete the sale
   only after the payment is `captured` or `completed`.

Intent completion or payment authorisation is not success. Declined, failed and
cancelled results remain explicit. A timeout, malformed/lost response, unknown
state, reference mismatch, or process crash after dispatch leaves an unresolved
operation. The affected order and terminal stay blocked, the force-done path is
guarded, and mutating requests are never automatically replayed.

### Unsuccessful payments and retries

Upgrade the addon to `19.0.1.3.0` before using this flow so Odoo has the
attempt-history, retry-eligibility, and recovery fields. Follow the normal stopped-service
module upgrade in the staging deployment runbook. No credential rotation or new
production Python dependency is required. For earlier unsuccessful attempts,
**Check status** recognizes the recorded provider-final evidence (or a terminal
check failure with no dispatch claims) and enables retry. Old pending or uncertain
attempts remain blocked until reconciled.

The foreground checkout waits for up to 60 seconds, polling approximately once
per second. Cashier outcomes have distinct meanings:

| Outcome | Meaning and cashier action |
| --- | --- |
| Declined | Revolut confirmed the card payment was declined. Retry is allowed. |
| Failed | Revolut confirmed failure, or the initial terminal check stopped the attempt before any charge dispatch. Retry is allowed. |
| Cancelled | Revolut confirmed cancellation. Retry is allowed. |
| Interrupted | Communication was interrupted; payment may still succeed. Check status, without starting another charge. |
| Timed out | The local waiting limit expired; this is not provider failure. Check status, without starting another charge. |
| Unresolved | Missing or inconsistent evidence prevents a final decision. Keep the line and contact support if status checks cannot resolve it. |

Cancel requests first check the intent. Only a pending intent can be cancelled;
processing cannot. Odoo reads the result again after the cancel request, including
when the response is lost or rejected. If payment won the race, verified success
is preserved and the normal checkout can complete. An unresolved cancellation
does not remove the line or unlock the amount.

Only a server-confirmed safe outcome enables a new charge. Each explicit retry
creates a new persisted attempt and a fresh Revolut order and intent; previous
references remain for audit. Duplicate starts or cancellations do not repeat
financial operations. A changed amount cannot alter an active attempt.

For unresolved payments, keep the original order and payment line, avoid another
tender or terminal charge for the same sale, and select **Check status**. **Retry** is available only after a safe outcome. Known
intent references can be queried again; a local timeout never proves that the
customer was not charged. If a creation response was lost and its reference is
missing, ask support to reconcile it with Revolut. Do not clear database locks,
force the line paid, or delete audit records. The manager worklist remains
a follow-up ticket, as do refunds, split tender and retail fulfilment.

### Recovery after reload, server restart, or late success

Upgrade to `19.0.1.3.0` and keep Odoo scheduled actions running. The addon installs
**Reconcile Revolut POS payments**, a one-minute scheduled action. Each run checks
at most 50 due attempts with both an order ID and intent ID. Transitional or
uncertain results are checked again; a provider or network error backs off from
one minute to at most 30 minutes. A local 60-second timeout is due for the
next scheduled run; a non-network invalid response is checked no sooner than
five minutes later. The cashier's **Check status** action can still
query the original attempt immediately. It uses the same server-side outcome
rules as the scheduled action.

A browser reload restores the attempt by the original order UUID and payment-line
UUID. It does not create another Revolut order or intent. The POS line displays
its pending or unresolved status, and **Check status** can restore a late verified
payment. Once the unchanged original order is reopened and fully paid, the
normal POS checkout finalizes it and stores the order, intent and payment
references. Scheduled reconciliation only records the payment result; it never
creates or finalizes a POS sale in the background. An edited order is rejected
at finalization even when the total still matches. Keep the original order and
request manager reconciliation in that case.

An attempt missing an external order or intent ID is intentionally excluded from
scheduled polling. The provider may have accepted a request whose response was
lost, so Odoo cannot safely repeat it. Keep the order and terminal blocked and
have a manager or support associate the attempt with authoritative Revolut
records. Until the manager worklist is delivered, support can inspect the
server-side `pos.revolut.payment.operation` record by order/payment UUID and
its recorded `state`, `next_reconcile_at`, `reconcile_failures`, and external
references through an authorized Odoo shell. Do not clear blocking fields by
hand. No new credential or credential rotation is required for this upgrade;
the scheduled action uses the same server environment variable as checkout.

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

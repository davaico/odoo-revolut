# Deploy and activate POS Revolut on Odoo 18

Use this checklist when deploying POS Revolut to an Odoo 18 Community or
Enterprise installation, including Odoo.sh. Installing the addon, configuring a
Merchant account and accepting a real terminal payment are separate checks.
See [Validation](validation.md) for tested scope and remaining device limits.

## Prepare the deployment

- Identify the reviewed addon version and source revision. Keep a copy of the
  deployed artifact and confirm that the installed module matches it.
- Back up the database, filestore and runtime configuration and verify the
  restoration process. Inventory unresolved payments, refunds, returns and
  their original Merchant authorities in restricted records.
- Confirm the intended company, currency, bank journal, register, Merchant
  account, location and terminal. Check the Enterprise entitlement and hosting
  access where applicable.
- Test installation or upgrade on an isolated copy, with Production Revolut
  traffic blocked. Review the results and any skips; successful startup alone
  does not establish payment or recovery correctness.

On Odoo.sh, promoting code to the project's Production branch deploys that
code. It does not transfer settings created only on Staging. Follow the
[Odoo.sh guide](odoo-sh-staging.md) for copies, credentials and environment
restrictions. Odoo Apps publication is a separate distribution step; verify
its registered repository, branch and scanning policy before publishing a release.

## Install or upgrade before enabling cashiers

1. Keep Revolut cashier use closed during the maintenance window. Deploy the
   reviewed addon, then [install](installation.md) or [upgrade](upgrading.md) it
   through the supported hosting process. Verify the installed version, restart
   workers as appropriate and reload POS assets.
2. Apply the [register configuration](installation.md#configure-a-register) to
   the operational database. Select the correct company and bank journal,
   configure the Merchant authority, location/terminal UUIDs and credential
   reference, enable automatic terminal validation and set a suitable tip product.
3. On Odoo.sh, use the administrator-managed **Database** credential source
   unless persistent environment injection is explicitly supported by the
   deployment. A shell `export` does not configure running HTTP or cron workers.
   Never put keys in Git, browser code or logs.
4. Retain the original authorities and working keys needed by unresolved
   attempts and historical refunds. Rotation creates a new authority/reference;
   it does not redirect existing operations or update payment methods automatically.
5. Verify the operational database has not been neutralized. On Odoo.sh, real
   Revolut traffic requires the platform's actual Production stage. Keep
   Staging/Development copies neutralized and use separate Sandbox credentials
   and devices there. Do not alter `ODOO_STAGE` or clear neutralization to bypass
   these restrictions.
6. Check terminal discovery, online status and **Pay at Counter** mode. Verify
   supported currency and payment-report permissions separately: **Check
   Connection** sends no payment and does not establish financial readiness.
7. Enable **Reconcile Revolut POS payments** and **Reconcile Revolut POS refunds**
   deliberately on the operational database. Verify their execution and inspect
   existing unresolved attempts before permitting new collection. Grant register
   access initially to the acceptance operator and supervisor only.

## Accept a real payment and refunds

The Merchant account owner and terminal operator agree the sale and refund
amounts before starting. Retain real identifiers and financial evidence in
restricted records.

1. Select the intended company/register and an authorized cashier. Start one
   sale and complete the card payment on the intended terminal.
2. Verify the underlying provider payment reached its successful final state,
   with matching currency, base allocation and any terminal tip. Check the same
   attempt/provider references in Odoo, native paid order and expected stock and
   accounting effects. A completed payment intent alone is insufficient.
3. Make a partial refund against that sale through the supported native return
   flow. Verify the provider's successful final refund and matching original
   payment, refund operation, return, amount and references in Odoo.
4. Refund the remaining eligible balance and verify the same financial and
   native completion. A submitted or pending refund is not a successful result.
5. Record the deployed version, outcomes, operator and timestamp privately.
   Enable ordinary cashier access only after payment/refund outcomes and native
   completion are accepted.

See [Validation](validation.md#device-and-deployment-limits) for scenarios not
established by the recorded device checks. Verify the hardware and workflows
required by your own installation before general use.

## Recovery and rollback

If an outcome is uncertain, retain the original payment/refund attempt,
provider references, order, tender and reservations, and reconcile that attempt.
Do not send a replacement charge/refund, force a paid state, delete history or
uninstall the addon. Distinguish verified financial success from pending native
checkout; use the [recovery controls](user-guide.md#understand-the-payment-status)
to finish the same order or return without another financial dispatch.

Stop new cashier use if acceptance fails. Preserve restricted logs and snapshots,
check the original credential source and worker availability, and restore service
under the recovery plan. Do not downgrade the database schema blindly or restore
a pre-payment backup over newer financial evidence. Reconcile all post-backup
operations before a database restore; prefer a reviewed forward correction once
financial activity has occurred.

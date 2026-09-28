# Install and configure POS Revolut

This release supports cash plus Revolut and multiple Revolut payment lines on
one POS order. Odoo persists each line's operation before Merchant API dispatch,
sends only that line's amount to its configured terminal, and verifies the
underlying payment as `captured` or `completed`. A partial payment leaves the
order open; normal automatic checkout runs only after the full order is paid.

## Requirements

- Odoo Community `19.0.20260908`
- PostgreSQL 16
- the standard Odoo `point_of_sale` addon
- outbound HTTPS from the Odoo server to the selected fixed Revolut host
- a Revolut Merchant secret key, location UUID, and terminal UUID
- a restaurant fulfilment selection supported by the published terminal guide:
  `eat_in` or `take_away`

`pos_restaurant` is optional. When it is installed alongside `pos_revolut`, the
small `pos_revolut_restaurant` bridge installs automatically and guards bill
splits, merges and transfers after a Revolut payment starts. The terminal guide
provides the provisional restaurant `eat_in` and `take_away` payloads; their
acceptance by the pinned Merchant API still needs controlled testing. Revolut
has not confirmed a retail `fulfilment_type`, so this addon does not claim live
retail compatibility. A manager-configured value in a retail POS is for mocked
or controlled contract testing only.

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

Place **both** `addons/pos_revolut` and `addons/pos_revolut_restaurant` from the
same reviewed release in one directory on Odoo's `addons_path`. Refresh the
Apps list, stop Odoo after taking database and filestore backups, and install
the base module offline:

```bash
odoo --database DATABASE_NAME --init pos_revolut \
  --stop-after-init --no-http --workers=0
```

On a retail database without `pos_restaurant`, the bridge stays uninstalled.
When Restaurant is already installed, its auto-install bridge is installed with
the base module. If Restaurant is installed later, refresh the Apps list and
install Restaurant; verify `pos_revolut_restaurant` is installed before opening
POS. Reopen existing POS sessions to load the bridge assets.

For a base-only upgrade, deliver both addon directories before the offline
update. If Restaurant is installed and the bridge is missing, run
`--update pos_revolut --init pos_revolut_restaurant`. If the bridge is already
installed, run `--update pos_revolut,pos_revolut_restaurant`. A retail-only
upgrade uses `--update pos_revolut`. Use the same `--stop-after-init --no-http
--workers=0` flags shown above, verify the expected module states, and restart
only after every update succeeds. Keep Odoo stopped and reconcile uncertain
payments or refunds before recovering a failed update.

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
6. Select the guide-documented fulfilment for this payment method. In a
   Restaurant POS, the active table and standard Dine In/Takeout preset select
   `eat_in` or `take_away` for each payment. Delivery and unknown no-table
   presets are guarded because the provisional terminal contract does not
   define their mapping.
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
force the line paid, or delete audit records. Refunds and live retail
fulfilment remain separate acceptance work.

### Split tender and Restaurant checkout

Set the cash or other normal payment line to its intended amount, then select
Revolut for the remainder. The POS sends the selected Revolut line amount, not
the full sale total. A successful partial Revolut line stays on the open order;
add another Revolut line or normal tender to settle the remaining balance. Each
Revolut line has its own order, intent and payment references and is checked
against its own amount and the POS currency. Odoo completes the sale automatically
only when every required tender is paid. A draft Restaurant order can retain a
verified partial payment while the cashier navigates away or reloads.

Restaurant uses the standard Dine In/Takeout preset and table context to choose
`eat_in` or `take_away` at dispatch. Moving the **same** draft order to another
table keeps its order UUID and verified payment association. Splitting a bill,
merging orders or transferring into a different order after a Revolut payment
has started is guarded in POS. Keep the original order and use the manager
reconciliation worklist if a financial edit, copied payment line, or changed
order identity is detected. The server rejects a changed cart or an operation
linked to another order, even when the displayed total is unchanged. It also
rejects checkout through cash or another terminal while any Revolut attempt for
that order is unresolved. Wait for a verified or provider-final result before
continuing; never use another tender to cover uncertain exposure.

The Restaurant bridge adds no Merchant credentials or direct browser API calls.
If Restaurant is installed later, upgrade the addons and reopen POS to load its
assets. Installation of `pos_revolut` alone remains supported without Restaurant.

### Recovery after reload, server restart, or late success

Upgrade `pos_revolut` to `19.0.1.7.3` for recovery when the initial read-only
operation lookup fails before a payment or refund start is attempted. The
POS reports **No payment request sent** or **No refund request sent** and offers
**Retry**. Once connectivity returns, retry resumes the normal first-start
flow on the same order and payment-line UUIDs. A manager still chooses an
original allocation before starting a refund. You may also edit or remove
this genuinely undispatched line and choose another eligible tender; refunds
remain limited to their original tender balances. No manager reconciliation
is required for a line that has never attempted a financial start.

The line stays guarded while discovery is running. A lookup failure or timeout
after an attempted start, a discovered operation, or a surviving transaction
reference remains uncertain and uses **Check status**. An empty lookup alone
never unlocks such a line. Older saved waiting/retry lines without evidence of
undispatched preparation also retain their guards. A timed-out read's late
response cannot overwrite a resumed request or mark a line paid.

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
at finalization even when the total still matches. Attempts created before
this upgrade lack an original cart snapshot; their late success also requires
manager reconciliation before the sale can be completed. Keep the original
order for that reconciliation.

An attempt missing an external order or intent ID is intentionally excluded from
scheduled polling. The provider may have accepted a request whose response was
lost, so Odoo cannot safely repeat it. Keep the order and terminal blocked and
have a manager or support associate the attempt with authoritative Revolut
records. Use the manager worklist and procedure below. Do not clear blocking
fields by hand. No new credential or credential rotation is required for this upgrade;
the scheduled action uses the same server environment variable as checkout.

### Manager reconciliation of uncertain attempts

Upgrade to `19.0.1.4.0` before using the worklist. A Point of Sale manager opens
**Point of Sale → Orders → Revolut Reconciliation**. The list is limited to
allowed companies and shows the original POS session and order UUID, amount,
currency, age, current state, known provider references, a sanitized error
summary and a support explanation. Cashiers continue to see the status of their own payment line in
POS, but cannot associate references or run manager actions.

Upgrade `pos_revolut` to `19.0.1.7.1` to apply company isolation to direct
reads of internal dispatch claims and order locks. Manager inspection remains
read-only and is limited to the companies active in Odoo's company selector,
including for managers who have access to several companies. Dispatch claims
belong to their payment operation's company; order locks use their own company.
The reconciliation procedure remains the same.

Upgrade `pos_revolut` to `19.0.1.7.2` to enforce settlement verification through
direct order, payment and order-line operations as well as POS synchronization.
An unverified Revolut tender can be saved as a waiting draft, but cannot be
recorded as done or finalize the order. Verified tenders retain their original
operation, order, payment line and provider references. Orders with financial
exposure cannot change company, session, POS configuration, currency,
conversion rate, refund document type or financial contents, or delete their
evidence. Stored payment and line ownership must agree with the order.
Stored line totals must match Odoo's tax calculation, and a verified partial
payment remains a draft until the complete tender balance is present.
Unexposed waiting drafts and unclaimed return drafts can be cancelled or
discarded. Restaurant table changes and additional valid split
tenders remain supported. Return drafts remain editable before reservation;
they must retain their original sale, and settlement still checks return
quantities, reservations and original tender limits. Refunds require a POS
manager. Reconciliation uses the existing manager worklist; there is no public
SQL lock control or context option that disables these checks.

This is a server update with no new configuration or credential rotation.
Follow the offline upgrade procedure above and reopen POS. It prevents new
unverified settlements; it does not retroactively repair an order fabricated
through an older version. Keep any such order and its evidence for manager
investigation rather than editing transaction references or deleting it.

1. Keep the original POS order and payment line. Find the matching order and
   payment intent in the **same Revolut Merchant account** using the original
   amount, currency, creation time, terminal/location and POS UUIDs.
2. Open the attempt. If an order or intent reference was lost, select
   **Associate References** and enter the UUIDs. Odoo retrieves the order with
   the attempt's server-side Merchant credential. It accepts an order only when
   the provider's amount, currency, location and saved POS order/payment-line
   UUIDs match. For an intent, its order, amount, currency and terminal must
   also match. A reference already owned by another attempt is rejected.
3. Select **Request Reconciliation**. Odoo retrieves the intent and underlying
   payment using the same server verification path as POS and the scheduled
   action. Only a captured or completed **payment** becomes verified. The
   audit tab records who associated or reconciled, when, which UUID evidence
   was used and the resulting state.
4. If the result remains unresolved, keep the order and terminal blocked.
   Check the provider again later or send the shown references and POS UUIDs
   to support. A timeout, missing reference or empty response does not prove
   that another charge is safe.

The worklist does not offer a mark-paid or unlock control. A verified result
still follows the normal POS finalization rules when the unchanged original
order is reopened and fully paid. Orders created before this version lack the
new POS UUID metadata at Revolut; a lost reference for those attempts cannot
be safely associated through the worklist. Keep them blocked and escalate for
provider-backed investigation. Do not enter credentials, card data or raw API
responses as evidence; the audit stores only reference UUIDs.

## Disposable verification environment

The root `compose.yaml` pins the official Odoo image containing package
`19.0.20260908` and PostgreSQL 16.14 by digest. The test image adds a fixed
Google Chrome package whose SHA-256 is verified during the build. Its runtime
network is internal. A test-only Python guard also raises an assertion for any
unmocked request to either Revolut Merchant host; both runners prove the guard
is active before starting Odoo. Automated tests patch every expected Revolut
request.

Run the addon suite on a fresh database:

```bash
./scripts/test-addon
```

Run the fresh install, full addon suite, manager and POS browser tours, module
upgrade, and retail/Restaurant checkout tours:

```bash
./scripts/test-addon --verify-install-upgrade
```

Run the focused two-company authorization and manager workflow regressions:

```bash
./scripts/test-addon --test-tags /pos_revolut:TestRevolutAuthorization,/pos_revolut:TestRevolutReconciliation
```

Run the direct public-method and ORM settlement regressions, including
ordinary cashiers, managers and restricted company contexts:

```bash
./scripts/test-addon --test-tags /pos_revolut:TestRevolutMutationBoundaries,/pos_revolut:TestRevolutRefund,/pos_revolut:TestRevolutAuthorization
```

Run the separate-process recovery check to start a payment, stop Odoo, and
reconcile the same persisted attempt from a fresh Odoo process:

```bash
./scripts/test-restart-recovery
```

Run the remote deployment preflight SQL against pending payment and refund
records in a disposable Odoo database, then verify each blocker clears only
after its operation settles:

```bash
./scripts/test-deployment-guard
```

The addon suite verifies the Odoo package version before starting. All three
checks remove their disposable containers, networks, databases, and filestores
when they exit.

## Partial and allocated Revolut returns (POS manager)

Sign in with an Odoo POS-manager account. Open **Orders**, select the original
paid sale, and use Odoo's **Refund** flow for the products and quantities being
returned. On the payment screen choose a Revolut method used on the original
sale and click **Refund**. The allocation dialog shows each verified original
Revolut payment and its remaining refundable balance. Select the source payment
and confirm the amount. When the original sale used several Revolut payments,
the source selection is required. Add a separate return payment line for each
additional Revolut allocation. For a mixed-tender sale, refund its non-Revolut
portion using the same original non-Revolut tender; it is never sent to
Revolut automatically. A cash-only partial return is possible up to the
original cash share. Return prices, discounts, taxes, currency and original-line
relationships must remain unchanged, and returned quantities cannot exceed the
original lines.

For each original Revolut payment, remaining balance is its verified paid amount
minus all completed, pending, dispatching and uncertain local refunds. Failed
refunds release their reservation. The server locks the original payment while
reserving each allocation and checks that the sum of allocations does not exceed
the requested return total. Other refunds already reported by Revolut block a
new dispatch until a manager resolves the difference. The original sale is
also locked while checking quantities already returned or reserved by another
active return; a later return cannot refund more units than were sold.

The request creates a separate refund order at Revolut. An accepted request is
pending, not proof of completion. Only a server-verified completed refund can
finish the negative Revolut payment. Cash substitution and force-done cannot
bypass verification. The refund and original Revolut references are retained
with the completed return for support and reconciliation.

If communication fails or the wait expires, keep the existing return and use
**Check status**, including after reloading POS. Never create a replacement
refund to bypass an uncertain outcome. Duplicate submissions of the same
payment line reuse its operation and key. Simultaneous returns cannot reserve
more than the original paid amount. A completed allocation stays completed if
another allocation fails or remains uncertain; the return cannot finish until
every active Revolut allocation is verified. For a provider-confirmed failed
allocation, remove only its failed payment line, add a new line, select the
same eligible source and confirm the amount. This creates a new operation for
that line without repeating completed refunds. Keep uncertain lines in place
and reconcile them before changing tender.

If **Check status** reports an interruption because the original sale could
not be loaded, leave the same refund line in place. Its return and payment-line
identities remain reserved. Restore the POS connection and choose **Check
status** again; it looks up the existing refund operation and its final result.
Do not remove the line or select another tender while the refund is uncertain.

Managers can also open **Point of Sale → Revolut Refunds** to inspect pending,
failed, uncertain and completed refunds, their original sale, return UUID,
provider references, and idempotency key. **Check status** and the scheduled
reconciler read provider status; background reconciliation does not finish the
POS return by itself. Resume the unchanged return to complete it after a late
success. Failed refunds remain visible and cannot finish that return.

If a response was lost before the refund ID was saved, reconciliation searches
by the stored merchant reference, then validates the refund's original order,
amount, currency and completion. An empty, ambiguous or mismatched response
remains unresolved. Contact Revolut support with the original order ID and
idempotency key when the association cannot be established. Do not refund
outside Odoo while an Odoo refund is pending or uncertain.

Upgrade the addon to `19.0.1.7.0` to enable partial allocations and the revised
refund uniqueness constraint. No new credentials or configuration fields are
required; refunds use each original payment's server-side credential reference
and environment.

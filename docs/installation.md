# Install and configure POS Revolut

Physical-terminal release acceptance is still open. Use the
[ticket 12 evidence and operator checklist](testing/ticket-12-release-evidence.md)
to confirm the tested/deployed revision, complete account/device preflight,
record authorized test amounts and reconcile observed payments/refunds before
rollout. The procedures below have mocked runtime coverage; the checklist
records the remaining checks on actual devices.

This release supports cash plus Revolut and multiple Revolut payment lines on
one POS order. Version `19.0.1.10.2` saves and prices the native draft on the
server, authorizes its base balance and tender plan, then reserves each card
allocation before Merchant API dispatch. It verifies the captured payment and
an authenticated payment report with an explicit tip amount, including zero.
A partial payment leaves the order open; automatic checkout runs only after
the full authorized base and all proven tips are paid.

## Requirements

- Odoo Community `19.0.20260908`
- PostgreSQL 16
- the standard Odoo `point_of_sale` addon
- outbound HTTPS from the Odoo server to the selected fixed Revolut host
- a Revolut Merchant secret key, location UUID, and terminal UUID
- a fulfilment selection supported by the published terminal guide: `eat_in`
  or `take_away`

`pos_restaurant` is optional. When it is installed alongside `pos_revolut`, the
small `pos_revolut_restaurant` bridge installs automatically and guards bill
splits, merges and transfers after a Revolut payment starts. Controlled Sandbox
probes confirmed that the pinned Merchant API accepts the terminal guide's
`eat_in` and `take_away` values and rejects omission as invalid `SERVICE`.
Revolut documents no retail-specific value; the project owner therefore selects
`eat_in` as the interim retail mapping until Revolut publishes another rule.
This is a product decision backed by runtime acceptance, not a claim that
Revolut defines retail as restaurant consumption.

## Provision the secret

The addon never stores a Merchant secret in Odoo. A system administrator first
authorizes the environment-variable reference for its owning company and
environment under **Point of Sale → Revolut Merchant Authorities**. Verify the
Merchant account and company outside Odoo before creating that record; the
addon cannot infer account ownership from a variable name. A Point of Sale
manager can then select only an authorized reference for the payment method's
company. Creating a new Revolut payment method as a system administrator also
registers its explicitly selected company, environment and reference as an
authority if none exists. Treat that new-method setup as an authorization
decision and independently verify the Merchant account first. Saving or
importing changes to an existing method never provisions authority; create
its reviewed authority separately before configuring, converting or rotating it.
New-method creation also authorizes matching existing configurations; it never
attests historical financial operations. POS-manager creation and all existing
method changes require an already provisioned authority.
That name must begin with
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

For a key rotation within the same Merchant account, replace the value behind
the same reference, restart every Odoo worker, run **Check Connection**, and
only then revoke the old key. To change Merchant accounts or reference names,
provision a new server variable and administrator authority record first,
then change the payment method and verify it. Keep the old reference available
while its historical payments or refunds still need reconciliation. Existing
attempts retain their original authorized reference; changing the current POS
method never redirects them to the new Merchant account. An authority record
cannot be reassigned to another company or environment; create a new one.

Sandbox and production credentials are independent. The addon maps the selected
environment to these hosts; managers cannot enter a custom host:

| Environment | Host |
| --- | --- |
| Sandbox | `https://sandbox-merchant.revolut.com` |
| Production | `https://merchant.revolut.com` |

Every request sends `Revolut-Api-Version: 2026-08-17`.

On 2026-09-28, two nominal-success Sandbox virtual-terminal probes created
failed underlying payments while their intents remained `pending` with no
`payment_id`. The order payment-list endpoint exposed the final failures. Treat
this as a recorded Sandbox simulator limitation, not production evidence; do
not repeatedly create test intents while the provider issue remains unresolved.
See the [terminal contract record](revolut-terminal-contract-2026-09-22.md).

## Install or upgrade

Version `19.0.1.10.0` adds company-scoped Merchant authority records. On an
existing database the upgrade deliberately creates **no** authority records
from old payment methods or attempts. Those old references may have been
misassigned; all unreviewed methods fail configuration and connection checks,
and unreviewed attempts cannot contact Merchant. Their external references,
outcomes and financial reservations remain intact. Before reopening POS, a
system administrator must verify each existing variable's Merchant account and
company, create the corresponding authority record, and explicitly attest each
historical payment operation that still needs provider reconciliation or
refunds. Do not start replacement payments or force-complete an uncertain
attempt during this review. After attestation, keep the original variable
available for recovery and verify the exact existing order and payment in
Merchant before resuming POS. The administrator-only Odoo shell action for a
reviewed historical record is:

```python
operation = env["pos.revolut.payment.operation"].browse(REVIEWED_OPERATION_ID)
operation.action_revolut_authorize_legacy_credential()
env.cr.commit()
operation.invalidate_recordset(["credential_id"])
assert operation.sudo().credential_id
```

It accepts only an exact company, environment and reference authority match;
it performs no Merchant request or financial mutation. Leave any uncertain or
inconsistent record unbound and escalate it for administrator investigation.
No secret value belongs in the shell command, Odoo fields or review evidence.
The action requires the System Administrator group; POS-manager membership is
not required. The explicit commit above persists successful shell attestation.
If validation fails, roll back the shell transaction and investigate before
trying again. Do not commit or manually edit an uncertain binding.

Version `19.0.1.10.3` corrects historical attestation for system administrators
without a POS role and prevents existing-method saves from silently authorizing
unreviewed references. It also rejects redirects on connection, payment and
reconciliation HTTP, keeping requests on the selected provider origin. Deploy
both addons from the reviewed release, upgrade `pos_revolut` and restart every
Odoo worker before reopening POS. No secret rotation or automatic historical
binding is performed. Existing unbound records still require the independent
review and committed attestation above.

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
6. Select the guide-documented fulfilment for this payment method. Use
   `eat_in` for retail under the current owner-approved interim contract. In a
   Restaurant POS, the active table and standard Dine In/Takeout preset select
   `eat_in` or `take_away` for each payment. Delivery and unknown no-table
   presets are guarded because the terminal contract does not define their
   mapping.
7. Have a system administrator verify and authorize the company's Merchant
   reference. Enter that environment-variable name, not its value, in
   **Revolut Secret Reference** and save.
8. Select **Check Connection**.
9. Add the payment method to the intended POS configuration and keep
   **Automatically validate terminal payments** enabled. The server rejects a
   payment start when this standard Odoo setting is disabled.
10. Configure Odoo's **Tip Product**. Its taxes and Product Price precision must
    represent collected currency minor units exactly; preparation checks this
    before dispatch. The standard untaxed tip product is supported. Enable the
    customer tip prompt on the physical terminal as required by your setup.
11. Disable Restaurant **Add tips after payment** for this configuration.
    Revolut tips are selected on the terminal during the payment. Remove any
    unexposed Odoo-entered tip before selecting Revolut to avoid two prompts.
12. Confirm the server credential can create, poll and download Merchant
    `payments_report` runs. Report availability and terminal identity/units
    still require the ticket 12 device acceptance checks.

The check performs only `GET /api/terminals` with the location and
`operation_mode=pos`. It reports success only when the configured terminal is
returned as online. It never initiates a payment. Non-managers and users outside
the payment method's company are rejected on the server.

## Payment behavior and current limitations

When the cashier selects Revolut, the browser synchronizes the draft and asks
Odoo to prepare its exact order ID/UUID and tender plan. The server derives
permitted native prices and taxes, records an immutable cart version and admits
only the named remaining base allocation. A changed price/tax calculation is
shown for review; use **Resume** after reviewing the canonical cart. Restricted
price overrides require a POS manager to open the saved order in their own
Odoo session and choose **Approve Revolut cart**, then the cashier resumes.
An employee selection or browser confirmation cannot grant this approval.

Unexposed preparation expires after five minutes. Resume prepares a current
version. Once a payment is exposed, the approved base stays frozen; expiry or
refund does not restore card capacity. Cash corrections and the tender ledger
are saved atomically during preparation of a subsequent card allocation.

An exposed cart retains its original tip product and checked tax/rounding/price
precision policy. Changing the configured tip product applies to new carts.
If the original effective tax policy changes or price precision is reduced,
restore the original policy before reconciling or sending a remaining card
allocation; captured money stays reserved while that conflict is unresolved.

The Merchant credential, terminal ID, location, fulfilment and all Merchant API
calls stay on the Odoo server. Requests have bounded 10-second HTTP timeouts.
Base cash rounding is frozen separately from terminal tips: an approved 10.00
base plus a collected 0.03 tip settles at 10.03.

The successful flow is:

1. save, price and authorize the base cart and tender allocation;
2. reserve the immutable local operation;
3. verify that the configured terminal is online, at the expected location and
   in Pay at Counter mode;
4. durably claim and create the Revolut order and terminal payment intent;
5. poll the intent and underlying payment, then retrieve the authenticated
   payment report to prove the gross/base/tip decomposition;
6. project the native tip line and gross tender once, then let Odoo's automatic
   terminal-payment validation complete a fully paid sale.

After capture, a delayed or unavailable report displays **Payment received —
awaiting terminal tip details**. Keep the original order and payment line; use
**Check status** or manager reconciliation. Background reconciliation can
finish the report later. Do not create another charge. Full refunds include
the proven tip; partial refunds select base and tip components separately.

Upgrade from earlier versions does not invent authorizations or zero-tip
evidence for old operations. Historical verified/uncertain attempts remain
recoverable with their original references, receipts and refund limits. They
cannot receive another new allocation without audited manager reconciliation.
Safe failed drafts can be prepared under the new rules. Deliver both addons,
run the stopped-service module update, and reopen POS to load the new assets.
No credential is stored in Odoo and no automatic credential rotation occurs.

Intent completion or payment authorisation is not success. Declined, failed and
cancelled results remain explicit. A timeout, malformed/lost response, unknown
state, reference mismatch, or process crash after dispatch leaves an unresolved
operation. The affected order and terminal stay blocked, the force-done path is
guarded, and mutating requests are never automatically replayed.

Version `19.0.1.7.7` keeps observing documented pending, authentication and
early authorisation payment states within the same 60-second foreground limit.
Each underlying payment must still match the persisted payment/order references,
exact integer minor-unit amount and currency. Invalid intent evidence stops the
current poll, retaining known references for later reconciliation. A partial
capture leaves the remaining order amount due; only a fully paid unchanged
order completes automatically. Follow the offline module upgrade procedure
and reopen POS when this candidate is authorized for release. No configuration
or credential changes are required. Deployment and live retests remain gated
by reconciliation of the pending financial operations recorded under ticket 12.

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
force the line paid, or delete audit records. Physical-terminal payment and
refund acceptance remain ticket 12 work.

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

Upgrade `pos_revolut` to `19.0.1.7.6` and reopen POS for terminal-busy recovery.
When the server definitively rejects a start before creating an operation, POS
reports **Terminal busy — no payment request sent**. Remove that unpaid line
to choose another tender, or use **Resume** after the other request is cancelled
or reconciled and the terminal is released. Resume preserves the order and
payment-line UUIDs. **Check status** only looks for an existing attempt; it
never starts a new charge, including after the terminal is released. Reloading
POS retains the definite rejection and these recovery actions.

This recovery requires the structured server rejection for the same start.
A transport error, an exception containing busy wording, or an empty lookup
after an uncertain start keeps the line guarded. Reconcile that attempt before
retrying. Pending refunds and unresolved financial operations must be reconciled
before deploying or repeating the live terminal contention scenario.

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

Upgrade `pos_revolut` to `19.0.1.7.4` for isolated payment and refund recovery.
Malformed, missing and unsupported provider states leave the operation
unresolved and defer its next scheduled read for five minutes. References,
dispatch claims, order/terminal blocks and refund reservations stay intact;
**Check status** can query the same operation immediately. A later valid read
can verify it without a new charge, refund request or idempotency key.

Each scheduled run continues with later due operations after a recoverable
provider/parsing failure. Evidence application retries serialization conflicts
and deadlocks at most three times, each in a fresh transaction, with no provider
request inside that retry. If the conflicts persist, the scheduler records an
interrupted unresolved result in a fresh locked transaction and backs off from
one minute to at most 30 minutes. A valid intent alone does not reset that
backoff while its underlying payment read is still interrupted. If contention
also prevents recording the delay, the operation retains its previous schedule
and a warning identifies its internal operation ID. Other database errors
still fail the scheduled action for investigation. Independently committed
references and verified outcomes survive a later failed observation or audit.

Recovery warnings contain the internal operation ID and a fixed failure
category, without provider bodies or exception text. Cashiers keep the order
blocked and use **Check status**; managers use the reconciliation worklist and
retain its audit history. Refund recovery applies the same five-minute delay
for inconclusive evidence and the one-to-30-minute transport/conflict backoff.
This update adds a refund recovery counter; perform the normal stopped-service
module upgrade and reopen POS. No new credential or credential rotation is
required.

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

## Download payment and refund receipts

Upgrade `pos_revolut` to `19.0.1.8.0` using the offline procedure above, then
reload POS to load the receipt controls. This adds reports and optional merchant
identity snapshots to existing operation records. No credential rotation,
customer record, accounting invoice, new Python dependency or terminal setting
is required.

At checkout, use **Revolut receipts** on the receipt screen. For an older sale,
open **Orders** in POS, select **Paid**, find and select the sale, then use
**Revolut receipts**. The original session may already be closed. Select the
payment or refund document when more than one is available. Each Revolut tender
has its own payment receipt; its amount does not represent other tenders or
assert that the entire sale is paid. Refund receipts are separate documents,
including each partial refund. The original payment remains available after a
refund.

In administration, open **Point of Sale > Orders > Orders**, select the sale
and open the **Revolut receipts** tab. Follow the individual payment or refund
download link. The original sale lists its refunds too; the return order also
lists its own refund documents. Existing sale access and the companies active
in the company selector apply to every download. Cashiers can view permitted
documents without receiving permission to issue refunds or alter evidence.

Open the downloaded PDF in an ordinary PDF viewer to print it, or attach it to
an email manually. The document is clearly labelled as an **Odoo-generated**
receipt. It is distinct from Revolut's original terminal document and Odoo's
itemized sales receipt. There is no automatic email, public sharing link,
accounting document creation or remote terminal printer command.

The timestamp labelled **Verified in Odoo at** records local verification,
not the provider transaction time. A separate generation time identifies this
download. When old records lack a merchant snapshot, the document labels the
available identity as **Current merchant identity**; it does not reconstruct
historical merchant details. Missing optional card or provider date fields
are omitted. Receipt viewing does not fetch them from Revolut or modify the
saved payment evidence.

Only verified successful payments and completed refunds qualify. Pending,
declined, failed, cancelled and uncertain attempts cannot produce completion
documents. If required evidence is missing or inconsistent, contact a POS
manager with the sale reference. If PDF generation fails, retry the download
or ask the administrator to check Odoo's report service. Downloads work from
stored evidence without terminal connectivity and never create another charge
or refund. Cancelling a print or a printer failure has no effect on the payment.

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

Run the three-process recovery check to prepare and start payments, restart
with captured payments awaiting tip reports, then restart again to verify the
reports and project the same operations exactly once:

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

Upgrade `pos_revolut` to `19.0.1.7.5` to preserve the original Revolut tender
classification after its payment method is reconfigured. A historical verified
Revolut payment never becomes an eligible manual bank refund. Keep its original
operation and references; restore the method's Revolut configuration before
using its manager refund flow. Follow the stopped-service upgrade procedure
and reopen POS. No new configuration field or credential rotation is required.

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
If the register was closed after the refund was reserved, reopen that same
register and load the existing return. A verified refund can finalize there
only after the original session is closed and the return contents and tender
still match the reserved allocation. Do not create a new refund.

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

## Financial cart limits and safe correction

Upgrade `pos_revolut` to `19.0.1.7.8` using the offline upgrade procedure and
reopen POS. This combined candidate retains the payment-processing correction
introduced by `19.0.1.7.7` and adds the financial cart limits below.
No configuration or credential change is required.

Revolut cart evidence is bounded before numeric expansion and before a charge
or refund reservation. These server limits apply to starts, return discovery
and final cart comparisons:

| Input | Supported limit |
| --- | --- |
| Lines | 1–1,000; checked before traversal |
| Quantity and unit price | −1,000,000,000 to +1,000,000,000, inclusive |
| Discount | −1,000,000 to +1,000,000, inclusive; normal POS still uses 0–100% |
| Snapshot total, when supplied | −1,000,000,000,000 to +1,000,000,000,000 |
| Numeric representation | At most 64 ASCII characters, 28 significant digits; decimal notation or scientific exponent −324…324 |
| Normalized number | At most 354 fixed-point characters, including sign and decimal point |
| Line identifier | Nonempty, unique text of at most 128 characters |
| Record identifiers | Integers 0…2,147,483,647; products and original return lines must be nonzero |
| Taxes | At most 100 per line, including Odoo tax commands |
| Retained snapshot | At most 256 KiB in default ASCII JSON, including taxes and original return identifiers |

These limits retain the pinned Odoo runtime's ordinary float values, fractional
quantities, negative return quantities, float artifacts, scientific notation
and subnormal values such as `5e-324`. The generous signed magnitudes retain
negative prices and existing backend discounts without changing POS business
rules. Precision matches the previous normalizer's 28-digit Decimal context;
excess precision is rejected instead of silently rounded. Nothing is clamped,
truncated or rounded to pass the bounds. No current fixture requires larger
magnitudes or carts; customer-specific catalog and unit-of-measure extremes
have not been validated.

A **Revolut cart needs correction** message identifies the rejected field or
limit. A direct, identity-bound rejection proving that no payment/refund attempt
exists permits editing or removing the unpaid line. Correct quantities, prices,
discounts, identifiers, lines or taxes, then use **Resume** to explicitly start.
**Check status** stays read-only. A manager must select the original payment
again when resuming a rejected refund. An invalid return discovered before
starting displays its server error and has no refund reservation.

Existing attempts and provider references stay protected. Lost responses,
exceptions and empty status lookups do not establish safe retry or removal.
Check status or ask a manager to reconcile an existing or uncertain attempt.
Previously persisted snapshots within the supported bounds compare in the same
canonical form after upgrade, including signed zero, sorting and original return
links. Historical evidence outside the bounds is retained; it must be reconciled
with its original references. Never edit the stored snapshot to fit a limit,
remove its reservation or restart a financial request based on a validation error.

## Server PDF renderer prerequisite

Payment and refund receipt downloads require a server-installed patched-Qt
renderer. For the supported Ubuntu 24.04 hosting layout, provision
`wkhtmltox 1:0.12.6.1-3.jammy` (`wkhtmltopdf 0.12.6.1 (with patched qt)`)
through `odoo-hosting`; use its documented `repair-pdf` workflow on an existing
host. This is an Odoo server dependency. Installing software on the cashier's
computer does not resolve a missing server renderer. The addon never installs
packages at runtime. A controlled Odoo restart may be required to refresh its
renderer detection, after financial and maintenance gates are met.

See [PDF preflight and repair guidance](staging-deployment.md#pdf-prerequisite-and-deployment-refusal)
for diagnostics and the existing historical receipt download/print check.
Deployment rejects missing, incompatible or failing PDF capability before
stopping Odoo or changing the addon release. A Revolut payment/refund receipt
is distinct from an accounting invoice.

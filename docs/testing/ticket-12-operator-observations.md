# Ticket 12 — Operator observations

Ticket 12 remains open. This record preserves observations from the guided
acceptance session, including verified card payments, guard tests, pending
refunds and two software findings. Refund completion and remaining acceptance
subcases are still required. Entries below are chronological observations;
earlier prerequisites and planned steps are superseded by later dated results.
Use the [release checklist](ticket-12-release-evidence.md) for all gates and
required scenarios.

## Current checkpoint — 2026-09-29 13:42:07 UTC

- Eighteen payment operations, zero active card-payment blockers. Six sources
  are verified for eight GBP minor units in total. Seven of ten authorized
  additional pence have been captured; three pence remain in that budget.
- Five one-penny refunds are processing/unverified, with their reservations
  and deployment blockers retained. Sources `11` and `16` have two and one
  captured pence, respectively, not yet allocated to refunds. The Cash penny
  from the mixed sale remains to be returned.
- Original full-payment automatic checkout, split-tender allocations, safe
  cancellations/retries, selected reload paths, refund caps/amount locking,
  and same-browser/independent-browser terminal guards have narrow passing
  evidence. Other subcases and all final refund settlement remain open.
- [Ticket 22](../tickets/ready-for-agents/22-recover-terminal-busy-rejection.md)
  records the terminal-busy rejection shown as a false communication failure,
  followed by an unrecoverable Check status loop with no dispatched payment.
- [Ticket 23](../tickets/ready-for-agents/23-preserve-polling-through-payment-processing.md)
  records approved payments requiring manual Check status. Classifier and
  foreground-loop characterizations identify a reproducible software gap;
  the exact early live provider payload remains unverified.

This checkpoint does not change the deployed addon. Fixes require a reviewed
candidate and affected retesting; outstanding refunds must be reconciled
before a live upgrade/restart. All financial requests in this session were
sent by the operator.

## Staging upgrade — PASS, 2026-09-28

The project owner explicitly authorized the staging upgrade. The existing
reviewed-revision deployer completed with exit zero and its financial checks,
backup, stopped-service module update and health checks enabled.

| Observation | Recorded result |
| --- | --- |
| Target | `https://odoo-revolut.davaiodoo.com`, database `revolut_staging` |
| Previous release / installed base version | `b96aad6b226684ad479708cc877c901a87570ae7` / `19.0.1.7.0` |
| Deployed tested revision | `76209bb3c3ac705dcc724ba329e044c6626c59cd` |
| Reviewed integration ref | Contained in `origin/main` at `e309367575f478ac3f793cf94b772ba3f42a42a9`; addon and deployment/test source comparison was empty |
| Archive SHA-256 | `472364a875c89f43c2cdceee58203528020c057c9cddb29e36fe712d80f4d476`; matches the tested artifact and deployed marker |
| Odoo package / installed base version | `19.0.20260908` / `19.0.1.7.5` |
| Restaurant | Uninstalled; bridge `19.0.1.0.0` delivered and available, uninstalled |
| Release root | `/opt/odoo-releases/revolut/staging/76209bb3c3ac705dcc724ba329e044c6626c59cd/` |
| Configuration snapshot | `/var/backups/odoo-revolut-deploy/20260928T150752Z-76209bb3c3ac` |
| Database/filestore backup service | Success, exit zero at `2026-09-28 15:07:52 UTC` |
| Latest isolated restore check at preflight | Success, exit zero at `2026-09-25 08:04:31 UTC` |
| Postflight | Odoo active; local and public login HTTP 200; base module installed |
| Financial blockers at postflight | Zero payment and zero refund blockers; recheck before financial acceptance |
| Recent service journal | Zero error, critical or traceback lines since `2026-09-28 15:07:30 UTC` |

These observations came from deployment output and read-only SSH/database checks
on 2026-09-28. Full deployment verification has not been repeated on 2026-09-29;
the credential setup below repeated selected service-health checks. The upgrade
made no Merchant request or terminal charge/refund. No Revolut payment method
was configured at the pre-upgrade inspection.

## Cash smoke — PASS, 2026-09-28

The operator completed a new Cash order after the upgrade. Their receipt showed
**Payment Successful**, ticket `261-1-000004`, one Revolut Test Product and
`11.50 EUR` paid entirely through Cash. The receipt operator was Administrator.

A read-only database query independently confirmed:

- Order `Revolut Development POS - 000004`, reference `261-1-000004`.
- Order UUID `a3e3ab50-ab85-4086-a1ca-5e604569d362`.
- Order time `2026-09-28 15:11:13 UTC`, state `paid`, total `11.50`.
- One payment of `11.50` through Cash, with no terminal integration.

EUR is observed on the receipt; the database check confirmed the order and
tender above. This was a Cash smoke check, not Revolut terminal acceptance.

## Merchant dashboard — OBSERVED, 2026-09-29

The operator's screenshots show **Test Guzman** selected at
`https://business.revolut.com/merchant`. After opening Get started, the Merchant
dashboard and its Integrations control became visible. This verifies dashboard
access; API access, account eligibility and terminal association remain open.

The dashboard displays GBP while the Cash receipt uses EUR. Confirm the
supported and authorized acceptance currency before dispatching a payment;
the displayed dashboard currency alone does not establish incompatibility.

The operator subsequently reported that the physical terminal displays pounds
and believes the test account uses GBP. A read-only staging check on 2026-09-29
confirmed EUR is active, GBP is inactive and company Davai uses EUR. The installed
Odoo POS source derives checkout currency from its sales journal, falling back
to company currency. GBP acceptance therefore needs a verified GBP checkout
configuration; changing a price label or pricelist alone is insufficient.
No currency or POS configuration was changed during this inspection. Exact
financial amounts, currency support and authorization remain open.

## Server-only production credential — PASS, 2026-09-29

The operator's screenshot shows the Merchant API tab and masked Production API
Secret/Public key controls. No secret was disclosed. This establishes that the
key-management page is available; it does not verify authentication or terminal
API eligibility.

Read-only staging inspection found no Odoo environment-file drop-in or
credential directory. Both payment and refund deployment-blocker counts were
zero. A preparation step created the root-owned directory
`/etc/odoo-revolut` with mode `0700` and the root-owned file
`/etc/odoo-revolut/test-guzman-production.env` with mode `0600`, initially holding
an empty assignment. The operator privately entered the key and reported it
saved. Subsequent checks validated its presence, basic format and permissions
without displaying its value.

The server uses systemd 255. The key was converted to a host-bound encrypted
credential at `/etc/odoo-revolut/test-guzman-production.cred`, owned by root with
mode `0600`. An encrypted-value round trip and a transient Odoo service-user
loading check both passed. The override
`/etc/systemd/system/odoo.service.d/90-revolut-secret.conf` uses
`LoadCredentialEncrypted` and exports the decrypted key only into the server
environment as `ODOO_REVOLUT_SECRET_TEST_GUZMAN_PRODUCTION` before executing
the existing Odoo command. This follows systemd's
[encrypted service-credential mechanism](https://github.com/systemd/systemd/blob/main/docs/CREDENTIALS.md).

Financial guards returned zero blockers before and after stopping Odoo. The
guarded restart passed: Odoo was active, local and public login returned HTTP
200, and the credential matched in all five inspected Odoo service processes.
The private plaintext entry file was removed after activation; no editor backup
matching its filename remained. Both encrypted credential and host encryption
key were verified root-owned and private. The recent Odoo log tail had zero
error, critical or traceback lines at the health check.

Encryption is bound to the server's local host key; no TPM or disk-level
encryption claim is made. Recovery onto another host requires reprovisioning the
Merchant secret or securely restoring the credential-encryption key. No secret
value was copied into commands, this repository or tool output.

## Davai discovery and Odoo Check Connection — PASS, 2026-09-29

Server-only requests using production host `https://merchant.revolut.com` and
API version `2026-08-17` returned:

| Read-only check | Result |
| --- | --- |
| `GET /api/locations?type=physical` | HTTP 200; one matching Davai physical location |
| Davai location UUID/type | `7a531302-52af-4f7c-82c2-eaa6b2fe371b` / `physical` |
| `GET /api/terminals?operation_mode=pos&location_id=…` for Davai | HTTP 200; one terminal returned, `online: true` |
| Terminal UUID | `aec8020d-cdf6-4f16-a7f4-a6ca908a1f64` |

Location and operation mode were checked through the documented request filters;
the terminal response did not echo these fields or provide version metadata.
The street address and complete provider response were omitted.

Odoo payment method **Revolut - Davai**, ID `4`, is configured for Terminal /
Revolut, Production, these location/terminal UUIDs and the server environment
reference above. Its retail fulfilment is the existing interim `eat_in` mapping.
After GBP setup below, the native **Check Connection** action passed under the
ordinary Administrator account, whose POS-manager membership was verified.
The method's server-only secret-reference field is absent from the inspected
cashier POS load fields. Only GET requests were made; no provider order,
payment intent, charge or refund was created.

## GBP register preparation — PASS; browser display observed, 2026-09-29

The separate **Davai GBP Terminal Test** register, ID `2`, was created through
Odoo's ORM and passed its saved-configuration checks:

| Configuration | Recorded result |
| --- | --- |
| Checkout / pricelist currency | GBP / GBP; currency activated |
| POS / Revolut / Cash journals | Dedicated GBP journals, IDs `10` / `11` / `12` |
| Terminal / Cash payment methods | Revolut - Davai, ID `4` / Cash - Davai GBP Test, ID `5` |
| Test product | Revolut GBP Test Product, variant ID `3` |
| One-unit test total | Fixed GBP pricelist price `1.00`; no product tax |
| Automatic terminal validation | Enabled |
| Outstanding-account currency | Compatible with GBP |
| Session at verification | None opened |

The staged test product has no tax solely to make the first amount exactly
`1.00 GBP`; this is not acceptance of a real business tax configuration. The
company and original register remain in EUR, and the original register does not
include the Revolut method.

The ECB daily feed supplied `0.85785 GBP` per EUR for `2026-09-28`, one day old at
setup. EUR/GBP rates were recorded for company Davai on that date, and Odoo's
GBP-to-EUR conversion matched the reciprocal rate. The source is the
[ECB daily XML feed](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml),
also shown in the [ECB GBP reference-rate history](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/eurofxref-graph-gbp.en.html).
These are accounting reference rates, not a claim about Merchant settlement
conversion or fees.

Saved-state verification confirmed the one-pound price, zero product taxes,
GBP currency, automatic validation and native manager Check Connection. At that
check there were zero local Revolut payment operations and zero refund
operations. No POS session or sale was created by the configuration script.
The operator subsequently opened the register and provided its payment-screen
screenshot. It shows total `1.00`, the Cash - Davai GBP Test and Revolut - Davai
methods, no selected payment line and disabled Validate. The screen does not
show a currency symbol beside the total. A read-only server check independently
confirmed configuration `2` and open session `5`,
**Davai GBP Terminal Test/00003**, use GBP.
Session `5` was opened by Odoo user ID `2` at `2026-09-29 08:53:13 UTC`.
The session/operation inspection was recorded at `2026-09-29 08:57:26 UTC`.

The screenshot's client order UUID is
`f65cbfcb-33c2-41b2-8ab9-d46e8edf2275`. No matching persisted order was returned
at that check; the displayed total is an operator browser observation, not a
server-verified paid order. Both local Revolut payment-operation and
refund-operation counts remained zero. No financial authorization was supplied
with the screenshot.

The initially approved financial test was one `1.00 GBP` card payment to the selected
Test Guzman / Davai Merchant location, followed by a full `1.00 GBP` refund
through Odoo after payment verification. The project operator explicitly
authorized this plan in the conversation with **"I approve."** Approval was
recorded at the audit clock reading `2026-09-29 08:59:15 UTC`, following the
proposal specifying the payment, refund and retained processing fee. Its scope
is the first single payment and full refund, with at most `1.00 GBP` of charged
principal; it does not authorize additional financial scenarios. The original
client order UUID, configuration `2`, session `5` and method `4` are recorded
above.

The operator asked about using their personal Revolut card. Revolut's
[terminal card guidance](https://help.revolut.com/business/help/merchant-accounts/revolut-terminal/setting-up-the-revolut-terminal/question-cards-and-contactless-payments-with-revolut-terminal/)
supports Visa/Mastercard card payments, including contactless and chip/PIN.
No cardholder identity, account balance, card number or PIN was requested or
recorded.

A subsequent read-only pre-payment check returned zero blocking payment and
refund operations, no operation for the original client UUID, and HTTP 200 for
Davai terminal discovery. The selected terminal remained uniquely online under
the `operation_mode=pos` filter. All checks sent only GET requests. The installed
Odoo interface has automatic sending enabled for this payment method: selecting
Revolut - Davai sends the payment request without requiring a separate Send
click. No card-payment outcome is recorded yet.

The merchant's original processing fee is retained after a refund according to
[Revolut's refund-fee guidance](https://help.revolut.com/business/help/merchant-accounts/refunding-payments/will-i-be-charged-for-a-refund/).

## One-penny revision and prior cancellations — 2026-09-29

The operator subsequently requested reducing the transaction to `0.01 GBP`.
This replaces the earlier one-pound test amount: the current plan is one
`0.01 GBP` payment and its full `0.01 GBP` refund after verification. The
requested reduction stays within the previously approved exposure; processing
fees remain applicable, and further financial scenarios remain unauthorized.
Revolut's [production terminal testing recommendations](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
explicitly give `0.01 GBP` as a small test amount.

Inspection found two one-pound operations for the original client UUID, both
locally `cancelled`, with provider state `cancelled`, `retry_safe: true` and no
payment ID. Their stored times and reference UUIDs are:

| Operation | Created / last local update, UTC | Merchant order / payment intent |
| --- | --- | --- |
| `1` | `09:02:54.088017` / `09:04:22.244049` | `6abb7ebe-5a5e-aa26-96ee-d9a5d455ebba` / `6abb7ebe-0ee5-abaa-9dcc-584a65b972b9` |
| `2` | `09:04:36.725906` / `09:05:06.824546` | `6abb7f25-7a8d-a888-a91d-f6ae3700a721` / `6abb7f25-24d4-ab04-91ba-45f32794b390` |

Fresh GET checks of each intent, order and order payment list independently
verified the matching references, original `100` minor units / GBP, intent
state `cancelled` with no payment ID, order state `pending`, and an empty
underlying payment list. This confirms both intents were cancelled without a
successful payment. Both deployment-blocker counts were zero. No refund is
needed for these unpaid attempts, and no mutating Merchant request was made by
the agent. The operator's terminal/browser cancellation steps have not been
described, so this is partial cancellation evidence, not a complete L05 pass.

At `2026-09-29 09:11:22 UTC`, Odoo's ORM updated the dedicated test pricelist's
fixed price to `0.01 GBP` and the test product's accounting-currency base price.
Saved-state checks confirmed one-unit price `0.01 GBP`, zero product taxes,
normalization to exactly `1` minor unit and no cash rounding applied to card
totals. No session, order, intent, charge or refund was created by this update.
The operator subsequently supplied a fresh order's product-screen screenshot:
order tab `1002`, client UUID `2a490fdb-9ab0-4a57-a3ad-29da3582b664`, still shows
one test product and a total of `1.00`. A read-only server check reconfirmed the
saved test pricelist rule and product price are `0.01`; it found no Revolut
operation for this fresh UUID and no deployment blockers. The native Price
button is visible and the register does not restrict price control. The next
operator step is to set this unpaid line's unit price to `0.01` and verify the
order total before selecting Revolut. This is an operator workaround; the
cause of the displayed-price discrepancy and the one-penny browser/terminal
result have not been verified.

## L01 full retail payment — PASS, 2026-09-29

The operator reported that payment completed and supplied a receipt screenshot.
It shows **Payment Successful**, ticket `261-2-000001`, one Revolut GBP Test
Product at `0.01`, total `0.01`, tender **Revolut - Davai** and payment reference
`6abb8461-34d8-a89e-8de3-68af531a8489`. This later paid order has a different
UUID from the earlier unpaid product-screen observation. Its recorded unit
price and total confirm the one-penny correction for this sale; the cause of
the earlier catalogue display discrepancy remains unverified.

Read-only database inspection and four fresh production Merchant GET requests
at `2026-09-29 09:29:12 UTC` independently established:

| Evidence | Result |
| --- | --- |
| Sale / receipt | Odoo order `6`, Davai GBP Terminal Test - 000001 / `261-2-000001` |
| POS order UUID | `9e90c676-d6e2-4282-8189-c760aac07c15` |
| Session / checkout currency / pricelist | `5` / GBP / `2` |
| Sale state / total / paid / change | `paid` / `0.01` / `0.01` / `0.00` |
| Sale line | Product `3`, quantity `1`, unit price `0.01`, zero discount and tax |
| Odoo tender / payment-line UUID | Payment `5`, Revolut - Davai, `done` / `4bbf7730-f891-43f9-818a-18fc7e6593ad` |
| Local operation / final state | `4` / `verified`, provider state `captured`, not deployment-blocking |
| Local operation created / verified | `09:26:29.237510 UTC` / `09:26:59 UTC` |
| Amount / environment | `1` minor unit / GBP / Production |
| Immutable fulfilment / automatic terminal validation | `eat_in` / enabled |
| Merchant order | `6abb8445-d976-a860-96e6-8f8febdd54a3`, `completed`, amount `1`, GBP |
| Payment intent | `6abb8445-f29a-a261-9f66-341b88a7a60d`, `completed`, amount `1`, GBP |
| Underlying payment | `6abb8461-34d8-a89e-8de3-68af531a8489`, `captured`, amount `1`, GBP |
| Original refundable balance | Provider refunded amount `0`; no local refund allocation; `0.01 GBP` remains |
| Current deployment blockers | Zero payments / zero refunds |

`GET /api/orders/{order_id}`, `GET /api/payment-intents/{intent_id}`,
`GET /api/payments/{payment_id}` and `GET /api/orders/{order_id}/payments` all
returned HTTP 200. Their IDs and associations match the stored operation and
receipt. The provider order's POS order/payment-line metadata matches Odoo.
The order location and intent terminal match the previously verified Davai
location and terminal. The payment-list response contains exactly one captured
one-penny payment for this Merchant order. Payment success is supported by the
underlying captured payment, rather than intent completion alone.

At the confirmation recorded at `2026-09-29 09:30:16 UTC`, the operator answered
**Yes to both**: the physical terminal displayed `0.01 GBP`, and Odoo opened
the receipt automatically without the operator pressing Validate. Read-only
configuration inspection also confirmed the operation's immutable fulfilment
is `eat_in` and automatic terminal validation is enabled. These observations,
the independently captured payment, paid sale and matching references establish
the L01 full retail-payment happy-path pass for this attempt. Other live
scenarios are not covered by this result. At that verification, no refund
request had been made.
All agent Merchant requests in this verification were read-only and printed
only selected non-sensitive fields, never credentials, card data or complete
provider responses.

## L08 full refund — IN PROGRESS, 2026-09-29

The operator's Orders screenshot shows the paid ticket under the **Active**
filter, still labelled **Receipt**, with only **Load Order** available.
Inspection of this installed Odoo version's native ticket-screen source
confirmed that selecting the **Paid** filter opens the synced-order view with
the refund quantity keypad and **Refund** action. The next instruction is to
select Paid, choose ticket `261-2-000001` and return its single item. This is
refund-flow preparation; no refund completion is established by the screenshot.

The subsequent screenshot shows return `1002 (Refund)`, total `-0.01`, a
Revolut - Davai line for `-0.01`, **Refund in process**, disabled Validate and
the linked refund/original/source references. The operator has been instructed
to keep this same return open and leave Force done untouched. Its visible
presence is not evidence that forcing completion succeeds; that control has
not been exercised in this live attempt.

Read-only Odoo inspection at `2026-09-29 09:35:56 UTC` found one refund
operation for the captured original, and no finalized return order or tender:

| Evidence | Result |
| --- | --- |
| Local refund / original operation | `1` / `4` |
| Return UUID | `700cf100-23c5-479b-9023-6029db5bb1c9` |
| Return payment-line UUID | `42e4979b-7151-46ff-9869-6fb89927bbef` |
| Amount / currency / return total | `1` minor unit / GBP / `1` minor unit |
| Request dispatch time | `2026-09-29 09:34:50 UTC` |
| Refund Merchant order | `6abb863a-e259-a83c-ba76-d11f47544160` |
| Local / provider state | `pending` / `processing`; no verified timestamp |
| Linked original Merchant order | `6abb8445-d976-a860-96e6-8f8febdd54a3` |
| Local refundable allocation | Captured `0.01`, completed refunds `0.00`, active reservation `0.01`, available `0.00 GBP` |
| Deployment blockers | Zero payments / one refund |

Fresh production GETs at `2026-09-29 09:36:28 UTC` returned HTTP 200 for both
refund and original orders. The refund is type `refund`, amount `1`, currency
GBP, state `processing`, with `related_order_id` matching the original above.
The original remains `completed` and reports `refunded_amount: 1`. That amount
alone does not establish refund completion: the authoritative refund order
still reports processing, and the POS return must remain unfinished. The
[Revolut refund guide](https://developer.revolut.com/docs/guides/merchant/operations/refunds)
documents asynchronous processing and a separate completed refund order.
L08 is not yet a pass, and receipt of the penny in the customer's account has
not been observed. No duplicate refund or mutating Merchant request was made
by the agent.

The operator then reported a timeout message after about 60 seconds and
supplied the same return/payment screen. It shows **Waiting limit expired —
refund unresolved**, an available **Check status** action, disabled Validate
and the unchanged return UUID, refund order, original order and source `4`.
The precise dismissed dialog text was not captured. This establishes the
foreground waiting-limit behavior and retained references, rather than a
provider-final failure or completed refund.

At `2026-09-29 09:37:55 UTC`, read-only database inspection still found exactly
one refund operation (`1`) for original operation `4`, with unchanged return
and payment-line UUIDs. Its latest scheduled observation at `09:37:53 UTC`
records local `pending`, provider `processing`, no verified timestamp and an
active deployment block. There is no finalized return or negative tender.
Fresh GETs at `09:38:01 UTC` independently confirmed the same refund order is
still `processing`, amount `1` / GBP, linked to the same original. The provider
has not reported successful completion. The operator was instructed to use
Check status on this existing line. L08 and L10 recovery completion remain
open; this timeout does not authorize another refund or release its balance.

The operator subsequently reported that their personal Revolut app shows an
incoming `0.01 GBP` refund in processing, with an estimated receipt date of
**2026-10-04**. This is an operator-reported customer-account observation and
estimate; the funds have not been reported received. Their new POS screenshot
shows the same return and refund references back at **Refund in process**,
with Validate still disabled.

At `2026-09-29 09:38:57 UTC`, fresh production GETs still confirmed the same
refund order is `processing`, correctly linked and for `1` minor unit / GBP.
Odoo retained exactly one refund operation, locally `unresolved` with
`local_outcome: timed_out`, provider state `processing`, no verified timestamp
and its reservation/deployment block intact. No finalized return exists.
The installed refund reconciliation scheduled action is active with a
one-minute interval; its code checks existing operations and does not issue a
replacement refund. Background verification can continue while the operator
waits, but finishing the POS return requires resuming the same return after
verified completion. Provider completion and customer receipt are separate
observations; the customer-app estimate does not establish the API's future
completion time. L08 remains in progress.

The next Orders screenshot lists original `1001` / `261-2-000001` at `0.01`
with status **Receipt**, and return `1002 (Refund)` / `261-2-000002` at `-0.01`
with status **Payment**, under Active. The original line also links to the
same return UUID. Native source inspection confirmed that Active deliberately
includes finalized orders whose current screen is Receipt. **Load Order**
selects the existing order and navigates to its saved screen: the original's
receipt, or the return's payment/recovery screen. Its handler does not create
a replacement sale or refund. Keeping both linked records is expected; the
return remains unfinished until refund completion is verified.

## L04 decline / safe retry and L05 POS cancellation — PARTIAL, 2026-09-29

While the original full refund was pending, the operator independently ran a
further one-penny attempt and a retry. They confirmed that the decline was
triggered with a card lacking available funds and that they cancelled the
second attempt by clicking the POS **Cancel** control beneath Force done.
The exact terminal/POS outcome messages were not supplied. No new financial
request was dispatched by the agent.

| Evidence | Declined attempt | Cancelled retry |
| --- | --- | --- |
| Local operation / attempt number | `5` / `1` | `6` / `2`, predecessor `5` |
| Created / final local update, UTC | `09:42:49.429606` / `09:43:30.221005` | `09:44:38.858314` / `09:44:47.273237` |
| Amount / currency | `1` minor unit / GBP | `1` minor unit / GBP |
| Local / provider outcome | `declined` / `declined` | `cancelled` / `cancelled` |
| Safe retry / deployment blocker | true / false | true / false |
| Merchant order | `6abb8819-6973-a85b-9605-a52a71918d1d` | `6abb8887-9073-a0af-991b-d8b00a8f7ff1` |
| Intent | `6abb8819-ec1a-a211-a751-7fd61e0b11d5` | `6abb8887-94a0-a4fa-a52f-9c0f299595b4` |
| Underlying payment | `6abb8839-00b6-aade-97a0-837c3268a951`, declined | No payment ID; empty order payment list |

Both operations preserve POS order UUID
`b0277675-a878-4bbc-9e33-d1bdf5983f3b` and payment-line UUID
`3c586be7-8e78-455e-a938-8d58349c1a55`. The explicit retry has distinct Merchant
order and intent IDs and retains its predecessor. Neither operation is linked
to a settled Odoo order or tender. The GBP session still has only the original
paid sale and zero stored orders in state `cancel`.

Fresh production GETs at `2026-09-29 09:49:52 UTC` returned HTTP 200 for both
intent and order payment-list checks, plus the declined payment read. The
first intent is `completed`, but its underlying payment is `declined`; Odoo
correctly retained an unpaid declined outcome. The second intent is
`cancelled`, with no payment ID and an empty underlying payment list. These
reads establish unsuccessful final outcomes without a captured payment, rather
than relying on intent completion. L04 remains partial because controlled
provider failure and all specified retry checks are not complete. L05 remains
partial because processing/uncertain cancellation and capture-race subcases
have not been observed.

The same read-only pass recovered an additional earlier one-pound cancellation,
operation `3`, created `09:08:51.627558 UTC` and finalized locally at
`09:09:18.489031 UTC`. Its order is
`6abb8023-299a-a98e-8c5b-40ae23fd392e`, intent
`6abb8024-b9d2-ac16-bae2-b04258464f91`, amount `100` minor units / GBP. Fresh
GETs confirmed a cancelled intent and empty payment list. This extends the
earlier unpaid-cancellation record; no operator action description for this
specific attempt was supplied.

## Payment-history visibility — observed limitation, 2026-09-29

Installed native and addon views, and backend menu/action metadata, confirm:

- POS Orders labels Ongoing, Payment and Receipt describe the checkout screen;
  Paid exposes settled orders. There is no Cancelled filter in this POS view.
- Backend **Point of Sale → Orders → Orders** has a Cancelled filter for saved
  orders with state `cancel`, plus Group By Status.
- **Point of Sale → Orders → Payments** lists recorded tender amounts and
  payment methods, grouped by method by default. It is not a complete attempt
  history.
- **Point of Sale → Orders → Revolut Refunds** shows all stored refund
  operations, including pending/unresolved refunds before POS settlement.
- **Point of Sale → Orders → Revolut Reconciliation** is a manager recovery
  worklist. Its action domain includes unsettled attempts and unsuccessful
  attempts only when retry is unsafe. It excludes verified payments and
  safely cancelled/declined/failed attempts; clearing search filters cannot
  remove this action-domain restriction.

The unsuccessful attempts above are retained, but they are not cancelled POS
sales. Their absence from the Orders Cancelled filter is expected. The current
addon has no general manager menu to browse every resolved payment attempt;
this is a visibility limitation, not evidence that cancellation history was
deleted. No view, filter, payment state or financial record was changed during
this inspection.

## Order search and accidental return-customer selection — 2026-09-29

The operator reported that the paid sale disappeared after reopening Orders
and changing status filters. Their screenshot shows a nonempty customer-name
search and only return `1002 (Refund)`. Read-only database inspection confirmed
the original order `6` / `261-2-000001` remains `paid`, with total and amount
paid `0.01`, no assigned customer and no accounting invoice. Changing the
status filter does not clear the search. Native search-bar inspection confirmed
that clearing its input emits an empty search and removes the customer-search
restriction. The operator was instructed to clear that input, then choose
Paid to retrieve the original receipt.

The operator also reported accidentally assigning a customer to the pending
return and being unable to change it. Native `PosStore.selectPartner` rejects
customer changes when an order already has a customer and refund lines. The
refund operation still targets captured original operation `4` and its
original Merchant order/payment, for `1` minor unit / GBP. The backend request
uses that original reference; a POS customer label does not select a different
card recipient. Customer attribution of the test return may be inaccurate,
but the refund recipient has not changed. The return is not yet finalized,
and no customer record, original sale, refund identity or pending reservation
was edited by the agent. The customer name is omitted from this shared record.

## Additional backend return draft — 2026-09-29

The operator clicked native **Return Products** on paid sale `6`, then asked
whether to use the new draft's Payment action. Read-only inspection at about
10:02 UTC confirmed that native `refund()` prepares another negative-quantity
order; it does not dispatch a Merchant refund. The resulting order `7`,
`Davai GBP Terminal Test - 000001 REFUND`, UUID
`84297c16-83c1-48a2-9bba-a335dcdfcbb2`, was created at 09:57:15 UTC and remains
`draft`, with total `-0.01`, amount paid `0.00`, no invoice, no tender and no
charge or refund operation. Its line `7` points to original sale line `6`.

The original refund operation `1` remains the sole refund against captured
operation `4`: `pending`, provider state `processing`, no verification timestamp,
and a blocking one-penny reservation. Its original POS return UUID remains
`700cf100-23c5-479b-9023-6029db5bb1c9`; neither the operation nor a settled return
payment is attached to new draft `7`. The original sale remains paid for `0.01`.
The backend Refunds count reflects related Odoo return records and does not
prove completion of the Merchant refund.

The operator was instructed not to use Payment on the extra draft, to cancel
only that unused draft through the native **Cancel Order** action, and to resume
the existing POS return `1002 (Refund)` for status recovery. The installed action
is available in form/list/kanban actions for POS users and cancels draft orders
through the guarded ORM; it does not call the Merchant API. No cancellation,
deletion, settlement or provider mutation was performed by the agent.

After the operator reported removing the extra draft, a read-only recheck at
about 10:07 UTC confirmed order `7` is `cancel`, with amount paid `0.00`.
The sole original refund operation remains `pending` / provider `processing`,
with its existing return UUID and no verification timestamp. Cancellation of
the unused draft is confirmed; completion of the original refund remains open.

## Duplicate-refund guard test — PASS for normal POS allocation, 2026-09-29

The operator explicitly requested guidance to attempt a second refund of the
same purchased item and observe whether the guard rejects it. Scope is one
additional normal POS attempt against original sale `6` / `261-2-000001`, for
`0.01 GBP`; expected outcome is rejection before another Merchant request.
The existing pending return must remain intact. No additional purchase, cash
substitution or forced settlement is part of this test.

Read-only baseline at about 10:14 UTC: sale `6` remains paid for `0.01`, its only
refund operation is `1` / Merchant refund order
`6abb863a-e259-a83c-ba76-d11f47544160`, still pending / provider processing,
with no verification timestamp. Its one minor unit is fully reserved; available
refundable balance is zero. The extra backend return `7` remains cancelled and
unpaid, with no settled return tender. The operator has been guided to use a
new empty POS order, select the original paid receipt, attempt one returned
unit, and select Revolut only if a distinct negative return is created.

Record the first native quantity warning or Revolut balance rejection, the
new return UUID if one is created, and the post-attempt operation count and
remaining balance before claiming a result. A native quantity rejection alone
does not exercise the addon's refund balance or reservation checks. A normal
UI balance rejection does not prove the concurrent reservation race path.
At this baseline, no result, new refund dispatch or additional financial
operation was claimed.

At about 10:18 UTC, the operator reached **Allocate Revolut refund** on a
distinct POS return `1004 (Refund)`, UUID
`35986973-a20b-4b5e-b790-d9e98492f5a6`, total `-0.01`. The dialog lists source
operation `4` with **Remaining: 0 GBP**; the source radio is disabled and the
amount is initially empty. **Remaining on this return: 0.01 GBP** describes the
new return total, not available funds on the original payment. Deployed template
and JavaScript inspection confirms that a zero-balance source cannot be selected
and Confirm rejects missing selection or an amount above its remaining balance.
The previously anticipated **No Revolut refund balance** alert is not used in
this path, because the source exists and is displayed even with zero balance.

Read-only inspection still found exactly the original refund operation `1`,
pending / provider processing, with one minor unit reserved and zero available.
There is no refund operation or persisted POS order for the new return UUID.
The operator has been instructed to enter `0.01` and click Confirm once to
observe the visible rejection. Its actual error and the subsequent operation
count still need verification; this is not yet a completed guard test.

At about 10:20 UTC, the operator supplied a screenshot of the same new return
with `0.01` entered and the visible validation error **Choose an original Revolut
payment and an amount within its remaining balance and this return.** The
operator explicitly confirmed that the zero-balance original payment could
not be selected. The dialog remained open; the new return did not settle.

Read-only post-attempt checks confirmed exactly one refund against original
operation `4`: the unchanged original operation `1`, still pending / provider
processing with its original Merchant order ID and return UUID. New return
`35986973-a20b-4b5e-b790-d9e98492f5a6` has zero refund operations, zero charge
operations, zero persisted POS orders and zero settled tenders. The original
sale remains paid for `0.01`; reserved balance remains one minor unit and
available balance remains zero. **PASS for the normal POS allocation guard:**
the zero-balance source is disabled and confirming the requested penny is
rejected without creating another refund operation.

This exercises the POS balance display and confirmation validation against
the server's existing refund reservation. It does not exercise a direct
reservation request with stale data or simultaneous competing refunds, and
does not complete the broader partial/mixed-tender refund matrix. The original
full refund remains in progress. The operator has been guided to cancel the
allocation dialog and discard only unclaimed test return `1004 (Refund)`,
preserving original pending return `1002 (Refund)`. Cleanup of `1004` has not
yet been reported; the agent made no mutating Merchant request.

## Further operator scenarios — PLANNED, 2026-09-29

The operator requested additional use cases to exercise while the original
refund is processing. Read-only preflight confirmed session `5` remains open,
payment operations `1`–`3` and `6` are safely cancelled, `5` is safely declined,
and `4` is verified. None has a deployment/terminal payment blocker. Original
refund `1` remains unresolved / provider processing, retains its one-penny
reservation and blocks deployment changes. The new duplicate-test return has
no persisted order; its browser cleanup has not been independently observed.

The proposed next check is a normal browser reload while a fresh `0.01 GBP`
terminal request waits for a card. The operator must not present a card in
this check. First record the order/payment-line/operation/provider references,
then refresh normally (preserving browser storage), reconcile the same attempt,
and cancel the pending request after its status is known. Only an authoritative
final unpaid result establishes successful cleanup. This is a planned browser
interruption case, not permission to disconnect the terminal during payment.

Further proposed checks cover abandoned-request timeout/status recovery,
repeated status reads, terminal contention between two orders, attempted cart
changes after dispatch, terminal unavailability before dispatch, paid retry and
late-success recovery, Cash/Revolut split tender, multiple Revolut lines, and
partial returns with reserved/refunded quantity and source-balance limits.
Restaurant fulfilment and table/order operations require a later prepared
Restaurant environment; the deployed Restaurant module remains uninstalled.

The operator explicitly approved a maximum aggregate budget of `0.10 GBP` in
additional real card charges for later paid scenarios, answering **Approve up
to GBP 0.10 total** to the budget question. Proposed cases are a `0.02 GBP`
Cash/card sale with `0.01` on the card, a `0.02` sale with two `0.01` card
allocations, a `0.03` partial-refund sale, and `0.01` payment-recovery/retry
cases. Eligible test charges will be refunded after their references are
recorded. This budget is additional to the original captured penny; zero of
the new budget has been spent at this observation. Paid scenarios have not
started, and no new scenario result is claimed. Approval was recorded at
2026-09-29 10:26:04 UTC.

## No-card browser refresh — IN PROGRESS, 2026-09-29

The operator supplied the pre-card screenshot for a new positive POS order
`1004`, UUID `b6959c8f-8225-47dc-b9ad-68c1304365ca`, displaying `0.01` and
**Waiting for card**. This is a distinct sale from the prior duplicate-return
test, although the POS reused display number `1004`. The original pending
return `1002 (Refund)` remains visible. The screenshot alone does not establish
cleanup of the duplicate-return draft or any financial result.

Read-only checks at 10:33:27 UTC recorded payment operation `7`, attempt `1`,
payment-line UUID `d075efa8-e8aa-4b02-8df3-39e4ccf2534d`, amount one GBP minor
unit, local/provider state pending, no previous operation, no underlying
payment ID and no verification timestamp. The operation was created at
10:32:28.271300 UTC. Its Merchant order is
`6abb93bc-b53b-ac4e-ab84-71dca5305845` and its payment intent is
`6abb93bc-e9a7-ad82-8da9-813d316d70d6`, associated with the same Davai terminal.
The original refund remains operation `1`, pending / provider processing,
with its one-penny reservation and deployment blocker intact.

The operator is being guided to keep card and phone away, refresh normally
without clearing browser storage, and show the restored screen before using
any payment action. The pre-refresh state and references are recorded; actual
reload recovery, identity preservation and final unpaid cancellation remain
unverified. No new capture or additional-budget spending is claimed.

The next operator screenshot shows the same order UUID and positive `0.01`
payment line after reload, now **Payment unresolved** with **Check status** and
checkout still unpaid. The operator reports that the physical terminal is
still waiting for payment. This establishes restoration of the cart and its
unresolved payment line, but does not alone establish operation identity.

At 10:35:11 UTC, server inspection found original attempt `7` safely cancelled,
followed by attempt `8` on the same order and payment-line UUID. Attempt `7`
was last written at 10:34:26.970869 UTC; attempt `8` was created at
10:34:30.673414 UTC, explicitly references predecessor `7`, and remains
pending. Its Merchant order is `6abb9436-7661-acca-9038-5fa48cced02a` and its
intent is `6abb9437-810c-ae46-b9e7-16d417ef6159`. Both amounts are one GBP
minor unit. Neither operation has an underlying payment ID or verification
timestamp, and no persisted POS order was found for this cart.

Read-only Merchant GETs at 10:35:53 UTC returned HTTP 200 for each attempt's
intent, order and payment list. Attempt `7`'s intent is cancelled (provider
updated at 10:34:25.952565 UTC); attempt `8`'s intent is pending. Both payment
lists are empty. Original refund `1` remains pending / provider processing.
The agent asked the operator for the intervening sequence of Cancel, Retry,
terminal cancellation and refresh actions. Until that is answered, creation
of attempt `8` cannot be attributed to reload or claimed as an intentional
retry. The intended same-attempt reload test is not marked PASS. The next
guided action is Check status once on the currently active attempt, while
keeping card and phone away. No new capture or budget spending is observed.

The operator then supplied the next screen, showing **Payment cancelled**,
**Retry**, and the alert **The Revolut payment was cancelled. You can retry.**
The order is still unpaid with `0.01` remaining; no receipt or automatic
checkout occurred. At 10:40:22 UTC, both attempts `7` and `8` are locally
cancelled / provider cancelled, retry safe and nonblocking, retaining their
original identities. There is no later payment operation on configuration `2`
and no persisted POS order for this cart. Original refund `1` remains pending /
provider processing with its existing reservation.

Merchant GETs at 10:40:23 UTC confirmed attempt `8`'s intent is cancelled,
provider updated at 10:36:34.537161 UTC, and its payment list is empty (HTTP 200
for both). Thus the recovered cancellation is authoritative and no payment
or additional-budget spending occurred on this attempt. No replacement
operation was observed across this status-recovery step. This supports the
final-cancellation recovery subcase, while the broader pending-request reload
identity test remains incomplete until the operator's intervening action
sequence explains the transition from attempt `7` to `8`. Cancellation's
trigger is not inferred from its elapsed time. The agent is guiding dismissal
of the alert and cancellation of only the now-unclaimed sale cart `1004`,
preserving the original pending return `1002 (Refund)`.

The operator repeated the no-card scenario on a fresh order and reported
refreshing the page, supplying another **Payment unresolved / Check status**
screen. Although its display number is again `1004`, its UUID is distinct:
`a15dd516-a469-48c6-83dc-4aaf6ec724a6`. The screenshot shows `0.01` remaining
and the original pending return `1002 (Refund)` still present. The original
attempt-`7`/`8` action sequence remains unanswered; this repeat is recorded
separately rather than used to explain that earlier transition.

At 10:42:28 UTC, this fresh order has exactly one operation, `9`, attempt `1`,
with no predecessor. It was created at 10:41:44.031029 UTC and remains local /
provider pending for one GBP minor unit. Its payment-line UUID is
`01aa95d0-2b83-4737-9341-722581e29b30`, Merchant order
`6abb95e8-bc33-a6e7-9950-a6f18787a396`, and intent
`6abb95e8-bdae-adbf-8d05-5933b887e712`. No underlying payment ID, verification
timestamp, replacement operation or persisted POS order exists for the cart.
The additional verified-charge budget remains zero of ten minor units spent.
Original refund `1` remains pending / provider processing.

This repeat shows restoration of the unresolved order without a second
operation observed across reload. The operator is guided to Check status
once, cancel through the POS if Waiting for card resumes, or acknowledge a
final cancellation if it has already occurred. Final operation identity,
unpaid cleanup and the physical terminal returning to idle still need checking.

The operator explicitly reported that Check status restored **Waiting for
card**, that they then clicked Cancel, and that the payment became cancelled.
At 10:44:17 UTC, read-only checks found exactly the same operation `9`, amount,
order/payment-line UUIDs and Merchant order/intent references, now cancelled /
provider cancelled, retry safe and nonblocking. There is no later payment
operation or persisted POS order for this scenario. Merchant GETs at
10:44:19 UTC returned HTTP 200, showing the same intent cancelled (provider
updated at 10:43:26.896202 UTC) and an empty payment list.

**PASS for the single-attempt no-card reload, status recovery and cancellation
subcase:** the unresolved cart was restored, Check status resumed waiting on
its sole existing request, and the operator's cancellation reached an
authoritative unpaid final state without a replacement request. No new card
charge occurred; the additional ten-minor-unit budget remains unspent.
The terminal returning to its physical idle screen has not yet been explicitly
reported. This narrow result does not complete late-capture, post-payment
reload, repeated/concurrent status reads or the full L06/L07 matrix. The earlier
two-attempt scenario's intervening actions remain unexplained. Original refund
`1` remains pending / provider processing and is preserved.

The next guided scenario prepares a fresh `0.02 GBP` Cash/Revolut split sale,
with `0.01 GBP` cash and an intended `0.01 GBP` card portion. Preparation stops
with the cash line entered and `0.01` remaining, before selecting Revolut or
validating the order, so the tender allocation can be checked first. Actual
terminal/card dispatch and payment are not yet performed or claimed.

## Cash/Revolut split sale — IN PROGRESS, 2026-09-29

The operator supplied the prepared payment screen for fresh sale UUID
`efd4bb61-8c0a-40a1-bd05-c0c22043fc3b`, POS display number `1004`. It shows
total `0.02`, exactly one Cash - Davai GBP Test line for `0.01`, remaining
`0.01`, and checkout not yet completed. No Revolut line is present. This is
browser evidence of the intended tender allocation, not proof of physical
cash receipt or settled payment.

Read-only preflight at 10:47:36 UTC found no deployment-blocking payment
operation on configuration `2`, zero payment operations for this new sale,
no persisted POS order for its UUID, and zero additional verified card-charge
minor units spent from the approved ten-minor-unit budget. Original refund
`1` remains pending / provider processing with its existing reservation.

The next guided action is to select Revolut once, verify `0.01 GBP` on the
physical terminal, and pay only that penny using the operator's card. This
financial test is covered by the existing aggregate `0.10 GBP` additional
charge authorization. The operator must cancel and report any different
terminal amount. Capture, automatic completion, persisted tender allocation,
receipt references and cumulative budget usage remain to be verified after
the operator pays. No card charge or L02 pass is claimed at this preparation.

The operator subsequently reported paying by card and seeing approval on the
terminal. The supplied Odoo screen still shows total `0.02`, Cash `0.01`,
Revolut `0.01`, remaining `0.01`, and **Payment unresolved / Check status**.
Its alert says the result is unresolved, prohibits charging again or using
the terminal until reconciliation, and directs Check status for the existing
payment. The operator has not yet explicitly confirmed the physical terminal
amount. Automatic checkout and a receipt did not occur at this observation.

At 10:49:27 UTC, this cart has exactly one operation, `10`, attempt `1`, with
no predecessor, amount one GBP minor unit and payment-line UUID
`5498a2cc-c448-44aa-98d5-2d4589774182`. Created at 10:48:10.479154 UTC, it is
locally unresolved / provider processing, last written at 10:48:29.876863 UTC,
unverified, retry safety unconfirmed and deployment blocking. Its Merchant
order is `6abb976a-f7dc-af5f-b89a-0e5e51cae3fa`, intent
`6abb976a-e5c0-abcf-8cde-6090811abc0c`, and underlying payment
`6abb977d-4b9b-a048-9851-027128b0cc1f`. No persisted POS order exists for
the cart. Original refund `1` remains pending / provider processing.

Direct Merchant GETs at 10:49:53 UTC returned HTTP 200 for the intent,
underlying payment, order and payment list. The intent is completed; the
underlying payment is **captured**, amount one GBP minor unit, associated with
the recorded order. The order is completed and its payment list contains
exactly that one captured payment. Provider timestamps show payment created
at 10:48:29.256954 UTC and updated to the captured observation at
10:48:31.429494 UTC. This is proof of a successful penny charge despite the
stale unresolved POS screen; it is not inferred from intent completion or
device approval. The additional-charge budget is now **one of ten GBP minor
units spent**, based on provider capture, although the local verified-only
budget query still reported zero before recovery. Refunding this test charge
later does not replenish the authorized aggregate-charge budget.

**Automatic completion did not pass on this attempt.** The observed local
processing result predates the provider's final capture by about two seconds;
the reason foreground polling did not reach that final result remains to be
diagnosed. No code root cause, fix or full L02 pass is claimed. The operator
is guided to dismiss the alert and click Check status once, preserving this
order and both tender amounts. A retry, replacement charge, manual Force done
or cash substitution is not used. Recovery to a paid `0.02` order with matching
tenders and receipt references still needs verification.

The operator reported **All I did was click Check status** and supplied receipt
`261-2-000004` on the same sale UUID. The receipt shows total `0.02`, Revolut
`0.01`, Cash `0.01`, and the original underlying-payment reference; no second
tap or manual Validate was reported. At 10:52:07 UTC, operation `10` is
verified / provider captured, nonblocking, with all its order/payment-line
and Merchant references unchanged. It is linked to POS order `9` and payment
`7`, verified at 10:50:53 UTC. There is exactly one operation for this cart.

Order `9` is paid, total and paid amount `0.02`, change zero, no invoice,
and date 10:50:53 UTC. Its two persisted tenders are Cash method `5`, payment
`6`, amount `0.01`, and Revolut method `4`, payment `7`, amount `0.01`, status
done, linked to captured payment `6abb977d-4b9b-a048-9851-027128b0cc1f`.
The local verified-charge tally now agrees with provider capture: **one of
ten additional GBP minor units spent; nine remain**. Original refund `1`
remains pending / provider processing. The physical terminal amount and
cash handover were not separately confirmed by the operator and are not
inferred from the accounting records.

**PASS for persisted Cash/Revolut allocation and same-payment recovery:** the
captured card amount was the one-penny remainder, Check status completed the
existing sale, and both tenders reconcile to two pence without another charge.
Automatic completion on the initial foreground request still failed; the
whole L02 matrix is not marked PASS, and multiple Revolut tenders remain unrun.

Local diagnosis used only deployed Git revision `76209bb` and mocks. A Node
replay of pending -> unresolved / last provider state processing -> later
verified reproduced the initial request returning false before reading the
final capture, in two deterministic runs. The command was
`node --test --test-isolation=none --test-name-pattern='live intermediate processing' tests/revolut_payment_state.test.mjs`
in `/tmp/ticket12-processing-repro-20260929`; the focused assertion failed with
`false !== true`. This reproduces the recovery requirement but does not identify
the exact early Merchant response, which was not captured. Normal Node test
worker isolation failed in this sandbox; no-isolation executed the actual
focused test and produced its assertion failure.

Three causes were considered: an unhandled temporary underlying-payment state,
temporarily incomplete or mismatched provider fields, or interrupted polling.
A standalone probe executed the deployed Python observation method with fake
ORM plumbing and matching IDs, amount and currency. It confirms that documented
initial `pending`, authentication and early authorisation states are classified
unresolved, while `authorised` / `capture_started` remain pending and `captured`
verifies. This is a confirmed classifier coverage gap, but not proof that a
particular one of those states caused this live incident. The probe does not
exercise real ORM transactions or SQL locks. The retained provider state
processing belongs to the prior intent observation and does not identify the
rejected underlying-payment state. The saved empty local outcome and zero
reconcile failures favour the unknown-evidence path over a transport error;
a narrow journal query found no matching warning and provides no extra proof.

Primary references checked on 2026-09-29:
[Revolut payment lifecycle](https://developer.revolut.com/docs/guides/merchant/reference/order-lifecycle)
documents the initial pending and early authentication/authorisation states;
[terminal polling guide](https://developer.revolut.com/docs/guides/merchant/accept-payments/in-person-payments/terminal/push-payments)
requires continued observation through temporary states and success only on
the underlying final payment. Unknown or invalid evidence must still block
settlement and retry. No addon fix, deployment or full live pass is claimed.
Automatic confirmation remains a release issue requiring correction and a
real ORM regression test before its next live validation.

The next no-charge check prepares a full two-penny return of receipt
`261-2-000004`, then inspects the allocation dialog before confirmation.
The Revolut source should offer only its one-penny captured balance, despite
the two-penny mixed-tender return total. Preparation must stop before any
valid refund confirmation; no new refund dispatch is claimed.

The operator has prepared POS `1005 (Refund)`, return UUID
`123c2cb4-b387-435e-9ee1-cf48ab33d522`, total `-0.02`, with an unstarted
Revolut line of `-0.02`. The read-only baseline at 10:59:02 UTC found no
payment or refund operation for this return. Original source operation `10`
remains verified / captured, with one GBP minor unit available and none
reserved. Only the original refund operation `1` exists and remains processing.
On this return screen, choosing Revolut adds the line; the separate **Refund**
button opens allocation. Guidance is to click that button once and stop before
Confirm refund allocation. The mixed-tender limit test has not yet run.

After clicking Refund, the operator's allocation screenshot shows source `10`
selected, with `0.01 GBP` remaining, a default refund amount of `0.01`, and
`0.02 GBP` remaining on this return. These amounts match the captured card
portion and the full mixed-tender return respectively. The next guided step
is to enter `0.02` and confirm once to exercise rejection above the source's
available balance. No result or dispatch from that guard attempt is claimed yet.

The operator then reported that `0.02` was rejected with the expected remaining
balance validation. They subsequently confirmed `0.01`, submitting the eligible
card portion. **PASS for the normal POS mixed-tender source-balance guard:** the
two-penny return did not permit two pence against a one-penny Revolut source.
This does not exercise direct RPC manipulation or concurrent claims.

The read-only database check at 11:03:42 UTC found exactly one new refund:
operation `2`, source operation `10`, return UUID
`123c2cb4-b387-435e-9ee1-cf48ab33d522`, payment-line UUID
`16679d90-d6b5-48cd-8430-39bed8f08990`, amount one GBP minor unit, return total
two GBP minor units. Dispatch was at 11:03:02 UTC; Merchant refund order
`6abb9ae7-0da0-a055-8a1d-3a0f1c459cb0` is pending / provider processing with
no verification yet. No payment operation or settled POS order exists for this
return, and no two-penny refund operation appeared. Original refund `1` remains
pending / processing with its references unchanged.

Independent Merchant GETs at 11:04:12 UTC returned HTTP 200 for both refunds.
New refund `2` is type refund, state processing, amount `1`, currency GBP and
related original order `6abb976a-f7dc-af5f-b89a-0e5e51cae3fa`. Original refund
`1` is also processing for one GBP minor unit against its own original order.
The new refund is **IN PROGRESS**, not a verified refund or completed mixed
return. Both refunds now reserve their full original card balances.

The remaining cash penny has not been added or returned. The deployed POS guard
blocks adding another tender while this Revolut refund is unresolved; the
unfinished card line is not yet counted as completed, explaining the displayed
remaining total `-0.02`. Preserve both pending returns, avoid Force done, and use
Check status after the foreground timeout. Once the card refund verifies, the
remaining cash portion can be handled with the original Cash method. No new
card charge was made; the additional charge budget remains one penny spent,
nine pence available. The agent made only database reads and Merchant GETs.

The next proposed no-charge safety check is one click on Cash while refund `2`
remains unresolved. The expected result is that the POS blocks adding another
tender, leaving the existing refund untouched. Stop before validation if a
cash line unexpectedly appears. No outcome for this check is recorded yet.

**PASS for the normal POS alternative-tender guard during an unresolved
refund:** after the Cash click, the operator's screenshot shows the error
"Reconcile the unresolved Revolut payment before adding another tender."
The only visible payment line remains Revolut `-0.01`, with no Cash line.
The read-only check at 11:09:50 UTC found the same two refund operations, both
pending / processing and unverified. Return `1005` still has no saved or settled
POS order and no payment operation. No new refund or card charge appeared.

The next no-charge check is a single browser refresh of this pending return,
then Check status on the restored line. Its baseline is refund operation `2`,
Merchant refund `6abb9ae7-0da0-a055-8a1d-3a0f1c459cb0`, source `10`, amount
one GBP minor unit, same return and payment-line UUIDs above, with two refunds
globally. Expected behavior is restoration and reconciliation of that existing
refund rather than another dispatch. No result for this reload check is claimed
yet; preserve the older pending return `1002` throughout.

**PASS for restoring and checking the existing pending refund after one browser
refresh:** the operator reports refreshing and clicking Check status. Their
screenshot retains return UUID `123c2cb4-b387-435e-9ee1-cf48ab33d522`, amount
`-0.01`, source `10`, and Merchant refund
`6abb9ae7-0da0-a055-8a1d-3a0f1c459cb0`. The database check at 11:11:43 UTC
still found exactly refund operations `1` and `2`, with the same return and
payment-line UUIDs, dispatch times and external references. Both remain pending
/ processing and unverified. No duplicate refund or settled return appeared.
This verifies one normal reload/status recovery; final asynchronous completion,
concurrent tabs and more disruptive interruption remain open.

The same preflight found no blocking payment operation and only operation `10`
verified among additional-budget charges: one GBP minor unit spent, nine
available. The next planned paid case prepares three units at `0.01 GBP` each,
total `0.03 GBP`, on a new sale. This will allow a later one-unit partial return
while two units remain eligible. Guidance stops at the payment screen before
selecting Revolut, with the existing pending returns preserved. No preparation,
new charge or partial refund is claimed yet; this amount is within the existing
approved aggregate budget.

The operator's payment-screen screenshot now shows new sale `1006`, UUID
`b1969cf8-ceb1-4fad-a449-1f259d3c6300`, total `0.03`, with no payment line yet.
The screen does not show the product quantity breakdown; the guided preparation
was three units at one penny each and that breakdown will be checked on the
saved sale. Preflight at 11:14:00 UTC found zero payment operations for this UUID,
no blocking card attempt, session `5` open, and one additional GBP minor unit
already charged with nine available under the approved budget. Both existing
refunds remain pending / processing and unverified. The next authorized operator
step is one Revolut request, verify `0.03 GBP` on the terminal, then pay. If the
terminal approves but Odoo reports unresolved, use Check status on that same
line without retrying or forcing completion. No new charge or outcome is claimed
at this preflight.

The operator's receipt is `261-2-000006`, showing three units at `0.01` each,
total `0.03`, all paid by Revolut. They confirm the terminal showed `0.03 GBP`
and clarify that Odoo reported unresolved; they clicked Check status to open
the receipt. **Initial automatic checkout failed again.** The verified sale
and same-payment recovery are recorded, without an automatic-completion pass.

Database reads at 11:15:49 UTC found exactly payment operation `11`, attempt
`1`, no predecessor, order UUID `b1969cf8-ceb1-4fad-a449-1f259d3c6300`, payment
line `22d75192-0068-4935-bfe5-17d4ad8141ee`, amount three GBP minor units,
verified / provider captured, nonblocking. Created at 11:14:32.874664 UTC and
verified at 11:15:13 UTC, it links POS order `10`,
`Davai GBP Terminal Test - 000006`, paid total `0.03`, paid amount `0.03`,
zero change and no invoice. Original product line `11` is variant `3`, quantity
`3`, unit price `0.01`, zero discount, totals `0.03`. Tender `8`, method `4`,
amount `0.03`, is done and linked to operation `11`.

Merchant references are order `6abb9d99-4f3a-ac07-a617-8f982005d251`, intent
`6abb9d99-3b66-aa2e-b4e4-e7ed08fa011c`, and payment
`6abb9dac-4c9a-a1ce-86f3-6b64e7d6872f`. Independent GETs at 11:16:27 UTC
returned HTTP 200, a completed intent with that payment ID, and exactly one
captured underlying payment for amount `3`, currency GBP, matching the original
Merchant order. Payment creation was 11:14:52.936276 UTC and capture update was
11:14:55.107357 UTC. These final reads do not identify the earlier response that
caused Odoo to report unresolved; the classifier issue remains open.

The additional-charge budget is now **four GBP minor units spent, six available**:
one on the split sale and three on this sale. Refunds `1` and `2` are still
processing. No refund has yet been submitted for source operation `11`.
The next step is to select paid receipt `261-2-000006`, set one unit to return,
and create a linked return totaling `-0.01`; stop at its payment screen before
choosing Revolut. The native installed quantity handler and Refund action were
read to confirm this creates a one-unit return and navigates to PaymentScreen.
No partial-return preparation or refund dispatch is claimed yet.

The operator has now prepared `1007 (Refund)`, return UUID
`e959d9c1-1d87-4916-b7f3-baa3b4aa0ec3`, showing total `-0.01` and no payment
line. Preflight at 11:18:57 UTC found no refund or charge operation for this
return. Source operation `11` remains verified / captured, with three GBP minor
units available; refunds `1` and `2` are unchanged and still processing.
The next step selects Revolut and clicks its separate Refund action to inspect
allocation before confirmation. Expected source is `11`, available `0.03 GBP`,
refund amount `0.01`, return remaining `0.01 GBP`. Before submitting the valid
one-penny partial refund, the planned reciprocal limit check will attempt
`0.02`: within the original card balance but above this one-penny return. No
allocation confirmation, limit-check result or partial-refund dispatch is
claimed at this preparation step.

The allocation screenshot for return `1007` now shows source `11` selected,
matching original Merchant order `6abb9d99-4f3a-ac07-a617-8f982005d251` and
captured payment `6abb9dac-4c9a-a1ce-86f3-6b64e7d6872f`. Its available balance
is `0.03 GBP`; the default allocation is `0.01` and this return's remaining
amount is `0.01 GBP`, as expected. The next guided actions are one confirmation
of `0.02` to exercise the return-total limit, then, only if that is rejected,
one confirmation of the authorized valid `0.01` partial refund. If the larger
amount is accepted, stop before any further request. No guard result or actual
partial-refund dispatch is recorded yet.

The operator reports that `0.02` was rejected and `0.01` was accepted.
**PASS for the normal POS return-total allocation guard:** the available
three-penny card balance did not permit a two-penny refund for this one-penny
return. This is operator-reported UI rejection, not a direct stale RPC or race
test. The valid partial refund is submitted but not yet completed.

The read-only check at 11:21:15 UTC found exactly one new refund, operation `3`,
source `11`, return UUID `e959d9c1-1d87-4916-b7f3-baa3b4aa0ec3`, payment line
`b031fabb-6573-4d4b-82ee-cde88528ff69`, amount one GBP minor unit, return total
one GBP minor unit. Its persisted financial snapshot contains one unit returned
(`qty -1`), product variant `3`, unit price `0.01`, no discount or taxes, linked
to original line `11`. Dispatch was 11:20:20 UTC. Merchant refund order
`6abb9ef4-9ca7-af6e-96d2-368134e54254` is pending / provider processing,
unverified and deployment blocking. No two-penny refund operation appeared and
the return has no saved or settled POS order yet.

An independent Merchant GET at 11:21:37 UTC returned HTTP 200: type refund,
state processing, amount `1`, currency GBP, related original order
`6abb9d99-4f3a-ac07-a617-8f982005d251`, created at 11:20:20.422014 UTC.
Source `11` remains verified for three pence with one penny reserved by this
partial refund and **two GBP minor units available**. This does not imply that
the pending penny has reached the cardholder. Refunds `1` and `2` remain
processing and unchanged; there are now three actual one-penny refunds against
three different captured sources. The additional charge budget is still four
pence spent, six available. No new charge or agent financial mutation occurred.

The next no-charge step inspects paid receipt `261-2-000006` in the POS Orders
screen to observe how its product details display the one-unit pending return
and remaining units. Do not create another return at that inspection step.
Native display behavior and the remaining-quantity guard have not yet been
verified for this partial return.

The operator's paid-order screenshot shows original receipt `261-2-000006`,
quantity `3`, unit price `0.01`, with both **1.00 Refunded** and **Refunding 1.00
in e959d9c1-1d87-4916-b7f3-baa3b4aa0ec3**. These describe the same one-unit
return; they are not two different refunds and `1.00` is quantity, not GBP.
The native installed `PosOrderline.refundedQty` getter counts linked return
lines whenever their order state is not cancelled, including unfinished drafts.
Consequently its Refunded badge does not establish a completed Merchant refund
or receipt of funds. The check at 11:25:16 UTC still found exactly refunds
`1`–`3`, all pending / processing and unverified; source `11` has two GBP minor
units available. The pending-return link and amount observation are confirmed,
without a final-refund pass.

Native quantity validation subtracts that linked one-unit return from the three
original units. The next no-charge quantity check is to click the selected paid
product line (resetting the input buffer), then enter quantity `3`. Expected is
Maximum Exceeded with only `2` units eligible. Do not click Refund or change
pending return `1007`. No result for this quantity-limit check is recorded yet.

The operator's next screenshot shows **Maximum Exceeded**: three units requested
while only two can be refunded. **PASS for the native POS remaining-quantity
guard:** the existing one-unit return reduces the three-unit sale's remaining
quantity to two. This is a normal UI quantity rejection, not a direct server
RPC or concurrent quantity-claim test. No second return or financial request
was submitted in this step.

The read-only check at 11:27:07 UTC still found exactly refund operations
`1`–`3`, with their existing references and amounts. Their local state is now
unresolved with provider state processing and no verification; this does not
establish refund failure or final completion. Refund `3` retains its one-unit
snapshot (`qty -1`, unit price `0.01`, original line `11`), and original line
`11` remains quantity three at `0.01` per unit. There is no blocking card
payment operation. The additional charge budget remains four pence spent,
six available. No agent financial mutation occurred.

The next planned no-card subcase is contention between two unpaid orders on
the same terminal. Prepare both one-penny positive carts before dispatching
either request, so creating the second cart does not consume the first
request's foreground waiting window. Preserve pending returns `1002`, `1005`
and `1007`. At preparation, stop before selecting any payment method. The
subsequent controlled test will start the first terminal request without a
card, attempt the second while the first is still waiting, and reconcile or
cancel the original request. No terminal-contention result is claimed yet.

The preparation screenshots show positive order `1008`, UUID
`a5deb51e-0299-4182-98da-f94985ef4944`, with one test-product unit priced at
`0.01` and total `0.01`, and order `1009`, UUID
`f312aad6-2544-492e-a12a-7ac1f6d6e8d0`, on its `0.01` payment screen without
a payment line. At 11:32:27 UTC the read-only preflight found eleven payment
operations, latest operation `11`, no operation for either new cart, and no
blocking card payment operation. Refund operations `1`–`3` remain unverified,
pending / provider processing; the charge budget remains four pence spent
and six available.

The guided contention sequence will select Revolut once on `1008`, wait for
Waiting for card without presenting a card, then immediately select Revolut
once on `1009`. Expected is rejection of the second request while the first
owns the terminal. The deployed backend checks the blocking terminal key
before creating another payment operation. The frontend may present a general
communication warning for a rejected start, so the actual UI and persisted
operation count must be checked before assigning a pass. Preserve the second
order's result for evidence, then cancel the first request if the second was
blocked; stop for investigation if the second also reaches Waiting for card.
No request, cancellation or contention pass is claimed at this preparation.

The operator supplied the next two screenshots in execution order. On `1009`,
the first shows **There is already an electronic payment in progress**, with
no payment line added. On `1008`, the second shows **Payment cancelled** and
the retry action after cancellation of the original request.
**PASS for the cross-order electronic-payment guard in one POS browser:** the
second order was blocked during the first order's payment. This does not test
concurrent independent browsers or establish that the server's terminal-lock
rejection path was exercised.

At 11:34:44 UTC the read-only check found exactly one additional payment
operation: `12`, order `1008` / UUID
`a5deb51e-0299-4182-98da-f94985ef4944`, line
`f7830ad8-dacd-46b8-8b63-b9015279885a`, attempt one, one GBP minor unit.
Created at 11:33:38.852325 UTC, it is now cancelled / provider cancelled,
retry safe and not blocking, last written at 11:34:02.338252 UTC. Merchant
order is `6abba213-9456-a8e5-874f-238d6f86b041`; intent is
`6abba213-d7ab-a57c-aa14-17c88d451679`. It has no payment reference, saved
POS order or tender. Order `1009` has no payment operation or saved POS order.
No blocking card payment operation remains. Refunds `1`–`3` remain pending /
processing and unverified, and the additional charge budget is unchanged at
four pence spent, six available.

Independent Merchant GETs at 11:35:13 UTC returned HTTP 200: operation `12`'s
intent is cancelled for one GBP minor unit, updated at 11:34:02.164242 UTC,
and the original order's underlying payment list is empty. No card charge
occurred in this subcase. The persisted terminal lock is released; the
physical terminal's idle display has not separately been confirmed.

The next no-card follow-up will try the previously blocked order `1009` after
the first cancellation. Select Revolut once, expect Waiting for card and the
terminal's one-penny request, then cancel without presenting a card. This
checks that cancellation permits the second order to start and does not leave
the browser or server stuck behind the previous payment. No result for this
lock-release follow-up is claimed yet.

The follow-up screenshot shows **Payment cancelled** on order `1009` and its
existing Revolut line. **PASS for starting the previously blocked order after
the first order's cancellation, then safely cancelling that new request.**
At 11:36:55 UTC the read-only check found exactly one new operation, `13`,
for UUID `f312aad6-2544-492e-a12a-7ac1f6d6e8d0`, line
`3ab8e665-177c-4dc1-82be-aa39b190e04f`, attempt one, one GBP minor unit.
Created at 11:36:07.535492 UTC, after operation `12` was cancelled, it is
cancelled / provider cancelled, retry safe and not blocking, last written at
11:36:20.753574 UTC. Merchant order is
`6abba2a7-ecaa-a687-92ab-a38c4c78ce3d`; intent is
`6abba2a7-ad35-a6b9-a9e8-2517f6224d5a`. It has no payment reference, saved
POS order or tender. There are thirteen payment operations and no blocking
card payment operation. Refunds `1`–`3` remain pending / processing and
unverified; the charge budget is unchanged at four pence spent, six available.

Independent Merchant GETs at 11:37:15 UTC returned HTTP 200: operation `13`'s
intent is cancelled for one GBP minor unit, updated at 11:36:20.576307 UTC,
and its underlying payment list is empty. No card charge occurred. The
screenshots do not independently document the physical terminal amount or
idle display, so those displays are not separately claimed as verified.

The next guided subcase is a paid retry after a confirmed cancellation on
the same order and payment line. Close the cancellation dialog on `1009`,
click its existing line's Retry once, confirm the terminal requests `0.01 GBP`,
and present the card once. This uses one penny of the already-approved
aggregate additional charge budget if captured. Expected is a second attempt
linked to cancelled operation `13`, one captured payment, and one paid POS
order; record whether receipt navigation is automatic or requires Check
status. No retry dispatch or success is claimed yet, and the actual captured
budget remains four pence until verified. Refund eligible test charges after
their payment evidence is recorded, as already authorized.

The operator reports that the paid retry opened the receipt automatically
this time, without an unresolved error. The screenshot shows receipt
`261-2-000009`, one test-product unit at `0.01 GBP`, total `0.01`, one Revolut
tender for `0.01`, and payment reference
`6abba353-67f4-a8d3-9303-1440a9f4c456`.
**PASS for a paid retry after confirmed cancellation on the same logical
payment line, with automatic receipt navigation in this run.** The previous
automatic-completion failures on operations `10` and `11` remain open; one
successful run does not resolve their intermittent behavior.

At 11:39:53 UTC the read-only check found exactly operation `14` as the new
attempt: attempt two, previous operation `13`, same order UUID
`f312aad6-2544-492e-a12a-7ac1f6d6e8d0` and payment line
`3ab8e665-177c-4dc1-82be-aa39b190e04f`, one GBP minor unit, verified /
provider captured. It was created at 11:38:48.201928 UTC and verified at
11:39:02 UTC. Merchant order is
`6abba348-9bb1-ab4d-9172-88b827ff2b97`, intent
`6abba348-0cde-aa08-8630-901a353af779`, payment
`6abba353-67f4-a8d3-9303-1440a9f4c456`. Operation `13` remains cancelled,
without a payment reference or settlement. There are fourteen payment
operations and no blocking card payment operation.

Exactly one paid POS order exists for that UUID: order `11`,
`Davai GBP Terminal Test - 000009`, receipt `261-2-000009`, total and paid
amount `0.01`, zero change, no invoice. Product line `12` contains one unit
of variant `3` at `0.01`. Its sole tender, payment `9`, is method `4`,
amount `0.01`, done, on the same logical line, linked to operation `14`
and the matching captured payment reference.

Independent Merchant GETs at 11:40:18 UTC returned HTTP 200: the intent is
completed and the underlying payment is captured for one GBP minor unit,
on the matching order. The order's payment list contains exactly that one
captured payment. This establishes underlying financial success, rather
than relying only on intent completion or the receipt screenshot. Payment
creation was 11:38:59.631452 UTC and capture update 11:39:01.652910 UTC.
The operator has not separately reported the physical terminal's displayed
amount for this retry.

Five additional pence are now captured in total; five remain in the approved
ten-penny aggregate charge budget. Refunds `1`–`3` remain unverified and
processing; this new penny has not yet been refunded. No agent financial
mutation occurred.

The next no-charge subcase will refresh the completed receipt once, then
inspect Orders with the Paid filter and select `261-2-000009`. Expected is
one paid order still showing `0.01`, without another terminal request or
payment attempt. The pre-refresh baseline is one paid order and operations
`13` cancelled / `14` verified for the same logical payment line. No
post-success refresh result is claimed yet; refund this eligible test penny
after preserving that evidence.

The post-refresh screenshot shows receipt `261-2-000009` once under the Paid
filter, amount `0.01`, with one test-product unit at `0.01` and no linked
return yet. **PASS for a normal browser refresh after the completed payment:**
the paid sale remains available without another recorded payment attempt.
This does not exercise a reload between capture and order persistence or
network loss during that interval.

The read-only check at 11:42:07 UTC still found fourteen payment operations,
latest `14`, with no blocking card payment operation. For this order,
operation `13` remains cancelled and operation `14` remains verified /
captured with unchanged references and timestamps. There is exactly one
saved paid POS order (`0.01` total and paid) and one tender (`0.01`). Source
`14` has one GBP minor unit captured, zero reserved or refunded, and one
available. Refunds `1`–`3` remain pending / processing and unverified; the
additional charge budget remains five pence spent and five available.

The next authorized cleanup returns the paid test penny from
`261-2-000009`: select its product, quantity one, create the one-penny return,
choose Revolut, and open its Refund allocation dialog. Before confirming
once, check source `14`, captured payment
`6abba353-67f4-a8d3-9303-1440a9f4c456`, remaining `0.01 GBP`, refund amount
`0.01`, and return total `-0.01`. The cancelled original attempt `13` is not
an eligible refund source. Preserve existing pending returns. No new return
or refund dispatch is claimed at this preparation; record the resulting
refund reference and status after the operator's confirmation.

The operator's next screenshot shows return `1010 (Refund)`, UUID
`98451171-7364-4fc0-899d-6af5f404bf34`, with total `-0.01` and the allocation
dialog open. Source `14` is selected, its original order and captured payment
match operation `14`, its remaining balance is `0.01 GBP`, and the refund
amount and remaining return amount are both `0.01`. This is the expected
pre-confirmation allocation for paid order `1009`.

A fresh read-only database check at 12:47:49 UTC confirms source `14` is still
verified / captured with one available GBP minor unit and the same payment
reference. There is no refund operation for this new return UUID. There are
still fourteen payment operations and three refund operations; refunds `1`–`3`
remain pending / processing and unverified. No card payment operation is
blocking, and the additional charge budget remains five pence spent and five
available. The next operator action is the already authorized single click
on **Confirm refund allocation**, then preserve the resulting refund reference
and status. No dispatch or completion is claimed from this dialog screenshot.

The operator then confirmed the allocation and supplied the resulting
`1010 (Refund)` screenshot: Revolut line `-0.01`, **Refund in process**,
source `14`, original order `6abba348-9bb1-ab4d-9172-88b827ff2b97`, and refund
`6abbb3a9-c456-a39b-beb9-87ce71dc00d1`. Validate remains inactive and the
displayed remaining return is `-0.01`; this pending refund is not yet counted
as settled tender.

The read-only database check at 12:49:16 UTC found exactly one operation for
this return: refund `4`, source `14`, amount and return total each one GBP
minor unit, state pending / provider processing, dispatched at 12:48:41 UTC,
unverified and deployment-blocking. Payment-line UUID is
`3fa36490-b5d6-4678-946b-9cca059571d3`. Its snapshot has one test-product line
with quantity `-1`, unit price `0.01`, no discount or tax, and original POS
line `12`. No settled POS return is saved for this UUID. Source `14` is still
verified / captured, now with zero available minor units because refund `4`
reserves its penny.

Independent Merchant GETs at 12:49:17 UTC returned HTTP 200: refund
`6abbb3a9-c456-a39b-beb9-87ce71dc00d1` has type refund, state processing,
amount `1`, currency GBP, and the matching original related order. That
original is still a completed one-penny GBP payment order. **Submission and
reference matching are confirmed; final refund completion remains open.**
There are fourteen payment operations, no blocking card payment operation,
and four actual one-penny refunds, all pending / processing and unverified.
The additional charge budget remains five pence spent and five available.
The agent made only read-only database and Merchant GET requests.

The next no-charge UI guard test attempts to edit this submitted refund's
payment-line amount to `0.02` with the keypad. The deployed adapter checks
`paymentActions(...).canEditAmount` in both payment-screen input handling and
the payment model's amount setter; a dispatched, unverified refund is locked.
Expected is an unchanged `-0.01` line and inactive Validate, with the same
refund reference and no second operation. This is a planned live test, not a
passing result yet. Keep the pending return and record the operator's screen
and independent operation/snapshot check after the attempt.

The operator reports that the Revolut payment line was selected, entering
`0.02` changed nothing, and Validate remained disabled. **PASS for the live
POS payment-line amount lock after refund submission.** The read-only check
at 12:53:14 UTC confirms exactly one refund operation for return `1010`,
still operation `4`, source `14`, amount and return total both one minor unit,
unchanged payment-line/refund references, dispatch time, and immutable line
snapshot. The provider state remains processing; the local state is now
unresolved and unverified, with the penny still reserved and no settled POS
return saved. There are still fourteen payment operations, no blocking card
payment operation, and four refund operations. No new request or amount
mutation is recorded from the input attempt. This does not claim protection
against a tampered RPC, final refund completion, or restored-browser input.

The next authorized paid scenario is a fresh two-penny order containing two
test-product units at one penny each, paid with two distinct one-penny
Revolut payment lines. Its total intended additional capture is `0.02 GBP`,
within the five remaining pence; no amount is spent at preparation. Keep all
existing pending returns. First prepare the cart and open its Payment screen
without selecting a method; verify its UUID, total and absence of tenders
before starting a terminal request.

The installed POS auto-starts a card request for the full remaining balance
when Revolut is selected. A controlled no-card cancellation followed by
editing the safely cancelled line to one penny and Retry will be needed to
prepare the first partial payment without changing configuration. Inspection
of deployed `paymentActions` and `_create_revolut_operation_owned` confirms
that a retry-safe prior attempt permits amount editing and a new linked
attempt with the updated amount, provided no successor already exists.
The cart snapshot stays two pence throughout. Verify cancellation and then
the terminal's one-penny amount before the operator presents the card. After
that payment is verified, one penny should remain due, allowing a second
Revolut line for the remaining penny. This is a planned live scenario, not
a passing result or a dispatched/captured payment yet; all financial actions
remain operator-driven.

The operator's preparation screenshot shows positive order `1011`, UUID
`d456938f-d37d-491b-a908-a3eb15cf4695`, on the Payment screen, total `0.02`,
no payment lines and inactive Validate. Product quantities and unit price are
not visible on this screen; verify the persisted attempt snapshot before the
first paid retry. The read-only baseline at 12:55:46 UTC found zero payment
operations and no saved POS order for this UUID, fourteen total payment
operations, and no blocking card payment operation. Four refund operations
remain pending / processing and unverified. The additional charge budget
remains five pence spent and five available.

The next operator-driven setup is to select Revolut once without presenting
a card. This auto-starts the two-penny remaining amount. While Waiting for
card, use **Cancel** beneath that status, then preserve the Payment cancelled
screen before editing or retrying. If the foreground shows unresolved first,
Check status can reconcile the same request and restore Waiting for card;
cancel only then. Verify the recorded cancellation, retry-safe status, lack
of an underlying captured payment and cart snapshot before guiding the
one-penny amount edit. No request, cancellation or capture is claimed at this
baseline.

The operator supplied the `1011` Payment cancelled screen, with the selected
Revolut line still `0.02`, total and remaining both `0.02`, Retry available,
and Validate inactive. The read-only check at 13:09:35 UTC found exactly one
attempt for this order: operation `15`, attempt one, no predecessor, amount
two GBP minor units, state cancelled / provider cancelled, retry-safe, with
no deployment block or underlying payment ID. Its payment-line UUID is
`1fd30b10-906c-458a-8636-1909e569d514`, Merchant order
`6abbb84a-0fb1-a011-802e-8a04bf1e2acd`, and intent
`6abbb84a-a5f9-a0f7-9733-17dd27825d2b`. It was created at
13:08:26.244826 UTC and locally updated at 13:08:40.017926 UTC. The immutable
cart lines confirm two test-product units at `0.01`, zero discount and no
tax; no POS order or tender is saved for this UUID.

Independent Merchant GETs at 13:09:36 UTC confirm the intent is cancelled,
amount `2`, currency GBP, linked to the matching order, and the order's
underlying payment list is empty. **PASS for this no-card cancellation setup:**
the two-penny request was cancelled without a card payment and can be retried
safely. There are fifteen payment operations, no blocking card payment
operation, and the additional captured amount is still five pence. All four
existing refunds remain pending / processing and unverified. This does not
claim that the device's idle display was independently confirmed.

The next authorized step edits this safely cancelled line to `0.01` while
leaving the two-penny cart unchanged, then Retry once. The operator must see
`0.01` on the POS payment line and one penny on the terminal before presenting
the card once. Expected after verification is one completed one-penny tender
and `0.01` remaining due, with no completed receipt yet. Preserve that screen
before adding the second Revolut line. If the first result is unresolved,
Check status reconciles that existing payment rather than creating another
retry. No edited amount, successor attempt or paid partial tender is claimed
at this checkpoint.

The operator reports needing **Check status** after the first one-penny paid
retry and supplies the resulting `1011` screen: total `0.02`, one successful
Revolut line at `0.01`, remaining due `0.01`, Validate inactive, and no
completed receipt. **PASS for the first partial-card allocation and recovery
of its existing payment.** The remaining balance and lack of checkout are
correct for this partially paid cart. Initial automatic status handling did
not complete this payment in the foreground; record that repeated issue
separately from the working manual reconciliation.

The read-only check at 13:15:48 UTC finds operation `15` still cancelled,
amount two GBP minor units, and operation `16`, attempt two linked to `15`,
verified / captured for one GBP minor unit. Operation `16` has the same
order UUID, payment-line UUID and unchanged two-unit one-penny cart snapshot.
Its Merchant order is `6abbb955-4853-a1c7-9164-afb3fe751e0d`, intent
`6abbb956-a350-abea-9541-8912ac1b78b1`, and captured payment
`6abbb96a-d535-aa0b-93ef-a7ddc68837ea`. It was created at 13:12:53.587043 UTC
and verified at 13:14:58 UTC. No saved POS order or tender is linked yet,
consistent with the still-partially-paid order.

Independent Merchant GETs at 13:15:49 UTC confirm the completed intent links
to that exact payment/order, the underlying payment is captured for `1 GBP`
minor unit, and the payment order contains exactly that one captured payment.
The provider payment was created at 13:13:14.557300 UTC and updated at
13:13:16.765146 UTC. Six additional pence are captured in total; four remain
in the approved ten-penny budget. There are sixteen payment operations, no
blocking card payment operation, and four existing refunds still pending /
processing and unverified. No second card line or completed two-card sale
is claimed yet.

The next authorized step selects **Revolut – Davai** once in the left method
list to add a distinct second line for the remaining penny. Keep the verified
first line and cart unchanged. Confirm the terminal requests one penny,
present the card once, and preserve the resulting receipt or unresolved
screen; Check status can reconcile that second request if needed. Expected
final sale total is `0.02`, paid by two verified one-penny lines with distinct
captured references and no extra captured payment. The second penny would
bring the additional aggregate captured amount to seven pence, leaving three;
that capture is not claimed before execution and verification.

The operator reports needing **Check status manually** for the second portion
too, and supplies receipt `261-2-000011`: two units at `0.01`, total `0.02`,
two Revolut tenders of `0.01`, and two distinct payment references. **PASS for
the live sale funded by two separate Revolut payment lines and their manual
status recovery.** Automatic foreground status handling failed for both
portions; this acceptance issue remains open. Receipt navigation following
the verified second payment does not establish automatic status reconciliation.

The read-only check at 13:20:08 UTC found seventeen payment operations and no
blocking card operation. Cancelled operation `15` remains without a payment
ID. Operation `16` remains verified / captured, amount one GBP minor unit,
and is now linked to POS order `12` and tender `10`. The distinct second
line is operation `17`, attempt one, no predecessor, amount one GBP minor
unit, verified / captured at 13:19:03 UTC. Its line UUID is
`6ec09706-5d27-4689-aad2-0e894e305a37`, Merchant order
`6abbba92-90a6-ad25-9ffd-6c5f114eb2c3`, intent
`6abbba92-0e4e-a567-9042-a9b99922e06a`, and captured payment
`6abbbaa2-2368-af52-a7d7-c8bfd338aaf5`. It was created at
13:18:09.846690 UTC and is linked to POS order `12` and tender `11`.
Both captured operations preserve the original two-unit one-penny cart lines.

Exactly one saved paid POS order exists for this UUID, named
`Davai GBP Terminal Test - 000011`, receipt `261-2-000011`, total and paid
both `0.02`, change zero and no invoice, dated 13:19:03 UTC. Original product
line `13` has quantity two, unit price `0.01`, zero discount and subtotal
`0.02`. Exactly two saved method-`4` tenders are done, amount `0.01` each,
with their corresponding distinct line UUIDs, operation IDs and captured
transaction references.

Independent Merchant GETs at 13:20:09 UTC confirm both payments are captured
for one GBP minor unit, linked to their matching original orders, with
exactly one captured payment in each provider order. The second provider
payment was created at 13:18:26.865035 UTC and updated at 13:18:29.079364 UTC.
Eligible sources `16` and `17` each have one captured penny available and no
refund reservation. The cancelled two-penny operation `15` is not a refund
source. Seven additional pence are now captured; three remain in the approved
ten-penny aggregate budget. Four existing refunds remain pending / processing
and unverified. No new refund is claimed from this paid receipt.

The next authorized refund test creates a return of both original units,
total `-0.02`, then opens Revolut refund allocation without confirming yet.
Expected are two eligible sources, `16` and `17`, each with `0.01 GBP`
remaining and its own captured payment reference, while the remaining return
amount is `0.02`. This exercises selection among multiple original payments
on the same sale. Inspect that dialog before allocating one penny to a
selected source. Each source is individually capped at one penny. Once an
allocation is processing, reconcile it before adding another tender to the
same return; subsequent allocation and checkout must retain verified proof.
Full allocation and final refund settlement remain unrun at this checkpoint.

The next operator screenshot shows return `1012 (Refund)`, total `-0.02`,
with the allocation dialog displaying exactly the expected sources. Source
`17` is selected, remaining `0.01 GBP`, with its matching original order and
captured payment ending `aaf5`; source `16` is also available for `0.01 GBP`,
with its matching original order and captured payment ending `37ea`. The
refund input is `0.01`, while Remaining on this return is `0.02`. **PASS for
displaying the two eligible original payment allocations and their separate
balances.** The screenshot does not establish how source `17` was selected,
so no automatic-selection behavior is claimed. Its crop does not expose the
new return UUID; obtain that from the submitted operation later.

The fresh read-only baseline at 13:24:36 UTC confirms both sources are
verified / captured, each one GBP minor unit, tied to the same paid POS order
`12` and their distinct done tenders. Neither has any refund reservation or
refund operation yet. There are still four refund operations, none verified,
seventeen payment operations, and no blocking card payment operation. Seven
additional pence are captured and three remain available in the charge
budget. Opening this allocation dialog has not submitted a refund.

The next authorized source-cap test keeps source `17` selected, enters
`0.02` and confirms once. Expected is rejection even though the whole return
is two pence: the selected payment has only one penny available, and source
`16`'s separate penny must not be pooled into that request. Only after that
rejection, restore amount `0.01` and confirm once to submit the eligible first
allocation. Preserve the resulting reference and status; verify it is tied
to source `17` and leaves source `16` unreserved. No rejection, dispatch or
final refund result is claimed at this pre-confirmation checkpoint.

The operator reports that `0.02` was denied, then supplies the accepted
`0.01` screen on `1012 (Refund)`: one Revolut line at `-0.01`, Refund in
process, source `17`, matching original order, and refund
`6abbbc70-d2d2-a4c0-a0e7-1e7d1c0cf28e`. **PASS for the individual-source
cap in the normal multi-source POS allocation flow:** the other original
payment's penny did not permit a two-penny request against source `17`.
The screenshot's remaining return is still `-0.02`, since the submitted
penny is not yet verified as a settled tender. This is not a completed
two-payment refund or direct-RPC/concurrent-claim coverage.

The read-only check at 13:27:28 UTC finds exactly one new refund operation,
`5`, source `17`, amount one GBP minor unit, return total two minor units,
return UUID `b7ce760b-f05c-4a7c-b771-fe70fdda710c`, and payment-line UUID
`6d2a6268-c771-4c08-b0ac-c8846c7d26a7`. It was dispatched at 13:26:08 UTC,
is locally unresolved / provider processing, unverified and deployment-
blocking, and has no saved POS order or tender. Its immutable snapshot
contains two returned units at `0.01`, zero discount/no tax, original line
`13`, and return-line UUID `aaf1a0fa-e26d-4073-9851-fdecf2cdd662`.
Source `17` now has one reserved penny and zero available; source `16`
remains unreserved with one penny available. No refund operation exists for
source `16`.

Independent Merchant GETs at 13:27:28 UTC confirm the new refund has type
refund, state processing, amount `1`, currency GBP, and related original
order `6abbba92-90a6-ad25-9ffd-6c5f114eb2c3`; that original remains a
completed one-penny payment order. There are still seventeen payment
operations, no blocking card operation, and now five actual one-penny
refunds, all provider processing and unverified. Seven additional pence
are captured and three remain in the approved charge budget. Keep `1012`
open: reconcile this allocation before adding the remaining source-`16`
tender to the same return. No agent financial mutation occurred.

The next no-card scenario prepares two independent POS browser instances
sharing the configured terminal, to exercise the server terminal lock beyond
the earlier one-browser native guard. Keep the original Chrome POS and all
pending returns open. Open Chrome Incognito, sign into the same Odoo account,
and open **Davai GBP Terminal Test**. Prepare a separate one-penny positive
order there and stop at its Payment screen before selecting a payment
method. Record the second instance's configuration, order UUID and amount
before starting either request. This uses two instances under the same user;
it does not prove different-user access-control behavior. No concurrency
request or result is claimed at this preparation, and no card will be
presented for the planned contention/cancellation subcase.

The operator's Incognito preparation screenshot shows POS configuration `2`,
order `2001`, UUID `bed1e3ed-3369-4dce-acc3-5b9067bc9247`, total explicitly
displayed as `£0.01`, both test payment methods, no payment line and inactive
Validate. This is a separate browser instance from the original Chrome POS;
it is ready for the independent-browser contention test, not a concurrency
result yet.

Read-only preflight at 13:34:47 UTC finds seventeen payment operations, zero
blocking card operations, and no operation or persisted order for the
Incognito UUID. Session `5`, configuration `2`, remains opened. Original
browser order `1008` / UUID `a5deb51e-0299-4182-98da-f94985ef4944` still has
only operation `12`, amount one GBP minor unit, safely cancelled and retry-safe,
without a deployment/terminal blocker. Refunds `1`–`5` remain pending /
provider processing, unverified and deployment-blocking. The additional
captured charge budget remains seven pence used and three pence available.

The next operator steps reuse the existing cancelled one-penny line on `1008`:
confirm its one-penny total and Retry once in the original browser, without
presenting a card. While that request is waiting for a card, immediately
select Revolut once on Incognito order `2001`. Record the second browser's
result and verify both order UUIDs against the server operations before
claiming the terminal-lock test passed. Neither request has been dispatched
at this preparation check, and no financial mutation was made by the agent.

## L07 independent-browser terminal contention — server guard PASS, UI feedback FAIL, 2026-09-29

After retrying `1008` in the original browser, the operator selected Revolut
on Incognito order `2001`. Their screenshot shows the same Incognito order
UUID, a one-penny Revolut line, inactive Validate and **Communication
interrupted — payment unresolved**. Its dialog says communication was
interrupted and that the payment may have succeeded. This is misleading
feedback for the server's confirmed terminal-lock rejection.

Read-only database verification at 13:38:10 UTC finds exactly one new payment
operation, `18`, for original-browser order `1008` /
`a5deb51e-0299-4182-98da-f94985ef4944`. It is attempt two linked to cancelled
operation `12`, using the same payment-line UUID
`f7830ad8-dacd-46b8-8b63-b9015279885a`, amount one GBP minor unit, created at
13:37:26.960844 UTC. Its Merchant order is
`6abbbf17-c801-ac37-8b75-ad6c6fb2c395`, intent
`6abbbf17-1a38-ac12-b5df-398b434b396f`, with no payment reference. It remains
pending / provider pending and terminal-blocking. There is no payment
operation or saved POS order for Incognito UUID
`bed1e3ed-3369-4dce-acc3-5b9067bc9247`, and neither of these two browser
orders has a persisted POS sale.

The server log records **An existing Revolut payment blocks this order or
terminal.** at 13:37:35 UTC. Independent Merchant GETs at 13:38:41 UTC return
HTTP 200: operation `18`'s intent is pending for one GBP minor unit, linked to
the matching Merchant order, and its underlying payment list is empty.
**PASS for the server terminal lock across these two independent browser
instances:** the second order was rejected before operation creation and
financial dispatch while the first held the terminal. Both browser instances
use the same account; different-user permissions and a simultaneous-start
race are not covered. The rejection must not be classified as a successful
second charge or an uncertain dispatched payment.

**FAIL for clear busy-terminal feedback:** the Incognito POS replaced the
server rejection with a communication-interrupted/payment-may-have-succeeded
message and Check status. The deployed frontend sets `revolutStarted` before
the start call and uses generic interrupted handling when that call rejects.
This inspection explains the displayed message but does not establish live
recovery or cleanup of the blocked browser line; those remain to be exercised.
No addon fix or deployment is claimed.

There are eighteen payment operations and one active card-operation blocker.
The additional captured amount remains seven pence, leaving three pence in
the approved budget. Refunds `1`–`5` remain processing/unverified and retain
their reservations. Next, use the original browser's existing `1008` line
to check status if needed and cancel the request while it is waiting for a
card, then verify authoritative cancellation and an empty payment list before
testing recovery of Incognito `2001`. Keep both browser orders and all pending
returns open, and present no card. All agent Merchant requests were GET only.

The operator's next screenshot shows original-browser order `1008` with
**Payment cancelled**, a one-penny line, Retry, one penny remaining and inactive
Validate. Read-only verification at 13:40:33 UTC finds the same operation
`18` safely cancelled / provider cancelled, `retry_safe = true`, no payment
reference and no remaining terminal blocker. Its last local update is
13:39:54.132714 UTC. There are still eighteen payment operations and no
operation or persisted order for Incognito `2001`; neither browser order has
a saved paid sale.

Independent Merchant GETs at 13:40:33 UTC confirm HTTP 200: the same one-penny
intent is cancelled, provider update 13:39:53.953926 UTC, and the order's
underlying payment list is empty. **PASS for cleanup of the first request and
release of the server terminal lock without a charge.** The screenshot does
not separately establish the exact operator click sequence or the terminal's
idle display. Seven additional pence remain captured, three pence remain
available in the budget, and refunds `1`–`5` remain processing/unverified.

Next, keep `1008` cancelled and, on the unchanged Incognito `2001` line, close
the message and press Check status once. Record whether the blocked line
recovers after the terminal lock has been released, then verify that this
status check did not create an operation or dispatch a new payment. No card
will be presented, and blocked-line recovery is not a passing result yet.

The operator pressed Check status on Incognito `2001` after cancellation of
the first browser's request. The next screenshot still shows **Communication
interrupted — payment unresolved**, Check status, one penny remaining and
inactive Validate. **FAIL for recovery of a request rejected before dispatch:**
the blocked browser line remains stuck even though the server terminal lock
has been released.

Read-only verification at 13:42:07 UTC finds eighteen payment operations,
zero blocking card operations, no operation or saved POS order for Incognito
UUID `bed1e3ed-3369-4dce-acc3-5b9067bc9247`, and original-browser operation
`18` still safely cancelled with the same references. This Check status did
not create an operation or dispatch a second payment. The financial guard
and read-only recovery action remain safe; the cashier cannot recover the
rejected line through the offered control. The additional captured amount
remains seven pence, leaving three pence in the approved budget. All five
refunds remain processing/unverified.

A deterministic local characterization copies the actual deployed
`revolut_payment_state.js` at commit
`76209bb3c3ac705dcc724ba329e044c6626c59cd` into the isolated debug directory
`/tmp/ticket12-contention-repro-20260929`. A mocked adapter returns no existing
operation, rejects the start with the confirmed server terminal-lock message,
and returns no operation again when Check status is invoked. No HTTP or
Merchant call is made by this test. The command
`node --test --test-isolation=none /tmp/ticket12-contention-repro-20260929/contention_recovery.test.mjs`
fails the recoverability assertion (`retrySafe` expected true, observed false).
The actual module makes calls `find`, `start`, `find`, shows interrupted once,
remains checkout-blocking, and reports both retry and deletion unavailable.
This reproduces the stuck state in milliseconds; the native status transitions
and server exception are fixture inputs, not a captured browser/RPC trace.
Deletion unavailability is characterized locally, not claimed as a separate
operator deletion test.

The future fix must distinguish an authoritative pre-dispatch terminal-busy
rejection from an uncertain lost start response, offer clear busy feedback,
and let that rejected line recover after the terminal is free. Generic
transport failures and uncertain financial starts must retain reconciliation
and duplicate-charge protections. No addon change, successful fix test or
deployment is claimed. The blocked Incognito instance can now be closed after
recording this failure; the original browser and its pending returns must
remain preserved.

## Physical terminal preparation — PARTIAL, 2026-09-29

This section preserves the earlier operator-reported preparation. Subsequent
discovery, configuration and live checks above verified the matching location,
configured terminal and online Pay at Counter eligibility.
The operator reports connecting the terminal to Wi-Fi, logging into Test Guzman
and enabling Pay at Counter. The terminal warned that standalone checkout would
be unavailable in this mode and that it would accept card payments sent from
another POS. It also described exiting the mode through a long press and the
staff passcode. This matches the expected passive-terminal behavior.

The operator subsequently reported **Davai** as the currently selected terminal
location and explicitly chose it for acceptance, despite other available
locations. The location name suffices for this shared record; its street address
is not copied here. Later discovery evidence supplies the provider location
UUID/type and exact terminal association.

The operator reported firmware **V1.0.37** and terminal application version
**1.102 (101)**. Application version 1.102 meets the documented minimum 1.56
(minor version 102 is later than 56); firmware is recorded separately, with no
additional firmware acceptance claim.

These device-version details are operator observations; the discovery checks
above subsequently verified a single online terminal at Davai through the
Pay at Counter filter. Reconfirm the terminal's waiting screen before the first
physical payment. No passcode was disclosed or recorded, and no payment was sent.

## Remaining gates

Davai's matching physical location, terminal UUID, online discovery,
server-only credential, payment-method configuration and native manager
Check Connection passed the checks recorded above. Device-version observations
remain operator-reported. The separate GBP checkout's browser display has been
observed; reconfirm the device's idle display before another payment.
The initial one-pound payment attempts were cancelled without payment, as
recorded above. The approved `0.01 GBP` payment is now captured and the Odoo sale
is paid, with matching receipt references. The operator confirmed the terminal
amount and automatic checkout; **L01 is PASS**. Its approved full `0.01 GBP` refund is
**IN PROGRESS**: Revolut reports processing and Odoo retains its reservation.
The operator independently performed the additional one-penny decline and
cancelled retry recorded above. The authorized single duplicate-refund guard
attempt passed in the normal POS allocation flow as described above. The
operator has also approved the further testing plan's aggregate `0.10 GBP`
additional-card-charge budget and refund plan, recorded above.
Seven additional pence are now captured: one on the Cash/Revolut split sale,
three on the three-unit sale, one on the successful retry after cancellation,
and two on the sale with separate Revolut payment lines. Three pence remain in that aggregate charge
budget. The split allocation and
same-payment status recovery passed, while initial automatic completion
failed again on the three-unit sale and remains an open release issue. Its
payment is verified and paid after Check status; its one-unit partial return
is submitted as refund `3`, still processing. Its return-total guard passed in
the normal allocation flow, and two pence remain available on its source.
The native POS quantity guard also rejected three further units when only two
remained; server RPC and concurrent quantity-claim coverage remain open.
The single-attempt no-card reload/status/cancel
subcase passed with operation `9`; broader interruption and concurrency cases
remain open.
The one-browser cross-order guard passed: `1009` was blocked while `1008` had
operation `12` in progress. Operation `12` was cancelled with no underlying
payment and no remaining terminal lock. Starting the previously blocked order
after that cancellation also passed with operation `13`, which was cancelled
without an underlying payment. Its paid retry passed with operation `14`,
attempt two linked to cancelled attempt `13`, exactly one captured payment,
one paid POS order, and operator-confirmed automatic receipt navigation.
The normal post-success browser refresh also passed without another attempt
or paid order. The independent-browser server terminal lock also passed:
operation `18` on original-browser `1008` blocked Incognito `2001` before
operation creation or dispatch. Its busy-terminal UI feedback failed, showing
communication interruption and a possibly successful payment despite the
server's rejection. The first request's cancellation and terminal-lock release
are verified without a charge. Blocked-line recovery failed: Check status on
Incognito `2001` leaves the line interrupted and checkout disabled despite no
operation existing, with no new financial dispatch. A deterministic local
characterization reproduces the unrecoverable state; fixing and retesting
busy feedback/recovery remain release blockers.
Different-user permissions, simultaneous starts and interruption between
capture and order persistence remain open. The retry's eligible penny is now submitted
as refund `4` on return `1010`, provider processing and locally unresolved /
unverified after the foreground wait. Its payment-line amount lock passed:
attempted input left the one-penny operation and snapshot unchanged and
Validate disabled. Restored-browser amount editing and tampered RPC coverage
remain open. Order `1011` is now paid `0.02` using two distinct verified
one-penny card lines (`16` and `17`), with one saved paid order and two done
tenders. The edited-amount retry is attempt two (`16`) linked to cancelled
two-penny request `15`, with the cart unchanged. That allocation and manual
status recovery passed for both portions; initial automatic status handling
failed for both and remains an open release issue. Return `1012` displayed
sources `16` and `17` with separate one-penny balances, passing the discovery
check. Its individual source-cap test also passed: `0.02` was denied against
source `17`, then `0.01` was submitted as refund `5`, still processing /
unverified. Source `16` retains one available penny; its remaining allocation
and complete two-payment refund are open.
The mixed-tender card-balance guard also passed in the normal POS flow. Its
accepted one-penny card allocation is refund `2`, still processing; the cash
portion and complete mixed-tender return remain open. There are now five actual
one-penny refunds processing against five different captured source payments.
The POS also blocked adding Cash to unresolved return `1005`, with no new
operation or settled return. A single refresh followed by Check status restored
the same refund without a duplicate; final refund completion remains open.
The agent has made no mutating Merchant request.

L02–L10 scenarios, test-money reconciliation, required provider discrepancy
resolution and instructions based on actual terminal observations remain open.
No screenshot balance, credential, passcode, card data or raw API response is
copied into this record.

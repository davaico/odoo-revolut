# Use POS Revolut

Complete [register setup](installation.md) first. Cashiers need a backend-user register grant; refunds and manual reconciliation require a POS manager with that grant.

## Take a payment

1. Review the goods. Remove Odoo-entered tips; customers choose tips on the terminal.
2. Select Revolut and use **Send** if shown. The terminal receives that line's amount.
3. The customer follows the prompts and presents their card.
4. Wait for verification. Odoo completes a fully paid sale when native checkout requirements are satisfied.

For cash/card splits, enter cash first and use Revolut for the remainder. For a partial card payment, use **Choose amount — [payment method]**, then add tenders for the balance. Keep paid goods and prices unchanged.

If price approval is required, a manager opens the saved order in their own Odoo session and selects **Approve Revolut Cart**. The cashier reviews the approved cart and uses **Resume**. Employee switching cannot grant this approval.

## Understand the payment status

| Status | Action |
| --- | --- |
| **Waiting for card** | Let the customer finish. |
| **Payment received — verifying payment details** | Money was captured. Keep the line; use **Check status** if offered while Odoo verifies the report/tip. |
| Declined, failed or cancelled | Use **Retry** only when offered. |
| Interrupted, timed out or unresolved | Keep the order and line. Reconnect, use **Check status**, then ask a manager if unresolved. |
| **Terminal busy — no payment request sent** | **Resume** when available, or remove the undispatched line if permitted. |
| **Verified — reconnect and Check status to restore checkout** | Reconnect and check the same line to restore checkout without charging again. |

**A timeout does not prove failure.** Never replace an uncertain charge with another payment/tender, clear browser storage or force a line paid. **Check status** recovers the existing attempt. Scheduled reconciliation records late outcomes; the original order still needs POS completion.

To cancel, use the line's cancellation/removal action and wait. Processing payments may be uncancellable; a payment that succeeds during cancellation remains recorded, and uncertainty keeps the line protected.

For preparation failures leaving a waiting line after reload, fix setup and choose **Check status** on the original line in its original open session. Use **Resume** or removal only when offered. Missing references or lost responses do not prove no payment started.

## Restaurant orders

Use the normal table and the addon’s Odoo 18 Dine In/Takeout preset. Split/merge orders before payment; changing identity or financial contents after an attempt starts is guarded. Moving the same draft between tables preserves its payment association.

Timed Takeout needs an available pickup date/time before collection. Choose another day if no slots remain. If checkout requests scheduling after capture, keep the order and line, select the slot, recover details with **Check status** if needed, then **Validate**. This completes the paid order without charging again; terminal success alone does not establish Odoo completion.

## Refund a sale in Odoo

1. As an authorized manager, open POS **Orders**, select the original sale and **Refund** the returned products/quantities.
2. Choose an original Revolut method on the payment screen and click **Refund**.
3. Select the original payment. Review **Base refund amount** and **Terminal tip refund amount**, then **Confirm refund allocation**. For a full refund, return all eligible goods and include the remaining tip you intend to refund.
4. Add a line for each further original payment. Refund cash/manual portions through their original tender with negative amounts.
5. Wait for verified success, then validate the saved return when all tenders are complete. Provider acceptance can still mean processing.

Preserve original prices, discounts, taxes and currency. Refund limits include original quantities, tender balances, and pending/uncertain reservations. A zero-value adjustment needs no reimbursement or balancing tender.

After a timeout/reload, keep the saved return and **Check status** on the same line. Replace only a confirmed failed allocation when permitted; never repeat completed or uncertain refunds.

In **Point of Sale → Revolut Refunds**, **Refund Status** describes the money and **Odoo Return** links the native return. **Restore missing return** reconstructs a missing older return without refunding again: review and validate its draft. Closed-session recovery uses a new session on the same authorized register. Uncertain refunds and unfinished returns can block register closure.

## Refunds issued from Revolut

Scheduled discovery finds terminal/other Merchant-tool refunds under **Revolut Refunds → Detected in Revolut**. Discovery may take time; a card refund alone does not return stock, credit an invoice or reimburse cash.

Choose **Complete native work**:

| Situation | Action |
| --- | --- |
| Goods returned | Confirm original products, positive **Return now** quantities, lots/serials and any requested base/tip split. **Review native work**, review the draft, then validate once the refund is verified. |
| Return already recorded | **Associate an existing native return**; select its exact reimbursement payment and all relevant external refunds. |
| No goods returned | **No products returned**; record a reason. Have an accountant prepare/post the correction for the exact sale and amount, then select it in completion. For an uninvoiced sale, configure the original payment method's outstanding account and prepare the correction through this workflow. |

These actions use money already refunded. A pending refund may reserve a draft but cannot validate it. **Native completion** and **Refund Status** are separate. Unexplained totals or unknown base/tip splits block further refunds pending review.

## Reconcile an uncertain payment

A manager opens **Point of Sale → Revolut Reconciliation**, selects the original attempt and **Request Reconciliation**. For lost references, use **Associate References** only after identifying the matching transaction in its original Merchant account. Odoo verifies amount, currency, device and order/tender identity.

There is no manual mark-paid/unlock. Keep unresolved records and involve an administrator or provider support through an approved private channel.

## Receipts and invoices

In POS **Orders → Paid**, find the sale and choose **Print Receipt**, **Details** or **Invoice**. A current authorized register session can access historical receipts after the original session closes.

- **POS sales receipt:** Odoo sale and tenders, possibly with Revolut references.
- **Accounting invoice:** separate native Odoo document; customer and invoice setup may be required.
- **Revolut payment receipt:** retrieve/reprint through the terminal's transaction history.

Printing a reference does not turn an Odoo receipt into a Revolut receipt. Reprinting sends no payment or refund.

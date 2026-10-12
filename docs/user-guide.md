# Use POS Revolut

An administrator must complete [installation and register setup](installation.md) before checkout. Cashiers need a backend-user register grant; refunds and manual reconciliation require a POS manager with the same register access.

## Take a payment

1. Add the goods and review the order. Remove any tip entered in Odoo; the customer chooses the tip on the terminal.
2. Select the Revolut payment method. If a **Send** button is shown, use it to start the selected line. The terminal receives that line's amount.
3. The customer follows the terminal prompts and presents their card.
4. Wait for Odoo to verify the payment. The sale completes automatically when the full order is paid and native checkout requirements are satisfied.

For cash plus card, enter the intended cash amount first and use Revolut for the remainder. For a partial card payment, use **Choose amount — [payment method]**, then add further tenders for the balance. A successful partial payment leaves the order open; it is not permission to change the paid goods or price.

If price control requires manager approval, a manager opens the saved order in their own Odoo session and selects **Approve Revolut Cart**. The cashier then uses **Resume** after reviewing the canonical cart. Switching employees in the cashier browser does not provide this approval.

## Understand the payment status

| What you see | What to do |
| --- | --- |
| **Waiting for card** | Let the customer finish on the terminal. |
| **Payment received — verifying payment details** | Money was captured; Odoo is verifying the report and tip details. Keep the same line and use **Check status** if offered. |
| Declined, failed, or cancelled | Follow **Retry** only when Odoo offers it after establishing that another charge is safe. |
| Interrupted, timed out, or unresolved | Keep the order and payment line. Reconnect and choose **Check status**; ask a manager if it remains unresolved. |
| **Terminal busy — no payment request sent** | Use **Resume** after the terminal is released, or remove the undispatched line if the interface permits it. |
| **Verified — reconnect and Check status to restore checkout** | Reconnect and choose **Check status** on the same line. Odoo restores checkout data without collecting again. |

A local timeout does not mean the customer was not charged. Do not create a replacement payment, use another tender to cover an uncertain charge, clear browser storage, or force a line paid. **Check status** recovers the existing attempt; it does not initiate a new charge. The scheduled reconciler can record a late outcome, but the original order must still complete through POS.

To cancel, use the payment line's cancellation/removal action and wait for confirmation. Processing payments may no longer be cancellable. If payment succeeds while cancellation is being checked, the verified payment is retained. An uncertain cancellation keeps the line protected.

If preparation failed before a payment existed and a waiting line remains after reload, fix the reported setup problem and choose **Check status** on the original line in its original open session. Odoo may then offer **Resume**, or allow its safe removal. A lost response or missing reference is not enough to establish that a line never started.

## Restaurant orders

Use the normal table and Dine In/Takeout preset. Settle bill splitting and order merging before collecting payment: changing order identity or financial contents after a Revolut attempt starts is guarded. Moving the same draft to another table preserves its payment association.

Timed Takeout currently has a known readiness gap. Select a valid pickup date/time before starting payment. If a captured tender is already present and native checkout asks for scheduling, correct scheduling and validate the **same order** without sending another payment. Automatic completion with a valid slot remains pending verification; do not assume the terminal's success screen means the native order completed.

## Refund a sale in Odoo

1. Sign in as an authorized POS manager. In POS **Orders**, select the original paid sale and use **Refund** to choose the products and quantities being returned.
2. On the payment screen, choose a Revolut method used on the original sale and click **Refund**.
3. Select the original Revolut payment. Confirm the **Base refund amount** and, when applicable, **Terminal tip refund amount**, then choose **Confirm refund allocation**. To refund everything, return all eligible goods and include the remaining tip amount you intend to refund.
4. Add a separate refund line for each additional original Revolut payment. Return any cash or other manual-tender portion using its original tender; manual refund amounts are negative.
5. Wait for financial verification, then validate the saved return once all its tenders are complete. A provider-accepted refund can remain processing; acceptance alone does not finish the return.

Odoo limits refunds by original products, quantities, tender balances, and prior reservations. Preserve the original prices, discounts, taxes, and currency. Pending or uncertain refunds consume refundable capacity until reconciled. A zero-value adjustment return needs no reimbursement payment; do not send a zero refund or add a balancing tender.

If a refund times out or connectivity fails, keep the saved return and use **Check status** on the same line, including after reload. Never issue another refund to work around uncertainty. For a confirmed failed allocation, replace only that failed line when permitted; completed allocations must not be repeated.

Open **Point of Sale → Revolut Refunds** for the worklist. **Refund Status** describes the money; **Odoo Return** links the native return. If a completed older refund lost its return, **Restore missing return** reconstructs a draft using the existing financial records. Review and validate it; restoration sends no new refund. If the original session is closed, recovery uses a new session on the same authorized register. Uncertain refunds and unfinished native returns can block register closure.

## Refunds issued from Revolut

The scheduled reconciler also discovers refunds made on the terminal or in other Merchant tools. They appear in **Revolut Refunds** with source **Detected in Revolut**. Discovery can take time. A detected card refund does not identify returned products and does not itself return stock, credit an invoice, or reimburse cash.

Open the refund and select **Complete native work**:

- For goods, confirm the original products, positive **Return now** quantities, and any required lot/serial details. Confirm the base/tip split when requested. Select **Review native work**, review the resulting draft, then validate the confirmed return once the refund is verified.
- Choose **Associate an existing native return** when the return was already recorded. Select its exact reimbursement payment and every relevant external refund instead of creating another return.
- Choose **No products returned** for a financial-only refund and record a reason. An accountant must prepare and post the required correction for the exact original sale and amount. Reopen completion and select that document. For an uninvoiced original, configure the original payment method's outstanding account and prepare its correction through this workflow.

These completion actions use money already refunded; they send no new card refund. A pending refund can reserve a draft but cannot validate it. **Native completion** and **Refund Status** remain separate. An unexplained refund total or unknown base/tip split blocks further Odoo refunds until reviewed; do not bypass that safeguard.

## Reconcile an uncertain payment

A manager opens **Point of Sale → Revolut Reconciliation**, finds the original attempt, and chooses **Request Reconciliation**. If a provider reference was lost, use **Associate References** only after identifying the matching transaction in the original Merchant account. Odoo checks the amount, currency, device, and saved order/tender identity before accepting it.

There is no manual mark-paid or unlock control. If the result remains uncertain, keep the original records and involve your administrator or provider support. Share original transaction references only through approved private support channels.

## Print a receipt or invoice

In POS **Orders**, choose **Paid**, find the sale, and use **Print Receipt**, **Details**, or **Invoice**. Historical receipt access can use a current authorized register session even when the original session is closed.

An Odoo **POS sales receipt** describes the sale and tenders. An **accounting invoice** is a separate native Odoo document and may require a customer and the normal invoice-creation flow. A **Revolut payment receipt** comes from Revolut; retrieve or reprint it through the terminal's transaction history. Adding a payment reference to an Odoo receipt does not make it the original Revolut receipt. Reprinting does not initiate another payment or refund.

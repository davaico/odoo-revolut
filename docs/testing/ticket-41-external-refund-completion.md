# Ticket 41 — Complete an existing Revolut refund in Odoo

This workflow records what happened after money was refunded through Revolut.
It uses the existing **Point of Sale → Revolut Refunds** worklist for both
**Odoo POS** and **Detected in Revolut** refunds. The latter label records the
known provenance; it does not establish whether a terminal or a portal initiated
the refund.

## Review the original sale

An authorized POS manager opens the refund and its **Original Sale**. Check the
purchase date, products, original prices and taxes, quantities, and all original
payment methods. Review the original card payment and Revolut refund references,
refund amount and currency, financial status, and any linked **Odoo Return**.

The provider's refund time, when available from authenticated evidence, is
separate from the time Odoo discovered the refund and the time Odoo confirmed its
status. **Unavailable** means no provider initiation time has been established.
Do not treat an import or reconciliation timestamp as the time money was refunded.

Money movement alone does not identify returned products. A refund of the entire
card payment on a sale paid partly in cash can still be a partial product return.
The card refund cannot pay the cash share. Choose the actual products and
quantities, or record that no goods were returned.

## Returned products

Start native completion and choose **Select returned products**. Select original
sale lines and the quantities the customer returned. The server checks the
remaining quantity after earlier completed returns and active reservations, and
keeps original prices, discounts, taxes, price list and fiscal position.

For tracked products, provide the original lot or serial details for the actual
items returned. Serial quantities must match the selected distinct serials. Do
not copy every original serial when only some items came back. Unsupported or
ambiguous lot evidence requires investigation before validation.

Review the native return draft and its recorded negative card payment. The
already-issued Revolut refund is linked as reimbursement with its existing
provider reference. Preparing or saving this draft does not send another refund.
The refund keeps its original source payment and source session; the native
return may use an open session on the same authorized register and company.

For several external refunds, associate each with its correct original card
tender and one payment on the same native return. Review their exact total. If
the selected return exceeds the reimbursements already issued, handle any
additional reimbursement as a separate authorized operation. Do not invent a
cash payment or mark an unpaid balance as complete.

When terminal tips exist, confirm the refund's base and tip amounts explicitly.
Their sum must equal the external refund, and both remain within the original
source/component ceilings and the selected return. An unknown split stays under
review; the gross amount does not prove a split. The conserved partial-return
rounding from [ticket 40](ticket-40-return-rounding.md) supplies product monetary
entitlements and native totals.

Validate the prepared return after checking the products, quantities, tracking
details and tenders. A completed card tender requires authoritative successful
provider evidence. Native validation uses Odoo's normal paid-order, stock and
accounting paths. The native return appears in **Orders**, links to the original
sale and refund, and uses Odoo's POS sales receipt for printing and reprinting.

Services create no inventory movements. Inventory products follow the register's
stock configuration, including any stock update deferred until session closing.
For an invoiced original, the applicable native credit note must relate to the
original invoice and carry the correct return total. Review unfinished pickings
or accounting errors as unfinished native work; a financial status of
**Completed** does not prove those documents finished.

## A return already exists

Choose **Associate existing return** when a separate native draft or finalized
return already records the same original sale and actual returned quantities.
Select its appropriate payment when required. Its amount, currency, register,
original-line relationships and refund allocation must match. A finalized return
must already contain the matching reimbursement evidence; association cannot
replace another refund's payment or reuse an unrelated reimbursement.

An incompatible or ambiguous document is rejected. Investigate its existing
references rather than creating a second return. Associating a finalized return
does not repeat native validation, inventory movement, invoice creation or card
refund. Keep the linked document and provider reference for reconciliation.

## No products returned

Choose **No products returned / financial only** and record a reason. This records
the responsible manager and time, original sale, external refund and accounting
correction links. It creates no product return, returned quantity or inventory
movement.

All supported financial-only cases require a separately posted native accounting
correction before this work can be marked complete:

| Original sale | Required evidence |
| --- | --- |
| Invoiced | A posted native customer credit note linked to the original invoice, in the correct company/currency and for the exact refund amount |
| Not invoiced | A posted separate native settlement journal entry with an explicit original-sale/refund relationship and the exact refund amount |

Use **Prepare financial correction** to create a native draft for accountant
review. For an invoiced sale, it prepares a reversal of the original invoice;
the accountant adjusts a partial correction before posting. An existing exact
posted credit note reversing that invoice can be associated instead. For an
uninvoiced sale, prepare the separate journal entry from this refund so its
original-sale relationship is recorded. The accountant records the appropriate
expense or correction debit and the exact refund credit to the original
Revolut outstanding account, in the refund currency. An arbitrary preexisting
journal entry does not establish that original-sale relationship.

The accountant posts the appropriate correction using existing accounting
permissions. Do not manufacture product quantities or a return picking to
obtain a financial document. A manager's reason or acknowledgement alone cannot
complete this disposition. Do not associate the same correction with unrelated
refunds or count an existing reimbursement twice. Completed correction evidence
is protected against cancellation or changes to its amount and settlement account.

## Pending refunds and recovery

An associated draft can wait while the provider refund is pending or uncertain.
Use **Check status** to reconcile it. The draft and financial reservation remain
recoverable, but native final validation is blocked until successful payment
evidence and exact tender totals exist. Failed or cancelled provider refunds do
not become completed negative card payments through manager acknowledgement.

After a reload, repeated click or failed validation, reopen the existing linked
draft or association. Continue from its recorded state instead of replacing the
provider refund. Native stock/accounting failures do not authorize another
financial request. Concurrent managers must resolve to the same recorded
association; review the current record if a transaction conflict asks for a retry.

Historical acknowledgements remain historical assertions. They do not establish
returned goods, a native return or an accounting correction. An older unlinked
external refund can enter this workflow using its existing financial evidence and
provider reference without repeating its financial instructions.

## Controlled acceptance using an existing refund

This scenario is an operator acceptance procedure, not evidence of a live run.
Use the existing release process for approval and physical acceptance. Automated
verification uses mocked Merchant HTTP and must assert zero financial POSTs.

1. Select a refund already issued through Revolut and matched to its known Odoo
   sale. Confirm its individual authoritative status, amount, currency and parent
   payment. Do not make a replacement charge or refund to prepare the scenario.
2. Record the existing sale, card payment and provider refund references and
   financial amounts. Review existing native returns or corrections first.
3. Choose the actual disposition: select the goods actually returned, associate
   an existing compatible return, or select financial-only with its posted native
   correction. For mixed tenders, demonstrate that the card amount does not
   become a cash reimbursement.
4. Save and reload the draft/association. Repeat the preparation click and
   confirm the same return and payment remain linked. No new financial request
   should be sent by preparation, association, saving or resuming.
5. For a verified product return, validate once, then reopen and reprint its
   native POS receipt. Confirm the expected negative order/payment linkage and
   stock movements for the selected quantities; services have none. For tracked
   items, confirm the selected lot/serials on the actual native moves. For an
   invoiced original, inspect the posted native credit note and original-invoice
   relationship. Account for configured stock updates at session closing.
6. For financial-only, confirm there is no returned quantity or stock movement,
   and inspect the posted correction's exact amount, original-sale relationship
   and stored manager/reason/time evidence.
7. Reopen the refund worklist and original sale. Confirm financial status and
   native completion are distinct, the linked documents are accessible, the
   original provider references/amounts are unchanged, and repeated completion
   creates no second document, stock effect, accounting entry or reimbursement.

Pending-to-completed, failure/recovery and concurrent-manager cases are exercised
with controlled mocked evidence in automated verification. Do not change real
provider states or issue money solely to exercise these cases.

## Public workflow entry points

The manager wizard offers `select_products`, `existing_return` and
`financial_only` dispositions. Its server operations are:

- `action_prepare_native_return(selection, session_id=None,
  return_order_id=None, payment_id=None, base_amount_minor=None,
  tip_amount_minor=None)`, where selection rows identify `original_line_id`,
  `quantity` and `lot_names`;
- `action_validate_native_return()` for normal native completion;
- `action_record_financial_only(...)` with a reason and native correction.

These workflow operations consume existing financial evidence and send no new
charge or refund financial requests. Company, register, manager and native
document access rules apply on the server as well as in the UI.

## Focused native stock/accounting verification

On 2026-10-05, the isolated runner below passed **8 tests, 0 failures/errors**
on pinned Odoo `19.0.20260908`; runner exit was 0:

```sh
ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket41-stock ./scripts/test-addon --test-tags '/pos_revolut:TestExternalNativeStock'
```

The tests exercise actual partial stock quant changes, completed native moves
with original outgoing-move links, selected lot and serial quantities, rejection
of foreign/missing/reused tracking details, and tracking checks when associating
an existing return. Services create no inventory movement. The invoiced-original
test posts an exact 6.17 native credit note linked to the original invoice and
posted negative payment accounting, then verifies repeated completion creates no
additional accounting entry. Another case actually closes the original session
and completes in a newly opened session on the same register while retaining
the refund's original financial session. Injecting a native stock-finalization
failure rolls back validation to the existing draft; resuming creates one return
move and retains the same payment. Every test mocks Merchant HTTP and asserts
zero calls after external-refund discovery.

Temporary local log: `/tmp/ticket41-stock.log`. Python compilation and
`git diff --check` also passed. This focused result does not establish physical
acceptance, the full-suite result, or final review; those are recorded by the
implementation verification before ticket closure.

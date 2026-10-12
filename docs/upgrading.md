# Upgrade POS Revolut

An upgrade must preserve existing financial records and their original Merchant account access. Read the release notes for the exact starting and target versions. Do not uninstall the addon, delete uncertain attempts, or change transaction references to make an upgrade pass.

## Before upgrading

1. Inventory pending or uncertain payments, refunds, unfinished native returns, and externally detected refunds requiring review. Reconcile them with their existing references and plan recovery before maintenance; do not collect or refund again to clear the list.
2. Back up the database, filestore, current addon release, and deployment configuration. Preserve historical secret references securely. Verify the restore procedure.
3. Test the upgrade on a disposable copy appropriate to your retention policy, with real provider traffic disabled. Run the relevant historical upgrade tests from [Contributing](../CONTRIBUTING.md).
4. Arrange a maintenance window and stop all Odoo workers. Replace the addon with the reviewed release while retaining any required legacy bridge described below.
5. Run the module update using your Odoo service configuration and environment:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --update pos_revolut --stop-after-init --no-http --workers=0
   ```

6. Restart only after the update succeeds. Verify company authorities, register grants, connection checks, scheduled actions, current setup, and access to historical sales/returns. Reopen every POS browser to load the new assets.

If the update fails, keep the service stopped while investigating. Do not restore an old database over financial operations that may have happened since its backup. Preserve the current evidence and reconcile provider outcomes before deciding a rollback or restore.

## Timed Takeout readiness

Version `19.0.1.18.14` checks required pickup scheduling before new timed Takeout collection. Update the module and reopen every POS browser to load the guard. This change introduces no data migration or credential rotation. Existing captured tenders keep their original references; correct scheduling and complete the same order without collecting again.

## Older Merchant authority records

Version `19.0.1.10.0` introduced company-scoped Merchant authorities. Upgrades do not automatically trust old secret references. A system administrator must verify each reference's Merchant account, company, and environment, create its authority, and attest each historical operation that still needs reconciliation or refunds. Creating or editing a current payment method does not attest historical operations.

For an independently reviewed operation, the administrator-only Odoo shell action is:

```python
operation = env["pos.revolut.payment.operation"].browse(REVIEWED_OPERATION_ID)
operation.action_revolut_authorize_legacy_credential()
env.cr.commit()
operation.invalidate_recordset(["credential_id"])
assert operation.sudo().credential_id
```

`REVIEWED_OPERATION_ID` must identify the exact reviewed record. The action binds only a matching authority and sends no Merchant request. If validation fails, roll back and investigate; do not invent a binding or approve records in bulk. Keep the original environment-variable reference available for historical work. Authorities cannot be reassigned across companies or environments.

## Register grants and historical financial evidence

Version `19.0.1.11.0` introduced explicit register grants. Existing registers start with an empty **Revolut backend users** list. Provision backend till users and supervisors before reopening Revolut checkout. Company membership, POS-manager status, or an employee PIN does not grant access automatically.

Older verified records may lack newer cart or tip evidence. Upgrades preserve them and their references; they do not fabricate authorizations or assume a zero tip. Affected recovery or additional allocations may require administrator/manager reconciliation. Keep original prices, currency, tender ownership, and financial history intact.

## Former Restaurant bridge

Version `19.0.1.15.0` merged the former `pos_revolut_restaurant` bridge into `pos_revolut`. When upgrading from a two-addon release, retain the old bridge directory on `addons_path` until the `pos_revolut` update succeeds. The migration retires the asset-only bridge while preserving financial records.

After success, remove the old bridge directory, refresh the Apps list, and confirm **POS Revolut** plus standard Odoo Restaurant are installed. There is no separate Revolut Restaurant addon for new installations. Do not manually uninstall POS Revolut to remove the old bridge entry.

## Retired custom receipt and evidence screens

Version `19.0.1.12.0` retired standalone Revolut receipt interfaces in favor of native POS receipts and invoices. Existing financial references, accounting documents, and saved PDF attachments remain preserved. Retrieve the original Revolut card receipt from the terminal. Verify native invoice PDF generation on the server where it is needed.

Version `19.0.1.16.1` removed the internal refund-discovery evidence screen and user read access. Matched refunds remain available through **Revolut Refunds**. Do not restore broad user permissions to inspect merchant-wide observations; an administrator should investigate retained server evidence through a trusted support process.

Newer releases preserve completed and uncertain refund allocations while improving fractional/discounted returns, external native completion, and saved-payment recovery. Missing or inconsistent historical evidence still requires reconciliation. The [user guide](user-guide.md) describes supported recovery actions; database edits and replacement financial operations are not recovery procedures.

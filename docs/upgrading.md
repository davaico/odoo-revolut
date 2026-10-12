# Upgrade POS Revolut

Preserve financial records and their original Merchant access. Review changes between the starting and target versions. Never uninstall the addon or delete uncertain attempts to make an upgrade pass.

## Upgrade procedure

1. Inventory unresolved payments, refunds, native returns and external refunds needing review. Plan recovery using their existing references.
2. Back up the database, filestore, addon and configuration; securely preserve secret references. Verify restoration.
3. Test on a disposable copy with real provider traffic disabled. Run relevant [historical upgrade tests](../CONTRIBUTING.md#choose-checks).
4. Stop all workers for maintenance. Install the reviewed release, retaining any legacy bridge described below.
5. Update with the service's configuration and environment:

   ```bash
   odoo --config /path/to/odoo.conf --database DATABASE_NAME \
     --update pos_revolut --stop-after-init --no-http --workers=0
   ```

6. After success, restart and verify authorities, register grants, connection checks, scheduled actions and historical sales/returns. Reopen every POS browser.

If updating fails, keep the service stopped. Preserve evidence and reconcile provider outcomes before rollback: restoring an older database could lose subsequent financial operations.

## Version-specific steps

### Timed Takeout — 19.0.1.18.14

Required pickup scheduling is checked before new collection. Update and reopen POS; no data migration or credential rotation is needed. For already captured payments, correct scheduling and complete the same order without collecting again.

### Merchant authorities — 19.0.1.10.0

Old secret references are not automatically trusted. A system administrator must verify each reference's account, company and environment, create its authority, and attest historical operations needing reconciliation/refunds. Editing current payment methods does not attest history.

For each independently reviewed operation, use the administrator-only Odoo shell action:

```python
operation = env["pos.revolut.payment.operation"].browse(REVIEWED_OPERATION_ID)
operation.action_revolut_authorize_legacy_credential()
env.cr.commit()
operation.invalidate_recordset(["credential_id"])
assert operation.sudo().credential_id
```

Use the exact reviewed record ID. The action binds a matching authority without a Merchant request. On failure, roll back and investigate; do not invent bindings or approve records in bulk. Retain original environment references. Authorities cannot change company or environment.

### Register access — 19.0.1.11.0

**Revolut backend users** starts empty. Grant till users and supervisors access before reopening checkout. Company membership, manager status and employee PINs do not grant register access.

Older records may lack newer cart/tip evidence. Upgrades preserve history without fabricating authorizations or assuming zero tips. Recovery or further allocations may require reconciliation.

### Former Restaurant bridge — 19.0.1.15.0

The separate `pos_revolut_restaurant` bridge merged into `pos_revolut`. Keep its old directory on `addons_path` until updating `pos_revolut` succeeds; migration retires it while preserving financial records.

Then remove the bridge directory, refresh Apps and confirm **POS Revolut** and standard Restaurant are installed. Do not uninstall POS Revolut to remove the bridge entry.

### Retired screens — 19.0.1.12.0 and 19.0.1.16.1

Custom receipt screens were replaced by native POS receipts/invoices; financial references, accounting documents and saved PDFs remain. Retrieve Revolut card receipts from the terminal and verify native invoice PDF generation separately.

The internal refund-discovery evidence screen and user access were removed. Matched refunds remain in **Revolut Refunds**. Administrators investigate retained server evidence privately; do not restore broad access to merchant-wide observations.

Missing or inconsistent evidence requires [reconciliation](user-guide.md#reconcile-an-uncertain-payment), not database edits or replacement financial operations.

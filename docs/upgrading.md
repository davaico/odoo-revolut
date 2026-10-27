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

### Repository layout

The addon now lives at `pos_revolut/` instead of `addons/pos_revolut/`. If deploying a full Git clone, change its `addons_path` entry from the repository's `addons` directory to the repository root, preserving other entries. Deployments that copy only the module directory can keep their existing parent path. Remove any obsolete deployed copy from the active addon paths so Odoo loads the reviewed version.

This changes packaging only; the technical module name remains `pos_revolut`. Preserve the database and financial history, and follow the normal update procedure above.

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

### Existing waiting refund recovery — 19.0.1.18.15

This release changes manager recovery of an already-verified refund and its form action;
there is no schema migration, credential rotation or automatic financial repair.
Use the normal backup, stopped-worker module update and POS reopen procedure
above. The addon update is necessary to load **Recover return** in the form.

After checking the original refund's status, use **Recover return** to resume
its original waiting tender. Review and validate the same return in POS, and
explicitly complete any outstanding Cash portion. Recovery never issues another
refund. Conflicting references or uncertain sibling allocations require review.

Before rollout, rehearse on a backed-up database copy with Merchant HTTP
blocked. Synthetic tests cannot establish the condition of a deployed database
or physical device.

Restore the complete pre-update database, filestore and addon together only
while financial activity remains stopped. After new provider or native financial
activity, reconcile first: reverting only the source code or restoring an older
database can lose subsequent operations.

### Combined V19 refund recovery and refresh — 19.0.1.18.16

This release combines recovery of existing waiting refunds, restoration of
verified refund references after native POS refresh, and the fixed Revolut
integration partner metadata.

Upgrade directly from `19.0.1.18.14` using the backup, stopped-worker module
update and POS reopen procedure above. The module update loads the refund form
action, and reopening POS loads the updated JavaScript. No schema migration,
credential rotation or automatic historical-record repair is required. Payment
and refund requests identify the integration as `davai-akae-integration`.

Manager recovery reuses the original verified refund and waiting tender. POS
validation restores verified refund references lost by native record loading,
while retaining explicit Check status after an earlier restoration failure.
Pending or unresolved refunds remain blocked, and Cash still requires explicit
completion. Neither recovery path sends another charge or refund request.

See [Release validation](validation.md) for test results and limitations.
The rollback limits above continue to apply.

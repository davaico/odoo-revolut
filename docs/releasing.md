# Release and activate POS Revolut on Odoo 18

Code promotion and client activation are separate operations. A PR into `18.0`
prepares the reviewed addon for distribution and automatically builds the reference
Odoo.sh project's Production branch. It does not install or configure a client
system. The reference project is a trial test environment; do not activate a
paid plan or permanently register it. Bounded real payment/refund testing belongs
to T82 on the existing Odoo.sh Enterprise trial. Obtain approval for the concrete
release before merging. This adaptation's delivery scope is reusable addon compatibility
validated on the trial database; it requires no permanent activation code or
executed client rollout. The client sections below are instructions for a future,
separately approved operational deployment, not gates for delivering the addon.

## Real payment/refund testing on the existing trial

The owner requires real terminal payment/refund acceptance as well as the mocked
hosted checks. The trial's Odoo.sh hosting and Enterprise edition are one test
target. No Enterprise activation code or permanent registration is required by
the test plan. Verify trial/build usability before execution. Use the actual
operational Production-stage database for real traffic; Staging/Development and
neutralized copies remain blocked. Do not bypass those guards or change expiry.
For this reference project, the owner may approve candidate promotion into
`18.0` for the team's trial testing after mocked and hosted validation, before
T82's real terminal acceptance. That promotion deploys trial code; it does not
establish client rollout or marketplace release readiness.
The deployment and financial amounts require concrete approval before execution;
T82's reopening is not a merge or money-movement instruction. Record final
provider outcomes and matching native records, including partial and remaining
balance refunds, under [T82](tickets/ready-for-human/82-activate-odoo-sh-and-check-payment-refund.md).
The client instructions below remain guidance for separate future deployments.

Odoo.sh deployment and Odoo Apps marketplace publication are separate paths.
Check the publisher's registered repository/branch and automatic/manual scanning
policy before promoting test code into a branch used by the marketplace.
Disabling a GitHub CI workflow does not by itself establish that marketplace
scanning is paused. Keep marketplace publication paused for trial-only promotion;
resume it only after acceptance and separate release approval.

## Before approving the release

- Identify the source commit, addon Git tree, version, PR head and target revision.
  Require the released addon to match the tested addon tree exactly. A documentation
  commit outside the addon does not change that identity.
- Retain fresh-install, populated native-data preservation, versioned-upgrade,
  payment/refund, permissions, credential, neutralization and browser evidence.
  Record failures and skips separately. A build status or successful installation
  cannot establish payment safety.
- Compare hosted and assembled application bytes. Revalidate changed payment,
  credential, data, view or POS behavior on staging. Attribute earlier lifecycle
  results to their actual build; do not claim an untested exact revision was hosted.

## Before a future client activation

- Back up the client database, filestore, addon and runtime configuration and
  verify restoration. Inventory unresolved attempts, returns and original
  credential authorities in restricted records. Keep a tested rollback artifact.
- Confirm the client's Enterprise entitlement, hosting administrator, intended
  company, register, currency, journal, Merchant account, location and terminal.
  Record the client's installed revision/build and version separately from the
  reference project's code build.

## Install or upgrade before enabling cashiers

1. Approve and merge only the reviewed PR through the release process. Never push
   directly to `18.0`. Client installation still needs its own approved maintenance
   window and administrator access.
2. Keep Revolut cashier use closed. Deploy the identified addon, then install it
   or run the module upgrade in [Upgrading](upgrading.md) using the supported
   hosting process. Restart all workers and reload POS assets. On Odoo.sh verify
   the installed module version; a green code build alone is insufficient.
3. Apply configuration from [Installation](installation.md) deliberately.
   **Staging configuration is not promoted automatically with code.** Create the
   Production authority for the correct company and environment, configure the
   bank journal, Merchant location/terminal UUIDs and credential reference, enable
   automatic terminal validation and set the exact tip product. Initially grant
   register access only to the acceptance operator and supervisor. Prepare the
   ordinary cashier access list, then apply those grants only after the acceptance
   steps below finish.
4. Use Database credentials where persistent environment injection is unavailable.
   Only a system administrator enters keys. Verify the selected source; an
   interactive shell export does not provision HTTP/cron workers. For environment
   authorities, verify the original variables on every worker after restart.
   Never put keys in Git or evidence logs.
5. Preserve old authorities and keys needed by pending payments, reconciliation
   and historical refunds. Rotation creates a new immutable authority/reference;
   it does not redirect old operations or automatically update methods. Do not
   revoke a historical key merely because the new connection succeeds.
6. Verify the client database is the intended operational database, has not been
   neutralized, and the platform reports its real Production stage. Do not clear
   neutralization or alter `ODOO_STAGE` to bypass restrictions. Keep test copies
   neutralized and Production API traffic blocked. Set up separate Sandbox
   authorities/methods for testing.
7. Check terminal discovery, online status and Pay at Counter mode. Check report
   permissions separately: Check Connection sends no payment and does not prove
   payments_report access. Deliberately enable **Reconcile Revolut POS payments**
   and **Reconcile Revolut POS refunds** on the approved client setup, verify
   scheduling under the intended cron user, and inspect the original unresolved
   attempts before permitting new collection.

## Bounded client payment and refund acceptance

The client administrator and terminal custodian agree one small amount and the
refund amount before starting. Retain real identifiers only in restricted records.

1. Select the intended company/register and an authorized cashier. Start one
   sale and complete the card payment on the intended terminal.
2. Confirm the underlying provider payment reached its successful final state,
   with matching amount/currency, base allocation and any terminal tip. Confirm
   the same Odoo attempt/provider references, native paid order and expected
   stock/accounting effects. A completed payment intent alone is insufficient.
3. Refund that original sale through the supported native return flow. Verify
   the provider's final successful refund and the matching original payment,
   refund operation, return, amount and references in Odoo. A submitted or pending
   refund is not acceptance. Full and partial refunds have mocked regression
   coverage; this bounded live check need not repeat the entire hardware campaign.
4. Record final outcomes, client build/version, participant and timestamp in
   restricted evidence, with a sanitized acceptance summary. Apply the approved
   cashier register grants and enable ordinary cashier use only after both
   outcomes and native completion are accepted.

Earlier hardware limitations remain: two distinct physical cards in one split,
real issuer decline and unobserved interruption variants were not established.
Physical printer output was not tested. Do not reopen unrelated historical
transactions or repeat accepted hardware scenarios to complete this checklist.

## Recovery and rollback

If any outcome is uncertain, keep the original payment/refund attempt unresolved,
retain its provider references, order, tender, cart authority and reservations,
and reconcile that attempt. Do not create a replacement charge/refund, force a
paid state, delete history or uninstall the addon. Distinguish verified financial
success from pending native checkout; use [the recovery controls](user-guide.md#understand-the-payment-status)
to finish the same order/return without another financial dispatch.

Stop new cashier use if acceptance fails. Preserve restricted logs and snapshots,
check the original credential source and worker availability, and restore service
under the approved recovery plan. Keep the original versioned backup and code
artifact. Do not downgrade the database schema blindly or restore a pre-payment
backup over newer financial evidence: assess and reconcile all post-backup
operations before a database restore. Prefer a reviewed forward correction when
financial activity has already occurred.

# 34 - Provision and gate Odoo PDF generation

**Approved:** 2026-10-01; owner approved merging provisioning and deployment preflight into one ticket. Latest branch clarification: create an appropriately named branch in `odoo-revolut`, but work on `feat/revolut-staging` in `odoo-hosting`.

**Work branches:** `odoo-revolut`: create a ticket-specific branch with an appropriate name following repository conventions. `odoo-hosting`: use `feat/revolut-staging`.

Create the integration work branch in `odoo-revolut`. In the VM repository, `odoo-hosting`, work on `feat/revolut-staging`; reuse it if it exists or create it if absent. Do not substitute a differently named hosting branch or require matching names across repositories. Inspect existing branch and worktree state first, incorporate reviewed upstream changes, and preserve other work. Do not reset an existing branch.

**State:** open

**Triage:** needs-triage

**Work type:** Infrastructure and deployment reliability

## What to build

An operator can provision or repair an Odoo server through the supported hosting workflow and download a printable historical Revolut payment or refund PDF. Subsequent addon deployments refuse to proceed when the server cannot generate PDFs, with an actionable explanation before stopping Odoo or changing the release.

This is one complete slice spanning durable server provisioning, integration deployment preflight, actual report rendering, automated verification and operator guidance. Renderer installation belongs to `odoo-hosting`; addon deployment checks and receipt prerequisites belong to `odoo-revolut`. The addon must not install operating-system packages at runtime.

## Source and scope

On 2026-10-01, while testing the receipt feature on reported version `19.0.1.10.2`, the owner encountered: "Unable to find Wkhtmltopdf on this system. The PDF can not be created." The owner also reported the same warning in Revolut Module Info. This is a reported server-side PDF dependency failure, not a confirmed browser or workstation defect. Establish the exact installed package, executable visibility and Odoo service environment before selecting the repair.

Ticket 25 delivered Odoo-generated card transaction receipts, not accounting invoices or remote terminal printing. Keep it closed and preserve its implementation and evidence. The missing runtime dependency is separate follow-up work.

[Odoo 19 installation guidance](https://www.odoo.com/documentation/19.0/administration/on_premise/packages.html) identifies wkhtmltopdf as a separately installed dependency. Select and record the compatible build for the supported server OS and architecture, including required report features; do not assume an arbitrary distribution package is equivalent.

## Acceptance criteria

- [ ] Reproduce the reported failure in a disposable environment using the supported Odoo package and hosting configuration. Identify whether the renderer is absent, incompatible, inaccessible to the service user or missing from the service environment. Record target facts separately from local assumptions; live inspection requires authorized access.
- [ ] Make the supported hosting workflow install an explicitly versioned, OS/architecture-compatible renderer and its required runtime dependencies from a verified source. Support both fresh provisioning and the documented repair of an existing host. Re-running the workflow must not disturb databases, filestores, credentials, unrelated services or the installed Odoo version.
- [ ] Verify executable access and actual rendering under the Odoo service identity/environment. Exercise a real Odoo PDF report in a disposable database, checking that the result is a readable, nonempty PDF with expected content. A package/version check or successful provisioning command alone is insufficient.
- [ ] Add a bounded, read-only/non-financial addon deployment preflight that detects missing, inaccessible or incompatible rendering capability and reports corrective operator steps before any Odoo service stop, offline module update or release switch. Keep existing financial, host-identity and reviewed-artifact guards intact; do not install or repair packages implicitly during addon deployment.
- [ ] Test preflight rejection and success, including executable-not-found, execution/compatibility failure and rendering failure. Assert that rejection leaves the running service, active release and financial records unchanged. Use disposable report data and temporary output, not live credentials or Merchant calls, for rendering checks.
- [ ] Render and inspect the actual historical payment and completed-refund receipt PDFs in isolated tests using stored verified evidence and mocked/blocked provider access. Cover repeat downloads and a closed original POS session; confirm no new payment/refund, provider request, evidence change or session reopening occurs.
- [ ] Document the server prerequisite, provisioning/repair procedure, preflight diagnostics, any necessary controlled Odoo restart, and the manual receipt download/print check. Explain that installing software on the cashier's computer is not the fix and that an accounting invoice is a different document.
- [ ] After separately authorized staging repair or rollout and satisfaction of applicable safety gates, download an existing verified historical receipt and verify its reference, amount/currency and printable PDF output. Record the exact deployed revisions, renderer build and result without secrets. If staging is blocked, preserve the blocker and distinguish local completion from unexecuted staging acceptance.

## Blocked by

None for local implementation and disposable verification. Ticket 25 is closed and provides the existing receipt workflow; it does not need reopening.

## External prerequisites

Staging inspection, package installation, service restart and deployment require authorized infrastructure access and the existing financial and deployment-security gates. Tickets 12, 31 and 32 retain their own unresolved evidence and safety requirements where applicable. Recheck current state rather than relying on earlier pending-refund counts. Creating this ticket does not authorize bypassing those gates or altering live financial outcomes.

## Out of scope

No new terminal charge or refund for testing, forced verification of pending operations, credential changes, accounting invoice creation, automatic email, public receipt sharing, remote terminal printing, broad PDF-engine replacement or unrelated hosting refactor.

## Working agreement

Keep implementation in the repository that owns each concern and follow the separate branch instructions above: a newly created integration branch in `odoo-revolut`, and `feat/revolut-staging` in `odoo-hosting`. Preserve concurrent changes and run the narrowest relevant hosting, deployment and receipt-rendering tests. Record real PDF evidence, not just a passing build. No production mutation or live Merchant request is part of local automated verification.

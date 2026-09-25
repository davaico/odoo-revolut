# 17 — Deliver the Restaurant bridge with the reviewed addon release

**Work branch:** `codex/17-deliver-restaurant-bridge`

**State:** open

**Triage:** ready-for-agent

## What to build

An operator installing or upgrading a reviewed Revolut release delivers the
complete optional Restaurant integration. Restaurant checkout receives its
payment exposure guards, while a retail-only installation continues to work
without requiring Restaurant.

## Observed problem

The integrated-revision audit on 2026-09-25 at `086dd12` confirmed that the
deployment archive contains only the base addon. The remote extractor rejects
an archive that includes the Restaurant bridge and activates only the base
addon. Manual installation instructions repeat the omission while promising
automatic bridge installation. Repository acceptance mounts both addons, so
its successful Restaurant tests do not establish that the delivered artifact
contains the guards. Server settlement checks remain present.

## Acceptance criteria

- [ ] Build the delivery artifact from the exact reviewed revision with both the base addon and its Restaurant bridge. Verify the complete artifact and make both addons available from the same reviewed release; no working-tree or manually edited server source enters the deployment.
- [ ] The remote workflow safely accepts, validates, activates and installs/upgrades both addons as applicable. Preserve path validation, immutable releases, repeat-deployment integrity checks, revision reporting and existing addon-path entries. A failed step cannot be reported as a complete release.
- [ ] A fresh retail installation works without Restaurant. When Restaurant is installed, the bridge installs automatically; installing Restaurant later also makes its guards available. Upgrading a base-only deployment delivers and enables the missing bridge, and later upgrades refresh an already installed bridge.
- [ ] Demonstrate Restaurant split/merge/transfer protection for an order with Revolut exposure using the shipped artifact. Preserve ordinary checkout and the permitted table change that keeps the original order identity.
- [ ] Retain financial-operation preflight checks, backup, stopped-service update and failure/recovery behavior. Payment and refund activity must not race deployment, and failed activation/update must leave a clear recoverable state without restarting into an incomplete release.
- [ ] Add artifact-level coverage using the actual archive/extraction flow and disposable install/upgrade acceptance using only delivered addons. Tests must fail when the bridge is omitted; mounting the complete repository is insufficient evidence for this ticket.
- [ ] Correct manual installation, upgrade and staging recovery instructions to describe the complete release and optional Restaurant behavior. Record artifact, migration and Restaurant acceptance results, with all provider calls mocked and no live deployment required for closure.

## Blocked by

- None. Existing Restaurant and deployment foundations are implemented. Tickets 02, 16 and 18 do not gate this correction; use disposable environments and mocked provider calls.

## Release gate

Blocks ticket 12 — Validate real terminal payments and publish release evidence.

## Triage decision

2026-09-25: The owner approved the three-ticket breakdown, requested publication
directly under ready-for-agent, and required all three corrections before
ticket 12. This ticket is independently actionable with mocked provider calls.
Its declared work branch has been created. Update it from the latest reviewed
main before starting; use an isolated worktree for concurrent implementation.

## Verification evidence

The audit inspected an actual reviewed-revision archive and exercised the
production remote extractor with an archive containing both addons. The bridge
was absent from the production artifact, and the complete archive was rejected
as an unsafe path. No staging deployment was performed. Implementation has
not started.

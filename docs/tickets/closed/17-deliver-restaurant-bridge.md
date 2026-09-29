# 17 — Deliver the Restaurant bridge with the reviewed addon release

**Work branch:** `codex/17-deliver-restaurant-bridge`

**State:** closed

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

- [x] Build the delivery artifact from the exact reviewed revision with both the base addon and its Restaurant bridge. Verify the complete artifact and make both addons available from the same reviewed release; no working-tree or manually edited server source enters the deployment.
- [x] The remote workflow safely accepts, validates, activates and installs/upgrades both addons as applicable. Preserve path validation, immutable releases, repeat-deployment integrity checks, revision reporting and existing addon-path entries. A failed step cannot be reported as a complete release.
- [x] A fresh retail installation works without Restaurant. When Restaurant is installed, the bridge installs automatically; installing Restaurant later also makes its guards available. Upgrading a base-only deployment delivers and enables the missing bridge, and later upgrades refresh an already installed bridge.
- [x] Demonstrate Restaurant split/merge/transfer protection for an order with Revolut exposure using the shipped artifact. Preserve ordinary checkout and the permitted table change that keeps the original order identity.
- [x] Retain financial-operation preflight checks, backup, stopped-service update and failure/recovery behavior. Payment and refund activity must not race deployment, and failed activation/update must leave a clear recoverable state without restarting into an incomplete release.
- [x] Add artifact-level coverage using the actual archive/extraction flow and disposable install/upgrade acceptance using only delivered addons. Tests must fail when the bridge is omitted; mounting the complete repository is insufficient evidence for this ticket.
- [x] Correct manual installation, upgrade and staging recovery instructions to describe the complete release and optional Restaurant behavior. Record artifact, migration and Restaurant acceptance results, with all provider calls mocked and no live deployment required for closure.

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

The initial audit inspected a reviewed-revision archive and exercised the
production extractor. It found the base-only artifact and rejection of the
complete archive. No staging deployment was performed.

Correction verified on 2026-09-25 from commit
`c846a54047d0c3dd826c981f5c6e0fae2e9387b2`. Its two-addon Git archive
had SHA-256 `912bd10b235b9a8e257e60538bfd9855b3513ba317a41f5be9ff634f24da6cfc`.
The production extractor accepted both manifests and the Restaurant guard asset
from that archive. Unit coverage rejects a missing bridge, unsafe paths,
tampering on repeat deployment, incomplete or writable releases, and unsafe
activation. The local deployer still rejects dirty or unreviewed revisions and
uses the remote script from the same commit.

- `./scripts/test-delivered-addon --revision c846a54047d0c3dd826c981f5c6e0fae2e9387b2 --scenario retail` passed. Only the extracted artifact was mounted: the base installed on a fresh retail database, the bridge remained uninstalled, and retail startup plus cash/bank checkout tests passed (2 tests, zero failures). Installing Restaurant later auto-installed the bridge; a subsequent update of both addons ran 8 tests with zero failures.
- The same command with `--scenario migration` passed. A disposable base-only deployment installed POS Revolut and Restaurant without the bridge. Switching to the extracted complete release and running the production update/init combination installed the bridge (8 tests, zero failures); a later update of both modules passed another 8 tests. The Restaurant browser tour guarded split payment, split transfer, order merge, occupied-table merge, and transfer into another order after Revolut exposure. A move to an empty table kept the original order UUID and payment line.
- `./scripts/test-addon` passed the complete pinned Odoo 19 addon suite: 143 tests, zero failures. `./scripts/test-deployment-guard` passed against actual disposable payment and refund records, including blocked pending states and unblocked settled states. `python3 -m unittest discover -s tests -p 'test*.py'` passed 29 tests; the JavaScript state test and syntax/compile checks passed.

All provider HTTP calls in these checks were mocked or blocked. No live
deployment, terminal operation, or real-money payment was performed. Ticket 12
still requires integrated acceptance after tickets 16–18 are combined.

# 32 — Verify deployment host identity on first SSH use

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/32-investigate-deployment-host-authentication`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-32`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** needs-info

**Work type:** Investigation

## What to build

Evidence that the deployment workflow authenticates the approved host on first use, or a precisely scoped correction when that identity check is absent.

## Source and scope

The wrapper accepts first-seen SSH keys and checks target syntax, while the runbook requires a trusted workstation and approved private-tailnet inventory. The source proves a trust-on-first-use setting, not that a network attacker can defeat the actual tailnet/host provisioning controls.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 30: `csf_a56049a247fa1b951ca588b2` — A first deployment can run against an unverified SSH host

## Acceptance criteria

- [x] Inspect available versioned workstation/deployment instructions for known-host provisioning, dedicated host keys or SSH host CA, approved inventory and tailnet endpoint guarantees. Keep private key material and credentials out of evidence.
- [ ] Determine whether a supported first deployment can occur with no independent host identity anchor. Separate transport encryption, successful client authentication, target authorization and server identity.
- [x] Use an isolated mock/SSH fixture if needed to check first-seen, correctly pinned, changed-key and wrong-approved-target behavior before artifact transfer. No real MITM attempt or connection to an unapproved production endpoint.
- [x] Assess source disclosure and forged deployment-success acknowledgement separately from mutating the intended host; receiving a client SSH authentication does not disclose its private key.
- [x] Return an evidence-backed verdict and identify any missing provisioning/network fact. External tailnet or known-host guarantees must be demonstrated, not assumed present or absent.
- [x] If the gap is real, specify fail-closed approved-host authentication before upload, including first-use provisioning and legitimate host-key rotation. Preserve supported deployment and recovery without implementing the change here.
- [x] Retain exact revision and evidence, with a concrete needs-info handoff when target trust facts remain unavailable.

## Blocked by

None (can start immediately).

## External prerequisites

Local source/configuration and safe mocked investigation can start immediately. Actual host, access-policy or owner facts may be needed for a conclusive result; missing facts are not assumed.

## Out of scope

No credential rotation, production key replacement, tailnet changes or broad network audit.

## Release and integration relationship

Independent of ticket 31: host identity and local file integrity require different evidence. A demonstrated host-authentication defect must be resolved before the affected deployment workflow is relied on.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

## Owner clarification — 2026-09-30

The owner reports that their boss operates SSH access to the company-managed Hetzner VM. The exact deployment connection route and first-use identity verification remain unknown. Versioned hosting setup enables Tailscale SSH; confirm the effective route and identity/access controls with the infrastructure owner rather than assuming ordinary public-host SSH semantics.

## Investigation evidence — 2026-10-01

Local investigation completed on reviewed main
`719bae93390c3a326673af2d0e6b89aea0a84b65`; no production correction was
implemented. See [the exact inputs, loopback observations, verdict and scoped
correction](../../testing/ticket-32-deployment-host-authentication.md).

Real OpenSSH observed first-seen acceptance, correct-pin acceptance, changed-key
refusal before authentication/upload, and acceptance of a different correctly
pinned target. A mock server received the archive/deployer and fabricated a
success report without executing the deployer. These establish wrapper
limitations, not a demonstrated attacker path through the company tailnet.

The remaining unchecked criterion requires infrastructure-owner evidence. Gary
confirmed that his boss handles this setup and he does not know these facts.
Tailscale SSH provisioning is versioned and can supply an independent identity
anchor; its effective route, approved-node binding, grants, workstation trust
provisioning and rotation process remain unverified.

**Initial needs-info handoff:** obtain the four non-secret owner evidence items in the
report's infrastructure-owner table, then determine whether a supported first
deployment lacks an independent anchor. Keep the source claim open; do not close
as safe or assume a production MITM. If a gap is confirmed, create a scoped
remediation following the report before relying on the affected deployment
workflow. No credential or infrastructure mutation is authorized by this handoff.

## Broader search and verified staging route — 2026-10-01

At the owner's request, the investigation expanded to complete tracked hosting
source/history, the original setup chat, selectively extracted local state,
workstation public trust records, Tailscale status, Hetzner metadata and pinned
read-only staging checks. See the report's broader setup/live-evidence section.

The current route is **Tailscale SSH**, verified by its protocol banner,
`RunSSH: true`, and root authentication type `none`. The approved VM is Hetzner
`166917896`, `odoo-revolut-staging`; its DMI serial matches. The current Tailscale
device is `n6m6qZXtkD11CNTRL`, `odoo-revolut-staging.tail9f54b7.ts.net`,
`100.94.15.48`, with the staging tag. Local/server node identities and the
expected bootstrap marker match. An empty temporary known-host file check
confirmed SSH first-use acceptance on this authenticated tailnet route without
any upload. No genuinely new workstation was enrolled.

This establishes an independent Tailscale node-authentication anchor for the
observed route. It does not establish every enrollment/replacement control, so
the supported-new-workstation criterion remains open and no claim is closed as
safe. The earlier missing-route/VM questions are now resolved by evidence.

Effective root rules include Gary's laptop, four Emile-owned device addresses,
and two unmapped device principals. Current provisioning takes a manually
supplied enrollment key; old OAuth/one-hour/single-use documentation is stale.

**Broader-search needs-info handoff (before the clarification below):** obtain administrative enrollment/tag-owner and
Hetzner replacement permissions, identify the two other root-rule devices and
their source network/SSH rules, and provide new-workstation/replacement approval
procedures. The report lists exact non-secret evidence needed. No deployment or
infrastructure setting was changed.

## Owner clarification — 2026-10-01

Gary confirms that Emile administers device enrollment/tagging and Hetzner VM
replacement. The two previously unmapped root-rule devices also belong to
Emile, Gary's boss. These owner-supplied facts resolve those identification
questions without claiming an independently verified administrative inventory.

Gary does not have the approved new-workstation and VM/key replacement procedure.
**Current needs-info handoff:** obtain Emile's documented or approved procedure
for workstation authorization, first-upload staging identity verification, and
legitimate replacement/re-verification of the VM, Tailscale node or SSH host key.
Retain the ticket as open/needs-info for that procedure. No message, deployment
or infrastructure change was performed.

# 32 — Verify deployment host identity on first SSH use

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/32-investigate-deployment-host-authentication`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-32`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Investigation

## What to build

Evidence that the deployment workflow authenticates the approved host on first use, or a precisely scoped correction when that identity check is absent.

## Source and scope

The wrapper accepts first-seen SSH keys and checks target syntax, while the runbook requires a trusted workstation and approved private-tailnet inventory. The source proves a trust-on-first-use setting, not that a network attacker can defeat the actual tailnet/host provisioning controls.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 30: `csf_a56049a247fa1b951ca588b2` — A first deployment can run against an unverified SSH host

## Acceptance criteria

- [ ] Inspect available versioned workstation/deployment instructions for known-host provisioning, dedicated host keys or SSH host CA, approved inventory and tailnet endpoint guarantees. Keep private key material and credentials out of evidence.
- [ ] Determine whether a supported first deployment can occur with no independent host identity anchor. Separate transport encryption, successful client authentication, target authorization and server identity.
- [ ] Use an isolated mock/SSH fixture if needed to check first-seen, correctly pinned, changed-key and wrong-approved-target behavior before artifact transfer. No real MITM attempt or connection to an unapproved production endpoint.
- [ ] Assess source disclosure and forged deployment-success acknowledgement separately from mutating the intended host; receiving a client SSH authentication does not disclose its private key.
- [ ] Return an evidence-backed verdict and identify any missing provisioning/network fact. External tailnet or known-host guarantees must be demonstrated, not assumed present or absent.
- [ ] If the gap is real, specify fail-closed approved-host authentication before upload, including first-use provisioning and legitimate host-key rotation. Preserve supported deployment and recovery without implementing the change here.
- [ ] Retain exact revision and evidence, with a concrete needs-info handoff when target trust facts remain unavailable.

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

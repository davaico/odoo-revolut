# 31 — Determine deployment upload and lock-file exploitability

**Approved:** 2026-09-30; owner approved scope, dependencies and direct ready-for-agent placement.

**Work branch:** `codex/31-investigate-privileged-deployment-files`

**Worktree:** `/home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-31`

Work in this worktree on the assigned branch; respect the blockers below and update from reviewed main before starting.

**State:** open

**Triage:** ready-for-agent

**Work type:** Investigation

## What to build

A separate evidence-backed verdict for each privileged upload, archive-replacement and lock-file claim under the supported hosting configuration, with a narrow filesystem hardening handoff where justified.

## Source and scope

The deployment workflow uses a predictable remote temporary archive name, hashes a pathname once before reopening it, and opens a constant lock pathname in write mode before locking. The six findings include distinct regular-file, symlink, post-verification replacement, upload-clobber, denial and lock-truncation claims. Effective filesystem/kernel/OpenSSH controls and a supported lower-privilege local actor were not established.

Source scan `95c73550-ed81-4cfe-9e81-b6f2be355a38` was canceled with partial coverage. Individual static triage on 2026-09-30 assessed main revision `1d549c11507878fd95fb91a38337599d486e7afc`. These findings are claims with the recorded evidence level, not evidence of production exploitation.

- Scan input 5: `csf_dbbeda1c4299496bf775a644` — Predictable root deployment archive permits privileged overwrite, content replacement, or deployment denial
- Scan input 15: `csf_06a7474b0b79b37bb8cef2a6` — A local user can replace the root-staged addon after verification and execute code as Odoo
- Scan input 17: `csf_4925cf001b94023f9c915d73` — A local user can redirect the root deployment upload and clobber a privileged file
- Scan input 23: `csf_08451af4690fad4915a4809c` — A local host user can replace a reviewed deployment archive and execute code in Odoo
- Scan input 27: `csf_460c7a2adbddf8cb4cd4e1f6` — A local user can redirect the root deployment archive upload
- Scan input 32: `csf_1b61b708da0cb8c139a79b05` — A local user can make the root deployer truncate an arbitrary file

## Acceptance criteria

- [ ] Inspect the versioned hosting/runbook configuration read-only to identify the supported lower-privilege actor, temporary/lock directory ownership and modes, sticky-directory protections, effective protected_symlinks/protected_regular settings and deployed SCP/SFTP implementation. Record unverified target facts rather than using workstation settings.
- [ ] Construct a bounded disposable filesystem/process harness for the relevant pinned upload/deploy semantics, never production directories. Do not run a real deployment or alter live Odoo services, database, backups or host files.
- [ ] Test each source claim separately: attacker-owned regular archive retaining write access; symlink upload clobber with reviewed bytes; followed symlink plus post-hash replacement; deterministic-name denial; and pre-created lock symlink causing pre-flock truncation. Do not use proof of one primitive as proof of all six findings.
- [ ] Include controls for protected kernel settings, private root-owned paths, ordinary reviewed upload/extraction and mutual exclusion. Distinguish root file corruption from code execution as the Odoo service and from full root code execution.
- [ ] Record whether archive member filtering, initial hash checking and read-only releases defeat each path or leave a verification/use gap. Preserve exact steps and safe fixture evidence for any demonstrated issue.
- [ ] Produce one verdict and proof-gap list per original finding. Identify whether missing facts belong to the hosting repository or integration repository; do not modify hosting or inspect live hosts without the required authorization.
- [ ] If applicable, propose private root-owned staging and safe descriptor/lock handling with deploy/recovery compatibility checks, scoped into follow-up work. Do not implement filesystem hardening within this investigation.
- [ ] Keep unresolved target prerequisites as a precise needs-info request. A failed exploit under an unrelated local configuration does not establish safety of the supported target.

## Blocked by

None (can start immediately).

## External prerequisites

Local source/configuration and safe mocked investigation can start immediately. Actual host, access-policy or owner facts may be needed for a conclusive result; missing facts are not assumed.

## Out of scope

No live symlink race, privileged-file overwrite, service stop, package update or generic host audit.

## Release and integration relationship

Disposition must precede relying on the reviewed-artifact guarantee for a release deployment; an independently demonstrated defect requires remediation before that workflow is used.

## Working agreement

Start from current reviewed main and record the exact revision; do not implement against the stale scanned checkout. Preserve existing work and use an isolated worktree if another agent is editing overlapping code. All automated Revolut calls are mocked and blocked from reaching real Merchant endpoints. Physical terminal actions, deployment and production mutations require a separate authorized workflow.

## Owner clarification — 2026-09-30

The owner reports that deployment SSH access is held by their boss and that the Hetzner VM belongs to company infrastructure. This identifies the operating context, not the complete local-process privilege model. Establish service-account access and effective filesystem protections before confirming or dismissing the six claims.

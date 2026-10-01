# Ticket 31 — partial investigation and infrastructure handoff

Recorded 2026-10-01 from the interrupted **T31** chat. This preserves existing
evidence; it is not a fresh validation run, a completed security review, or a
finding closure. All six source findings remain `needs_review`.

## Provenance and limits

- Chat: `01a0f6e8-9cc0-7d31-9f7f-d7ee2ac2f2cf` (T31).
- Investigated integration revision: `719bae93390c3a326673af2d0e6b89aea0a84b65`.
- Hosting source inspected read-only: `245f58ef7c8f2d96e0281f6451f992d0439cf8ec`.
- Successful historical command record:
  `exec-11744eb8-d757-4fa6-b0ca-f696697df9f4`, in turn
  `01a0f6f0-50f1-7b51-bc3e-ae347051276f`: exit 0, **17 tests passed**,
  1.658 seconds. The overall chat turn subsequently failed with a cybersecurity
  content restriction; that does not erase the completed command result.
- Earlier run: 17 cases, two fixture failures. The fixture was corrected for
  target-directory access and same-second backup-name collisions before the
  successful run. These were not production fixes.
- Disposable local container: network disabled, repository mounted read-only,
  temporary fixture filesystem, distinct synthetic actor/service identities;
  service, database and health commands were mocked. No live deployment or
  Merchant call was part of the recorded suite.
- Image recorded by the chat:
  `sha256:ceea43280375efa7d2aae189fbbb24df7db5cbecfda52b0a0c2fb970744a6898`.
  Python 3.12.3; local kernel controls reported `protected_symlinks=1` and
  `protected_regular=2`. These are not observations of the Hetzner VM.
- Uploads used an **OpenSSH V_9_6_P1 syscall model**, not a complete real
  SSH/SFTP transfer. A later SCP receiver startup probe did not establish
  end-to-end protocol equivalence. The actual target receiver remains unknown.
- The uncommitted harness remains at `scripts/investigate-deployment-files` in
  the assigned ticket-31 worktree. Its SHA-256 when this handoff was extracted:
  `a9b64f72feb27dcfacca026c8d43abd951fa28d0b58297f562ea2c3defa780ee`.
  It has not received a completed independent review and is not promoted into
  the supported deployment/test tooling by this documentation update.

## Useful source observations

At the investigated revision, `scripts/deploy-addon:153` chooses a predictable
temporary archive pathname. `scripts/deploy-addon-remote:503` verifies its hash,
while extraction at line 286 opens the pathname again. The lock file is opened
in write mode at line 588 before the exclusive lock is acquired. These source
observations identify where host filesystem protections matter; they do not
establish that a supported lower-privilege actor can reach those paths.

Hosting source identifies an Odoo service account and Tailscale SSH setup.
It does not establish the effective deployed directory permissions, service
sandbox, supplementary groups, kernel protections or receiver implementation.
The owner's boss has SSH access to the company-managed Hetzner VM; that does
not establish whether other local processes can influence deployment files.

## Retained results by original claim

The following are historical fixture observations, not confirmed production
vulnerabilities. Keep the original source claims distinct.

| Scan input / source ID | Useful observation | Remaining proof gap / verdict |
| --- | --- | --- |
| 5 — `csf_dbbeda1c4299496bf775a644` | Under permissive shared-directory conditions, the model allowed archive changes after verification. A predictable-name obstruction also made a modeled upload fail. Protected/private-path cases blocked corresponding modifications. | Actual staging-directory access, receiver behavior and supported local actor are unknown. `needs_review`. |
| 15 — `csf_06a7474b0b79b37bb8cef2a6` | A pre-existing actor-owned regular archive retained that ownership in the upload model; a later change reached a benign initializer under the synthetic service identity in the permissive fixture. | Not actual Odoo execution or a deployed-host reproduction; target ownership and protection rules remain unknown. `needs_review`. |
| 17 — `csf_4925cf001b94023f9c915d73` | Modeled upload through a followed link replaced a root-owned fixture file with reviewed archive bytes under permissive conditions; protected/private cases blocked access. | Does not establish arbitrary attacker-selected root code execution. Actual receiver and target path access remain unknown. `needs_review`. |
| 23 — `csf_08451af4690fad4915a4809c` | The permissive fixture allowed a linked archive target to change after verification and reach the benign service-identity initializer. | Real upload semantics and target ability to change the archive are unverified. `needs_review`. |
| 27 — `csf_460c7a2adbddf8cb4cd4e1f6` | The same upload-redirection fixture is relevant, but this remains a separate source claim. Restrictive controls blocked the modeled redirection. | Supported host applicability and full transfer behavior remain unverified. `needs_review`. |
| 32 — `csf_1b61b708da0cb8c139a79b05` | In a fixture where the actor could write the lock directory through its group, a linked root-owned fixture file was truncated before lock rejection. Private-directory and protected world-writable-directory controls blocked corresponding access. | Actual lock-directory ownership, ACLs, groups and service access remain unknown. File truncation is not proof of root code execution. `needs_review`. |

Additional successful controls covered ordinary reviewed extraction, read-only
release files, initial checksum rejection, archive traversal rejection,
existing-release content mismatch detection and ordinary mutual exclusion.
Passing these cases establishes their fixture assertions, not that the six
reported weaknesses are fixed. Read-only release files cannot by themselves
prove that bytes remained unchanged between verification and extraction.

## Required infrastructure answers

An authorized infrastructure operator should provide a sanitized record of:

1. Effective ownership, modes, ACLs and mount behavior of the archive staging
   directory and lock directory, including parent-path traversal permissions.
2. Effective `fs.protected_symlinks` and `fs.protected_regular` values and
   whether provisioning guarantees them across restart/rebuild.
3. Which lower-privilege accounts/processes can access those directories,
   especially the Odoo service identity, supplementary groups and effective
   systemd sandbox/private temporary-directory settings.
4. The deployed SSH/SCP/SFTP receiver versions and actual transfer route,
   including whether Tailscale SSH changes the receiver path.
5. The deployed integration revision and any local deployment-script changes.

Do not include credentials, private keys, payment identifiers or customer
records. Unknown answers stay unknown; local workstation defaults are not a
substitute. This handoff does not authorize live testing or host changes.

## Resume and release conditions

Automated investigation was interrupted repeatedly by the reported Daybreak /
cybersecurity content restriction. The user requested deferral and extraction
of useful information. Resume through an appropriately authorized review
workflow when access and target evidence are available; do not keep retrying
the interrupted experimental work as part of this documentation task.

An authorized reviewer must review the local evidence and actual transfer
semantics, assess each source claim against the supported host configuration,
then record a separate verdict. Where justified, propose scoped follow-up
hardening such as private administrator-owned staging and safe lock/archive
handling, with deployment and recovery regression coverage. No such change is
implemented here. Ticket 31 remains open and cannot supply a completed
deployment-integrity assurance for ticket 12.

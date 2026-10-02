# Ticket 32 — First-use deployment host identity

Investigation date: 2026-10-01. Initial local-only verdict: **wrapper
trust-on-first-use and missing target binding demonstrated; approved-route
exploitability needs info**. The broader follow-up below now verifies the actual
approved staging route as Tailscale SSH and identifies its VM/device. Gary's
subsequent clarification identifies Emile as the administrator and owner of the
remaining devices. The new-workstation/replacement procedure remains unverified;
on 2026-10-02 Gary closed the ticket as **wontfix** because that operational work
is outside the addon-delivery scope (see the final closure decision below).
No remote deployment ran and no host,
credential, tailnet policy or production code was changed. The initial pass made
no production connection; the follow-up performed only pinned, read-only staging
checks and a no-upload first-SSH-use observation.

## Exact inputs

- Integration revision: `719bae93390c3a326673af2d0e6b89aea0a84b65`, local reviewed
  main at the start of work. The assigned ticket branch was fast-forwarded from
  `080f3fb` to this revision before investigation.
- Hosting source: `245f58ef7c8f2d96e0281f6451f992d0439cf8ec`, clean versioned
  checkout. The development document's older hosting baseline is `d5c8aba`;
  comparison shows no changes to the cited bootstrap, firewall or host-identity
  readiness logic. These are source revisions, not a claim about running systems.
- `scripts/deploy-addon` SHA-256:
  `c9e65095bddc9caec2407202d99f3f949ca78b2abe602da1f56c4ea77d1a41dd`.
- `scripts/deploy-addon-remote` SHA-256:
  `6e0c21a699132725f68c5aa4f5ac48feab61e5acd740417393eb2ec514e1c3bf`.
- OpenSSH client: `9.6p1 Ubuntu-3ubuntu13.19`, OpenSSL `3.0.13`.
  Investigation-only SSH server library already installed: Paramiko `2.12.0`.
- Retained source claim: scan input 30, `csf_a56049a247fa1b951ca588b2`, from
  canceled partial scan `95c73550-ed81-4cfe-9e81-b6f2be355a38`. Its earlier
  static assessment used `1d549c11507878fd95fb91a38337599d486e7afc`.

## Versioned evidence

| Source at the revisions above | Observation | Limit |
| --- | --- | --- |
| [`scripts/deploy-addon`](../../scripts/deploy-addon), lines 51–69 | Target validation accepts any syntactically valid `user@hostname`, including an IP or a host outside the tailnet. It checks neither root nor a customer/environment inventory mapping. | The runbook instructs the operator to select an approved target; CLI acceptance is not operational approval. |
| Same file, lines 153–167 | The first network operation is `scp`, using `BatchMode=yes`, `StrictHostKeyChecking=accept-new`, `ConnectTimeout=10`. There is no independent identity preflight before upload. | Effective client known-host files, host CA, `KnownHostsCommand`, DNS trust and connection routing can supply additional controls outside this wrapper. They were not inspected on the operator workstation. |
| Same file, lines 168–198 | `ssh` sends the versioned Python deployer on stdin, then accepts stdout containing `Deployed POS Revolut revision <SHA>`. | A checksum/commit check performed by the receiving endpoint cannot independently identify that endpoint. |
| [`docs/staging-deployment.md`](../staging-deployment.md), prerequisites and install command | Requires a trusted workstation, approved root target from company tailnet inventory, no public SSH port. Example target is a placeholder. | No versioned approved-node inventory, workstation host-key/CA provisioning, first-use fingerprint approval or SSH rotation procedure was found in the inspected deployment instructions. Absence from these files does not prove absence in company operations. |
| [`docs/development-environment.md`](../development-environment.md), current target | Reports verified Tailscale SSH provisioning and tailnet-only administration. | Does not establish the effective route, current policy or keys used by a first deployment. |
| Hosting `infrastructure/hetzner/bootstrap.sh`, lines 25–36 | Installs Tailscale and initially enrolls with `tailscale up ... --ssh`; checks running state and Tailscale IP presence. | The guarded first-boot enrollment does not prove current SSH advertisement on an existing VM. |
| Hosting `infrastructure/hetzner/main.tf`, lines 65–88 | Firewall has UDP 41641 and ICMP ingress; no public TCP SSH rule. | Versioned desired state is not observed runtime state. It materially limits the applicability of a generic public-network SSH attack. |
| Hosting `docs/HETZNER_INSTANCES.md`, lines 19–23; `customers/revolut.staging.json` | Requires operator root access through Tailscale, single-use enrollment, configured staging tag, console recovery. | Actual grants/SSH policy, enrollment approval and node ownership are external. No private state or enrollment material was read. |
| Hosting `scripts/odoo-instance`, `wait_ready`, lines 158–205 | Uses local Tailscale peers to resolve one matching hostname; checks a deployment marker and service readiness with `accept-new`. | Helpful provisioning identity check, but not called by this addon wrapper; remote marker output alone is not independent cryptographic server identity. |
| [`ticket-12-operator-observations.md`](ticket-12-operator-observations.md), deployment record | Records successful prior deployment output and SSH/database checks. | Does not retain first-use host-key or effective connection-route evidence. |

Only tracked instructions/configuration were inspected in hosting in the initial
pass. No operator
SSH configuration, Terraform state, private keys, known-host contents, account
tokens, live DNS, tailnet status or production server was inspected.

## What the protocols establish

[OpenSSH's manual](https://man.openbsd.org/ssh_config#StrictHostKeyChecking)
documents that `accept-new` automatically records unknown keys but rejects a
changed key. `yes` requires prior trust. Encryption by itself does not bind a
first-seen key to the approved VM; a stored pin only binds to the key previously
approved or observed. Client authentication establishes the client's authority
to the server, rather than identifying the approved server to the client.
Successful public-key authentication does not transmit the client's private key.

[Tailscale's SSH documentation](https://tailscale.com/docs/features/tailscale-ssh)
describes WireGuard node authentication, SSH port interception on tailnet
addresses, and control-plane distribution of public SSH host keys. Access
requires both network and SSH permissions. This can supply an independent
identity anchor on first use; missing manual workstation pins do not alone imply
an unverified connection. These are product guarantees conditional on the actual
route/configuration. They do not prove which company node is approved for this
customer/environment. Official documentation consulted on 2026-10-01.

## Isolated observation

The retained [fixture](../../scripts/investigate-deployment-host-authentication)
loads the exact versioned wrapper and exercises its `main` entry point with real
OpenSSH `scp`/`ssh` processes and a disposable loopback SFTP/SSH server. Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/investigate-deployment-host-authentication \
  --revision 719bae93390c3a326673af2d0e6b89aea0a84b65
```

The environment needs Python, its existing Paramiko library, Git, OpenSSH and
permission to bind an ephemeral loopback listener. Paramiko is not added to
deployment or addon dependencies. The original sandbox forbids sockets; the
approved fixture run used elevated execution solely for this local experiment.

Fixture controls and limitations:

- Fresh in-memory server keys and temporary known-host/config files per case;
  no private key output or persistent workstation changes.
- Reserved `.invalid` names explicitly mapped to `127.0.0.1` in an isolated
  `-F` configuration. No DNS/network access to a real target, proxy, jump host,
  shared SSH session, client identity or agent. Server accepts authentication
  type `none`; this is a fixture simplification, not a Tailscale simulation.
- Git archive, revision resolution, ancestry and remote-script reads are real
  local commands. Cleanliness is mocked to permit investigation with report
  files uncommitted; the reviewed ref is the exact investigated SHA. Existing
  tests cover cleanliness/reviewed-ref refusals separately.
- Upload is stored in memory. The remote Python script is consumed as data and
  never executed. The server returns a fabricated success line with exit zero.
- The wrong-target case represents another otherwise approved/reachable company
  host with its own correctly provisioned pin. The wrapper has no inventory
  binding for the fixture customer/environment. It is not a claim that such a
  target exists or is accessible in the company tailnet.

Observed output, with assertions for rejection stage and transferred bytes:

| Case | Wrapper exit | Client authentications | Archive bytes received | Script bytes received | Wrapper reports success |
| --- | --- | --- | --- | --- | --- |
| First-seen, empty fixture known-host file | 0 | 2 | 127988 | 23250 | Yes |
| Correctly pinned host | 0 | 2 | 127988 | 23250 | Yes |
| Changed key versus independently seeded pin | 1 | 0 | 0 | 0 | No |
| Wrong otherwise approved target, correctly pinned | 0 | 2 | 127988 | 23250 | Yes |

First-seen keys were recorded automatically. Changed-key stderr included
`Artifact upload failed` and `Host key verification failed`; rejection occurred
before authentication and before either transfer. Every success acknowledgement
in the fixture was fabricated: **no deployment occurred**.

## Impact and verdict

The wrapper permits first use with no *wrapper-managed* identity anchor. This
proves trust-on-first-use at the SSH layer in the isolated configuration. It
does **not** prove that a supported company deployment lacks an independent
tailnet or externally provisioned SSH anchor. A supported route still requires
the approved inventory and workstation; those facts remain unavailable.

If an operator's effective route reaches an unintended endpoint and no trusted
anchor rejects it, that endpoint receives both addon source directories and the
remote deployer. No Merchant credential is accepted/transferred by the wrapper;
client authentication is not private-key disclosure. No broader confidentiality
impact or stolen credential is demonstrated.

An unintended endpoint can also fabricate the expected success substring, as
demonstrated. That is false deployment evidence, independently of whether the
source is confidential. Neither transfer nor forged stdout demonstrates mutation
of the intended staging VM, command execution there, access to its database, or
a viable attacker route through the private tailnet. A legitimate but wrong
target could execute the real deployer if its privileges/configuration permit;
that was neither executed nor established here.

Keep the finding open as **needs-info**. Do not label it safe, exploited, or a
confirmed public-network MITM vulnerability from this source evidence.

## Scoped correction if owner evidence confirms a trust gap

Specify a separate remediation after confirming the route; do not implement it
under this investigation ticket:

1. Bind customer/environment to an owner-approved node identity and permitted
   SSH user/address. Reject unknown or mismatched targets before any archive or
   script transfer. Correct pins on another approved host must not pass this
   binding check.
2. For ordinary OpenSSH, provision an independently approved host public key or
   host CA and expected principal from an authenticated owner channel. Use
   fail-closed host checking on **both** upload and execution. Scanning a key
   from the same unauthenticated route is collection, not approval. Preflight
   and transfer must use the same trust source and target binding; avoid a
   preflight followed by a permissive transfer.
3. For confirmed Tailscale SSH, demonstrate/enforce the approved node mapping,
   authenticated tailnet route, relevant grants and effective host-key
   distribution/checking. Preserve supported Tailscale behavior rather than
   introducing an incompatible ordinary-OpenSSH assumption or silent fallback.
4. Legitimate rotation/rebuild requires owner approval of the replacement key
   or CA/principal, or approved Tailscale node reassociation and key distribution,
   before transfer. Retire the old identity explicitly. An unexpected change
   must block deployment, not trigger automatic pin deletion or `accept-new`.
   Recovery uses the documented owner/Hetzner console process to restore trust,
   then repeats verification before install/upgrade. Do not rotate Merchant
   credentials or change the tailnet under this ticket.
5. Exercise unknown, correct, changed, rotated and wrong-approved-target cases
   before artifact transfer for the confirmed route. Retain authenticated
   endpoint identity with revision/checksum evidence; a reported SHA alone
   cannot prove which VM was changed.

## Infrastructure-owner handoff

Gary confirmed on 2026-10-01 that his boss handles this setup and he does not
know the route or trust provisioning. The following non-secret evidence is
needed from that infrastructure owner; no message was sent to them:

| Missing fact | Evidence needed | Decision it resolves |
| --- | --- | --- |
| Effective deployment route | Sanitized effective SSH routing/settings for the deployment target, including destination/port, proxies, host-key sources and multiplexing; confirm Tailscale SSH interception versus OpenSSH over the tailnet | Whether the observed first-use SSH setting relies on authenticated node transport/key distribution or external pins/CA |
| Approved endpoint binding | Owner-approved customer/environment-to-VM/node record; explain name/IP ownership, enrollment/tag approval and replacement/stale-node handling | Whether the route identifies this VM, rather than merely a reachable authorized peer |
| Current trust/access controls | Relevant sanitized network/SSH grants and confirmation of expected node identity, SSH advertisement and client host-key distribution; or approved public fingerprint/CA/principal provisioning record | Whether a supported first deployment has an independent anchor and who can reach/authenticate to it |
| First-use and rotation process | How a new workstation verifies the endpoint before upload; how legitimate host/node replacement is independently approved and how unexpected keys fail | Whether deployment and console recovery remain supported without permissive first use |

Do not provide private keys, enrollment/auth tokens, full state, credentials or
unrelated tailnet inventory. Reassess only against dated owner evidence and the
then-current wrapper revision. If no independent identity anchor exists, create
a narrowly scoped remediation ticket and resolve it before relying on the
affected workflow. This investigation does not clear ticket 12's release gates.

## Verification

- Four real OpenSSH loopback scenarios above passed on the exact source revision.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_deploy_addon.py'`:
  29 deployment regressions passed.
- No production behavior was changed, so red/green remediation TDD does not
  apply. The fixture observes the existing CLI seam rather than specifying a
  new implementation.
- Final full local deployment suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`: 29 passed.
- Python AST syntax checks passed for the fixture and both deployment scripts;
  `git diff --check` passed. No project typechecker is configured. Odoo
  install/upgrade, financial-operation DB checks and real terminal tests are
  outside this documentation/SSH investigation; they would not establish
  first-use host identity.

## Independent code review

Fixed point: `719bae93390c3a326673af2d0e6b89aea0a84b65`. Two independent
reviewers assessed `git diff 719bae93390c3a326673af2d0e6b89aea0a84b65...93ed354`
before this review record was added.

### Standards

No findings. Documentation/script placement, Python conventions, scoped
behavior, assumptions, exercised SSH evidence and ticket lifecycle conform to
the supplied repository standards. The ready-for-agents placeholder remains
tracked. No actionable baseline smells were identified; Paramiko adapters
implement required framework seams.

### Spec

No actionable findings. All locally available investigation requirements are
covered. The supported-route identity criterion remains unchecked with the
explicitly permitted needs-info handoff. No unasked production changes or scope
creep were found. Conditional Tailscale claims agree with official documentation
and are not presented as observed company configuration.

Standards: 0 findings. Spec: 0 findings. Operational trust remains unresolved.

## Broader setup and live evidence — 2026-10-01

At the owner's request, the follow-up searched the complete tracked hosting tree,
relevant Git history and local branch tips; the original `HOSTING - Setup` chat;
ignored instance filenames and selectively extracted non-secret state metadata;
local SSH public-key records/configuration; local Tailscale peer status; and the
approved VM's current Hetzner metadata and pinned read-only identity/SSH rules.
Hosting remained at `245f58ef7c8f2d96e0281f6451f992d0439cf8ec`. This expands the
initial evidence scope; its earlier limitations are historical, not the final
search result. Observations were completed by `2026-10-01T10:56:46Z`.
Original setup chat ID: `01a0c3a5-2be8-7423-af94-4835349a8f6a`; creation/access
turns `01a0c82b-d66b-7091-881a-7ab82a058527` and
`01a0c840-a0ac-7ae2-8bb2-ca8c7bb61490`. Local Tailscale client: `1.102.4`.

### 1. Actual connection route

**Confirmed Tailscale SSH**, reached with the normal OpenSSH client. A connection
to `root@odoo-revolut-staging` resolved to `100.94.15.48:22`. Verbose SSH reported:

```text
Remote protocol version 2.0, remote software version Tailscale
Host 'odoo-revolut-staging' is known and matches the ED25519 host key.
Authenticated to odoo-revolut-staging ([100.94.15.48]:22) using "none".
```

The server's selectively filtered `tailscale debug prefs` reported `RunSSH: true`
and `WantRunning: true`. Checks used `-F /dev/null`, `BatchMode=yes`,
`StrictHostKeyChecking=yes`, disabled identities/agent forwarding and no shared
session. The pre-existing workstation pin was verified before the read-only
commands. Public fingerprint:
`SHA256:t0MCYZeMofYhedirgJ7DbgdQ7wrgwJv2JDkinuOVaaA` (`ssh-ed25519`).

### 2. Exact approved VM/device association

| Identity | Observed value and cross-check |
| --- | --- |
| Hetzner server | `166917896`, name `odoo-revolut-staging`; current API reports running, customer `revolut`, environment `staging`, managed by `odoo-hosting` |
| Local provisioning state | Same server ID/name in `.instances/revolut/staging/terraform.tfstate`, serial 11; named CLI context `odoo-revolut`; applied profile is `revolut` / `staging` |
| Actual VM serial | `/sys/class/dmi/id/product_serial` reports `166917896`, matching state and Hetzner API |
| Tailscale name | `odoo-revolut-staging.tail9f54b7.ts.net` |
| Tailscale IPv4 | `100.94.15.48` |
| Stable Tailscale device ID | `n6m6qZXtkD11CNTRL`, matching both workstation peer status and server self status |
| Device tag | `tag:odoo-revolut-staging`, observed on both sides, rather than inferred from the profile |
| Bootstrap marker | The server's `/var/lib/odoo-hosting/bootstrap-complete` matches the expected tunnel ID from local Terraform instance output |

The original setup chat records creation on 2026-09-22, successful enrollment,
Tailscale SSH activation, a policy denial for Gary, and Gary's later confirmation
that root SSH worked after access was granted. Current live cross-checks above
are stronger evidence than that historical narrative alone. They establish the
present association; the addon wrapper still does not enforce this association
before every upload or bind its target to a stable node ID.

### 3. First-use trust

The actual route supplies **authenticated Tailscale node transport** in addition
to the SSH session. Official [Tailscale SSH documentation](https://tailscale.com/docs/features/tailscale-ssh)
identifies node keys as the authentication/authorization/encryption anchor and
describes public SSH host-key distribution. Thus the earlier fixture's ordinary
SSH trust-on-first-use observation does not establish an unauthenticated
first-use route for this verified staging endpoint.

The workstation has the matching host key recorded, but no dedicated host CA,
explicit preinstalled host-key process or new-workstation procedure was found.
Its system SSH configuration uses ordinary known-host handling. A safe follow-up
used an empty temporary `UserKnownHostsFile`, disabled global host files,
identities, agents and persistent configuration, and sent only `true`:

| Mode, on the already authenticated tailnet workstation | Result |
| --- | --- |
| `StrictHostKeyChecking=yes` | Exit 255, host-key verification failed, temporary trust file remained empty |
| `StrictHostKeyChecking=accept-new` | Exit 0, expected Tailscale endpoint/key, SSH authentication type `none`, key recorded only in the temporary file |

No artifact or deployer was uploaded. This observes first SSH use without a
stored SSH pin on the current authenticated tailnet workstation. It does not
enroll a genuinely new workstation or demonstrate the organization's rules for
approving one. Tailscale node authentication, company node authorization and
initial SSH key acceptance remain distinct facts.

### 4. Root access, enrollment and replacement

The VM's current effective `SSHPolicy` has three accepting rules permitting
`root`. Correlation with local Tailscale device/user records identifies:

- Gary's current laptop, owned by `gary@davai.co`; root authentication was
  directly exercised with no SSH private key or password.
- Four device addresses belonging to `emile@davai.co`; their root permission
  is present at the SSH-policy layer, not separately exercised from those devices.
- Two additional IPv4 device principals, `100.106.119.120` and `100.125.232.36`,
  whose owners cannot be mapped from either available peer map. Their SSH rule
  permits root, but their current reachability/network authorization was not
  tested. Do not silently omit these principals or infer their owners.

The effective rules are expanded device principals, not the administrative
source policy. They do not reveal `tagOwners`, user roles, groups, who can issue
enrollment keys, who can edit policy, or Hetzner team membership.

The source/history search found an important provisioning qualification:
`d5c8aba5af2a3673d0b9e4a1cc686fa01cbeab1c` switched to an externally supplied
`TAILSCALE_AUTH_KEY` and removed Terraform's key-creation resource. Current
`scripts/odoo-instance:275–277` passes the supplied key; the variable validation
checks its prefix, not expiry, reuse, preapproval or tags. The original setup
chat ties the initial enrollment to the key owner's `emile@davai.co` identity
and records a subsequent policy change, but it is not an admin-role inventory.
The tag is now observed live; the precise tagging/change history is unavailable.

README/HETZNER instructions describing Terraform OAuth-created, one-hour,
single-use keys are stale for this manual-key workflow. Those properties must
not be treated as established for the supplied enrollment key. No credentials
were used from the historical chat or reproduced in this report.

### Revised handoff and verdict

Questions 1 and 2 are now answered with live evidence. Question 3's current
route/authentication mechanism is established; a genuinely new workstation's
organization-specific approval/process remains undocumented. Question 4 has
partial concrete root-access evidence, but enrollment/replacement authority and
two root-policy device owners remain unavailable.

**Revised verdict:** the observed supported staging route has an independent
Tailscale node-authentication anchor, so a generic unverified-public-SSH MITM is
not established. The wrapper's permissive target handling remains demonstrated.
The broader-search handoff, before the owner clarification below, requested:

1. Current tailnet administrator/tag-owner and auth-key issuance rights, key
   restrictions and enrollment approval process; Hetzner project members/token
   permissions able to replace this VM. Root access is not proof of these rights.
2. Owners/purpose of the two additional root-rule device principals, plus the
   source network/SSH policy that explains all three effective rules.
3. New-workstation approval and legitimate node/host-key replacement procedure,
   including how the staging association is independently approved after change.

The local raw network map requires root and the workstation has no passwordless
sudo; it was not obtained by changing operator settings. The verified server's
root account could expose its own effective SSH rules through a filtered read.
Neither these rules nor status/API metadata grants access to the administrative
policy/role inventory. No credential creation, device enrollment, policy changes,
service changes, key rotation or deployment was performed.

Follow-up verification: local evidence links, ticket index, preserved placeholder
and `git diff --check` passed. No product code changed, so payment/deployment
regression suites were not rerun for this documentation-only follow-up; the risky
connection/identity observations were exercised as described above. Independent
Standards and Spec reviewers assessed `git diff 790bfca...e1617b0`: 0 findings on
each axis. The reviewers assessed the recorded evidence without repeating live
queries. This final provenance/review note was added after their review.

## Owner clarification — 2026-10-01

Gary subsequently confirmed:

- Emile has administrative authority to enroll/tag devices and replace the
  Hetzner staging VM.
- The two additional root-rule device principals, `100.106.119.120` and
  `100.125.232.36`, belong to Emile, Gary's boss.
- Gary does not have the approved new-workstation and legitimate VM/key
  replacement procedure.

These are owner-supplied facts, distinct from the earlier machine observations.
They resolve the administrator and two-device ownership questions; they do not
constitute an independently exported role/policy inventory or prove enrollment
key restrictions. No exclusivity of administrative rights is inferred.

**Needs-info handoff as of 2026-10-01 (superseded below):** Emile should provide or approve the procedure
for authorizing a new workstation, verifying the approved staging association
before its first upload, and approving/re-verifying a legitimate VM, Tailscale
node or SSH host-key replacement. The procedure should specify enrollment-key
settings and preserve rejection of an unexpected identity change. No message
was sent to Emile. Ticket 32 remains open for this procedure; the earlier requests
to identify the administrator and the two device owners are resolved.

This clarification changes documentation only. Evidence links, the ticket index
and whitespace were checked; runtime suites were not repeated because no code
or deployed behavior changed.


## Owner scope decision and closure — 2026-10-02

After discussing the remaining work with Emile, Gary requested that ticket 32
be set aside and closed. The team will deliver the addon to the client; it will
not own workstation setup, deployment access or host/VM/device/key replacement
procedures. Gary reports that the client and its Odoo/Revolut support or
operations teams will handle these human tasks. SaaS was mentioned, but a
specific hosting platform and allocation of provider responsibilities were not
verified by this investigation.

[Ticket 32](../tickets/wontfix/32-investigate-deployment-host-authentication.md)
is therefore **closed / wontfix**, by owner scope decision. No further owner
procedure is requested from Gary under this ticket. The evidence and conditional
correction proposal are retained for the eventual hosting operator; the
first-deployment procedure remains unresolved. This disposition does not change
the technical verdict, establish safety, or claim a remediation. No runtime,
deployment, credential or infrastructure change was made.

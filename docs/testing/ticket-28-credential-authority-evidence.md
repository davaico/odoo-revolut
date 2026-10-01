# Ticket 28 — company-scoped Merchant credential authority

The implementation began from reviewed `origin/main` and was integrated with
`09c982d` (the ticket 12 session-rollover fix). Addon version: `19.0.1.10.0`.
This is mocked local evidence, not a staging deployment or live Merchant test.

## Boundary and security-fix verification

- A server-administrator-owned authority record binds one environment-variable
  reference to one company and one Revolut environment. POS managers cannot
  create, edit, delete, reassign, or read another company's authority records.
  The binding is checked when a method is configured and again before Merchant
  HTTP for connection checks, payment starts, refunds, and recovery.
- Financial operations retain their original company, environment, and secret
  reference. A method change cannot redirect an existing attempt to a new
  Merchant account. A missing secret fails before refund reservation is saved.
  An unbound historical attempt fails closed, retains its financial evidence,
  and shows an administrator remedy without revealing a secret.
- Two-company Odoo tests exercise restricted manager configuration and direct
  public payment/refund/recovery entrypoints, including foreign IDs, altered
  allowed-company context, method reassignment, historical references, and
  unauthorized connection checks. Mocked provider calls remain at zero on
  rejected paths; authorized same-company controls make expected mocked calls.
  The POS browser receives no credential value or foreign-reference inventory.
- An independent Standards/Spec review found no remaining concrete tenant
  bypass after the missing-secret preflight and unbound-history remedy were
  added. The requested public two-company entrypoint regression was added and
  run against real Odoo. This verifies the reported foreign-credential
  selection paths; it does not assert that a live Merchant account was probed.

## Executed checks

| Check | Result |
| --- | --- |
| Focused real Odoo credential authority, payment-method, reconciliation, and refund suite | 76 tests, zero failures/errors |
| Credential-authority upgrade from `09c982d` in a fresh Odoo database | Passed: old pending operation stays unbound, zero provider HTTP before administrator attestation, GET-only recovery afterward |
| Historical cart-authority upgrade from old to current runtime | Passed: six historical states and legacy refund preserved |
| Restart recovery across separate Odoo processes | Passed: two authorized carts, four seed POSTs, zero financial replay during wait/recovery |
| Python compilation and Git whitespace checks | Passed |

All automated Merchant HTTP was mocked and covered by the test harness's
outbound-Merchant guard. The suite also exercises declined/cancelled and
verified refund paths inherited from the integrated main revision.

## Upgrade and staging handoff

The upgrade creates **no** authority records or historical-operation bindings
from existing payment-method values. Before reopening the staging POS, a
system administrator must independently verify the Merchant account and
company behind each current environment variable and create the matching
authority record under **Point of Sale → Revolut Merchant Authorities**.
For a historical operation that still needs provider reconciliation or a new
refund, the administrator must explicitly attest its exact company,
environment, and reference using the server-side action documented in
`docs/installation.md`. Keep the old secret available while those attempts
need recovery. Do not infer account ownership from the old reference name or
send a replacement financial mutation for an uncertain attempt.

The ticket 12 staging preflight at this handoff found five verified refund
operations and no pending payment operations. Those verified operations remain
stored and unbound after migration. The same-register, closed-to-opened POS
session refund settlement in `09c982d` can finalize their Odoo orders locally;
provider polling of a historical operation requires administrator attestation.
Backups and isolated restore have been checked by the ticket 12 owner. Staging
has not been upgraded or reopened as part of ticket 28, and no physical-terminal
acceptance is claimed here.

## Post-upgrade administrator action correction — 2026-10-01

The guarded ticket 12 deployment installed `f303580` on staging. A system
administrator created the reviewed Davai/production authority. Four existing
verified refunds finalized locally without binding historical payment
operations. The remaining two-card return requires a new one-penny refund
from historical source `16`. Its recorded provider IDs matched the earlier
independent Merchant GET, but the documented administrator attestation action
raised the operation model's write ACL before saving anything. No new refund
was dispatched.

A real-administrator mocked Odoo test reproduced that exact `AccessError`.
The action now checks the administrator group and exact original credential
authority, then performs only its internal binding write with server
authority. The red test failed with one access error; the corrected test passed,
as did all 53 credential-authority and refund tests. Candidate addon version
`19.0.1.10.1` still requires upgrade and a live retry of the same historical
attestation before the remaining refund can proceed.

The exact follow-up commit `d52a4079522b9fd56ff282e02d3ec91f92147e5d`
passed packaged migration acceptance (nine Restaurant tests in each phase,
zero failures/errors) and was pushed to `main`. The guarded staging upgrade
installed `19.0.1.10.1` with a configuration backup and healthy Odoo restart.
Using the real administrator identity, the documented action bound only the
independently reviewed historical payment operation `16` to authority `1`.
Readback showed operation `17` remained unbound. Refund operation count was
still five; this attestation made no Merchant request or new refund.


## Completion audit — 2026-10-01

Audited runtime: `57af76b26f8b1e4e126a24153ff57b480ea0180d`, matching the
local `origin/main` at the start of this task. The original fix `5033eb7` and
administrator correction `d52a407` are already integrated; this audit makes no
runtime change. The company authority controls are unchanged since the tested
administrator correction. Later ticket 12 changes add local refund settlement
and recovery behavior without changing credential selection.

### Independent Standards review

No hard implementation violations were found against `AGENTS.md`, `CONTEXT.md`
or the tracker guidelines. One optional **possible Duplicated Code** suggestion
remains: `pos_payment_method.py` and `revolut_reconciliation.py` both compare
credential company, environment and reference with the frozen operation.
Their additional checks differ; no correctness defect was demonstrated and no
refactor was introduced during completion. Standards: zero hard findings, one
low-priority maintenance suggestion.

### Independent Spec review

Zero actionable findings. Exact administrator-owned authorization is enforced
on configuration and credential use; frozen attempts, refund preflight and
historical attestation preserve the original Merchant account. Existing public
entrypoint tests cover foreign IDs and company context with zero mocked
provider calls on rejection. Authority ACLs deny tenant inventory reads, POS
exports omit credential fields, snapshots use allowlists, and connection errors
strip provider exceptions. Static review found only operation IDs and fixed
outcome labels in addon logs, without credentials, reference inventories,
headers or report bodies. This review relies on the recorded earlier Odoo
execution and current static inspection; it claims no fresh Odoo pass.

### Explicit independent security-fix verification

| Source finding | Verdict | Boundary evidence |
| --- | --- | --- |
| `csf_80f049f2c08527348e7c02a1` | `fixed` | Exact administrator-owned company/environment/reference authorization precedes connection-check, payment, refund, report and recovery HTTP. The adapter rechecks persisted method/company/authority snapshots before loading any secret. Context or foreign terminal/location input cannot select another company's authority. |
| `csf_5563e82d2fa05c79f4d2223a` | `fixed` | Configuration create/write and inherited copy/import enforce authorization. Managers cannot provision or reassign authority; historical attestation requires administrator membership plus an exact frozen tuple. Rotation controls retain the historical account. |

The verifier traced manual association, cron/restart recovery, refund source
selection and reporting to the same authority gate. The two-company regressions
in `test_revolut_credential_authority.py` and public entrypoint regressions in
`test_revolut_reconciliation.py`, together with prior recorded runtime results,
support legitimate same-company behavior and the rejected foreign paths.
Managers may still read reference names already recorded on their own company's
historical operation rows; those names grant no credential authority. No live
credential inventory was inspected and no new runtime or live Merchant pass is
claimed.

### Checks in this completion task

| Check | Result |
| --- | --- |
| `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | 75 tests passed, zero failures/skips |
| Python AST syntax / XML parsing across `addons/` | 48 Python files and 11 XML files passed |
| `bash -n scripts/test-addon scripts/test-credential-authority-upgrade scripts/test-restart-recovery` | Passed |
| `git diff --check` | Passed |
| Focused `scripts/test-addon` credential/method/reconciliation/refund run | Could not start: Docker daemon socket unavailable; zero Odoo tests executed |
| Full `scripts/test-addon --verify-install-upgrade` | Same startup failure; zero install/upgrade or Restaurant tests executed |

There is no configured Python or JavaScript typechecking pipeline in this
repository. Syntax checks do not exercise Odoo access controls or payment
behavior. The earlier 76-test, 53-test, upgrade, packaged migration and restart
results above retain their original revision identities; they are not reruns
of the current runtime. Fresh full Odoo install/upgrade, Restaurant and restart
acceptance must run where the pinned Docker harness is available before ticket
12's final release acceptance.

### Remaining deployment and release work

The prior ticket 12 records report a staging upgrade to `19.0.1.10.1` and one
reviewed historical attestation. This audit performs no deployment or provider
operation. For each further company or historical source, administrators must
follow `docs/installation.md`: independently verify Merchant ownership, provision
the exact authority, attest only reviewed frozen records, and keep original
credentials available for outstanding recovery. Leave uncertain records blocked
and preserve their reservations; do not create replacement mutations. Ticket
12 owns updated candidate acceptance, device checks and final financial
reconciliation. Ticket 28's local implementation and verification scope is
closed against the combined historical and current evidence.

While this audit ran, `main` advanced to `7351c7c` through a separate ticket 12
documentation commit. Its only files are ticket 12 evidence and the ticket 12
tracker record; the audited addon runtime is unchanged. Those earlier edits were
preserved; this completion commit only updates the two current ticket 28 gate
references in those files. Dated checkpoints remain historical records.

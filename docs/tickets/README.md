# Odoo–Revolut tickets

Approved implementation and architecture work for the Odoo–Revolut addon. Tickets 01–12 come from the original project planning conversation and approved implementation plan. Tickets 13–15 come from the architecture review and breakdown approved on 2026-09-25. Tickets 16–18 address findings from the final integrated audit and were approved on the same date. Tickets 19–21 address the four findings from the integrated payment safety audit on 2026-09-28; their three-ticket grouping was approved on the same date. No tracker issue URLs were supplied, so no parent issue is invented or modified.

## Triage folders and state

Open tickets are filed by the canonical triage label recorded in each file.
The `ready-for-agent` label uses the owner-selected `ready-for-agents/` folder:

- **`needs-triage`:** maintainer evaluation is required.
- **`needs-info`:** external information or access is required.
- **`ready-for-agent`:** the ticket is fully specified; dependency gates still
  apply.
- **`ready-for-human`:** human or physical-world execution is required.
- **`wontfix`:** the ticket will not be actioned.

Completed tickets are archived under **`closed`**. Lifecycle state is separate
from triage: an open ticket has state `open` or `claimed`, while completed and
`wontfix` tickets have state `closed`. Placeholder files preserve empty label
folders in Git.

Keep `ready-for-agents/.gitkeep` when moving or closing the last ticket so
the folder remains available in future checkouts.

Numbers are stable identifiers assigned in dependency order. They do not
require linear execution: a `ready-for-agent` ticket is actionable only when
all of its blockers are closed. Move a ticket when its triage label changes,
set its state to `claimed` when work starts, and update this index. Do not
renumber, duplicate or erase dependency history. On completion, record
verification evidence, set state to `closed`, and move the ticket to `closed/`.

## Branch workflow

Each ticket declares its local `codex/<ticket-number>-<slug>` work branch
immediately below the title. The original 12 branches were created from the
same committed ticket baseline; branch existence does not satisfy a dependency.
Branches for tickets 13–15 are created from the committed ticket definitions
on reviewed `main`. Update the assigned branch from `main` before claiming work.
Branches for tickets 16–18 are created from their committed definitions on
`main`. Update the assigned branch from reviewed `main` before starting.

Branches for tickets 19–21 are created from their committed definitions on
`main`. Update the assigned branch from reviewed `main` before starting,
without overwriting existing work.

Ticket 34 requires a newly created, appropriately named integration branch in
`odoo-revolut`, following this repository's conventions. Hosting changes must
use `feat/revolut-staging` in `odoo-hosting`,
reusing that branch if present or creating it if absent.

Use `main` as the shared integration branch for this ticket set. Integrate
reviewed, verified ticket work there, including its state and triage updates.
Before starting a ticket, merge the latest integration branch into its assigned
branch and confirm every declared blocker is closed and its implementation is
present. Never treat branch existence as permission to skip blockers. Do not
reset or overwrite a branch that already contains work.

Use separate worktrees for concurrent agents, within the project's designated worktree area. Keep each ticket's changes on its assigned branch. Resolve overlaps against the integration branch and run the affected tests before integration. These branches are local; publishing them to a remote is a separate action.

## Ticket directory

| Ticket | Triage | State | Blocked by |
| --- | --- | --- | --- |
| [01 — Configure and verify a Revolut payment method](closed/01-configure-revolut-payment-method.md) | `ready-for-agent` at closure | Closed | None |
| [02 — Resolve the Revolut terminal contract and testing prerequisites](closed/02-confirm-terminal-contract.md) | `ready-for-agent` at closure | Closed | None |
| [03 — Complete one verified Revolut terminal payment](closed/03-verified-terminal-payment.md) | `ready-for-agent` at closure | Closed | 01 (closed) |
| [04 — Handle unsuccessful payments and safe retries](closed/04-unsuccessful-payments-safe-retries.md) | `ready-for-agent` at closure | Closed | 03 (closed) |
| [05 — Recover payments after interruption or late success](closed/05-recover-interrupted-payments.md) | `ready-for-agent` at closure | Closed | 04 (closed) |
| [06 — Resolve uncertain payments from a manager worklist](closed/06-manager-reconciliation-worklist.md) | `ready-for-agent` at closure | Closed | 05 (closed) |
| [07 — Use Revolut with split tender and restaurant checkout](closed/07-split-tender-restaurant-checkout.md) | `ready-for-agent` at closure | Closed | 05 (closed) |
| [08 — Issue and reconcile a full Revolut refund](closed/08-full-revolut-refund.md) | `ready-for-agent` at closure | Closed | 05 (closed) |
| [09 — Issue partial refunds across original payment allocations](closed/09-partial-allocated-refunds.md) | `ready-for-agent` at closure | Closed | 07 (closed), 08 (closed) |
| [10 — Install and upgrade a reviewed revision on staging](closed/10-staging-install-upgrade.md) | `ready-for-human` at closure | Closed | 03 (closed) |
| [11 — Verify the complete addon on the target Odoo version](closed/11-target-version-acceptance.md) | `ready-for-agent` at closure | Closed | 06, 09, 10 |
| [12 — Validate real terminal payments and publish release evidence](ready-for-human/12-live-terminal-release-evidence.md) | `ready-for-human` | Open | 02, 11, 16–24, 27 and 28 closed; refund 1012 still processing, final reconciliation, updated-device and broader acceptance |
| [13 — Deepen Return allocation](closed/13-deepen-return-allocation.md) | `ready-for-agent` at closure | Closed | None |
| [14 — Deepen POS payment state](closed/14-deepen-pos-payment-state.md) | `ready-for-agent` at closure | Closed | None |
| [15 — Deepen payment outcome application](closed/15-deepen-payment-outcome-application.md) | `ready-for-agent` at closure | Closed | None |
| [16 — Preserve uncertain refunds when original-sale recovery fails](closed/16-preserve-uncertain-refund-recovery.md) | `ready-for-agent` at closure | Closed | None |
| [17 — Deliver the Restaurant bridge with the reviewed addon release](closed/17-deliver-restaurant-bridge.md) | `ready-for-agent` at closure | Closed | None |
| [18 — Isolate internal payment records by allowed company](closed/18-isolate-internal-payment-records.md) | `ready-for-agent` at closure | Closed | None |
| [19 — Enforce verified settlement and internal-operation permissions](closed/19-enforce-payment-server-boundaries.md) | `ready-for-agent` at closure | Closed | None |
| [20 — Recover POS lines after a failed pre-payment lookup](closed/20-recover-undispatched-pos-lines.md) | `ready-for-agent` at closure | Closed | None |
| [21 — Keep reconciliation progressing after malformed provider responses](closed/21-isolate-reconciliation-failures.md) | `ready-for-agent` at closure | Closed | None |
| [22 — Recover a POS line after a terminal-busy rejection](closed/22-recover-terminal-busy-rejection.md) | `ready-for-human` at closure | Closed | None; controlled two-browser no-card retest passed on staging |
| [23 — Preserve payment polling through valid processing states](closed/23-preserve-polling-through-payment-processing.md) | `ready-for-human` at closure | Closed | None; full, Cash/Revolut split and two-card live retests passed |
| [24 — Bound financial snapshot processing before numeric expansion](closed/24-bound-financial-snapshot-processing.md) | `ready-for-agent` at closure | Closed | None for local validation and mocked implementation |
| [25 — Download historical Revolut payment and refund receipts](closed/25-download-historical-payment-refund-receipts.md) | `ready-for-agent` at closure | Closed | None for local implementation and mocked verification |
| [26 — Decide server-authorized cart and tip behavior](closed/26-decide-order-and-tip-authorization.md) | `ready-for-agent` at closure | Closed | None |
| [27 — Enforce the authorized order balance before terminal dispatch](closed/27-enforce-authorized-terminal-allocation.md) | `ready-for-agent` at closure | Closed | 26 (closed); fix merged to main, staging/device acceptance remains ticket 12 |
| [28 — Bind Revolut credential authority to the owning company](closed/28-bind-merchant-credentials-to-company.md) | `ready-for-agent` at closure | Closed | None; integrated fix, migration evidence and independent verification accepted |
| [29 — Determine the impact of concurrent payment status polling](needs-info/29-investigate-concurrent-status-polling.md) | `needs-info` | Open | Effective Odoo/proxy capacity and Merchant quota; bounded local evidence preserved |
| [30 — Determine authorized access to shared POS sessions](ready-for-agents/30-investigate-shared-pos-session-authorization.md) | `ready-for-agent` | Open | None for local work; external evidence may be required |
| [31 — Determine deployment upload and lock-file exploitability](needs-info/31-investigate-privileged-deployment-files.md) | `needs-info` | Open | Target host facts and authorized review access; partial evidence preserved |
| [32 — Verify deployment host identity on first SSH use](needs-info/32-investigate-deployment-host-authentication.md) | `needs-info` | Open | Route/VM verified; Emile confirmed as administrator/device owner; workstation/replacement procedure missing |
| [33 — Determine whether release evidence exposes restricted identifiers](ready-for-agents/33-investigate-release-evidence-disclosure.md) | `ready-for-agent` | Open | None for local work; external evidence may be required |
| [34 — Provision and gate Odoo PDF generation](needs-triage/34-provision-and-gate-odoo-pdf-generation.md) | `needs-triage` | Open | None for local implementation; authorized staging access and existing safety gates for rollout |

## Architecture triage — 2026-09-25

Tickets 13–15 were approved as independent architecture work and are now
closed. Their design decisions and verification evidence remain in their
archived tickets.

## Final audit corrections — 2026-09-25

The owner approved tickets 16–18 and requested direct publication as
`ready-for-agent`. All three can start independently; suggested priority is
16, then 18, then 17, without introducing dependencies between them. Coordinate
overlapping tests during integration. Ticket 02's contract verification is now
closed; physical-terminal and financial acceptance remain ticket 12 work.

All three corrections block ticket 12. Before live acceptance, integrate their
reviewed implementations and record mocked install, upgrade and Restaurant
acceptance on the final combined revision, including the delivered artifact.

## Integrated payment safety corrections — 2026-09-28

The owner approved three tickets covering the four findings in the
[integrated payment safety audit](../testing/release-audit-2026-09-28.md):

- **19 (P1):** enforce verified settlement across server entry points and close
  the related internal-lock authorization bypass.
- **20 (P2):** recover an undispatched POS payment/refund after discovery fails.
- **21 (P2):** validate malformed provider evidence and keep other operations
  progressing during reconciliation.

Tickets 19–21 are closed with reviewed corrections and mocked
install/upgrade evidence. Ticket 21 also records actual transaction isolation,
malformed-provider recovery and restart verification; ticket 20 records POS
discovery recovery. Coordinate overlapping changes during integration. Ticket
02 is also closed with its documented/observed contract; ticket 12 retains all
physical-terminal and financial acceptance work.

All three block ticket 12. Before live acceptance, independently review the
payment-verification boundary and record the full integrated mocked suite on
the final combined revision: install/upgrade, Restaurant, lifecycle,
deployment checks, restart recovery, delivered-artifact acceptance and the new
adversarial regressions. Earlier green runs are baseline evidence, not proof
that these newly identified paths are fixed.

Ticket 12's [software evidence and operator
checklist](../testing/ticket-12-release-evidence.md) records the combined candidate,
an additional reviewed historical-tender refund correction, and the controlled
human handoff. Physical-device testing subsequently ran on 2026-09-29, with
the [operator chronology](../testing/ticket-12-operator-observations.md)
recording verified payments, selected guard/recovery passes, five pending
refunds and explicitly unexecuted subcases. Tickets 22–23 were triaged on
2026-09-29 as `ready-for-agent` for local diagnosis and mocked implementation
of busy-terminal recovery and automatic status handling;
they must be resolved and retested before ticket 12 closes. Full acceptance
and financial reconciliation remain open under `ready-for-human`.

## Financial snapshot resource bounds — 2026-09-30

The owner approved [ticket 24](closed/24-bound-financial-snapshot-processing.md)
as one complete remediation slice and approved direct placement in
`ready-for-agents/`. It covers safe pinned-Odoo validation, resource bounds
before numeric expansion, shared payment/refund and settlement behavior, POS
rejection recovery, regression tests and independent fix verification.

Ticket 24 is closed locally with original implementation `604962a` and the
[bounded Odoo reproduction and independent verification](../testing/ticket-24-financial-snapshot-bounds.md).
The authenticated cashier amplification path and old helper's cashier/manager/
internal/portal dispatch were demonstrated on the baseline. Shared bounds now
reject unsupported input and the private utility rejects RPC dispatch.
The combined `19.0.1.7.8` candidate `d64e962` includes main `fbab631` and its
ticket 23 processing correction. Its refreshed acceptance is in the linked
record: 243 install, 243 upgrade and eight Restaurant tests, 71 lifecycle and
29 deployment checks, plus restart recovery, all passed. The original
234/234/eight and 65/29 results retain their initial identity.
Standards/Spec findings are zero; independent resource-bound fix verification
reports `fixed`. Actual deployed worker exhaustion remains unverified; the
original outage severity is separate from local remediation completion.

Ticket 12 still requires reviewed integration and final combined-candidate
acceptance before closure. Ticket 23's reviewed local correction is now in main
and this branch; refresh combined-candidate evidence while preserving earlier
dated results and outstanding human and financial reconciliation gates.

## Security scan follow-up — 2026-09-30

The owner approved tickets **26–33** and their direct placement in
`ready-for-agents/`. This set follows individual static triage of all 32
retained findings from Codex Security scan
`95c73550-ed81-4cfe-9e81-b6f2be355a38`. That scan was canceled with partial
coverage; the triage assessed reviewed main revision
`1d549c11507878fd95fb91a38337599d486e7afc`, not proof of the deployed version.

- **26** selects validated native drafts, atomic base allocations and required customer-selected terminal tips verified through authenticated payments reports. The owner approved waiting safely for report details; the design is closed locally, with target-device/report acceptance remaining a release gate.
- **27**, blocked by **26**, remediates the five confirmed amount-authority
  findings as one complete checkout slice. Ticket 26's reviewed design is now
  integrated into its assigned branch. On 2026-10-01 the ticket's explicit
  complete-slice stop condition was used to propose a [concrete development
  breakdown](../ticket-27-implementation-breakdown.md); ticket 27 remains open
  under `needs-triage` pending sequencing review at that point, with all five
  source claims still open and no runtime guard in that documentation-only
  proposal. The owner resumed complete implementation later on 2026-10-01;
  P1–P6 became internal milestones of the complete candidate. Ticket 27 is now
  closed locally on tested runtime `88c88a5`: both 340-test install/upgrade
  phases, nine Restaurant checks and both exact-artifact scenarios pass.
  Independent Standards/Spec review is clean and all five source claims were
  explicitly verified fixed. [Final evidence](../testing/ticket-27-cart-authority.md)
  records the commands, hashes and separate ticket 12 physical-device gate.
  The work branch awaits shared integration; the live POS was untouched.
- **28** is closed on 2026-10-01 after auditing the integrated company credential
  authority fix and administrator-attestation correction at `57af76b`.
  Independent Standards/Spec review found no actionable implementation defects;
  both source claims were verified fixed. [Evidence](../testing/ticket-28-credential-authority-evidence.md)
  distinguishes prior mocked Odoo install/upgrade/restart checks from today's
  available checks and the unavailable fresh Docker rerun. Ticket 12 retains
  final combined-runtime and live acceptance.
- **29–33** investigate the eleven unresolved findings: concurrent polling,
  shared-register authorization, privileged deployment files, first-use SSH
  identity, and release-evidence disclosure. Every source ID remains in its
  assigned ticket; shared investigation setup does not merge source verdicts.

The only new logical dependency is **26 → 27**. All other tickets can begin
local work independently. Coordinate overlapping payment-adapter changes
between 27 and 28; use fixed revisions and separate worktrees for concurrent
work. Investigation tickets are agent-ready because their questions, methods
and deliverables are specified, not because their security claims are confirmed.
If essential external evidence is unavailable, record a targeted needs-info
handoff rather than closing the claim as safe.

The fourteen snapshot-normalization findings were addressed by ticket 24 on
the assessed main revision and receive no duplicate remediation tickets.
The owner subsequently authorized closing those fourteen scan findings as
`already_fixed`; their closure notes cite ticket 24 and merge commit `1d549c1`.
Do not infer deployment from that source assessment or repeat the old fix
against a stale checkout. Each new ticket records its release relationship;
this publication does not change or close parent ticket 12. Confirmed fixes
require reviewed regression evidence, while investigation outcomes determine
whether additional remediation is needed before final release acceptance.

### Ticket 31 deferral — 2026-10-01

Ticket 31 is now **open / needs-info** after repeated cybersecurity content
restrictions interrupted its investigation. Its [partial evidence and
infrastructure handoff](../testing/ticket-31-partial-investigation.md) preserves
17 passing local fixture cases and their limits. All six linked findings
remain `needs_review`; target host configuration and actual upload behavior
are unverified. This later status supersedes the original agent-ready
placement above. Other tickets retain their own dependencies.

## Shared implementation contract

- The addon, tests, documentation and local deployment tooling belong to odoo-revolut. Hosting provisioning is complete for this scope; do not edit odoo-hosting or develop source on the server.
- Target Odoo Community 19.0.20260908. Use existing Odoo conventions and runtime facilities; a new framework or dependency requires approval.
- Every product ticket includes the persistence, server behavior, UI, tests and documentation needed to demonstrate its stated outcome. Ticket 02 is an external-contract verification slice; tickets 10–12 are delivery/acceptance slices. Tickets 13–15 are behavior-preserving architecture refactors of the implemented addon, each verified through its complete affected workflow.
- Support retail and restaurant, a configured terminal per payment method, server-managed secrets and manager-only refunds. Late successful payments finalize when the unchanged original order resumes, rather than through unattended background order finalization.
- Persist operations before external dispatch. Verify the underlying payment, never intent completion alone. Unknown outcomes remain unresolved; local timeouts, empty payment lists and missing IDs do not prove retry safety.
- Never expose credentials to POS or logs. All automated Merchant API calls are mocked; actual terminal testing belongs to the explicitly controlled acceptance session.
- Dependencies are gates, not a task ordering preference: closed ticket 02 supplies the documented/observed contract, while ticket 12 owns physical-terminal configuration and financial acceptance. Shared code changes from independently ready tickets still require coordination and integration review.

Read the project instructions, API validation report and development-environment document before implementing. Current documentation and official source take precedence over stale assumptions; record provider ambiguities rather than silently choosing financial behavior.

### Ticket 29 investigation — 2026-10-02

Ticket 29 is now **open / needs-info**. Its
[concurrent-status evidence](../testing/ticket-29-concurrent-status-polling.md)
records three simultaneous mocked provider reads for the same operation and
successful financial/late-success controls. Source claim
`csf_95a9d6200acbce5037818172` remains `needs_review`; no deployed worker or
Merchant quota exhaustion was demonstrated. Effective deployment admission
limits and Merchant endpoint/account quotas are required for a final verdict.
The owner's requested recommendation and a separate scoped lease proposal are
recorded; runtime polling was unchanged. This supersedes ticket 29's original
agent-ready placement without changing ticket 12's release gates.

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
| [12 — Retest the complete integration before release and open-source publication](ready-for-human/12-live-terminal-release-evidence.md) | `ready-for-human` | Open | Manual evidence through .18.10; PR #73 records .18.11 deployed, targeted retests pending; six refunds last observed pending; setup-dependent coverage and 33 publication gate open; 34 PDF gate closed |
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
| [29 — Determine the impact of concurrent payment status polling](closed/29-investigate-concurrent-status-polling.md) | `ready-for-agent` at closure | Closed | Investigation complete; duplicate-read HTTP contention confirmed, separate proposal in 38 |
| [30 — Determine authorized access to shared POS sessions](closed/30-investigate-shared-pos-session-authorization.md) | `ready-for-agent` at closure | Closed | Investigation complete; confirmed policy gap and recovery bypass proposed as ticket 35 |
| [31 — Determine deployment upload and lock-file exploitability](wontfix/31-investigate-privileged-deployment-files.md) | `wontfix` | Closed | Owner stopped investigation after Daybreak interruptions; six findings closed locally as wontfix; workbench unchanged |
| [32 — Verify deployment host identity on first SSH use](wontfix/32-investigate-deployment-host-authentication.md) | `wontfix` | Closed | Owner scope decision (2026-10-02): client/hosting operator handles deployment access; evidence retained, first-deployment procedure unresolved |
| [33 — Determine whether release evidence exposes restricted identifiers](needs-info/33-investigate-release-evidence-disclosure.md) | `needs-info` | Open | Owner policy resolved and sample references confirmed; permanent private retention, custodian and recovery remain unverified |
| [34 — Provision and gate Odoo PDF generation](closed/34-provision-and-gate-odoo-pdf-generation.md) | `ready-for-human` at closure | Closed | Native staging invoice PDF inspected; repeat downloads confirmed 2026-10-09; physical printing skipped by owner |
| [35 — Enforce explicit backend-user access to shared registers](closed/35-enforce-shared-register-authorization.md) | `ready-for-agent` at closure | Closed | Explicit grants verified; 406 install/406 upgrade/9 Restaurant; rollout remains 12 |
| [36 — Remove custom Revolut receipts and preserve native printing](closed/36-remove-custom-revolut-receipts.md) | `ready-for-agent` at closure | Closed | 398 install/398 upgrade/9 Restaurant; actual native PDF and old-release preservation verified; physical/staging gates remain 12/34 |
| [37 — Reconcile refunds created outside Odoo](closed/37-reconcile-external-terminal-refunds.md) | `ready-for-agent` at closure | Closed | GET-only discovery and separate native reconciliation verified; 430 install + tip regression/431 upgrade/9 Restaurant; rollout and live reconciliation remain 12 |
| [38 — Coalesce concurrent payment status polls](closed/38-coalesce-concurrent-payment-status-polls.md) | `ready-for-agent` at closure | Closed | Coalesced observations; 446 install / 446 upgrade / 9 Restaurant tests passed |
| [39 — Honor payment cancellation before dispatch](closed/39-cancel-payment-before-dispatch.md) | `ready-for-agent` at closure | Closed | Cancelled preparation prevents dispatch; 88 lifecycle tests, 5 focused native tests and 493 install/493 upgrade tests verified |
| [40 — Conserve rounding across partial refunds](closed/40-conserve-partial-refund-rounding.md) | `ready-for-agent` at closure | Closed | Conserved 309/925 returns; 508 install / 508 upgrade, native accounting/receipts and actual history upgrades verified |
| [41 — Complete Revolut-initiated refunds through native Odoo returns](closed/41-complete-external-refund-returns.md) | `ready-for-agent` at closure | Closed | Native returns and financial corrections; 546 install tests, 90 merged checks and real history upgrades verified; full upgrade stopped at owner request |
| [42 — Deepen native return allocation and recovery](closed/42-deepen-native-return-allocation.md) | `ready-for-agent` at closure | Closed | Shared native decisions and recovery; 552 install / 552 upgrade, 90 compatibility checks and clean Standards/Spec review |
| [43 — Deepen external return association and unify return locking](closed/43-deepen-external-return-allocation.md) | `ready-for-agent` at closure | Closed | Shared batch association and complete native ownership locking; 561 install / 561 upgrade, historical compatibility and independent Standards/Spec review |
| [44 — Recover payment reservations interrupted before dispatch](closed/44-recover-unclaimed-payment-reservations.md) | `ready-for-agent` at closure | Closed | Safe unclaimed cancellation; 573 install / 573 upgrade, native recovery and clean Standards/Spec review |
| [45 — Complete refunds for discounted and rounded sales](closed/45-refund-discounted-and-rounded-sales.md) | `ready-for-agent` at closure | Closed | Conserved discounts/rounding and frozen history; 591 install / 591 upgrade tests, native returns and independent reviews passed |
| [46 — Recover checkout refresh after payment verification](closed/46-recover-verified-checkout-refresh.md) | `ready-for-agent` at closure | Closed | Read-only verified checkout recovery; 597 install / 597 upgrade tests, six native scenarios and independent reviews passed |

## Integration review follow-up — 2026-10-06

The owner approved three P2 tickets from the full integration review of main
`597a59ae0f8e489773e02f7776bda7001beb5741` and requested direct publication
as `ready-for-agent`. Ticket 44 covers recovery of an interrupted reservation
before financial dispatch is claimed. Ticket 45 groups the negative/discount
line and rounding-remainder findings into one complete return-allocation slice,
with separate regressions for both defects. Ticket 46 covers browser checkout
restoration after financial verification. All three were published open and
unclaimed, with no blocking edges between them. Ticket 44 is now closed after
safe unclaimed-reservation recovery passed 573 install / 573 upgrade tests,
native checkout/session closure and independent Standards/Spec review.
Ticket 45 is now closed after discounted and rounded return conservation passed
591 install / 591 upgrade tests, native browser/stock/accounting checks and
independent Standards/Spec review. Ticket 46 is now closed after verified
checkout recovery passed 597 install / 597 upgrade tests, six native recovery
scenarios and independent Standards/Spec review.

The review reproduced the reservation and refund defects in pinned Odoo and
the browser recovery defect in the exact state module with the pinned native
lifecycle traced. Its existing-suite baseline passed 561 fresh-install Odoo
tests, 88 state-machine tests and 50 tooling tests, with three optional checks
skipped. These results describe the reviewed baseline, not fixes or completed
ticket acceptance. Existing live-device and release gates remain separate.

## Return allocation deepening — 2026-10-06

The owner approved a merged two-ticket design: ticket 42 centralizes native
return monetary decisions and recovery; ticket 43 extends the same ownership
to external refund association and completes shared locking verification.
Both were initially published under needs-triage and promoted to
ready-for-agent at the owner's request. That triage did not claim implementation,
runtime verification or deployment. Ticket 42 is now closed after shared native
decisions and recovery passed 552 install / 552 upgrade tests, 90 compatibility
checks and independent Standards/Spec review. Its local main integration satisfies
ticket 43's dependency. Ticket 43 is now closed after shared batch association
and locking consolidation passed 561 install / 561 upgrade tests, both affected
historical upgrade scenarios and independent Standards/Spec review. One minor
optional Standards duplication heuristic remains; no Spec findings remain.
Keep native Odoo stock, receipts and accounting workflows and existing Revolut
communication unchanged. Earlier tickets 13, 40 and 41 remain closed.

## Mission audit triage — 2026-10-05

> *This was generated by AI during triage.*

The owner requested investigation and future implementation tickets for the
two defects in the [mission audit](../testing/mission-audit-2026-10-05.md).
Tickets 39 and 40 preserve the causes, reproducible cases, proposed fix
directions and evidence limits. Both were triaged at the owner's request and
are now implemented and closed. Ticket 40 completed its public Odoo reproduction,
conserved allocation and native accounting/receipt milestones, incorporating
reviewed refund-reconciliation and current refund-screen work. It passed 508
install and 508 upgrade tests plus actual financial-history preservation checks.
The tickets were independent; the reconciliation work did not fix the rounding
defect. Existing release acceptance remains separate.

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

### Ticket 31 deferral — 2026-10-01 (superseded by closure below)

Ticket 31 is now **open / needs-info** after repeated cybersecurity content
restrictions interrupted its investigation. Its [partial evidence and
infrastructure handoff](../testing/ticket-31-partial-investigation.md) preserves
17 passing local fixture cases and their limits. All six linked findings
remain `needs_review`; target host configuration and actual upload behavior
are unverified. This later status supersedes the original agent-ready
placement above. Other tickets retain their own dependencies.

### Ticket 31 closure — 2026-10-02

At Gary's request, [ticket 31](wontfix/31-investigate-privileged-deployment-files.md)
is **closed / wontfix** and set aside because repeated Daybreak interruptions
prevent continuing. All six associated findings are closed as **wontfix in the
local tracker**, with their original IDs and partial evidence preserved in the
[archived investigation record](../testing/ticket-31-partial-investigation.md).
No fix or safety verdict is claimed, and no further investigation is scheduled.
The available security tools provide no finding-triage closure operation, so
the Codex Security workbench statuses remain unchanged. This disposition
supersedes the needs-info handoff; ticket 12's own release requirements remain.

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

The initial ticket 29 handoff was **open / needs-info**. Its
[concurrent-status evidence](../testing/ticket-29-concurrent-status-polling.md)
records three simultaneous mocked provider reads for the same operation and
successful financial/late-success controls. Source claim
`csf_95a9d6200acbce5037818172` remains `needs_review`; no deployed worker or
Merchant quota exhaustion was demonstrated. Effective deployment admission
limits and Merchant endpoint/account quotas are required for a final verdict.
The owner's requested recommendation and a separate scoped lease proposal are
recorded; runtime polling was unchanged. This supersedes ticket 29's original
agent-ready placement without changing ticket 12's release gates.

The subsequent owner-supplied Revolut response and unfiltered Cloudflare Free
zone dashboard, together with verified host settings and an actual two-HTTP-worker
mocked probe, resolve that handoff. Ticket 29 is **closed as an investigation**:
duplicate reads for one cashier's operation occupy both workers and delay an
unrelated authenticated RPC while provider responses are held. No production
outage or fixed Merchant quota exhaustion is claimed, and no runtime behavior
changed. [Ticket 38](closed/38-coalesce-concurrent-payment-status-polls.md)
is closed after the owner-approved implementation on 2026-10-02.
[Verification](../testing/ticket-38-payment-observations.md) records token-fenced
coalescing and successful full mocked install/upgrade/Restaurant acceptance.

### Shared-register investigation — 2026-10-02

[Ticket 30](closed/30-investigate-shared-pos-session-authorization.md) is closed
as an investigation after the owner selected explicit backend-user register
grants with shared employee login. Both source findings are confirmed against
that policy. The unchanged addon permits native same-company initiation and
bypasses an actual register-denying record rule during known-ID recovery.
[Evidence](../testing/ticket-30-shared-pos-session-access.md) preserves the
access matrix, separate verdicts, public identifier-discovery path, twelve
mocked reproduction tests and verification limits. This is not a permission
fix or deployed exploitation claim. [Ticket 35](closed/35-enforce-shared-register-authorization.md)
is the approved agent-ready remediation described below; investigation closure
and scope approval do not mark either source finding fixed or close ticket 12.

### Ticket 35 approved triage — 2026-10-02

> *This was generated by AI during triage.*

[Ticket 35](closed/35-enforce-shared-register-authorization.md) is
**bug / ready-for-agent**, state **open**. The owner approved explicit
administrator-managed backend-user register grants for cashiers and managers,
shared employee login and colleague handoff, with no emergency manager override.
Provision supervisors for the registers they oversee. Revocation preserves
financial exposure and privileged background reconciliation. Complete the
reviewed remediation before ticket 12 final acceptance; this approval is not
a security-fix verdict.

## Native printing scope revision — 2026-10-02

> *This was generated by AI during triage.*

The owner approved ticket 36 to remove standalone Revolut payment/refund
receipts while retaining native Odoo documents and current terminal reprinting.
Ticket 25 stays closed as historical work; its custom-document requirement is
superseded. Ticket 34 retains PDF infrastructure and uses native Odoo invoice
rendering for remaining acceptance. Automatic invoicing of every sale is not
part of this removal. Ticket 36 now closes local removal and native printing
verification; final physical printing and staging acceptance remain tickets
12/34. The original publication itself changed no runtime behavior.

### Ticket 35 remediation — 2026-10-02

[Ticket 35](closed/35-enforce-shared-register-authorization.md) is closed after
administrator-only explicit register grants, native/role/company enforcement,
shared colleague controls and preserved historical/revocation/cron behavior.
[Evidence](../testing/ticket-35-register-authorization.md) records final source
`e3333ea`, current-main integration, separate Standards/Spec reviews, both linked
source findings independently verified fixed, 406 installation tests, 406 upgrade
tests, 9 Restaurant tests, 41 employee-enabled tests and old-to-new migration.
No deployment or security-workbench verdict was changed. Existing registers need
administrator provisioning during rollout; ticket 12 retains physical/financial
acceptance. Ticket 36 remains the separate approved receipt-removal task.

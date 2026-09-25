# Odoo–Revolut tickets

Approved implementation and architecture work for the Odoo–Revolut addon. Tickets 01–12 come from the original project planning conversation and approved implementation plan. Tickets 13–15 come from the architecture review and breakdown approved on 2026-09-25. Tickets 16–18 address findings from the final integrated audit and were approved on the same date. No tracker issue URLs were supplied, so no parent issue is invented or modified.

## Triage folders and state

Open tickets are filed by the canonical triage label recorded in each file:

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
| [02 — Resolve the Revolut terminal contract and testing prerequisites](needs-info/02-confirm-terminal-contract.md) | `needs-info` | Open | External: provider clarification and test access |
| [03 — Complete one verified Revolut terminal payment](closed/03-verified-terminal-payment.md) | `ready-for-agent` at closure | Closed | 01 (closed) |
| [04 — Handle unsuccessful payments and safe retries](closed/04-unsuccessful-payments-safe-retries.md) | `ready-for-agent` at closure | Closed | 03 (closed) |
| [05 — Recover payments after interruption or late success](closed/05-recover-interrupted-payments.md) | `ready-for-agent` at closure | Closed | 04 (closed) |
| [06 — Resolve uncertain payments from a manager worklist](closed/06-manager-reconciliation-worklist.md) | `ready-for-agent` at closure | Closed | 05 (closed) |
| [07 — Use Revolut with split tender and restaurant checkout](closed/07-split-tender-restaurant-checkout.md) | `ready-for-agent` at closure | Closed | 05 (closed) |
| [08 — Issue and reconcile a full Revolut refund](closed/08-full-revolut-refund.md) | `ready-for-agent` at closure | Closed | 05 (closed) |
| [09 — Issue partial refunds across original payment allocations](closed/09-partial-allocated-refunds.md) | `ready-for-agent` at closure | Closed | 07 (closed), 08 (closed) |
| [10 — Install and upgrade a reviewed revision on staging](closed/10-staging-install-upgrade.md) | `ready-for-human` at closure | Closed | 03 (closed) |
| [11 — Verify the complete addon on the target Odoo version](closed/11-target-version-acceptance.md) | `ready-for-agent` at closure | Closed | 06, 09, 10 |
| [12 — Validate real terminal payments and publish release evidence](ready-for-human/12-live-terminal-release-evidence.md) | `ready-for-human` | Open | 02, 11, 16, 17, 18 |
| [13 — Deepen Return allocation](closed/13-deepen-return-allocation.md) | `ready-for-agent` at closure | Closed | None |
| [14 — Deepen POS payment state](closed/14-deepen-pos-payment-state.md) | `ready-for-agent` at closure | Closed | None |
| [15 — Deepen payment outcome application](closed/15-deepen-payment-outcome-application.md) | `ready-for-agent` at closure | Closed | None |
| [16 — Preserve uncertain refunds when original-sale recovery fails](closed/16-preserve-uncertain-refund-recovery.md) | `ready-for-agent` at closure | Closed | None |
| [17 — Deliver the Restaurant bridge with the reviewed addon release](ready-for-agent/17-deliver-restaurant-bridge.md) | `ready-for-agent` | Open | None |
| [18 — Isolate internal payment records by allowed company](ready-for-agent/18-isolate-internal-payment-records.md) | `ready-for-agent` | Open | None |

## Architecture triage — 2026-09-25

Tickets 13–15 were approved as independent architecture work and are now
closed. Their design decisions and verification evidence remain in their
archived tickets.

## Final audit corrections — 2026-09-25

The owner approved tickets 16–18 and requested direct publication as
`ready-for-agent`. All three can start independently; suggested priority is
16, then 18, then 17, without introducing dependencies between them. Coordinate
overlapping tests during integration. Ticket 02's external clarification can
proceed in parallel and does not block these mocked corrections.

All three corrections block ticket 12. Before live acceptance, integrate their
reviewed implementations and record mocked install, upgrade and Restaurant
acceptance on the final combined revision, including the delivered artifact.

## Shared implementation contract

- The addon, tests, documentation and local deployment tooling belong to odoo-revolut. Hosting provisioning is complete for this scope; do not edit odoo-hosting or develop source on the server.
- Target Odoo Community 19.0.20260908. Use existing Odoo conventions and runtime facilities; a new framework or dependency requires approval.
- Every product ticket includes the persistence, server behavior, UI, tests and documentation needed to demonstrate its stated outcome. Ticket 02 is an external-contract verification slice; tickets 10–12 are delivery/acceptance slices. Tickets 13–15 are behavior-preserving architecture refactors of the implemented addon, each verified through its complete affected workflow.
- Support retail and restaurant, a configured terminal per payment method, server-managed secrets and manager-only refunds. Late successful payments finalize when the unchanged original order resumes, rather than through unattended background order finalization.
- Persist operations before external dispatch. Verify the underlying payment, never intent completion alone. Unknown outcomes remain unresolved; local timeouts, empty payment lists and missing IDs do not prove retry safety.
- Never expose credentials to POS or logs. All automated Merchant API calls are mocked; actual terminal testing belongs to the explicitly controlled acceptance session.
- Dependencies are gates, not a task ordering preference: 02 gates live acceptance, while provisional contracts allow mocked implementation. Shared code changes from independently ready tickets still require coordination and integration review.

Read the project instructions, API validation report and development-environment document before implementing. Current documentation and official source take precedence over stale assumptions; record provider ambiguities rather than silently choosing financial behavior.

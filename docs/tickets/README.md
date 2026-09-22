# Odoo–Revolut tickets

Approved implementation breakdown for the Odoo–Revolut addon. Source: the three project tickets pasted into the planning conversation and the subsequently approved implementation plan. No tracker issue URLs were supplied, so no parent issue is invented or modified.

## Status folders

- **Ready to implement:** all prerequisite tickets are closed; status `ready-for-agent`.
- **In implementation:** work has started; status `in-implementation`.
- **Blocked:** prerequisite tickets or explicitly recorded external prerequisites remain outstanding; status `blocked`.
- **Closed:** acceptance criteria have been demonstrated and evidence recorded; status `closed`.

Initially tickets 01 and 02 are ready, 03–12 are blocked, and the other folders are empty. Placeholder files preserve empty folders in Git.

Numbers are stable identifiers, assigned in dependency order. They do not require a linear execution order: work any ticket whose blockers are all closed. Move its existing file to the appropriate folder and update its Status and Category; do not renumber, duplicate or erase its dependency history. Record external blockers when discovered. On closure, record verification commands/results and promote newly unblocked tickets. Update the links below whenever files move.

## Branch workflow

Each ticket declares its local `codex/<ticket-number>-<slug>` work branch immediately below the title. All 12 branches were created from the same committed ticket baseline; blocked branches do not yet contain future prerequisite implementations.

Use `main` as the shared integration branch for this ticket set. Integrate reviewed, verified ticket work there, including its status update. Before starting a ticket, merge the latest integration branch into its assigned branch and confirm every declared blocker is closed and its implementation is present. Never treat branch existence as permission to skip blockers. Do not reset or overwrite a branch that already contains work.

Use separate worktrees for concurrent agents, within the project's designated worktree area. Keep each ticket's changes on its assigned branch. Resolve overlaps against the integration branch and run the affected tests before integration. These branches are local; publishing them to a remote is a separate action.

## Ticket directory

| Ticket | Category | Blocked by |
| --- | --- | --- |
| [01 — Configure and verify a Revolut payment method](ready-to-implement/01-configure-revolut-payment-method.md) | Ready to implement | None |
| [02 — Resolve the Revolut terminal contract and testing prerequisites](ready-to-implement/02-confirm-terminal-contract.md) | Ready to implement | None |
| [03 — Complete one verified Revolut terminal payment](blocked/03-verified-terminal-payment.md) | Blocked | 01 |
| [04 — Handle unsuccessful payments and safe retries](blocked/04-unsuccessful-payments-safe-retries.md) | Blocked | 03 |
| [05 — Recover payments after interruption or late success](blocked/05-recover-interrupted-payments.md) | Blocked | 04 |
| [06 — Resolve uncertain payments from a manager worklist](blocked/06-manager-reconciliation-worklist.md) | Blocked | 05 |
| [07 — Use Revolut with split tender and restaurant checkout](blocked/07-split-tender-restaurant-checkout.md) | Blocked | 05 |
| [08 — Issue and reconcile a full Revolut refund](blocked/08-full-revolut-refund.md) | Blocked | 05 |
| [09 — Issue partial refunds across original payment allocations](blocked/09-partial-allocated-refunds.md) | Blocked | 07, 08 |
| [10 — Install and upgrade a reviewed revision on staging](blocked/10-staging-install-upgrade.md) | Blocked | 03 |
| [11 — Verify the complete addon on the target Odoo version](blocked/11-target-version-acceptance.md) | Blocked | 06, 09, 10 |
| [12 — Validate real terminal payments and publish release evidence](blocked/12-live-terminal-release-evidence.md) | Blocked | 02, 11 |

## Shared implementation contract

- The addon, tests, documentation and local deployment tooling belong to odoo-revolut. Hosting provisioning is complete for this scope; do not edit odoo-hosting or develop source on the server.
- Target Odoo Community 19.0.20260908. Use existing Odoo conventions and runtime facilities; a new framework or dependency requires approval.
- Every product ticket includes the persistence, server behavior, UI, tests and documentation needed to demonstrate its stated outcome. Ticket 02 is an external-contract verification slice; tickets 10–12 are delivery/acceptance slices. No prefactoring is needed in this documentation-only repository.
- Support retail and restaurant, a configured terminal per payment method, server-managed secrets and manager-only refunds. Late successful payments finalize when the unchanged original order resumes, rather than through unattended background order finalization.
- Persist operations before external dispatch. Verify the underlying payment, never intent completion alone. Unknown outcomes remain unresolved; local timeouts, empty payment lists and missing IDs do not prove retry safety.
- Never expose credentials to POS or logs. All automated Merchant API calls are mocked; actual terminal testing belongs to the explicitly controlled acceptance session.
- Dependencies are gates, not a task ordering preference: 02 gates live acceptance, while provisional contracts allow mocked implementation. Shared code changes from independently ready tickets still require coordination and integration review.

Read the project instructions, API validation report and development-environment document before implementing. Current documentation and official source take precedence over stale assumptions; record provider ambiguities rather than silently choosing financial behavior.

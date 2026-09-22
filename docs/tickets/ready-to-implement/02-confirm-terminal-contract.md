# 02 — Resolve the Revolut terminal contract and testing prerequisites

**Work branch:** `codex/02-confirm-terminal-contract`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**Status:** ready-for-agent

**Category:** Ready to implement

## What to build

The team has an evidence-backed terminal integration contract and a confirmed route to controlled terminal testing, including retail and restaurant fulfilment behavior.

## Acceptance criteria

- [ ] Reconcile the terminal guide with the 2026-08-17 create-order field list, particularly channel and fulfilment_type. Record authoritative evidence for accepted retail and restaurant payloads; do not invent a retail fulfilment mapping.
- [ ] Confirm terminal-specific capture behavior, required location/mode/app version, and the supported sandbox or other controlled testing environment. Distinguish documented claims from observed behavior.
- [ ] Record documented idempotency guarantees and limits separately for order creation, terminal intent creation and refunds. Absence of a documented guarantee must not become an assumed safe replay.
- [ ] Confirm merchant access, a matching physical location and a Pay at Counter terminal are available for the later acceptance session. Record access readiness and responsible operator, never credential values.
- [ ] Any provider clarification or controlled probe records its date, source, outcome and limitations. Do not perform real financial operations as an incidental documentation check.
- [ ] Keep this ticket open if required provider answers or testing prerequisites remain unavailable; name the external dependency. Mocked development may proceed using explicitly provisional contracts.
- [ ] This is a verification slice: closure requires a reviewable contract and testing-readiness record, not product schema/API/UI changes.

## Blocked by

None (can start immediately).

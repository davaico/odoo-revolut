# 02 — Resolve the Revolut terminal contract and testing prerequisites

**Work branch:** `codex/02-confirm-terminal-contract`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**Status:** blocked

**Category:** Blocked

## What to build

The team has an evidence-backed terminal integration contract and a confirmed route to controlled terminal testing, including retail and restaurant fulfilment behavior.

## Acceptance criteria

- [ ] Reconcile the terminal guide with the 2026-08-17 create-order field list, particularly channel and fulfilment_type. Record authoritative evidence for accepted retail and restaurant payloads; do not invent a retail fulfilment mapping.
- [x] Confirm terminal-specific capture behavior, required location/mode/app version, and the supported sandbox or other controlled testing environment. Distinguish documented claims from observed behavior.
- [x] Record documented idempotency guarantees and limits separately for order creation, terminal intent creation and refunds. Absence of a documented guarantee must not become an assumed safe replay.
- [ ] Confirm merchant access, a matching physical location and a Pay at Counter terminal are available for the later acceptance session. Record access readiness and responsible operator, never credential values.
- [x] Any provider clarification or controlled probe records its date, source, outcome and limitations. Do not perform real financial operations as an incidental documentation check.
- [x] Keep this ticket open if required provider answers or testing prerequisites remain unavailable; name the external dependency. Mocked development may proceed using explicitly provisional contracts.
- [x] This is a verification slice: closure requires a reviewable contract and testing-readiness record, not product schema/API/UI changes.

## Blocked by

No ticket dependency. Closure is externally blocked by:

- authoritative Revolut clarification of the retail `fulfilment_type` value and
  the create-order schema discrepancy for `channel` and `fulfilment_type`;
- a project owner assigning a responsible acceptance operator and confirming
  sandbox Merchant access; and
- for later production acceptance, confirmation of a matching physical
  location and Revolut Terminal app 1.56+ in Pay at Counter mode.

## Evidence and current decision

The reviewable contract and readiness matrix are recorded in
[Revolut terminal contract and testing readiness](../../revolut-terminal-contract-2026-09-22.md).
The official guide documents restaurant values `eat_in` and `take_away`, but it
does not define a retail value while still calling `fulfilment_type` required.
The versioned create-order field list omits both `channel` and
`fulfilment_type`, although the payment-intent reference requires
`channel: "pos"`. No provider clarification or authenticated probe was
available to resolve that contradiction, so no retail mapping is selected.

The same guide now documents a sandbox virtual terminal and amount-driven
simulated outcomes. That is the controlled test route once sandbox Merchant
access and a responsible operator are available. No authenticated request,
terminal operation or financial operation was performed for this ticket.

Mocked development may continue against the explicitly provisional contract.
This ticket must not close, and live retail compatibility must not be claimed,
until the external dependencies above are recorded as resolved.

## Verification evidence

Documentation was reviewed on 2026-09-22 against the official Revolut terminal
guide and Merchant API reference pinned to `2026-08-17`. Repository checks:

```bash
git diff --check
python3 -m compileall -q addons
./scripts/test-addon
```

All commands passed on 2026-09-22. The full addon suite ran in the pinned Odoo
`19.0.20260908` container and exited successfully. Odoo emitted the existing
`websocket-client module is not installed` browser-helper warnings; this basic
suite does not run the optional browser acceptance tours. The addon code and
tests are unchanged by this verification-only slice.

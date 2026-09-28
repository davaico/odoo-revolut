# 02 — Resolve the Revolut terminal contract and testing prerequisites

**Work branch:** `codex/02-confirm-terminal-contract`

Before starting, confirm this ticket’s blockers are closed and merge the latest reviewed `main` into this branch. Verify it includes the completed blocker implementations; do not start from the initial branch snapshot alone. Use a separate worktree when another agent is working in this repository.

**State:** closed

**Triage:** ready-for-agent at closure

## What to build

The team has an evidence-backed terminal integration contract and a confirmed route to controlled terminal testing, including retail and restaurant fulfilment behavior.

## Acceptance criteria

- [x] Reconcile the terminal guide with the 2026-08-17 create-order field list, particularly channel and fulfilment_type. Record documented claims, observed runtime acceptance and the owner's interim retail decision separately; do not present the interim decision as provider-confirmed semantics.
- [x] Confirm terminal-specific capture behavior, required location/mode/app version, and the supported sandbox or other controlled testing environment. Distinguish documented claims from observed behavior.
- [x] Record documented idempotency guarantees and limits separately for order creation, terminal intent creation and refunds. Absence of a documented guarantee must not become an assumed safe replay.
- [x] Confirm Sandbox Merchant access, a physical Sandbox location and a responsible operator without recording credential values.
- [x] Record the documented production prerequisites and hand off physical-terminal configuration, production discovery and all financial acceptance to ticket 12 without executing them in this ticket.
- [x] Any provider clarification or controlled probe records its date, source, outcome and limitations. Do not perform real financial operations as an incidental documentation check.
- [x] Keep this ticket open if required provider answers or testing prerequisites remain unavailable; name the external dependency. Mocked development may proceed using explicitly provisional contracts.
- [x] This is a verification slice: closure requires a reviewable contract and testing-readiness record, not product schema/API/UI changes.

## Blocked by

No ticket dependency. There is no remaining Ticket 2 blocker.

Revolut API Support has been contacted about the Sandbox virtual-terminal
state-propagation defect described below. That response remains useful, but it
does not block the local contract record. Physical-terminal configuration,
production discovery and all real-money acceptance remain ticket 12 work and
require their own explicit authorization.

## Evidence and current decision

The reviewable contract, dated controlled probes and readiness matrix are
recorded in [Revolut terminal contract and testing readiness](../../revolut-terminal-contract-2026-09-22.md).

On 2026-09-28, responsible operator **Gary — tester** confirmed Sandbox
Merchant access and secure off-repository storage of the Sandbox secret. The
operator created a `physical` Sandbox location through the Merchant API and
discovered Revolut's fixed virtual terminal. Authenticated probes established:

- `eat_in` and `take_away` order payloads are accepted by the versioned API;
- omitting `fulfilment_type` is rejected because the service substitutes
  `SERVICE`, while the endpoint accepts only `EAT_IN` or `TAKE_AWAY`;
- omitting `channel` is accepted by order creation, but the terminal guide and
  create-intent prerequisites still require `channel: "pos"`, so the addon
  continues to send it; and
- the owner selects `eat_in` as the interim retail value until Revolut publishes
  a retail-specific rule. This is an explicit product decision backed by
  observed API acceptance, not a claim that Revolut defines retail as eat-in.

Two virtual-terminal probes using documented success amounts (`100` and `101`
minor GBP units) reproduced the same Sandbox defect. Each payment intent stayed
`pending`, while an underlying payment was created and reached `failed` with no
`decline_reason` or `bank_message`. `GET /api/orders/{order_id}/payments`
reliably exposed the failed payment even though the intent kept
`payment_id: null`. The Sandbox terminal list reported the virtual terminal
online but omitted its location and operation mode, and the Sandbox Merchant
**Devices** page failed to load. No real financial operation was performed.

No production API request, physical-terminal operation or financial test was
performed. Those activities are explicitly outside this verification slice and
are handed off to ticket 12.

## Verification evidence

Documentation was initially reviewed on 2026-09-22 against the official
Revolut terminal guide and Merchant API reference pinned to `2026-08-17`.
Authenticated, non-financial Sandbox probes were performed on 2026-09-28. No
credential value, full card detail or production financial operation is
recorded in the repository.

Repository checks for this evidence update:

```bash
git diff --check
python3 -m compileall -q addons
```

Both commands passed on 2026-09-28. The full addon suite was not rerun because
this verification slice changes documentation only; addon code and automated
tests are unchanged from the merged, reviewed `main` revision.

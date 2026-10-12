# 47 — Recover an unstarted Revolut tender after preparation failure and reload

**Work branch:** `codex/47-recover-unstarted-tender-after-reload`

**State:** open

**Triage:** needs-triage

**Reported:** 2026-10-12 during ticket 12 restricted-price acceptance on .18.11.

## Problem

An unstarted sale tender persisted as waiting after cart preparation rejected
a missing Tip Product. After the owner restored the product and reloaded the
POS, no Resume action was visible. Removing the tender via red X produced one
communication-failure popup. Later removal attempts did nothing visibly, even
after refresh. Turning Price Control back off did not restore removal.

The sale remains unpaid with an undeletable tender and no usable continuation.
Do not infer that an actual network failure occurred solely from the message.

## Evidence

- Staging .18.11, acceptance register 3, session 10, order 59 / 1022 /
  261-3-000022: one product at overridden unit price £0.02, total £0.02.
- Initial preparation error: “Configure a valid terminal tip product before
  Revolut payment.” Manager approval was not reached. After restoration,
  config 3 uses existing active shared Tips product 1; automatic terminal
  validation remains on. Why Tip Product became blank is not established.
- SQL at 09:35:27 and 09:40:19 UTC: tender 79 still waiting; zero payment
  attempts and zero cart authorizations for this order. Counts remain
  72 operations / 161 dispatch claims / 17 refunds. No new recorded dispatch.
- At 09:40:19 UTC Price Control is false, Tip Product 1, native Tips true.
  The owner reports another failed removal after turning Price Control off.
- Initial preparation and reloaded-line screenshots are recorded in the
  [acceptance checklist](../../testing/ticket-12-final-release-checklist.md).
  The red-X failures are owner reports; their popup screenshot was not captured.

## Local reproduction and limits

`node /tmp/ticket12-restored-unstarted-tender-repro.mjs` imports the actual
`revolut_payment_state.js`, restores a waiting line with empty UI state and no
financial references, mocks empty `revolut_find_payment` results, then calls
`screenCancel` twice, as used by the deletion path. Exit 1 is the reproduced
stuck-state signal: both removals false; one interrupted message; final status
retry; canDelete false; canResume false. The mock rejects financial RPCs.

This is a fresh local lifecycle reproduction, not a full native browser replay
or an Odoo integration test. Browser diagnostics were unavailable and no focused
Odoo test ran. Existing regression suites were not repeated. No fix, server
mutation or deployment was performed by the agent. The inline reproduction below preserves the temporary script. It still needs
conversion to a tracked regression at the appropriate native lifecycle seam.

### Durable local reproduction

Run from the repository root with Node. Exit 1 is the expected current red
signal; this invokes only local lifecycle code with mocked lookup results.

```bash
node --input-type=module <<'JS'
import { RevolutPaymentState, paymentActions, restorePaymentLine } from './addons/pos_revolut/static/src/app/revolut_payment_state.js';

const calls = [], errors = [];
const order = { uuid: 'fixture-order', state: 'draft', payment_ids: [] };
const line = {
  uuid: 'fixture-line', amount: 0.02, pos_order_id: order,
  payment_method_id: { use_payment_terminal: 'revolut' },
  payment_status: 'waiting', uiState: {}, transaction_id: false,
  payment_ref_no: false,
  getPaymentStatus() { return this.payment_status; },
  setPaymentStatus(value) { this.payment_status = value; },
};
order.payment_ids.push(line);
const state = new RevolutPaymentState({
  methodId: 7, sessionId: 10, currencyId: 1,
  adapter: {
    async call(method) {
      calls.push(method);
      if (method !== 'revolut_find_payment') throw new Error('Unexpected financial RPC');
      return false;
    },
    showError(payment, outcome) { errors.push(outcome); },
  },
});
restorePaymentLine(line);
const deletionResults = [];
for (let click = 0; click < 2; click++) {
  const actions = paymentActions(line);
  deletionResults.push(actions.canDelete || (actions.shouldCancelBeforeDelete &&
    await state.screenCancel(order, line, async () => { throw new Error('Unexpected payment resume'); }, () => {})));
}
const result = { deletionResults, errors, calls, status: line.payment_status,
  canDelete: paymentActions(line).canDelete, canResume: paymentActions(line).canResume };
console.log(JSON.stringify(result, null, 2));
if (!deletionResults.some(Boolean)) {
  console.error('REPRODUCED: restored waiting tender with no found operation remains undeletable; repeated interruption feedback is suppressed.');
  process.exitCode = 1;
}
JS
```

## Investigation boundaries

`restorePaymentLine` treats persisted waiting as potentially started;
`cancelPayment` maps an empty lookup to interrupted/false; repeated identical
messages are suppressed. These code paths reproduce the observed symptoms.
Unknown legacy waiting lines are deliberately protected by existing tests.
An empty lookup alone must not be reinterpreted as permission to delete,
resume or release possible financial exposure. Establish a durable, server-owned
proof of an unstarted preparation failure or another safe recovery contract.

## Acceptance criteria

- [ ] Reproduce preparation failure → native saved waiting tender → reload →
  removal/continuation through the real native POS path with mocked Merchant HTTP.
- [ ] Recover an authoritatively unstarted tender without provider dispatch,
  alternate-tender settlement of uncertain money, or force completion.
- [ ] Preserve the same order/tender authority as required by the chosen recovery
  contract; no new charge can occur without an explicit authorized start.
- [ ] Preserve unknown legacy, exposed, pending and verified payment protections;
  absent lookup evidence is not sufficient to unlock them.
- [ ] Show usable recovery or understandable persistent feedback on repeated
  actions rather than leaving an apparently inert red X.
- [ ] Verify the narrow affected lifecycle/native tests and continue ticket 12's
  manager-cart approval on the existing fixture after a reviewed deployed fix.

## Dependencies and external blockers

No implementation dependency is currently identified. Triage must choose the
safe recovery contract. Mocked/native Odoo validation requires an available
disposable runtime. Ticket 12's exact manager-approval scenario is blocked by
this issue; its completed regressions and owner-accepted return 1019 stay closed.

## Fixture preservation

Keep order 1022/tender 79 for recovery. No storage clearing, whole-order
cancellation, replacement sale/tender, direct SQL edits or staging process
fault injection. Gross live charge budget remains £0.06. Test Price Control
cleanup is confirmed; keep the restored Tip Product configured. Root cause
of the missing Tip Product can be investigated separately without recreating
this failure on financial staging records.

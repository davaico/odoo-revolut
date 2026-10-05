# Integration mission audit

The integration implements the original payment flow and the recorded scope extensions, but it is not ready to be declared complete. This audit found two defects affecting cancellation and repeated partial refunds. Physical acceptance and final deployment evidence also remain incomplete. Architecture cleanup should follow correction and regression coverage of these behaviors.

## Audit boundary

- Audited commit: `01718690f355081c635c959d99d1a4e65a61e75e`, addon `19.0.1.15.2`.
- Date: 5 October 2026. This is a whole-integration acceptance/code audit, not a commit-diff review or an exhaustive security certification.
- Baseline: the eight original requirements, the ninth repository requirement for installation and instructions, approved local tickets, `CONTEXT.md`, and accepted ADRs.
- Payment, refund, and scope/credential reviews were performed separately. The lead auditor independently reran both defect reproductions.
- An immutable `git archive` copy at `/tmp/revolut-audit-01718690` supplied the reviewed/tested source. The shared checkout changed during another agent's work; it was not used to silently change the audit baseline.
- No product code, ticket status, deployment, credential, or live financial record was changed by this audit. Automated Merchant calls are mocked; the Docker environment uses an internal network and the Merchant HTTP guard.

The active **T12 V2** work was inspected read-only. The audited commit already includes `7779c0e` and `0171869`, which correct shared-Merchant discovery scope and preserve known references in unmatched discovery. Those earlier issues are not reported again as current defects. Historical credential repair, reconciliation and deployment remain that agent's work; neither its in-progress statements nor historical counts establish final deployment acceptance.

## Defects

### D1 Cancellation during payment preparation can still dispatch a charge

**Priority P2. Requirement 5.** In `static/src/app/revolut_payment_state.js:355–371`, payment preparation is awaited without rechecking `owner.cancelDiscovery` before `revolut_start_payment`. The refund branch already performs that check after preparation at lines 348–350.

Reproduce by delaying `preparePayment`, requesting cancellation while preparation is pending, then resolving preparation successfully. The actual pinned state machine sends `revolut_start_payment` despite the cancellation. Cancellation at lines 514–518 waits for the request to finish, while the request at lines 441–442 waits for cancellation. The foreground timeout breaks this dependency after approximately 60 seconds, after which cancellation finally reaches the server.

Observed call sequence:

```text
After cancel during preparation:
revolut_find_payment, revolut_start_payment
After advancing the controlled clock past 60 seconds:
revolut_find_payment, revolut_start_payment,
revolut_mark_timeout, revolut_cancel_payment
```

The cashier's cancellation before financial dispatch should prevent that dispatch. Instead, the terminal can present an unwanted payment and the customer may complete it before cancellation is sent. This does not demonstrate duplicate charging or bypass of final-payment verification.

Evidence: `node /tmp/payment-cancel-preparation-repro.mjs` imports the actual pinned production state machine, uses deferred preparation and a controlled clock, and performs no HTTP. The ordinary 79 state-machine tests pass but do not cover cancellation during this preparation await. A fix should add a regression requiring zero start calls in this scenario and retain cancellation-versus-capture coverage. No fix was made during the audit.

### D2 Independent rounding can prevent the last partial return from completing

**Priority P2. Requirement 6.** `models/return_allocation.py:227–228` rounds each returned fraction of an original line separately, without conserving the rounding remainder across earlier returns.

For an untaxed Revolut-only sale of quantity 1 for EUR 12.34:

| Return | Quantity | Computed refund | Available source balance |
| --- | --- | --- | --- |
| First | 0.25 | EUR 3.09 | EUR 12.34 |
| Remaining | 0.75 | EUR 9.26 | EUR 9.25 |

The production calculation demands 1,235 minor units from a source containing 1,234. Source/component caps at lines 417–421 reject the larger amount. Refunding the remaining EUR 9.25 cannot settle the EUR 9.26 native return because final settlement requires exact tender equality at lines 659–660. `_return_original` at lines 60–65 prohibits changing the original price or discount, and an all-Revolut original has no cash allocation available for substitution.

Evidence: `python3 /tmp/revolut-refund-rounding-audit.py` executes the pinned production `_return_components` and `normalize_amount` method bodies with fake ORM record containers. It returns `[(309, 0), (926, 0)]`. The lead auditor independently reproduced this output and checked the reservation and settlement consequences in code. This is a production-method reproduction plus static tracing, **not a complete Odoo browser/database reproduction**.

The existing `test_repeated_partial_refunds_can_use_full_remaining_balance` in `tests/test_revolut_refund.py:1062` uses two exactly divisible halves of EUR 12.34. Ticket 09 explicitly requires repeated partial and remaining-balance refunds; ticket 24 retains fractional quantities. This is a supported-flow defect. Correction needs a conservation policy consistent with native return totals and regressions for both rounding directions, successive fractions, taxes and applicable cash rounding. No rounding policy was changed during this audit.

## Requirements and behavioral evidence

Paths in this section are relative to `addons/pos_revolut/`. Test references identify exercised scenarios or existing coverage; actual run results are recorded separately below. Presence of a test alone is not a pass.

| Requirement | Implementation trace | Behavioral evidence and verdict |
| --- | --- | --- |
| 1 Send the POS amount to the terminal | `models/cart_authorization.py` prepares a server-authorized cart/tender; `models/pos_payment_method.py:739` persists and dispatches the attempt; `revolut_payment_operation.py` normalizes minor units | Payment tests cover exact amounts/currency exponents, split allocation and changed-cart rejection. UI tests cover remaining Cash/Revolut tender and multiple card lines. Implemented. |
| 2 Customer pays on the terminal | `pos_payment_method.py` checks terminal eligibility and creates the terminal payment intent; the POS state machine waits for the server result | Mocked terminal dispatch and processing are covered. Earlier physical retail evidence exists in ticket 12. Target-device acceptance of the final combined candidate remains open. |
| 3 Monitor and verify final payment | `pos_payment_method.py` polls intent and underlying payment, checks identity/amount/currency; `payment_observation.py` fences competing observations; `terminal_tip.py` verifies report evidence | `test_completed_intent_with_failed_payment_is_not_success`, reference-mismatch, interruption and observation-concurrency tests cover rejection of insufficient evidence. Completion of an intent alone does not settle a sale. Implemented with report-availability acceptance still open. |
| 4 Automatically confirm only after success | `static/src/app/payment_revolut.js` integrates the native payment screen; `models/pos_order.py:416` validates settlement before native processing at line 562 | `test_ui.py` covers verified automatic checkout, split tender, multiple cards and reload recovery. Server configuration requires automatic terminal validation. Background cron verifies operations but does not finalize a browser-absent order; the unchanged POS order must resume. This boundary is recorded in the approved contract. |
| 5 Decline, failure, cancellation, timeout | Explicit operation/local states, guarded retry and persisted evidence in `revolut_payment_operation.py`, server cancellation/reconciliation, browser state machine | Existing tests cover these outcomes, late capture, lost responses and cancellation/capture races. **D1 is an uncovered preparation cancellation defect.** Uncertain attempts remain reserved rather than being treated as failed. |
| 6 Full and partial refunds | `revolut_refund.py` validates originals and persists claims before POST; `return_allocation.py` checks quantity, tender, source balances and final settlement | Tests cover completed full refunds, repeated partials, mixed tender, multiple originals, concurrency, duplicate submit, lost response and saved-return recovery. **D2 is an uncovered rounding defect.** Provider completion and native return completion are separately enforced. |
| 7 Store transaction references | Immutable operation/order/intent/payment IDs, idempotency keys and original refund linkage; native linking in `pos_order.py` and `ReturnAllocation.link_settled_refunds` | Immutability, reference reuse/mismatch, reload, late recovery and different-return rejection tests exist. References survive uncertain outcomes. Implemented. |
| 8 Keep credentials on the server | `merchant_credential.py` binds company authority; `pos_payment_method.py:615–678` resolves frozen server environment references and uses fixed hosts; report transport follows the same authority | Configuration-export exclusion, cashier read denial, foreign-authority denial, rotation, legacy attestation, redirect and browser canary checks cover the boundary. No credential exposure was identified in this review. This is not a repository-wide security certification. |
| 9 Install cleanly and document setup | Single `addons/pos_revolut` manifest, migrations, security/data files; `docs/installation.md`; pinned Docker test and delivery scripts | Fresh install/upgrade verification is recorded below. Earlier exact-archive retail and two-addon migration results are historical evidence, not reruns at this audit commit. Instructions exist; final operating guidance must incorporate remaining physical observations. |

## Scope drift assessment

**No unapproved feature expansion was identified in the reviewed ticket and ADR history.** The implementation is broader than the eight-item shorthand, but the additions have recorded approval:

| Area | Approval and relationship to the mission |
| --- | --- |
| Split tender and Restaurant | Original ticket plan and tickets 07/17; supported POS checkout variants. |
| Durable attempts, safe retries, reconciliation, bounded input | Original transaction-safety requirements and tickets 19–24; protect payment/refund correctness. |
| Server-authorized carts and terminal-selected tips | Tickets 26/27 and accepted ADR 0001. Tips are an approved extension; cart authority prevents client-controlled amounts from bypassing native pricing. |
| Company credentials and register grants | Tickets 28/35; authorization boundaries for shared POS sessions and original financial evidence. |
| External terminal refunds | Ticket 37; approved extension to reconcile refunds initiated outside Odoo. |
| Coalesced provider observations | Ticket 38; reduces competing read traffic while preserving authoritative state transitions. |
| Custom Revolut receipt removal | Ticket 36 supersedes the earlier receipt extension. Native Odoo documents and terminal reprinting remain; the removed custom PDF is not a missing core requirement. |
| Deployment/PDF tooling | Approved operational work supporting reproducible installation and native document use. |

Approval does not remove acceptance obligations. In particular, **every new authorized capture, including a zero-tip sale, waits for asynchronous report evidence**. That approved tip design adds a provider dependency to ordinary checkout and needs observation on the target terminal/account.

Tickets 31/32 are owner-declined work recorded as `wontfix`; this audit does not reopen them or treat their closure as proof that the deployment risks were eliminated.

## Unverified acceptance criteria

These are evidence gaps or explicit compatibility limits, separate from D1/D2:

1. **Final candidate deployed and reconciled.** Ticket 12's pinned checkpoint records staging `19.0.1.14.1` and a blocked later rollout. The other agent is actively repairing and reconciling discovery evidence. Its latest inspected message still requires final upgrade checks and staging deployment. The old count of 15 is historical, not the current count or proof of 15 pending refunds.
2. **Physical checkout on the final candidate.** Earlier retail, split and busy-terminal passes are useful but do not certify the newer combined cart/tip/refund/Restaurant release. Restaurant dine-in/takeaway and unchanged partially paid recovery still need recorded acceptance.
3. **Terminal tip reports.** Explicit zero/nonzero tips, report identity, units, delay and recovery need target-device evidence. ADR 0001 records report applicability as an inference requiring acceptance.
4. **Controlled unsuccessful and interrupted flows.** Remaining provider failure, decline-to-paid retry, processing/capture cancellation race, network/capture-to-persistence interruption and failed/interrupted refund recovery must be observed or recorded as unavailable controlled scenarios. Mocked coverage does not establish provider behavior.
5. **Native completion and test-money reconciliation.** Completed provider refunds are not proof of a completed native POS return, stock/accounting effects, or a receipt. The recovered existing return still requires its recorded native validation/receipt gate; no replacement refund is implied. Reconcile money by original source.
6. **Native PDF acceptance.** Ticket 34 retains an actual historical native invoice download/print check on staging. Earlier custom-PDF evidence does not satisfy it.
7. **Publication evidence.** Ticket 33 retains private preservation/custodianship/recovery requirements before open-source publication. This is not evidence of a leaked credential.
8. **D2 integration reproduction.** Add a complete Odoo regression before considering the rounding fix verified. The present audit proves the arithmetic and traces the blocking checks, but does not claim an end-to-end reproduction.

Two existing refund limits also need accurate operator guidance: missing-return recovery refuses tracked products when original lot details are unavailable; external refunds on a tipped original block further Odoo refunds because the external base/tip allocation is unknown. These conservative limits are not new findings of unsafe money movement.

## Verification performed

- POS state machine: `node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` on the archive — **79 passed**. Log: `/tmp/revolut-audit-node79.log`.
- Repository Python checks: `python3 -m unittest discover -s tests` — **43 run, 40 passed, 3 optional Docker checks skipped**. Log: `/tmp/revolut-audit-python-repo.log`. An initial archive-only invocation failed its Git-dependent extraction test because the archive has no `.git`; rerunning in the Git checkout passed. This was a test-environment issue, not a product defect.
- D1 actual state-machine reproduction — confirmed independently by reviewer and lead auditor; no provider HTTP.
- D2 production-method reproduction — confirmed independently by reviewer and lead auditor; no provider HTTP; full ORM/UI consequence remains statically traced.
- Pinned Odoo fresh install: **489 tests, zero failures/errors**, including server and native browser behavior. Command: `ODOO_REVOLUT_TEST_PROJECT=revolut-audit-01718690 scripts/test-addon --verify-install-upgrade` from the archive. The terminal interruption ended the controlling session but the install container completed; its recovered full log is `/tmp/revolut-audit-install-complete.log`. This establishes the install phase only, not a completed full install/upgrade invocation.
- Upgrade verification: **49 tests, zero failures/errors** after separately updating that isolated database and running the changed external-refund and consolidation checks (`TestExternalRefunds`, `TestExternalRefundConcurrency`, `TestRestaurantConsolidation`). Log: `/tmp/revolut-audit-upgrade.log`. The full 489-test suite was not rerun after upgrade.

No new physical tests, real charge/refund, deployment, or external agent message was performed by this audit. Existing live records were read as historical evidence and distinguished from this run.

## Recommended completion sequence

1. Correct D1 and D2 in focused changes with regressions for the reproduced behavior; retain immutable attempts, source caps and verified-only settlement.
2. Take the other agent's final refund-reconciliation result and exact release revision, then run affected combined acceptance and complete the open native/physical gates.
3. Freeze that accepted behavior before architecture cleanup. Survey ownership in `pos_payment_method.py`, HTTP policy shared by connection/JSON/report transports, and settlement rules spanning `pos_order.py`, `cart_authorization.py` and `return_allocation.py`. Similarity or file size alone is not evidence that code can safely be deleted.

No architecture change is proposed as a substitute for fixing or verifying these behaviors.

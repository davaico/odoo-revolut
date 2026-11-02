# Ticket 82 — Pre-payment setup and browser checks

Date: 2026-11-02. Work branch: `codex/82-live-test-checkpoint`, based on
reviewed `staging/18-enterprise` at `4330188446d96aca4f517522fd86165d24fa2254`.
Integration target: `staging/18-enterprise`. Live acceptance remains open.

## Candidate and environments

The owner requested automatic setup and non-financial checks, stopping before
card participation. They selected Davai as company/location, terminal
**Test Guzman** or **Davai**, and EUR if supported, with the previous GBP
restriction retained as a possibility. No collection/refund amount is approved.

- Production build **40905690**, branch `18.0` at `2814e8f6`, opens normally.
  Settings reports **Odoo 18.0+e (Enterprise Edition)** and database expiry
  **3 December 2026**. Restricted parameter inspection confirmed reason `trial`,
  expiry value `2026-12-03 10:43:31` and no `database.is_neutralized` row.
  POS Revolut is available but uninstalled on this older source.
- The empty Production trial company's name/currency were changed to
  **Davai / EUR** and verified after reload. No accounting or POS transaction
  was created. This confirms Odoo configuration, not Merchant EUR support.
- Staging build **41044597** reports the neutralized banner, installed addon
  **18.0.1.0.8**, and Odoo Enterprise 18. The initial browser checks used the
  runtime behind source `4330188`. Existing T80/T81 evidence keeps its original
  scope and source attribution.
- Correction `4a56e8ee18e27bd1214a645016750f70cf25ad62` was independently reviewed
  and pushed to `origin/staging/18-enterprise`. Odoo.sh subsequently reported
  that source successful on the same build, and the corrected public action was
  exercised in the hosted browser. Addon Git tree:
  `7538c06c385716864f9a9d302b1c453caf63e89a`.

No Enterprise registration, activation/subscription code, plan purchase,
expiry change, Production code deployment or PR merge was performed.

## Browser checks

| Check | Observation |
| --- | --- |
| Installation/version | Installed `.8` confirmed through developer-mode Module Info; Upgrade/Uninstall controls present. No reinstall needed. |
| Native register | Existing Clothes Shop session retained. Its methods were Card, Customer Account and Cash; automatic terminal validation was enabled and Revolut backend-user grants were empty. |
| Existing authorities | Only revoked Sandbox fixtures were present before the new keyless test. No usable Merchant authority was available. |
| Bank journal prerequisite | Selecting Terminal without a journal hides the native provider selector and shows an install-terminal hint. Selecting Bank exposes Integrate with → Revolut. This is native behavior, not an addon defect. |
| Revolut fields/help | Company, environment, location/terminal UUIDs, fulfilment, credential reference and Check Connection were visible. The form requests a reference, never a Merchant API key. |
| Invalid namespace | Save rejected `T82_INVALID_REFERENCE` with the required `ODOO_REVOLUT_SECRET_` namespace message. |
| Invalid location | Save rejected a non-UUID location with the explicit location/terminal UUID validation message. |
| Production access guard | A saved, unassigned, keyless Production fixture was blocked before credential resolution/HTTP. The initial generic RPC dialog exposed the presentation defect below. |
| Corrected guard dialog | After Staging deployment, the same archived fixture showed native **Invalid Operation** with the complete Production-access restriction, without opening technical details. |
| Scheduled actions | Both Revolut reconciliation jobs were installed and inactive. Each completed a manual browser invocation without an error; both remained inactive. This is a smoke check, not fresh pending-operation recovery or platform scheduling proof. |
| Cleanup | The new method was archived and its keyless Environment authority revoked. Neither was attached to a register. Existing session/history was preserved. |

The fixture used explicitly synthetic UUIDs and reference
`ODOO_REVOLUT_SECRET_T82_GUARD_ONLY`, with no API key. It created no payment or
refund attempt. No genuine Merchant credential was copied into Staging.

## Public error correction and native tests

Odoo serializes the custom `RevolutEnvironmentError` with its addon-specific
class name. The web client displayed a generic RPC error instead of the normal
Odoo user-error dialog. The restriction itself remained effective.

The correction catches only this exception at
`action_revolut_check_connection()` and raises native `UserError` with the same
message. Internal typed exceptions, the guard, credential binding and financial
dispatch/recovery behavior are unchanged.

- Red: the existing blocked-stage test failed in all five stage subcases when
  asserting the native serialized exception name; one selected method,
  five failures, zero errors, exit 1.
- Green: the complete `TestRevolutPaymentMethod` class passed: **16 tests,
  zero failures/errors**, exit 0. The regression retains its zero-HTTP assertion.
- Independent Standards and Spec reviews of `8886b8c...4a56e8e`: **0 / 0 findings**.
- AST syntax and whitespace checks passed. No static type checker is configured.

Native checks used pinned Odoo Community `18.0.20261015` image
`a138d2204f1249d295f99df82bd399706e7494e45d5a674b4e977ad8858b1c05`, synthetic
credentials, an internal Docker network and the Merchant HTTP guard. Disposable
focused-test resources were removed. Logs are retained locally as
`/tmp/t82-regression-red.log` and `/tmp/t82-regression-green.log`.

## Full regression invocation

One full `/pos_revolut` invocation used an immutable snapshot of the corrected
addon, the same pinned runtime and blocked Merchant HTTP. It was stopped at
the owner's explicit checkpoint request: **interrupted/incomplete**, exit 137,
`OOMKilled=false`, after 1,713.73 seconds. There is no aggregate pass.

Before interruption, the log recorded 797 test-start markers, two browser
failures, one browser error and nine skips (eight Chrome startup skips and the
optional `pos_hr` characterization). The observed red cases were:

- `TestRevolutVerifiedCheckout.test_cancelled_payment_then_minimal_unsent_allocation_reload`
  — browser script timeout.
- `TestRevolutVerifiedCheckout.test_declined_payment_can_retry_once_without_duplicate_charge`
  — WebSocket timeout error.
- `TestRevolutVerifiedCheckout.test_delayed_native_preparation_cannot_start_after_same_tender_recovery`
  — receipt-step timeout.

Shared-host pressure coincided with these results: available RAM reached
174,684 KiB, one-minute load reached 103.11 and full memory-pressure `avg10`
reached 39.63 percent. The test container had no OOM/swap event and peaked at
1,231,302,656 bytes. This does not establish the failures' root cause. No
timeout/assertion was changed, and no full or focused retry was started.

All 174 frozen addon files match `4a56e8e` byte for byte, with no missing/extra
paths. Own test containers, networks and volumes were removed and their absence
verified. Retained artifacts include the partial log, source inventory, command,
admission checks, resource observations, exact skipped/red cases and cleanup.
Local results do not establish hosted lifecycle or live payment acceptance.
Resolve the observed failures/skips before treating this candidate's release
validation as complete.

## Remaining setup gates

- The Revolut portal recognizes the owner's account but requires its passcode.
  The login was left for the owner to complete directly; no passcode or new key
  was requested in chat. Merchant EUR support and exact device/location UUIDs
  remain unverified. An approved usable Merchant credential source is required.
- The Odoo.sh web terminal remained at **Loading terminal session** after a
  bounded reload; the displayed SSH fallback timed out. The focused hosted
  shell test selection was therefore not rerun. Prior T80 worker/copy evidence
  remains historical; manual job smoke checks do not replace it.
- Browser access disconnected, then temporarily recovered. A manual Production
  backup was requested with comment **T82 before Revolut installation — Davai
  EUR, no payments**. The last observed status was **A backup operation is in
  progress**; completion/download/restoration were not verified. Browser access
  became unavailable again at the pause. No Production addon installation or
  code promotion was completed.
- Finish validation and the reviewed release path, then deliberately configure
  the Production authority, terminal method, bank journal, register, suitable
  untaxed tip product, authorized operator and reconciliation jobs. Do not
  promote synthetic test references or weaken Staging guards.
- Before any money moves, confirm supported currency, online terminal, operator,
  sale amount and partial/remaining refund amounts with the owner. Then verify
  underlying payment/refund finality and matching native orders/accounting.

## Paused checkpoint

The owner explicitly requested stopping and resuming later. No further tests,
deployment, registration, credential changes or financial operations should run
until that request is resumed. T82 remains open; PR #96 remains unmerged.

Artifacts are copied into ignored local
`build/ticket82-checkpoint-20261102/`, including `full-suite/pause-checkpoint.json`,
the partial full-suite log and browser screenshots. The original `/tmp` copies
also remain. Screenshots contain private build context and must not be published
as repository evidence. The code fix is already on `origin/staging/18-enterprise`;
this checkpoint documentation is committed locally for the next continuation.

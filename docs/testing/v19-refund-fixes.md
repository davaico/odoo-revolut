# Combined Odoo 19 refund fixes

Candidate: `codex/v19-refund-fixes`, addon `19.0.1.18.16`. Base and PR
target: production `19.0` at `440f1a8c89048e5c2170425a4684ed23cbb0e261`.

Only standalone V19 commits are selected: PR #87 (`904cc56`), #71
(`3964148`, `e114589`, `e21127b`, `17a6287`), and #74 (`f121796`,
`0c19616`). Cherry-pick messages retain the original source hashes. No V18
commit, V18 addon path, or divergent `main` history is included. The final
release commit assigns the combined version, corrects the description of
request metadata, and aligns the retained upgrade fixture with that version.

## Completed DEV verification — 2026-10-26

Tested code: `1e8afa26467d0452e1b56b3dcae9588bd5536d79`, addon
`19.0.1.18.16`, against base `440f1a8`. The subsequent evidence commit changes
only this report. All remaining DEV release gates passed; this candidate is
ready for merge on the evidence below. No merge or deployment was performed.

- Combined native payment/refund and browser run: **112 tests, 0 failures,
  0 errors**, exit 0. All nine selected browser tours reported success.
- Versioned upgrade rehearsal: **passed**, exit 0. Installed archived base
  `19.0.1.18.14`, seeded synthetic records, stopped the old process, updated to
  candidate `19.0.1.18.16`, then verified all **37 record snapshots** unchanged.
  Pending/unresolved refunds still reject recovery; verified waiting refunds
  recover onto the existing tender; repeat recovery is idempotent; four refund
  records remain. SQL confirms the installed candidate version.
- JavaScript tests rerun: **159 passed** (142 state, 14 checkout-refresh,
  3 allowance tests). Portable tooling tests: **23 passed**.
- Native combo pricing suite on the same code: **19 passed**, including the
  two red/green rounding regressions described below.
- Whitespace check passed. Previous Standards and Spec reviews of
  `440f1a8...f41b9bf` found no actionable issues; these were static reviews.
- No GitHub workflow runs or commit statuses were returned for the tested
  commit; merge readiness relies on the local DEV evidence recorded here.

The native runner verified Odoo `19.0.20260908`, browser transport and the
Merchant HTTP guard. Both runs used separate disposable Docker projects with
internal networks, fake credentials and mocked provider calls. Explicit unused
subnets avoided exhausted Docker default pools. Only their own resources were
removed afterward. No production access or physical-terminal acceptance is
claimed. This is targeted combined-release validation, not a rerun of every
addon test.

### Native/browser coverage and reproduction

Run `scripts/test-addon --test-tags` with the comma-separated selectors below:

```text
/pos_revolut:TestRevolutPayment
/pos_revolut:TestRevolutRefund
/pos_revolut:TestRevolutRefundRecoveryUi
/pos_revolut:TestRevolutVerifiedCheckout.test_cash_and_bank_still_checkout_without_revolut_dispatch
/pos_revolut:TestRevolutVerifiedCheckout.test_completed_refund_native_refresh_recovers_without_second_refund
/pos_revolut:TestRevolutVerifiedCheckout.test_two_completed_refunds_native_refresh_recovers_without_replay
/pos_revolut:TestRevolutVerifiedCheckout.test_pending_refund_recovers_from_saved_return_without_browser_state
/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_offline_loader_recovers_without_second_refund
/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_rejection_recovers_without_second_refund
/pos_revolut:TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_timeout_recovers_without_second_refund
```

The two manager recovery tours include a mixed return requiring explicit Cash
completion. The refresh/recovery fixtures assert original refund identities and
provider request counts, exercising recovery without duplicate financial dispatch.

### Upgrade reproduction and retained evidence

In a disposable database, install the `pos_revolut` tree archived from
`440f1a8`, execute the candidate's
`pos_revolut/tests/refund_recovery_upgrade_seed.py` in an Odoo shell, stop the
old process, update `pos_revolut` using the candidate tree, then execute
`pos_revolut/tests/refund_recovery_upgrade_verify.py` in a new Odoo shell.
Keep the Merchant HTTP guard enabled throughout. Never seed a deployment DB.
The run printed `REFUND_RECOVERY_UPGRADE_SEED_OK 37` and
`REFUND_RECOVERY_UPGRADE_VERIFY_OK 37`.

Local evidence retained for this run:

- `/tmp/v19-remaining-native.log` and `/tmp/v19-remaining-tags`;
  temporary runner `/tmp/v19-remaining-test` uses project
  `v19-remaining-checks`, internal subnet `10.245.188.0/24`.
- `/tmp/v19-upgrade-check-20261026/`: version, guard, install, seed, upgrade,
  verify, database-state and cleanup logs. Runner
  `/tmp/v19-upgrade-check.sh` used project `v19-upgrade-check`, internal subnet
  `10.245.189.0/24`.
- `/tmp/v19-js-direct.log`, `/tmp/v19-js-refresh.log`,
  `/tmp/v19-js-allowances.log`, `/tmp/v19-remaining-tooling.log`.

Earlier combined runs had no recoverable passing result; this completed run
supersedes that evidence gap. The first upgrade runner attempt omitted the
`odoo` executable from its shell invocation and exited 127. It was corrected
and the complete rehearsal rerun from a fresh database. The pre-existing
missing-access-rules warning for `pos.revolut.external.refund.evidence` appears
on both old installation and candidate update; the final upgrade has no errors
or tracebacks. No application changes were needed for these checks.

Source histories and earlier failures remain in
[ticket 71](ticket-71-refund-recovery.md) and
[ticket 74](ticket-74-refund-refresh.md).

## Combo rounding regression fix

The Odoo 19 configurator's `getSelectedComboItems()` enumerates numeric
combo/item keys by ID before `computeComboItems()` allocates the parent price.
The server instead iterated combo groups in their default `sequence, id` order.
Sort groups by ID so a display-sequence change cannot move the rounding cent
between tax rates or classify native prices as a restricted manual override.

Two native regressions persist selections in reversed display order for a
0.05 combo with equal bases and 20%/0% taxes. Odoo allocates 0.03/0.02,
producing a 0.06 total. Before the fix, the unrestricted cart rejected that
tender against a 0.05 authorized balance, and the restricted cart wrongly
required manager approval. Both fail before the fix and pass afterward.

Validation on the pinned Odoo 19 image: `TestRevolutCartPricing`, all 19 tests
passed (0 failures, 0 errors), including existing extra-selection and genuine
manual-override coverage. Run via `scripts/test-addon --test-tags
/pos_revolut:TestRevolutCartPricing`; a temporary Compose override supplied an
unused internal subnet because Docker's default pools were exhausted. Provider
HTTP stayed mocked and guarded. No configuration or credential change is
needed. The combined refund, browser and upgrade checks are now also complete, as
recorded above.

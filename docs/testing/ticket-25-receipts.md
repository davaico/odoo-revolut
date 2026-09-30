# Ticket 25: Historical payment and refund receipt verification

## Scope and revision

Verified locally on 2026-09-30 using Odoo Community package
`19.0.20260908`, Chrome `153.0.8010.52`, and the repository's guarded
`odoo-revolut-test:19.0.20260908-chrome153` image.

- Reviewed baseline: `fbab631eaf7595de7893b95bee99c1c83245bd9d`.
- Implementation: `daf0445`.
- Final reviewed and tested code: `57f6e16afa4c5dab8ac7158eb437d77919f59931`.
- Branch: `codex/25-download-historical-payment-refund-receipts`.
- Addon version: `19.0.1.8.0`, previously `19.0.1.7.7`.

This is an Odoo-generated PDF slice, not an accounting invoice, provider-original
receipt, or remote terminal-print implementation. The original checkout and
unrelated dirty files were preserved in a separate checkout. No staging change,
deployment, push, real charge, refund, or provider probe was performed.

At final status inspection, `origin/main` had advanced by eight commits to
`0c614fd`, including ticket 24's financial snapshot changes. They are not part
of this branch's reviewed/tested code revision. Before release, integrate the
branches and rerun the affected receipt, settlement, recovery and return tests;
these results are not combined ticket 24/25 acceptance evidence.

The staff workflow, upgrade instructions, legacy metadata labels, and manual
print/email procedure are in [installation guidance](../installation.md#download-payment-and-refund-receipts).

## Automated results

All Docker runs used compose project `odoo-revolut-ticket25`, an internal
network, disposable PostgreSQL, and `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`.
The image's Merchant HTTP guard was checked before acceptance. Provider calls
inside payment/refund fixtures were mocked; receipt retrieval requires no
provider call. Test counts below are Odoo's final result counts, not its
separate fixture/statistics counters.

Raw browser logs and failure screenshots were preserved locally in
`/tmp/ticket25-report-artifacts.tar` before removing the disposable containers
and volumes. Local `/tmp` evidence is temporary; this committed record retains
the reviewed revision, commands, results and limitations.

| Check | Result | Local log |
| --- | --- | --- |
| Initial public receipt API regression | Expected red: missing `revolut_receipt_options` | `/tmp/ticket25-red.log` |
| Focused report/access suite | 14 passed, including actual PDF extraction | `/tmp/ticket25-focused2.log` |
| Full fresh-install retail suite at final code revision | 243 tests; 1 timeout failure, 0 errors; all 22 receipt tests passed | `/tmp/ticket25-full-suite-recovered.log` |
| Module reload/upgrade: receipt suite plus isolated failed tour | 23 passed, 0 failures/errors | `/tmp/ticket25-upgrade.log` |
| Restaurant installation and bridge upgrade | Installed; 8 compatibility tests passed, 0 failures/errors | `/tmp/ticket25-restaurant-install.log`, `/tmp/ticket25-restaurant.log` |
| Pre-ticket baseline installation | Version `19.0.1.7.7` installed in a second disposable database | `/tmp/ticket25-baseline-install.log` |
| Baseline-to-ticket schema upgrade | `19.0.1.7.7` to `19.0.1.8.0`; all 22 receipt tests passed, 0 failures/errors | `/tmp/ticket25-baseline-upgrade.log` |
| Deployment tooling unit tests | 29 passed | `python3 -m unittest discover -s tests -v` |
| Native payment-state JavaScript regressions | Passed; Node reports one test file | `node --test addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` |
| Python compilation, JavaScript syntax, whitespace | Passed | `compileall`, `node --check`, `git diff --check` |

The full fresh-install run is **not recorded as wholly green**. Its single
failure was the existing
`TestRevolutVerifiedCheckout.test_cancel_racing_with_capture_preserves_successful_payment`
tour: the receipt screen did not appear within the existing 10-second step
limit while host memory and swap were heavily constrained. The isolated rerun
at the unchanged code revision passed, including verified payment persistence
and receipt-screen completion. Resource contention is the suspected cause,
not a proven root cause. No timeout was relaxed and no assertion was removed.

Restaurant-only context and browser tests were intentionally skipped in the
retail phase because `pos_restaurant` was absent; the subsequent 8-test
Restaurant phase exercised those contexts, table checkout, merge/transfer,
and POS startup with the bridge installed. Installed versions were checked:
`pos_revolut 19.0.1.8.0`, `pos_restaurant 19.0.1.0`, and
`pos_revolut_restaurant 19.0.1.0.0`.

Earlier exploratory runs contained fixture errors, an ambiguous full-refund
sale selector, and memory-constrained Chrome startup skips. These are not
acceptance evidence. The corrected selector identifies the original sale by
reference rather than amount; the final receipt runs had no browser skips.

## Exercised behavior

`TestRevolutReceipt` has 14 server/report tests; `TestRevolutReceiptUi` has
8 HTTP/browser tests. Both actual PDF bytes and extracted PDF text were
checked, rather than relying on HTML previews or report installation alone.

- Current checkout and week-old history after normal session closure, a new
  session, and fresh browser load; no customer or accounting invoice required.
- Legacy missing merchant snapshot and local verification time, without
  inventing provider/card metadata; future merchant snapshots and verification
  times remain immutable.
- Separate full and multiple partial refund documents, original payment
  retained, selected split tender amount rather than sale total, and explicit
  original-payment references.
- Cashier and manager retrieval under sale and active-company permissions;
  unauthenticated, non-POS, foreign/inactive-company, tampered identifiers,
  inconsistent evidence, and non-final attempts rejected through direct report
  and custom download entry points. No PDF attachments are created.
- POS current/history controls, individual document selection, administration
  order-form links, repeated real downloads, and an actionable render failure
  followed by successful retries. Non-final historical records have no
  completion-receipt option or button.
- Provider financial calls blocked during receipt retrieval; operation counts,
  write dates, verified evidence, closed sessions, and refund permissions
  unchanged by viewing, repeated downloads, or report failure.

The upgrade checks exercise schema/report/view installation and legacy-shaped
records with absent optional fields. They do not claim migration of a copy of
production transaction history.

## Reproduction

Use the pinned environment described in
[development environment](../development-environment.md). From the tested
worktree, the fresh-install run used:

```sh
docker compose --project-name odoo-revolut-ticket25 --file compose.yaml run --rm odoo \
  --database ticket25_full --stop-after-init --workers 0 --log-level info \
  --init pos_revolut --test-tags pos_revolut
```

The upgrade receipt selection is:

```sh
--update pos_revolut \
--test-tags /pos_revolut:TestRevolutReceipt,/pos_revolut:TestRevolutReceiptUi
```

For the isolated failure rerun, append
`/pos_revolut:TestRevolutVerifiedCheckout.test_cancel_racing_with_capture_preserves_successful_payment`
to that selection. Install `pos_restaurant` without tests, then run
`--update pos_revolut,pos_revolut_restaurant --test-tags pos_revolut_restaurant`.
Never point these disposable test commands at a real business database.

## Standards

Independent Standards review covered the baseline-to-implementation diff,
then the final test-selection/eligibility additions through `57f6e16`.
**0 actionable findings.** Existing Odoo report/download, Bootstrap and
FontAwesome conventions were retained; the shared financial-operation mixin's
existing verified-state guards were checked for duplicate-transition
regressions. No new general financial-operation access was granted.

## Spec

Independent Spec review checked the ticket against the same implementation
and final follow-up diff. **0 actionable code findings.** The initial review
identified missing explicit legacy/non-final POS browser evidence. Both were
added and exercised; the follow-up review confirmed those coverage gaps were
addressed with no scope expansion. This record supplies the revision,
fresh-install/upgrade results, operator documentation and unexecuted checks
required before local ticket closure.

## Unexecuted checks

Physical printer output, print cancellation, printer hardware failures,
manual email delivery, real terminal behavior, staging deployment and live
financial acceptance were not exercised. Downloaded PDFs are ordinary A4
documents; printing/emailing them occurs outside the payment integration.
Automated PDF checks do not establish physical printing success. No terminal
printer command, automatic email, public QR link or accounting document was
introduced. Existing human release/financial gates remain unchanged.

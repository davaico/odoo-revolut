# Ticket 36 — Retire standalone receipts and preserve native printing

Date: 2026-10-02. Branch: `codex/36-remove-custom-revolut-receipts`.
Baseline: fetched main `83a7b2484ee16adcacc16e336d1c6e53e8d5508d`, including
PDF deployment guards (34) and explicit register authorization (35).
Candidate addon: `19.0.1.12.0`. Implementation: `1cc330c`.
Latest documentation-only main `2587962` was integrated by `bb5bcdd` while
verification ran. The ticket-index conflict retained claimed ticket 36 and new
ticket 37; no runtime files changed. Tested addon subtree:
`2816de20d3eae1cfe8bcd49d268fa73bc0e46a1c`; tested scripts subtree:
`b541fa849ef3e88a247202b19f920198e40c217e`. Both match the implementation
and merged candidate. Final combined verification passed; results follow.

## Final results

| Check | Result | Evidence |
| --- | --- | --- |
| Full fresh install | 398 passed, zero failures/errors | `/tmp/ticket36-full.log` |
| Full upgrade | 398 passed, zero failures/errors | `/tmp/ticket36-full.log` |
| Restaurant bridge | 9 passed, zero failures/errors | `/tmp/ticket36-full.log` |
| Actual old-release upgrade + native PDF | Passed, all stored fixture fields preserved, retired interfaces absent, readable QWeb/native download PDFs | `/tmp/ticket36-upgrade-native.log` |
| Focused native/backend/access checks | All paths pass in final full suite; focused 49/51 then 4/5 and repaired last single test passed before full run | `/tmp/ticket36-focused2.log`, `/tmp/ticket36-native-ui.log`, `/tmp/ticket36-native-later.log` |
| Payment state JavaScript | 75 passed | `/tmp/ticket36-node-final.log` |
| Host deployment/PDF suite | 39 run, 36 passed, 3 renderer cases skipped on host | `/tmp/ticket36-python-final.log` |
| Pinned-image PDF preflight suite | All 7 passed, no skips | `/tmp/ticket36-pdf-runtime7.log` |
| Compilation/syntax/whitespace | Python compileall, JS check, bash syntax and Git diff checks pass | Local commands below |
| Independent Standards / Spec | 0 / 0 actionable findings | Review sections below |

Full verification command:

```bash
ODOO_REVOLUT_TEST_PROJECT=ticket36-full ./scripts/test-addon --verify-install-upgrade
./scripts/test-receipt-retirement-upgrade
python3 -m unittest discover -s tests
node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs
python3 -m compileall -q addons scripts tests
node --check addons/pos_revolut/static/tests/tours/pos_revolut_native_printing.js
bash -n scripts/test-receipt-retirement-upgrade
git diff --check
```

The actual PDF-preflight checks ran with `docker run --rm --network none`, the
repository mounted read-only, the pinned test image, and
`python3 -m unittest discover -s tests -p test_pdf_probe.py`. Chrome transport and
the outbound Merchant guard were checked by the full runner. No browser startup
skips occurred. Expected invalid/missing-report and fault-injection warnings
are negative-path evidence; all three final Odoo results have zero failures or
errors. Final closure changes only documentation and ticket links; runtime and
scripts subtree hashes remain the tested values above.

## Implementation

Removed the separate POS checkout/history controls, administration tab,
`pos.revolut.receipt` model, order receipt-options RPC/computed links, custom
report models/actions/templates and download controller. The pre-migration
removes obsolete report/view registrations before native order view validation.
A real upgrade initially reproduced the dangling `revolut_receipt_links` field
error; the pre-migration resolves it without deleting financial history.

The financial mixin retains stored legacy merchant snapshots and their write
protection, immutable verified timestamps and deployment blockers. New payment
and refund operations no longer capture receipt-only merchant identity. Native
POS tender references, base/tip allocations, recovery and reconciliation remain
under their existing financial and access controls. Native accounting and
terminal printing policies are unchanged. POS browsers must reload after the
reviewed offline upgrade to load the new asset bundle.

## Verification boundaries and initial failures

Ticket acceptance criteria supply the agreed native UI/RPC/report/upgrade
boundaries. Automated Merchant calls remain mocked or rejected; all databases
and HTTP services are disposable and have no external network route. Tests use
Odoo Community package `19.0.20260908` and the repository's pinned browser image.
There is no configured static typechecker; Python compilation, JavaScript syntax
checks and shell syntax checks cover the languages changed here.

- `/tmp/ticket36-upgrade-red.log`: exact currency return fixture corrected,
  then actual receipt-enabled upgrade failed on the obsolete inherited view.
- `/tmp/ticket36-upgrade-green.log`: pre-migration passes stored-history and
  retired-interface checks. Its shell-only PDF has missing HTTP assets; this
  earlier output is superseded by the normal-server check below.
- `/tmp/ticket36-focused.log`: forced native PDF rendering under Odoo's shared
  test cursor waited on its own HTTP assets; the disposable project was stopped.
  Native report HTML is now verified inside the shared-cursor suite; actual
  PDF rendering/downloads run against committed history in a normal server.
- `/tmp/ticket36-focused2.log`: 49 of 51 passed. Two invoice browser tests
  exposed a bound browser adapter observation and existing accounting ACLs.
  The adapter is observed at its final output boundary; native accounting
  methods remain real. Later invoice creation uses an accounting-authorized
  fixture manager; a separate native RPC proves ordinary cashier denial.
- `/tmp/ticket36-native-ui.log`: four of five passed. Later invoicing succeeded
  but native settlement relinking updated operation `write_date`. Only that
  explicit invoice-creation test permits this technical timestamp change;
  all financial values/verified timestamps remain strict. Receipt reprinting,
  existing invoice retrieval and denied invoicing retain full timestamp checks.
- `/tmp/ticket36-pdf-runtime.log`: an attempted all-file run inside the Odoo
  image had one unrelated deployment test error because the image lacks Git.
  Deployment tests pass on the host; all seven PDF runtime cases pass in the
  targeted image run. No skipped renderer cases are claimed as tested.

## Actual upgrade and native PDF evidence

`./scripts/test-receipt-retirement-upgrade` installs immutable receipt-enabled
baseline `83a7b24` in a disposable database. It seeds an eight-day-old verified
payment, partial refund, saved sale/return tenders, posted accounting invoice,
closed original session, legacy merchant evidence and a previously downloaded
customer PDF. After upgrade it compares every retained stored scalar field,
including original write dates and financial references, and the saved PDF's
checksum/raw bytes. Retired models/RPC/field/XML registrations are absent.

The runner then starts a separate normal Odoo HTTP process for report assets,
renders `account.account_invoices` to actual PDF and parses its reference,
product, amount and currency. It also authenticates with disposable local test
credentials and downloads the invoice twice through its native download action,
checking actual PDF bytes and extracted invoice reference/amount each time.
`/tmp/ticket36-upgrade-native.log` records `NATIVE_INVOICE_PDF_OK` and
`RECEIPT_RETIREMENT_VERIFY_OK`, with no renderer network-error fallback.

Inside HttpCase, native invoice actions use Odoo's documented test-mode HTML
fallback. Tours check the matching invoice article, customer, product and amount
through the authenticated native URL. Those browser tests are evidence of native
navigation and permissions; actual PDF evidence is the normal-server runner.

## Standards

Independent review of `/tmp/ticket36-review.patch` against main `83a7b24`:
zero documented violations and zero meaningful judgement-call smells. Retirement
and migration target the approved custom feature; financial guards and stored
history remain. Follow-up review of the browser observation/accounting-role
fixture corrections also reports zero findings.

## Spec

Independent review: zero actionable findings. Removed models/RPC/controllers/
reports/assets and pre-upgrade cleanup satisfy interface retirement. Stored
merchant JSON, financial history and saved documents remain; timestamp and
deployment guards remain. No automatic invoicing or terminal behavior changes.
Native printing and invoice paths retain existing permissions; separate actual
PDF verification avoids claiming HTML-only evidence as PDF success. Follow-up
permission/browser test correction review also reports zero findings. Final
commit-range review against main `2587962` confirms zero findings in either axis.

Total findings: Standards 0; Spec 0. No worst issue in either axis.

## Remaining human checks

Ticket 12 must test the final integrated/deployed release's native receipt on a
week-old saved non-invoiced sale, closed original session and fresh browser,
existing invoice printing and physical current/historical terminal printing.
Ticket 34 independently retains authorized staging native invoice PDF acceptance.
No physical printer, terminal/device, deployment or staging mutation was tested
or authorized by this local implementation. Prior ticket 25/34 evidence remains
historical; the superseded custom reports do not establish native acceptance.

## Self-evaluation

Overall: 4.6/5; no corrective implementation work remains.

| Axis | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 5 | Actual native PDF extraction/downloads, exact stored-field upgrade comparison, 398/398/9 clean Odoo results and independent reviews support the local claims. |
| Completeness | 5 | All local ticket criteria covered; native accounting denial, direct retired interfaces and shared financial guards tested, with human gates retained explicitly. |
| Clarity | 4 | The final results table makes success visible, but the failure chronology still needs reading to understand shared-cursor HTML versus normal-server PDF evidence. Keep later updates in the result table. |
| Actionability | 5 | Committed implementation, reproducible runners, exact tested subtree hashes, operator guidance and separate human acceptance instructions are available. |
| Conciseness | 4 | The audit retains several initial failures and log paths; keep the user handoff short and future operator evidence in tickets 12/34. |

Critical issues: none. Top improvement: preserve the concise result table for
future updates instead of expanding the chronology. Self-check: the user can
verify the local outcome and see exactly which physical/staging work remains.
Verdict: deliver the local implementation as-is.

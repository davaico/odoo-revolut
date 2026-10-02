# Ticket 36 — Retire standalone receipts and preserve native printing

Date: 2026-10-02. Branch: `codex/36-remove-custom-revolut-receipts`.
Baseline: fetched main `83a7b2484ee16adcacc16e336d1c6e53e8d5508d`, including
PDF deployment guards (34) and explicit register authorization (35).
Candidate addon: `19.0.1.12.0`. Final implementation revision and combined
suite results are recorded below after completion.

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
permission/browser test correction review also reports zero findings.

Total findings: Standards 0; Spec 0. No worst issue in either axis.

## Remaining human checks

Ticket 12 must test the final integrated/deployed release's native receipt on a
week-old saved non-invoiced sale, closed original session and fresh browser,
existing invoice printing and physical current/historical terminal printing.
Ticket 34 independently retains authorized staging native invoice PDF acceptance.
No physical printer, terminal/device, deployment or staging mutation was tested
or authorized by this local implementation. Prior ticket 25/34 evidence remains
historical; the superseded custom reports do not establish native acceptance.

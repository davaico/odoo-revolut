# Ticket 81 — Enterprise 18 release candidate

Work branch: `codex/81-release-validation`. Reviewed base and integration target:
`staging/18-enterprise` at `d5d13d3943c7eadff4a0bdd44d0d1bdc19e8fc49`.
Production PR target: `18.0`; never merge or push directly there in this ticket.

## Identity and scope

Frozen candidate: `f8abaa3fcab1f1261ab04cc92bdf1bdc6d03d9ea`, addon
`18.0.1.0.8`, addon Git tree `a6b87c19d9615ea07ff0b9dd86c82b4495f26e70`.
Exact addon archive SHA256:
`20e2200907fd2de02eef225dc962650eb41c7f09bfc6c8ce09a64860a0cc7b23`.
Release metadata corrects the manifest's obsolete Enterprise-verification text;
no payment runtime behavior changes in #81. Subsequent evidence/runbook changes
outside the addon preserve this tested tree.

Production base: `2814e8f6d24cccfa99fccbe0ea6e08c1bfb646b6`, version `.4`.
The corrected `.4` commit `ed82c90` is an ancestor of staging. Its former
`addons/pos_revolut` tree differs from production's root addon only in manifest
and store-description metadata/assets. The approved changes assembled above are
T76 environment guard (`.5`), T77 credential authority/storage/log redaction
(`.6`), T78 neutralization (`.7`), T79 configuration (`.8`), and T80/T84 fixtures.
No Community restoration commit is included.

A direct staging PR would reintroduce agent guidance, internal tickets and old
acceptance evidence removed from the production tree. Prepare an allowlisted
release projection on the production base: exact `pos_revolut/`, the two new
upgrade/neutralization runners, the cron host tests, CONTRIBUTING/SECURITY,
installation, upgrade, public lifecycle, validation and release instructions.
Retain this ticket and campaign evidence on Enterprise staging. Check projected
addon-tree equality and the full production diff before opening the PR.

## Hosted evidence applicability

Hosted build **41044597**, source `fdfa74596f2445e0a54a1206cb28a052386cda01`,
installed `.8`, Odoo `18.0+e` (Odoo `2982b5f`, Enterprise `631c5ab`), is the
accepted T80 lifecycle build. See [the detailed evidence](ticket-80-odoo-sh-staging.md).
It exercised populated first installation, runtime access boundaries, installed
copy cleanup, neutralized first install and payment/refund recovery, including
actual native cron-worker death/replacement with mocked HTTP. The separate
platform-managed restart command/scheduling limitation remains.

Between that hosted revision and the assembled candidate, models, views,
security, data, hooks and production POS assets are unchanged. Addon differences
are the manifest description, T84's test-only held-response correction/delayed
regression and T80's two standalone native-worker fixtures (executed on that
hosted build from hash-checked temporary files). T84's full-suite source
`fccfd12` differs from this candidate only in those two standalone files and
manifest prose. Neither standalone file is imported by `tests/__init__.py`.
There is no material production runtime difference requiring a new hosted
lifecycle run. This is an explicit byte-comparison assessment, not a claim that
`f8abaa3` itself was hosted. Reopen hosted validation for any later runtime change.

The reference project remains a test-only trial. No paid production activation
or client hosting follows from this release. Client build/version, configuration,
entitlement and bounded live acceptance belong to ticket 82.

## Validation

Current results: 146 JavaScript checks passed; 80 host tests passed with three
existing PDF dependency skips. Python compilation and whitespace checks pass.
No configured static type checker exists. No new executable feature or test seam
is introduced in this ticket, so no new TDD test is needed.

Fresh populated installation, same-candidate update, versioned `.4 -> .8` upgrade,
neutralized-before-install and final full-addon validation are in progress on
the frozen addon. Do not claim production readiness or open a ready PR until
these acceptance results are recorded.

Transient artifact root: `/tmp/ticket81-validation/`. Candidate and `.4` baseline
come from `git archive`, mounted read-only. Pinned derived image:
`sha256:a138d2204f1249d295f99df82bd399706e7494e45d5a674b4e977ad8858b1c05`,
Odoo Community `18.0.20261015`, repository-pinned PostgreSQL `16.14`, internal
network `10.237.181.0/24`, synthetic credentials, mocked provider traffic and
`ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1`. No real terminal or Merchant API is used.
Resource limits disable container swap (Odoo 3 GiB/4 CPUs, database 1.5 GiB/2 CPUs).
The initially exhausted shared host was reported to the owner; no Odoo test was
started until capacity was freed and the recorded admission check passed.

## Maintained Community impact

Production 18 and restored Community 18 (`4b8b5cd`) have identical addon tree
`b5a29021233889695d9bd6b391292461bdf7d4fb`, version `.4`. Neither Community
branch is modified by this work. Odoo 19 remains independently released at
`c2b7d40ea39d373a0ad9f9d4e11cd5bb9ddf1b7e`, version `19.0.1.18.16`.
Its T74 evidence covers `.14 -> .16`, 112 targeted native/browser checks, 159 JS
checks and 23 portable checks; its earlier failing full run remains historical.
No Odoo 19 Enterprise/Odoo.sh certification is in scope.

Both Community lines retain the same short held-response test race. Applicable
shared fixture corrections need selective backports plus each version's native
recovery tests and full-suite evidence before claiming the corrected fixture on
that line. T77 storage/logging and T79 UI changes need deliberate version-specific
adaptation if adopted; T76/T78 hosted/copy protections are not certified on the
unchanged Community branches. Do not merge the divergent branches wholesale.
These are explicit maintained-line follow-up gates, not evidence of equivalent
verification from this Enterprise 18 run.

## Activation and recovery handoff

[The public checklist](../releasing.md) covers release approval, backups/module
upgrade, correct company/register/terminal, credential source and retention,
configuration that is not automatically promoted, one small client payment/refund,
verified final outcomes, original-attempt recovery and cashier enablement only
after acceptance. Accepted earlier hardware limitations remain; unrelated historic
transactions and deferred ticket 83 are not reopened.

PR reference and independent Standards/Spec review: pending final validation.
Production remains unchanged.

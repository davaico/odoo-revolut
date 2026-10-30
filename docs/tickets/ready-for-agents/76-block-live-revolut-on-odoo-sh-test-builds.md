# 76 — Block real Revolut access on Odoo.sh test environments

**State:** open

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None (can start immediately).

**External blockers:** None for local implementation and mocked verification.

## What to build

Make Odoo.sh staging and development reject real Revolut access consistently
through checkout, refunds, connection checks and scheduled reconciliation.
Users see an understandable restriction instead of a misleading terminal error.
Existing supported self-hosted production and sandbox workflows continue to work.

Keep the policy at the existing server-side application/transport boundary,
including the separate connection-check path. Any small consolidation needed to
apply the same policy belongs in this slice; no broad prefactoring project is
required. The policy must work before any database-copy cleanup exists and must
not depend on an absent secret or a disabled cron as its only protection.

## Acceptance criteria

- [ ] Production Revolut HTTP is blocked before dispatch on staging/development
  for payment/refund creation, cancellation, status retrieval, connection checks
  and privileged payment/refund reconciliation.
- [ ] Unrecognised Odoo.sh stages do not implicitly enable real operations.
  Supported self-hosted operation without Odoo.sh stage metadata remains
  explicit and functional; absence alone does not identify Odoo.sh production.
- [ ] First installation after neutralization is protected even when valid-looking
  environment credentials exist. Browser input or ordinary configuration changes
  cannot bypass the server policy.
- [ ] Blocking preserves original operation identities and uncertain states;
  it does not invent success, release reservations for an unsafe retry or send
  a replacement financial request.
- [ ] Existing payment/refund/credential tests invoke real application methods
  with mocked HTTP and assert zero production dispatch for every blocked path.
  Allowed production/self-hosted and supported sandbox cases are also exercised
  with mocks, without contacting a real provider.
- [ ] Focused UI checks cover understandable restriction feedback without keys
  or sensitive provider content; operating documentation explains the policy.

## Verification evidence

Pending implementation. Record exact revision, focused test commands/results
and remaining limits. Coordinate edits to shared credential/request code with
ticket 77; shared files are not a dependency between these independently
verifiable slices.

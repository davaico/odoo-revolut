# 77 — Manage company credentials through Odoo

**State:** closed

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](../ready-for-agents/75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None (can start immediately).

**External blockers:** None for local implementation and mocked verification.

## What to build

Allow system administrators to configure and safely rotate company-specific
Revolut keys through Odoo. POS managers select authorised references without
reading secrets, and existing environment-variable deployments continue working.
Demonstrate the complete setup-to-payment-to-refund path with mocked provider
responses, including historical-operation recovery after configuration changes.

Extend the existing credential authority instead of creating a parallel account
system. Credentials remain bound to company and environment. Database storage
also places keys in production backups; masking is not encryption. Unrelated
customers use separate databases, while each database's system administrators
remain trusted across its companies.

## Acceptance criteria

- [x] Administrator-only forms support the database credential source and safe
  replacement/rotation; restricted model access protects reads, writes, exports
  and direct RPC access, not merely visible form fields.
- [x] POS managers can configure authorised references without obtaining keys;
  cashiers and POS-loaded browser data receive no secrets. Logs and error
  messages remain sanitised.
- [x] Connection checks, payment/refund preflight, dispatch, status retrieval
  and scheduled recovery use the configured source consistently. Environment-
  variable credentials remain supported without an automatic account fallback.
- [x] Rotation preserves immutable authority bindings and frozen references on
  pending payments and historical refunds. Missing/revoked historical keys
  produce an explicit safe failure without replacement financial operations.
- [x] Tests exercise at least two companies, multiple terminals and a user with
  access to both companies. Requests follow the bound company/terminal, and
  foreign identifiers cannot redirect credential selection.
- [x] Synthetic separate-installation fixtures demonstrate that credentials,
  accounts and terminals are not hard-coded to the initial customer.
- [x] Existing model/RPC and focused UI seams verify configuration, mocked
  payment/refund completion, full/partial refunds, rotation/recovery and rejected
  secret access. The resolver under test is not mocked away.
- [x] Upgrade fixtures preserve existing environment-backed authorities and
  financial history. Setup/rotation documentation covers both credential sources.

## Verification evidence

Implemented on `6fbea9d7a78e96a4684ef2679934c40079345f48` (`18.0.1.0.6`),
based on `bcc2f9395a931fae9f90e3d8979165ae2272e293` from `feat/v18_rev`.
Task branch: `codex/77-company-credentials`; local integration target:
`feat/v18_rev`.

[Verification record](../../testing/ticket-77-company-credentials.md) contains
exact commands, revisions, results and limits. Focused credential/model/RPC/UI
verification passed **29 tests**; the previous-revision environment-authority
upgrade passed; JavaScript passed **146 tests**; host tooling ran **75 tests**
with three PDF dependency skips. Standards and Spec reviews have zero outstanding
findings. SQL and RPC debug-log key exposure was reproduced and fixed.

The full addon run completed **811 cases: three failures, zero errors, one
optional `pos_hr` skip**. Its three existing checkout browser failures passed
unchanged on isolated reruns. Their cause remains unestablished and is retained
in [ticket 84](../needs-triage/84-investigate-checkout-browser-full-suite-failures.md).
This is not a green full-suite or hosted release claim. No hosted deployment,
live credential change or real financial operation was performed.

Do not deploy this as a standalone hosted release before the environment/copy
guards and release gates.

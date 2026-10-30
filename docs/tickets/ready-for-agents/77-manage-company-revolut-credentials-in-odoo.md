# 77 — Manage company credentials through Odoo

**State:** claimed

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

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

- [ ] Administrator-only forms support the database credential source and safe
  replacement/rotation; restricted model access protects reads, writes, exports
  and direct RPC access, not merely visible form fields.
- [ ] POS managers can configure authorised references without obtaining keys;
  cashiers and POS-loaded browser data receive no secrets. Logs and error
  messages remain sanitised.
- [ ] Connection checks, payment/refund preflight, dispatch, status retrieval
  and scheduled recovery use the configured source consistently. Environment-
  variable credentials remain supported without an automatic account fallback.
- [ ] Rotation preserves immutable authority bindings and frozen references on
  pending payments and historical refunds. Missing/revoked historical keys
  produce an explicit safe failure without replacement financial operations.
- [ ] Tests exercise at least two companies, multiple terminals and a user with
  access to both companies. Requests follow the bound company/terminal, and
  foreign identifiers cannot redirect credential selection.
- [ ] Synthetic separate-installation fixtures demonstrate that credentials,
  accounts and terminals are not hard-coded to the initial customer.
- [ ] Existing model/RPC and focused UI seams verify configuration, mocked
  payment/refund completion, full/partial refunds, rotation/recovery and rejected
  secret access. The resolver under test is not mocked away.
- [ ] Upgrade fixtures preserve existing environment-backed authorities and
  financial history. Setup/rotation documentation covers both credential sources.

## Verification evidence

Pending implementation. Record exact revision, test commands/results and limits.
This local slice can start independently of ticket 76; do not deploy it as a
standalone hosted release before the environment/copy guards and release gates.

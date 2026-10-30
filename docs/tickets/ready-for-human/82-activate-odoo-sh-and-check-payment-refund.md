# 82 — Activate production and verify one payment and refund

**State:** open

**Triage:** ready-for-human

**Work branch:** Validated release from `feat/v18_rev` through the reviewed PR
into `18.0`; that branch automatically deploys production.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](../ready-for-agents/75-adapt-revolut-to-odoo-sh.md)

**Blocked by:**
- [81 — Validate the release candidate and prepare the production PR](../ready-for-agents/81-prepare-odoo-sh-production-release-pr.md)

**External blockers:** Release approval for the concrete candidate, production
administrative access, the intended Revolut credentials/terminal and the owner's
participation in the physical payment/refund. Scope approval is not evidence
that a specific release has passed its gates.

## What to build

Activate the reviewed integration in production and verify the actual hosted
credential/terminal path with the agreed small payment and refund before opening
Revolut payments to cashiers. Keep this a bounded acceptance check, not another
full hardware campaign. The addon remains reusable across companies/terminals;
this live check verifies the initial deployment rather than narrowing support.

## Acceptance criteria

- [ ] Confirm release approval and the exact tested candidate, review deployment
  and recovery instructions, then promote only the reviewed PR into `18.0`.
  Verify the resulting build and installed addon version.
- [ ] Apply the required production configuration and appropriate Enterprise
  registration, verifying administrator permissions, company, merchant authority
  and terminal before enabling financial operations. Do not assume staging
  configuration was copied with the code.
- [ ] With the owner, select a small test amount and complete one real payment.
  Verify the underlying payment's successful final state and its matching Odoo
  transaction before treating the sale as paid.
- [ ] Refund that payment and verify the provider's final successful outcome
  and matching Odoo return/refund references. A submitted or processing refund
  is not a completed refund.
- [ ] If an outcome is uncertain, keep it explicitly unresolved, reconcile the
  original attempt and preserve identity; do not send a replacement payment or
  refund just to complete the checklist.
- [ ] Record restricted live evidence and a sanitised acceptance summary. Enable
  cashier use only after acceptance; if verification fails, follow the reviewed
  recovery procedure without deleting financial history or blindly replaying.
- [ ] Keep ordinary staging/development production API access blocked throughout.
  Do not repeat accepted hardware scenarios or operate on unrelated historical
  pending records.

## Verification evidence

Pending release and human-assisted live acceptance. Record the deployed revision,
owner participation and final outcomes; keep live identifiers and credentials
out of public tickets. This ticket is `ready-for-human` because physical-terminal
execution is required, independently of its blocking dependency.

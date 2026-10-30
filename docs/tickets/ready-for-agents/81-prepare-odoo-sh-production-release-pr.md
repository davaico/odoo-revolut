# 81 — Validate the release candidate and prepare the production PR

**State:** open

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; the production-ready PR targets `18.0` only
after the acceptance gates pass. Do not merge the PR or push directly to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

**Blocked by:**
- [79 — Clarify the Revolut configuration workflow](79-clarify-revolut-configuration-workflow.md)
- [80 — Install and verify the integration on Odoo.sh staging](80-verify-odoo-sh-staging-lifecycle.md)

**External blockers:** Repository access to publish the PR and staging access
if the assembled candidate differs from the previously validated hosted build.

## What to build

Assemble the tested changes into one identified production-ready candidate and
prepare a reviewable PR into the automatic-deployment branch. Provide evidence
and operational instructions sufficient to release without guessing which code
was tested or which configuration still needs to be applied in production.

## Acceptance criteria

- [ ] Record the exact assembled revision, addon version and staging build.
  Include the corrected `.4` baseline and all approved slices without unrelated
  changes. Revalidate material differences from earlier staged evidence.
- [ ] Exercise fresh installation and versioned upgrade on populated disposable
  data, preserving native business data, financial history and environment-backed
  installations. Use existing upgrade fixtures and mocked provider traffic.
- [ ] Relevant payment/refund, credential, environment, recovery and UI checks
  pass on the assembled candidate. Preserve success/decline/failure/cancellation/
  timeout/retry behavior, underlying-payment verification, authorized cart rules,
  full/partial refunds and affected Restaurant/split-tender/tip flows.
- [ ] Assess maintained Community 18/19 impact, coordinate applicable shared
  fixes and record version-specific evidence or explicit remaining release
  gates. Do not claim Odoo 19 compatibility from Odoo 18 tests alone or add
  Odoo 19 Enterprise/Odoo.sh certification to scope.
- [ ] Verify that the hosted lifecycle evidence covers the assembled candidate;
  no build status substitutes for exercised payment safety and copy behavior.
- [ ] Open a production-ready PR into `18.0` with payment-flow impact, test
  results/limitations, configuration and credential steps, module upgrade needs,
  and recovery instructions. Explain that staging configuration is not promoted
  automatically with code.
- [ ] Prepare the bounded production activation checklist: correct company,
  terminal and credentials, small payment/refund, verified final outcomes and
  cashier enablement only after acceptance. Preserve accepted earlier hardware
  limitations; do not reopen unrelated historical transactions.
- [ ] Leave production unchanged: no direct push, PR merge, database mutation
  or live financial operation as part of this ticket.

## Verification evidence

Pending release assembly. Record candidate identity, validation commands/results,
staging evidence and PR reference. The next ticket owns activation and live proof.

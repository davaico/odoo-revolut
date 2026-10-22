# 68 — Investigate an extra Revolut line after draft reload

**Work branch:** prospective `codex/68-v18-duplicate-line-reload` after triage.

**State:** open

**Triage:** needs-triage

**Base and integration target:** sanitized `feat/v18_rev`. Assess the maintained
Odoo 19 counterpart under ADR 0002 once the cause is known. Transplant reviewed
changes without merging the old private history.

## Observation

During Odoo 18 manual acceptance, a draft sale had a preceding terminal request
that was cancelled without capture. The operator subsequently used Choose
amount to create an unsent editable Revolut line, changed its amount to zero
and back, and refreshed the browser. The supplied screenshot shows two
Revolut lines instead of the preceding single line. One shows Payment request
pending and Send; the other has no visible status controls. Validate remains
unavailable and the order remains unpaid.

The operator explicitly confirmed that the extra line appeared on refresh
without clicking Choose amount or the ordinary Revolut method again. A later
single-line screenshot is after the operator removed the extra line with its
red cross; it is not evidence of automatic recovery.

Read-only database snapshots before and after this interval preserve all
payment operations, dispatch claims, refunds, native orders, product lines and
tenders. No new financial dispatch or capture is observed. The two visible
rows alone do not establish two persisted native tenders. Original screenshots,
exact identities and live evidence stay in restricted private acceptance storage;
never copy them into publishable history.

## Reproduction status

One operator-observed occurrence; no deterministic mocked reproduction or root
cause established. Preserve the preceding cancellation and unsent allocation
sequence when building the initial disposable browser regression. Use mocked
Merchant responses only; do not reproduce by sending new live requests.

## Acceptance criteria

- Reproduce and minimise the extra-line restoration with the native browser
  model/sync path and mocked provider responses.
- Capture each visible line's UUID, native identity and state around reload to
  distinguish retained cancelled history from an extra client or server row.
- Restore the expected pending allocation exactly once without losing original
  operation history or introducing financial redispatch.
- Cover the preceding cancellation, unsent amount edits, reload and removal
  sequence at the real failing seam before implementing a correction.
- Verify relevant Odoo 18 behavior and assess Odoo 19 parity deliberately.

## Dependencies and boundaries

Triage and an unattended failing reproduction are required before selecting a
fix. Keep the existing manual-acceptance runtime and protected records intact.
This report authorizes no deployment, live charge, refund or history deletion.
The unsent-draft reload acceptance subcase remains open.

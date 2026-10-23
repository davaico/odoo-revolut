# 70 — Recover a completed refund whose existing tender is not yet projected

**Work branch:** prospective `codex/70-v18-verified-refund-return-recovery` after triage.

**State:** open

**Category:** bug

**Triage:** needs-triage

**Base and integration target:** latest sanitized `feat/v18_rev`. Assess the
maintained Odoo 19 counterpart under ADR 0002. Do not merge old private ancestry.

## Observation

A POS-origin card refund is issued once against a saved draft return. The card
provider initially reports processing. The native return and its matching
negative Revolut tender already exist, while the tender remains waiting with
no transaction/reference or final refund-operation linkage.

Later, backend Check status verifies that the same provider refund completed.
The refund form shows Completed and Native return awaiting validation. It also
offers Restore missing return even though its Odoo Return link finds the
existing draft by its original identity. Clicking recovery raises:

> The verified refund payment link does not match its original allocation.

Native completion is blocked; the financial reimbursement itself is complete.
Do not issue a replacement refund or use Force done.

The same failure is now reported for both a standalone card return and the
card portion of a mixed Cash/card return. Both issued card refunds are verified
completed. The mixed return still has its manual Cash portion outstanding;
recovery must preserve that balance for explicit completion in the register.
The operator supplied a completed-status screenshot and the same recovery
error for the mixed case. Only the standalone case has additionally been
reproduced by the agent with provider HTTP forbidden and rollback.

## Verification

The exact `action_recover_return()` path was reproduced against the preserved
original records with every provider HTTP call forbidden and the transaction
always rolled back. The command exits red with the same UserError. The guard
finds exactly one tender with matching UUID, method and negative amount; its
transaction reference is absent, so it fails comparison against the completed
refund reference. Final native refund links are unset and its status is waiting.

A subsequent read-only snapshot preserves every recorded payment operation,
financial dispatch, refund and native order/line/tender field from the verified
pre-recovery baseline. No provider request, additional refund or persistent
repair was made during reproduction. Full screenshots, identities and the
live-record reproduction helper remain in restricted private storage and must
not be copied into public history. A portable synthetic regression is still
needed before selecting or implementing a correction.

## Expected behavior and scope

The supported manager path should safely resume this existing return after
backend verification of its original refund, or expose a clear safe route to
perform the still-missing native projection. Reuse the original return/tender
and completed refund identities. Preserve verification and allocation checks;
genuinely conflicting amounts, ownership or populated references must still
be rejected. Do not treat missing native projection as permission for a fresh
financial request or a blind reference overwrite.

## Acceptance criteria

- Reproduce with mocked Merchant responses and native Odoo persistence:
  processing refund, saved waiting return tender, backend verification to
  completed, then manager return recovery.
- Distinguish an absent final native projection from contradictory financial
  evidence. Preserve exact original return/tender and refund identities.
- Allow the legitimate return to resume and complete once through normal POS
  validation, with no new provider order/refund/intent dispatch.
- Reject inconsistent method, amount, ownership, duplicate tender identity or
  conflicting existing references; do not weaken uncertain-outcome guards.
- Cover existing-draft and genuinely-missing-return paths, and repeat recovery
  without duplicate native orders, tenders, stock or accounting effects.
- Exercise standalone card and mixed Cash/card returns. A verified card
  refund must not automatically add, erase or mark paid the outstanding manual
  Cash portion; the existing return must remain available for that completion.
- Test the actual recovery/projection boundary on Odoo 18 and assess Odoo 19
  parity deliberately. State any remaining physical acceptance limitations.

## Dependencies and boundaries

Triage and a portable mocked failing regression precede correction selection.
No live database repair, deployment, new collection/refund or history deletion
is authorized by this report. Keep protected manual-acceptance records intact.
The existing refund remains financially completed; native validation is open.

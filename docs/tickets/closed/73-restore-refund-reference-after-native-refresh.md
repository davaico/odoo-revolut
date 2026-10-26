# 73 — Restore verified refund references after native refresh

**Work branch:** `feat/v18_rev`.

**State:** closed

**Triage:** needs-triage

**Base and integration target:** latest `feat/v18_rev`, not `main`.

## Problem

During ticket 63 refund completion, provider-verified returns could show a done
browser tender without its transaction reference. Native Validate then correctly
rejected the return: “The refund payment details do not match Revolut verification.”
The original refunds remain verified; this is a native projection/recovery
problem, not permission to replay the refund or weaken verification.

## Acceptance criteria

- [x] Reproduce reference loss through real native loading followed by Validate.
- [x] Recover the existing verified reference before validation without another
  financial operation or weakening server checks.
- [x] Preserve original refund/tender identities and correct base/tip amounts.
- [x] Pass focused regressions, review and no-money original-record retest.
- [x] Record exact candidate and remaining acceptance obligations in ticket 63.

## Dependencies

No prior ticket blocks investigation. Ticket 63 native refund completion and
session accounting depend on resolution. Odoo 19 parity impact must be assessed
separately; do not infer that version is tested.

## Verification

See [the refund continuation](../../testing/ticket-63-refund-completion-20261026.md).
Investigation and synthetic regressions are complete; no original financial
records were repaired directly and no existing refund was replayed.


Resolved locally on 18.0.1.0.4, commit `334c8a8`. Reviewed recovery preserves
backend verification and all refund identities. Original failing returns passed
normal Validate after update; related sessions posted balanced accounting.
142 state checks, three focused browser cases and standalone fresh-database
two-refund recovery passed. Combined-run Chrome timeout is retained in evidence.
Odoo 19 follow-up is ticket 74. Ticket 63 remains open for the last pending penny.

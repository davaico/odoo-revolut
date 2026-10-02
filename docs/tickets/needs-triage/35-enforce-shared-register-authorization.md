# 35 — Enforce explicit backend-user access to shared registers

**Work branch:** `codex/35-enforce-shared-register-authorization`

**State:** open

**Triage:** needs-triage

**Work type:** Remediation proposal

## What to build

Enforce the owner's selected per-register backend-user entitlement while
preserving shared employee login, explicitly granted colleague handoff and
safe reconciliation of existing payments. Ticket 30 investigated this boundary;
it did not implement permission changes. This proposal needs scope/sequence
triage before implementation.

## Source and scope

[Ticket 30 evidence](../../testing/ticket-30-shared-pos-session-access.md)
assesses main `9e1bdd7c64566ccec802b45f818bfbdf99ec4d0d` in pinned disposable
Odoo `19.0.20260908`. The owner selected “Explicit backend-user access per
register, with shared employee login” on 2026-10-02.

Separate source findings are confirmed against that policy:

- Input 7: `csf_07cbc859664310f0ebdc4d36` — POS user can trigger another session's Revolut terminal.
- Input 25: `csf_157cf1168e2a1b99dde24367` — A cashier can initiate terminal payments for another open POS session.

Native Odoo allows same-company backend POS users to share registers; employee
candidate lists do not implement backend-user grants. A separate actual native
register-denying rule blocks preparation/start but is bypassed by existing
find/poll/timeout/cancel. The retained characterization reproduces both facts
with mocked provider I/O. This is not evidence of deployed exploitation.

## Proposed acceptance criteria

- [ ] Administrator-owned backend-user grants per `pos.config`, protected from ordinary POS config write/create/copy/import; no blanket grant to all same-company cashiers during migration.
- [ ] Consistent server-owned register boundary before prepare/admit/start, checkout-state disclosure, find/poll/timeout/cancel, with native config/session/order access plus active company and POS role. A payment method shared across registers does not substitute for the original operation's register entitlement.
- [ ] Shared employee cashier switching and two separately granted backend colleagues can start, reload/coalesce and recover without an opener-only rule or creator-only operation rule.
- [ ] Same-company nonmembers, no-employee backend users, revoked users, actual native rule denials and cross-company/inactive-company callers cannot discover/control another register's operation; rejection occurs before provider I/O.
- [ ] Define explicit manager privileges and any audited override, and apply the equivalent boundary to refunds and manager financial actions. Do not silently exempt every manager from register entitlement.
- [ ] Historical recovery checks the frozen original register/session; revocation never unlocks financial reservations or authorizes replacement charges. Privileged cron still reconciles existing payments, including late success, without restoring revoked cashier access.
- [ ] Retain ticket 30's baseline reproduction and update its expectations with the remediation. Exercise all public entrypoints, grant mutation, method sharing, migration, authorized handoff, revocation, refunds and historical/closed-session recovery using mocked provider calls.
- [ ] Document explicit administrator provisioning/migration and verify affected install/upgrade and independent review before claiming either source finding fixed.

## Blocked by

Ticket 30's investigation and evidence must be integrated; this proposal also
requires maintainer scope/sequence triage. No implementation is authorized by
its `needs-triage` placement.

## Out of scope

No session-opener-only rule, browser-supplied employee identity as authentication,
credential changes, live terminal activity or generic Odoo access redesign.

## Release relationship

The selected register policy is not enforced until approved remediation passes.
Ticket 30's closure is an investigation result, not security-fix acceptance.
Preserve ticket 12's physical-terminal and financial acceptance gates.

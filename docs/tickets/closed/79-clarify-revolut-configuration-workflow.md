# 79 — Clarify the Revolut configuration workflow

**State:** closed

**Triage:** ready-for-agent

**Work branch:** `codex/79-configuration-workflow`. Historical starting base:
`feat/v18_rev` at `bb13748`. Enterprise integration target:
`staging/18-enterprise`, incorporating its routing commit `eff53ba` after the
full run. The owner authorized integration/push to staging on 2026-11-02;
Community `feat/v18_rev` and production `18.0` remain outside this task's scope.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](../ready-for-agents/75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None.

**Completed prerequisite:** [77 — Manage company credentials through Odoo](../closed/77-manage-company-revolut-credentials-in-odoo.md).

**External blockers:** Hosted access is useful for observing the reported form;
local UI validation and wording work need not wait for hosted acceptance.

## What to build

Give administrators and POS managers a clear, verified route from credential
setup to a correctly configured Revolut Payment Method. Correct actual field
labels/help and matching instructions, including company, environment, location,
terminal and credential selection, without redesigning the wider POS interface.

## Acceptance criteria

- [x] Inspect the current rendered Payment Method and credential forms before
  selecting wording; document the observed labeling issues and their correction.
- [x] Labels/help distinguish account authority, Revolut environment and terminal
  selection, and accurately explain which role can administer a secret versus
  configure a permitted reference.
- [x] A system administrator and a POS manager can follow the documented steps
  to configure an authorised company/terminal and complete a mocked connection
  check; restricted users cannot view secrets or select a foreign authority.
- [x] Focused native UI checks verify visibility, labels and the resulting
  saved configuration. User-facing errors/help do not reveal secret values.
- [x] Instructions cover database and environment-backed keys, safe rotation,
  company/terminal separation and relevant Odoo.sh restrictions. Supported UI
  languages are respected without adding a broad localisation project.
- [x] Use the domain glossary where relevant: Revolut payment receipt, POS
  sales receipt and accounting invoice are distinct documents.

## Verification evidence

Implemented in `ee49512` and test correction `0fd1ae7`, addon `18.0.1.0.8`.
[Verification evidence](../../testing/ticket-79-configuration-workflow.md) records
the observed missing native labels, corrected layout/help, source/role workflow,
French controls, exact saved configuration and mocked connection checks.

All focused credential and native configuration checks passed; all three
configuration cases also passed inside the full run. JavaScript: 146 passed.
Tooling: 75 run, three existing dependency skips. Standards/Spec reviews: zero
remaining findings each.

The full suite ran 815 cases with two existing-tour failures, zero errors and
two skips. Both failures and the browser-startup skip passed unchanged on
isolated reruns. This does not make the original full run green or establish
its cause. Follow-up [ticket 84](../closed/84-investigate-checkout-browser-full-suite-failures.md)
is now closed after a corrected candidate completed 816 cases with zero
failures/errors and only the optional skip. Ticket 79's focused workflow
criteria are complete; hosted lifecycle and production acceptance remain #80
and #82. No production push or live financial request was performed.

# 79 — Clarify the Revolut configuration workflow

**State:** open

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`; base implementation branches on its latest
reviewed revision and integrate back there. Do not push to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](75-adapt-revolut-to-odoo-sh.md)

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

- [ ] Inspect the current rendered Payment Method and credential forms before
  selecting wording; document the observed labeling issues and their correction.
- [ ] Labels/help distinguish account authority, Revolut environment and terminal
  selection, and accurately explain which role can administer a secret versus
  configure a permitted reference.
- [ ] A system administrator and a POS manager can follow the documented steps
  to configure an authorised company/terminal and complete a mocked connection
  check; restricted users cannot view secrets or select a foreign authority.
- [ ] Focused native UI checks verify visibility, labels and the resulting
  saved configuration. User-facing errors/help do not reveal secret values.
- [ ] Instructions cover database and environment-backed keys, safe rotation,
  company/terminal separation and relevant Odoo.sh restrictions. Supported UI
  languages are respected without adding a broad localisation project.
- [ ] Use the domain glossary where relevant: Revolut payment receipt, POS
  sales receipt and accounting invoice are distinct documents.

## Verification evidence

Pending implementation. Record the exact revision and configuration/UI checks.
This ticket need not wait for database-copy or hosted lifecycle validation.

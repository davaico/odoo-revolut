# Tickets

Internal tickets and live acceptance evidence remain in restricted records.
Ticket 63 publishes only a sanitized progress checklist and continuation brief;
physical-terminal acceptance remains open. Other private ticket statuses are
unchanged by this snapshot.

New public tickets use synthetic data and follow
[the tracker rules](../agents/issue-tracker.md) and
[triage labels](../agents/triage-labels.md). Keep original financial references,
private host details and credentials in restricted records.

## Open tickets

| Ticket | Category | Triage | State | Blocked by |
| --- | --- | --- | --- | --- |
| [63 — Perform controlled Odoo 18 terminal acceptance](ready-for-human/63-v18-terminal-acceptance.md) | Release gate | `ready-for-human` | Open | Native completed-refund recovery (#70), physical reload retest after #68 deployment, remaining acceptance checks and financial scope |
| [69 — Apply durable tender removal to Odoo 19](needs-triage/69-port-durable-tender-removal-to-odoo-19.md) | `bug` | `needs-triage` | Open | Native Odoo 19 failing reproduction before correction |
| [70 — Recover a completed refund whose existing tender is not yet projected](needs-triage/70-recover-verified-refund-with-unprojected-native-tender.md) | `bug` | `needs-triage` | Open | Triage and portable mocked recovery regression |

## Closed tickets

| Ticket | Resolution |
| --- | --- |
| [68 — Investigate an extra Revolut line after draft reload](closed/68-investigate-duplicate-revolut-line-after-reload.md) | Fixed on `feat/v18_rev`; 771 full-addon tests passed (1 optional test skipped). Odoo 19 follow-up: #69. |

# Tickets

Internal tickets and live acceptance evidence are preserved outside this public
snapshot. This tree makes no change to their private status or completion.
Physical-terminal acceptance remains pending.

New public tickets use synthetic data and follow
[the tracker rules](../agents/issue-tracker.md) and
[triage labels](../agents/triage-labels.md). Keep original financial references,
private host details and credentials in restricted records.

## Open tickets

| Ticket | Category | Triage | State | Blocked by |
| --- | --- | --- | --- | --- |
| [69 — Apply durable tender removal to Odoo 19](needs-triage/69-port-durable-tender-removal-to-odoo-19.md) | `bug` | `needs-triage` | Open | Native Odoo 19 failing reproduction before correction |
| [70 — Recover a completed refund whose existing tender is not yet projected](ready-for-agents/70-recover-verified-refund-with-unprojected-native-tender.md) | `bug` | `ready-for-agent` | Claimed | Red gate satisfied; implementation and validation in progress |

| [71 — Recover existing waiting refund tenders on Odoo 19](needs-triage/71-port-existing-waiting-refund-recovery-to-odoo-19.md) | `bug` | `needs-triage` | Open | Native Odoo 19 failing regression before correction |

## Closed tickets

| Ticket | Resolution |
| --- | --- |
| [68 — Investigate an extra Revolut line after draft reload](closed/68-investigate-duplicate-revolut-line-after-reload.md) | Fixed on `feat/v18_rev`; 771 full-addon tests passed (1 optional test skipped). Odoo 19 follow-up: #69. |

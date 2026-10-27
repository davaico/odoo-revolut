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
| [63 — Perform controlled Odoo 18 terminal acceptance](ready-for-human/63-v18-terminal-acceptance.md) | Release gate | `ready-for-human` | Open | Bounded recovery/reload checks passed; broader physical/parity release scope remains separate |
| [74 — Check Odoo 19 refund references after native refresh](needs-triage/74-check-odoo19-refund-reference-refresh.md) | `bug investigation` | `needs-triage` | Open | Native Odoo 19 reproduction; coordinate with #71 |

## Closed tickets

| Ticket | Resolution |
| --- | --- |
| [71 — Recover existing waiting refund tenders on Odoo 19](closed/71-port-existing-waiting-refund-recovery-to-odoo-19.md) | Completed and published on `codex/71-v19-refund-recovery`; 664 full cases, upgrade preservation and 0/0 reviews passed. Production rollout remains separate. |
| [73 — Restore verified refund references after native refresh](closed/73-restore-refund-reference-after-native-refresh.md) | Fixed on V18 18.0.1.0.4; original returns validated, balanced session posting. Odoo 19 follow-up: #74. |
| [68 — Investigate an extra Revolut line after draft reload](closed/68-investigate-duplicate-revolut-line-after-reload.md) | Fixed on `feat/v18_rev`; 771 full-addon tests passed (1 optional test skipped). Odoo 19 follow-up: #69. |
| [69 — Apply durable tender removal to Odoo 19](closed/69-port-durable-tender-removal-to-odoo-19.md) | Fixed on Odoo 19 `main` (`8269e90`); 687 full-suite tests reported with zero failures/errors, 65 focused checks and clean Standards/Spec reviews. |
| [70 — Recover a completed refund whose existing tender is not yet projected](closed/70-recover-verified-refund-with-unprojected-native-tender.md) | Fixed on `feat/v18_rev`; 778 full-addon tests, zero failures/errors (one optional skip). Odoo 19 follow-up: #71. |
| [72 — Avoid a stale return-recovery warning on POS reload](closed/72-consume-completed-return-resume-route.md) | Fixed on Odoo 18; nine native browser tests and 144 JavaScript checks passed; local no-money deployment/retest verified. |

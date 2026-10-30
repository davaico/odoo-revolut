# Tickets

Internal tickets and live acceptance evidence remain in restricted records.
Ticket 63's accepted Community 18 release campaign is closed; its deferred
refund/return/session obligation remains open in ticket 83. Ticket 74's combined
Odoo 19 release and upgrade gates passed. Other private ticket statuses are
unchanged by this review.

New public tickets use synthetic data and follow
[the tracker rules](../agents/issue-tracker.md) and
[triage labels](../agents/triage-labels.md). Keep original financial references,
private host details and credentials in restricted records.

## Open tickets

| Ticket | Category | Triage | State | Blocked by |
| --- | --- | --- | --- | --- |
| [75 — Adapt Revolut to Odoo.sh Enterprise 18](ready-for-agents/75-adapt-revolut-to-odoo-sh.md) | Deployment compatibility | `ready-for-agent` | Open | No local implementation blocker; hosted access/registration and staging evidence gate release; bounded live check follows production deployment |
| [78 — Make database copies safe](ready-for-agents/78-neutralize-revolut-database-copies.md) | Deployment compatibility | `ready-for-agent` | Open | None |
| [79 — Clarify the Revolut configuration workflow](ready-for-agents/79-clarify-revolut-configuration-workflow.md) | Configuration | `ready-for-agent` | Open | None |
| [80 — Install and verify the integration on Odoo.sh staging](ready-for-agents/80-verify-odoo-sh-staging-lifecycle.md) | Hosted acceptance | `ready-for-agent` | Open | #78; hosted access and registration information |
| [81 — Validate the release candidate and prepare the production PR](ready-for-agents/81-prepare-odoo-sh-production-release-pr.md) | Release preparation | `ready-for-agent` | Open | #79, #80; PR access |
| [82 — Activate production and verify one payment and refund](ready-for-human/82-activate-odoo-sh-and-check-payment-refund.md) | Live acceptance | `ready-for-human` | Open | #81; release approval and owner/terminal participation |
| [83 — Finish the deferred Odoo 18 refund, return and session](ready-for-human/83-finish-deferred-v18-refund-return-session.md) | Deferred acceptance follow-up | `ready-for-human` | Open | Original provider finality and authorised custodian; non-blocking for release |
| [84 — Investigate full-suite checkout browser failures](needs-triage/84-investigate-checkout-browser-full-suite-failures.md) | Test reliability | `needs-triage` | Open | None |

## Closed tickets

| Ticket | Resolution |
| --- | --- |
| [77 — Manage company credentials through Odoo](closed/77-manage-company-revolut-credentials-in-odoo.md) | Database/environment sources, immutable rotation and historical recovery implemented in `.6`; 29 focused tests and upgrade passed. Full-run browser follow-up: #84. |
| [76 — Block real Revolut access on Odoo.sh test environments](closed/76-block-live-revolut-on-odoo-sh-test-builds.md) | Runtime policy completed on Odoo 18 `d0d5225`; 796 full-addon tests (one optional skip), 146 JavaScript checks, and Standards/Spec reviews with zero findings. Hosted lifecycle remains in #80. |
| [63 — Perform controlled Odoo 18 terminal acceptance](closed/63-v18-terminal-acceptance.md) | Accepted Community 18 campaign complete; corrected `.4` READY report and PR #88 integration. Deferred original refund/native completion remains open in #83. |
| [74 — Restore Odoo 19 refund references after native refresh](closed/74-check-odoo19-refund-reference-refresh.md) | Combined `.16` candidate passed targeted native/browser, JS, tooling and versioned-upgrade gates; merged into `19.0` by PR #89. Earlier failing full-suite evidence remains historical. |
| [71 — Recover existing waiting refund tenders on Odoo 19](closed/71-port-existing-waiting-refund-recovery-to-odoo-19.md) | Completed and published on `codex/71-v19-refund-recovery`; 664 full cases, upgrade preservation and 0/0 reviews passed. Production rollout remains separate. |
| [73 — Restore verified refund references after native refresh](closed/73-restore-refund-reference-after-native-refresh.md) | Fixed on V18 18.0.1.0.4; original returns validated, balanced session posting. Odoo 19 follow-up: #74. |
| [68 — Investigate an extra Revolut line after draft reload](closed/68-investigate-duplicate-revolut-line-after-reload.md) | Fixed on `feat/v18_rev`; 771 full-addon tests passed (1 optional test skipped). Odoo 19 follow-up: #69. |
| [69 — Apply durable tender removal to Odoo 19](closed/69-port-durable-tender-removal-to-odoo-19.md) | Fixed on Odoo 19 `main` (`8269e90`); 687 full-suite tests reported with zero failures/errors, 65 focused checks and clean Standards/Spec reviews. |
| [70 — Recover a completed refund whose existing tender is not yet projected](closed/70-recover-verified-refund-with-unprojected-native-tender.md) | Fixed on `feat/v18_rev`; 778 full-addon tests, zero failures/errors (one optional skip). Odoo 19 follow-up: #71. |
| [72 — Avoid a stale return-recovery warning on POS reload](closed/72-consume-completed-return-resume-route.md) | Fixed on Odoo 18; nine native browser tests and 144 JavaScript checks passed; local no-money deployment/retest verified. |

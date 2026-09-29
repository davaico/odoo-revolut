# Triage labels

| Canonical role | Local label | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Maintainer evaluation required |
| `needs-info` | `needs-info` | Waiting for external information or access |
| `ready-for-agent` | `ready-for-agent` | Fully specified; dependency gates still apply |
| `ready-for-human` | `ready-for-human` | Requires human or physical-world execution |
| `wontfix` | `wontfix` | Will not be actioned |

When a skill names a canonical triage role, use the matching local label from
this table. Do not use dependency state as a substitute triage label.

The `ready-for-agent` label is filed in `docs/tickets/ready-for-agents/`.
See [issue-tracker.md](issue-tracker.md) for folder mapping and preservation.

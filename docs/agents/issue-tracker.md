# Issue tracker: Local Markdown

Issues and specifications live under `docs/tickets/`.

## Layout

Open tickets are organized by triage label:

- `needs-triage/`
- `needs-info/`
- `ready-for-agents/` for the canonical `ready-for-agent` label
- `ready-for-human/`
- `wontfix/`

Resolved tickets are archived under `closed/`. `README.md` is the
authoritative index.

The owner-selected `ready-for-agents/` folder uses the plural spelling; ticket
metadata keeps the canonical `ready-for-agent` label. Preserve this folder and
its tracked `.gitkeep` when moving or closing its last ticket.

## Ticket metadata

Each open ticket records:

- `State`: `open` or `claimed`
- `Triage`: one canonical label
- work branch
- acceptance criteria
- dependency and external blockers
- verification evidence when applicable

Dependencies are independent of triage. A `ready-for-agent` ticket is
actionable only when every listed blocker is closed.

## Operations

- Create new reports under `needs-triage/`.
- Move a ticket when its triage label changes and update the index.
- Claim work by setting `State: claimed`; keep the file in its triage folder.
- Close completed work by setting `State: closed`, moving it to `closed/`, and
  recording verification evidence. For `wontfix`, set `State: closed` and keep
  the ticket in `wontfix/` so the disposition remains visible.
- Append discussion under `## Comments` when persistent conversation history
  is required.
- Fetch a referenced ticket by reading its indexed file.

## Skill instructions

When a skill says to publish to the issue tracker, create a Markdown ticket in
`docs/tickets/needs-triage/` and add it to `docs/tickets/README.md`. When a
skill says to fetch a ticket, resolve its stable number through that index and
read the linked file.

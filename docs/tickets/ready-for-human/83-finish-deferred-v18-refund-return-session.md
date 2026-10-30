# 83 — Finish the deferred Odoo 18 refund, return and session

**State:** open

**Triage:** ready-for-human

**Work branch:** `feat/v18_rev` for documentation or any separately scoped fix.
This is an existing acceptance-record follow-up, not an Odoo.sh rollout task.

**Parent:** [63 — Perform controlled Odoo 18 terminal acceptance](../closed/63-v18-terminal-acceptance.md)

**Blocked by:** None among implementation tickets. This obligation was accepted
as non-blocking for release and does not block tickets 75–82.

**External blockers:** Provider finality for the original refund and access to
the preserved acceptance records through their authorised custodian. The last
recorded outcome was processing; no current provider recheck has been performed.

## What to finish

Preserve the remaining original small refund, native return and session until
the provider's final outcome is verified. Once a successful refund is established,
resume that same return and close/post its existing session with balanced native
accounting. Keep transaction identities in restricted evidence.

The owner accepted this delay as a deferred, non-blocking obligation on
2026-10-26. Moving it out of the completed acceptance campaign does not mark the
financial/native work complete or grant permission for a new live operation.

## Acceptance criteria

- [ ] The authorised operator identifies the original refund, return and session
  from restricted acceptance evidence, without copying live identifiers here.
- [ ] Verify the provider's final outcome using the applicable existing access
  and authorisation. Keep processing/unknown outcomes pending; if the refund
  failed, record that failure and the required disposition rather than forcing
  native completion.
- [ ] After verified success, reconcile the original operation and finish its
  existing return without issuing another refund or collecting more money.
- [ ] Close/post the same session and verify balanced native accounting with
  original references and amounts preserved.
- [ ] Record a sanitised result and evidence location, including any unresolved
  condition; close this ticket only when the obligation is completed or an
  explicit owner disposition supersedes it.

## Boundaries and evidence

No replacement refund, financial replay, forced completion, monitor or live
operation is authorised by this ticket's creation. The pending condition was
retained during the 2026-10-30 tracker review; no terminal/API call was made.
See the [acceptance handoff](../../testing/ticket-63-handoff.md) and the
[original owner disposition](../closed/63-v18-terminal-acceptance.md#owner-release-disposition--2026-10-26).

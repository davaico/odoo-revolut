# Saved native return requirement

The new refund start RPC requires a native saved draft and its selected negative
Revolut payment line before reserving any new financial attempt. The POS already
saves them automatically; this adds the same requirement at the server boundary.
No new register grants, dialogs or operator steps are introduced.

The reservation transaction acquires the existing session and return UUID locks,
then checks the saved order's state, session, register, company, currency and
canonical original-return contents. It checks the selected payment UUID, method,
amount, session and absence of completed or unrelated provider evidence. Return
totals use the established original-price, tax, rounding and terminal-tip rules.
Native order/payment/line mutation guards share the UUID lock, so a concurrent
edit must serialize with the reservation and cannot remove a claimed return.

A missing or changed draft is rejected before a refund reservation or Revolut
HTTP call. An existing attempt with the same frozen details remains retrievable
without requiring a replacement draft and without redispatch. Existing status,
manager recovery, verified allocation preservation and safe failed-line retry
continue to use their established paths.

## Verification

The direct API seam is the authenticated non-superuser Odoo `call_kw` refund
start RPC, with real native `sync_from_ui` persistence and mocked provider HTTP.
The first missing-draft regression failed against the previous implementation
because it reached provider dispatch; it passed after enforcing persistence.
The mismatch regression also failed before the matching checks were added.

The regressions cover missing drafts, missing or different payment UUIDs,
changed amounts, payment methods and return contents, cancelled returns, one
successful dispatch for a matching draft, and replay of a historical orphan
attempt with no new dispatch. Existing full/partial, split-tender, terminal-tip,
rounding, failed retry, concurrency, native settlement and recovery cases are
adapted to save drafts before new starts. Historical orphan fixtures explicitly
seed old operations rather than using a now-prohibited new unsaved start.

Final suite, review and deployment evidence will be recorded after completion.

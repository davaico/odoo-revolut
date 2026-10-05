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

### Final candidate — 2026-10-05

Candidate `19.0.1.15.1`, revision
`944e07ebc6beeb21eed0cd37c3f4cc68442dc6c6`, passed:

| Check | Result | Local evidence |
| --- | --- | --- |
| Full pinned Odoo install / upgrade | 478 / 478 tests; zero failures or errors | `/tmp/refund-saved-final.log` |
| Exact archive retail acceptance | 16 tests; zero failures or errors | `/tmp/refund-saved-artifact-retail.log` |
| Exact archive migration from deployed `30492a6` | Four groups of 16 tests, including repeated retail and installed Restaurant bridge migrations; zero failures or errors | `/tmp/refund-saved-artifact-migration.log` |
| POS payment lifecycle | 79 passed | `/tmp/refund-saved-node-final.log` |
| Repository Python checks | 43 run, 40 passed, 3 optional Docker checks skipped; actual Odoo/Docker acceptance ran separately above | `/tmp/refund-saved-scripts-final.log` |

The exact candidate archive SHA-256 is
`1df05106bcc3ac2c0b216685084382f6e01bf6f96a4f2096e15d787627997253`.
Python compilation, JavaScript syntax and `git diff --check` passed.
Independent Standards and Spec reviews found zero remaining findings against
merged main `2c7aa7c`. The Restaurant guard tour resolves native POS screens
inside its POS steps, preserving backend test asset loading after the addon
consolidation. This is a test-only compatibility correction.

### Guarded deployment stopped — 2026-10-05

The deployment attempt stopped at its initial financial preflight, before
backup, checkout quiescence or module upgrade. At 10:12–10:13 UTC, staging
contained **15 blocking external discovery records**: nine `unmatched_source`
and six `conflicting_original_authority`. The guard output's `=15` is a count,
not an evidence record ID. These records concern incomplete discovery or
original credential attribution; they do not establish 15 pending refunds.

Read-only inspection found the six referenced integration originals verified
but without a bound credential authority: sources 36, 17, 14, 11, 10 and 4.
Their company, environment and secret-reference comparisons agree with the
scanning credential, but that alone does not constitute administrator
attestation. Several unmatched list entries lack an original provider order.
No evidence was marked resolved and no authority was changed to bypass the
guard. Provider financial status remains a separate reconciliation question.

Staging remains on `19.0.1.14.1`; the additional server requirement is **not
deployed**. Resolve the discovery evidence through authoritative reconciliation
and the established credential-attestation workflow, then rerun the guarded
deployment against the reviewed merged revision. This attempt performed no
live Merchant request, new refund, receipt validation or terminal retest.
Evidence: `/tmp/refund-saved-deployment.log`. Ticket 12 remains open.

### Protection deployed — 2026-10-05

The earlier preflight stop is superseded by the completed
[discovery reconciliation and guarded rollout](refund-discovery-scope.md#guarded-rollout-completed--2026-10-05).
Staging runs **19.0.1.15.3**, exact source
`0bc84ecf2d8fb22a94b80465eaae8943c299f9e7`, including the saved matching
return/payment requirement. Final combined install and upgrade suites passed
490 tests each; the exact archive retail and migration checks also passed.

Live public `call_kw` checks as Administrator user 2 with superuser mode disabled
rejected an unsaved return and a missing selected payment line before any
provider HTTP call or refund creation. Each recorded zero HTTP calls; their
test transaction rolled back. Evidence: `/tmp/discovery-final-api-smoke.log`.
The recovered two-penny draft remains open for operator review and Validate;
no replacement refund or native receipt finalization was performed. The POS
continues to persist the draft automatically before a new refund, with no
additional cashier step.

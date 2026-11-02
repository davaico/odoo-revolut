# 81 — Validate the release candidate and prepare the production PR

**State:** closed

**Triage:** ready-for-agent

**Work branch:** `codex/81-release-validation`, based on reviewed
`staging/18-enterprise` at `d5d13d3943c7eadff4a0bdd44d0d1bdc19e8fc49`;
integration target: `staging/18-enterprise`. The production-ready PR targets
`18.0` only after acceptance gates pass. Do not merge the PR or push directly
to `18.0`.

**Parent:** [75 — Adapt Revolut to Odoo.sh Enterprise 18](../ready-for-agents/75-adapt-revolut-to-odoo-sh.md)

**Blocked by:** None; release preparation is complete.

**Completed prerequisites:**

- [79 — Clarify the Revolut configuration workflow](../closed/79-clarify-revolut-configuration-workflow.md).
- [80 — Install and verify the integration on Odoo.sh staging](../closed/80-verify-odoo-sh-staging-lifecycle.md).
- [84 — Investigate full-suite checkout browser failures](../closed/84-investigate-checkout-browser-full-suite-failures.md).

The corrected addon tree completed 816 full-suite cases with zero failures/errors,
only the optional `pos_hr` skip, and all ten affected browser cases executed.
Historical red runs retain their results. #84's local full-suite gate is satisfied;
#80's hosted acceptance is also complete; #81 retains its own release requirements.
Revalidate material changes to the assembled candidate before production readiness.

**Completed hosted prerequisite:** [80 — Install and verify the integration on Odoo.sh staging](../closed/80-verify-odoo-sh-staging-lifecycle.md).
Its final native cron-worker interruption/replacement proof passed on candidate
`fdfa745`, build 41044597, with scheduler selection/provider traffic mocked and
the platform-managed restart limitation retained. The reference project remains
test-only, with no paid Enterprise production activation or client hosting.

**External blockers:** None for release preparation. Client activation and live
acceptance remain separate in #82. The owner explicitly instructed not to merge.

## What to build

Assemble the tested changes into one identified production-ready candidate and
prepare a reviewable PR into the automatic-deployment branch. Provide evidence
and operational instructions sufficient to release without guessing which code
was tested or which configuration still needs to be applied in production.

## Acceptance criteria

- [x] Record the exact assembled revision, addon version and staging build.
  Include the corrected `.4` baseline and all approved slices without unrelated
  changes. Revalidate material differences from earlier staged evidence.
- [x] Exercise fresh installation and versioned upgrade on populated disposable
  data, preserving native business data, financial history and environment-backed
  installations. Use existing upgrade fixtures and mocked provider traffic.
- [x] Relevant payment/refund, credential, environment, recovery and UI checks
  pass on the assembled candidate. Preserve success/decline/failure/cancellation/
  timeout/retry behavior, underlying-payment verification, authorized cart rules,
  full/partial refunds and affected Restaurant/split-tender/tip flows.
- [x] Assess maintained Community 18/19 impact, coordinate applicable shared
  fixes and record version-specific evidence or explicit remaining release
  gates. Do not claim Odoo 19 compatibility from Odoo 18 tests alone or add
  Odoo 19 Enterprise/Odoo.sh certification to scope.
- [x] Verify that the hosted lifecycle evidence covers the assembled candidate;
  no build status substitutes for exercised payment safety and copy behavior.
- [x] Open a production-ready PR into `18.0` with payment-flow impact, test
  results/limitations, configuration and credential steps, module upgrade needs,
  and recovery instructions. Explain that staging configuration is not promoted
  automatically with code.
- [x] Prepare the bounded production activation checklist: correct company,
  terminal and credentials, small payment/refund, verified final outcomes and
  cashier enablement only after acceptance. Preserve accepted earlier hardware
  limitations; do not reopen unrelated historical transactions.
- [x] Leave production unchanged: no direct push, PR merge, database mutation
  or live financial operation as part of this ticket.

## Verification evidence

Completed 2026-11-02. [Production PR #95](https://github.com/davaico/odoo-revolut/pull/95)
is open, ready for review and **unmerged**, head
`53ab3aea02e4e81193a2671de978723a7215df0a`, targeting unchanged `18.0`
`2814e8f6d24cccfa99fccbe0ea6e08c1bfb646b6`. Frozen source `3f2ff4a`, addon
`18.0.1.0.8`, tree `57730fd0d5a81ea6a288081ac0eced63eb9e5b1b`.
[Full evidence](../../testing/ticket-81-release-candidate.md) records fresh/populated
installation, `.4 -> .8` history/environment-credential preservation, neutralized
first installation and hosted build 41044597 applicability.

The new full run reported 816 cases, zero failures/errors, with four Chrome
startup skips plus the optional HR skip. All four browser cases subsequently
executed unchanged and passed with no skips. T84's prior clean full prerequisite
remains attributed to its byte-equivalent runtime/loaded-test source; the new
resource-skipped full run is not relabelled clean. 146 JS and 80 host tests passed
(three optional host PDF skips). Independent Standards and Spec reviews: 0/0.

The bounded [client activation checklist](../../releasing.md) is prepared.
Production and live financial state are unchanged. The owner's final “Don't
merge” instruction leaves the PR and task branches unmerged; Enterprise
integration target remains `staging/18-enterprise`. #82 owns release approval,
client activation and live proof.

## Comments

> *This was generated by AI during triage.*

### 2026-11-02 — Preserve the full-suite release gate

Ticket #84 now has an agent brief and is `ready-for-agent`, still open. Its six
selected browser cases passed unchanged on both staging candidate `fdfa745`
and baseline `bcc2f93`. The full-suite failures did not reproduce in those
isolated runs; host swap headroom was insufficient for controlled full-suite
validation. #84 remains an explicit blocker until the failures are resolved
and the assembled candidate has clean full-suite evidence, including the
affected browser cases. No production-readiness claim follows from this triage.


> *This was generated by AI during triage.*

### 2026-11-02 — Full-suite prerequisite completed; hosted gate retained

#84 closed after native red/green proof and a clean 816-case full run on addon
source `fccfd12`, zero failures/errors and one optional `pos_hr` skip. All ten
affected browser cases succeeded, including those previously skipped after
Chrome connection failures. Its fixture correction retains the original
financial/native assertions and restoration deadline. [Evidence](../../testing/ticket-84-checkout-browser-triage.md).

The #84 prerequisite is cleared on this tested tree. #81 remains open and blocked
by #80; hosted evidence, release assembly/upgrade checks and PR preparation remain
required. No production-readiness, production-branch or live-financial action
follows from this local test result.


### 2026-11-02 — Release preparation complete

PR #95 contains the exact validated addon plus scoped public instructions/tools,
without restoring internal tracker/history files into the production diff.
Retained clean-full and current assembled-source evidence are separately
attributed; no assertion or timeout was weakened. The owner explicitly requested
that the PR not be merged. No production push, merge, database mutation or live
financial operation was performed.

# Ticket 74 — Odoo 19 native refund refresh

## Candidate boundary

Prepared on 2026-10-26 in the isolated `ticket74` checkout, detached at production
`19.0` commit `440f1a8c89048e5c2170425a4684ed23cbb0e261`. The patch was initially local and
uncommitted. During investigation, no production connection, live financial operation, push, deployment
or V18 addon edit was performed. The shared ticket registry alone was updated
to `bug` / `ready-for-agent` as requested.

The addon remains at repository-root `pos_revolut/`. Only two production
JavaScript files change; backend verification, schemas and provider requests
are unchanged. The manifest remains `19.0.1.18.14` during investigation. This
is a test candidate, not a publishable release: assign a unique higher version
when assembling the reviewed release, coordinated with #71 (`19.0.1.18.15`).

## Reproduction and correction

The new single-refund browser tour makes a synthetic sale and refund, forgets
browser storage, recovers the original saved return, and calls the real native
`pos.data.read("pos.payment", [id])`. It asserts that references disappeared
while `revolutCheckoutRestored` stayed true, then uses normal Validate.

On unchanged production code with only the test added, Odoo 19 failed to reach
the receipt after Validate (tour step 30/32). The saved references were erased
by native loading; this is not inferred from V18. The focused state test also
failed with `done !== retry` after the same missing-reference state.

The correction invalidates the restored flag when verified refund references
no longer match. Validate restores verified refund evidence after native
original-record reads. After the last shared refresh it projects all eligible
tenders together, so restoring a later refund cannot erase an earlier one.
It retains current-order/draft, tender membership/ownership, snapshot and
operation identity checks. Pending, failed and actively preparing refunds
retain the existing checkout block and are not restored by this new path.

The single-refund browser regression passed after the initial correction,
with one refund request, the original paid return and canonical references.
Subsequent guard tightening is covered by focused state/checkout tests; native
final-candidate checks are recorded below separately.

## Verification

- Pinned Odoo Community `19.0.20260908`, PostgreSQL `16.14`, Chrome `153`.
- Test image `sha256:4bbd14b8dd2b7aa3612d576d7d330ebe8378c6c4465f8862f0086119d165da7d`.
- Fake credentials, mocked provider requests, verified Merchant HTTP guard,
  dedicated internal network and disposable databases. No published ports.
- Baseline native single-refund regression: **1 failed, 0 errors**;
  `/tmp/ticket74-v19-red.log`.
- Initial corrected native single-refund regression: **1 passed, 0 errors**;
  `/tmp/ticket74-v19-green-single.log`.
- Final JavaScript suite: **158 passed**, including stale-reference recovery,
  multiple-tender final projection, pending/active protection, failed restoration,
  identity changes and ordinary sale/cash behavior. These use real state logic
  and the actual checkout method with mocked loading; they do not replace tours.
- Portable runner suite: **23 passed**; `/tmp/ticket74-runner-tests.log`.
- Independent code review: no actionable correctness findings. A potential
  active-refund flag mutation was found during review and avoided by preserving
  the early unresolved-payment block; its guard tests went red then green.
- Four-case browser group: **not passed**. Ordinary cash/bank browser execution
  hit a script timeout; the group was stopped rather than treated as evidence.
  `/tmp/ticket74-v19-focused.log` preserves the failure. Host memory was about
  14.8/15.1 GB used, swap 4.1/4.1 GB used. Resource pressure is a possible cause,
  not an established explanation for every timeout.
- Standalone final two-refund native test: **1 passed, 0 errors**, exit 0,
  in a fresh database; `/tmp/ticket74-v19-two.log`. Both original tender IDs,
  operation IDs, distinct references and once-only receipt references survive;
  both tenders are done, the return is paid, exactly two initial refund requests
  were made and recovery did not add another.
- Final tightened single-refund native test: **1 passed, 0 errors**;
  `/tmp/ticket74-test_completed_refund_native_refresh_recovers_without_second_refund.log`.
- Final pending-refund recovery and ordinary Cash/bank checkout: **each 1 passed,
  0 errors**, in separate Odoo processes; the serial command exited 0. Logs are
  `ticket74-test_pending_refund_recovers_from_saved_return_without_browser_state.log`
  and `ticket74-test_cash_and_bank_still_checkout_without_revolut_dispatch.log`.
- All logs are retained in ignored `build/ticket74/`, including the non-passing
  combined run. Disposable test containers, database volume and network were
  removed after verification; other environments were not changed.

## Local patch

The owner subsequently authorized pushing the fix branch on 2026-10-26.
Publication target: `origin/codex/74-v19-refund-refresh`, based directly on
production `440f1a8`. This authorization does not include a PR, a merge into
`19.0`, or deployment. The earlier no-push statements record the testing phase.

`build/ticket74/ticket74-v19-local.patch` contains the two production JavaScript
changes and four test files, including the new guard test. SHA-256:
`eb23b042cbf0e957b8eb0f2016118ed2725548e730d061da8829a9eb1c3bc944`.
`git apply --check` passed against a clean archive of production `440f1a8`.
The production branch ref still points to that commit. No commit was created.

## Reproduction commands

From this checkout:

```bash
node --test --test-isolation=none pos_revolut/static/tests/*.test.mjs
python3 -m unittest discover -s tests -v
ODOO_REVOLUT_TEST_PROJECT=ticket74-fresh ./scripts/test-addon \
  --test-tags '/pos_revolut:TestRevolutVerifiedCheckout.test_completed_refund_native_refresh_recovers_without_second_refund,/pos_revolut:TestRevolutVerifiedCheckout.test_two_completed_refunds_native_refresh_recovers_without_replay'
```

The standard runner initially could not allocate a Docker subnet. The actual
run used `docker compose -p ticket74-v19 -f compose.yaml -f
/tmp/ticket74-compose.yaml`, with a dedicated unused internal `10.247.74.0/24`
network. Do not prune or stop other environments to make tests pass.

## Release continuation

Ticket status reviewed after the owner's closure request: **#74 remains open**.
Implementation and targeted regression verification are complete in published
commit `f121796` on `codex/74-v19-refund-refresh`. The ticket also requires the
versioned upgrade rehearsal and coordinated release validation with #71, which
have not been completed. Closing the ticket would incorrectly mark those gates
complete. No PR, production merge or deployment is authorized by this update.

1. The final candidate passes single/two-refund refresh, pending recovery and
   ordinary Cash/bank browser checks; the refund tours also make a normal
   Revolut sale first. Repeat affected checks on any combined release candidate.
   Retain failing/timeout evidence; do not infer passes from installation.
2. Run the broader refund/payment regression suite and final review on the
   assembled release. #71's backend manager-recovery change does not exercise
   this native frontend refresh seam; test both together if both are selected.
3. Assign the release version without overwriting #71's version. Preserve public
   packaging, metadata, license and documentation. Do not merge divergent `main`
   or V18 history into production.
4. Rehearse production-version-to-candidate upgrade on disposable synthetic data,
   with provider access blocked; check retained pending/completed refund identities
   and configuration. The current same-version test update is not a completed
   versioned production upgrade rehearsal.
5. Obtain owner authorization before any push or deployment. Follow the existing
   upgrade guide: backups, planned worker shutdown, module update, restart and
   reopen POS browsers. Do not restore an old database across later financial
   activity without reconciling it first.

No physical-terminal or live-production acceptance is claimed.

## Follow-up verification — 2026-10-26

At the owner's request, reran the state checks and the entire addon suite in
a fresh disposable database, with the Merchant HTTP guard verified. The first
full run reports **660 tests, 2 failures, 0 errors**, exit 1. It is not a clean
full-suite result. See `build/ticket74/ticket74-full-verification.log`.

The two failures were real interaction regressions in the candidate, not
dismissed as timing: existing verified-refund checkout rejection and timeout
tours could not click Check status because an extra modal remained. Validate
was retrying a previous explicit `checkout_restore_failed`, displaying a new
restoration error and then the generic checkout block. Existing behavior
requires explicit Check status after that failure.

Added a focused regression that failed before correction, then extended the
existing unresolved-checkout guard to retain that explicit recovery flow.
Native refresh reference loss without a prior restoration error still receives
automatic repair. Successful Check status clears the failure marker normally.
No backend or provider behavior changed. Independent review found no actionable
issue with the added guard.

Final verification after this correction:

- **159 JavaScript checks passed**;
  `build/ticket74/ticket74-js-recheck-final.log`.
- **5 native browser tests passed, 0 failures/errors**, exit 0: both original
  single/two-refund refresh cases, verified-refund rejection, timeout and offline
  loader recovery. Original tests and deadlines were retained. The refund
  fixtures assert exact initial refund-request counts and no replay.
  `build/ticket74/ticket74-corrected-recovery.log`.
- Local patch regenerated with the SHA-256 recorded above; forward application
  check passed against clean production `440f1a8`; whitespace check passed.

The entire 660-test suite was not repeated after the final one-condition guard;
the affected browser tests and full JavaScript suite were rerun. Do not report
the initial full run as passing. Final combined-release and versioned upgrade
gates still apply. No push, PR, commit, deployment, production access or V18
addon edits occurred. Only this task's disposable test resources were used.

## Self-evaluation

Accuracy 4/5: native red/green and exact request-count checks support the fix;
broader release behavior remains unverified. Completeness 4/5: requested local
implementation and ready-for-agent brief are complete; versioned upgrade and
combined-release validation remain explicit follow-up gates. Clarity 4/5: the
handoff distinguishes production-base evidence from release approval, though
the detailed report is technical. Actionability 4/5: a checked patch, commands
and evidence are retained; another agent must assemble the final release.
Conciseness 4/5: detail is needed to retain both timeout and passing evidence.
Overall 4.0/5. Highest-value next steps are combined-release regressions and
versioned upgrade preservation. The user should be able to rely on the local
result without mistaking it for permission to publish or deploy.

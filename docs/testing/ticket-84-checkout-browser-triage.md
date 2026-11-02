# Ticket 84 — Checkout browser reproduction and triage

Investigated locally on 2026-11-02. Task branch:
`codex/84-checkout-browser-triage`. Reviewed base and integration target:
`staging/18-enterprise` at `fdfa74596f2445e0a54a1206cb28a052386cda01`.
This triage changes documentation only.

## Reproduction result

The five previously failing browser cases and the retail startup case skipped
in ticket 79 were executed unchanged against two immutable addon snapshots:

| Snapshot | Addon version | Result | Process duration, including installation |
| --- | --- | --- | --- |
| Candidate `fdfa74596f2445e0a54a1206cb28a052386cda01` | `18.0.1.0.8` | 6 passed, 0 failures/errors/skips, exit 0 | 115.01 s |
| Baseline `bcc2f9395a931fae9f90e3d8979165ae2272e293` | `18.0.1.0.5` | 6 passed, 0 failures/errors/skips, exit 0 | 115.01 s |

Each run's `odoo.tests.result` summary reports
`0 failed, 0 error(s) of 6 tests`. Six tour-success signals and no test skips
were checked in each log. The statistics logger separately reports 14; the
selected-case count here follows the six test methods and result summary.

Both snapshots exercised:

- `TestRevolutVerifiedCheckout.test_verified_card_first_rounds_only_the_remaining_cash`
- `TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_rejection_recovers_without_second_refund`
- `TestRevolutVerifiedCheckout.test_verified_saved_refund_checkout_timeout_recovers_without_second_refund`
- `TestRevolutRefundHistory.test_saved_return_recovers_unavailable_closed_original_without_duplicate_refund`
- `TestRevolutTakeoutReadinessUi.test_captured_tender_finishes_after_native_scheduling_correction`
- `TestRevolutRetailPosStarts.test_retail_pos_starts_with_addon_installed`

**Verification verdict:** historical full-suite failures are documented, but
the symptoms did not reproduce in these targeted runs. This does not establish
a cause, a credential/configuration regression, or a resolved full suite.

## Runtime and resource limits

Runs were serial, with separate fresh disposable databases and volumes, using
the same cached test image
`sha256:765f1fcec4895e23315cfe613a5bea7352741e078821692cc3ae96dea574c3e2`.
Package inspection confirmed Odoo Community `18.0.20261015`; Chrome reported
`153.0.8010.52`. PostgreSQL was the repository-pinned `16.14-bookworm` image.
No image was rebuilt or pulled. The repository runtime pins were unchanged.

The temporary Compose copy retained the internal network and synthetic
credential, used subnet `10.237.184.0/24`, and mounted the selected snapshot
read-only. `ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1` was enabled. The test-image
Merchant HTTP guard passed before execution; tests mocked provider HTTP.
No financial assertions, fixtures, application code or timeouts were changed.

Host memory, load and CPU/memory pressure were sampled every five seconds:

| Snapshot | Available memory, GiB | Free swap, KiB | One-minute load |
| --- | --- | --- | --- |
| Candidate | 1.79–3.53 | 124–28,744 | 2.16–4.22 |
| Baseline | 1.82–3.06 | 4–32,868 | 2.97–4.96 |

The host has approximately 14.7 GiB RAM and 4 GiB swap. Swap remained almost
exhausted. Other workloads were left untouched. These runs therefore do not
satisfy the ticket's controlled CPU/memory/swap-headroom acceptance criterion.
A full-suite rerun was not launched on this host during triage for that reason.
Resource observations alone do not explain the earlier failures.

## Commands and retained artifacts

`git archive` exported only `pos_revolut` from each recorded revision into
`/tmp/ticket84-triage/{candidate,baseline}`. The Compose copy was made from the
reviewed repository configuration, with an absolute build context and the
explicit internal subnet above. Build configuration was retained but not used.

The actual invocation for each snapshot was equivalent to:

```bash
source scripts/odoo-runtime
export ODOO_REVOLUT_ADDONS_DIR=/tmp/ticket84-triage/candidate
compose=(docker compose -p odoo-revolut-ticket84 -f /tmp/ticket84-triage/compose.yaml)
tags="$(cat /tmp/ticket84-triage/test-tags.txt)"
"${compose[@]}" down --volumes --remove-orphans
"${compose[@]}" run --rm --no-deps --entrypoint dpkg-query odoo \
  --show '--showformat=${Version}' odoo
"${compose[@]}" up --detach --wait db
"${compose[@]}" run --rm --no-deps odoo \
  --database odoo_revolut_tests --init pos_revolut --stop-after-init --workers 0 \
  --log-level warn --log-handler odoo.tests.result:INFO \
  --log-handler odoo.tests.stats:INFO --log-handler odoo.addons.pos_revolut:INFO \
  --test-tags "$tags"
"${compose[@]}" down --volumes --remove-orphans
```

The baseline invocation changed only the mounted snapshot to
`/tmp/ticket84-triage/baseline`; its database and volumes were recreated.
`test-tags.txt` contains the six case names above, each prefixed with
`/pos_revolut:` and joined with commas.

Transient artifacts under `/tmp/ticket84-triage/`: `candidate.log`,
`baseline.log`, each snapshot's `*-command.json`, `*-result.json`,
`*-resources.jsonl`, setup/cleanup logs, `compose.yaml`, and the temporary
`run-reproduction.py` orchestration script. The task's containers, volumes and
network were removed after the comparison. Snapshot directories and logs remain
for inspection; this document preserves the result if `/tmp` is cleared.

The existing `/tmp/ticket79-full-container.log` and
`/tmp/ticket79-full-exit` were also inspected. They confirm two failures out of
815 cases and exit 1: the historical-refund receipt step timed out after
10,000 ms, and the Takeout tour exceeded its overall script timeout. Retail
startup was skipped after a Chrome connection error. Ticket 77's original
logs were unavailable; its prior evidence remains in the linked ticket records.

## Triage disposition and remaining work

Category: **bug** (browser/full-suite test reliability). State:
**ready-for-agent**, with controlled-resource host availability still required
for final comparison and release evidence. No reporter clarification or live
account/terminal access is needed to execute the investigation brief.

Redundancy search covered checkout restoration (`revolut_checkout_state` and
`RevolutPaymentState`), recovery tours, saved-refund/history and Takeout browser
tests, and tickets 77–79's evidence. No completed investigation or established
fix was found. The repository has no `.out-of-scope/` rejection records.

The recovery tour's combined assertion still cannot identify which condition
failed. It waits three seconds for the held RPC response while restoration has
a five-second deadline. This is a diagnostic limitation, not proof of either
premature payment completion or an environment cause. Since it did not fail in
this comparison, no temporary diagnostic instrumentation was added.

The agent brief in ticket 84 defines the remaining investigation. Ticket 84
stays open and ticket 81 stays blocked until the full-suite failures are
resolved and the assembled candidate has clean full-suite evidence, including
execution of the affected browser cases. The prior red runs retain their
original results. This local Community-image comparison supplies no hosted
Enterprise/Odoo.sh acceptance evidence.

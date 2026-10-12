# Ticket 48 — Native Odoo tip rejection feedback

Base: `6a973d566f39eb7de0677a98fab3cc6fcaf4f57c` (`main`).
Branch: `codex/48-explain-odoo-tip-rejection`.
Runtime: pinned Odoo `19.0.20260908`, Chrome `153.0.8010.52`.
The inherited addon version is `19.0.1.18.11`; release numbering is left to
integration with the concurrently developed tickets 47 and 49.

## Change and financial boundary

Cart pricing checks the server-configured tip product identity before generic
product eligibility. The native Tips product is active but unavailable in POS;
it now receives the existing **Remove the Odoo-entered tip before using
terminal-selected tips.** message. It is still rejected. Product names and
browser tip flags do not establish that identity or permit ineligible goods.
Linked returns still require refund allocation.

Preparation, dispatch, payment state and recovery contracts are unchanged.
No schema migration, new configuration, credential rotation or frontend
production change is needed. Install the reviewed integrated server revision
through the normal deployment procedure and reopen POS. Do not change the
standard Tips product into ordinary sale goods to obtain clearer feedback.

## Reproduction and verification

All runs use disposable Docker projects named `odoo-revolut-ticket48-*`.
Merchant HTTP is globally blocked and mocked at the provider boundary. No
live fixture, terminal, hosting environment or other agent's runtime is used.

- **Red:** `TestRevolutCartPricing.test_native_odoo_tip_explains_removal_before_product_eligibility`
  failed before the code change with the generic product/linked-return message
  instead of the expected tip guidance. The fixture uses the actual native
  `point_of_sale.product_product_tip`, valid goods and an Odoo-entered tip.
  Log: `/tmp/ticket48-red.log` (1 failure, zero errors).
- **Green:** the same regression passed after reordering the two rejection
  checks. Log: `/tmp/ticket48-green.log` (1 test).
- **Cart pricing:** `./scripts/test-addon --test-tags /pos_revolut:TestRevolutCartPricing`
  passed all 17 tests. The new guards cover renamed/available configured tips
  without browser tip flags, inactive/unsaleable/unavailable ordinary goods
  named Tips with forged tip flags, and linked returns. Every preparation test
  asserts zero provider calls. Log: `/tmp/ticket48-pricing.log`.
- **Native POS feedback/removal:** `./scripts/test-addon --test-tags /pos_revolut:TestOdooTipBrowser`
  passed (1 test). The tour enters a tip through the native Tip dialog, selects
  Revolut through the real adapter, asserts the specific server message and
  definite non-dispatch state, deletes the tender through the native payment
  screen, and checks out with cash on the same order. It retains the Odoo tip
  for the cash lane. Server assertions prove a single paid 13.34 order with
  a 1.00 tip, cash only, zero provider calls and zero payment/refund operations.
  Log: `/tmp/ticket48-native.log`.
- **Existing native recovery:** the isolated authorization-pending cancellation
  rerun reported zero failures but was skipped after Chrome failed to start.
  Pinned Odoo raises `unittest.SkipTest` in that case, so its summary is not
  proof that the tour ran. Do not count this isolated run as recovery evidence.
  The executed new native tip tour above covers safe undispatched removal;
  the complete payment lifecycle suite covers preparation/exposure guards.
  Log: `/tmp/ticket48-recovery.log`.
- **JavaScript:** running each `static/tests/*.test.mjs` directly passed 122
  payment lifecycle tests and 3 refund allowance tests. Logs:
  `/tmp/ticket48-lifecycle.log`, `/tmp/ticket48-refund-js.log`.
- **Repository Python:** `python3 -m unittest discover -s tests` passed 65 tests,
  with 3 existing environment-dependent skips. Log: `/tmp/ticket48-python.log`.
- **Syntax:** Python compilation, `node --check` on the new tour and
  `git diff --check` passed. No static typechecking configuration is present.
- **Full addon suite:** `./scripts/test-addon` completed with **1 failed,
  0 errors, 625 tests**; exit 1. The failure was the existing
  `TestNativeAdjustmentBrowser.test_browser_completes_remaining_adjustment_without_another_refund`
  tour timing out at its first Open Register step before opening POS.
  Three existing native-printing tours skipped after Chrome startup failed:
  conserved remaining-refund receipt, narrow receipt and narrow split receipt.
  Two invoice tours also reported Chrome debugger connection timeouts and
  remain unverified. The new tip-feedback tour executed with its expected
  server rejection and no recorded failure. Log: `/tmp/ticket48-full.log`.

This is not a green full-suite result. During the run the shared host had
239 MiB free memory, essentially full 4 GiB swap, load 25.59 and substantial
memory/I/O waits. Those observations support a runtime-pressure explanation,
but are not proof that all startup failures are environmental. No unrelated
return/printing code was changed. Serial reruns of the affected existing tours
remain a broader validation limit. At ticket 47's owner-authorized coordination
request, no additional Docker/browser suite was launched after this run;
all ticket 48 disposable containers were stopped before its validation window.

The first combined focused run had three new fixture assertion failures:
deferred product-template writes were not flushed before preparation opened
its server cursor. Explicit fixture flushes corrected this; all 17 pricing
tests then passed. The same combined run had one existing browser startup
timeout before opening POS. Its isolated rerun skipped browser execution.
The 17 cart-authority tests and native invalid-cart removal/cash checkout
reported no failures in that run. Original log: `/tmp/ticket48-focused.log`.

## Ticket 12 handoff and limits

Do not mutate preserved order 1023 / 60 or tender 80, present a card, Resume,
replace the tender, cancel the order or perform SQL repair for this ticket.
No staging deployment or live acceptance has been performed. The observed
staging rejection already demonstrated no dispatch; this change corrects its
reason. Ticket 47 remains responsible for authoritatively recovering the
existing saved waiting tender after reload. Use that reviewed recovery contract
before removing the original tender or the unexposed Odoo tip; retain status
and reconciliation protections for uncertain or verified money. Ticket 49
owns Takeout readiness. Ticket 12's broader release gates remain open.

## Standards

Independent review of `6a973d5...81d367f`: no findings. The change follows the
existing addon/test style, keeps configured-tip identity on the server and
preserves financial rejection and recovery boundaries. No actionable baseline
smells were introduced.

## Spec

Independent review found no implementation defect or scope creep. One P2
evidence finding identified the misleading recovery rerun claim: Chrome startup
failure raises `SkipTest`, so zero failures did not prove that tour executed.
That claim is corrected above. The skipped check remains explicitly unverified;
the new executed tip tour independently proves the ticket's safe-removal path.

The Spec reviewer rechecked the corrected evidence and confirmed no remaining
findings. Review totals: Standards 0 findings; Spec 1 evidence finding, resolved;
0 open findings on either axis.

## Integration with merged ticket 47

Before opening the ticket 48 PR, merged `origin/main` at
`57937232af9c1e769f56373ba7d0e85c548b6586` (PR 79). The only conflict was the
ticket index; both tickets' closure/evidence entries were preserved. Production
code merged without conflicts. The integrated addon inherits `19.0.1.18.12`
and ticket 47's recovery/upgrade contract; ticket 48 adds no schema change.

Post-integration checks passed: 141 payment lifecycle tests, 3 refund allowance
tests, Python compilation, tour JavaScript syntax and whitespace checks.
Repository Python tests passed 65 tests with 3 existing skips. Logs:
`/tmp/ticket48-post-main-lifecycle.log`, `/tmp/ticket48-post-main-refund-js.log`,
`/tmp/ticket48-post-main-python.log`.

No post-integration native Odoo run was started because ticket 49 owns the
agreed serial Docker/browser window. Earlier ticket-specific native evidence
and the full-suite limitations above remain distinct from these lightweight
integration checks. The owner explicitly authorized opening and merging this PR.

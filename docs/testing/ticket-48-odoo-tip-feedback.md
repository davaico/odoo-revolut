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
- **Existing native recovery:** authorization-pending preparation cancellation
  passed separately (1 test). Log: `/tmp/ticket48-recovery.log`.
- **JavaScript:** running each `static/tests/*.test.mjs` directly passed 122
  payment lifecycle tests and 3 refund allowance tests. Logs:
  `/tmp/ticket48-lifecycle.log`, `/tmp/ticket48-refund-js.log`.
- **Repository Python:** `python3 -m unittest discover -s tests` passed 65 tests,
  with 3 existing environment-dependent skips. Log: `/tmp/ticket48-python.log`.
- **Syntax:** Python compilation, `node --check` on the new tour and
  `git diff --check` passed. No static typechecking configuration is present.
- **Full addon suite:** running; final outcome will be recorded before closure.

The first combined focused run had three new fixture assertion failures:
deferred product-template writes were not flushed before preparation opened
its server cursor. Explicit fixture flushes corrected this; all 17 pricing
tests then passed. The same combined run had one existing browser startup
timeout before opening POS. Its isolated rerun passed. The other 32 tests in
that run passed, including 17 cart-authority tests and native invalid-cart
removal/cash checkout. Original log: `/tmp/ticket48-focused.log`.

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

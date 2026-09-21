# Repository Guidelines

## Repository Boundary

This Git repository is `/home/gary/delivery/Tek2/stage/odoo-rev/odoo-revolut`. Its sibling `../odoo-hosting` provides the local/development environment, while `../worktree` holds additional worktrees for parallel-agent tasks. Do not add Odoo–Revolut product code to either sibling.

## Project Mission

Build an Odoo 19 Point of Sale addon that integrates a Revolut payment terminal through the Revolut Merchant API. Follow established Odoo addon conventions and keep changes focused on this integration.

The finished integration must:

1. Send the payment amount from Odoo POS to the Revolut terminal.
2. Let the customer complete the card payment on the terminal.
3. Monitor and verify the final payment status.
4. Confirm the Odoo order automatically only after successful payment.
5. Handle declined, failed, cancelled, and timed-out payments explicitly.
6. Support full and partial refunds.
7. Store Revolut transaction references in Odoo for reconciliation and support.
8. Keep all Revolut API credentials on the Odoo server; never expose secrets to the POS browser.

## Planned Project Structure

Place the addon under `addons/`, keeping models, views, security rules, static POS code, data, and tests inside one addon package. Put project documentation in `docs/` and reusable development scripts in `scripts/`.

## Development and Testing Principles

- Treat the Odoo server as the only trusted boundary for Revolut API calls and credentials.
- Make payment operations idempotent and persist external references before relying on callbacks or polling.
- Model payment states explicitly and link refunds to their original transaction.
- Never log access tokens, secrets, or sensitive cardholder data.
- Mock Revolut HTTP calls in automated tests; tests must never contact a real terminal or Merchant API.
- Cover success, failure, cancellation, timeout, retry, and full/partial refund paths.

Run the narrowest relevant tests before submission. Use short, imperative commit subjects. Pull requests should explain payment-flow impact, tests performed, configuration changes, and deployment or credential-rotation steps.

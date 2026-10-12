# Repository guidelines

The installable Odoo 19 integration lives in `addons/pos_revolut`. Keep product code, tests and integration documentation in this repository. Inspect existing code and use its conventions before changing an interface.

## Payment boundaries

- Keep Revolut credentials and authenticated HTTP calls on the Odoo server.
- Persist attempts and external references, use idempotency where supported, and reconcile uncertain operations before permitting retries.
- Verify the underlying successful payment and required payment details before completing a sale. A completed terminal intent alone is insufficient.
- Link refunds to original payments and conserve base, tip and returned-quantity allowances.
- Preserve native Odoo authorization, company and register boundaries.
- Use synthetic fixtures. Never commit credentials, original operational evidence or sensitive cardholder data.

## Verification and contributions

Read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and test commands, and [CONTEXT.md](CONTEXT.md) when changing payment terminology. For state, authorization, retry or refund changes, inspect the relevant models and existing regression tests before implementation.

Keep changes scoped to the request. Run the narrowest relevant checks, including a behavior test when a financial boundary changes. State skipped checks and their reason; a build alone does not prove the risky behavior was exercised. Revolut HTTP in automated tests must be mocked and the Merchant network guard must remain enabled.

Use short imperative commit subjects. Pull requests should explain payment-flow impact, verification, configuration changes and any upgrade or credential-rotation steps. Keep public reports sanitized; use [SECURITY.md](SECURITY.md) for vulnerabilities.

Internal historical tickets and financial acceptance records are maintained outside the public distribution; use the public issue tracker for new public reports.

# Working on POS Revolut

`addons/pos_revolut` is the Odoo 19 addon. Keep integration code here; follow existing Odoo conventions.

Before changing payment flows, read [Architecture](docs/architecture.md) for the lifecycle and source map. Use [CONTEXT.md](CONTEXT.md) for domain terms and [CONTRIBUTING.md](CONTRIBUTING.md) for test commands.

## Financial boundaries

- Keep credentials and authenticated Revolut calls on the server.
- Persist attempts and references before dispatch; reconcile uncertainty before retrying.
- Verify the underlying payment and base/tip amounts. A completed intent alone cannot authorize checkout.
- Preserve original order, tender and Merchant authority during recovery.
- Enforce company/register access and refund quantity, base and tip limits on the server.

## Changes

Keep changes scoped. Exercise affected behavior with the narrowest relevant tests; report skipped checks. Mock all Revolut HTTP and keep the Merchant network guard enabled. Use synthetic fixtures and follow [SECURITY.md](SECURITY.md) for sensitive reports.

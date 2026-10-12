# POS Revolut for Odoo 19

> Release candidate. Final acceptance and publication checks are pending.

Connect Odoo Point of Sale to a Revolut terminal: send the amount, let the customer pay, and complete the sale after Odoo verifies payment. Credentials and authenticated Revolut calls stay on the server.

Supports retail and Restaurant registers, split payments, terminal-selected tips, full and partial refunds, interrupted-payment recovery, and refunds issued outside Odoo.

Tested runtime: **Odoo Community 19.0.20260908** and **PostgreSQL 16.14**. Other builds are not yet verified. The addon requires standard `point_of_sale` and `pos_restaurant`; retail registers can stay in retail mode.

## Documentation

| Task | Guide |
| --- | --- |
| Install, configure credentials and grant access | [Installation](docs/installation.md) |
| Take payments, refund, recover and print | [User guide](docs/user-guide.md) |
| Preserve financial history during an update | [Upgrading](docs/upgrading.md) |
| Run tests and contribute | [Contributing](CONTRIBUTING.md) |
| Understand the lifecycle and code | [Architecture](docs/architecture.md) · [Vocabulary](CONTEXT.md) |
| Report a vulnerability privately | [Security](SECURITY.md) |

## Before using it

The server and terminal need internet access. The terminal must use **Pay at Counter**; Merchant credentials need terminal and payment-report access.

Use terminal-selected tips; Odoo-entered tips and Restaurant **Add tips after payment** are unsupported. Timed Takeout requires a pickup slot before payment. Retail currently uses the **Eat In** fulfilment mapping.

A timeout does not prove failure. Keep the original order and tender until reconciliation resolves uncertainty. Checkout requires verified payment details, the full balance, and native Odoo validation. See the [user guide](docs/user-guide.md) for recovery steps.

## License

[LGPL-3](LICENSE), with the referenced [GPL-3 terms](COPYING).

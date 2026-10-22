# POS Revolut for Odoo 18

Connect Odoo Community 18 Point of Sale to a Revolut terminal. Send the amount,
let the customer pay, and complete the sale after Odoo verifies the underlying
payment. Credentials and authenticated Revolut calls stay on the server.

This branch, `feat/v18_rev`, contains the Odoo 18 implementation in a fresh Git
history. Odoo 19 is maintained on `main`. Use the branch matching the server's
Odoo major version.

Supports retail and Restaurant registers, split payments, terminal-selected
tips, full and partial refunds, interrupted-payment recovery, external refund
reconciliation, shared-register access, native receipts, invoices and accounting.
Odoo 18 preset and pickup controls provide dine-in and timed Takeout workflows.

Test runtime: **Odoo Community 18.0.20261015** and **PostgreSQL 16.14**.
Physical-terminal acceptance remains pending; automated tests do not establish
production readiness. Installing into an existing Odoo 18 database preserves
native business data; importing another integration's payment history is outside
the initial installation scope.

## Repository structure

- `addons/pos_revolut/`: installable addon, migrations, Odoo and browser tests.
- `docs/`: installation, usage, upgrade and architecture guides.
- `scripts/`, `docker/`, `compose.yaml`: guarded disposable development runners.
- `tests/`: tests for the development and deployment tooling.

For a full clone, include the repository's `addons` directory in Odoo's
`addons_path`. The addon depends on standard `point_of_sale` and `pos_restaurant`;
retail registers can remain in retail mode.

## Documentation

| Task | Guide |
| --- | --- |
| Install and configure credentials/access | [Installation](docs/installation.md) |
| Take payments, refund and recover | [User guide](docs/user-guide.md) |
| Update an existing installation | [Upgrading](docs/upgrading.md) |
| Run tests and contribute | [Contributing](CONTRIBUTING.md) |
| Understand payment boundaries | [Architecture](docs/architecture.md) |
| Report a vulnerability privately | [Security](SECURITY.md) |

Internal deployment records and live financial acceptance notes are kept outside
this public snapshot. Use synthetic data in shared reports and test fixtures.

## License

[LGPL-3](LICENSE), with the referenced [GPL-3 terms](COPYING).

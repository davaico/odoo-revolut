# POS Revolut for Odoo 18

Connect Odoo Community 18 Point of Sale to a Revolut terminal. Send the amount,
let the customer pay, and complete the sale after Odoo verifies the underlying
payment. Credentials and authenticated Revolut calls stay on the server.

Use `18.0` for Odoo 18 and `19.0` for Odoo 19. Each version is maintained
separately; install the branch matching the server's Odoo major version.

Supports retail and Restaurant registers, split payments, terminal-selected
tips, full and partial refunds, interrupted-payment recovery, external refund
reconciliation, shared-register access, native receipts, invoices and accounting.
Odoo 18 preset and pickup controls provide dine-in and timed Takeout workflows.

Test runtime: **Odoo Community 18.0.20261015** and **PostgreSQL 16.14**.
See [Validation](docs/validation.md) for recorded automated coverage and device
testing limitations. Installing into an existing Odoo 18 database preserves
native business data; importing another integration's payment history is outside
the initial installation scope.

## Repository structure

- `pos_revolut/`: installable addon, migrations, Odoo and browser tests.
- `docs/`: installation, usage, upgrade and architecture guides.
- `scripts/`, `docker/`, `compose.yaml`: guarded disposable development runners.
- `tests/`: tests for the development and deployment tooling.

For a full clone, include the repository root in Odoo's
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
| Check tested scope and limitations | [Validation](docs/validation.md) |
| Report a vulnerability privately | [Security](SECURITY.md) |

Use synthetic data in shared reports and test fixtures. Keep credentials and
live financial evidence in restricted storage.

## License

[LGPL-3](LICENSE), with the referenced [GPL-3 terms](COPYING).

# POS Revolut for Odoo 19

> Release candidate. Public release is pending final acceptance and completion of the publication checks.

`pos_revolut` connects Odoo Point of Sale to a Revolut terminal. The cashier selects a Revolut payment method, the customer pays on the terminal, and Odoo verifies the payment before completing the sale. Merchant credentials and authenticated Revolut requests stay on the Odoo server.

The addon supports retail and Restaurant registers, cash/card split payments, multiple card payments, terminal-selected tips, full and partial refunds, interrupted-payment recovery, and reconciliation of refunds issued outside Odoo. It stores transaction references for support and reconciliation.

The development runtime is pinned to **Odoo Community 19.0.20260908** and **PostgreSQL 16.14**. Compatibility with other Odoo builds is not established by that test baseline. The single addon depends on Odoo's standard `point_of_sale` and `pos_restaurant`; retail registers can remain in retail mode.

## Start here

- [Install and configure](docs/installation.md): administrator setup and credentials.
- [Use the terminal](docs/user-guide.md): payments, refunds, receipts, and recovery.
- [Upgrade an existing installation](docs/upgrading.md): financial history and older versions.
- [Contribute](CONTRIBUTING.md): local tests and pull requests.
- [Understand the implementation](docs/architecture.md): trust boundaries and source map.
- [Security guidance](SECURITY.md): private vulnerability reporting and sensitive evidence.

## Current limits

Both the Odoo server and terminal need internet access. The terminal must belong to the configured Revolut location and use Pay at Counter mode. Setup requires a Merchant credential with access to terminal operations and payment reports.

Only terminal-selected tips are supported for Revolut checkout. Remove an Odoo-entered tip before starting payment, and disable Restaurant **Add tips after payment**. Retail uses `Eat In` as an interim fulfilment mapping; this is an integration choice, not a retail-specific Revolut contract.

Timed Takeout requires a pickup date and time before a new Revolut payment can start. Choose an available slot in Odoo's native scheduling picker; choose another date if the selected day has no slots. With scheduling satisfied, a verified payment can complete the fully paid order automatically. If scheduling needs correction after capture, keep the same order and tender, correct the slot, and validate without collecting again.

An uncertain payment stays protected until reconciled. A timeout is not proof of failure. Odoo completes a sale only after the underlying payment and its base/tip breakdown are verified and the whole order is paid. Background reconciliation records financial outcomes; the original sale or return still follows native POS completion.

## License

This project is licensed under **LGPL-3**. See [LGPL-3](LICENSE) and its referenced [GPL-3 terms](COPYING).

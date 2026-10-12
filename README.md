# POS Revolut for Odoo 19

> Release candidate. Public release is pending final acceptance, completion of the publication checks, and confirmation of the right to publish under LGPL-3.

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

Timed Takeout checkout has a known readiness gap: missing pickup scheduling can prevent native order completion after payment is captured. Select the required pickup slot before payment. If capture has already happened, correct scheduling and validate the original order without collecting again. Automatic completion for a valid timed Takeout slot still needs regression verification before claiming full support.

An uncertain payment stays protected until reconciled. A timeout is not proof of failure. Odoo completes a sale only after the underlying payment and its base/tip breakdown are verified and the whole order is paid. Background reconciliation records financial outcomes; the original sale or return still follows native POS completion.

## License

The addon manifest declares **LGPL-3**, which is the intended release license. See [LGPL-3](LICENSE) and its referenced [GPL-3 terms](COPYING). Confirmation of the copyright holder's authority to license the code remains a publication prerequisite.

# Security

Keep credentials and original customer or payment evidence out of public issues, pull requests and test fixtures. This includes Merchant secrets, access tokens, card data, terminal/location identifiers and transaction references that can be linked to live operations. Use synthetic examples.

## Report a vulnerability

Use GitHub's private **Report a vulnerability** form in this repository's Security tab. Describe the affected version, required permissions, impact and a minimal reproduction using mocked provider responses. Share only the evidence needed to reproduce the issue. Do not exercise a report against another merchant, live terminal or customer transaction.

If the private form is unavailable, do not open a public issue containing vulnerability details or financial evidence. Ask a maintainer for an approved private reporting route first.

## Operating the addon

Merchant secrets belong in the Odoo server's secret store and worker environment. Odoo stores an authorized variable reference, not the secret value. Restrict access to server configuration, backups and logs; grant each backend POS user access only to the required register.

Use supported Odoo updates and review the addon upgrade notes before deploying. An unresolved payment or refund must be reconciled using its existing operation. Do not clear a reservation, remove a pending tender or start a replacement transaction merely to dismiss an error.

The repository's Compose environment is disposable and uses public test credentials. It is not a production deployment template. Automated tests block real Merchant API traffic.

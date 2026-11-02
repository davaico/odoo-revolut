# Security

## Report a vulnerability

Use **Report a vulnerability** in this repository's GitHub Security tab. Include the affected version, permissions, impact and a minimal reproduction with mocked provider responses.

If the private form is unavailable, contact the maintainers through an approved private channel before sharing details. Never put vulnerabilities, credentials or financial evidence in a public issue. Do not test against another merchant, live terminal or customer transaction.

Use synthetic examples. Keep secrets, card/customer data, live terminal/location identifiers, transaction references, private hostnames and operational logs out of public reports and fixtures.

## Deployment

Store Merchant secrets in the server secret store and worker environment, or in
administrator-only database credential authorities. POS managers configure
authorized references without reading keys. Database keys are included in
backups; password masking is not encryption. Restrict database access,
configuration, backups and logs; grant users only the registers they need.

Follow [Installation](docs/installation.md) and [Upgrading](docs/upgrading.md). Resolve uncertain payments/refunds through their original records using the [recovery steps](docs/user-guide.md#understand-the-payment-status).

Compose is a disposable test environment with fake credentials and blocked Merchant HTTP, not a production template.

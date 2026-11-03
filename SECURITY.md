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

On Odoo.sh, use the **Database** credential source so configuration does not
depend on custom environment variables for HTTP and cron workers. Only system
administrators administer authorities and keys. Rotation creates a new authority;
retain the original authority and working key for unresolved operations and
historical refunds. The configured source never falls back to another source
or Merchant account.

Keep test databases neutralized. The addon blocks Production Revolut access on
Odoo.sh test stages and neutralized databases, including connection checks and
scheduled reconciliation. Neutralization removes Production database keys and
disables live configuration while preserving financial history. Protect backups,
which can still contain their original keys, and use separate Sandbox
credentials for testing.

Follow [Installation](docs/installation.md) and [Upgrading](docs/upgrading.md). Resolve uncertain payments/refunds through their original records using the [recovery steps](docs/user-guide.md#understand-the-payment-status).

Compose is a disposable test environment with fake credentials and blocked Merchant HTTP, not a production template.

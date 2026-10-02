# Development Environment

This document contains only the infrastructure facts needed to build and test the Odoo–Revolut addon. Provisioning and cloud operations remain owned by the sibling `odoo-hosting` repository.

## Current staging target

- URL: `https://odoo-revolut.davaiodoo.com`
- Customer/environment: `revolut` / `staging`
- Odoo: Community 19, package `19.0.20260908`
- Database: `revolut_staging`
- Company/currency: Davai / EUR
- Hosting profile: `../odoo-hosting/customers/revolut.staging.json`
- Hosting baseline: branch `feat/revolut-staging`, commit `d5c8aba`

The VM, PostgreSQL, Odoo, Cloudflare Tunnel, Tailscale SSH, and base Point of Sale setup were verified during provisioning. A normal cash sale was completed to verify POS independently of the future Revolut addon. Basic DNS and TLS connectivity to Revolut's sandbox host was also checked without authenticating or sending payment data.

Cloudflare Access is intentionally disabled for this staging profile, so the public URL presents the normal Odoo login. Server administration uses the company tailnet; the VM has no public SSH port.

## Repository boundary

- All addon source, tests, setup instructions, and payment-integration documentation belong in this repository.
- `../odoo-hosting` owns Terraform, the VM profile, Cloudflare/Tailscale setup, and local Terraform state.
- Do not edit integration code directly on the VM. The repository remains the source of truth.
- GitHub CI may lint and test the addon, but it must not deploy it.

## Development and deployment workflow

Development can begin entirely with mocked Revolut HTTP behavior; Merchant credentials and a physical terminal are not required for the first implementation stages.

The intended workflow is:

1. Build and test the addon locally in this repository.
2. Use the local deployment script to copy a reviewed revision to the staging
   VM, following [the staging deployment runbook](staging-deployment.md).
3. Install or upgrade the addon in the staging database.
4. Validate the POS behavior in the browser and inspect server logs through Tailscale SSH.
5. Perform physical-terminal and financial tests only under ticket 12 after the
   production Merchant environment, matching physical location, eligible
   terminal, Pay at Counter mode and test amounts are explicitly verified and
   authorized.

Future deployment tooling must place the addon in a customer-specific directory, preserve the existing Odoo `addons_path`, stop Odoo during an upgrade, run the module update with `--stop-after-init --no-http --workers=0`, and restart the service. The script must fail safely and identify the exact revision deployed.

## Secrets and generated data

Never commit or document Merchant API tokens, Odoo passwords, Terraform state, Tailscale enrollment material, or Cloudflare tunnel credentials here. Revolut credentials must remain on the Odoo server and must never be exported to POS JavaScript or written to logs.

The infrastructure account IDs, VM provisioning commands, Terraform recovery procedure, and provider credentials are intentionally omitted because they are not required to implement the addon. Consult `../odoo-hosting` when infrastructure work is actually needed.

## Local addon verification

The repository now includes a disposable environment pinned to Odoo Community
`19.0.20260908` and PostgreSQL 16.14. Run the addon tests with:

```bash
./scripts/test-addon
```

Verify install, upgrade, the manager configuration browser flow, and actual
retail and Restaurant POS startup:

```bash
./scripts/test-addon --verify-install-upgrade
```

The runtime environment has no external network route. Expected Revolut calls
are mocked; any accidental outbound API traffic fails. The browser-test image
adds a checksum-verified Chrome package and Odoo's `python3-websocket` browser
transport to the exact pinned Odoo base image. The latter was approved as a
test-only dependency on 23 September 2026. The runner verifies it imports before
testing: without it, Odoo silently skips browser tours after a warning, so those
older warning-only runs are not browser acceptance evidence.

The official Revolut terminal guide documents a controlled Sandbox route using
a fixed virtual terminal and amount-driven simulated outcomes. On 2026-09-28,
Gary — tester confirmed Sandbox Merchant access, created a physical Sandbox
location and ran non-financial contract probes. Order validation and underlying
payment retrieval worked, but two nominal-success virtual-terminal attempts
created failed payments while their intents remained pending. The Sandbox
Devices page also failed. See the
[terminal contract record](revolut-terminal-contract-2026-09-22.md).

No Sandbox credential value belongs in this repository. Production
physical-terminal configuration, discovery and financial acceptance are not
development-environment prerequisites; they remain ticket 12 work.

Verify retirement against actual receipt-enabled history, including preserved
accounting documents and archived customer PDFs:

```bash
./scripts/test-receipt-retirement-upgrade
```

This runner installs fixed receipt-enabled revision `83a7b24` in an isolated
database, seeds verified historical payment/partial-refund records with provider
traffic blocked, upgrades to the candidate and compares stored values. Native
historical printing and invoice rendering are covered by
`TestRevolutNativePrinting` and `TestRevolutNativeDocuments` on the pinned build.
Physical printing and staging PDF checks remain tickets 12 and 34.

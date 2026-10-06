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

## Historical upgrade runner

All seven historical commands use one shared module,
`scripts/test-historical-upgrade <scenario>`. The existing entry commands remain
available; each selects its fixed historical scenario. The runner owns Git
extraction, runtime checks, old-code installation and seeding, candidate upgrade,
verification in separate Odoo processes, and cleanup. Scenario descriptions are
private to the runner; callers do not supply phase hooks or cleanup callbacks.
This keeps lifecycle knowledge local without introducing a manifest parser or
making each caller manage temporary paths and addon mounts.

| Existing command | Historical revision | Seed / verify fixture prefix |
| --- | --- | --- |
| `scripts/test-cart-authority-upgrade` | `719bae93390c3a326673af2d0e6b89aea0a84b65` | `upgrade` |
| `scripts/test-credential-authority-upgrade` | `09c982d` | `credential_upgrade` |
| `scripts/test-register-access-upgrade` | `d1124f4` | `register_upgrade` |
| `scripts/test-receipt-retirement-upgrade` | `83a7b2484ee16adcacc16e336d1c6e53e8d5508d` | `receipt_retirement` |
| `scripts/test-return-rounding-upgrade` | `7df76793d7bd772af69b1e3e5054c96d9c69b84b` | `return_rounding_upgrade` |
| `scripts/test-external-native-upgrade` | `354ca65` | `external_native_upgrade` |
| `scripts/test-evidence-retirement-upgrade` | `319407e1a47a37f1a7aa8c328c0d7f290301ce66` | `evidence_retirement` |

Historical revisions, default project/database names and financial fixture
assertions are retained. The cart verifier compares the installed addon version
with the candidate manifest instead of a release-specific constant, and checks
final-evidence polling before and after explicit Merchant-account authorization.
Its positive recovery assertion runs after that authorization, as required by
the current observation module. It also saves the native return before testing
the historical amount-based refund, as current dispatch requires. Archives
containing the former Restaurant addon retain that addon alongside current
`pos_revolut` during migration, matching deployment. The overlay is removed
before verification; receipt retirement additionally starts a separate normal
Odoo process for native report assets and PDF downloads.

The default Compose projects remain disposable. Set
`ODOO_REVOLUT_TEST_PROJECT` to a distinct disposable project to run scenarios
concurrently. The runner uses `flock` to reject overlapping historical runs with
the same project before any Docker operation. Locks are shared across repository
worktrees under `/tmp/odoo-revolut-upgrade-locks-<uid>/`; their small lock files
remain after release to avoid replacing an inode still held by another run.
Other test scripts do not participate in this lock, so give those scripts their
own project names too.

Cleanup runs on success, failure, SIGINT and SIGTERM, including signals sent
to only the runner PID. The runner forwards interruption to its active child
and waits for it before removing resources. It removes the report
process, Compose resources/volumes, and owned temporary addon directories. A
cleanup failure is reported and makes a successful verification exit nonzero;
a prior phase failure keeps its original exit status. The success message is
printed only after cleanup succeeds. SIGKILL and host shutdown cannot run shell
traps; rerun the same disposable project to reset leftover Compose resources.

Run the focused runner checks without Docker:

```bash
python3 -m unittest discover -s tests -p test_historical_upgrade_runner.py -v
```

These checks cross the same command interface as users, with real Git archives
and filesystem operations and a Docker executable stand-in. They exercise all
historical selections, mount transitions, separate phase invocations, version
and guard rejection, failures, interruptions, cleanup errors and project
isolation. Actual historical commands must also pass on the pinned runtime:
recorded commands alone are not proof that migrations preserve financial data.

Verification on 6 October 2026: all seven historical commands exited 0 on pinned
Odoo `19.0.20260908`, including the receipt verifier's real QWeb PDF rendering
and repeated authenticated downloads. The focused CLI suite passed all 10 tests;
all eight shell entry scripts passed `bash -n`. Provider HTTP remained blocked
by the unchanged Compose network and Merchant guard. Local logs are
`/tmp/upgrade-runner-<scenario>-final.log` and
`/tmp/upgrade-runner-cli-final.log`. The original cart runner's missing-addon
migration failure was reproduced separately before correcting the shared
migration mount; subsequent fixture corrections retained its six historical
states, exact financial comparisons, retry and legacy-refund assertions.

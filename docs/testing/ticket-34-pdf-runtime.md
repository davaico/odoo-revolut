# Ticket 34 — PDF provisioning and deployment gate

## Scope and target facts

Local work on 2026-10-01 started from integration
`dad0e1515ee7b936834906f810f50999f3e33da9` and hosting `245f58e`.
Initial integration implementation is `c2f0baf` on
`codex/34-provision-and-gate-odoo-pdf`; hosting implementation is `1f2aa0287f919a95a2268705f639ba616c8c8788` on
`feat/revolut-staging`.
Fetched integration `origin/main` matched the baseline. Both initial checkouts
were clean; existing worktrees and hosting branch were retained.

No staging inspection, package installation, restart, deployment, Merchant
request or financial outcome change was performed. The owner-reported missing
renderer on addon `19.0.1.10.2` remains a reported target fact. Its installed
package, binary permissions, service environment and current financial blockers
have **not** been established by these local tests. Tickets 12, 31 and 32 retain
their existing evidence and gates. Ticket 25 stays closed and unchanged.

The supported hosting configuration selects Ubuntu 24.04. The official
[Odoo 19 Dockerfile](https://github.com/odoo/docker/blob/d9c2d8d50aa8eca1aadc186241bee3eac0e2d79e/19.0/Dockerfile)
also uses Ubuntu Noble with the upstream Jammy patched-Qt build. Hosting pins
`wkhtmltox 1:0.12.6.1-3.jammy` from the official
[packaging release](https://github.com/wkhtmltopdf/packaging/releases/tag/0.12.6.1-3):

| Architecture | SHA256 |
| --- | --- |
| amd64 | `4f723b2691ad8638a9df960e0421d346d7315083e3583a334f33362280ddba15` |
| arm64 | `2095f20256661ebf0983b9311168596c9d012666e21a94bc24f304db6ac69ec5` |

Runtime evidence here is from amd64. An arm64 runtime was not available;
architecture selection, package metadata and digest guards are automated, but
an arm64 report rendering pass is not claimed.

## Behavior and test seams

The owner confirmed provisioning/repair, deployment before mutation, and actual
historical report rendering as the test seams, plus the starting integration
HEAD as review baseline. The first new deployment refusal test failed before
implementation: the old workflow reached service stop rather than refusing a
PDF failure. The implemented check now executes before backup, stop, offline
module update or release switching. It renders local disposable body/header/
footer HTML under `odoo` with only the running process's renderer/Python
environment allowlist, and parses the PDF with Odoo's PDF library. It uses no
database, saved report data, external URL, credentials or provider call.

The unit suite covers subprocess refusal for absent/incompatible/unexecutable
renderers, unreadable output, unconfirmed success and timeout; invalid/missing
service identity/PID/environment is also rejected. It verifies unchanged
fixture files and release symlink, no backup/release directory, no service
start/stop, and only SELECT financial queries on rejection. Existing checksum,
reviewed-artifact, financial blockers, quiescence and update checks remain.
Host authentication and privileged-file investigations are not resolved by this
PDF change.

Historical receipt tests use stored verified payment/refund fixtures, mocked
provider access and the image's Merchant HTTP guard. Repeated full and partial
refund PDFs and the original payment PDFs retain references, amount/currency,
financial snapshots, merchant snapshots, verification timestamps, write dates,
operation/order/payment/audit counts and the closed original POS session. No
new financial operation or PDF attachment is created by downloading.

## Executed checks

| Check | Result | Local log |
| --- | --- | --- |
| Deployment unit suite | 32 passed | `/tmp/ticket34-deployment-tests.log` |
| Native JavaScript payment-state suite | Passed | `node --test addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` |
| Focused actual historical report suite | 15 passed, 0 failures/errors | `/tmp/ticket34-receipts.log` |
| Missing renderer, actual historical Odoo report | Expected error: “Unable to find Wkhtmltopdf on this system. The PDF can not be created.” | `/tmp/ticket34-missing-renderer.log` |
| Real probe failure scenarios and restored renderer | Missing/inaccessible/incompatible/execution/rendering/unreadable all refused; real body/header/footer passed | `/tmp/ticket34-pdf-probe.log` |
| Durable actual probe regressions in supported image, network disabled | 7 passed, no skips | `/tmp/ticket34-probe-regressions.log` |
| Whole service-environment preflight wrapper | Success, missing-executable refusal, restored success, same service process kept running | `/tmp/ticket34-pdf-wrapper-capability.log` |
| Restored renderer and final focused receipt tests | 15 passed, 0 failures/errors | `/tmp/ticket34-receipts-restored.log` |
| Full addon installation suite | 357 passed, 0 failures/errors, no Chrome startup skips | `/tmp/ticket34-full-addon.log` |
| Hosting full check | 46 Python tests; shell checks; Terraform format/validate and mocked-provider test passed | Hosting `docs/testing/ticket-34-pdf-provisioning.md` |

The missing-renderer reproduction renames only the executable in an ephemeral
container, then starts a fresh Odoo process against the isolated test database.
It uses Community package `19.0.20260908`, Ubuntu `24.04.5`, `odoo` uid 100,
and normal guarded repository addon/configuration mounts. The available renderer
is `/usr/local/bin/wkhtmltopdf 0.12.6.1 (with patched qt)`. This reproduces the
reported server-side dependency symptom, not an inspected staging root cause.

The full addon suite loaded the equivalent receipt helper before its duplicate
refund search was consolidated; the final helper passed all 15 focused tests.
The whole wrapper test uses actual `odoo` process `/proc` environment and real
`runuser`; only systemd's absent container metadata query is substituted. Docker
required `SYS_PTRACE` to read another UID's process environment, whereas normal
host root supplies this capability. An initial container attempt without it
refused safely (`/tmp/ticket34-pdf-wrapper.log`); it is not a successful runtime
check. Both wrapper success and refusal kept the same Odoo process alive and
excluded a fake secret from the renderer environment.

Hosting removed only the renderer in a disposable official Odoo container,
installed from the verified asset twice, and preserved Odoo `19.0.20260908`.
Its service-identity verification passed with `umask 077`. Full systemd/cloud-init
startup was not executed in a new VM; the wiring is covered by hosting's mocked
Terraform and script checks. See the hosting evidence for package mutation
guards, exact commands and limits.

Reproduce the durable probe checks from this checkout:

```sh
docker run --rm --network none --env ODOO_REVOLUT_BLOCK_MERCHANT_HTTP=1 \
  --volume "$PWD:/mnt/ticket34:ro" --workdir /mnt/ticket34 \
  --entrypoint python3 odoo-revolut-test:19.0.20260908-chrome153 \
  -m unittest discover -s tests -p test_pdf_probe.py -v
```

On a workstation without the Odoo library, the three parsing/real-rendering
cases intentionally skip; all seven ran without skips in the supported image.
For report reproduction, use `scripts/test-addon --test-tags
/pos_revolut:TestRevolutReceipt`; the full suite uses `/pos_revolut` with the
same internal-network compose environment and guarded image. An evidence
archive with runtime scenario scripts, logs and fixture PDFs is locally saved
at `/tmp/ticket34-pdf-evidence.tar.gz`; it contains no live financial data.

No static typechecker is configured for the deployment scripts; Python
compilation and the executable tests are the applicable checks. A passing
compilation or package version alone is not treated as rendering evidence.

## Actual PDF inspection

The report-test exporter writes only disposable verified fixture documents to
`/tmp/ticket34-artifacts/`. The parent visually inspected rasterized A4 payment,
full refund and partial refund PDFs. All have legible titles and amounts,
unclipped references, timestamps, and clear Odoo-generated document labels.
Refunds visibly link the original payment; no accounting invoice is implied.
The selected fixture PDFs are:

| File | Content | SHA256 |
| --- | --- | --- |
| `payment-32.pdf` | Verified payment 12.34 USD | `e8838be8fa5fe6b064deab675b47ef07206642a349c1c441062e707ee75def27` |
| `refund-10.pdf` | Completed partial refund 6.17 USD | `c2ac4703e5430d0bea9453cd292d008895ff699ade74e2f9b03ad95f0a8c4b38` |
| `refund-12.pdf` | Completed full refund 12.34 USD | `5373510bde1e875a3cafdaeb0ab8695681ab283ff890f6aaaf43d2d0af50f913` |

Local `/tmp` artifacts are temporary; this committed record preserves findings
and hashes. These tests and visual inspection establish readable PDF output,
not physical printer success.

## Remaining staging acceptance

Staging acceptance requires separately authorized infrastructure access and
current satisfaction of the financial, host-identity and reviewed-artifact
gates. Do not reuse old pending-refund counts. The operator must inspect the
actual renderer package, executable access and service environment; run the
reviewed hosting repair; perform any authorized controlled Odoo restart; then
download an existing historical verified payment and completed refund twice.
Check references, amounts/currency, original payment links and print preview
without opening the original session or initiating any payment/refund.

Record the exact deployed integration and hosting revisions, renderer build,
operator/time and result without secrets. Installing workstation software does
not repair this server dependency. See the
[deployment PDF runbook](../staging-deployment.md#pdf-prerequisite-and-deployment-refusal)
and hosting `docs/PDF_RENDERING.md` for concrete repair commands. The ticket must
retain this human acceptance gap until that evidence exists.

## Standards

Independent review of integration baseline through `c2f0baf` plus the final
repair-diagnostic/probe-test additions, and hosting `245f58e...1f2aa028`, found
no remaining documented-standard violations or actionable smell judgments.
The initial hosting issue (root-owned private probe HTML under `umask 077`)
was fixed by giving the files Odoo ownership and directly verified with a real
strict-umask rendering run.

## Spec

Independent review found the integration diagnostic named an unavailable
`repair-pdf` operation, and the initial orchestration mocks did not themselves
exercise the probe's detection branches. The diagnostic now names the actual
reviewed installer and hosting PDF guide. Seven durable tests execute those
branches and real successful rendering in the supported network-disabled image.
An unrelated replacement-VM documentation link accidentally changed during
that correction was restored to hosting `docs/OPERATIONS.md`. No financial
behavior or staging gate was changed. Staging acceptance remains open.

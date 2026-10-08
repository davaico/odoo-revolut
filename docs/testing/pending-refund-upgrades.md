# Update while refunds are pending

The owner requested on 2026-10-08 that normal updates remain possible while
refunds are pending, and that the already implemented retirement of the broad
Merchant discovery page be used without unnecessary manual UI/access changes.

The previous deployment guard refused every nonfinal refund and unresolved
internal discovery observation. A provider refund can remain processing beyond
the deployment window, so requiring a final outcome prevents routine updates.
The relevant distinction is between provider settlement and an Odoo dispatch
that still lacks a safe persisted identity.

## Scoped behavior

Only deployment tooling changes. The addon payment/refund state machine,
reserved amounts, replay restrictions, credentials, reconciliation and native
returns remain unchanged. The existing addon migration removes the broad
Merchant-wide menu, action, views and user read permission, while retaining
internal evidence. No additional menu, ACL or data cleanup is required.

| Existing state during upgrade | Deployment result |
| --- | --- |
| Active/uncertain payment | Refuse, as before |
| Refund dispatching, with or without a provider reference | Refuse |
| Pending/unresolved refund with missing or malformed provider UUID | Refuse |
| Pending/unresolved refund with a persisted provider UUID | Permit with preservation checks |
| Internal GET-only discovery evidence, including an unidentified refund | Permit with preservation checks; retain its financial restrictions |
| Completed/failed refund | Permit, as before |
| Unrecognized financial operation model | Retain its existing guard |

Install mode keeps the previous conservative guard. Upgrade mode does not
change any stored `deployment_blocking` flag; discovery evidence continues
to protect refund capacity and authority independently of deployment.

After backup and service stop, the deployer repeats its preflight and snapshots
every stored operation/evidence column except `write_date` and `write_uid`.
The snapshot is stored privately with mode `0600` in the root-only configuration
backup. The offline upgrade runs without serving HTTP or checkout workers.
Before restart, every original row, key and value must still exist unchanged.
New schema defaults may be added. Decimal monetary values are compared exactly.
A failed preservation check leaves Odoo stopped and names only the affected
table; it does not print ledger records or automatically restore a database.

Stopping Odoo pauses local polling. Once restarted, existing reconciliation
uses the original provider references. It does not resend the refund or
pretend that a pending refund has completed. The operator must still follow
the payment-safe recovery runbook if an update fails.

## Verification scope

Existing agreed seams are the deployment command/workflow and disposable
Odoo/PostgreSQL upgrade and refund-polling interfaces from T12 A05.

- Regression first: the old guard returned an external-evidence blocker, and
  the actual PostgreSQL runner refused a pending refund even after its provider
  reference was saved.
- Deployment unit regressions exercise a successful pending-refund upgrade
  and private preservation snapshot, plus deleted/added rows and changed
  references, amounts, states, reservations, retry protection, report history,
  native correction/status/lot evidence. Corruption prevents restart.
- The actual SQL runner exercises active payment, missing provider identity,
  active refund dispatch, malformed reference and safely referenced pending
  or unresolved refunds. An actual offline Odoo upgrade must preserve the full
  ledger, including blocking internal evidence.
- After upgrade, the public refund-polling API verifies the original external
  refund using one mocked GET; a repeated poll makes no request and no POST
  occurs. The provider identity, source and refund-record count stay unchanged.
- `--legacy-addons-dir` exercises the same path from staging's exact old addon
  revision, including the existing broad-page retirement migration.

Commands and final results are recorded in the current T12 guided retest once
the candidate is frozen. Provider HTTP is blocked in every disposable test.
No test contacts a live terminal or Merchant API.

## Local checkpoint — 2026-10-08

- Full Python tooling suite: 61 tests run, 58 passed, three unchanged local PDF
  skips. Those PDF cases were already executed in the supported Odoo runtime
  during this campaign; no PDF code changed here.
- Historical deployment SQL/upgrade/recovery runner: PASS, exit 0, starting
  from staging revision `bcb02045931633436bbd419cce0f79722937bc7f`.
  Pending/unresolved references and all pre-existing ledger values survived;
  cached replay after one mocked GET sent no new financial request.
- Unit corruption regressions: deleted/added rows and changes to states,
  references, amounts, reservations, native completion evidence, retry/history
  protection and sub-float monetary precision all prevent restart.
- Independent Standards and Spec reviews: no remaining findings. Both identified
  the initial snapshot allowlist gap; it was corrected by snapshotting every
  stored column rather than maintaining a partial list.
- The addon, Docker configuration and ordinary addon/lifecycle suites are
  byte-for-byte unchanged from `693937ee3b7a78991a33cc714e0d47a4c70c3663`.
  Earlier broad mocked acceptance remains attributable to that unchanged source.

Local working logs are under `build/ticket12-2026-10-08/`:
`pending-upgrade-guard-red.log`, `pending-upgrade-guard-green.log` (retained
intermediate fixture failure), `pending-upgrade-guard-historical.log` (final
successful historical path), and `pending-upgrade-all-tooling-final.log`.
These logs are not permanent private preservation. Staging deployment and all
fresh live acceptance results are recorded separately in the guided retest.

# Ticket 35: explicit register authorization

Date: 2026-10-02. Scope: local implementation and mocked acceptance of
[ticket 35](../tickets/closed/35-enforce-shared-register-authorization.md).

## Candidate and policy

The isolated branch `codex/35-enforce-shared-register-authorization` starts
from fetched main `d1124f4c0c0736e4a0af73bb10418346d722328d`. The initial
implementation is `ef738c4c7d50a16ff1e30e0c88a20a5f006881e2`; a subsequent
review correction closes native tender and historical receipt disclosure.
The final combined source revision is
`e3333ea20abdddfd1609f3ec20d8f14f6c632609`, including current fetched main
`0ddde9a9b431f5e7d1c9ac83f98c5033a6274dfd`. New main commits change ticket
33/34/36 documentation; the ticket-index merge preserves those updates and
this task's status. Runtime corrections are in `0777103` and `74d7ec5`.
The final evidence commit changes only documentation; runtime acceptance uses
this immutable source revision.

`pos.config.revolut_user_ids` is an administrator-only, non-copying backend-user
grant. Create/default-context/write/import/relation commands cannot supply
grants as cashiers or POS managers. Native system administrator config ACLs
remain the provisioning workflow; administrator status does not exempt an
interactive POS manager from the grant requirement.

Public preparation, admission, start, checkout state, recovery, refund discovery,
refund control and manager reconciliation require the applicable role, active
company, native config/session/order access and explicit register grant before
effects or disclosure. Dedicated financial worklists and protected native
tenders intersect fresh native visibility queries. Ordinary native cash data
continues to load. Receipt documents and options authorize the original financial
operation identity as well as linked native orders.

Two granted colleagues can share a register and recover the same attempt.
Native employee selection/PIN does not change the backend UID or supply a grant;
a granted backend user needs no linked employee. Historical access uses original
persisted config/session identity, preserving same-register closed-session
recovery and rollover. Sharing/reassigning a payment method does not relocate
an attempt's authority or expand cross-register refunds.

Revocation blocks subsequent interactive requests without cancellation, evidence
deletion or replacement charges. Trusted background reconciliation still handles
late success, and regrant restores the original attempt. Existing/new/copied
registers have no implicit grants. Installation instructions document administrator
provisioning and supervisor grants for every register they oversee.

## Verification environment

Commands run from
`/home/gary/delivery/Tek2/stage/odoo-rev/worktree/35-register-authorization`.
The disposable Compose environment uses Odoo `19.0.20260908`, Chromium 153,
PostgreSQL 16.14 and the repository Merchant HTTP guard. Provider requests in
financial tests are mocked. No terminal or real Merchant API was contacted.
The acceptance runner verifies the Odoo package, websocket browser dependency
and Merchant HTTP guard before running tests.

## Red evidence and corrections

- The original public known-ID native-denial regression failed on the baseline:
  five failed assertions in one test, including four unauthorized recovery/control
  calls and provider activity. This retains the ticket 30 bypass reproduction.
- The first full retail run had four failures in 392 tests: two outdated
  cross-register error assertions, a retry fixture whose grant write invalidated
  prepared pricing authority, and a real unsaved globally rounded refund browser
  regression. Fixtures now prepare fresh authority after administrator grants;
  the runtime pricing checks remain intact. The refund absence RPC accepts native
  persisted session identity only when no historical attempt/order supplies the
  boundary; the browser passes its session ID. Original bindings always win.
- Initial independent security review reproduced native tender disclosure and
  cash-only native order reload failure from receipt-link computation. Grant
  protection and per-user derived fields were added; unauthorized computed receipt
  links hide financial options while explicit receipt APIs still deny access.
- Independent Spec review of `ef738c4` found native tender related-record rules
  were incomplete and historical receipt checks omitted the original session.
  Two new tests reproduced four failures before the correction: native config,
  session and order denials each leaked a tender, and same-register rollover
  leaked receipt options. Native tender read/search and payment/refund receipt
  download/discovery now apply those boundaries. A further failing regression
  covers a verified refund without native association: matching saved return
  company/UUID identity still supplies its native order boundary. Another failing
  regression covers derived exposure/payable fields after same-register rollover;
  those fields now authorize the original cart and financial session before
  reading exposure and hide values on native denial.
- Intermediate focused runs also exposed missing legitimate fixture grants,
  native copy restrictions, optional-related-record domain semantics, and a
  cashier financial-model ACL restriction in the first tender-query correction.
  These failures were corrected rather than counted as acceptance. One mixed
  employee/receipt rerun also encountered a native fixture setup deadlock; retail
  receipt coverage and the actual employee authorization profile are verified
  separately. Interrupted full runs produced no passing result.

[Ticket 30's original report](ticket-30-shared-pos-session-access.md) retains
its original revision, policy investigation and mixed-profile failures. Those
historical failures are not passing ticket 35 acceptance evidence.

## Exact acceptance commands

```bash
ODOO_REVOLUT_TEST_PROJECT=ticket35-final ./scripts/test-addon --verify-install-upgrade
ODOO_REVOLUT_TEST_PROJECT=ticket35-migration-final ./scripts/test-register-access-upgrade
docker compose --project-name ticket35-access --file compose.yaml run --rm odoo \
  --database ticket35_claims_corrected --stop-after-init --workers 0 --max-cron-threads 0 \
  --log-level warn --log-handler odoo.tests.result:INFO --init pos_revolut,pos_hr \
  --test-tags /pos_revolut:TestSharedPosSessionAccess,/pos_revolut:TestRevolutRegisterRefund,/pos_revolut:TestRevolutRegisterWorklists
node --test --test-isolation=none addons/pos_revolut/static/tests/revolut_payment_state.test.mjs
python3 -m unittest discover -s tests -v
docker run --rm --network none \
  --volume /home/gary/delivery/Tek2/stage/odoo-rev/worktree/35-register-authorization:/repo:ro \
  --workdir /repo --entrypoint python3 odoo-revolut-test:19.0.20260908-chrome153 \
  -m unittest discover -s tests -p test_pdf_probe.py -v
python3 -m compileall -q addons/pos_revolut addons/pos_revolut_restaurant tests
bash -n scripts/test-register-access-upgrade
git diff --check
```

Additional retail-focused command on the final source correction (58 tests):

```bash
docker compose --project-name ticket35-access --file compose.yaml run --rm odoo \
  --database ticket35_access --stop-after-init --workers 0 --max-cron-threads 0 \
  --log-level warn --log-handler odoo.tests.result:INFO --update pos_revolut \
  --test-tags /pos_revolut:TestSharedPosSessionAccess,/pos_revolut:TestRevolutReceipt,/pos_revolut:TestRevolutRegisterWorklists,/pos_revolut:TestRevolutRegisterRefund
```

| Check | Result | Local output |
| --- | --- | --- |
| Combined focused retail access/refund/worklist/actual receipt PDFs | 58 tests; 0 failures/errors | `/tmp/ticket35-focused-final.log` |
| Independent actual POS employee authorization profile | 41 tests; 0 failures/errors; exit 0 | `/tmp/ticket35-claims-corrected.log` |
| Old-to-new migration and retained late-success attempt | Passed; exit 0 | `/tmp/ticket35-migration-final-source.log` |
| JavaScript payment lifecycle | 75 passed; 0 failed/skipped | `/tmp/ticket35-lifecycle-final.log` |
| Host tooling suite | 39 tests; OK; 3 PDF dependency skips | `/tmp/ticket35-local-final.log` |
| PDF probe in pinned runtime | 7 passed; no skips; includes host-skipped renderer/parser controls | `/tmp/ticket35-pdf-final.log` |
| Python compilation, addon XML parsing, shell syntax, diff whitespace | Passed; no configured standalone typechecker | Local command outputs |
| Clean retail installation, including Chromium tours | 406 tests; 0 failures/errors | `/tmp/ticket35-acceptance-final.log` |
| Full retail upgrade, including Chromium tours | 406 tests; 0 failures/errors | Same combined acceptance log |
| Sequential Restaurant install and bridge browser profile | 9 tests; 0 failures/errors | Same combined acceptance log |

The retail employee-list test is intentionally skipped when `pos_hr` is absent;
its real employee-domain and backend-identity controls run in the separate
41-test employee-enabled profile. The pinned PDF run covers the three dependency
checks skipped on the host. No skip is treated as proof of the affected behavior.

The full acceptance runner exited 0 after all three phases. Its disposable
project and the migration project cleaned up automatically; the focused
verification database/project was removed after independent verification.

Logs under `/tmp` are ephemeral; this report records durable commands, revision,
counts and outcomes. The full runner installs retail, upgrades retail, installs
Restaurant (including the auto-installed bridge), then runs the actual
`pos_revolut_restaurant` profile. Its browser tours execute with Chromium and
websocket support; addon installation alone is not acceptance.

The migration runner installs archived baseline `d1124f4` in one Odoo process,
seeds an existing manager/opener/register and uncertain payment, then upgrades
in a new process. It verifies no implicit grants, retained financial evidence,
zero unauthorized provider calls, root reconciliation of late success without
replacement dispatch, and recovery of the same operation after explicit grant.

## Source findings

Separate standalone verification returned **fixed** for each original finding
on final combined revision `e3333ea`. The independent read-only verifier installed
actual `pos_hr` on new database `ticket35_claims_corrected` and passed **41 tests,
zero failures/errors**, process exit 0. This repeats and extends the preliminary
39-test verification on `ef738c4`; final verdicts include subsequent corrections.
The exact independent command is listed above; its log is
`/tmp/ticket35-claims-corrected.log` (ephemeral local output).

- **Fixed — `csf_07cbc859664310f0ebdc4d36`:** attacker-controlled preparation/start and known-ID
  recovery now encounter caller-native role/company/grant checks before dispatch,
  disclosure or control. Grants cannot be self-provisioned, and a granted
  non-opener can still use/recover the shared register.
- **Fixed — `csf_157cf1168e2a1b99dde24367`:** supplied session/order/payment-line identifiers
  cannot initiate another register's terminal activity without an explicit grant.
  Preparation and owned reservation repeat authorization; employee identity and
  shared payment methods cannot relocate the persisted boundary.

The first path is closed by `PosConfig._check_revolut_register_access`, cart
identity checks, `_validate_revolut_pos_request`, and persisted-operation checks
in find/owned recovery reads. The second path repeats these checks for requested
session, prior attempt and coalesced operation before dispatch. Both verdicts
retain zero mocked I/O on rejected calls and legitimate separately granted
non-opener initiation/recovery. Equivalent tender, receipt and derived-field
paths receive caller-native checks against persisted historical identity.

These are repository verification verdicts, not deployed remediation claims.
No security-workbench scan record or verdict was modified.

## Standards

Independent review of `0ddde9a...e3333ea` against `AGENTS.md`, `docs/agents/`,
`CONTEXT.md`, ADR 0001, established addon conventions and the Fowler smell baseline:

> No documented-standard violations or actionable heuristic smells found.
>
> The additional historical-access fixes follow the existing boundary pattern:
> sudo resolves persisted identity, then caller-native checks authorize
> disclosure. Receipt recovery now checks a matching saved return before
> association; derived exposure checks the original cart session and operations
> before exposing financial state. Catching AccessError in the derived-field
> computation preserves ordinary native order reads.
>
> Both added regressions exercise denied behavior and subsequent permitted
> controls, with mocked Merchant requests and explicit zero-I/O assertions.
> They remain within the existing addon test structure.
>
> The earlier possible Duplicated Code finding is resolved through the shared
> immutable operation-native paths tuple. The merge from current main adds no
> competing integration behavior or standards conflict.

**Standards: 0 hard violations, 0 heuristic findings.** Runtime acceptance is
separate from this source-review verdict.

## Spec

Independent review of `e3333ea` against current main `0ddde9a`:

> No remaining source-level spec findings.
>
> Native Revolut tender reads/searches enforce caller-native config/session/order
> visibility and persisted payment/refund identity, while ordinary cash rows
> retain native behavior. Receipt discovery/downloads authorize original financial
> sessions and linked or matching company/UUID return orders. The previously
> unassociated verified-refund case now respects native order denials. Derived
> exposure/payable fields check original cart authority and payment sessions after
> rollover, hiding financial state when denied while preserving native order reads.
>
> The corrections satisfy the requirement to reject actual native-rule denials
> during existing disclosure and to bind historical access to the operation's
> persisted original register/session.
>
> Administrator grant management, explicit manager entitlement, role restrictions,
> authorized colleague sharing, revocation/regrant and trusted cron separation
> remain consistent with the requested policy. No unrelated implementation
> expansion identified. Ticket 36's receipt removal is a separate future change;
> protecting existing receipt paths belongs within ticket 35.

**Spec: 0 remaining source findings.** Review initially found disclosure gaps,
which were reproduced and corrected before this final verdict. Runtime gates
are recorded separately; source review alone does not close the ticket.

## Rollout and human checks

Actual administrator provisioning, deployment, physical employee/device
acceptance, real payments/refunds and final financial reconciliation remain
ticket 12 rollout work. Provision supervisors and till users explicitly before
enabling this candidate: existing registers fail closed until granted. Local
acceptance does not close ticket 12 or authorize live financial operations.

## Completion

Ticket 35 is closed after local implementation, independent source review,
separate verification of both linked findings and the combined acceptance
above. The original ticket 30 report and its baseline/mixed-profile observations
remain intact. Relevant characterization tests now assert the denial regression
and authorized shared-register controls. Ticket 12 stays open for rollout and
physical/financial acceptance. Current-main ticket 36's future receipt removal
is preserved and remains separate work.

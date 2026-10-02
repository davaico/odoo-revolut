# Ticket 30: shared POS session authorization

Assessment date: 2026-10-02. This is an investigation, not a permission fix.
Runtime addon code is unchanged. Every provider request is mocked; no host,
real terminal, account credential or production transaction was accessed.

## Verdicts and owner policy

The owner selected **explicit backend-user access per register, with shared
employee login** on 2026-10-02. Colleague handoff does not imply exclusive
session-opener ownership. A POS role and matching company alone do not satisfy
the selected register policy.

| Original source claim | Verdict | Evidence and limits |
| --- | --- | --- |
| Input 7, `csf_07cbc859664310f0ebdc4d36`: POS user can trigger another session's Revolut terminal | **confirmed against the selected register policy** | A different backend POS user can prepare a native draft and start the configured terminal with no register grant, including when their linked employee is excluded from a nonempty employee list. Native company/ACL checks pass. This is a missing additional register entitlement boundary, not a bypass of native opener ownership. |
| Input 25, `csf_157cf1168e2a1b99dde24367`: A cashier can initiate terminal payments for another open POS session | **confirmed against the selected register policy** | The public `call_kw` start path sends mocked order and intent POSTs under a non-opener backend POS user. The terminal belongs to the requested session; the payment uses a real prepared native draft. An actual register-denying record rule blocks fresh start, so the addon does not bypass that native control on initiation. |

Both findings originate in cancelled, partially covered scan
`95c73550-ed81-4cfe-9e81-b6f2be355a38`, statically triaged at `1d549c1`.
They describe the same absent owner-required entitlement, and can share a
remediation, but retain separate verdicts. Without the owner's stronger policy,
cross-opener initiation alone matches vanilla Odoo and is not evidence of a
native authorization vulnerability. No production exploitation or customer
financial loss was demonstrated. These claims are **not fixed** by this ticket.

An additional concrete recovery bypass is demonstrated: a real global Odoo
record rule denying the caller's register, session and orders blocks native
reads, preparation and start, yet **find, poll, timeout and cancel still succeed**
for an existing operation's known UUID pair. Poll performs a provider read;
cancel sends exactly one mocked cancel POST and reconciles a cancelled outcome.
This path bypasses a configured native boundary, independently of the absence
of a creator-identity comparison.

## Assessed revision and runtime

- Clean assigned worktree `../worktree/ticket-30`, branch
  `codex/30-investigate-shared-pos-session-authorization`, fast-forwarded from
  `080f3fb` to fetched main **`9e1bdd7c64566ccec802b45f818bfbdf99ec4d0d`** before work.
- Addon `19.0.1.10.3`; Odoo package **`19.0.20260908`**, verified with `dpkg-query`.
- Exact native source extracted offline from the pinned test image. Base image
  digest `144175ec0039d52daff1d79f7e51c9281ca3c98b96c830feb49d09764a9f5d7c`;
  rebuilt test image `sha256:b42620d0e400a657415deb62c4e7c584dfef383d93a18776dedba794b36fe8e8`.
- PostgreSQL `16.14-bookworm`, digest
  `64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8`.
- Compose network is `internal: true`; Merchant HTTP guard was explicitly
  verified. Fixture interception rejects unexpected URLs. The environment
  value is `test-only`; provider IDs are randomly generated fixture UUIDs.
- New [characterization tests](../../addons/pos_revolut/tests/test_shared_pos_session_access.py)
  SHA-256: `5967ab097599ac76c6ce86df129c114392f97e60cf03cc16460c3521c2dcf2fa`.
  Registry test mode shares an isolated test transaction across the addon's
  owned cursors. Calls pass through Odoo's public `call_kw` dispatcher as real
  nonsuperuser accounts. Discovery clears the fixture's ORM cache to represent
  a later RPC after the owned preparation/start transaction. This is server
  authorization evidence, not a production HTTP/session or employee-PIN test.

## Native identities and controls

Paths in this table are relative to the pinned package's `odoo/addons/`.

| Identity/control | Exact source | Meaning |
| --- | --- | --- |
| Authenticated backend user | `point_of_sale/security/ir.model.access.csv:4,24–27,35–37`; `security/point_of_sale_security.xml:13–18,46–65,71–80` | POS users can read/write/create sessions, read/write configurations and fully access orders; methods are readable. Managers inherit POS user. Global native rules restrict active companies, with no per-register or opener condition. |
| Session opener | `point_of_sale/models/pos_session.py:37–43` | `user_id` is “Opened By”, defaults to backend UID and is writable; it is not an exclusive owner grant. |
| Shared backend session | `point_of_sale/models/pos_config.py:807–827`; `controllers/main.py:69–78` | Native opening explicitly supports sessions created by another backend user; the controller finds the selected config's open session without an opener comparison. |
| Selected POS employee | `pos_hr/__manifest__.py:9–24`; `models/pos_session.py:9–14`; `static/src/app/services/pos_store.js:58–74,103–109` | Employee POS supports one backend till login and multiple cashiers. `employee_id` and `current_cashier_id` are client-controlled attribution, not independently authenticated backend identities. |
| Employee candidates | `pos_hr/models/pos_config.py:78–85`; `models/hr_employee.py:14–16,34–66` | With a nonempty basic list, company employees are restricted to basic/minimal/advanced lists or the session opener's linked employee. `current_user_id` is computed from the opener (`point_of_sale/models/pos_config.py:440–454`), not the RPC caller. With an empty basic list, advanced/minimal lists alone do not narrow candidates. |
| Employee PIN/role | `pos_hr/static/src/app/utils/select_cashier_mixin.js:35–57,75–125` | Employee selection and PIN comparison occur in the POS client. No `pos_hr` session/config record-rule files are installed. A selected employee does not change the authenticated backend UID. |
| Who edits employee lists | `pos_hr/models/pos_config.py:22–47` | POS user config write access remains; employee command lists are written using sudo after the normal config write. These are not an administrator-owned backend-user entitlement list. |

Native source SHA-256 checks for reproducibility:

| File | SHA-256 |
| --- | --- |
| `point_of_sale/security/point_of_sale_security.xml` | `bc4848a18af2cf2b2b37cfbafcc5afa5b7732e09c89ae4eda170b369322f3ca8` |
| `point_of_sale/security/ir.model.access.csv` | `676eb38b69f8c221d7eddd28650fd5f3bebdd2df98bf75b4f40f75c6a9b5a5d3` |
| `point_of_sale/models/pos_config.py` | `4530fa0bdd32dcfa5a8421e548061066cf349197e81fb6d5dbedde821ac35624` |
| `point_of_sale/models/pos_session.py` | `c9b347e4a38056fc7a3d3b35323543b6900572c35d795cd8da57c91e35a2b7ab` |
| `pos_hr/models/pos_config.py` | `c38f30a839530d4c4f56a4925ede98c823fedd4f26417f9d937341a38e017914` |
| `pos_hr/models/hr_employee.py` | `e9dc490e9806b6aaab7594d9ba402b95871722f85aa15267101e043c687f65da` |

## Access matrix

“Owner-required” describes the selected policy; “observed” describes the
unchanged runtime. Employee exclusion and actual native denial are separate.

| Actor | Owner-required | Prepare/start observed | Find/poll/timeout/cancel observed |
| --- | --- | --- | --- |
| Opener and authorized same-register colleague, separate POS backend accounts | Allow both when explicitly granted | Allow; colleague prepares/starts opener's register | Allow; colleague repeats the same start without provider dispatch, then recovers; opener can recover colleague's operation |
| Shared employee cashier under a granted backend till login | Allow employee switching without requiring employee = opener | Uses the backend UID; employee lists affect POS selection separately | Uses same backend UID; no employee identity is accepted by these payment RPCs |
| Same-company POS backend user with no linked employee/grant | Deny until explicitly granted | Allow natively; tested before linking employees | Allow all four |
| Same-company POS backend user whose employee is explicitly omitted from a nonempty basic list | Deny when backend account has no grant | Allow despite native employee-selection exclusion | Allow all four; no employee PIN supplied |
| Same-company POS user denied register/session/order access by a real global rule | Deny | Native reads, preparation and start raise `AccessError`; zero HTTP | **All four allow with known IDs**; cancellation POST observed |
| Same-company POS manager | Allow only when explicitly granted; no implicit override is approved here | Native allow | Native allow |
| User restricted to another company | Deny | `AccessError` | All four `AccessError`; zero HTTP |
| Multi-company manager with target company inactive | Deny | `AccessError` | All four `AccessError`; zero HTTP |
| Multi-company manager with target company active | Require register grant | Native allow | Native allow |
| Internal user without POS role | Deny | `AccessError` | All four `AccessError`; zero HTTP |
| Permitted colleague, but selected method absent from requested session | Deny inconsistent start | `AccessError`; zero HTTP | This is not a forbidden-user test |
| Permitted colleague with wrong payment-line UUID | Deny unrelated lookup/control | Not a fresh-start case | Find returns false; poll/timeout/cancel raise `AccessError`; zero HTTP |

The two permitted colleague tests exercise handoff and reload/coalescing, not
merely a payment created by that same user. “Authorized” is fixture policy
intent: no production backend-register grant field exists yet. Successful
employee switching in the native browser/PIN flow is source evidence; the
experiment does not claim to have tested that browser flow or a deployed policy.

## Addon paths and identifier preconditions

- **Fresh start:** `_validate_revolut_pos_request()` in
  `models/pos_payment_method.py:247–295` checks POS group, method read access,
  active company, same-company open session, method membership and currency.
  `models/cart_authorization.py:271–314` checks native draft write access and
  identity; `_admit()` repeats that check before financial reservation. Those
  checks block the synthetic native denial on start. They do not check a
  backend-user register grant or the employee list.
- **Recovery:** `revolut_find_payment()` (`pos_payment_method.py:859–886`) searches
  operations with sudo after group/method/company/UUID checks.
  `_read_revolut_operation_owned()` (`:490–532`) similarly uses sudo and checks
  method/company and supplied UUID pair. `revolut_poll_payment()` (`:888`),
  `revolut_mark_timeout()` (`:964`) and `revolut_cancel_payment()` (`:938`) reach
  that helper. They do not recheck native session/config/order access. This is
  why a register-level native deny can be bypassed on recovery.
- **Fresh-start reachability:** no victim operation ID or secret is needed.
  Native readable configurations/sessions expose session, method and currency
  IDs. A POS user can create their own ordinary priced draft and tender UUIDs,
  prepare it through the native-cart boundary, then start that register's method.
  Amount authority, credential authority and terminal reservation still apply.
- **Existing-operation discovery:** the public test uses `pos.config.search_read`
  to read the current session and method IDs, `pos.order.search_read` for draft
  ID/UUID, then `pos.order.revolut_checkout_state()` for the authority's tender
  UUID and method ID. `revolut_find_payment()` returns the operation ID, completing
  the prerequisite set for poll/timeout/cancel. All calls use the excluded
  same-company cashier; direct operation-model search raises `AccessError`.
  These UUIDs are not an authorization secret under native company-wide access.
- **Revoked or custom-denied users:** if the order is also hidden, the above
  discovery chain is blocked after denial. Recovery then requires previously
  retained IDs from legitimate access, a shared browser/session, or another
  disclosure. The record-rule reproduction deliberately supplies known fixture
  IDs; it does not prove new discovery through an order-denying rule. If a
  deployment only denies session/config but leaves orders visible, investigate
  that deployment's discovery path separately.

## Narrow remediation proposal

Use an administrator-managed backend-user grant on the register (`pos.config`),
checked server-side with native read access on config/session/order plus active
company and POS role. Preserve shared employee login and multiple explicitly
granted colleagues; do not introduce a session-opener-only rule. Native POS
users already have config write rights, so protect grant mutation independently
of those rights. Do not repurpose the mutable employee lists, `employee_id` or
browser `current_cashier_id` as trusted identity. Managers need an explicit
register grant for cashier RPCs under this policy; design any audited recovery
override as a separate explicit capability rather than silently granting it.

Check the same boundary before preparing/admitting a new payment, revealing
checkout state, finding operations, reading provider status, timing out or
cancelling. Resolve historical recovery against the operation's frozen original
register/session rather than the method's current configuration. A method can
be shared across registers, so method read access alone is insufficient.
Extend the equivalent boundary to refund and manager financial entrypoints
when scoping the remediation, while preserving deliberately privileged cron
reconciliation of existing financial evidence after a cashier grant is revoked.
Never use revocation to release a reservation, create a replacement charge,
erase evidence or stop safe background reconciliation.

The follow-up must cover two allowed backend users plus shared employees,
nonmember same-company users, no-employee backend users, manager permissions,
company context changes, register rules, method sharing, reload/idempotent
coalescing, grant revocation during an existing attempt, late success and
historical/closed-session recovery. Grant create/write/copy/import and migration
need server-authority tests. Existing registers require an explicit reviewed
allowlist; do not populate every same-company cashier by default. Preserve this
characterization as a baseline and change its expectations only with the fix.

Ticket 30 closes as a source/runtime investigation with the owner policy
resolved and verification recorded. The confirmed policy gap and recovery bypass remain remediation work
before the selected register model can be represented as enforced. This report
does not close ticket 12's physical-device or financial acceptance gates.
The concrete follow-up is [ticket 35](../tickets/closed/35-enforce-shared-register-authorization.md),
originally filed for scope/sequence triage. The owner subsequently approved
its agent brief on 2026-10-02; that approval does not mark either finding fixed.

## Exact verification commands

Run from `../worktree/ticket-30`. These commands use disposable databases and
the internal Compose network, not staging:

```bash
git fetch origin main
git merge --ff-only origin/main
git rev-parse HEAD
docker compose --project-name ticket30-access --file compose.yaml build odoo
docker compose --project-name ticket30-access --file compose.yaml up --detach --wait db
docker compose --project-name ticket30-access --file compose.yaml run --rm --no-deps --entrypoint dpkg-query odoo --show '--showformat=${Version}' odoo
docker compose --project-name ticket30-access --file compose.yaml run --rm --no-deps --entrypoint python3 odoo /opt/odoo-test-guard/verify_merchant_http_guard.py
docker compose --project-name ticket30-access --file compose.yaml run --rm --no-deps --entrypoint python3 odoo -c 'import websocket'
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_access --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --init pos_revolut,pos_hr --test-tags /pos_revolut:TestSharedPosSessionAccess
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_access --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --update pos_revolut --test-tags /pos_revolut:TestSharedPosSessionAccess
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_full --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --init pos_revolut,pos_hr,pos_restaurant --test-tags /pos_revolut,/pos_revolut_restaurant
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_full --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --update pos_revolut --test-tags /pos_revolut:TestRevolutReceiptUi,/pos_revolut:TestRevolutManagerUi,/pos_revolut:TestRevolutRefund.test_public_unclaimed_return_cancellation_remains_allowed
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_retail --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --init pos_revolut --test-tags /pos_revolut
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_retail --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --init pos_restaurant --test-tags /pos_revolut_restaurant
docker compose --project-name ticket30-access --file compose.yaml run --rm odoo --database ticket30_retail --stop-after-init --workers 0 --log-level warn --log-handler odoo.tests.result:INFO --update pos_revolut --test-tags pos_revolut_restaurant
node addons/pos_revolut/static/tests/revolut_payment_state.test.mjs
python3 -m unittest discover -s tests -v
docker run --rm --network none --volume /home/gary/delivery/Tek2/stage/odoo-rev/worktree/ticket-30:/repo:ro --workdir /repo --entrypoint python3 odoo-revolut-test:19.0.20260908-chrome153 -m unittest discover -s tests -p test_pdf_probe.py -v
python3 -m compileall -q addons/pos_revolut/tests/test_shared_pos_session_access.py
git diff --check
docker compose --project-name ticket30-access --file compose.yaml down --volumes --remove-orphans
```

The initial narrow install exposed a fixture URL mismatch, corrected to the
order-scoped intent endpoint. A second run exposed a stale fixture ORM cache
during discovery; clearing it before the later RPC corrected the reproduction.
Final narrow upgrade: **12 tests, zero failures/errors**, including `pos_hr`
employee exclusion. All five cashier entrypoints are exercised with both
allowed users and forbidden company/non-POS users. The actual register-rule
case demonstrates four recovery bypasses and a rejected fresh start.

The all-at-once `pos_revolut,pos_hr,pos_restaurant` profile returned **four
failures, zero errors out of 380 tests**. Three failures are backend browser
tours with an undefined `@pos_restaurant/app/screens/split_bill_screen/split_bill_screen`
asset: both `TestRevolutReceiptUi.test_admin_order_receipt_links_download_*`
cases and `TestRevolutManagerUi.test_manager_configures_and_checks_terminal_in_browser`.
The fourth is the unchanged retail refund test
`TestRevolutRefund.test_public_unclaimed_return_cancellation_remains_allowed`,
whose assertion finds the draft still present. Repeating only the existing
receipt/manager classes and that refund method, **without running the ticket 30
class**, reproduced the same four failures out of ten tests. This profile is
not a green full-suite result and these failures were not fixed in this
investigation. The repository runner tests base retail before separately
installing Restaurant; that documented sequence is assessed separately below.

Documented retail install: **375 tests, zero failures/errors** (one expected
`pos_hr`-only skip; that case passed in the separate employee-POS narrow run).
SQL confirmed `pos_revolut:installed`, with `pos_hr`, `pos_restaurant` and
`pos_revolut_restaurant` uninstalled in that retail database before the separate
Restaurant phase. Separate Restaurant phase: **nine tests, zero failures/errors**, including
browser checkout/guards/startup. Lifecycle: **75 passed**.
Local deployment/PDF suite: **39 tests, 36 passed, three PDF-runtime tests
skipped** because the host Python lacks the supported renderer/parser runtime.
Rerunning the PDF file inside the pinned offline test image: **all seven pass**,
including actual body/header/footer rendering and malformed output rejection.
Python syntax compilation and whitespace checks passed; no separate static
typechecker is configured. The initial `/pos_revolut_restaurant` module selector
ran zero tests because these checks are tagged inside `pos_revolut`; the final
`--test-tags pos_revolut_restaurant` update ran the actual nine checks.
Independent Standards/Spec review against pinned main is recorded below.

Native source extraction used:

```bash
docker run --rm --network none --entrypoint tar odoo-revolut-test:19.0.20260908-chrome153 -C /usr/lib/python3/dist-packages/odoo/addons -c point_of_sale pos_hr hr > /tmp/ticket-30-odoo-source.tar
mkdir -p /tmp/ticket-30-odoo-source
tar -xf /tmp/ticket-30-odoo-source.tar -C /tmp/ticket-30-odoo-source
```

The test seam is the exact public start/find/poll/timeout/cancel entrypoints
already specified in the ticket, with public native checkout preparation and
identifier discovery. Because runtime behavior must remain unchanged here,
these are characterization assertions rather than a red/green permission fix.

## Review identity

Reviewed investigation commit: **`8f63c06ee8040705d7a26be0f32abcf41dbc418c`**.
Fixed point: `9e1bdd7c64566ccec802b45f818bfbdf99ec4d0d` (fetched main).
Two independent review agents used
`git diff 9e1bdd7c64566ccec802b45f818bfbdf99ec4d0d...HEAD` and the commit list
`8f63c06 test(pos): investigate shared register authorization`.
The final follow-up commit records review results only; the tested Python file
and assessed runtime remain unchanged. Disposable containers, database tmpfs
and test-data volume were removed after verification.

## Standards

No findings. Tests, evidence and tracker changes follow the repository's
documented boundaries and lifecycle rules. Mocked public calls, isolated
registry test mode, explicit failure/skip reporting and the preserved
`ready-for-agents/.gitkeep` meet the standards. The committed test SHA-256
matches the recorded reproduction. No actionable baseline smells were found.

## Spec

No findings. The access matrix distinguishes identities, the selected policy
and actual native controls. The public reproduction separates initiation,
recovery, method membership and identifier discovery. Both original findings
have qualified verdicts; known-ID, browser/PIN and deployment proof gaps are
preserved. Closure concerns the investigation, with permission changes deferred
to the separately triaged ticket 35.

Review totals: **Standards 0; Spec 0; no worst issue on either axis**.


## Remediation follow-up — 2026-10-02

[Ticket 35 verification](ticket-35-register-authorization.md) records explicit
register grants and independently verified fixes on source `e3333ea` with
mocked acceptance. The characterization tests on that candidate now assert the
fixed boundary and legitimate shared-register controls. This dated follow-up
preserves the original baseline observations, commands, hashes and mixed-profile
failures above; it does not turn those earlier failures into passing evidence
or close ticket 12's deployment/device gate.

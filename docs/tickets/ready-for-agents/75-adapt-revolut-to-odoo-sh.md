# 75 — Adapt Revolut to Odoo.sh Enterprise 18

**State:** open

**Category:** feature / deployment compatibility

**Triage:** ready-for-agent

**Work branch:** `feat/v18_rev`. Base task branches on its latest reviewed
revision and integrate back there. Hosted validation targets
`staging/18-enterprise`; `18.0` automatically deploys production and must remain
untouched until the candidate is production-ready.

**Dependencies:** No outstanding ticket blocks starting this adaptation.
Preserve the corrected Odoo 18 baseline and existing accepted limitations.
Do not change the status of other acceptance or Odoo 19 tickets as part of this
specification.

**External gates:** Hosted acceptance requires authenticated Odoo.sh access,
verification of the Enterprise subscription/database registration, and a usable
staging build. Production release requires the staging evidence and a reviewed
production-ready PR. Final live acceptance requires the owner's terminal and
credentials. These gate the corresponding deployment steps, not local work.

**Specification agreed:** 2026-10-30. The owner confirmed scope and the testing
boundaries in the planning chat. This ticket records requirements, not completed
implementation or hosted verification.

## Problem Statement

The client has created an Odoo 18 Enterprise project on Odoo.sh with production
and staging branches. The client reports that the instance starts and the
Revolut addon is available but remains to be installed. They need to finish
Enterprise registration, install and validate the addon on staging, correct
Payment Method labels and documentation, and make credential handling work
reliably on this hosting platform.

The current addon resolves credentials from server environment variables.
Its existing company authority and payment verification protections must be
preserved, but it has no established Odoo.sh test-copy protection. A copied
database must never charge or refund through production Revolut credentials,
including through scheduled reconciliation or a connection check.

The result must remain a reusable addon: unrelated customers install it in
their own Odoo databases with their own accounts and terminals. Companies
managed within one database must retain separate credentials and transactions.
This is not a one-company or one-terminal product.

## Solution

Deliver the client's four requested outcomes within the existing addon:

1. Verify the appropriate Enterprise database registration and install the
   addon on staging with repeatable instructions.
2. Correct Revolut labels/help in the Payment Method form and update the
   installation and operating documentation for Odoo.sh.
3. Add administrator-managed, company-specific database credentials while
   preserving environment-variable installations, and prevent real Revolut
   access from Odoo.sh staging/development copies.
4. Validate installation, permissions, restarts, scheduled reconciliation and
   database copies on Enterprise/Odoo.sh, then prepare the production-ready PR
   into `18.0`.

After production deployment, perform the agreed small payment and refund before
opening Revolut payments to cashiers. Reuse existing accepted physical-terminal
evidence; do not repeat the entire hardware acceptance campaign.

## User Stories

1. As a deployment administrator, I want to verify the Enterprise subscription and database registration, so that the intended database is registered correctly without incorrectly registering a staging copy as another production database.
2. As a deployment administrator, I want to install the addon on Odoo.sh staging, so that I can validate the hosted integration before production deployment.
3. As a deployment administrator, I want repeatable staging setup instructions, so that a new staging build does not depend on undocumented manual configuration.
4. As an existing Odoo customer, I want installation to preserve native business data, so that adding Revolut does not disrupt my existing POS operations.
5. As a POS manager, I want clear Revolut field labels and help, so that I can configure a payment method without guessing what each field means.
6. As a system administrator, I want to enter a Revolut API key in a restricted Odoo form, so that Odoo.sh setup does not depend solely on custom server environment variables.
7. As a system administrator, I want to replace credentials safely, so that rotation does not silently redirect pending payments or historical refunds to another account.
8. As a system administrator, I want credentials bound to the correct company and Revolut environment, so that one company's configuration cannot select another company's authority.
9. As an existing self-hosted customer, I want environment-variable credentials to keep working, so that the hosting adaptation does not force me to change deployment methods.
10. As a POS manager, I want to select an authorised credential reference without obtaining its secret, so that I can configure permitted registers without administering API keys.
11. As a cashier, I want the POS browser to receive no API credentials, so that accepting payments does not expose merchant secrets.
12. As a company administrator, I want ordinary users blocked from reading or modifying another company's credential configuration and transactions, so that company boundaries remain effective.
13. As an independent customer, I want to install the addon with my own Revolut account, so that I do not depend on another customer's credentials, terminals or database.
14. As an organisation operating several companies, I want each company to use its own authorised payment methods, so that payments and refunds stay with the right business.
15. As a business operating several terminals, I want each configured payment method to address its intended terminal, so that one register does not dispatch to another terminal accidentally.
16. As a tester, I want staging and development builds blocked from real Revolut access, so that testing cannot charge, refund, cancel or otherwise affect production transactions.
17. As a tester, I want those protections to apply when the addon is first installed after a database copy, so that safety does not depend on the addon having existed during neutralization.
18. As a deployment administrator, I want copied live credentials cleared during neutralization, so that staging does not retain usable production keys through the normal copy lifecycle.
19. As a deployment administrator, I want background jobs and connection checks subject to the same environment policy as checkout, so that alternate execution paths cannot bypass the restriction.
20. As a tester, I want an understandable explanation when an operation is blocked, so that I can distinguish expected test-environment restrictions from a broken terminal.
21. As a cashier, I want a sale confirmed only after the underlying payment is verified successful, so that a completed payment intent or a network interruption cannot produce an unpaid completed order.
22. As a cashier, I want declined, failed, cancelled, interrupted and timed-out attempts handled explicitly, so that I can recover without accidentally issuing a replacement charge.
23. As a POS manager, I want full and partial refunds tied to their original transaction, so that reimbursement remains correct after credential or hosting changes.
24. As a deployment administrator, I want pending payments and refunds to survive a restart, so that worker recycling does not lose transaction identity or permit duplicate operations.
25. As a POS manager, I want scheduled reconciliation to recover uncertain outcomes under Odoo.sh scheduling constraints, so that delayed jobs do not invalidate payment safety.
26. As a support operator, I want useful transaction references and sanitised errors, so that I can investigate problems without exposing keys or sensitive cardholder information.
27. As a maintainer, I want mocked regression tests and actual hosted lifecycle evidence, so that a successful build is not mistaken for proof that the risky behavior works.
28. As a release owner, I want development and staging changes kept away from `18.0` until ready, so that automatic deployment cannot publish unfinished work.
29. As a release owner, I want a small production payment and refund after deployment, so that the actual hosted credential and terminal path is verified with limited live activity.
30. As an existing Community 18 or 19 customer, I want the current supported features preserved, so that adding Enterprise/Odoo.sh support does not reduce my integration's capabilities.

## Implementation Decisions

- Keep the existing `pos_revolut` addon and established Odoo model, view and
  security conventions. Extend credential administration, credential resolution,
  outbound Revolut access, neutralization, relevant views and deployment
  documentation. Do not create an Enterprise-only fork or unrelated framework.
- Use `feat/v18_rev`, whose reviewed baseline is version `18.0.1.0.4`; record
  the exact candidate revision used for each new verification. The earlier
  proposal to work on `feat/v18` is superseded. Do not transplant the older
  `.1` branch over the corrected candidate.
- Keep the maintained Community 18 and 19 scope and ADR parity commitments.
  Coordinate relevant shared fixes across supported versions with version-specific
  verification; Odoo 18 results alone do not establish Odoo 19 compatibility.
- Extend the existing administrator-owned credential authority with a restricted
  database-backed secret source. Only system administrators administer keys;
  POS managers retain permitted configuration through authorised references.
  Keys remain absent from POS loading, ordinary-user reads/exports, logs and
  sanitised errors. A masked widget is not an access-control mechanism.
- Retain the environment-variable source for existing installations. Resolve
  the configured source consistently for connection checks, payments, refunds
  and reconciliation, including existing preflight checks. Missing or invalid
  credentials must stop safely; do not silently fall back to a different
  merchant account or environment.
- Preserve immutable company/environment/authority bindings and the references
  frozen on existing operations. Credential replacement must not reassign
  historical operations. Keep recovery and refund behavior explicit when a
  historical credential is unavailable or revoked; never create a replacement
  financial operation merely to bypass that condition.
- Database-backed keys are stored in the production database and its backups.
  Restricted fields and form masking do not imply application-level encryption.
  System administrators remain trusted across their installation. Unrelated
  customers use separate databases; multi-company access rules do not create
  isolation from a shared database's system administrator.
- Apply one consistent server-side environment policy to all outgoing Revolut
  paths. Ordinary Odoo.sh staging and development must reject production API
  access before HTTP dispatch, including payment/refund creation, cancellation,
  status retrieval, connection checks and privileged reconciliation jobs.
  Preserve allowed mocked and supported sandbox workflows.
- Use Odoo.sh's runtime stage information together with copy neutralization.
  Unrecognised Odoo.sh stages must not implicitly enable real operations.
  Preserve explicit self-hosted production operation where Odoo.sh stage
  information is absent; do not equate every self-hosted installation with an
  Odoo.sh production instance.
- Clear live database keys and disable copied live-operation configuration
  through the addon's neutralization integration. Runtime protection must also
  work when the addon is installed after the staging copy was created, when
  someone re-enters a key, or when a matching environment-variable key exists.
  ORM record-copy flags alone do not protect whole database copies.
- Preserve copied financial history and uncertain attempt identities. Blocking
  external access must not fabricate a successful payment/refund or reset an
  uncertain attempt into an apparently safe retry. No staging override for
  production Revolut access is part of this scope.
- Reuse durable payment/refund attempts and existing reconciliation behavior.
  Odoo.sh worker recycling must not lose identity or depend on a persistent
  custom daemon. Scheduled reconciliation is a recovery mechanism, not a
  promise of seconds-level cron execution during checkout.
- Inspect the actual Payment Method form before choosing final wording. Align
  labels, help and documentation with the existing domain vocabulary and
  supported UI languages; do not invent a broader translation or UI redesign
  project. Distinguish a Revolut payment receipt from a POS sales receipt and
  an accounting invoice wherever relevant.
- Verify registration status before changing it. Do not assume the production
  Enterprise subscription must be independently registered on staging. Record
  the repeatable staging installation/configuration steps, since staging builds
  may replace earlier manual work from a fresh production copy.
- Prepare a production-ready PR into `18.0` only after staging validation.
  Include payment-flow impact, test evidence, configuration/credential steps,
  module upgrade requirements and recovery instructions. Code promotion does
  not automatically copy staging database configuration into production.

## Testing Decisions

- The owner explicitly confirmed these test boundaries on 2026-10-30: existing
  Odoo payment/refund and credential tests with mocked Revolut HTTP, focused UI
  checks, hosted staging lifecycle verification, and the small production
  payment/refund after deployment.
- Prefer the highest existing application boundary: invoke real Odoo model/RPC
  operations as representative users, with the external HTTP transport mocked.
  Assert observable permissions, operation states, persisted references,
  selected company/terminal and dispatch counts. Do not mock away the credential
  resolver or environment policy whose behavior is under test.
- Extend existing credential-authority and Payment Method tests. Prior art
  already exercises cross-company reference selection, direct known-record
  access, administrator-only management, connection checks, POS payload secrecy
  and credential rotation. Add both credential sources, denied secret access
  and safe missing-key behavior at these same boundaries.
- Cover at least two companies and multiple configured terminals, including a
  user with access to both companies. Verify selection uses the operation's
  bound company/terminal rather than browser input or the current company alone.
  Use synthetic independent-installation fixtures to rule out customer-specific
  account or terminal assumptions.
- Extend existing payment/refund and reconciliation tests for stage restrictions.
  Exercise both the ordinary request transport and the separate connection-check
  transport. Assert zero production HTTP dispatch from staging/development,
  including privileged jobs, copied pending operations, re-entered keys and
  environment-backed credentials. Verify production and supported self-hosted
  operation still work with mocked responses.
- Exercise actual neutralization with synthetic live-looking credentials and
  pending history, then inspect the resulting database and invoke the public
  operations. Separately cover first installation after neutralization and
  repeated neutralization. A unit test of an isolated stage predicate is
  insufficient evidence of copied-database protection.
- Reuse existing payment, refund, native POS browser and recovery fixtures for
  success, decline, failure, cancellation, interruption, timeout, safe retry,
  full/partial refunds and representative Restaurant/split-tender/tip behavior
  affected by the change. Preserve underlying-payment verification, authorized
  cart constraints and the separation of terminal-selected tips from the base
  payment allocation.
- Use focused native UI checks for credential administration, ordinary-user
  visibility, Payment Method wording and understandable blocked-environment
  feedback. Add new test infrastructure only if an observable behavior cannot
  be exercised through these existing boundaries.
- Reuse install/upgrade and restart-recovery fixtures. Verify installation into
  an existing populated database, upgrade from the reviewed baseline, retention
  of environment-backed configuration and financial history, and recovery of
  the same attempts after process restart without duplicate dispatch.
- On Odoo.sh Enterprise staging, record the exact build and addon revision;
  verify installation, administrator/POS permissions, key persistence across
  workers and restarts, copy neutralization and rebuild behavior. Use synthetic
  credentials and mocked traffic for production-path probes. No automated test
  or staging acceptance step may contact the real Merchant API or terminal.
- Explicitly invoke or enable the relevant scheduled jobs in the controlled
  staging setup and record their results. Staging crons may start disabled,
  staging does not automatically run the unit suite, and a green build alone
  is not acceptance. Test delayed reconciliation rather than assuming the
  addon's one-minute schedule is guaranteed by Odoo.sh.
- After production deployment, the owner performs or coordinates the agreed
  small real payment and refund on the intended company/terminal. Record
  verified final provider outcomes and matching Odoo records. A pending refund
  remains pending evidence; do not create another refund to make the check pass.
  Keep live financial references in restricted acceptance records.
- Run the narrowest meaningful regressions during implementation, followed by
  the applicable integration and hosted release gates. Record exact commands,
  results, artifact identity and limitations. Reuse earlier accepted hardware
  evidence without claiming it validates the changed hosted environment.

### Acceptance criteria

- [ ] The intended Enterprise database registration is verified and staging
  installation is demonstrated with repeatable setup instructions.
- [ ] Payment Method labels/help and Odoo.sh documentation are corrected against
  the actual interface; installation preserves native business data.
- [ ] System administrators can configure and rotate database-backed keys;
  existing environment-variable installations remain functional.
- [ ] Secret access, company authority and terminal selection are verified with
  multiple companies/terminals and representative user roles.
- [ ] Staging/development cannot issue production Revolut requests through any
  interactive or background path, including first installation after cloning.
- [ ] Copy neutralization removes live secrets without corrupting transaction
  history; runtime protection survives reconfiguration and credential presence.
- [ ] Hosted restart, rebuild and scheduled-reconciliation behavior is exercised
  with retained operation identities and no duplicate financial dispatch.
- [ ] Relevant mocked regression and focused UI checks pass for the exact
  candidate; supported-version impact and remaining limitations are recorded.
- [ ] A production-ready PR into `18.0` includes staging evidence and explicit
  configuration, upgrade and recovery instructions; no premature production push.
- [ ] After release, the bounded production payment and refund reach verified
  final outcomes, or any pending/failed outcome remains explicitly unresolved.

## Out of Scope

- An Enterprise-only fork, a new payment provider architecture, a separate
  hosted multi-tenant service, or hard-coded customer/company/terminal settings.
- Replacing the existing financial state model, weakening payment verification,
  introducing new payment/refund features, or migrating another integration's
  financial history.
- Permitting real Revolut operations on ordinary staging/development, bypassing
  environment protections, or an extended new live-terminal test campaign.
- A custom encryption/key-vault platform or claims that UI masking encrypts
  database secrets. Existing hosting and backup controls remain relevant.
- Broad UI redesign, comprehensive new localisation, or unrelated ticket fixes.
- Odoo 19 Enterprise/Odoo.sh certification. Existing Community 19 maintenance
  obligations remain in force, including relevant coordinated shared fixes.
- Publishing credentials, private project URLs, financial references or the
  shared login password in tickets, source code, logs or public documentation.
- Implementing the addon, registering databases, installing on hosted systems,
  opening a PR or deploying production merely by publishing this specification.

## Further Notes

- Keep the work limited to the client's four requests. The owner approved the
  scope, administrator-managed database keys, separate customer databases,
  multi-company support, the production branch boundary and limited live
  acceptance. The final branch choice is `feat/v18_rev`.
- The local corrected baseline is `18.0.1.0.4`; hosted build identity and
  subscription state have not been verified during specification work.
  Existing accepted physical-test limitations remain accepted, and unrelated
  historical pending operations must not be retried as part of the new smoke
  test. Keep private evidence separate from this public specification.
- Odoo.sh custom persistent environment-variable injection across all workers
  and rebuilds was not established from the official material inspected. This
  is an unverified hosting capability, not a claim that it is forbidden.
- Relevant official sources: [Odoo.sh build lifecycle](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/builds.html),
  [branch behavior](https://www.odoo.com/documentation/18.0/administration/odoo_sh/getting_started/branches.html),
  [Odoo.sh FAQ and runtime stages](https://www.odoo.sh/faq?expand=1),
  [Odoo 18 neutralization implementation](https://github.com/odoo/odoo/blob/18.0/odoo/modules/neutralize.py),
  [native restricted-key precedent](https://github.com/odoo/odoo/blob/18.0/addons/pos_adyen/models/pos_payment_method.py)
  and [Odoo.sh runtime/scheduled-action guidance](https://www.odoo.com/documentation/18.0/administration/odoo_sh/advanced.html).
- Before implementation, recheck the exact target environment where needed.
  In particular, neutralization only processes applicable installed modules;
  first installation after a copy needs independent runtime protection.
- Verification at specification publication is limited to ticket structure,
  index consistency and patch hygiene. No addon test, live request, hosted
  registration, deployment or production operation is claimed by this ticket.

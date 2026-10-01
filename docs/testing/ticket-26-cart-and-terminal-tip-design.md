# Ticket 26 design verification

2026-09-30. Documentation-only contract; implementation remains ticket 27.

## Revisions and boundaries

- Reviewed main: `4adf1ab9f45605dfc023b7544189c78d5d29a057`.
- Assigned branch baseline: `080f3fb0a72df80fa772bb72b31eeba4fdc7d965`, already containing main with an identical tracked tree.
- Final reviewed design: `ece85a85a8f61839dd84f65746a7e88058fbd72d`. Later amendments add this evidence and its ticket link only.
- Source-inspection image: `sha256:b12192e6a72fc722a7ebbe1b93e3c04ce06700bc502f79a3a98e4cf23e3ca1aa`; package `19.0.20260908`. The cached test rebuild produced image `sha256:94511f91aae9d072ef45f4ff6f067e25508a59b93b6adffe15af8fb24812913a` from the repository test Dockerfile. Source archive and official OpenAPI hashes are in [the contract](../revolut-cart-authorization.md).

## Checks

| Command / check | Result and limit |
| --- | --- |
| `node --test addons/pos_revolut/static/tests/revolut_payment_state.test.mjs` | Passed; Node reports one test file. |
| `python3 -m unittest discover -s tests -v` | 29 passed. |
| `ODOO_REVOLUT_TEST_PROJECT=odoo-revolut-ticket26 ./scripts/test-addon` | Exit 0; final Odoo result: 265 tests, 0 failures, 0 errors. Raw local log: `/tmp/ticket26-full-suite.log`. |
| Full-suite isolation | Disposable PostgreSQL, internal Docker network and Merchant HTTP guard; package and browser transport checks passed. Real API requests were blocked. |
| Markdown links and tracker | All changed-file local links resolve; reviewers additionally checked 44 relative links. Tracked `ready-for-agents/.gitkeep` remains. `git diff --check` passed. |
| Typechecking / TDD / prototype | Not applicable to documentation-only edits. No implementation or speculative prototype created; future public RPC/ORM/checkout/concurrency acceptance seams are specified for ticket 27. |

The default full suite is the fresh-install **retail** phase. Restaurant-only classes intentionally skip when `pos_restaurant` is absent. No separate Restaurant install, schema upgrade or new design behavior was tested by ticket 26, because no addon/schema/asset changed. The full suite protects the existing baseline and is not proof that the proposed authorization, report-tip projection, tax representability, rounding or concurrency contract is implemented. Ticket 27 must execute its complete matrix and appropriate install/upgrade/Restaurant checks. Target-terminal zero/nonzero tips, actual report identity/units and latency remain ticket 12 release acceptance.

No staging mutation, real charge/refund, terminal setting change, provider message or deployment occurred. Source extraction and public official-document downloads were read-only; all automated payment calls in the existing suite were mocked.

## Standards

No documented-standard breaches or baseline code smells found. Domain terms use root `CONTEXT.md`; the decision uses `docs/adr/`. Ticket closure/index/dependency wording and canonical triage follow the repository tracker rules. The ready folder marker is preserved. The reviewer requested final test/review evidence; this record supplies it.

Final Standards findings: **0**.

## Spec

Two initial P2 contract gaps were corrected: a covered rounded cash target cannot be reopened by declaring a card slot without a real locked cash correction; and terminal-tip tax/price precision must prove exact representability or fail configuration before dispatch. The final review at `ece85a8` passes with no remaining material findings. Frozen base rounding plus exact collected tip is also explicit (10.00 + 0.03 settles as 10.03).

The documentation satisfies ticket 26 and incorporates the owner's required terminal popup, customer-tip/provider-limits policy, asynchronous evidence waiting and authenticated manager override approval. No scope creep identified. Ticket 27 must implement the contract; physical terminal/report compatibility remains a release gate.

Final Spec findings: **0**. Both reviews used `git diff 080f3fb0a72df80fa772bb72b31eeba4fdc7d965...HEAD` and independent agents; initial findings remain recorded above rather than hidden.

## Self-evaluation

Overall: **4.2/5** across five axes; no critical issue. Deliver the reviewed design.

| Axis | Score | Evidence / improvement |
| --- | --- | --- |
| Accuracy | 4 | Pinned Odoo source and full official YAML establish the selected seams/fields. Applying the general report contract to actual terminal payments is an explicit inference; confirm the specified device/units/latency cases before release. |
| Completeness | 5 | All ticket 26 criteria map to source evidence, chosen authority, atomic tender calculations, terminal-tip rules, lifecycle/legacy behavior, state table and ticket 27 matrix; all material owner decisions are recorded. |
| Clarity | 4 | Glossary, ADR and tables expose the decision. The detailed pricing and projection protocol is dense; implementation can turn those clauses into named interfaces and operator guidance. |
| Actionability | 4 | Concrete RPC/ORM boundaries and regression expectations unblock ticket 27 after integration. Native pricing parity and the complete tip/receipt/refund slice may still require the specified concrete dependency breakdown. |
| Conciseness | 4 | Short ADR links the detailed contract; some rules recur in the matrix to make acceptance self-contained. Future implementation docs can replace repeated prose with executable tests. |

Improvements by impact: verify the explicit terminal/report release cases; keep ticket 27's pricing/projection interfaces and acceptance evidence directly traceable to the matrix. Self-check: the scope includes the user's actual terminal-tip intention, makes no remediation claim, and records the owner-approved waiting behavior instead of silently substituting Odoo pre-entry.

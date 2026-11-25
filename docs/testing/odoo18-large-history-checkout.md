# Odoo 18 checkout latency on a large POS history

On 2026-11-24 we reproduced history-wide order reads when a cashier selected Revolut on a one-line draft. The tender had no linked charge or refund. Odoo found the payment by index, then PostgreSQL evaluated its access rules against historical orders. Repeated reads of that tender accounted for most of the SQL time in all three reported methods.

## Measurements

The client reported 71–110 seconds for preparation, 9–11 seconds for checkout state, 29.6 seconds for Revolut sync and 1.8 seconds for cash sync on an Odoo.sh staging copy. They supplied aggregate timings. The following measurements come from an independent synthetic database.

| Cashier method | Local elapsed | Local SQL time | Statements | Payment visibility reads | SQL time in those reads |
| --- | ---: | ---: | ---: | ---: | ---: |
| `revolut_prepare_payment`, fresh Revolut draft | 9.51 s | 9.38 s | 191 | 16 | 9.23 s |
| `revolut_checkout_state`, before preparation | 1.46 s | 1.44 s | 35 | 2 | 1.37 s |
| `sync_from_ui`, Revolut draft update | 12.95 s | 12.70 s | 223 | 26 | 12.58 s |
| `sync_from_ui`, cash draft update | 0.40 s | 0.23 s | 277 | 26 | 0.075 s |

We used the published `18.0.1.0.9` addon at `79b433b`, pinned Odoo Community `18.0-20261015` and PostgreSQL 16.15. Enterprise base and integration target were `staging/18-enterprise` at `39b6ced`. Its models and security rules matched the release. The database held about 530,000 orders and 580,000 payments in one company, with historical orders spread across 530 closed sessions. Each test cart contained one product and one tender on the same open register. The calls ran as a POS cashier with a register grant, with provider requests blocked. Wall time covers the server method and SQL time is the sum of cursor execution times. The baseline used JIT off and zero parallel query workers. Hardware, data distribution, installed extensions and PostgreSQL settings on the client's instance remain unknown.

## Where the time went

Both the register rule on `pos.payment` and the addon's native tender visibility domain allow ordinary cash payments through a cheaper branch. A Revolut tender requires the cashier's register grant and visibility of its native order, session and configuration. Odoo expresses several of those checks as membership in subqueries over `pos_order`. Constraining the outer payment lookup to one draft still allows PostgreSQL to build those large sets. Preparation repeatedly reloads the draft's payments as it locks and prices the cart. Checkout state and sync both serialize the payments through native `read_pos_data`. [Register rule](../../pos_revolut/security/revolut_reconciliation_rules.xml) · [Visibility domain](../../pos_revolut/models/register_worklists.py) · [Locking and invalidation](../../pos_revolut/models/return_allocation.py) · [Preparation and checkout state](../../pos_revolut/models/cart_authorization.py)

In an `EXPLAIN (ANALYZE, BUFFERS)` of the actual cashier SELECT, PostgreSQL produced the following plan.

- The outer index scan used `pos_payment__pos_order_id_index` and returned one payment.
- The register-grant subquery sequentially scanned 530,001 order rows. Another subquery used the session index 531 times, returning about 998 orders per loop. The charge/refund subqueries were present but skipped for this unlinked tender.
- Execution took 579 ms and recorded 546,773 shared-buffer hits. A separate run with JIT enabled spent 1.40 seconds compiling the same statement and took 1.92 seconds in total. The history scans also occurred with JIT off.

A read-only SQL comparison first selected the draft's candidate payment via its existing index and correlated each order membership check with that payment's `pos_order_id`. The scoped SELECT executed in 0.86 ms and touched 31 shared buffers. Both variants returned the same tender for the granted cashier and an empty result when tested with an ungranted user ID. Correlating the order checks alone still allowed a scan over the payment primary-key index. Both sides of the lookup need checking in the plan. These measurements cover a single query variant. Full authorization and checkout regression testing remains necessary for an addon change.

## Implemented fix and verification

The addon scopes Odoo's register, session, order and financial-record membership queries to the foreign key on the current row. For a legacy attempt, it probes the order UUID and company, then checks the cashier's read rules against the matching order ID. An external refund whose return UUID is still missing retains its existing visibility rule. Both lookups run in the same SQL statement as the payment read. A restart with the staging code loads the fix. Database indexes, credentials and register grants need no changes.

We compared the released addon and the fix on copies of the same synthetic fixture with PostgreSQL 16.14 and the pinned Odoo 18 runtime. The timing is elapsed server-method time for one run, with fresh one-line drafts for preparation. Each call returned the expected tender or prepared cart authority.

| Cashier method | Released `.9` | Staging fix |
| --- | ---: | ---: |
| Prepare Revolut payment | 9.69 s | 0.26 s |
| Read Revolut checkout state | 1.20 s | 0.09 s |
| Sync Revolut draft | 12.65 s | 0.40 s |
| Sync cash draft | 0.32 s | 0.36 s |

The cashier payment SELECT in checkout state took 0.26 ms and touched 28 shared buffers. Each executed order lookup used the primary key. A sale linked only by its historical UUID took 0.37 ms and touched 48 buffers. A linked refund took 0.25 ms and touched 77. Hiding the original sale denied the cashier that refund in 0.25 ms. With JIT enabled at default thresholds, the linked cases also finished in under 1 ms. The cashier and register tests exercise searches, direct reads, pagination, grant revocation, cash visibility and the missing refund UUID.

The query rewrite applies while compiling access checks. Separate cashier and superuser searches by order UUID, including a lazy order query passed to the payment search, used the order UUID and payment foreign-key indexes. With internal UUID fields restricted to administrators, the cashier could still read the authorized cash tender.

## Rechecking the plan on staging

In an Odoo shell, substitute the cashier, company and saved draft IDs for a Revolut tender. This runs a read-only plan for the payment lookup using the cashier's record rules. The order ID and company must belong to that draft. Running it for an equivalent cash draft provides the control.

```python
from odoo.tools import SQL

payments = env["pos.payment"].with_user(cashier_id).with_context(
    allowed_company_ids=[company_id],
)
query = payments._search([("pos_order_id", "=", draft_id)], order="id desc")
statement = query.select(
    SQL.identifier("pos_payment", "id"),
    SQL.identifier("pos_payment", "pos_order_id"),
)
env.cr.execute(SQL("EXPLAIN (ANALYZE, BUFFERS) %s", statement))
print("\n".join(line for (line,) in env.cr.fetchall()))
```

For a one-tender draft at the reported scale, check the actual rows and loops for both `pos_order` and `pos_payment`. An index scan can still discard the full history under “Rows Removed by Filter”. On the client staging copy, repeat the three methods with provider traffic blocked and time the whole first tap. The browser shares its 60-second budget across multiple steps. Hosted Enterprise timings remain to be verified.

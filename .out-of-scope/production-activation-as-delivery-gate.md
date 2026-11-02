# Production activation as an addon delivery gate

**Decision:** Permanent activation of the reference Enterprise database and
execution of a client production rollout are outside this adaptation's delivery
scope (owner confirmed, 2026-11-02).

**Reason:** The product is a reusable Revolut addon that independent customers
can install on Odoo 18 Enterprise/Odoo.sh with their own accounts and terminals.
The owner's project is a trial database used for compatibility and hosted
lifecycle testing. Requiring its permanent activation, an activation code, or
an identified client deployment would turn product validation into an operating
commitment that the owner has not undertaken.

Keep installation, configuration, upgrade, recovery and customer activation
instructions in the deliverable. Preserve mocked payment/refund regression and
hosted lifecycle evidence, trial limits, prior hardware limitations, server-owned
credentials and test-environment protections. Closing the rollout ticket does
not establish a live Enterprise payment/refund pass or authorize a production
merge. A future client rollout requires separately agreed scope and access.

The original Community refund, return and session in T83 remain a separate,
non-blocking obligation; this decision does not dispose of financial records.

## Prior requests

- [T82 — Activate production and verify one payment and refund](../docs/tickets/wontfix/82-activate-odoo-sh-and-check-payment-refund.md):
  closed as `enhancement` / `wontfix` after the owner's trial-only clarification.

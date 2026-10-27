# Maintain Odoo 18 and 19 support

**Status:** accepted, 2026-10-20. The owner confirmed scope and execution order
in Q7, then confirmed the existing browser/server testing boundaries.

Support Odoo Community 18 alongside Community 19 as maintained product versions.
The owner requires full current feature parity for the first Odoo 18 release,
including Restaurant checkout, split tender, terminal tips, recovery, and full
and partial refunds. A temporary customer backport or reduced-feature pilot
does not meet the agreed scope.

Maintain separate version branches in this repository, retaining the
`pos_revolut` addon name. The owner selected `feat/v18_rev` for Odoo 18; the existing
Odoo 19 line remains on `main`. Odoo 18 task branches and agent worktrees start
from the latest `feat/v18_rev` and integrate back there. The operational agent rule
was originally recorded in root `AGENTS.md`; current release instructions are in `CONTRIBUTING.md`.

Exact feature parity is required, including behavior currently built on Odoo
19 presets and scheduling. Using native Odoo 18 workflows must not silently
reduce that scope. Where native capabilities differ, provide equivalent
behavior and validate it explicitly.

The first installation target is an existing Odoo 18 database receiving this
addon for the first time, preserving its native business data. Importing
payment/refund history from another integration or installation is outside
this initial scope.

Maintaining both versions adds ongoing compatibility and validation work.
Payment verification, idempotency, server-owned credentials, and refund
correctness remain required on each version; existing Odoo 19 evidence alone
does not establish Odoo 18 compatibility.

Separate branches allow explicit adaptation to each version's native APIs
without spreading runtime version checks throughout payment logic. The
trade-off is coordinated backporting: relevant fixes must reach and be tested
on both supported versions.

Deployment and live financial operations require separate authorization.

On 2026-10-22, the owner selected `feat/v18_rev` as the sanitized Odoo 18
continuation branch. Its fresh history excludes earlier internal evidence.

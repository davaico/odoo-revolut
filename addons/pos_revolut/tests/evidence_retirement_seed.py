"""Persist foreign and blocking observations in the page-enabled release."""

import json
from uuid import uuid4

from odoo.service.model import call_kw
from odoo.tests.common import new_test_user


manager = new_test_user(env, login="evidence_upgrade_manager", groups="point_of_sale.group_pos_manager,base.group_allow_export")
credential = env["pos.revolut.merchant.credential"].create({
    "company_id": env.company.id, "environment": "sandbox",
    "secret_reference": "ODOO_REVOLUT_SECRET_EVIDENCE_UPGRADE",
})
evidence = env["pos.revolut.external.refund.evidence"]
rows = evidence.create([{
    "credential_id": credential.id, "provider_order_id": str(uuid4()),
    "related_order_id": str(uuid4()), "amount_minor": 1234, "currency_code": "EUR",
    "reason": reason,
} for reason in ("unrelated_source", "unmatched_source")])
fields = ["credential_id", "provider_order_id", "related_order_id", "amount_minor",
          "currency_code", "reason", "resolved", "blocks_financial_capacity", "deployment_blocking"]
assert env.ref("pos_revolut.menu_external_refund_evidence")
assert len(call_kw(evidence.with_user(manager), "search_read", [[("id", "in", rows.ids)], fields], {})) == 2
assert rows[1].deployment_blocking and not rows[0].deployment_blocking
env["ir.config_parameter"].set_param("pos_revolut.evidence_retirement_fixture", json.dumps({
    "manager": manager.id, "fields": fields, "rows": rows.read(fields),
}))
env.cr.commit()
print("EVIDENCE_RETIREMENT_SEED_OK: manager can read unrelated and blocking evidence in old release", flush=True)

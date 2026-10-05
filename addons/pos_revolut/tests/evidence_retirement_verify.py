"""Check a real module upgrade removes disclosure without dropping evidence."""

import json
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.service.model import call_kw


fixture = json.loads(env["ir.config_parameter"].get_param("pos_revolut.evidence_retirement_fixture"))
for xmlid in (
    "menu_external_refund_evidence", "action_external_refund_evidence",
    "view_external_refund_evidence_list", "view_external_refund_evidence_form",
    "view_external_refund_evidence_search", "access_pos_revolut_external_refund_evidence_manager",
    "rule_revolut_external_refund_evidence_company_manager",
):
    assert not env.ref(f"pos_revolut.{xmlid}", raise_if_not_found=False), xmlid
evidence = env["pos.revolut.external.refund.evidence"]
manager = env["res.users"].browse(fixture["manager"])
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Evidence retirement must not contact Revolut")) as request:
    for expected in fixture["rows"]:
        record = evidence.browse(expected["id"]).exists()
        actual = json.loads(json.dumps(record.read(fixture["fields"])[0]))
        assert actual == expected
        for method, args in (
            ("search_read", [[("id", "=", record.id)], ["provider_order_id"]]),
            ("read", [[record.id], ["provider_order_id"]]),
            ("search_count", [[("id", "=", record.id)]]),
            ("export_data", [[record.id], ["provider_order_id"]]),
        ):
            try:
                call_kw(evidence.with_user(manager), method, args, {})
            except AccessError:
                pass
            else:
                raise AssertionError(f"Retired evidence is still exposed through {method}")
    # The existing deployer consumes this same persisted blocking flag.
    env.cr.execute("SELECT count(*) FROM pos_revolut_external_refund_evidence WHERE deployment_blocking")
    assert env.cr.fetchone()[0] == 1
    blocked = evidence.search([("deployment_blocking", "=", True)])
    blocked.write({"resolved": True})
    assert not blocked.deployment_blocking
    assert evidence.search_count([]) == len(fixture["rows"])
    request.assert_not_called()
env.cr.commit()
print("EVIDENCE_RETIREMENT_VERIFY_OK: page/ACL absent, RPC denied, immutable financial evidence preserved, server resolution works", flush=True)

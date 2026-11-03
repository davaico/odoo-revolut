"""Executed only after first install into an already neutralized native DB."""

import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.exceptions import UserError


assert env["ir.config_parameter"].sudo().get_param("database.is_neutralized")
assert env["ir.config_parameter"].sudo().get_param("pos_revolut.fixture.neutralized_before_install")
assert env["ir.module.module"].search([("name", "=", "pos_revolut")]).state == "installed"

for source in ("database", "environment"):
    reference = "ODOO_REVOLUT_SECRET_FIRST_INSTALL_" + source.upper()
    credential = env["pos.revolut.merchant.credential"].create({
        "company_id": env.company.id, "environment": "production",
        "secret_reference": reference, "source": source,
        "secret_key": "synthetic-reentered-live-key" if source == "database" else False,
    })
    method = env["pos.payment.method"].create({
        "name": "Synthetic first-install live method", "payment_method_type": "terminal",
        "use_payment_terminal": "revolut", "revolut_environment": "production",
        "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
        "revolut_fulfilment_type": "eat_in", "revolut_secret_reference": reference,
    })
    config = env["pos.config"].create({
        "name": "Synthetic first-install register",
        "payment_method_ids": [Command.link(method.id)],
        "auto_validate_terminal_payment": True,
        "revolut_user_ids": [Command.link(env.user.id)],
    })
    session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
    assert not credential.revoked and method.active
    assert credential.secret_key == ("synthetic-reentered-live-key" if source == "database" else False)
    with patch.dict(os.environ, {reference: "synthetic-environment-live-key"}), patch(
        "odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
    ) as connection, patch(
        "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
    ) as provider:
        for stage in ("staging", "production", None):
            if stage is None:
                os.environ.pop("ODOO_STAGE", None)
            else:
                os.environ["ODOO_STAGE"] = stage
            for action in (
                method.action_revolut_check_connection,
                lambda: method.revolut_start_payment(
                    session.id, str(uuid4()), str(uuid4()), 12.34, session.currency_id.id,
                ),
            ):
                try:
                    action()
                except UserError as error:
                    assert "Production Revolut access is disabled" in str(error), str(error)
                else:
                    raise AssertionError("Neutralized first install allowed live operation")
        connection.assert_not_called()
        provider.assert_not_called()
    assert not env["pos.revolut.payment.operation"].search_count([])
    assert not env["pos.revolut.refund.operation"].search_count([])

# Sandbox remains usable with deliberate sandbox configuration after copying.
credential = env["pos.revolut.merchant.credential"].create({
    "company_id": env.company.id, "environment": "sandbox", "source": "database",
    "secret_reference": "ODOO_REVOLUT_SECRET_FIRST_INSTALL_SANDBOX",
    "secret_key": "synthetic-sandbox-key",
})
session.write({"state": "closed"})
method.write({"revolut_environment": "sandbox", "revolut_secret_reference": credential.secret_reference})
response = Mock(status_code=200)
response.json.return_value = {"terminals": [{"id": method.revolut_terminal_id, "online": True}]}
with patch.dict(os.environ, {"ODOO_STAGE": "staging"}), patch(
    "odoo.addons.pos_revolut.models.pos_payment_method.requests.get", return_value=response,
) as connection:
    assert method.action_revolut_check_connection()["params"]["type"] == "success"
    connection.assert_called_once()
    assert connection.call_args.args[0] == "https://sandbox-merchant.revolut.com/api/terminals"
    assert connection.call_args.kwargs["headers"]["Authorization"] == "Bearer synthetic-sandbox-key"
print("NEUTRALIZED_FIRST_INSTALL_VERIFIED: both key sources blocked, zero live HTTP/reservations, sandbox usable")

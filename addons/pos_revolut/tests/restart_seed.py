"""First Odoo process: commit a pending attempt through the public POS RPC."""

from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


location_id, terminal_id = str(uuid4()), str(uuid4())
order_uuid, line_uuid = str(uuid4()), str(uuid4())
provider_order, provider_intent = str(uuid4()), str(uuid4())
method = env["pos.payment.method"].create({
    "name": "Restart recovery terminal",
    "payment_method_type": "terminal",
    "use_payment_terminal": "revolut",
    "revolut_environment": "sandbox",
    "revolut_location_id": location_id,
    "revolut_terminal_id": terminal_id,
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
})
config = env["pos.config"].create({
    "name": "Restart recovery POS",
    "payment_method_ids": [Command.link(method.id)],
    "auto_validate_terminal_payment": True,
})
session = env["pos.session"].create({
    "config_id": config.id, "state": "opened",
})
# The POS configuration exists before the cashier's separate RPC begins.
env.cr.commit()

snapshot = {
    "pricelist_id": config.pricelist_id.id,
    "fiscal_position_id": False,
    "lines": [{
        "uuid": order_uuid, "product_id": 1,
        "qty": 1, "price_unit": 12.34, "discount": 0, "tax_ids": [],
    }],
}
responses = [
    response({"terminals": [{
        "id": terminal_id, "online": True,
        "operation_mode": "pos", "location_id": location_id,
    }]}),
    response({"id": provider_order}),
    response({"id": provider_intent, "state": "pending"}),
]
with patch(
    "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
    side_effect=responses,
) as request:
    started = method.revolut_start_payment(
        session.id, order_uuid, line_uuid, 12.34, config.currency_id.id,
        False, snapshot,
    )
    assert started["state"] == "pending", started
    assert len([call for call in request.call_args_list
                if call.args[0] == "POST"]) == 2

env.cr.commit()
print("RESTART_SEED_OK", flush=True)

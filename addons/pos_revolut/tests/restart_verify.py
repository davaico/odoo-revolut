"""Second Odoo process: recover the committed attempt without a new POST."""

from unittest.mock import Mock, patch
from uuid import uuid4


def response(payload):
    result = Mock()
    result.json.return_value = payload
    return result


operation = env["pos.revolut.payment.operation"].search([
    ("secret_reference", "=", "ODOO_REVOLUT_SECRET_TEST_TERMINAL"),
], limit=1)
assert operation and operation.state == "pending", operation
method = operation.payment_method_id
provider_payment = str(uuid4())
with patch(
    "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
    side_effect=[
        response({
            "id": operation.revolut_payment_intent_id,
            "order_id": operation.revolut_order_id,
            "state": "completed",
            "payment_id": provider_payment,
        }),
        response({
            "id": provider_payment,
            "order_id": operation.revolut_order_id,
            "amount": operation.amount_minor,
            "currency": operation.currency_code,
            "state": "captured",
        }),
    ],
) as request:
    env.ref("pos_revolut.ir_cron_reconcile_payments").method_direct_trigger()
    # The cron committed in its own cursor. Start the next RPC transaction.
    env.cr.rollback()
    env.invalidate_all()
    recovered = method.revolut_find_payment(
        operation.order_uuid, operation.payment_line_uuid
    )
    replay = method.revolut_start_payment(
        operation.pos_session_id.id, operation.order_uuid,
        operation.payment_line_uuid, operation.amount,
        operation.currency_id.id, False, operation.financial_snapshot,
    )
    assert recovered == replay, (recovered, replay)
    assert recovered["operation_id"] == operation.id, recovered
    assert recovered["state"] == "verified", recovered
    assert recovered["order_id"] == operation.revolut_order_id, recovered
    assert recovered["payment_intent_id"] == operation.revolut_payment_intent_id, recovered
    assert recovered["payment_id"] == provider_payment, recovered
    assert len(request.call_args_list) == 2, request.call_args_list
    assert all(call.args[0] == "GET" for call in request.call_args_list)
    assert env["pos.revolut.payment.dispatch"].search_count([
        ("operation_id", "=", operation.id),
    ]) == 2

env.cr.commit()
print("RESTART_RECOVERY_OK", flush=True)

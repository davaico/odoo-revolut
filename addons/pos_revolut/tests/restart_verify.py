"""Process three: authenticated explicit zero/nonzero reports project once."""
import csv
import io
import json
from unittest.mock import Mock, patch

from odoo.addons.pos_revolut.models.terminal_tip import REPORT_COLUMNS


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    result.iter_content.return_value = [payload if isinstance(payload, bytes) else json.dumps(payload).encode()]
    return result


history = json.loads(env['ir.config_parameter'].get_param('pos_revolut.restart_fixture'))
for fixture in history:
    operation = env['pos.revolut.payment.operation'].browse(fixture['operation_id'])
    method = operation.payment_method_id
    assert operation.report_run_id == fixture['report_id'] and not operation.terminal_tip_evidence
    row = {
        'payment_id': fixture['provider_payment'], 'type': 'PAYMENT',
        'order_id': fixture['provider_order'], 'state': 'COMPLETED',
        'amount': f"{fixture['gross_minor'] / 100:.2f}", 'currency': operation.currency_code,
        'surcharge_amount': '', 'tip_amount': f"{fixture['tip_minor'] / 100:.2f}",
        'refunded_amount': '0.00', 'created_date': fixture['created_at'],
        'captured_date': fixture['captured_at'], 'location_id': operation.location_id,
    }
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=REPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(row)
    with patch('odoo.addons.pos_revolut.models.pos_payment_method.requests.request', side_effect=[
        response({'id': fixture['provider_intent'], 'order_id': fixture['provider_order'],
                  'state': 'completed', 'payment_id': fixture['provider_payment'],
                  'amount': 1234, 'currency': operation.currency_code, 'terminal_id': operation.terminal_id}),
        response({'id': fixture['provider_payment'], 'order_id': fixture['provider_order'],
                  'state': 'captured', 'amount': fixture['gross_minor'],
                  'currency': operation.currency_code, 'created_at': fixture['created_at']}),
        response({'report_run_id': fixture['report_id'], 'status': 'completed'}),
        response(output.getvalue().encode()),
        response({'id': fixture['provider_order'], 'currency': operation.currency_code,
                  'location_id': operation.location_id,
                  'payments': [{'id': fixture['provider_payment'], 'state': 'captured', 'amount': fixture['gross_minor']}]}),
    ]) as provider:
        verified = method.revolut_poll_payment(operation.id, fixture['order_uuid'], fixture['line_uuid'])
        assert verified['state'] == 'verified' and not verified['awaiting_tip_details'], verified
        assert verified['gross_amount_minor'] == fixture['gross_minor'], verified
        assert verified['terminal_tip_minor'] == fixture['tip_minor'], verified
        env.cr.rollback()
        env.invalidate_all()
        operation.invalidate_recordset()
        order = env['pos.order'].browse(fixture['order_id'])
        authority = order.revolut_authorization_id
        assert authority.id == fixture['authorization_id'] and authority.cart_version == fixture['cart_version']
        assert authority.tender_revision == fixture['tender_revision'] and authority.tenders == fixture['tenders']
        assert operation.financial_snapshot == fixture['financial_snapshot']
        assert operation.revolut_order_id == fixture['provider_order']
        assert operation.revolut_payment_intent_id == fixture['provider_intent']
        assert operation.revolut_payment_id == fixture['provider_payment']
        assert operation.report_run_id == fixture['report_id'] and operation.terminal_tip_evidence
        assert order.amount_total == fixture['gross_minor'] / 100
        assert len(order.lines.filtered(lambda line: line.product_id == authority.tip_product_id)) == bool(fixture['tip_minor'])
        assert len(order.payment_ids) == 1 and order.payment_ids.amount == fixture['gross_minor'] / 100
        projection_revision = authority.projection_revision
        replay = method.revolut_start_payment(
            fixture['session_id'], fixture['order_uuid'], fixture['line_uuid'], 12.34, operation.currency_id.id,
            False, False, authority.id, authority.cart_version, authority.tender_revision,
        )
        repeated = method.revolut_poll_payment(operation.id, fixture['order_uuid'], fixture['line_uuid'])
        # The observing caller is fresh; replay and final polling reuse the
        # same durable evidence without another provider observation.
        assert verified['observation_fresh'] is True, verified
        cached = dict(verified, observation_fresh=False)
        assert replay == repeated == cached, (replay, repeated, verified)
        assert authority.projection_revision == projection_revision
        assert len(provider.call_args_list) == 5 and all(call.args[0] == 'GET' for call in provider.call_args_list)
        assert env['pos.revolut.payment.dispatch'].search_count([('operation_id', '=', operation.id)]) == 2
    env.cr.commit()
print('RESTART_RECOVERY_OK: same authority/ledger/provider references, exact tips projected once, no POSTs', flush=True)

"""Process two: captured money waits for report evidence without replay."""
import json
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo.exceptions import UserError


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    result.iter_content.return_value = [json.dumps(payload).encode()]
    return result


history = json.loads(env['ir.config_parameter'].get_param('pos_revolut.restart_fixture'))
for fixture in history:
    operation = env['pos.revolut.payment.operation'].browse(fixture['operation_id'])
    method = operation.payment_method_id
    assert operation.state == 'pending' and operation.authorization_id.id == fixture['authorization_id']
    with patch('odoo.addons.pos_revolut.models.pos_payment_method.requests.request', side_effect=[
        response({'id': fixture['provider_intent'], 'order_id': fixture['provider_order'],
                  'state': 'completed', 'payment_id': fixture['provider_payment'],
                  'amount': 1234, 'currency': operation.currency_code, 'terminal_id': operation.terminal_id}),
        response({'id': fixture['provider_payment'], 'order_id': fixture['provider_order'],
                  'state': 'captured', 'amount': fixture['gross_minor'],
                  'currency': operation.currency_code, 'created_at': fixture['created_at']}),
        response({'report_run_id': fixture['report_id'], 'status': 'processing'}),
    ]) as provider:
        waiting = method.revolut_poll_payment(operation.id, fixture['order_uuid'], fixture['line_uuid'])
        assert waiting['state'] == 'pending' and waiting['awaiting_tip_details'], waiting
        assert not waiting['retry_safe'] and waiting['captured_amount_minor'] == fixture['gross_minor'], waiting
        env.cr.rollback()
        env.invalidate_all()
        order = env['pos.order'].browse(fixture['order_id'])
        operation.invalidate_recordset()
        assert order.state == 'draft' and order.amount_total == 12.34
        assert not operation.terminal_tip_evidence and operation.report_run_id == fixture['report_id']
        assert operation.authorization_id.tenders == fixture['tenders']
        try:
            with env.cr.savepoint():
                order.lines.write({'price_unit': 99})
        except UserError:
            pass
        else:
            raise AssertionError('Captured cart edit was accepted while tip evidence was missing')
        try:
            method.revolut_start_payment(
                fixture['session_id'], fixture['order_uuid'], str(uuid4()), 12.34, operation.currency_id.id,
                False, False, fixture['authorization_id'], fixture['cart_version'], fixture['tender_revision'],
            )
        except UserError:
            pass
        else:
            raise AssertionError('Captured reservation allowed another base charge')
        financial_posts = [call for call in provider.call_args_list
                           if call.args[0] == 'POST' and '/api/report-runs' not in call.args[1]]
        assert not financial_posts, financial_posts
        assert sum(call.args[0] == 'POST' for call in provider.call_args_list) == 1
    env.cr.commit()
print('RESTART_WAIT_OK: zero/nonzero captures stay exposed; report processing, no financial replay', flush=True)

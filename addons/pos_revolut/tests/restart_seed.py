"""Process one: commit two real authorized carts and pending terminal pushes."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    return result


product = env['product.product'].create({
    'name': 'Restart authorized goods', 'type': 'service', 'available_in_pos': True,
    'list_price': 12.34, 'taxes_id': [Command.clear()],
})
tip_product = env['product.product'].create({
    'name': 'Restart configured terminal tip', 'type': 'service',
    'list_price': 0, 'taxes_id': [Command.clear()],
})
history = []
for tip_minor in (0, 300):
    location, terminal, order_uuid, line_uuid = [str(uuid4()) for _ in range(4)]
    provider_order, provider_intent, provider_payment, report = [str(uuid4()) for _ in range(4)]
    method = env['pos.payment.method'].create({
        'name': f'Restart terminal tip {tip_minor}', 'payment_method_type': 'terminal',
        'use_payment_terminal': 'revolut', 'revolut_environment': 'sandbox',
        'revolut_location_id': location, 'revolut_terminal_id': terminal,
        'revolut_fulfilment_type': 'eat_in',
        'revolut_secret_reference': 'ODOO_REVOLUT_SECRET_TEST_TERMINAL',
    })
    config = env['pos.config'].create({
        'name': f'Restart authorized POS {tip_minor}',
        'payment_method_ids': [Command.link(method.id)], 'tip_product_id': tip_product.id,
        'auto_validate_terminal_payment': True,
    })
    session = env['pos.session'].create({'config_id': config.id, 'state': 'opened'})
    payload = {
        'uuid': order_uuid, 'name': f'Restart {tip_minor}', 'session_id': session.id,
        'user_id': env.uid, 'state': 'draft', 'sequence_number': 1,
        'pricelist_id': config.pricelist_id.id, 'fiscal_position_id': False,
        'amount_total': 12.34, 'amount_tax': 0, 'amount_paid': 0, 'amount_return': 0,
        'date_order': fields.Datetime.to_string(fields.Datetime.now()), 'to_invoice': False,
        'lines': [Command.create({
            'uuid': str(uuid4()), 'product_id': product.id, 'qty': 1,
            'price_unit': 12.34, 'discount': 0, 'tax_ids': [Command.set([])],
            'price_subtotal': 12.34, 'price_subtotal_incl': 12.34, 'pack_lot_ids': [],
        })],
        'payment_ids': [Command.create({
            'uuid': line_uuid, 'payment_method_id': method.id, 'amount': 12.34,
            'payment_status': 'waiting', 'transaction_id': False, 'name': fields.Datetime.now(),
        })],
    }
    saved = env['pos.order'].sync_from_ui([payload])
    order = env['pos.order'].browse(next(item['id'] for item in saved['pos.order'] if item['uuid'] == order_uuid))
    env.cr.commit()
    prepared = env['pos.order'].revolut_prepare_payment(order.id, order_uuid, 0, [{
        'uuid': line_uuid, 'payment_method_id': method.id, 'amount': 12.34,
    }])
    assert prepared['status'] == 'prepared', prepared
    with patch('odoo.addons.pos_revolut.models.pos_payment_method.requests.request', side_effect=[
        response({'terminals': [{'id': terminal, 'online': True,
                                 'operation_mode': 'pos', 'location_id': location}]}),
        response({'id': provider_order}), response({'id': provider_intent, 'state': 'pending'}),
    ]) as provider:
        started = method.revolut_start_payment(
            session.id, order_uuid, line_uuid, 12.34, config.currency_id.id,
            False, False, prepared['authorization_id'], prepared['cart_version'], prepared['tender_revision'],
        )
        assert started['state'] == 'pending', started
        assert sum(call.args[0] == 'POST' for call in provider.call_args_list) == 2
    env.cr.rollback()
    env.invalidate_all()
    operation = env['pos.revolut.payment.operation'].browse(started['operation_id'])
    created = datetime.now(timezone.utc).replace(microsecond=0)
    history.append({
        'operation_id': operation.id, 'order_id': order.id, 'order_uuid': order_uuid,
        'line_uuid': line_uuid, 'method_id': method.id, 'session_id': session.id,
        'authorization_id': prepared['authorization_id'], 'cart_version': prepared['cart_version'],
        'tender_revision': prepared['tender_revision'], 'tenders': operation.authorization_id.tenders,
        'financial_snapshot': operation.financial_snapshot,
        'provider_order': provider_order, 'provider_intent': provider_intent,
        'provider_payment': provider_payment, 'report_id': report,
        'tip_minor': tip_minor, 'gross_minor': 1234 + tip_minor,
        'created_at': created.isoformat().replace('+00:00', 'Z'),
        'captured_at': (created + timedelta(seconds=10)).isoformat().replace('+00:00', 'Z'),
    })
env['ir.config_parameter'].set_param('pos_revolut.restart_fixture', json.dumps(history))
env.cr.commit()
print('RESTART_SEED_OK: two saved authorized carts, exactly four financial POSTs', flush=True)

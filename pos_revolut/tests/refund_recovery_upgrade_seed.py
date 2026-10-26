"""Seed synthetic 19.0.1.18.14 records in a disposable guarded Odoo shell."""
import json
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields

assert env['ir.module.module'].search([('name', '=', 'pos_revolut')]).latest_version == '19.0.1.18.14'
method = env['pos.payment.method'].create({
    'name': 'Refund recovery upgrade terminal', 'payment_method_type': 'terminal',
    'use_payment_terminal': 'revolut', 'revolut_environment': 'sandbox',
    'revolut_location_id': str(uuid4()), 'revolut_terminal_id': str(uuid4()),
    'revolut_fulfilment_type': 'eat_in',
    'revolut_secret_reference': 'ODOO_REVOLUT_SECRET_TEST_TERMINAL',
})
config = env['pos.config'].create({
    'name': 'Refund recovery upgrade register', 'payment_method_ids': [Command.link(method.id)],
    'revolut_user_ids': [Command.link(env.uid)],
})
session = env['pos.session'].create({'config_id': config.id, 'state': 'opened'})
product = env['product.product'].create({
    'name': 'Preserved refund recovery service', 'type': 'service',
    'available_in_pos': True, 'list_price': 12.34, 'taxes_id': [Command.clear()],
})
rows = []
waiting_refund = None

with patch('odoo.addons.pos_revolut.models.pos_payment_method.requests.request',
           side_effect=AssertionError('Upgrade fixtures must not contact Revolut')) as provider:
    for scenario in ('waiting', 'completed', 'pending', 'unresolved'):
        payload = {
            'uuid': str(uuid4()), 'name': f'Upgrade original {scenario}', 'session_id': session.id,
            'user_id': env.uid, 'state': 'paid', 'pricelist_id': config.pricelist_id.id,
            'amount_total': 12.34, 'amount_tax': 0, 'amount_paid': 12.34, 'amount_return': 0,
            'date_order': fields.Datetime.to_string(fields.Datetime.now()),
            'lines': [Command.create({
                'uuid': str(uuid4()), 'product_id': product.id, 'qty': 1,
                'price_unit': 12.34, 'discount': 0, 'tax_ids': [Command.set([])],
                'price_subtotal': 12.34, 'price_subtotal_incl': 12.34,
            })],
            'payment_ids': [Command.create({
                'uuid': str(uuid4()), 'payment_method_id': method.id, 'amount': 12.34,
                'payment_status': 'done', 'transaction_id': str(uuid4()),
            })],
        }
        source = env['pos.revolut.payment.operation'].create({
            'payment_method_id': method.id, 'company_id': method.company_id.id,
            'pos_config_id': config.id, 'pos_session_id': session.id,
            'order_uuid': payload['uuid'], 'payment_line_uuid': payload['payment_ids'][0][2]['uuid'],
            'amount': 12.34, 'amount_minor': 1234, 'currency_id': session.currency_id.id,
            'currency_code': session.currency_id.name, 'environment': 'sandbox',
            'location_id': method.revolut_location_id, 'terminal_id': method.revolut_terminal_id,
            'fulfilment_type': 'eat_in', 'secret_reference': method.revolut_secret_reference,
            'state': 'verified', 'provider_state': 'captured', 'verified_at': fields.Datetime.now(),
            'revolut_order_id': str(uuid4()), 'revolut_payment_intent_id': str(uuid4()),
            'revolut_payment_id': payload['payment_ids'][0][2]['transaction_id'],
            'financial_snapshot': env['pos.revolut.payment.operation']._normalize_financial_snapshot(payload),
        })
        env['pos.order'].sync_from_ui([json.loads(json.dumps(payload, default=str))])
        source.invalidate_recordset()
        original = source.pos_order_id
        payload.update(uuid=str(uuid4()), name=f'Upgrade return {scenario}',
                       state='draft', amount_total=-12.34, amount_paid=-12.34)
        payload['lines'][0][2].update(uuid=str(uuid4()), qty=-1, price_subtotal=-12.34,
            price_subtotal_incl=-12.34, refunded_orderline_id=original.lines.id)
        payload['payment_ids'][0][2].update(uuid=str(uuid4()), amount=-12.34,
                                           payment_status='waiting', transaction_id=False)
        saved = env['pos.order'].sync_from_ui([json.loads(json.dumps(payload, default=str))])
        order = env['pos.order'].browse(next(item['id'] for item in saved['pos.order']
                                             if item['uuid'] == payload['uuid']))
        reference = str(uuid4())
        verified = scenario in ('waiting', 'completed')
        refund = env['pos.revolut.refund.operation'].create({
            'original_operation_id': source.id, 'pos_session_id': session.id,
            'order_uuid': order.uuid, 'payment_line_uuid': order.payment_ids.uuid,
            'amount': 12.34, 'amount_minor': 1234, 'return_total_minor': 1234,
            'currency_id': session.currency_id.id,
            'state': 'verified' if verified else scenario,
            'provider_state': 'completed' if verified else 'processing',
            'verified_at': fields.Datetime.now() if verified else False,
            'revolut_order_id': reference,
            'financial_snapshot': env['pos.revolut.payment.operation']._normalize_financial_snapshot(payload),
        })
        if scenario == 'completed':
            payload.update(id=order.id, state='paid')
            payload['lines'][0][2]['id'] = order.lines.id
            payload['payment_ids'][0][2].update(id=order.payment_ids.id,
                                                payment_status='done', transaction_id=reference)
            env['pos.order'].sync_from_ui([json.loads(json.dumps(payload, default=str))])
        if scenario == 'waiting':
            waiting_refund = refund.id
        rows += [source, refund, original, original.lines, original.payment_ids,
                 order, order.lines, order.payment_ids]
    provider.assert_not_called()

rows += [method, source.credential_id, config, session, product]
env.flush_all()
snapshots = []
for record in rows:
    names = [name for name, field in record._fields.items()
             if field.store and field.type not in {'one2many', 'many2many', 'binary'}]
    snapshots.append({'model': record._name, 'values': record.read(names)[0]})
env['ir.config_parameter'].set_param('pos_revolut.refund_recovery_upgrade', json.dumps({
    'records': snapshots, 'waiting_refund': waiting_refund,
}, default=str))
env.cr.commit()
print('REFUND_RECOVERY_UPGRADE_SEED_OK', len(snapshots), flush=True)

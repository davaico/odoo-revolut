"""Verify preservation and manager recovery after the production-base update."""
import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.service.model import call_kw

fixture = json.loads(env['ir.config_parameter'].get_param('pos_revolut.refund_recovery_upgrade'))
assert env['ir.module.module'].search([('name', '=', 'pos_revolut')]).latest_version == '19.0.1.18.15'
with patch('odoo.addons.pos_revolut.models.pos_payment_method.requests.request',
           side_effect=AssertionError('Upgrade verification must not contact Revolut')) as provider:
    for row in fixture['records']:
        record = env[row['model']].browse(row['values']['id']).exists()
        assert record, row['model']
        actual = json.loads(json.dumps(record.read(list(row['values']))[0], default=str))
        assert actual == row['values'], (row['model'], actual, row['values'])
    refund = env['pos.revolut.refund.operation'].browse(fixture['waiting_refund'])
    order = env['pos.order'].search([('uuid', '=', refund.order_uuid)])
    tender = order.payment_ids
    assert tender.payment_status == 'waiting' and not tender.transaction_id
    assert not refund.pos_payment_id
    for state in ('pending', 'unresolved'):
        uncertain = env['pos.revolut.refund.operation'].search([('state', '=', state)])
        assert len(uncertain) == 1
        try:
            call_kw(env['pos.revolut.refund.operation'], 'action_recover_return', [[uncertain.id]], {})
        except UserError:
            pass
        else:
            raise AssertionError('An uncertain refund must not be projected')
    action = call_kw(env['pos.revolut.refund.operation'], 'action_recover_return', [[refund.id]], {})
    assert action['url'] == f'/pos/ui/{order.config_id.id}/payment/{order.uuid}'
    assert refund.pos_order_id == order and refund.pos_payment_id == tender
    assert order.payment_ids == tender and order.state == 'draft'
    assert tender.payment_status == 'done'
    assert tender.transaction_id == tender.payment_ref_no == refund.revolut_order_id
    assert call_kw(env['pos.revolut.refund.operation'], 'action_recover_return', [[refund.id]], {}) == action
    assert len(env['pos.revolut.refund.operation'].search([])) == 4
    provider.assert_not_called()
# Recovery verification is intentionally nonpersistent; only the upgrade remains.
env.cr.rollback()
print('REFUND_RECOVERY_UPGRADE_VERIFY_OK', len(fixture['records']), flush=True)

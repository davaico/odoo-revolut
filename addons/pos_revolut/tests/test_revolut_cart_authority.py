import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError
from datetime import timedelta

from .test_revolut_terminal_tip import TerminalTipFixtures
from odoo.tests.common import tagged


@tagged('post_install', '-at_install')
class TestRevolutCartAuthority(TerminalTipFixtures, CommonPosTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.method = cls.bank_payment_method.copy({
            'name': 'Authorized Revolut', 'payment_method_type': 'terminal',
            'use_payment_terminal': 'revolut', 'revolut_environment': 'sandbox',
            'revolut_location_id': str(uuid4()), 'revolut_terminal_id': str(uuid4()),
            'revolut_secret_reference': 'ODOO_REVOLUT_SECRET_AUTHORITY_TEST',
            'revolut_fulfilment_type': 'eat_in',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Authorized basket', 'available_in_pos': True,
            'list_price': 100, 'taxes_id': [Command.clear()],
        })
        cls.tip = cls.env['product.product'].create({
            'name': 'Terminal tip', 'list_price': 0, 'taxes_id': [Command.clear()],
        })
        cls.pos_config_usd.write({
            'payment_method_ids': [Command.link(cls.method.id)],
            'auto_validate_terminal_payment': True, 'tip_product_id': cls.tip.id,
        })

    def setUp(self):
        super().setUp()
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({'state': 'opened'})
        self.order = self.env['pos.order'].create({
            'session_id': self.session.id, 'uuid': str(uuid4()),
            'amount_total': 100, 'amount_tax': 0, 'amount_paid': 0, 'amount_return': 0,
            'pricelist_id': self.pos_config_usd.pricelist_id.id,
            'lines': [Command.create({'product_id': self.product.id, 'qty': 1,
                'price_unit': 100, 'price_subtotal': 100, 'price_subtotal_incl': 100,
                'tax_ids': [Command.clear()]})],
        })
        self.line_uuid = str(uuid4())
        self.secret = self.enterContext(patch.dict(os.environ, {
            'ODOO_REVOLUT_SECRET_AUTHORITY_TEST': 'test-only',
        }))
        self.request = self.enterContext(patch(
            'odoo.addons.pos_revolut.models.pos_payment_method.requests.request',
            side_effect=AssertionError('Rejected authority must never call provider'),
        ))

    def prepare(self, amount=100, version=0, uuid=None):
        return self.env['pos.order'].revolut_prepare_payment(
            self.order.id, self.order.uuid, version,
            [{'uuid': uuid or self.line_uuid, 'payment_method_id': self.method.id, 'amount': amount}],
        )

    def start(self, authorization=None, amount=100, uuid=None):
        authorization = authorization or {}
        return self.method.revolut_start_payment(
            self.session.id, self.order.uuid, uuid or self.line_uuid, amount,
            self.order.currency_id.id, False, False,
            authorization.get('authorization_id'), authorization.get('cart_version'),
            authorization.get('tender_revision'),
        )

    def test_old_amount_snapshot_rpc_cannot_dispatch(self):
        with self.assertRaises(UserError):
            self.method.revolut_start_payment(self.session.id, self.order.uuid,
                self.line_uuid, 150, self.order.currency_id.id, False,
                {'lines': [{'uuid': str(uuid4()), 'product_id': self.product.id,
                    'qty': 1, 'price_unit': 150, 'tax_ids': []}]})
        self.request.assert_not_called()
        self.assertFalse(self.env['pos.revolut.payment.operation'].sudo().search([
            ('order_uuid', '=', self.order.uuid)]))

    def test_oversized_slot_is_rejected_without_operation(self):
        with self.assertRaises(UserError):
            self.prepare(amount=100.01)
        self.request.assert_not_called()
        self.assertFalse(self.env['pos.revolut.payment.operation'].sudo().search([
            ('order_uuid', '=', self.order.uuid)]))

    def test_order_edit_revokes_unexposed_authority(self):
        prepared = self.prepare()
        self.order.lines.write({'qty': 2})
        rejected = self.start(prepared)
        self.assertEqual(rejected['dispatched'], False)
        self.request.assert_not_called()
        self.assertFalse(self.env['pos.revolut.payment.operation'].sudo().search([
            ('order_uuid', '=', self.order.uuid)]))

    def provider(self, base=10000, tip=0):
        self.base_minor, self.tip_minor, self.gross_minor = base, tip, base + tip
        self.provider_order_id, self.provider_intent_id, self.provider_payment_id = (str(uuid4()) for _ in range(3))
        self.report_status, self.report_post_count = 'completed', 0
        self.csv_content, self.order_payments = None, None
        self.request.side_effect = self.provider_response

    def poll(self, operation):
        self.env.invalidate_all()
        uuid = self.env['pos.revolut.payment.operation'].browse(operation['operation_id']).payment_line_uuid
        result = self.method.revolut_poll_payment(operation['operation_id'],self.order.uuid,uuid)
        self.env.invalidate_all()
        return result

    def plan(self, slots, version=0):
        return self.env['pos.order'].revolut_prepare_payment(self.order.id,self.order.uuid,version,slots)

    def slot(self, uuid, amount, method=None):
        return {'uuid':uuid,'amount':amount,'payment_method_id':(method or self.method).id}

    def assert_no_financial_post(self, count):
        self.assertEqual(len([call for call in self.request.call_args_list
            if call.args[0] == 'POST' and '/api/report-runs' not in call.args[1]]), count)

    def test_browser_cannot_create_authority_or_assign_it_using_context(self):
        prepared = self.prepare()
        with self.assertRaises(AccessError):
            self.order.with_context(revolut_authority_cursor=True).write({'revolut_authorization_id':prepared['authorization_id']})
        with self.assertRaises(AccessError):
            self.env['pos.revolut.cart.authorization'].sudo().with_context(revolut_authority_cursor=True).create({})
        self.request.assert_not_called()

    def test_stale_tender_revision_cannot_start_a_changed_allocation(self):
        prepared = self.prepare(amount=40)
        self.plan([self.slot(self.line_uuid,60)],prepared['cart_version'])
        result = self.start(prepared,amount=40)
        self.assertFalse(result['dispatched'])
        self.request.assert_not_called()

    def test_expired_unexposed_authority_requires_preparation(self):
        from ..models.cart_authorization import _authority_mutation
        prepared = self.prepare()
        self.env.invalidate_all()
        with _authority_mutation(self.env):
            self.order.revolut_authorization_id.sudo().write({'expires_at':fields.Datetime.now()-timedelta(seconds=1)})
        self.env.invalidate_all()
        result = self.start(prepared)
        self.assertFalse(result['dispatched'])
        self.request.assert_not_called()
        renewed = self.prepare(version=prepared['cart_version'])
        self.assertGreater(renewed['cart_version'],prepared['cart_version'])

    def test_catalog_change_before_first_reservation_never_dispatches(self):
        prepared = self.prepare()
        self.product.list_price = 101
        self.env.invalidate_all()
        result = self.start(prepared)
        self.assertFalse(result['dispatched'])
        self.request.assert_not_called()

    def test_nonfinite_offscale_and_oversized_tenders_are_bounded(self):
        for amount in [True, 'NaN', 'Infinity', '1e999999999', '0.001', 21474836.48, '1'*65]:
            with self.subTest(amount=amount), self.assertRaises(UserError):
                self.prepare(amount=amount)
        self.request.assert_not_called()

    def test_unresolved_base_remains_reserved_and_cart_is_frozen(self):
        prepared = self.prepare(amount=60)
        self.provider(base=6000)
        started = self.start(prepared,amount=60)
        with self.assertRaises(UserError):
            self.order.lines.write({'price_unit':200})
        with self.assertRaises(UserError):
            self.plan([self.slot(self.line_uuid,60),self.slot(str(uuid4()),41)],prepared['cart_version'])
        self.assert_no_financial_post(2)
        self.assertEqual(started['state'],'pending')
        self.assertEqual(self.order.revolut_authorization_id.sudo()._response()['remaining_minor'],4000)

    def test_ordinary_zero_tip_is_proven_and_gross_projection_is_idempotent(self):
        prepared = self.prepare()
        self.provider()
        started = self.start(prepared)
        result = self.poll(started)
        self.assertEqual(result['state'],'verified')
        self.assertEqual(result['terminal_tip_minor'],0)
        self.assertTrue(self.env['pos.revolut.payment.operation'].browse(result['operation_id']).terminal_tip_evidence)
        self.poll(started)
        self.assertEqual(len(self.order.payment_ids),1)
        self.assertEqual(self.order.amount_total,100)
        self.assertFalse(self.order.is_tipped)
        self.assert_no_financial_post(2)
        self.assertEqual(self.report_post_count,1)

    def test_two_verified_cards_consume_base_independently_of_their_tips(self):
        second_uuid = str(uuid4())
        prepared = self.plan([self.slot(self.line_uuid,40),self.slot(second_uuid,60)])
        self.provider(base=4000,tip=300)
        first = self.poll(self.start(prepared,amount=40))
        self.assertEqual(first['state'],'verified')
        self.assertEqual(self.order.amount_total,103)
        with self.assertRaises(UserError):
            self.plan([self.slot(self.line_uuid,40),self.slot(second_uuid,63)],prepared['cart_version'])
        self.provider(base=6000,tip=200)
        second = self.poll(self.start(prepared,amount=60,uuid=second_uuid))
        self.assertEqual(second['state'],'verified')
        self.assertEqual(self.order.amount_total,105)
        self.assertEqual(self.order.amount_paid,105)
        self.assertEqual(len(self.order.payment_ids),2)
        self.assertEqual(len(self.order.lines.filtered(lambda line:line.product_id==self.tip)),1)
        self.assertEqual(self.order.revolut_authorization_id.sudo()._response()['remaining_minor'],0)
        self.assert_no_financial_post(4)

    def test_cash_correction_and_ledger_revision_are_one_atomic_action(self):
        cash_uuid, second_uuid = str(uuid4()), str(uuid4())
        self.order.write({'payment_ids':[Command.create({'uuid':cash_uuid,'amount':30,'payment_method_id':self.cash_payment_method.id})]})
        prepared = self.plan([self.slot(cash_uuid,30,self.cash_payment_method),self.slot(self.line_uuid,40)])
        self.provider(base=4000)
        self.assertEqual(self.poll(self.start(prepared,amount=40))['state'],'verified')
        with self.assertRaises(UserError):
            self.order.payment_ids.filtered(lambda p:p.uuid==cash_uuid).write({'amount':20})
        changed = self.plan([self.slot(cash_uuid,20,self.cash_payment_method),self.slot(self.line_uuid,40),self.slot(second_uuid,40)],prepared['cart_version'])
        self.assertEqual(changed['tender_revision'],prepared['tender_revision']+1)
        self.assertEqual(self.order.payment_ids.filtered(lambda p:p.uuid==cash_uuid).amount,20)
        with self.assertRaises(UserError):
            self.start(prepared,amount=40,uuid=second_uuid)
        self.assert_no_financial_post(2)
        self.provider(base=4000)
        self.assertEqual(self.poll(self.start(changed,amount=40,uuid=second_uuid))['state'],'verified')
        self.assertEqual(self.order.amount_paid,100)
        self.assert_no_financial_post(4)


    def rounding_cart(self, cash, card, *, cash_only=True):
        rounding = self.env['account.cash.rounding'].create({'name':'Authorized five-cent rounding',
            'rounding':0.05,'rounding_method':'HALF-UP','strategy':'add_invoice_line'})
        self.pos_config_usd.write({'cash_rounding':True,'only_round_cash_method':cash_only,'rounding_method':rounding.id})
        self.product.list_price = 10.02
        self.order.lines.write({'price_unit':10.02,'price_subtotal':10.02,'price_subtotal_incl':10.02})
        self.order.write({'amount_total':10.02})
        slots = []
        if cash:
            cash_uuid = str(uuid4())
            self.order.write({'payment_ids':[Command.create({'uuid':cash_uuid,'amount':cash,'payment_method_id':self.cash_payment_method.id})]})
            slots.append(self.slot(cash_uuid,cash,self.cash_payment_method))
        if card:
            slots.append(self.slot(self.line_uuid,card))
        return self.plan(slots),slots

    def test_cash_rounding_cash_first_keeps_the_exact_card_base(self):
        prepared,slots = self.rounding_cart(6,4.02)
        self.assertEqual(prepared['payable_minor'],1002)
        self.provider(base=402)
        self.assertEqual(self.poll(self.start(prepared,amount=4.02))['state'],'verified')
        self.assertEqual(self.order.amount_paid,10.02)
        self.assertEqual(self.order._get_rounded_amount(self.order.amount_total),10.02)

    def test_cash_rounding_card_first_rounds_only_the_cash_residual(self):
        prepared,slots = self.rounding_cart(4,6)
        self.assertEqual(prepared['payable_minor'],1000)
        self.provider(base=600,tip=3)
        self.assertEqual(self.poll(self.start(prepared,amount=6))['state'],'verified')
        self.assertEqual(self.order.amount_paid,10.03)
        self.assertEqual(self.order.amount_total,10.03)

    def test_cash_rounding_increase_belongs_to_cash_and_not_extra_card_capacity(self):
        prepared,slots = self.rounding_cart(5.05,4.99)
        self.assertEqual(prepared['payable_minor'],1004)
        self.provider(base=499)
        self.assertEqual(self.poll(self.start(prepared,amount=4.99))['state'],'verified')
        self.assertEqual(self.order.amount_paid,10.04)
        with self.assertRaises(UserError):
            self.plan(slots+[self.slot(str(uuid4()),0.02)],prepared['cart_version'])
        self.assert_no_financial_post(2)

    def test_fully_paid_cash_rounding_does_not_reopen_a_card_residual(self):
        prepared,slots = self.rounding_cart(10,0)
        self.assertEqual(prepared['payable_minor'],1000)
        with self.assertRaises(UserError):
            self.plan(slots+[self.slot(self.line_uuid,0.02)],prepared['cart_version'])
        self.request.assert_not_called()

    def test_global_rounding_freezes_base_before_adding_collected_tip(self):
        prepared,slots = self.rounding_cart(0,10,cash_only=False)
        self.assertEqual(prepared['payable_minor'],1000)
        self.provider(base=1000,tip=3)
        self.assertEqual(self.poll(self.start(prepared,amount=10))['state'],'verified')
        self.assertEqual(self.order.amount_total,10.03)
        self.assertEqual(self.order.amount_paid,10.03)

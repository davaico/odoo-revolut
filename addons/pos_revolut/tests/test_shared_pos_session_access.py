"""Ticket 30 characterization; passing cases describe access, not a fix."""

import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .authorization_fixtures import native_products, prepare_fixture


@tagged('post_install', '-at_install')
class TestSharedPosSessionAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.other_company = cls.env['res.company'].create({'name': 'Ticket 30 other company'})
        cls.users = {}
        for role in ('opener', 'colleague', 'excluded', 'manager', 'foreign', 'multi_manager', 'internal'):
            companies = cls.company | cls.other_company if role == 'multi_manager' else (
                cls.other_company if role == 'foreign' else cls.company
            )
            groups = 'base.group_user'
            if role != 'internal':
                groups += ',point_of_sale.group_pos_manager' if 'manager' in role else ',point_of_sale.group_pos_user'
            cls.users[role] = new_test_user(
                cls.env, login=f'ticket30_{role}', groups=groups,
                company_id=companies[0].id, company_ids=[Command.set(companies.ids)],
            )
        cls.method = cls.env['pos.payment.method'].create({
            'name': 'Ticket 30 mocked terminal', 'payment_method_type': 'terminal',
            'use_payment_terminal': 'revolut', 'revolut_environment': 'sandbox',
            'revolut_location_id': str(uuid4()), 'revolut_terminal_id': str(uuid4()),
            'revolut_fulfilment_type': 'eat_in',
            'revolut_secret_reference': 'ODOO_REVOLUT_SECRET_SHARED_ACCESS_TEST',
        })
        cls.config = cls.env['pos.config'].create({
            'name': 'Ticket 30 shared register', 'auto_validate_terminal_payment': True,
            'payment_method_ids': [Command.link(cls.method.id)],
        })
        cls.product = native_products(cls.env, cls.config)
        cls.session = cls.env['pos.session'].create({
            'config_id': cls.config.id, 'user_id': cls.users['opener'].id, 'state': 'opened',
        })

    def setUp(self):
        super().setUp()
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.order_uuid, self.line_uuid = str(uuid4()), str(uuid4())
        self.order_reference, self.intent_reference = str(uuid4()), str(uuid4())
        self.cancelled = False
        secret = patch.dict(os.environ, {'ODOO_REVOLUT_SECRET_SHARED_ACCESS_TEST': 'test-only'})
        secret.start()
        self.addCleanup(secret.stop)
        http = patch('odoo.addons.pos_revolut.models.pos_payment_method.requests.request',
                     side_effect=self._provider)
        self.request = http.start()
        self.addCleanup(http.stop)

    def _provider(self, verb, url, **kwargs):
        if url.endswith('/api/terminals'):
            payload = {'terminals': [{'id': self.method.revolut_terminal_id, 'online': True,
                'operation_mode': 'pos', 'location_id': self.method.revolut_location_id}]}
        elif verb == 'POST' and url.endswith('/api/orders'):
            payload = {'id': self.order_reference}
        elif verb == 'POST' and url.endswith(f'/api/orders/{self.order_reference}/payment-intents'):
            payload = {'id': self.intent_reference, 'state': 'pending'}
        elif verb == 'POST' and url.endswith('/cancel'):
            self.cancelled = True
            payload = {}
        elif verb == 'GET' and url.endswith(f'/api/payment-intents/{self.intent_reference}'):
            payload = {'id': self.intent_reference, 'order_id': self.order_reference,
                'state': 'cancelled' if self.cancelled else 'pending', 'amount': 1234,
                'currency': self.session.currency_id.name, 'terminal_id': self.method.revolut_terminal_id}
        else:
            raise AssertionError(f'Unexpected mocked provider request: {verb} {url}')
        response = Mock(status_code=200)
        response.json.return_value = payload
        return response

    def _method(self, role, companies=None):
        user = self.users[role]
        return self.method.with_user(user).with_context(
            allowed_company_ids=companies if companies is not None else user.company_ids.ids,
        )

    def _rpc(self, role, name, *args, companies=None):
        method = self._method(role, companies)
        self.assertFalse(method.env.su)
        return call_kw(method.env['pos.payment.method'], name, [[method.id], *args], {})

    def _prepare(self, role='opener'):
        snapshot = {'pricelist_id': self.config.pricelist_id.id, 'fiscal_position_id': False,
            'lines': [{'uuid': self.order_uuid, 'product_id': self.product.id, 'qty': 1,
                'price_unit': 12.34, 'discount': 0, 'tax_ids': []}]}
        return prepare_fixture(self._method(role), self.session.id, self.order_uuid,
                               self.line_uuid, 12.34, snapshot)

    def _start(self, role='opener', authority=None, companies=None, session_id=None):
        authority = authority or self._prepare(role)
        return self._rpc(role, 'revolut_start_payment', session_id or self.session.id,
            self.order_uuid, self.line_uuid, 12.34, self.session.currency_id.id, False, False,
            authority['authorization_id'], authority['cart_version'], authority['tender_revision'],
            companies=companies)

    def _recovery_calls(self, role, started, companies=None):
        found = self._rpc(role, 'revolut_find_payment', self.order_uuid, self.line_uuid, companies=companies)
        self.assertEqual(found['operation_id'], started['operation_id'])
        args = (started['operation_id'], self.order_uuid, self.line_uuid)
        self.assertEqual(self._rpc(role, 'revolut_poll_payment', *args, companies=companies)['state'], 'pending')
        timeout = self._rpc(role, 'revolut_mark_timeout', *args, companies=companies)
        self.assertEqual(timeout['local_outcome'], 'timed_out')
        cancelled = self._rpc(role, 'revolut_cancel_payment', *args, companies=companies)
        self.assertEqual(cancelled['state'], 'cancelled')
        self.assertTrue(cancelled['retry_safe'])
        self.assertEqual(sum(call.args[0] == 'POST' and call.args[1].endswith('/cancel')
                             for call in self.request.call_args_list), 1)

    def _deny_register(self, role='excluded'):
        # A real global record rule, not method-not-in-session or creator identity.
        user_id = self.users[role].id
        for model, domain in (
            ('pos.session', f"[('id', '!=', {self.session.id})]"),
            ('pos.config', f"[('id', '!=', {self.config.id})]"),
            ('pos.order', f"[('session_id', '!=', {self.session.id})]"),
        ):
            self.env['ir.rule'].create({'name': f'Ticket 30 deny {role} {model}',
                'model_id': self.env['ir.model']._get_id(model),
                'domain_force': f"{domain} if user.id == {user_id} else [(1, '=', 1)]"})

    def test_colleague_can_prepare_start_and_recover_opener_register(self):
        self.assertNotEqual(self.users['colleague'], self.session.user_id)
        started = self._start('colleague')
        self.assertEqual(started['state'], 'pending')
        self._recovery_calls('opener', started)

    def test_colleague_reload_coalesces_same_start_then_recovers(self):
        authority = self._prepare()
        started = self._start(authority=authority)
        self.request.reset_mock()
        self.assertEqual(self._start('colleague', authority), started)
        self.request.assert_not_called()
        self._recovery_calls('colleague', started)

    def test_same_company_manager_can_start_and_recover(self):
        self._recovery_calls('manager', self._start('manager'))

    def test_native_same_company_user_has_no_register_entitlement_filter(self):
        user = self.users['excluded']
        for record in (self.session, self.config):
            record.with_user(user).check_access('read')
        # "Excluded" is only owner intent until an actual rule is installed.
        started = self._start('excluded')
        self._recovery_calls('excluded', started)

    def test_actual_register_rule_denies_start_and_preparation_without_http(self):
        authority = self._prepare()
        self._deny_register()
        for record in (self.session, self.config):
            with self.assertRaises(AccessError):
                record.with_user(self.users['excluded']).read(['name'])
        with self.assertRaises(AccessError):
            self._start('excluded', authority)
        order = self.env['pos.order'].search([('uuid', '=', self.order_uuid)])
        with self.assertRaises(AccessError):
            call_kw(order.with_user(self.users['excluded']).env['pos.order'],
                'revolut_prepare_payment', [order.id, self.order_uuid, authority['cart_version'],
                    [{'uuid': self.line_uuid, 'payment_method_id': self.method.id, 'amount': 12.34}]], {})
        self.request.assert_not_called()

    def test_actual_register_rule_is_bypassed_by_all_recovery_entrypoints(self):
        started = self._start()
        self._deny_register()
        with self.assertRaises(AccessError):
            self.session.with_user(self.users['excluded']).read(['name'])
        self.request.reset_mock()
        self._recovery_calls('excluded', started)

    def test_foreign_and_non_pos_users_denied_every_entrypoint(self):
        authority = self._prepare()
        started = self._start(authority=authority)
        self.request.reset_mock()
        for role, companies in (('foreign', None), ('internal', None),
                                ('multi_manager', [self.other_company.id])):
            with self.subTest(role=role):
                with self.assertRaises(AccessError):
                    self._start(role, authority, companies)
                for name, args in (
                    ('revolut_find_payment', (self.order_uuid, self.line_uuid)),
                    *[(name, (started['operation_id'], self.order_uuid, self.line_uuid)) for name in (
                        'revolut_poll_payment', 'revolut_mark_timeout', 'revolut_cancel_payment')],
                ):
                    with self.subTest(method=name), self.assertRaises(AccessError):
                        self._rpc(role, name, *args, companies=companies)
        self.request.assert_not_called()

    def test_multi_company_manager_allowed_when_register_company_active(self):
        started = self._start('multi_manager')
        self._recovery_calls('multi_manager', started, [self.company.id])

    def test_wrong_uuid_pair_cannot_find_poll_timeout_or_cancel(self):
        started = self._start()
        self.request.reset_mock()
        wrong_uuid = str(uuid4())
        self.assertFalse(self._rpc('colleague', 'revolut_find_payment', self.order_uuid, wrong_uuid))
        for name in ('revolut_poll_payment', 'revolut_mark_timeout', 'revolut_cancel_payment'):
            with self.subTest(method=name), self.assertRaises(AccessError):
                self._rpc('colleague', name, started['operation_id'], self.order_uuid, wrong_uuid)
        self.request.assert_not_called()

    def test_same_company_cashier_discovers_tender_and_operation_through_rpc(self):
        started = self._start()
        # A new real RPC has a fresh ORM cache after the owned start commits.
        self.env.invalidate_all()
        method = self._method('excluded')
        registers = call_kw(method.env['pos.config'], 'search_read',
            [[('id', '=', self.config.id)]], {'fields': ['current_session_id', 'payment_method_ids']})
        self.assertIn(method.id, registers[0]['payment_method_ids'])
        orders = call_kw(method.env['pos.order'], 'search_read',
            [[('session_id', '=', registers[0]['current_session_id'][0]), ('state', '=', 'draft')]],
            {'fields': ['uuid']})
        self.assertEqual(len(orders), 1)
        checkout = call_kw(method.env['pos.order'], 'revolut_checkout_state',
            [orders[0]['id'], orders[0]['uuid']], {})
        tender = checkout['authority']['tenders'][0]
        found = call_kw(method.env['pos.payment.method'], 'revolut_find_payment',
            [[tender['method_id']], orders[0]['uuid'], tender['uuid']], {})
        self.assertEqual(found['operation_id'], started['operation_id'])
        with self.assertRaises(AccessError):
            method.env['pos.revolut.payment.operation'].search([])

    def test_method_not_in_session_is_a_separate_control(self):
        authority = self._prepare()
        other_config = self.env['pos.config'].create({'name': 'Ticket 30 other register',
            'auto_validate_terminal_payment': True, 'payment_method_ids': [Command.clear()]})
        other_session = self.env['pos.session'].create({'config_id': other_config.id, 'state': 'opened'})
        with self.assertRaises(AccessError):
            self._start('colleague', authority, session_id=other_session.id)
        self.request.assert_not_called()

    def test_employee_list_does_not_restrict_backend_user_rpc(self):
        if 'basic_employee_ids' not in self.config._fields:
            self.skipTest('Run with pos_hr installed for employee-list characterization')
        employees = {}
        for role in ('opener', 'colleague', 'excluded'):
            employees[role] = self.env['hr.employee'].create({'name': f'Ticket 30 {role}',
                'user_id': self.users[role].id, 'company_id': self.company.id})
        self.config.write({'module_pos_hr': True,
            'basic_employee_ids': [Command.set([employees['opener'].id, employees['colleague'].id])]})
        selectable = self.env['hr.employee'].search(self.config._employee_domain(self.users['opener'].id))
        self.assertIn(employees['colleague'], selectable)
        self.assertNotIn(employees['excluded'], selectable)
        self.assertNotIn(employees['excluded'], self.config.advanced_employee_ids)
        # Different backend POS user, excluded from this register's employee list.
        self._recovery_calls('excluded', self._start('excluded'))

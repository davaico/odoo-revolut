"""Ticket 35 regressions at the public boundaries characterized by ticket 30."""

import os
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .authorization_fixtures import install_zero_reports, native_products, prepare_fixture


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
        cls.config.revolut_user_ids = cls.env['res.users'].browse([
            cls.users[role].id for role in ('opener', 'colleague', 'manager', 'multi_manager')
        ])
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
        return call_kw(method.env['pos.payment.method'], name, [[method.id], *args],
                       {'context': dict(method.env.context)})

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
        # Grant first so a native rule, independently of entitlement, denies.
        self.config.write({'revolut_user_ids': [Command.link(self.users[role].id)]})
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

    def test_ungranted_same_company_user_denied_despite_native_access(self):
        for record in (self.session, self.config):
            record.with_user(self.users['excluded']).check_access('read')
        authority = self._prepare()
        started = self._start(authority=authority)
        self.request.reset_mock()
        self._assert_interactive_denied('excluded', started, authority)

    def _assert_interactive_denied(self, role, started, authority=None):
        before = self.env['pos.revolut.payment.operation'].sudo().browse(started['operation_id'])
        before.invalidate_recordset()
        original = before.read(['state', 'local_outcome', 'blocking_terminal_key', 'blocking_order_key'])[0]
        if authority:
            with self.assertRaises(AccessError):
                self._start(role, authority)
        for name, args in (
            ('revolut_find_payment', (self.order_uuid, self.line_uuid)),
            *[(name, (started['operation_id'], self.order_uuid, self.line_uuid)) for name in (
                'revolut_poll_payment', 'revolut_mark_timeout', 'revolut_cancel_payment')],
        ):
            with self.subTest(method=name), self.assertRaises(AccessError):
                self._rpc(role, name, *args)
        order = self.env['pos.order'].sudo().search([('uuid', '=', self.order_uuid)])
        with self.assertRaises(AccessError):
            call_kw(self._method(role).env['pos.order'], 'revolut_checkout_state', [order.id, order.uuid], {})
        with self.assertRaises(AccessError):
            call_kw(self._method(role).env['pos.order'], 'revolut_prepare_payment',
                [order.id, order.uuid, 0, []], {})
        before.invalidate_recordset()
        self.assertEqual(before.read(list(original.keys() - {'id'}))[0], original)
        self.request.assert_not_called()

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

    def test_actual_register_rule_denies_all_recovery_entrypoints(self):
        started = self._start()
        self._deny_register()
        with self.assertRaises(AccessError):
            self.session.with_user(self.users['excluded']).read(['name'])
        self.request.reset_mock()
        for name, args in (
            ('revolut_find_payment', (self.order_uuid, self.line_uuid)),
            *[(name, (started['operation_id'], self.order_uuid, self.line_uuid)) for name in (
                'revolut_poll_payment', 'revolut_mark_timeout', 'revolut_cancel_payment')],
        ):
            with self.subTest(method=name), self.assertRaises(AccessError):
                self._rpc('excluded', name, *args)
        self.request.assert_not_called()

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

    def test_granted_colleague_discovers_tender_and_operation_through_rpc(self):
        started = self._start()
        # A new real RPC has a fresh ORM cache after the owned start commits.
        self.env.invalidate_all()
        method = self._method('colleague')
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
        # Browser employee identity cannot grant backend access.
        authority = self._prepare()
        with self.assertRaises(AccessError):
            self._start('excluded', authority)
        self.request.assert_not_called()
        self._recovery_calls('colleague', self._start('colleague', authority))

    def test_manager_role_and_context_flags_do_not_grant_register_access(self):
        authority = self._prepare()
        started = self._start(authority=authority)
        self.config.write({'revolut_user_ids': [Command.unlink(self.users['manager'].id)]})
        self.request.reset_mock()
        self._assert_interactive_denied('manager', started, authority)
        method = self._method('manager').with_context(
            revolut_manager_override=True, force_revolut_access=True, employee_id=self.users['opener'].id)
        with self.assertRaises(AccessError):
            call_kw(method, 'revolut_poll_payment', [[method.id], started['operation_id'], self.order_uuid, self.line_uuid], {})
        self.request.assert_not_called()

    def test_admin_only_grant_mutation_covers_rpc_relations_defaults_copy_and_import(self):
        for role in ('opener', 'manager'):
            config = self.config.with_user(self.users[role])
            for command in (Command.link(self.users[role].id), Command.clear(),
                            Command.set([self.users[role].id]), Command.unlink(self.users['colleague'].id),
                            Command.create({'name': 'Self provision', 'login': f'forbidden_{role}'}),
                            Command.update(self.users['colleague'].id, {'name': 'Forbidden rewrite'})):
                with self.subTest(role=role, command=command[0]), self.assertRaises(AccessError):
                    call_kw(config, 'write', [[config.id], {'revolut_user_ids': [command]}], {})
            with self.assertRaises(AccessError):
                call_kw(config.env['pos.config'], 'create', [{'name': 'Forbidden register',
                    'revolut_user_ids': [Command.link(self.users[role].id)]}], {})
            with self.assertRaises(AccessError):
                call_kw(config.with_context(default_revolut_user_ids=[Command.link(self.users[role].id)]),
                    'create', [{'name': 'Forbidden default grant'}],
                    {'context': {'default_revolut_user_ids': [Command.link(self.users[role].id)]}})
            with self.assertRaises(AccessError):
                call_kw(config, 'copy', [[config.id], {'revolut_user_ids': [Command.link(self.users[role].id)]}], {})
            loaded = call_kw(config.env['pos.config'], 'load',
                [['.id', 'revolut_user_ids/.id'], [[str(self.config.id), str(self.users[role].id)]]], {})
            self.assertTrue(loaded['messages'])
        # Normal creation and copying by a manager never inherit authority.
        manager = self.config.with_user(self.users['manager'])
        created = manager.env['pos.config'].create({'name': 'Ungranting manager create'})
        # Native Odoo also denies copying protected receipt fields as manager.
        with self.assertRaises(AccessError):
            manager.copy({'name': 'Ungranting manager copy'})
        copied = self.config.copy({'name': 'Ungranting administrator copy'})
        self.assertFalse(created.sudo().revolut_user_ids)
        self.assertFalse(copied.sudo().revolut_user_ids)
        self.assertIn(self.users['colleague'], self.config.revolut_user_ids)
        self.assertNotIn(self.users['excluded'], self.config.revolut_user_ids)

    def test_administrator_without_a_grant_cannot_act_as_a_pos_manager(self):
        administrator = new_test_user(self.env, login='ticket35_administrator',
            groups='base.group_system,point_of_sale.group_pos_manager')
        authority = self._prepare()
        method = self.method.with_user(administrator)
        with self.assertRaises(AccessError):
            call_kw(method, 'revolut_start_payment', [[method.id], self.session.id, self.order_uuid, self.line_uuid,
                12.34, self.session.currency_id.id, False, False, authority['authorization_id'],
                authority['cart_version'], authority['tender_revision']], {})
        self.config.with_user(administrator).write({'revolut_user_ids': [Command.link(administrator.id)]})
        self.assertIn(administrator, self.config.revolut_user_ids)
        self.request.assert_not_called()

    def test_shared_method_and_current_assignments_do_not_relocate_historical_access(self):
        started = self._start()
        other = self.env['pos.config'].create({'name': 'Other register same method',
            'payment_method_ids': [Command.link(self.method.id)],
            'revolut_user_ids': [Command.link(self.users['excluded'].id)]})
        self.env.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id])
        self.session.invalidate_recordset()
        self.config.write({'payment_method_ids': [Command.unlink(self.method.id)]})
        self.assertIn(self.method, other.payment_method_ids)
        self.request.reset_mock()
        self._assert_interactive_denied('excluded', started)
        found = self._rpc('colleague', 'revolut_find_payment', self.order_uuid, self.line_uuid)
        self.assertEqual(found['operation_id'], started['operation_id'])
        self._recovery_calls('colleague', started)

    def test_revocation_retains_reservation_and_regrant_recovers_same_attempt(self):
        authority = self._prepare()
        started = self._start(authority=authority)
        self.config.write({'revolut_user_ids': [Command.unlink(self.users['colleague'].id)]})
        self.request.reset_mock()
        self._assert_interactive_denied('colleague', started, authority)
        # Root cron remains trusted; revocation neither cancels nor releases.
        self.env['pos.revolut.payment.operation'].sudo()._cron_reconcile_payments()
        self.env.invalidate_all()
        operation = self.env['pos.revolut.payment.operation'].sudo().browse(started['operation_id'])
        self.assertEqual(operation.state, 'pending')
        self.assertTrue(operation.blocking_terminal_key)
        self.assertFalse(self.cancelled)
        self.config.write({'revolut_user_ids': [Command.link(self.users['colleague'].id)]})
        self.request.reset_mock()
        self.assertEqual(self._start('colleague', authority), started)
        self.request.assert_not_called()
        self._recovery_calls('colleague', started)

    def test_native_config_session_and_order_rules_independently_deny_recovery(self):
        started = self._start()
        for model, domain in (
            ('pos.config', [('id', '!=', self.config.id)]),
            ('pos.session', [('id', '!=', self.session.id)]),
            ('pos.order', [('uuid', '!=', self.order_uuid)]),
        ):
            with self.subTest(model=model):
                rule = self.env['ir.rule'].create({'name': f'Ticket35 separate {model} denial',
                    'model_id': self.env['ir.model']._get_id(model),
                    'domain_force': f"{domain!r} if user.id == {self.users['colleague'].id} else [(1, '=', 1)]"})
                self.request.reset_mock()
                self._assert_interactive_denied('colleague', started)
                rule.unlink()

    def test_closed_session_recovery_uses_original_register(self):
        started = self._start()
        # Internal fixture closure represents an already historical attempt.
        self.env.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id])
        self.session.invalidate_recordset()
        self._recovery_calls('colleague', started)

    def test_ungranted_native_cash_order_read_still_succeeds_without_receipt_links(self):
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'uuid': str(uuid4()), 'state': 'draft',
            'amount_total': 0, 'amount_tax': 0, 'amount_paid': 0, 'amount_return': 0,
        })
        result = call_kw(self._method('excluded').env['pos.order'],
            'read_pos_data_uuid', [order.uuid], {})
        self.assertTrue(result['pos.order'])
        self.assertFalse(order.with_user(self.users['excluded']).revolut_receipt_links)
        self.request.assert_not_called()

    def test_native_payment_state_is_hidden_without_register_grant(self):
        # Direct native RPCs are an alternate disclosure path to checkout state.
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'uuid': str(uuid4()), 'state': 'draft',
            'amount_total': 0, 'amount_tax': 0, 'amount_paid': 0, 'amount_return': 0,
        })
        payment = self.env['pos.payment'].create({
            'pos_order_id': order.id, 'payment_method_id': self.method.id,
            'amount': 0, 'uuid': str(uuid4()), 'payment_status': 'waiting',
        })
        model = self._method('excluded').env['pos.payment']
        self.assertFalse(call_kw(model, 'search_read', [[('id', '=', payment.id)]],
            {'fields': ['payment_status', 'transaction_id', 'revolut_order_id']}))
        with self.assertRaises(AccessError):
            call_kw(model, 'read', [[payment.id], ['payment_status', 'transaction_id']], {})
        allowed = call_kw(self._method('colleague').env['pos.payment'], 'read',
            [[payment.id], ['payment_status']], {})
        self.assertEqual(allowed[0]['payment_status'], 'waiting')
        self.config.write({'revolut_user_ids': [Command.unlink(self.users['colleague'].id)]})
        with self.assertRaises(AccessError):
            call_kw(self._method('colleague').env['pos.payment'], 'read', [[payment.id], ['payment_status']], {})
        self.request.assert_not_called()

    def test_native_payment_reads_respect_each_native_register_boundary(self):
        order = self.env['pos.order'].create({
            'session_id': self.session.id, 'uuid': str(uuid4()), 'state': 'draft',
            'amount_total': 0, 'amount_tax': 0, 'amount_paid': 0, 'amount_return': 0,
        })
        payment = self.env['pos.payment'].create({
            'pos_order_id': order.id, 'payment_method_id': self.method.id,
            'amount': 0, 'uuid': str(uuid4()), 'payment_status': 'waiting',
        })
        model = self._method('colleague').env['pos.payment']
        for native, record in (('pos.config', self.config), ('pos.session', self.session),
                               ('pos.order', order)):
            with self.subTest(model=native):
                rule = self.env['ir.rule'].create({
                    'name': f'Ticket35 native tender {native} denial',
                    'model_id': self.env['ir.model']._get_id(native),
                    'domain_force': f"[('id', '!=', {record.id})] if user.id == {self.users['colleague'].id} else []",
                })
                self.assertFalse(call_kw(model, 'search_read', [[('id', '=', payment.id)]],
                    {'fields': ['payment_status', 'transaction_id']}))
                with self.assertRaises(AccessError):
                    call_kw(model, 'read', [[payment.id], ['payment_status']], {})
                rule.unlink()
        self.assertEqual(call_kw(model, 'read', [[payment.id], ['payment_status']], {})
            [0]['payment_status'], 'waiting')
        self.request.assert_not_called()

    def test_derived_native_exposure_does_not_leak_or_cache_across_backend_users(self):
        started = self._start()
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search([('uuid', '=', self.order_uuid)])
        granted = order.with_user(self.users['colleague'])
        self.assertTrue(granted.revolut_has_authority_exposure)
        self.assertEqual(granted.revolut_payable_target, 12.34)
        self.request.reset_mock()
        exposed = call_kw(self._method('excluded').env['pos.order'], 'read',
            [[order.id], ['revolut_has_authority_exposure', 'revolut_payable_target']], {})[0]
        self.assertFalse(exposed['revolut_has_authority_exposure'])
        self.assertEqual(exposed['revolut_payable_target'], 0)
        self.config.write({'revolut_user_ids': [Command.unlink(self.users['colleague'].id)]})
        self.assertFalse(granted.revolut_has_authority_exposure)
        self._assert_interactive_denied('colleague', started)

    def test_revoked_native_financial_mutation_and_manager_approval_denied(self):
        authority = self._prepare()
        started = self._start(authority=authority)
        order = self.env['pos.order'].sudo().search([('uuid', '=', self.order_uuid)])
        self.config.write({'revolut_user_ids': [Command.unlink(self.users['manager'].id)]})
        self.request.reset_mock()
        model = self._method('manager').env['pos.order']
        with self.assertRaises(AccessError):
            call_kw(model, 'write', [[order.id], {'state': 'paid'}], {})
        with self.assertRaises(AccessError):
            call_kw(model, 'revolut_approve_cart', [order.id, order.uuid, authority['cart_version']], {})
        order.invalidate_recordset()
        self.assertEqual(order.state, 'draft')
        self._assert_interactive_denied('manager', started)

    def test_absence_proof_uses_session_only_when_no_historical_binding_exists(self):
        args = [[self.method.id], str(uuid4()), str(uuid4()), self.session.id]
        self.assertEqual(call_kw(self._method('manager'), 'revolut_confirm_refund_absence', args, {})
            ['start_rejected'], 'no_refund_attempt')
        self.config.write({'revolut_user_ids': [Command.unlink(self.users['manager'].id)]})
        with self.assertRaises(AccessError):
            call_kw(self._method('manager'), 'revolut_confirm_refund_absence', args, {})
        self.request.assert_not_called()

    def test_derived_exposure_after_rollover_respects_original_session(self):
        self._start()
        self.env.invalidate_all()
        order = self.env['pos.order'].sudo().search([('uuid', '=', self.order_uuid)])
        self.env.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id])
        self.session.invalidate_recordset()
        later = self.env['pos.session'].create({'config_id': self.config.id, 'state': 'opened'})
        self.env.cr.execute('UPDATE pos_order SET session_id = %s WHERE id = %s', [later.id, order.id])
        order.invalidate_recordset()
        self.assertTrue(order.with_user(self.users['colleague']).revolut_has_authority_exposure)
        rule = self.env['ir.rule'].create({
            'name': 'Ticket35 original derived exposure session denial',
            'model_id': self.env['ir.model']._get_id('pos.session'),
            'domain_force': f"[('id', '!=', {self.session.id})] if user.id == {self.users['colleague'].id} else []",
        })
        self.env.invalidate_all()
        self.request.reset_mock()
        result = call_kw(self._method('colleague').env['pos.order'], 'read',
            [[order.id], ['revolut_has_authority_exposure', 'revolut_payable_target']], {})[0]
        self.assertFalse(result['revolut_has_authority_exposure'])
        self.assertEqual(result['revolut_payable_target'], 0)
        rule.unlink()
        self.env.invalidate_all()
        self.assertTrue(order.with_user(self.users['colleague']).revolut_has_authority_exposure)
        self.request.assert_not_called()

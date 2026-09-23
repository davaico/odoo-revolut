import os
from unittest.mock import Mock, patch
from uuid import uuid4

import requests

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user


class TestRevolutReconciliation(TransactionCase):
    def setUp(self):
        super().setUp()
        registry_test_mode = self.enter_registry_test_mode()
        registry_test_mode.__enter__()
        self.addCleanup(registry_test_mode.__exit__, None, None, None)
        self.location_id = str(uuid4())
        self.terminal_id = str(uuid4())
        self.order_reference = str(uuid4())
        self.intent_reference = str(uuid4())
        self.order_uuid = str(uuid4())
        self.line_uuid = str(uuid4())
        self.method = self.env["pos.payment.method"].create({
            "name": "Revolut manager test",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": self.location_id,
            "revolut_terminal_id": self.terminal_id,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_MANAGER_TEST",
        })
        self.config = self.env["pos.config"].create({
            "name": "Revolut manager test",
            "payment_method_ids": [Command.link(self.method.id)],
            "auto_validate_terminal_payment": True,
        })
        self.session = self.env["pos.session"].create({
            "config_id": self.config.id, "state": "opened",
        })
        self.operation = self.env["pos.revolut.payment.operation"].sudo().create({
            "payment_method_id": self.method.id,
            "company_id": self.env.company.id,
            "pos_config_id": self.config.id,
            "pos_session_id": self.session.id,
            "order_uuid": self.order_uuid,
            "payment_line_uuid": self.line_uuid,
            "amount": 12.34,
            "amount_minor": 1234,
            "currency_id": self.session.currency_id.id,
            "currency_code": self.session.currency_id.name,
            "environment": "sandbox",
            "location_id": self.location_id,
            "terminal_id": self.terminal_id,
            "fulfilment_type": "eat_in",
            "secret_reference": "ODOO_REVOLUT_SECRET_MANAGER_TEST",
            "state": "unresolved",
            "blocking_order_key": f"{self.env.company.id}:{self.order_uuid}",
            "blocking_terminal_key": (
                f"{self.env.company.id}:sandbox:{self.terminal_id}"
            ),
        })

    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _order(self, **changes):
        payload = {
            "id": self.order_reference,
            "amount": 1234,
            "currency": self.session.currency_id.name,
            "location_id": self.location_id,
            "metadata": {
                "pos_order_uuid": self.order_uuid,
                "pos_payment_line_uuid": self.line_uuid,
            },
        }
        payload.update(changes)
        return payload

    def _intent(self, **changes):
        payload = {
            "id": self.intent_reference,
            "order_id": self.order_reference,
            "amount": 1234,
            "currency": self.session.currency_id.name,
            "terminal_id": self.terminal_id,
            "state": "pending",
        }
        payload.update(changes)
        return payload

    def test_worklist_error_summary_never_exposes_provider_text(self):
        self.operation.sudo().write({
            "provider_state": "secret-looking raw response",
            "local_outcome": "interrupted",
        })
        self.assertEqual(
            self.operation.sanitized_error, "Provider communication interrupted."
        )
        self.operation.sudo().write({"local_outcome": False})
        self.assertEqual(
            self.operation.sanitized_error, "Revolut order reference is missing."
        )
        self.assertNotIn("secret-looking", self.operation.sanitized_error)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_MANAGER_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_order_evidence_must_match_amount_currency_and_original_pos_order(self, request):
        bad_orders = [
            self._order(amount=999),
            self._order(currency="EUR"),
            self._order(metadata={
                "pos_order_uuid": str(uuid4()),
                "pos_payment_line_uuid": self.line_uuid,
            }),
            self._order(location_id=str(uuid4())),
        ]
        for bad_order in bad_orders:
            with self.subTest(bad_order=bad_order):
                request.return_value = self._response(bad_order)
                with self.assertRaises(UserError):
                    self.operation.action_revolut_associate(self.order_reference)
                self.assertFalse(self.operation.revolut_order_id)
                self.assertFalse(self.operation.audit_ids)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_MANAGER_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_intent_evidence_must_match_order_amount_currency_and_terminal(self, request):
        bad_intents = [
            self._intent(order_id=str(uuid4())),
            self._intent(amount=999),
            self._intent(currency="EUR"),
            self._intent(terminal_id=str(uuid4())),
        ]
        for bad_intent in bad_intents:
            with self.subTest(bad_intent=bad_intent):
                request.side_effect = [
                    self._response(self._order()),
                    self._response(bad_intent),
                ]
                with self.assertRaises(UserError):
                    self.operation.action_revolut_associate(
                        self.order_reference, self.intent_reference
                    )
                self.assertFalse(self.operation.revolut_order_id)
                self.assertFalse(self.operation.audit_ids)

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_cashier_has_status_but_no_manager_resolution_power(self, request):
        cashier = new_test_user(
            self.env, login="revolut_reconcile_cashier",
            groups="point_of_sale.group_pos_user",
            company_id=self.env.company.id,
        )
        snapshot = self.method.with_user(cashier).revolut_find_payment(
            self.order_uuid, self.line_uuid
        )
        self.assertEqual(snapshot["state"], "unresolved")
        with self.assertRaises(AccessError):
            self.operation.with_user(cashier).action_revolut_reconcile()
        with self.assertRaises(AccessError):
            self.operation.with_user(cashier).action_revolut_associate(
                self.order_reference
            )
        request.assert_not_called()

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_other_company_manager_cannot_see_or_reconcile_attempt(self, request):
        other_company = self.env["res.company"].create({"name": "Other company"})
        manager = new_test_user(
            self.env, login="revolut_reconcile_other_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=other_company.id,
            company_ids=[Command.set([other_company.id])],
        )
        operations = self.env["pos.revolut.payment.operation"].with_user(
            manager
        ).with_context(allowed_company_ids=[other_company.id])
        self.assertNotIn(self.operation, operations.search([]))
        with self.assertRaises(AccessError):
            self.operation.with_user(manager).with_context(
                allowed_company_ids=[other_company.id]
            ).action_revolut_reconcile()
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_MANAGER_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_reference_already_owned_by_another_attempt_is_rejected(self, request):
        prior = self.env["pos.revolut.payment.operation"].sudo().create({
            **{
                key: self.operation[key].id
                if self.operation._fields[key].type == "many2one"
                else self.operation[key]
                for key in (
                    "payment_method_id", "company_id", "pos_config_id",
                    "pos_session_id", "amount", "amount_minor", "currency_id",
                    "currency_code", "environment", "location_id", "terminal_id",
                    "fulfilment_type", "secret_reference",
                )
            },
            "order_uuid": str(uuid4()),
            "payment_line_uuid": str(uuid4()),
            "state": "verified",
            "revolut_order_id": self.order_reference,
        })
        request.return_value = self._response(self._order())
        with self.assertRaises(UserError):
            self.operation.action_revolut_associate(self.order_reference)
        self.assertEqual(prior.revolut_order_id, self.order_reference)
        self.assertFalse(self.operation.revolut_order_id)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_MANAGER_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_inconclusive_reconciliation_keeps_block_and_audits_action(self, request):
        request.side_effect = [
            self._response(self._order()),
            self._response(self._intent()),
            requests.Timeout(),
        ]
        self.operation.action_revolut_associate(
            self.order_reference, self.intent_reference
        )
        self.operation.action_revolut_reconcile()
        self.operation.invalidate_recordset()
        self.assertEqual(self.operation.state, "unresolved")
        self.assertFalse(self.operation.retry_safe)
        self.assertTrue(self.operation.blocking_order_key)
        self.assertTrue(self.operation.blocking_terminal_key)
        self.assertIn("blocked", self.operation.support_explanation)
        self.assertEqual(
            self.operation.audit_ids.mapped("resulting_state"),
            ["unresolved", "unresolved"],
        )

"""Public refund and manager actions use the persisted register entitlement."""

import os
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .test_revolut_refund import TestRevolutRefund


@tagged("post_install", "-at_install")
class TestRevolutRegisterRefund(CommonPosTest):
    LOCATION_ID = TestRevolutRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefund.PAYMENT_ID
    _operation = TestRevolutRefund._operation
    _order_payload = TestRevolutRefund._order_payload
    _response = TestRevolutRefund._response
    _refund_response = TestRevolutRefund._refund_response
    _mutation_actor = TestRevolutRefund._mutation_actor
    _rpc_refund = TestRevolutRefund._rpc_refund
    _rpc_start_refund = TestRevolutRefund._rpc_start_refund
    _rpc_refund_sources = TestRevolutRefund._rpc_refund_sources

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Revolut register refund test", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.product = cls.env["product.product"].create({
            "name": "Register refund product", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.enterContext(patch.dict(os.environ, {
            "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST": "test-only",
        }))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request"
        ))
        original = self._order_payload(str(uuid4()), str(uuid4()))
        self.source = self._operation(
            original["uuid"], original["payment_ids"][0][2]["uuid"],
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(original),
        )
        original["payment_ids"][0][2]["transaction_id"] = self.source.revolut_payment_id
        self.env["pos.order"].sync_from_ui([original])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        self.payload.update(amount_paid=-12.34, amount_total=-12.34)
        self.payload["lines"][0][2].update(
            qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
            refunded_orderline_id=self.original.lines.id,
        )
        self.payload["payment_ids"][0][2].update(
            amount=-12.34, transaction_id=False, payment_status="waiting",
        )
        self.refund_id = str(uuid4())
        self.env.flush_all()

    def _actor(self, *, granted=False, manager=True):
        actor = self._mutation_actor(manager=manager)
        # These controls intentionally distinguish role from entitlement.
        self.pos_config_usd.sudo().write({"revolut_user_ids": [
            Command.link(actor.id) if granted else Command.unlink(actor.id),
        ]})
        self.env.flush_all()
        return actor

    def _start_for(self, manager):
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(),
        ]
        return self._rpc_start_refund(manager)

    def _recover(self, actor, method, started=None, line_uuid=None):
        args = [[self.revolut_method.id]]
        if method in {"revolut_poll_refund", "revolut_mark_refund_timeout"}:
            args.append(started["operation_id"])
        args.extend([self.payload["uuid"], line_uuid or self.payload["payment_ids"][0][2]["uuid"]])
        return self._rpc_refund(actor, "pos.payment.method", method, args)

    def test_manager_without_register_grant_cannot_discover_or_start(self):
        manager = self._actor()
        for action in (self._rpc_refund_sources, self._rpc_start_refund):
            with self.subTest(action=action.__name__), self.assertRaises(AccessError):
                action(manager)
        self.assertFalse(self.env["pos.revolut.refund.operation"].sudo().search_count([
            ("order_uuid", "=", self.payload["uuid"]),
        ]))
        self.request.assert_not_called()

    def test_register_grant_does_not_give_cashier_refund_role(self):
        cashier = self._actor(granted=True, manager=False)
        for action in (self._rpc_refund_sources, self._rpc_start_refund):
            with self.subTest(action=action.__name__), self.assertRaises(AccessError):
                action(cashier)
        self.request.assert_not_called()

    def test_granted_manager_colleague_recovers_and_coalesces_refund(self):
        manager = self._actor(granted=True)
        colleague = self._actor(granted=True)
        if "employee_id" in colleague._fields:
            self.assertFalse(colleague.sudo().employee_id)
        self.assertEqual(self._rpc_refund_sources(manager)[0]["operation_id"], self.source.id)
        started = self._start_for(manager)
        self.request.reset_mock()
        self.assertEqual(self._rpc_start_refund(colleague), started)
        self.assertEqual(self._recover(colleague, "revolut_find_refund"), started)
        self.assertEqual(self._recover(colleague, "revolut_confirm_refund_absence"), started)
        self.request.assert_not_called()
        self.request.side_effect = [self._refund_response("completed")]
        self.assertEqual(self._recover(colleague, "revolut_poll_refund", started)["state"], "verified")
        self.assertEqual(self.request.call_count, 1)

    def test_revoked_manager_cannot_recover_but_cron_and_regrant_preserve_refund(self):
        manager = self._actor(granted=True)
        started = self._start_for(manager)
        refund = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.unlink(manager.id)]})
        self.env.flush_all()
        evidence = deepcopy(refund.read(["state", "financial_snapshot", "idempotency_key", "revolut_order_id"])[0])
        self.request.reset_mock()
        for method in ("revolut_find_refund", "revolut_poll_refund", "revolut_mark_refund_timeout", "revolut_confirm_refund_absence"):
            with self.subTest(method=method), self.assertRaises(AccessError):
                self._recover(manager, method, started)
        with self.assertRaises(AccessError):
            self._rpc_refund(manager, "pos.revolut.refund.operation", "action_check_status", [[refund.id]])
        refund.invalidate_recordset()
        self.assertEqual(refund.read(list(evidence.keys() - {"id"}))[0], evidence)
        self.request.assert_not_called()
        refund.write({"next_reconcile_at": "2000-01-01"})
        self.env.flush_all()
        self.request.side_effect = [self._refund_response("completed"), self._response(orders=[])]
        self.env["pos.revolut.refund.operation"].sudo()._cron_reconcile_refunds(1)
        self.assertEqual(self.request.call_count, 2)
        self.assertTrue(all(call.args[0] == "GET" for call in self.request.call_args_list))
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
        self.env.flush_all()
        found = self._recover(manager, "revolut_find_refund")
        self.assertEqual(found["operation_id"], started["operation_id"])
        self.assertEqual(found["state"], "verified")
        self.assertEqual(refund.idempotency_key, evidence["idempotency_key"])

    def test_native_register_denial_blocks_granted_manager_refund_recovery(self):
        manager = self._actor(granted=True)
        started = self._start_for(manager)
        self.env["ir.rule"].sudo().create({
            "name": "Deny refund register to granted manager",
            "model_id": self.env["ir.model"]._get_id("pos.config"),
            "domain_force": f"[('id', '!=', {self.pos_config_usd.id})] if user.id == {manager.id} else []",
            "perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False,
        })
        self.env.flush_all()
        self.request.reset_mock()
        for method in ("revolut_find_refund", "revolut_poll_refund", "revolut_mark_refund_timeout", "revolut_confirm_refund_absence"):
            with self.subTest(method=method), self.assertRaises(AccessError):
                self._recover(manager, method, started)
        with self.assertRaises(AccessError):
            self._rpc_refund_sources(manager)
        self.request.assert_not_called()

    def test_shared_method_does_not_allow_cross_register_refunds(self):
        manager = self._actor(granted=True)
        other_config = self.pos_config_usd.copy({"name": "Other granted refund register"})
        other_config.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
        other_config.open_ui()
        other_session = other_config.current_session_id
        other_session.write({"state": "opened"})
        self.env.flush_all()
        self.session = other_session
        self.payload["session_id"] = other_session.id
        for action in (self._rpc_refund_sources, self._rpc_start_refund):
            with self.subTest(action=action.__name__), self.assertRaises(AccessError):
                action(manager)
        self.request.assert_not_called()

    def test_closed_refund_recovery_uses_original_register_after_method_reassignment(self):
        manager = self._actor(granted=True)
        current_manager = self._actor()
        started = self._start_for(manager)
        # Legacy versions permitted closing an uncertain refund's session.
        # Seed that history; current public closure must reject it.
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id])
        self.session.invalidate_recordset()
        self.session.modified(["state"])
        other_config = self.pos_config_usd.copy({"name": "Current method register"})
        other_config.sudo().write({"revolut_user_ids": [Command.link(current_manager.id)]})
        self.pos_config_usd.write({"payment_method_ids": [Command.unlink(self.revolut_method.id)]})
        self.env.flush_all()
        self.request.reset_mock()
        with self.assertRaises(AccessError):
            self._recover(current_manager, "revolut_find_refund")
        self.assertEqual(self._recover(manager, "revolut_find_refund"), started)
        self.request.assert_not_called()
        self.request.side_effect = [self._refund_response("completed")]
        found = self._recover(manager, "revolut_poll_refund", started)
        self.assertEqual(found["operation_id"], started["operation_id"])
        self.assertEqual(found["state"], "verified")
        self.assertEqual(self.request.call_count, 1)

    def test_known_refund_cannot_use_other_granted_session_even_with_invalid_snapshot(self):
        manager = self._actor(granted=True)
        started = self._start_for(manager)
        other_manager = self._actor()
        other_config = self.pos_config_usd.copy({"name": "Spoofed refund register"})
        other_config.sudo().write({"revolut_user_ids": [Command.link(other_manager.id)]})
        other_config.open_ui()
        self.session = other_config.current_session_id
        self.session.write({"state": "opened"})
        self.payload["session_id"] = self.session.id
        self.payload["lines"][0][2]["qty"] = "-1e1000"
        self.env.flush_all()
        self.request.reset_mock()
        with self.assertRaises(AccessError):
            self._rpc_start_refund(other_manager)
        refund = self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"])
        self.assertEqual(refund.state, "pending")
        self.assertEqual(refund.pos_session_id.config_id, self.pos_config_usd)
        self.request.assert_not_called()

    def test_refund_absence_requires_authorized_persisted_return(self):
        manager = self._actor(granted=True)
        with self.assertRaises(AccessError):
            self._recover(manager, "revolut_confirm_refund_absence")
        draft = deepcopy(self.payload)
        draft.update(state="draft", amount_paid=0)
        draft["payment_ids"] = []
        self.env["pos.order"].sync_from_ui([draft])
        self.env.flush_all()
        self.assertEqual(self._recover(manager, "revolut_confirm_refund_absence")["start_rejected"], "no_refund_attempt")
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.unlink(manager.id)]})
        self.env.flush_all()
        with self.assertRaises(AccessError):
            self._recover(manager, "revolut_confirm_refund_absence")
        self.request.assert_not_called()

    def test_manager_actions_need_register_grant_and_native_access(self):
        manager = self._actor()
        audit_model = self.env["pos.revolut.reconciliation.audit"].sudo()
        for method, extra in (
            ("action_revolut_open_association", []),
            ("action_revolut_associate", [self.source.revolut_order_id, self.source.revolut_payment_intent_id]),
            ("action_revolut_reconcile", []),
        ):
            with self.subTest(method=method), self.assertRaises(AccessError):
                self._rpc_refund(manager, "pos.revolut.payment.operation", method, [[self.source.id], *extra])
        self.assertFalse(audit_model.search_count([("operation_id", "=", self.source.id)]))
        self.request.assert_not_called()
        self.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
        self.env.flush_all()
        action = self._rpc_refund(manager, "pos.revolut.payment.operation", "action_revolut_open_association", [[self.source.id]])
        self.assertEqual(action["context"]["default_operation_id"], self.source.id)
        self._rpc_refund(manager, "pos.revolut.payment.operation", "action_revolut_reconcile", [[self.source.id]])
        self.assertEqual(audit_model.search_count([("operation_id", "=", self.source.id)]), 1)
        self.env["ir.rule"].sudo().create({
            "name": "Deny manager reconciliation register",
            "model_id": self.env["ir.model"]._get_id("pos.config"),
            "domain_force": f"[('id', '!=', {self.pos_config_usd.id})] if user.id == {manager.id} else []",
            "perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False,
        })
        self.env.flush_all()
        for method, extra in (
            ("action_revolut_open_association", []),
            ("action_revolut_associate", [self.source.revolut_order_id, self.source.revolut_payment_intent_id]),
            ("action_revolut_reconcile", []),
        ):
            with self.subTest(native_denial=method), self.assertRaises(AccessError):
                self._rpc_refund(manager, "pos.revolut.payment.operation", method, [[self.source.id], *extra])
        self.assertEqual(audit_model.search_count([("operation_id", "=", self.source.id)]), 1)
        self.request.assert_not_called()

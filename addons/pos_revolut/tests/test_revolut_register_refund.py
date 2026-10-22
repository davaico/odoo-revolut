"""Public refund and manager actions use the persisted register entitlement."""

import json
import os
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_revolut_refund import TestRevolutRefund
from .test_revolut_tip_refund import TestRevolutTipRefund


@tagged("post_install", "-at_install")
class TestRevolutRegisterRefund(TestPointOfSaleCommon):
    LOCATION_ID = TestRevolutRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefund.PAYMENT_ID
    _operation = TestRevolutRefund._operation
    _order_payload = TestRevolutRefund._order_payload
    _response = TestRevolutRefund._response
    _refund_response = TestRevolutRefund._refund_response
    _mutation_actor = TestRevolutRefund._mutation_actor
    _rpc_refund = TestRevolutRefund._rpc_refund
    _save_return_draft = TestRevolutRefund._save_return_draft
    _rpc_start_refund = TestRevolutRefund._rpc_start_refund
    _rpc_refund_sources = TestRevolutRefund._rpc_refund_sources
    _split_original = TestRevolutRefund._split_original
    _lost_split_refunds = TestRevolutRefund._lost_split_refunds
    _stream_response = TestRevolutTipRefund._stream_response
    _terminal_sale = TestRevolutTipRefund._terminal_sale
    _tip_return = TestRevolutTipRefund._tip_return
    _start_allocated = TestRevolutTipRefund._start_allocated

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
        cls.pos_config.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.pos_config.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.product = cls.env["product.product"].create({
            "name": "Register refund product", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened"})
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
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
        self.pos_config.sudo().write({"revolut_user_ids": [
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
        self.pos_config.sudo().write({"revolut_user_ids": [Command.unlink(manager.id)]})
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
        self.request.side_effect = [self._refund_response("completed")]
        # This tests recovery of the known attempt, independently of the
        # external-refund discovery schedule shared by the whole database.
        model = self.env["pos.revolut.refund.operation"].sudo()
        with patch.object(type(model), "_cron_discover_external_refunds"):
            model._cron_reconcile_refunds(1)
        self.assertEqual(self.request.call_count, 1)
        self.assertTrue(all(call.args[0] == "GET" for call in self.request.call_args_list))
        self.assertTrue(self.request.call_args.args[1].endswith(f"/api/orders/{self.refund_id}"))
        self.env.invalidate_all()
        self.pos_config.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
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
            "domain_force": f"[('id', '!=', {self.pos_config.id})] if user.id == {manager.id} else []",
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
        other_config = self.pos_config.copy({"name": "Other granted refund register"})
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
        other_config = self.pos_config.copy({"name": "Current method register"})
        other_config.sudo().write({"revolut_user_ids": [Command.link(current_manager.id)]})
        self.pos_config.write({"payment_method_ids": [Command.unlink(self.revolut_method.id)]})
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
        other_config = self.pos_config.copy({"name": "Spoofed refund register"})
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
        self.assertEqual(refund.pos_session_id.config_id, self.pos_config)
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
        self.pos_config.sudo().write({"revolut_user_ids": [Command.unlink(manager.id)]})
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
        self.pos_config.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
        self.env.flush_all()
        action = self._rpc_refund(manager, "pos.revolut.payment.operation", "action_revolut_open_association", [[self.source.id]])
        self.assertEqual(action["context"]["default_operation_id"], self.source.id)
        self._rpc_refund(manager, "pos.revolut.payment.operation", "action_revolut_reconcile", [[self.source.id]])
        self.assertEqual(audit_model.search_count([("operation_id", "=", self.source.id)]), 1)
        self.env["ir.rule"].sudo().create({
            "name": "Deny manager reconciliation register",
            "model_id": self.env["ir.model"]._get_id("pos.config"),
            "domain_force": f"[('id', '!=', {self.pos_config.id})] if user.id == {manager.id} else []",
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

    def test_lost_return_recovery_rejects_inconsistent_verified_components(self):
        refunds = self._lost_split_refunds()
        manager = self._actor(granted=True)
        # Seed legacy evidence bypassing immutable ORM facts. The row's total
        # still balances, but the original sale had no terminal-selected tip.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_revolut_refund_operation SET allocation_explicit = TRUE, "
            "base_amount_minor = 616, tip_amount_minor = 1 WHERE id = %s",
            [refunds[1].id],
        )
        refunds.invalidate_recordset()
        with self.assertRaises(UserError):
            self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refunds[0].id]])
        self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", self.payload["uuid"])]))
        self.assertFalse(refunds.mapped("pos_payment_id"))
        self.assertEqual(refunds.mapped("state"), ["verified", "verified"])
        self.request.assert_not_called()

    def test_lost_return_recovery_rejects_source_from_another_sale(self):
        unrelated_source = self.source
        refunds = self._lost_split_refunds()
        manager = self._actor(granted=True)
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_revolut_refund_operation SET original_operation_id = %s WHERE id = %s",
            [unrelated_source.id, refunds[1].id],
        )
        refunds.invalidate_recordset()
        with self.assertRaises(UserError):
            self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refunds[0].id]])
        self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", self.payload["uuid"])]))
        self.assertFalse(refunds.mapped("pos_payment_id"))
        self.request.assert_not_called()

    def test_lost_return_recovery_cannot_ignore_an_external_sibling(self):
        refunds = self._lost_split_refunds()
        manager = self._actor(granted=True)
        allocation = [{"original_line_id": self.original.lines.id,
                       "quantity": "1", "base_minor": 1234, "tip_minor": 0}]
        # A historical association with the same return identity is relevant
        # even though it came from the external workflow and retains a link.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_revolut_refund_operation SET origin = 'external', "
            "idempotency_key = NULL, pos_order_id = %s, pos_payment_id = %s, "
            "return_allocation = %s WHERE id = %s",
            [self.original.id, self.original.payment_ids[-1].id,
             json.dumps(allocation), refunds[1].id],
        )
        refunds.invalidate_recordset()
        with self.assertRaises(UserError):
            self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refunds[0].id]])
        self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", self.payload["uuid"])]))
        self.assertFalse(refunds[0].pos_order_id)
        self.assertEqual(refunds[1].pos_order_id, self.original)
        self.request.assert_not_called()

    def test_lost_return_reconstruction_failure_rolls_back_native_data_only(self):
        refunds = self._lost_split_refunds()
        manager = self._actor(granted=True)
        fields = ["state", "revolut_order_id", "idempotency_key", "financial_snapshot",
                  "return_total_minor", "return_allocation", "pos_order_id", "pos_payment_id"]
        evidence = deepcopy(refunds.read(fields))
        model = self.env["pos.order"]
        process = type(model)._process_saved_order

        def fail_after_native_save(order, draft):
            result = process(order, draft)
            if order.uuid == self.payload["uuid"]:
                raise UserError("Injected native return save failure")
            return result

        # Native 18 permits uninvoiced drafts without an invoice journal.
        # Fail its real save hook after native rows have been created instead.
        with patch.object(type(model), "_process_saved_order", fail_after_native_save), self.assertRaisesRegex(UserError, "Injected native return save failure"):
            self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refunds[0].id]])
        refunds.invalidate_recordset()
        self.assertEqual(refunds.read(fields), evidence)
        self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", self.payload["uuid"])]))
        self.assertFalse(self.env["pos.order.line"].search_count([
            ("uuid", "=", self.payload["lines"][0][2]["uuid"]),
        ]))
        self.assertFalse(self.env["pos.payment"].search_count([
            ("uuid", "in", refunds.mapped("payment_line_uuid")),
        ]))
        self.request.assert_not_called()

        action = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refunds[1].id]])
        recovered = refunds.mapped("pos_order_id")
        self.assertEqual(len(recovered), 1)
        self.assertEqual(action["url"], f"/pos/ui?from_backend=1&config_id={self.pos_config.id}&revolut_return_uuid={recovered.uuid}")
        self.assertEqual(recovered.amount_total, -12.34)
        self.assertEqual(recovered.amount_paid, -12.34)
        self.assertEqual(len(recovered.payment_ids), 2)
        self._rpc_refund(manager, "pos.order", "action_pos_order_paid", [[recovered.id]])
        self.assertEqual(recovered.state, "paid")
        payment_ids = recovered.payment_ids.ids
        completed = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refunds[0].id]])
        self.assertEqual(completed["res_id"], recovered.id)
        self.assertEqual(recovered.payment_ids.ids, payment_ids)
        self.assertEqual(refunds.mapped("revolut_order_id"), [item["revolut_order_id"] for item in evidence])
        self.request.assert_not_called()

    def test_lost_odd_cent_return_native_checkout_projects_effects_once(self):
        self.product = self.env["product.product"].create({
            "name": "Recovered return stock", "type": "consu", "is_storable": True,
            "available_in_pos": True, "list_price": 12.34, "taxes_id": [Command.clear()],
        })
        self._terminal_sale(tip_minor=0, partner=self.partner1)
        self._tip_return(goods_qty=0.25, tip_qty=0, payment_minor=309)
        self.payload.update(amount_total=-3.09, partner_id=self.partner1.id)
        manager = self._actor(granted=True)
        self.assertEqual(self._rpc_refund_sources(manager)[0]["return_total_minor"], 309)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=309), self._refund_response("completed", amount=309),
        ]
        started = self._start_allocated(309, 0)
        payment = self.payload["payment_ids"][0][2]
        completed = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
        ])
        self.assertEqual(completed["state"], "verified")
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        proof_fields = ["financial_snapshot", "return_total_minor", "return_allocation",
                        "base_amount_minor", "tip_amount_minor", "idempotency_key", "revolut_order_id"]
        proof = deepcopy(refund.read(proof_fields)[0])
        lost = self.env["pos.order"].search([("uuid", "=", self.payload["uuid"])])
        self.assertEqual(len(lost), 1)
        self.assertEqual(lost.state, "draft")
        self.assertFalse(lost.picking_ids)
        self.assertFalse(lost.account_move)
        lost_order_id = lost.id
        # Simulate an older installation losing its browser draft after the
        # provider reimbursement was durably verified. Current ORM forbids it.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_revolut_refund_operation SET pos_order_id = NULL, pos_payment_id = NULL WHERE id = %s",
            [refund.id],
        )
        self.env.cr.execute("DELETE FROM pos_payment WHERE pos_order_id = %s", [lost_order_id])
        self.env.cr.execute("DELETE FROM pos_order_line WHERE order_id = %s", [lost_order_id])
        self.env.cr.execute("DELETE FROM pos_order WHERE id = %s", [lost_order_id])
        self.env.invalidate_all()
        self.request.reset_mock(side_effect=True)

        action = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refund.id]])
        recovered = refund.pos_order_id
        self.assertEqual(action["url"], f"/pos/ui?from_backend=1&config_id={self.pos_config.id}&revolut_return_uuid={recovered.uuid}")
        self.assertNotEqual(recovered.id, lost_order_id)
        self.assertEqual(recovered.revolut_return_allocation, proof["return_allocation"])
        self.assertEqual(refund.read(proof_fields)[0], proof)
        self.assertEqual(recovered.lines.qty, -0.25)
        self.assertEqual(recovered.amount_total, -3.09)
        self.assertEqual(recovered.payment_ids.amount, -3.09)
        self.assertFalse(recovered.picking_ids)
        self.assertFalse(recovered.account_move)

        checkout = deepcopy(self.payload)
        checkout.update(id=recovered.id, state="paid", amount_total=-3.09, amount_paid=-3.09,
                        user_id=manager.id)
        line_values = checkout["lines"][0][2]
        line_values.update(price_subtotal=recovered.lines.price_subtotal,
                           price_subtotal_incl=recovered.lines.price_subtotal_incl)
        checkout["lines"] = [Command.update(recovered.lines.id, line_values)]
        payment_values = checkout["payment_ids"][0][2]
        payment_values.update(payment_status="done", transaction_id=refund.revolut_order_id)
        checkout["payment_ids"] = [Command.update(recovered.payment_ids.id, payment_values)]
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(checkout)]])
        recovered.invalidate_recordset()
        self.assertEqual(recovered.state, "paid")
        self.assertEqual(len(recovered.picking_ids), 1)
        picking = recovered.picking_ids
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.product_id, self.product)
        self.assertEqual(picking.move_ids.quantity, 0.25)
        self.assertEqual(picking.location_id.usage, "customer")
        self.assertEqual(picking.location_dest_id.usage, "internal")
        credit_note_domain = [("company_id", "=", recovered.company_id.id), ("move_type", "=", "out_refund")]
        credit_notes_before = self.env["account.move"].search(credit_note_domain)
        invoice = recovered.with_user(manager).with_context(generate_pdf=False).action_pos_order_invoice()
        move = self.env["account.move"].browse(invoice["res_id"])
        self.assertEqual(move.state, "posted")
        self.assertEqual(move.move_type, "out_refund")
        self.assertEqual(move.amount_total, 3.09)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0, places=6)
        payment_ids = recovered.payment_ids.ids
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(checkout)]])
        repeated = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[refund.id]])
        self.assertEqual(repeated["res_id"], recovered.id)
        self.assertEqual(recovered.picking_ids, picking)
        self.assertEqual(recovered.account_move, move)
        self.assertEqual(self.env["account.move"].search(credit_note_domain) - credit_notes_before, move)
        self.assertEqual(recovered.payment_ids.ids, payment_ids)
        self.assertEqual(refund.read(proof_fields)[0], proof)
        self.assertEqual(refund.pos_payment_id.revolut_refund_operation_id, refund)
        self.assertEqual(refund.pos_payment_id.transaction_id, proof["revolut_order_id"])
        receipt = self._rpc_refund(manager, "pos.order", "read_pos_data", [[recovered.id], [], self.pos_config.id])
        self.assertEqual(next(order for order in receipt["pos.order"]
                              if order["uuid"] == recovered.uuid)["amount_total"], -3.09)
        self._tip_return(goods_qty=0.75, tip_qty=0, payment_minor=925)
        self.payload["amount_total"] = -9.25
        self.assertEqual(self._rpc_refund_sources(manager)[0]["return_total_minor"], 925)
        self.request.assert_not_called()

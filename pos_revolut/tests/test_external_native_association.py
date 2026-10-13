"""Reconcile separately finalized native returns without replaying their effects."""
import os
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_external_refunds import TestExternalRefunds


@tagged("post_install", "-at_install")
class TestExternalNativeAssociation(CommonPosTest):
    LOCATION_ID = TestExternalRefunds.LOCATION_ID
    TERMINAL_ID = TestExternalRefunds.TERMINAL_ID
    PAYMENT_ID = TestExternalRefunds.PAYMENT_ID
    _operation = TestExternalRefunds._operation
    _order_payload = TestExternalRefunds._order_payload
    _response = TestExternalRefunds._response
    _refund_response = TestExternalRefunds._refund_response
    _mutation_actor = TestExternalRefunds._mutation_actor
    _external = TestExternalRefunds._external
    _discover = TestExternalRefunds._discover

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "External native association", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Historical returned service", "type": "service",
            "available_in_pos": True, "list_price": 12.34,
            "taxes_id": [Command.clear()],
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
        self.refund_id = str(uuid4())
        self.source.credential_id.sudo().write({"next_refund_discovery_at": False})

    def _legacy_completed_return(self, providers, session=None):
        """Seed native work completed before the addon required refund evidence.

        Public ORM prepares its valid original lines and waiting tenders; SQL
        supplies only historical completion/reference evidence unavailable through
        today's guarded checkout. Association must not finalize this work again.
        """
        payload = self._order_payload(str(uuid4()), str(uuid4()))
        payload.update(state="draft", amount_paid=-12.34, amount_total=-12.34,
                       session_id=(session or self.session).id)
        payload["lines"][0][2].update(
            qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
            refunded_orderline_id=self.original.lines.id,
        )
        template = payload["payment_ids"][0][2]
        payload["payment_ids"] = [Command.create({
            **deepcopy(template), "uuid": str(uuid4()),
            "amount": -provider["amount"] / 100,
            "transaction_id": False, "payment_status": "waiting",
        }) for provider in providers]
        saved = self.env["pos.order"].sync_from_ui([payload])
        native = self.env["pos.order"].browse(next(
            row["id"] for row in saved["pos.order"] if row["uuid"] == payload["uuid"]
        ))
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_order SET state = 'paid' WHERE id = %s", [native.id])
        for payment, provider in zip(native.payment_ids.sorted("id"), providers):
            self.env.cr.execute(
                "UPDATE pos_payment SET payment_status = 'done', transaction_id = %s, payment_ref_no = %s WHERE id = %s",
                [provider["id"], provider["id"], payment.id],
            )
        native.invalidate_recordset()
        native.payment_ids.invalidate_recordset()
        return native

    def _effect_counts(self):
        return {model: self.env[model].search_count([]) for model in (
            "pos.order", "pos.order.line", "pos.payment", "stock.move", "account.move",
        )}

    def _assert_no_replayed_effects(self, before, native, refunds):
        self.assertEqual(self._effect_counts(), before)
        self.assertEqual(set(refunds.mapped("native_reconciliation_status")), {"native_completed"})
        self.assertEqual(refunds.pos_order_id, native)
        self.assertEqual(refunds.pos_payment_id, native.payment_ids)
        self.assertEqual(self.original.lines.refunded_qty, 1)
        self.assertFalse(native.picking_ids, "Services must not acquire inventory movements")
        for refund in refunds:
            self.assertEqual(refund.pos_payment_id.transaction_id, refund.revolut_order_id)
            self.assertEqual(refund.pos_payment_id.revolut_refund_operation_id, refund)
            self.assertEqual(refund.origin, "external")
            self.assertEqual(refund.pos_session_id, self.source.pos_session_id)
        self.request.assert_not_called()

    def test_multiple_external_refunds_associate_finalized_return_atomically(self):
        providers = [self._external("completed", amount=617),
                     self._external("completed", amount=617, id=str(uuid4()))]
        native = self._legacy_completed_return(providers)
        refunds = self._discover(providers).sorted("id")
        allocations = [{"refund_id": refund.id,
                        "payment_id": native.payment_ids.filtered(
                            lambda payment: payment.transaction_id == refund.revolut_order_id).id}
                       for refund in refunds]
        manager_refunds = refunds.with_user(self._mutation_actor())
        before = self._effect_counts()
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Association must not contact Revolut")
        # A partial association cannot hide an unverified second reimbursement.
        with self.assertRaises(UserError):
            manager_refunds[:1].action_associate_native_return(native.id, allocations[:1])
        self.assertFalse(refunds.pos_order_id)
        action = manager_refunds.action_associate_native_return(native.id, allocations)
        self.assertEqual(action["res_id"], native.id)
        self._assert_no_replayed_effects(before, native, refunds)
        manager_refunds.action_associate_native_return(native.id, allocations)
        self._assert_no_replayed_effects(before, native, refunds)

    def test_manager_wizard_associates_all_finalized_reimbursements_without_replay(self):
        providers = [self._external("completed", amount=617),
                     self._external("completed", amount=617, id=str(uuid4()))]
        native = self._legacy_completed_return(providers)
        refunds = self._discover(providers).sorted("id")
        manager = self._mutation_actor()
        before = self._effect_counts()
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Manager association must not contact Revolut")
        action = refunds[0].with_user(manager).action_open_native_completion()
        wizard = self.env["pos.revolut.external.refund.wizard"].with_user(manager).browse(action["res_id"])
        wizard.write({"disposition": "existing", "return_order_id": native.id})
        with self.assertRaises(UserError):
            wizard.action_prepare()
        first_payment = native.payment_ids.filtered(
            lambda payment: payment.transaction_id == refunds[0].revolut_order_id)
        second_payment = native.payment_ids - first_payment
        wizard.association_line_ids.write({"payment_id": first_payment.id})
        with self.assertRaises(UserError):
            wizard.action_prepare()
        self.assertFalse(refunds.pos_order_id)
        wizard.write({"association_line_ids": [Command.create({
            "refund_id": refunds[1].id, "payment_id": first_payment.id,
        })]})
        with self.assertRaises(UserError):
            wizard.action_prepare()
        wizard.association_line_ids.filtered(
            lambda line: line.refund_id.id == refunds[1].id,
        ).write({"payment_id": second_payment.id})
        result = wizard.action_prepare()
        self.assertEqual(result["res_id"], native.id)
        self._assert_no_replayed_effects(before, native, refunds)
        wizard.action_prepare()
        self._assert_no_replayed_effects(before, native, refunds)

    def test_finalized_return_in_later_closed_session_retains_original_provenance(self):
        source_session = self.session
        source_session.post_closing_cash_details(0)
        source_session.close_session_from_ui()
        self.assertEqual(source_session.state, "closed")
        self.pos_config_usd.open_ui()
        return_session = self.pos_config_usd.current_session_id
        return_session.write({"state": "opened"})
        providers = [self._external("completed", amount=1234)]
        native = self._legacy_completed_return(providers, session=return_session)
        # This historical finalized session predates today's required addon
        # refund links; represent its saved closed state without redoing entries.
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [return_session.id])
        return_session.invalidate_recordset()
        refund = self._discover(providers)
        before = self._effect_counts()
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Closed native association must not contact Revolut")
        manager_refund = refund.with_user(self._mutation_actor())
        manager_refund.action_prepare_native_return(
            return_order_id=native.id, payment_id=native.payment_ids.id,
        )
        self._assert_no_replayed_effects(before, native, refund)
        self.assertEqual(native.session_id, return_session)
        self.assertEqual(refund.pos_session_id, source_session)
        self.assertEqual(return_session.state, "closed")
        manager_refund.action_prepare_native_return()
        self._assert_no_replayed_effects(before, native, refund)

    def test_failing_batch_leaves_every_binding_and_native_effect_unchanged(self):
        providers = [self._external("completed", amount=617),
                     self._external("completed", amount=617, id=str(uuid4()))]
        native = self._legacy_completed_return(providers)
        refunds = self._discover(providers).sorted("id")
        payments = native.payment_ids.sorted("id")
        allocations = [{"refund_id": refund.id, "payment_id": payment.id}
                       for refund, payment in zip(refunds, payments)]
        # A real historical mismatch in the last member must reject the batch,
        # preserving the valid first reimbursement and all existing native work.
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_payment SET transaction_id = %s WHERE id = %s",
                            [str(uuid4()), payments[-1].id])
        payments.invalidate_recordset()
        before = self._effect_counts()
        self.request.reset_mock()
        with self.assertRaisesRegex(UserError, "unrelated, ambiguous"):
            refunds.with_user(self._mutation_actor()).action_associate_native_return(native.id, allocations)
        self.assertFalse(refunds.pos_order_id)
        self.assertFalse(refunds.pos_payment_id)
        self.assertFalse(payments.revolut_refund_operation_id)
        self.assertEqual(self._effect_counts(), before)
        self.assertEqual(native.state, "paid")
        self.request.assert_not_called()

"""Session closure must preserve outstanding native refund settlement."""

from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_revolut_refund import TestRevolutRefund


@tagged("post_install", "-at_install")
class TestRefundSessionClose(TestPointOfSaleCommon):
    LOCATION_ID = TestRevolutRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefund.PAYMENT_ID
    _operation = TestRevolutRefund._operation
    _order_payload = TestRevolutRefund._order_payload
    _mutation_actor = TestRevolutRefund._mutation_actor
    _rpc_refund = TestRevolutRefund._rpc_refund

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Session close refund test", "payment_method_type": "terminal",
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
            "name": "Session close refund product", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened"})
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
        self.manager = self._mutation_actor()
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        self.payload.update(amount_paid=-12.34, amount_total=-12.34, user_id=self.manager.id)
        self.payload["lines"][0][2].update(
            qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
            refunded_orderline_id=self.original.lines.id,
        )
        self.payload["payment_ids"][0][2].update(
            amount=-12.34, transaction_id=False, payment_status="waiting",
        )

    def _refund(self, state="pending", *, external=False):
        values = {
            "original_operation_id": self.source.id, "pos_session_id": self.session.id,
            "amount": 12.34, "amount_minor": 1234,
            "currency_id": self.session.currency_id.id, "state": state,
        }
        if external:
            values.update(origin="external", revolut_order_id=str(uuid4()))
        else:
            values.update(
                order_uuid=self.payload["uuid"],
                payment_line_uuid=self.payload["payment_ids"][0][2]["uuid"],
                return_total_minor=1234,
                financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(self.payload),
            )
            if state == "verified":
                values["revolut_order_id"] = str(uuid4())
        return self.env["pos.revolut.refund.operation"].sudo().create(values)

    def _close(self, state="closing_control"):
        return self._rpc_refund(self.manager, "pos.session", "write", [[self.session.id], {"state": state}])

    def test_pending_refund_blocks_public_session_closing(self):
        self._refund()
        with self.assertRaisesRegex(UserError, "refund"):
            self._close()
        self.assertEqual(self.session.state, "opened")
        self.request.assert_not_called()

    def test_uncertain_refund_blocks_both_closing_states(self):
        refund = self._refund()
        for state in ("dispatching", "unresolved"):
            refund.write({"state": state})
            for closing_state in ("closing_control", "closed"):
                with self.subTest(state=state, closing_state=closing_state):
                    with self.assertRaisesRegex(UserError, "refund"):
                        self._close(closing_state)
                    self.assertEqual(self.session.state, "opened")
        self.request.assert_not_called()

    def test_completed_orphan_refund_blocks_session_closing(self):
        self._refund("verified")
        with self.assertRaisesRegex(UserError, "refund"):
            self._close()
        self.assertEqual(self.session.state, "opened")
        self.request.assert_not_called()

    def _save_verified_return(self, refund, *, draft=False):
        payload = deepcopy(self.payload)
        payload["state"] = "draft" if draft else "paid"
        payload["payment_ids"][0][2].update(
            payment_status="done", transaction_id=refund.revolut_order_id,
        )
        saved = self._rpc_refund(self.manager, "pos.order", "sync_from_ui", [[payload]])
        return self.env["pos.order"].browse(next(
            item["id"] for item in saved["pos.order"] if item["uuid"] == payload["uuid"]
        ))

    def test_completed_refund_on_unfinalized_return_blocks_session_closing(self):
        refund = self._refund("verified")
        order = self._save_verified_return(refund, draft=True)
        self.assertEqual(order.state, "draft")
        self.assertEqual(refund.pos_payment_id, order.payment_ids)
        with self.assertRaisesRegex(UserError, "refund"):
            self._close()
        self.assertEqual(self.session.state, "opened")
        self.request.assert_not_called()

    def test_completed_finalized_refund_allows_session_closing(self):
        refund = self._refund("verified")
        order = self._save_verified_return(refund)
        self.assertEqual(order.state, "paid")
        self.assertEqual(refund.pos_order_id, order)
        self.assertEqual(refund.pos_payment_id, order.payment_ids)
        self._close()
        self.assertEqual(self.session.state, "closing_control")
        self.request.assert_not_called()

    def test_failed_refund_allows_session_closing(self):
        self._refund("failed")
        self._close()
        self.assertEqual(self.session.state, "closing_control")
        self.request.assert_not_called()

    def test_external_refund_requires_no_native_return_for_session_closing(self):
        refund = self._refund(external=True)
        for state in ("pending", "unresolved", "verified"):
            refund.write({"state": state})
            self._close()
            self.assertEqual(self.session.state, "closing_control")
            self.session.write({"state": "opened"})
        self.request.assert_not_called()

    def _rollover_historical_refund(self):
        refund = self._refund("verified")
        historical_session = self.session
        # Emulate an old deployed version that permitted closing an orphan
        # verified refund. The current public close action must reject it.
        self.env.flush_all()
        self.env.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [historical_session.id])
        historical_session.invalidate_recordset()
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened"})
        self.payload["session_id"] = self.session.id
        return refund, historical_session

    def test_historical_refund_on_recovered_draft_blocks_current_session_closing(self):
        refund, historical_session = self._rollover_historical_refund()
        order = self._save_verified_return(refund, draft=True)
        self.assertEqual(order.session_id, self.session)
        self.assertEqual(refund.pos_session_id, historical_session)
        with self.assertRaisesRegex(UserError, "refund"):
            self._close()
        self.assertEqual(self.session.state, "opened")
        self.assertEqual(refund.pos_session_id, historical_session)
        self.request.assert_not_called()

    def test_historical_refund_on_finalized_return_allows_current_session_closing(self):
        refund, historical_session = self._rollover_historical_refund()
        order = self._save_verified_return(refund)
        self.assertEqual(order.session_id, self.session)
        self.assertEqual(refund.pos_session_id, historical_session)
        self._close()
        self.assertEqual(self.session.state, "closing_control")
        self.assertEqual(refund.pos_session_id, historical_session)
        self.request.assert_not_called()

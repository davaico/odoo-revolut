"""Resume the original saved refund through native Odoo 19 manager and POS UI."""
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .test_revolut_native_printing import TestRevolutNativePrinting
from .test_revolut_payment import TestRevolutOrderSettlement
from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestRevolutRefundRecoveryUi(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID
    PAYMENT_ID = TestRevolutVerifiedCheckout.PAYMENT_ID
    _configure_revolut_checkout = TestRevolutVerifiedCheckout._configure_revolut_checkout
    _pos_fixture = TestRevolutNativePrinting._pos_fixture

    def _resume_waiting_return(self, *, split=False):
        source = TestRevolutNativePrinting._historical_sale(self, split=split)
        session = self.main_pos_config.current_session_id
        session.write({"update_stock_at_closing": False})
        minor = 617 if split else 1234
        reference = str(uuid4())
        payload = self._pos_fixture(
            TestRevolutOrderSettlement._order_payload, str(uuid4()), str(uuid4()),
        )
        payload.update(session_id=session.id, state="draft", amount_total=-12.34,
                       amount_paid=-minor / 100, user_id=self.pos_admin.id)
        payload["lines"][0][2].update(
            qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
            refunded_orderline_id=self.original.lines.id,
        )
        payment = payload["payment_ids"][0][2]
        payment.update(amount=-minor / 100, payment_status="waiting", transaction_id=False)
        self.env["pos.order"].sync_from_ui([payload])
        native = self.env["pos.order"].search([("uuid", "=", payload["uuid"])])
        tender = native.payment_ids
        refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": source.id, "pos_session_id": session.id,
            "order_uuid": native.uuid, "payment_line_uuid": tender.uuid,
            "amount": minor / 100, "amount_minor": minor, "return_total_minor": 1234,
            "currency_id": session.currency_id.id, "state": "pending",
            "provider_state": "processing", "revolut_order_id": reference,
            "financial_snapshot": self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        })
        self.assertEqual(native.state, "draft")
        self.assertEqual(tender.payment_status, "waiting")
        self.assertFalse(tender.transaction_id)

        def provider_request(method, url, **kwargs):
            if method != "GET" or not url.endswith(f"/orders/{reference}"):
                raise AssertionError("Refund recovery must not dispatch another financial request")
            response = Mock(status_code=200)
            response.json.return_value = {
                "id": reference, "type": "refund", "state": "completed", "amount": minor,
                "currency": session.currency_id.name, "related_order_id": source.revolut_order_id,
            }
            return response

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=provider_request) as provider:
            action = self.env.ref("pos_revolut.action_revolut_refunds")
            tour = "pos_revolut_manager_resume_mixed" if split else "pos_revolut_manager_resume_waiting"
            self.start_tour(f"/odoo/action-{action.id}/{refund.id}?debug=tests", tour, login="pos_admin")
            self.assertEqual([call.args[0] for call in provider.call_args_list], ["GET"])

        self.env.invalidate_all()
        self.assertEqual(refund.pos_order_id, native)
        self.assertEqual(refund.pos_payment_id, tender)
        self.assertEqual(native.uuid, payload["uuid"])
        self.assertEqual(tender.uuid, payment["uuid"])
        self.assertEqual(native.session_id, session)
        self.assertEqual(native.state, "paid")
        self.assertEqual(native.amount_total, -12.34)
        self.assertEqual(native.amount_paid, -12.34)
        self.assertEqual(native.lines.refunded_orderline_id, self.original.lines)
        self.assertEqual(self.original.lines.refunded_qty, 1)
        self.assertEqual(tender.amount, -minor / 100)
        self.assertEqual(tender.transaction_id, reference)
        self.assertEqual(tender.payment_ref_no, reference)
        self.assertEqual(tender.payment_status, "done")
        self.assertEqual(len(native.payment_ids), 2 if split else 1)
        self.assertEqual(len(native.picking_ids), 1)
        self.assertEqual(native.picking_ids.state, "done")
        self.assertEqual(refund.state, "verified")
        self.assertEqual(refund.revolut_order_id, reference)
        self.assertEqual(self.env["pos.revolut.refund.operation"].search_count([
            ("original_operation_id", "=", source.id),
        ]), 1)

    def test_manager_resumes_existing_waiting_return_after_backend_check(self):
        self._resume_waiting_return()

    def test_manager_resumes_waiting_mixed_return_and_explicitly_completes_cash(self):
        self._resume_waiting_return(split=True)

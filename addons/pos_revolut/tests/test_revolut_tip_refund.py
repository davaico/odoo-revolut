"""Public refund/native tender behavior for verified terminal-tip decomposition."""
import os
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.tests.common import tagged

from .test_revolut_refund import TestRevolutRefund


@tagged("post_install", "-at_install")
class TestRevolutTipRefund(CommonPosTest):
    LOCATION_ID = TestRevolutRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutRefund.PAYMENT_ID
    _operation = TestRevolutRefund._operation
    _order_payload = TestRevolutRefund._order_payload
    _mutation_actor = TestRevolutRefund._mutation_actor
    _rpc_refund = TestRevolutRefund._rpc_refund
    _save_return_draft = TestRevolutRefund._save_return_draft
    _rpc_start_refund = TestRevolutRefund._rpc_start_refund
    _rpc_refund_sources = TestRevolutRefund._rpc_refund_sources
    _response = TestRevolutRefund._response
    _refund_response = TestRevolutRefund._refund_response

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Terminal tip refund test", "payment_method_type": "terminal",
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
            "name": "Tip refund goods", "available_in_pos": True,
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
        self.env.flush_all()

    def _legacy_sale(self):
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
        for name in ("amount_paid", "amount_total"):
            self.payload[name] = -12.34
        line = self.payload["lines"][0][2]
        line.update(qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34,
                    refunded_orderline_id=self.original.lines.id)
        self.payload["payment_ids"][0][2].update(amount=-12.34, transaction_id=False, payment_status="waiting")
        self.refund_id = str(uuid4())
        self.env.flush_all()

    def test_legacy_sources_preserve_amount_without_inventing_tip_evidence(self):
        self._legacy_sale()
        source = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual(source["amount_minor"], 1234)
        self.assertEqual(source["remaining_minor"], 1234)
        self.assertEqual(source["base_amount_minor"], 1234)
        self.assertEqual(source["tip_amount_minor"], 0)
        self.assertFalse(source["terminal_tip_evidence"])
        self.request.assert_not_called()

    def _stream_response(self, payload):
        import json
        from unittest.mock import Mock
        response = Mock(status_code=200)
        content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        response.json.return_value = payload
        response.iter_content.return_value = [content]
        return response

    def _terminal_sale(self, tip_minor=200, base_minor=1234, charge_base_minor=None, partner=None, taxes=None, split_lines=False):
        """Capture and report fixture through public preparation/start/poll."""
        from odoo.addons.pos_revolut.models.terminal_tip import REPORT_COLUMNS
        precision = self.session.currency_id.decimal_places
        factor = 10 ** precision
        charge_base_minor = base_minor if charge_base_minor is None else charge_base_minor
        self.product.write({"list_price": base_minor / factor,
                            "taxes_id": [Command.set(taxes.ids)] if taxes else [Command.clear()]})
        self.tip_product = self.env["product.product"].create({
            "name": "Verified customer terminal tip", "list_price": 0,
            "taxes_id": [Command.clear()],
        })
        self.pos_config_usd.write({"tip_product_id": self.tip_product.id})
        sale = self._order_payload(str(uuid4()), str(uuid4()), payment_status="waiting")
        sale.update(state="draft", amount_paid=0, amount_total=base_minor / factor)
        if partner:
            sale["partner_id"] = partner.id
        sale["lines"][0][2].update(price_unit=base_minor / factor,
                                  price_subtotal=base_minor / factor, price_subtotal_incl=base_minor / factor)
        if taxes:
            amounts = taxes.compute_all(base_minor / factor, currency=self.session.currency_id,
                                        quantity=1, product=self.product)
            sale["lines"][0][2].update(tax_ids=[Command.set(taxes.ids)],
                                      price_subtotal=amounts["total_excluded"],
                                      price_subtotal_incl=amounts["total_included"])
            sale["amount_tax"] = amounts["total_included"] - amounts["total_excluded"]
        sale["payment_ids"][0][2].update(transaction_id=False, amount=charge_base_minor / factor)
        if split_lines:
            self.product.write({"list_price": base_minor / factor / 2})
            template = deepcopy(sale["lines"][0][2])
            sale["lines"] = [Command.create(dict(template, uuid=str(uuid4()), qty=1,
                                                 price_unit=base_minor / factor / 2,
                                                 price_subtotal=base_minor / factor / 2,
                                                 price_subtotal_incl=base_minor / factor / 2)) for _ in range(2)]
        saved = self.env["pos.order"].sync_from_ui([sale])
        original = self.env["pos.order"].browse(next(
            item["id"] for item in saved["pos.order"] if item["uuid"] == sale["uuid"]
        ))
        line_uuid = sale["payment_ids"][0][2]["uuid"]
        prepared = self.env["pos.order"].revolut_prepare_payment(
            original.id, original.uuid, 0,
            [{"uuid": line_uuid, "payment_method_id": self.revolut_method.id, "amount": charge_base_minor / factor}],
        )
        order_id, intent_id, payment_id, report_id = [str(uuid4()) for _ in range(4)]
        self.request.side_effect = [
            self._response(terminals=[{"id": self.TERMINAL_ID, "online": True,
                                     "operation_mode": "pos", "location_id": self.LOCATION_ID}]),
            self._response(id=order_id), self._response(id=intent_id, state="pending"),
        ]
        started = self.revolut_method.revolut_start_payment(
            self.session.id, original.uuid, line_uuid, charge_base_minor / factor, self.session.currency_id.id,
            False, False, prepared["authorization_id"], prepared["cart_version"], prepared["tender_revision"],
        )
        self.assertIn("operation_id", started, started)
        created = "2026-10-01T07:00:00Z"
        gross_minor = charge_base_minor + tip_minor
        row = {
            "payment_id": payment_id, "type": "PAYMENT", "order_id": order_id,
            "state": "COMPLETED", "amount": f"{gross_minor / factor:.{precision}f}",
            "currency": self.session.currency_id.name, "surcharge_amount": "0",
            "tip_amount": f"{tip_minor / factor:.{precision}f}", "refunded_amount": "0",
            "created_date": created, "captured_date": created, "location_id": self.LOCATION_ID,
        }
        csv = (",".join(REPORT_COLUMNS) + "\n" + ",".join(row[name] for name in REPORT_COLUMNS) + "\n").encode()
        self.request.side_effect = [
            self._response(id=intent_id, order_id=order_id, state="completed", payment_id=payment_id,
                           amount=charge_base_minor, currency=self.session.currency_id.name, terminal_id=self.TERMINAL_ID),
            self._response(id=payment_id, order_id=order_id, amount=gross_minor,
                           currency=self.session.currency_id.name, state="captured", created_at=created),
            self._stream_response({"report_run_id": report_id, "status": "completed"}),
            self._stream_response(csv),
            self._stream_response({"id": order_id, "currency": self.session.currency_id.name,
                                   "location_id": self.LOCATION_ID,
                                   "payments": [{"id": payment_id, "amount": gross_minor, "state": "captured"}]}),
        ]
        observed = self.revolut_method.revolut_poll_payment(started["operation_id"], original.uuid, line_uuid)
        self.assertEqual(observed["state"], "verified")
        # Public adapters commit in separate owned environments. A later RPC
        # sees a fresh cache; reproduce that boundary before native checkout.
        self.env.invalidate_all()
        original.invalidate_recordset()
        # Native checkout uses the server-projected lines and gross tender.
        final = self._order_payload(original.uuid, line_uuid)
        final.update(id=original.id, state="paid", amount_paid=gross_minor / factor,
                     amount_total=gross_minor / factor, amount_tax=original.amount_tax)
        final["lines"] = [Command.update(line.id, {
            "uuid": line.uuid, "product_id": line.product_id.id, "qty": line.qty,
            "price_unit": line.price_unit, "discount": line.discount,
            "price_subtotal": line.price_subtotal, "price_subtotal_incl": line.price_subtotal_incl,
            "tax_ids": [Command.set(line.tax_ids.ids)],
        }) for line in original.lines]
        native_payment = original.payment_ids.filtered(lambda item: item.uuid == line_uuid)
        values = final["payment_ids"][0][2]
        values.update(amount=gross_minor / factor, transaction_id=payment_id)
        final["payment_ids"] = [Command.update(native_payment.id, values)]
        self.env["pos.order"].sync_from_ui([final])
        self.source = self.env["pos.revolut.payment.operation"].browse(started["operation_id"])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id
        self.assertEqual(self.original.state, "paid")
        self.assertEqual(self.source.amount_minor, charge_base_minor)
        self.assertEqual(self.source.pos_payment_id.amount, gross_minor / factor)
        self.request.reset_mock(side_effect=True)
        self.env.flush_all()

    def _tip_return(self, *, goods_qty=1, tip_qty=1, payment_minor=None):
        from copy import deepcopy
        self.payload = self._order_payload(str(uuid4()), str(uuid4()), payment_status="waiting")
        base_line = self.original.lines.filtered(lambda line: line.product_id == self.product)
        tip_line = self.original.lines.filtered(lambda line: line.product_id == self.tip_product)
        template = deepcopy(self.payload["lines"][0][2])
        self.payload["lines"] = []
        for original, quantity in ((base_line, goods_qty), (tip_line, tip_qty)):
            if not quantity:
                continue
            values = dict(template, uuid=str(uuid4()), qty=-quantity,
                          product_id=original.product_id.id, price_unit=original.price_unit,
                          tax_ids=[Command.set(original.tax_ids.ids)],
                          refunded_orderline_id=original.id,
                          price_subtotal=-quantity * original.price_subtotal,
                          price_subtotal_incl=-quantity * original.price_subtotal_incl)
            if original.tax_ids:
                amounts = original.tax_ids.compute_all(original.price_unit, self.session.currency_id,
                                                       -quantity, product=original.product_id)
                values.update(price_subtotal=amounts["total_excluded"],
                              price_subtotal_incl=amounts["total_included"])
            self.payload["lines"].append(Command.create(values))
        total = -(goods_qty * base_line.price_subtotal_incl + tip_qty * tip_line.price_subtotal_incl)
        paid = -payment_minor / 10 ** self.session.currency_id.decimal_places if payment_minor is not None else total
        self.payload.update(amount_total=total, amount_paid=paid)
        self.payload["payment_ids"][0][2].update(amount=paid, transaction_id=False)
        self.refund_id = str(uuid4())

    def _start_allocated(self, base_minor=None, tip_minor=None):
        manager = self._mutation_actor()
        payment = self.payload["payment_ids"][0][2]
        self._save_return_draft(actor=manager)
        return self._rpc_refund(manager, "pos.payment.method", "revolut_start_refund", [
            [self.revolut_method.id], self.session.id, self.payload["uuid"], payment["uuid"],
            payment["amount"], self.session.currency_id.id, self.payload, self.source.id,
            base_minor, tip_minor,
        ])

    def test_full_refund_includes_terminal_tip_and_preserves_native_tender(self):
        self._terminal_sale()
        self._tip_return()
        source = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual((source["amount_minor"], source["base_amount_minor"], source["tip_amount_minor"]),
                         (1434, 1234, 200))
        self.assertEqual(self.source.pos_payment_id.amount, 14.34)
        self.assertEqual(self.source.pos_payment_id.transaction_id, self.source.revolut_payment_id)
        self.assertEqual((self.source.amount_minor, self.source.terminal_tip_minor,
                          self.source.gross_amount_minor), (1234, 200, 1434))
        self.assertTrue(self.source.verified_at)
        self.request.assert_not_called()
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1434,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=1434), self._refund_response("completed", amount=1434),
        ]
        started = self._start_allocated()
        self.assertEqual((started["base_amount_minor"], started["tip_amount_minor"]), (1234, 200))
        payment = self.payload["payment_ids"][0][2]
        self.revolut_method.revolut_poll_refund(started["operation_id"], self.payload["uuid"], payment["uuid"])
        payment.update(payment_status="done", transaction_id=self.refund_id)
        self.env["pos.order"].sync_from_ui([deepcopy(self.payload)])
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        refund.invalidate_recordset()
        self.assertEqual(refund.state, "verified")
        self.assertTrue(refund.verified_at)
        self.assertEqual((refund.amount_minor, refund.base_amount_minor, refund.tip_amount_minor),
                         (1434, 1234, 200))
        self.assertEqual(refund.pos_payment_id.amount, -14.34)
        self.assertEqual(refund.pos_payment_id.transaction_id, self.refund_id)
        self.assertEqual(refund.original_operation_id, self.source)
        self.assertEqual(refund.pos_order_id.state, "paid")
        remaining = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual((remaining["remaining_base_minor"], remaining["remaining_tip_minor"]), (0, 0))
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET", "POST", "GET"])

    def test_partial_refund_requires_explicit_base_and_tip(self):
        from odoo.exceptions import UserError
        self._terminal_sale()
        self._tip_return(goods_qty=0.5, tip_qty=0.5)
        with self.assertRaisesRegex(UserError, "Specify the base and terminal tip"):
            self._start_allocated()
        self.request.assert_not_called()
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1434,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=717),
        ]
        started = self._start_allocated(617, 100)
        self.assertEqual((started["base_amount_minor"], started["tip_amount_minor"]), (617, 100))
        remaining = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual((remaining["remaining_base_minor"], remaining["remaining_tip_minor"]), (617, 100))
        repeated = self._start_allocated(617, 100)
        self.assertEqual(repeated["operation_id"], started["operation_id"])
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET", "POST"])
        self.request.side_effect = [self._refund_response("completed", amount=717)]
        payment = self.payload["payment_ids"][0][2]
        self.revolut_method.revolut_poll_refund(started["operation_id"], self.payload["uuid"], payment["uuid"])
        payment.update(payment_status="done", transaction_id=self.refund_id)
        self.env["pos.order"].sync_from_ui([deepcopy(self.payload)])
        self._tip_return(goods_qty=0.5, tip_qty=0.5)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1434,
                           currency=self.session.currency_id.name, refunded_amount=717),
            self._refund_response(amount=717), self._refund_response("completed", amount=717),
        ]
        second = self._start_allocated(617, 100)
        payment = self.payload["payment_ids"][0][2]
        self.revolut_method.revolut_poll_refund(second["operation_id"], self.payload["uuid"], payment["uuid"])
        payment.update(payment_status="done", transaction_id=self.refund_id)
        self.env["pos.order"].sync_from_ui([deepcopy(self.payload)])
        remaining = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual((remaining["remaining_base_minor"], remaining["remaining_tip_minor"]), (0, 0))

    def test_goods_return_cannot_spend_original_terminal_tip_balance(self):
        from odoo.exceptions import UserError
        self._terminal_sale()
        self._tip_return(goods_qty=0.5, tip_qty=0)
        with self.assertRaisesRegex(UserError, "allocations exceed the original return lines"):
            self._start_allocated(517, 100)
        self.request.assert_not_called()

    def test_tip_product_reconfiguration_preserves_original_return_decomposition(self):
        self._terminal_sale()
        self._tip_return()
        replacement = self.env["product.product"].create({"name": "New tip product", "taxes_id": [Command.clear()]})
        self.pos_config_usd.write({"tip_product_id": replacement.id})
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1434,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=1434),
        ]
        started = self._start_allocated()
        self.assertEqual((started["base_amount_minor"], started["tip_amount_minor"]), (1234, 200))


    def test_full_return_keeps_base_rounding_and_refunds_exact_collected_tip(self):
        rounding = self.env["account.cash.rounding"].create({
            "name": "Refund frozen five-cent rounding", "rounding": 0.05,
            "rounding_method": "HALF-UP", "strategy": "add_invoice_line",
            "profit_account_id": self.company_data["default_account_revenue"].id,
            "loss_account_id": self.company_data["default_account_expense"].id,
        })
        self.pos_config_usd.write({"cash_rounding": True, "only_round_cash_method": False,
                                   "rounding_method": rounding.id})
        self._terminal_sale(tip_minor=3, base_minor=1002, charge_base_minor=1000, partner=self.partner_mobt)
        sale_invoice = self.original.with_context(generate_pdf=False).action_pos_order_invoice()
        original_move = self.env["account.move"].browse(sale_invoice["res_id"])
        self.assertEqual(original_move.state, "posted")
        self.assertEqual(original_move.amount_total, 10.03)
        self._tip_return(payment_minor=1003)
        self.payload["partner_id"] = self.partner_mobt.id
        source = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual((source["return_base_minor"], source["return_tip_minor"], source["return_total_minor"]),
                         (1000, 3, 1003))
        # Native POS first saves the return draft, then sends only changed
        # fields after provider verification. Its final lines=[] payload must
        # validate the complete persisted cart, retaining the exact tip.
        from copy import deepcopy
        draft = deepcopy(self.payload)
        draft.update(state="draft", amount_paid=0)
        saved_draft = self.env["pos.order"].sync_from_ui([draft])
        self.payload["id"] = next(
            item["id"] for item in saved_draft["pos.order"] if item["uuid"] == self.payload["uuid"]
        )
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1003,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=1003), self._refund_response("completed", amount=1003),
        ]
        started = self._start_allocated()
        self.assertEqual((started["base_amount_minor"], started["tip_amount_minor"]), (1000, 3))
        # Checkout follows the canonical return target supplied by the refund
        # response, after the allocation picker displayed that exact amount.
        self.payload["amount_total"] = -started["return_total_minor"] / 100
        payment = self.payload["payment_ids"][0][2]
        self.revolut_method.revolut_poll_refund(started["operation_id"], self.payload["uuid"], payment["uuid"])
        payment.update(payment_status="done", transaction_id=self.refund_id)
        refund_snapshot = deepcopy(self.payload)
        return_uuid = self.payload["uuid"]
        self.payload["payment_ids"] = [list(command) for command in self.payload["payment_ids"]]
        self.payload["lines"] = []
        saved = self.env["pos.order"].sync_from_ui([deepcopy(self.payload)])
        returned = self.env["pos.order"].browse(next(
            item["id"] for item in saved["pos.order"] if item["uuid"] == return_uuid
        ))
        self.assertEqual(returned.state, "paid")
        self.assertEqual(returned.payment_ids.amount, -10.03)
        refund_invoice = returned.with_context(generate_pdf=False).action_pos_order_invoice()
        refund_move = self.env["account.move"].browse(refund_invoice["res_id"])
        self.assertEqual(refund_move.state, "posted")
        self.assertEqual(refund_move.amount_total, 10.03)
        self.assertEqual(refund_move.move_type, "out_refund")
        self.assertEqual(self._rpc_refund_sources(self._mutation_actor(), refund_snapshot)[0]["remaining_minor"], 0)

    def test_partial_allocation_cannot_swap_tip_entitlement_for_base(self):
        from odoo.exceptions import UserError
        self._terminal_sale()
        self._tip_return()
        with self.assertRaisesRegex(UserError, "insufficient refundable base or terminal tip"):
            self._start_allocated(1334, 100)
        self.request.assert_not_called()

    def test_provider_original_gross_mismatch_prevents_financial_refund_post(self):
        self._terminal_sale()
        self._tip_return()
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
        ]
        started = self._start_allocated()
        self.assertEqual(started["state"], "failed")
        self.assertEqual(started["provider_state"], "original_ineligible")
        self.assertEqual([call.args[0] for call in self.request.call_args_list], ["GET"])

    def test_partial_component_commands_require_explicit_minor_unit_integers(self):
        from odoo.exceptions import UserError
        self._terminal_sale()
        self._tip_return(goods_qty=0.5, tip_qty=0.5)
        for base, tip in ((617.0, 100), ("617", 100), (716, True), (None, 100), (-1, 718)):
            with self.subTest(base=base, tip=tip):
                with self.assertRaisesRegex(UserError, "Specify the base and terminal tip"):
                    self._start_allocated(base, tip)
        payment = self.payload["payment_ids"][0][2]
        self.assertFalse(self.revolut_method.revolut_find_refund(self.payload["uuid"], payment["uuid"]))
        remaining = self._rpc_refund_sources(self._mutation_actor())[0]
        self.assertEqual((remaining["remaining_base_minor"], remaining["remaining_tip_minor"]), (1234, 200))
        self.request.assert_not_called()

    def test_quarter_then_remaining_return_conserves_native_refund_total(self):
        self._terminal_sale(tip_minor=0)
        manager = self._mutation_actor()
        refunded = 0
        native_totals = []
        for quantity, expected in ((0.25, 309), (0.75, 925)):
            self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=expected)
            # Browser native totals round each fraction independently.
            self.payload["amount_total"] = -3.09 if quantity == 0.25 else -9.26
            sources = self._rpc_refund_sources(manager)
            self.assertEqual(sources[0]["return_total_minor"], expected)
            self.request.side_effect = [
                self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                               currency=self.session.currency_id.name, refunded_amount=refunded),
                self._refund_response(amount=expected),
                self._refund_response("completed", amount=expected),
            ]
            started = self._start_allocated(expected, 0)
            payment = self.payload["payment_ids"][0][2]
            completed = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
                [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
            ])
            self.assertEqual(completed["state"], "verified")
            payment.update(payment_status="done", transaction_id=self.refund_id)
            self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
            self.env.invalidate_all()
            refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
            self.assertEqual(refund.pos_order_id.state, "paid")
            native_totals.append(refund.pos_order_id.amount_total)
            self.assertEqual(refund.pos_payment_id.amount, -expected / 100)
            refunded += expected
        posts = [call.kwargs["json"]["amount"] for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(posts, [309, 925])
        self.assertEqual(native_totals, [-3.09, -9.25])
        self.assertEqual(refunded, 1234)

    def _complete_rounding_partition(self, manager, expected, refunded, *, invoice=False):
        factor = 10 ** self.session.currency_id.decimal_places
        self.payload["amount_total"] = self.session.currency_id.round(self.payload["amount_total"])
        source = self._rpc_refund_sources(manager)[0]
        self.assertEqual(source["return_total_minor"], expected)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=self.source._revolut_paid_minor(),
                           currency=self.session.currency_id.name, refunded_amount=refunded),
            self._refund_response(amount=expected), self._refund_response("completed", amount=expected),
        ]
        started = self._start_allocated(expected, 0)
        payment = self.payload["payment_ids"][0][2]
        args = [[self.revolut_method.id], self.session.id, self.payload["uuid"], payment["uuid"],
                payment["amount"], self.session.currency_id.id, self.payload, self.source.id, expected, 0]
        self.assertEqual(self._rpc_refund(manager, "pos.payment.method", "revolut_start_refund", args)["operation_id"],
                         started["operation_id"])
        completed = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
        ])
        self.assertEqual(completed["state"], "verified")
        self.payload["amount_total"] = -expected / factor
        payment.update(payment_status="done", transaction_id=self.refund_id)
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        order = refund.pos_order_id
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.amount_total, -expected / factor)
        self.assertEqual(order.payment_ids.amount, -expected / factor)
        data = self._rpc_refund(manager, "pos.order", "read_pos_data_uuid", [order.uuid])
        returned = next(row for row in data["pos.order"] if row["uuid"] == order.uuid)
        self.assertEqual(returned["amount_total"], -expected / factor)
        self.assertEqual(returned["revolut_payable_target"], -expected / factor)
        self.assertEqual(order.lines.qty, self.payload["lines"][0][2]["qty"])
        self.assertEqual(order.lines.price_unit, self.original.lines.price_unit)
        self.assertEqual(order.lines.discount, self.original.lines.discount)
        self.assertEqual(order.lines.tax_ids, self.original.lines.tax_ids)
        if invoice:
            result = order.with_context(generate_pdf=False).action_pos_order_invoice()
            move = self.env["account.move"].browse(result["res_id"])
            self.assertEqual(move.state, "posted")
            self.assertEqual(move.move_type, "out_refund")
            self.assertEqual(move.amount_total, expected / factor)
            self.assertEqual(move.amount_tax, 0)
            self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0, places=6)
        return refund

    def test_rounding_partitions_reverse_order_and_downward_remainder(self):
        for original_minor, quantities, expected in (
            (1234, [0.75, 0.25], [926, 308]),
            (1234, [0.25, 0.25, 0.25, 0.25], [309, 308, 309, 308]),
            (1233, [0.25, 0.75], [308, 925]),
        ):
            with self.subTest(original_minor=original_minor, quantities=quantities):
                self._terminal_sale(tip_minor=0, base_minor=original_minor, partner=self.partner_mobt)
                manager = self._mutation_actor()
                refunded = 0
                before = len(self.request.call_args_list)
                for quantity, amount in zip(quantities, expected):
                    self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=amount)
                    self.payload["partner_id"] = self.partner_mobt.id
                    self._complete_rounding_partition(manager, amount, refunded, invoice=True)
                    refunded += amount
                self.assertEqual(refunded, original_minor)
                posts = [call.kwargs["json"]["amount"] for call in self.request.call_args_list[before:]
                         if call.args[0] == "POST"]
                self.assertEqual(posts, expected)

    def test_rounding_partitions_zero_and_three_decimal_currencies(self):
        for quantum in (1, 0.001):
            with self.subTest(quantum=quantum):
                self.env["decimal.precision"].search([("name", "=", "Product Price")]).write({"digits": 3})
                self.session.currency_id.write({"rounding": quantum})
                self._terminal_sale(tip_minor=0)
                manager = self._mutation_actor()
                refunded = 0
                for quantity, amount in ((0.25, 309), (0.75, 925)):
                    self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=amount)
                    self._complete_rounding_partition(manager, amount, refunded)
                    refunded += amount
                self.assertEqual(refunded, 1234)

    def test_stale_remaining_rounding_selection_is_rejected_before_dispatch(self):
        from odoo.exceptions import UserError
        self._terminal_sale(tip_minor=0)
        manager = self._mutation_actor()
        self._tip_return(goods_qty=0.75, tip_qty=0, payment_minor=926)
        stale = deepcopy(self.payload)
        stale["amount_total"] = -9.26
        self.assertEqual(self._rpc_refund_sources(manager, stale)[0]["return_total_minor"], 926)
        self._tip_return(goods_qty=0.25, tip_qty=0, payment_minor=309)
        self.payload["amount_total"] = -3.09
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=309),
        ]
        self._start_allocated(309, 0)
        before = self.request.call_count
        self.payload = stale
        with self.assertRaises(UserError):
            self._start_allocated(926, 0)
        self.assertEqual(self.request.call_count, before)

    def test_native_session_closes_with_conserved_partial_return_bases(self):
        self._terminal_sale(tip_minor=0)
        manager = self._mutation_actor()
        for quantity, amount, prior in ((0.25, 309, 0), (0.75, 925, 309)):
            self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=amount)
            self._complete_rounding_partition(manager, amount, prior)
        result = self.session.close_session_from_ui()
        self.assertEqual(self.session.state, "closed", result)
        if self.session.move_id:
            self.assertEqual(self.session.move_id.state, "posted")
            self.assertAlmostEqual(sum(self.session.move_id.line_ids.mapped("balance")), 0, places=6)

    def test_taxed_partial_returns_preserve_native_tax_and_credit_note_totals(self):
        tax = self.env["account.tax"].create({
            "name": "Conserved return included twenty", "amount": 20,
            "amount_type": "percent", "company_id": self.company.id,
            "price_include_override": "tax_included",
        })
        for mode in ("round_per_line", "round_globally"):
            with self.subTest(mode=mode):
                self.company.write({"tax_calculation_rounding_method": mode})
                self._terminal_sale(tip_minor=0, partner=self.partner_mobt, taxes=tax)
                manager = self._mutation_actor()
                expected_taxes = (0.52, 1.54) if mode == "round_per_line" else (0.51, 1.54)
                for quantity, amount, prior, expected_tax in (
                    (0.25, 309, 0, expected_taxes[0]), (0.75, 925, 309, expected_taxes[1]),
                ):
                    self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=amount)
                    self.payload["partner_id"] = self.partner_mobt.id
                    refund = self._complete_rounding_partition(manager, amount, prior)
                    order = refund.pos_order_id
                    self.assertEqual(order.amount_tax, -expected_tax)
                    result = order.with_context(generate_pdf=False).action_pos_order_invoice()
                    move = self.env["account.move"].browse(result["res_id"])
                    self.assertEqual(move.state, "posted")
                    self.assertEqual(move.amount_total, amount / 100)
                    self.assertEqual(move.amount_tax, expected_tax)
                    self.assertAlmostEqual(move.amount_untaxed + move.amount_tax, move.amount_total, places=6)
                    self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0, places=6)

    def test_fractional_returns_conserve_odd_base_and_terminal_tip_components(self):
        self._terminal_sale(tip_minor=2)
        manager = self._mutation_actor()
        refunded = 0
        returned = []
        for quantity, base, tip in ((0.25, 309, 1), (0.75, 925, 1)):
            amount = base + tip
            self._tip_return(goods_qty=quantity, tip_qty=quantity, payment_minor=amount)
            # The picker returns the explicit checked base/tip total.
            self.payload["amount_total"] = -amount / 100
            source = self._rpc_refund_sources(manager)[0]
            self.assertEqual((source["return_base_minor"], source["return_tip_minor"]), (base, tip))
            self.request.side_effect = [
                self._response(id=self.source.revolut_order_id, state="completed", amount=1236,
                               currency=self.session.currency_id.name, refunded_amount=refunded),
                self._refund_response(amount=amount), self._refund_response("completed", amount=amount),
            ]
            started = self._start_allocated(base, tip)
            payment = self.payload["payment_ids"][0][2]
            self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
                [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
            ])
            payment.update(payment_status="done", transaction_id=self.refund_id)
            self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
            self.env.invalidate_all()
            refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
            self.assertEqual((refund.base_amount_minor, refund.tip_amount_minor), (base, tip))
            self.assertEqual(refund.pos_order_id.amount_total, -amount / 100)
            returned.append(refund)
            refunded += amount
        self.assertEqual(sum(row.base_amount_minor for row in returned), 1234)
        self.assertEqual(sum(row.tip_amount_minor for row in returned), 2)
        self.assertEqual([call.kwargs["json"]["amount"] for call in self.request.call_args_list
                          if call.args[0] == "POST"], [310, 926])

    def test_late_credit_notes_do_not_cash_round_conserved_returns_again(self):
        rounding = self.env["account.cash.rounding"].create({
            "name": "Conserved return late invoice five-cent rounding", "rounding": 0.05,
            "rounding_method": "HALF-UP", "strategy": "add_invoice_line",
            "profit_account_id": self.company_data["default_account_revenue"].id,
            "loss_account_id": self.company_data["default_account_expense"].id,
        })
        self.pos_config_usd.write({"cash_rounding": True, "only_round_cash_method": False,
                                   "rounding_method": rounding.id})
        self._terminal_sale(tip_minor=0, charge_base_minor=1235, partner=self.partner_mobt)
        manager = self._mutation_actor()
        returned = []
        for quantity, amount, prior in ((0.25, 309, 0), (0.75, 926, 309)):
            self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=amount)
            self.payload["partner_id"] = self.partner_mobt.id
            returned.append(self._complete_rounding_partition(manager, amount, prior).pos_order_id)
        result = self.session.close_session_from_ui()
        self.assertEqual(self.session.state, "closed", result)
        for order, amount in zip(returned, (3.09, 9.26)):
            result = order.with_context(generate_pdf=False).action_pos_order_invoice()
            move = self.env["account.move"].browse(result["res_id"])
            self.assertEqual(move.state, "posted")
            self.assertEqual(move.amount_total, amount)
            self.assertEqual(order.amount_total, -amount)
            reversals = self.env["account.move"].search([("reversed_pos_order_id", "=", order.id)])
            self.assertTrue(reversals)
            for reversal in reversals:
                self.assertEqual(reversal.state, "posted")
                self.assertAlmostEqual(sum(reversal.line_ids.mapped("balance")), 0, places=6)

        original_result = self.original.with_context(generate_pdf=False).action_pos_order_invoice()
        original_move = self.env["account.move"].browse(original_result["res_id"])
        self.assertEqual(original_move.state, "posted")
        self.assertEqual(original_move.amount_total, 12.35)
        self.assertEqual(original_move.invoice_cash_rounding_id, rounding)

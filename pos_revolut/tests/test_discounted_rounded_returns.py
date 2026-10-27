"""Discount adjustments and global rounding through paid sale/return workflows."""
import json
import os
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .test_revolut_tip_refund import TestRevolutTipRefund
from .test_external_refunds import TestExternalRefunds
from .authorization_fixtures import configure_fixture_currency


@tagged("post_install", "-at_install")
class TestDiscountedRoundedReturns(TestPointOfSaleCommon):
    LOCATION_ID = TestRevolutTipRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutTipRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutTipRefund.PAYMENT_ID
    _order_payload = TestRevolutTipRefund._order_payload
    _mutation_actor = TestRevolutTipRefund._mutation_actor
    _rpc_refund = TestRevolutTipRefund._rpc_refund
    _save_return_draft = TestRevolutTipRefund._save_return_draft
    _rpc_refund_sources = TestRevolutTipRefund._rpc_refund_sources
    _response = TestRevolutTipRefund._response
    _refund_response = TestRevolutTipRefund._refund_response
    _stream_response = TestRevolutTipRefund._stream_response
    _start_allocated = TestRevolutTipRefund._start_allocated
    _external = TestExternalRefunds._external
    _discover = TestExternalRefunds._discover

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Discounted and rounded refund", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config.write({"payment_method_ids": [Command.link(cls.revolut_method.id)],
                                 "auto_validate_terminal_payment": True})
        cls.product = cls.env["product.product"].create({
            "name": "Discounted return goods", "available_in_pos": True,
            "list_price": 10, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened"})
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_SETTLEMENT_TEST": "test-only"}))
        self.request = self.enterContext(patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request"))
        self.env.flush_all()

    def _five_cent_rounding(self):
        rounding = self.env["account.cash.rounding"].create({
            "name": "Discounted return five-cent rounding", "rounding": 0.05,
            "rounding_method": "HALF-UP", "strategy": "add_invoice_line",
            "profit_account_id": self.company_data["default_account_revenue"].id,
            "loss_account_id": self.company_data["default_account_expense"].id,
        })
        self.pos_config.write({"cash_rounding": True, "only_round_cash_method": False,
                                   "rounding_method": rounding.id})

    def _collected_sale(self, lines, collected_minor, *, taxes=None, line_taxes=None, stock=False, partner=None, discount=0):
        """Capture and report fixture through public preparation/start/poll."""
        from odoo.addons.pos_revolut.models.terminal_tip import REPORT_COLUMNS
        precision = self.session.currency_id.decimal_places
        factor = 10 ** precision
        charge_base_minor = collected_minor
        tip_minor = 0
        sale = self._order_payload(str(uuid4()), str(uuid4()), payment_status="waiting")
        template = sale["lines"][0][2]
        sale["lines"] = []
        for index, (price, quantity) in enumerate(lines):
            applied_tax = line_taxes[index] if line_taxes is not None else taxes
            product = self.env["product.product"].create({
                "name": f"Return allocation product {index}", "list_price": price,
                "available_in_pos": True, "type": "consu" if price > 0 else "service",
                "is_storable": stock and price > 0,
                "taxes_id": [Command.set(applied_tax.ids)] if applied_tax else [Command.clear()],
            })
            self.assertTrue(product.id)
            if stock and price > 0:
                location = self.pos_config.picking_type_id.default_location_src_id
                self.env["stock.quant"]._update_available_quantity(product, location, abs(quantity))
            identity = f"{index + 1:08x}{str(uuid4())[8:]}"
            values = dict(template, uuid=identity, product_id=product.id, price_unit=price,
                          qty=quantity, discount=discount, price_subtotal=price * quantity * (1 - discount / 100),
                          price_subtotal_incl=price * quantity * (1 - discount / 100))
            if applied_tax:
                calculated = applied_tax.compute_all(price * (1 - discount / 100), self.session.currency_id, quantity, product=product)
                values.update(tax_ids=[Command.set(applied_tax.ids)], price_subtotal=calculated["total_excluded"],
                              price_subtotal_incl=calculated["total_included"])
            sale["lines"].append(Command.create(values))
        sale.update(state="draft", amount_paid=0,
                    amount_total=self.session.currency_id.round(sum(price * qty * (1 - discount / 100) for price, qty in lines)))
        if line_taxes is not None:
            sale["amount_total"] = charge_base_minor / factor
        if taxes or line_taxes is not None:
            sale["amount_tax"] = self.session.currency_id.round(sum(
                command[2]["price_subtotal_incl"] - command[2]["price_subtotal"] for command in sale["lines"]))
        if partner:
            sale["partner_id"] = partner.id
        if stock:
            self.session.write({"update_stock_at_closing": False})
        sale["payment_ids"][0][2].update(transaction_id=False, amount=charge_base_minor / factor)
        self.env.flush_all()
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
        if partner:
            final["partner_id"] = partner.id
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

    def _return_lines(self, fractions, expected):
        self.payload = self._order_payload(str(uuid4()), str(uuid4()), payment_status="waiting")
        template = self.payload["lines"][0][2]
        self.payload["lines"] = []
        originals = self.original.lines.sorted("uuid")
        for original, fraction in zip(originals, fractions):
            if not fraction:
                continue
            self.payload["lines"].append(Command.create(dict(
                template, uuid=str(uuid4()), product_id=original.product_id.id,
                qty=-fraction * original.qty, price_unit=original.price_unit,
                discount=original.discount, tax_ids=[Command.set(original.tax_ids.ids)],
                price_subtotal=-fraction * original.price_subtotal,
                price_subtotal_incl=-fraction * original.price_subtotal_incl,
                refunded_orderline_id=original.id,
            )))
        if self.original.partner_id:
            self.payload["partner_id"] = self.original.partner_id.id
        self.payload["amount_tax"] = self.session.currency_id.round(sum(
            command[2]["price_subtotal_incl"] - command[2]["price_subtotal"] for command in self.payload["lines"]))
        self.payload.update(amount_total=self.session.currency_id.round(sum(
            command[2]["price_subtotal_incl"] for command in self.payload["lines"])),
            amount_paid=-expected / 10 ** self.session.currency_id.decimal_places)
        self.payload["payment_ids"][0][2].update(amount=self.payload["amount_paid"], transaction_id=False)
        self.refund_id = str(uuid4())

    def _complete_return(self, expected, refunded=0):
        manager = self._mutation_actor()
        source = self._rpc_refund_sources(manager)[0]
        self.assertEqual(source["return_total_minor"], expected)
        # The manager picker supplies the conserved target used by the saved
        # return and subsequent native checkout.
        self.payload["amount_total"] = -expected / 10 ** self.session.currency_id.decimal_places
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=self.source.amount_minor,
                           currency=self.session.currency_id.name, refunded_amount=refunded),
            self._refund_response(amount=expected), self._refund_response("completed", amount=expected),
        ]
        started = self._start_allocated(expected, 0)
        posted = [call for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(posted[-1].kwargs["json"]["amount"], expected)
        self.assertEqual(started["return_total_minor"], expected)
        payment = self.payload["payment_ids"][0][2]
        completed = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
        ])
        self.assertEqual(completed["state"], "verified")
        self.payload["amount_total"] = -expected / 10 ** self.session.currency_id.decimal_places
        payment.update(payment_status="done", transaction_id=self.refund_id)
        # Final checkout sends the already saved cart unchanged, as the POS
        # does after reloading a manager-created native return.
        checkout = deepcopy(self.payload)
        checkout["lines"] = []
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[checkout]])
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        native = refund.pos_order_id
        self.assertEqual(native.state, "paid")
        self.assertEqual(native.amount_total, self.payload["amount_total"])
        self.assertEqual(refund.pos_payment_id.amount, self.payload["amount_total"])
        self.assertEqual(refund.pos_payment_id.transaction_id, self.refund_id)
        data = self._rpc_refund(manager, "pos.order", "read_pos_data", [[native.id], [], native.config_id.id])
        receipt = next(row for row in data["pos.order"] if row["uuid"] == native.uuid)
        self.assertEqual(receipt["amount_total"], self.payload["amount_total"])
        self.assertEqual(receipt["revolut_payable_target"], self.payload["amount_total"])
        expected_lines = {command[2]["refunded_orderline_id"]: command[2] for command in self.payload["lines"]}
        for line in native.lines:
            values = expected_lines[line.refunded_orderline_id.id]
            self.assertEqual(line.qty, values["qty"])
            self.assertEqual(line.price_unit, values["price_unit"])
            self.assertEqual(line.discount, values["discount"])
            self.assertEqual(line.tax_ids, line.refunded_orderline_id.tax_ids)
        return refund

    def test_negative_price_adjustment_sale_returns_original_collected_amount(self):
        self._collected_sale([(10, 1), (-1, 1)], 900)
        self._return_lines([1, 1], 900)
        self._complete_return(900)

    def test_external_penny_return_native_signs_report_and_invoice_as_refund(self):
        self._collected_sale([(0.01, 1)], 1)
        self.refund_id = str(uuid4())
        refund = self._discover([self._external("completed", amount=1)])
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Native completion must not issue a refund")
        manager = self._mutation_actor()
        action = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_prepare_native_return", [
            [refund.id], [{"original_line_id": self.original.lines.id, "quantity": 1}],
        ])
        native = self.env["pos.order"].browse(action["res_id"])
        for finalized in (False, True):
            if finalized:
                self._rpc_refund(manager, "pos.revolut.refund.operation", "action_validate_native_return", [[refund.id]])
            self.env.flush_all()
            self.env.invalidate_all()
            line = native.lines.read(["qty", "price_subtotal", "price_subtotal_incl"])[0]
            self.assertEqual(line["qty"], -1)
            # Native Odoo 18 stores signed subtotals for returned quantities.
            self.assertEqual(line["price_subtotal"], -0.01)
            self.assertEqual(line["price_subtotal_incl"], -0.01)
            self.assertEqual(native.amount_total, -0.01)
        report = self.env["report.pos.order"].search([("order_id", "=", native.id)])
        self.assertEqual(sum(report.mapped("price_subtotal_excl")), -0.01)
        self.assertEqual(sum(report.mapped("price_total")), -0.01)
        self.assertEqual(native.lines.margin, -0.01)
        native.write({"partner_id": self.partner1.id})
        result = native.with_context(generate_pdf=False).action_pos_order_invoice()
        credit = self.env["account.move"].browse(result["res_id"])
        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(credit.state, "posted")
        self.assertEqual(credit.amount_total, 0.01)
        self.assertEqual(sum(credit.invoice_line_ids.mapped("balance")), 0.01)
        self.assertAlmostEqual(sum(credit.line_ids.mapped("balance")), 0)
        self.assertEqual(self.original.amount_total, 0.01)
        self.request.assert_not_called()

    def test_discounted_penny_return_native_subtotals_and_reporting(self):
        self._collected_sale([(0.01, 2)], 1, discount=50)
        self._return_lines([1], 1)
        # Native Odoo 18 serializes signed subtotals on linked returns.
        self.payload["is_refund"] = True
        self.payload["lines"][0][2].update(price_subtotal=-0.01, price_subtotal_incl=-0.01)
        refund = self._complete_return(1)
        self.env.flush_all()
        self.env.invalidate_all()
        native = refund.pos_order_id
        self.assertEqual(native.lines.qty, -2)
        self.assertEqual(native.lines.discount, 50)
        self.assertEqual(native.lines.price_subtotal, -0.01)
        self.assertEqual(native.lines.price_subtotal_incl, -0.01)
        self.assertEqual(native.amount_total, -0.01)
        report = self.env["report.pos.order"].search([("order_id", "=", native.id)])
        self.assertEqual(sum(report.mapped("price_total")), -0.01)
        self.assertEqual(native.lines.margin, -0.01)

    def test_global_rounding_small_last_line_returns_original_collected_amount(self):
        self._five_cent_rounding()
        self._collected_sale([(10.01, 1)] * 6 + [(0.01, 1)], 6005)
        self._return_lines([1] * 7, 6005)
        self._complete_return(6005)

    def test_negative_quantity_adjustment_reverses_native_sign_without_extra_money(self):
        self._collected_sale([(10, 1), (1, -1)], 900)
        manager = self._mutation_actor()
        action = self._rpc_refund(manager, "pos.order", "refund", [[self.original.id]])
        native = self.env["pos.order"].browse(action["res_id"])
        self.assertEqual(sorted(native.lines.mapped("qty")), [-1, 1])
        self.assertEqual(native.amount_total, -9)
        self._return_lines([1, 1], 900)
        self.payload.update(id=native.id, uuid=native.uuid)
        for command in self.payload["lines"]:
            saved = native.lines.filtered(lambda line: line.refunded_orderline_id.id == command[2]["refunded_orderline_id"])
            command[2]["uuid"] = saved.uuid
        refund = self._complete_return(900)
        self.assertEqual(refund.pos_order_id, native)
        self.assertEqual(sorted(self.original.lines.mapped("qty")), [-1, 1])
        self.assertEqual(sorted(refund.pos_order_id.lines.mapped("price_unit")), [1, 10])

    def test_discounted_partial_returns_in_both_orders_exhaust_original_money(self):
        for quantities, amounts in (((0.25, 0.75), (225, 675)), ((0.75, 0.25), (675, 225))):
            with self.subTest(quantities=quantities):
                self._collected_sale([(10, 1), (-1, 1)], 900)
                refunded = 0
                for quantity, amount in zip(quantities, amounts):
                    self._return_lines([quantity, quantity], amount)
                    self._complete_return(amount, refunded)
                    refunded += amount
                self.assertEqual(refunded, 900)
                self.assertEqual(self._rpc_refund_sources(self._mutation_actor())[0]["remaining_minor"], 0)

    def test_adjustment_distributes_across_positive_goods_with_prices_unchanged(self):
        for selections, amounts in (([[1, 0, 0], [0, 1, 1]], [900, 1800]),
                                     ([[0, 1, 0], [1, 0, 1]], [1800, 900])):
            with self.subTest(selections=selections):
                self._collected_sale([(10, 1), (20, 1), (-3, 1)], 2700)
                refunded = 0
                for selection, amount in zip(selections, amounts):
                    self._return_lines(selection, amount)
                    refund = self._complete_return(amount, refunded)
                    refunded += amount
                    self.assertTrue(all(row["base_minor"] >= 0 for row in refund.return_allocation))
                self.assertEqual(refunded, 2700)
                self.assertEqual(sorted(self.original.lines.mapped("price_unit")), [-3, 10, 20])

    def test_global_rounding_up_down_and_uuid_order_conserve_each_partial_return(self):
        self._five_cent_rounding()
        for price, collected in ((10.01, 6005), (10.02, 6015)):
            for tiny_first in (False, True):
                with self.subTest(price=price, tiny_first=tiny_first):
                    lines = ([(0.01, 1)] + [(price, 1)] * 6 if tiny_first
                             else [(price, 1)] * 6 + [(0.01, 1)])
                    self._collected_sale(lines, collected)
                    first = [0, 1, 1, 1, 0, 0, 0] if tiny_first else [1, 1, 1, 0, 0, 0, 0]
                    selections = (first, [1 - quantity for quantity in first])
                    refunded = 0
                    for selection in selections:
                        self._return_lines(selection, 1)
                        chosen = self._rpc_refund_sources(self._mutation_actor())[0]["return_total_minor"]
                        self.assertGreater(chosen, 0)
                        self.assertLessEqual(chosen, collected - refunded)
                        self.payload["amount_paid"] = -chosen / 100
                        self.payload["payment_ids"][0][2]["amount"] = -chosen / 100
                        self._complete_return(chosen, refunded)
                        refunded += chosen
                    self.assertEqual(refunded, collected)
                    self.assertEqual(self._rpc_refund_sources(self._mutation_actor())[0]["remaining_minor"], 0)

    def test_discounted_partitions_support_zero_and_three_decimal_currency(self):
        for quantum, price, adjustment, collected, amounts in (
            (1, 1000, -100, 900, (225, 675)),
            (0.001, 10, -1, 9000, (2250, 6750)),
        ):
            with self.subTest(quantum=quantum):
                self.env["decimal.precision"].search([("name", "=", "Product Price")]).write({"digits": 3})
                currency = self.env.ref("base.JPY" if quantum == 1 else "base.KWD")
                configure_fixture_currency(self.pos_config, currency)
                self.assertEqual(self.session.currency_id.rounding, quantum)
                self._collected_sale([(price, 1), (adjustment, 1)], collected)
                refunded = 0
                for quantity, amount in zip((0.25, 0.75), amounts):
                    self._return_lines([quantity, quantity], amount)
                    self._complete_return(amount, refunded)
                    refunded += amount
                self.assertEqual(refunded, collected)

    def test_external_refund_associates_discounted_native_return_without_dispatch(self):
        for adjustment in ((-1, 1), (1, -1)):
            with self.subTest(adjustment=adjustment):
                self._collected_sale([(10, 1), adjustment], 900)
                self.refund_id = str(uuid4())
                refund = self._discover([self._external("completed", amount=900)])
                self.request.reset_mock()
                self.request.side_effect = AssertionError("Already issued refund must not move more money")
                manager = self._mutation_actor()
                action = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_prepare_native_return", [
                    [refund.id], [{"original_line_id": line.id, "quantity": 1} for line in self.original.lines],
                ])
                native = self.env["pos.order"].browse(action["res_id"])
                self.assertEqual(native.amount_total, -9)
                self._rpc_refund(manager, "pos.revolut.refund.operation", "action_validate_native_return", [[refund.id]])
                self.assertIn(native.state, ("paid", "done", "invoiced"))
                self.assertEqual(refund.pos_payment_id.amount, -9)
                self.assertEqual(refund.pos_payment_id.transaction_id, self.refund_id)
                self.assertEqual(refund.native_reconciliation_status, "native_completed")
                for line in native.lines:
                    self.assertEqual(line.qty, -line.refunded_orderline_id.qty)
                    self.assertEqual(line.price_unit, line.refunded_orderline_id.price_unit)
                self.request.assert_not_called()

    def test_previous_accepted_partial_money_stays_frozen_and_remaining_return_exhausts_source(self):
        self._collected_sale([(10, 1), (-1, 1)], 900)
        self._return_lines([0.5, 0], 450)
        first = self._complete_return(450)
        # Upgrade fixture: the old allocator accepted this half-goods return
        # at its recorded 5.00 ceiling. Preserve that financial fact and its
        # frozen line allocation, rather than rewriting it as a new 4.50 claim.
        frozen = deepcopy(first.return_allocation)
        frozen[0]["base_minor"] = 500
        self.env.cr.execute("""
            UPDATE pos_revolut_refund_operation SET amount = 5, amount_minor = 500,
                base_amount_minor = 500, return_total_minor = 500, return_allocation = %s::jsonb
            WHERE id = %s
        """, [json.dumps(frozen), first.id])
        self.env.cr.execute("""
            UPDATE pos_order SET amount_total = -5, amount_paid = -5,
                revolut_return_allocation = %s::jsonb WHERE id = %s
        """, [json.dumps(frozen), first.pos_order_id.id])
        self.env.cr.execute("UPDATE pos_payment SET amount = -5 WHERE id = %s", [first.pos_payment_id.id])
        self.env.invalidate_all()
        history = first.read(["amount_minor", "base_amount_minor", "return_allocation", "revolut_order_id", "verified_at"])
        self._return_lines([0.5, 1], 400)
        self._complete_return(400, 500)
        self.assertEqual(first.read(["amount_minor", "base_amount_minor", "return_allocation", "revolut_order_id", "verified_at"]), history)
        self.assertEqual(self._rpc_refund_sources(self._mutation_actor())[0]["remaining_minor"], 0)

    def _complete_zero_return(self, remaining_minor=0):
        manager = self._mutation_actor()
        source = self._rpc_refund_sources(manager)[0]
        self.assertEqual(source["return_total_minor"], 0)
        self.assertEqual(source["remaining_minor"], remaining_minor)
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Zero entitlement must not dispatch a refund")
        self.payload.update(state="draft", amount_paid=0, payment_ids=[])
        saved = self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        native = self.env["pos.order"].browse(next(
            row["id"] for row in saved["pos.order"] if row["uuid"] == self.payload["uuid"]
        ))
        self.assertEqual(native.amount_total, 0)
        self.assertTrue(native.is_refund)
        self.payload.update(id=native.id, state="paid", amount_total=0)
        self.payload["lines"] = [Command.update(
            native.lines.filtered(lambda line: line.uuid == command[2]["uuid"]).id, command[2],
        ) for command in self.payload["lines"]]
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        self.env.invalidate_all()
        self.assertEqual(native.state, "paid")
        self.assertEqual(native.amount_total, 0)
        self.assertFalse(native.payment_ids)
        receipt = self._rpc_refund(manager, "pos.order", "read_pos_data", [[native.id], [], native.config_id.id])
        displayed = next(row for row in receipt["pos.order"] if row["id"] == native.id)
        self.assertEqual(displayed["amount_total"], 0)
        self.request.assert_not_called()
        return native

    def test_zero_money_adjustment_reversal_completes_after_goods_refund(self):
        for price, quantity in ((-1, 1), (1, -1)):
            with self.subTest(adjustment_price=price, adjustment_quantity=quantity):
                self._collected_sale([(10, 1), (price, quantity)], 900)
                self._return_lines([1, 0], 900)
                self._complete_return(900)
                self.assertTrue(self.original.has_refundable_lines)
                self._return_lines([0, 1], 0)
                native = self._complete_zero_return()
                self.assertEqual(native.lines.qty, -quantity)
                self.assertEqual(native.lines.price_unit, price)
                for line in self.original.lines:
                    self.assertEqual(line.refunded_qty, line.qty)
                self.assertFalse(self.original.has_refundable_lines)

    def test_zero_value_invoiced_return_keeps_credit_note_and_original_identity(self):
        self._collected_sale([(10, 1), (-1, 1)], 900, partner=self.partner1)
        self._return_lines([1, 0], 900)
        self._complete_return(900)
        self._return_lines([0, 1], 0)
        native = self._complete_zero_return()
        original_uuid = native.uuid

        action = native.with_context(generate_pdf=False).action_pos_order_invoice()

        credit = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(native.state, "invoiced")
        self.assertEqual(credit.state, "posted")
        self.assertEqual(credit.amount_total, 0)
        with self.subTest(boundary="credit_note"):
            self.assertEqual(credit.move_type, "out_refund")
        with self.subTest(boundary="identity"), self.assertRaises(UserError), self.env.cr.savepoint():
            native.write({"uuid": str(uuid4())})
        self.assertEqual(native.uuid, original_uuid)
        self.request.assert_not_called()

    def test_zero_money_tiny_rounded_fraction_completes_before_remaining_goods_refund(self):
        self._five_cent_rounding()
        self._collected_sale([(10.01, 1)] * 6 + [(0.01, 1)], 6005)
        self._return_lines([0] * 6 + [0.25], 0)
        native = self._complete_zero_return(remaining_minor=6005)
        self.assertEqual(native.lines.qty, -0.25)
        self.assertEqual(native.lines.price_unit, 0.01)
        self._return_lines([1] * 6 + [0.75], 6005)
        self._complete_return(6005)
        self.assertEqual(self.original.lines.mapped("refunded_qty"), [1] * 7)

    def test_previous_full_positive_line_keeps_money_and_zero_remaining_goods_return(self):
        self._collected_sale([(9, 1), (1, 1), (-1, 1)], 900)
        self._return_lines([1, 0, 0], 810)
        first = self._complete_return(810)
        # The prior allocator accepted all 9.00 on the first product. Its
        # already completed refund and quantity must remain immutable, while
        # the remaining positive product and adjustment still reverse natively.
        frozen = deepcopy(first.return_allocation)
        frozen[0]["base_minor"] = 900
        self.env.cr.execute("""
            UPDATE pos_revolut_refund_operation SET amount = 9, amount_minor = 900,
                base_amount_minor = 900, return_total_minor = 900, return_allocation = %s::jsonb
            WHERE id = %s
        """, [json.dumps(frozen), first.id])
        self.env.cr.execute("""
            UPDATE pos_order SET amount_total = -9, amount_paid = -9,
                revolut_return_allocation = %s::jsonb WHERE id = %s
        """, [json.dumps(frozen), first.pos_order_id.id])
        self.env.cr.execute("UPDATE pos_payment SET amount = -9 WHERE id = %s", [first.pos_payment_id.id])
        self.env.invalidate_all()
        history = first.read(["amount_minor", "return_allocation", "verified_at", "revolut_order_id"])
        self._return_lines([0, 1, 1], 0)
        native = self._complete_zero_return()
        self.assertEqual(sorted(native.lines.mapped("price_unit")), [-1, 1])
        self.assertEqual(first.read(["amount_minor", "return_allocation", "verified_at", "revolut_order_id"]), history)
        self.assertEqual(self.original.lines.mapped("refunded_qty"), [1, 1, 1])

    def test_positive_sub_minor_product_prices_return_collected_whole_cart_money(self):
        self.env["decimal.precision"].search([("name", "=", "Product Price")]).write({"digits": 3})
        self.company.write({"tax_calculation_rounding_method": "round_globally"})
        self._collected_sale([(0.004, 1)] * 6, 2)
        self._return_lines([1] * 6, 2)
        self._complete_return(2)

    def test_discounted_taxed_stock_return_posts_credit_note_and_restocks_once(self):
        tax = self.env["account.tax"].create({
            "name": "Discounted return included twenty", "amount": 20,
            "amount_type": "percent", "company_id": self.company.id,
            "price_include_override": "tax_included",
        })
        self._collected_sale([(12, 1), (-1.2, 1)], 1080, taxes=tax, stock=True, partner=self.partner1)
        goods = self.original.lines.sorted("uuid")[0].product_id
        location = self.pos_config.picking_type_id.default_location_src_id
        before = self.env["stock.quant"]._get_available_quantity(goods, location)
        self.assertTrue(self.original.picking_ids)
        self.assertEqual(set(self.original.picking_ids.mapped("state")), {"done"})
        self.assertEqual(self.original.amount_tax, 1.8)
        self._return_lines([1, 1], 1080)
        refund = self._complete_return(1080)
        native = refund.pos_order_id
        self.assertEqual(native.amount_tax, -1.8)
        self.assertEqual(self.env["stock.quant"]._get_available_quantity(goods, location), before + 1)
        moves = native.picking_ids.move_ids.filtered(lambda move: move.product_id == goods)
        self.assertEqual(moves.quantity, 1)
        self.assertEqual(moves.location_id.usage, "customer")
        self.assertEqual(moves.location_dest_id.usage, "internal")
        result = native.with_context(generate_pdf=False).action_pos_order_invoice()
        credit = self.env["account.move"].browse(result["res_id"])
        self.assertEqual(credit.state, "posted")
        self.assertEqual(credit.move_type, "out_refund")
        self.assertEqual(credit.amount_total, 10.8)
        self.assertEqual(credit.amount_tax, 1.8)
        self.assertAlmostEqual(sum(credit.line_ids.mapped("balance")), 0, places=6)
        evidence = (native.picking_ids.ids, moves.ids, native.payment_ids.ids, credit.id)
        self._rpc_refund(self._mutation_actor(), "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        self.assertEqual((native.picking_ids.ids, moves.ids, native.payment_ids.ids, native.account_move.id), evidence)
        self.assertEqual(self.env["stock.quant"]._get_available_quantity(goods, location), before + 1)

    def test_rounded_taxed_partial_credit_notes_keep_conserved_last_cent(self):
        self._five_cent_rounding()
        tax = self.env["account.tax"].create({
            "name": "Rounded partial return included twenty", "amount": 20,
            "amount_type": "percent", "company_id": self.company.id,
            "price_include_override": "tax_included",
        })
        self._collected_sale([(10.01, 1)], 1000, taxes=tax, partner=self.partner1)
        credits = self.env["account.move"]
        refunded = 0
        for quantity, amount in ((0.25, 250), (0.75, 750)):
            self._return_lines([quantity], amount)
            # Native POS recomputes the fractional line's taxes; prorating
            # the already rounded original base would introduce a stale cent.
            values = self.payload["lines"][0][2]
            totals = tax.compute_all(values["price_unit"], self.session.currency_id,
                                     values["qty"], product=self.original.lines.product_id)
            values.update(price_subtotal=totals["total_excluded"],
                          price_subtotal_incl=totals["total_included"])
            refund = self._complete_return(amount, refunded)
            native = refund.pos_order_id
            tax_amount = -native.amount_tax
            action = native.with_context(generate_pdf=False).action_pos_order_invoice()
            credit = self.env["account.move"].browse(action["res_id"])
            self.assertEqual(credit.state, "posted")
            self.assertEqual(credit.move_type, "out_refund")
            self.assertEqual(credit.amount_total, amount / 100)
            self.assertEqual(credit.amount_tax, tax_amount)
            self.assertEqual(credit.invoice_line_ids.revolut_return_line_id, native.lines)
            self.assertFalse(credit.invoice_cash_rounding_id)
            self.assertAlmostEqual(sum(credit.line_ids.mapped("balance")), 0, places=6)
            credits |= credit
            refunded += amount
        self.assertEqual(sum(credits.mapped("amount_total")), self.original.amount_total)
        self.assertEqual(self.original.lines.refunded_qty, 1)
        self.assertFalse(self.original.has_refundable_lines)

    def test_failed_discounted_reservation_releases_only_its_claim_and_survivor_recovers(self):
        self._collected_sale([(10, 1), (-1, 1)], 900)
        manager = self._mutation_actor()
        attempts = []
        for _ in range(2):
            self._return_lines([0.25, 0.25], 225)
            self.request.side_effect = [
                self._response(id=self.source.revolut_order_id, state="completed", amount=900,
                               currency=self.session.currency_id.name, refunded_amount=0),
                self._refund_response(amount=225),
            ]
            started = self._start_allocated(225, 0)
            attempts.append((started, deepcopy(self.payload), self.refund_id))
        first, first_payload, first_reference = attempts[0]
        survivor, survivor_payload, survivor_reference = attempts[1]
        self.refund_id = first_reference
        self.request.side_effect = [self._refund_response("failed", amount=225)]
        failed = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], first["operation_id"], first_payload["uuid"],
            first_payload["payment_ids"][0][2]["uuid"],
        ])
        self.assertEqual(failed["state"], "failed")
        self.env.invalidate_all()
        surviving = self.env["pos.revolut.refund.operation"].browse(survivor["operation_id"])
        frozen = deepcopy(surviving.return_allocation)
        self._return_lines([0.75, 0.75], 675)
        self.assertEqual(self._rpc_refund_sources(manager)[0]["return_total_minor"], 675)
        self.assertEqual(surviving.return_allocation, frozen)
        self.payload = survivor_payload
        self.refund_id = survivor_reference
        payment = self.payload["payment_ids"][0][2]
        self.request.side_effect = [self._refund_response("completed", amount=225)]
        verified = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], survivor["operation_id"], self.payload["uuid"], payment["uuid"],
        ])
        self.assertEqual(verified["state"], "verified")
        self.env.invalidate_all()
        payment.update(payment_status="done", transaction_id=self.refund_id)
        ready = deepcopy(self.payload)
        ready.update(state="draft", lines=[])
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[ready]])
        self.env.invalidate_all()
        self.request.reset_mock()
        self.request.side_effect = AssertionError("Recovery must not dispatch another refund")
        action = self._rpc_refund(manager, "pos.revolut.refund.operation", "action_recover_return", [[surviving.id]])
        self.assertTrue(action["url"].endswith(self.payload["uuid"]))
        self.assertEqual(surviving.return_allocation, frozen)
        self.request.assert_not_called()
        payment.update(payment_status="done", transaction_id=self.refund_id)
        checkout = deepcopy(self.payload)
        checkout["lines"] = []
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[checkout]])
        self._return_lines([0.75, 0.75], 675)
        last = self._complete_return(675, 225)
        self.assertEqual(surviving.amount_minor + last.amount_minor, 900)
        self.assertEqual(surviving.return_allocation, frozen)
        self.assertEqual(self._rpc_refund_sources(manager)[0]["remaining_minor"], 0)

    def test_globally_taxed_sub_minor_goods_and_untaxed_adjustments_return_collected_money(self):
        self.env["decimal.precision"].search([("name", "=", "Product Price")]).write({"digits": 3})
        self.company.write({"tax_calculation_rounding_method": "round_globally"})
        tax = self.env["account.tax"].create({
            "name": "Subminor goods excluded hundred", "amount": 100,
            "amount_type": "percent", "company_id": self.company.id,
            "price_include_override": "tax_excluded",
        })
        # Native global base/tax buckets round -0.006 base to -0.01 and
        # 0.024 tax to 0.02, collecting 0.01. Independently rounded native
        # line amounts have no positive net minor-unit total.
        self._collected_sale([(0.004, 1)] * 6 + [(-0.005, 1)] * 6, 1,
                             line_taxes=[tax] * 6 + [None] * 6)
        self._return_lines([1] * 12, 1)
        self._complete_return(1)

"""Durable return claims exercised through manager refund/native RPCs."""
import os
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged

from .test_revolut_tip_refund import TestRevolutTipRefund


@tagged("post_install", "-at_install")
class TestReturnAllocation(CommonPosTest):
    LOCATION_ID = TestRevolutTipRefund.LOCATION_ID
    TERMINAL_ID = TestRevolutTipRefund.TERMINAL_ID
    PAYMENT_ID = TestRevolutTipRefund.PAYMENT_ID
    _operation = TestRevolutTipRefund._operation
    _order_payload = TestRevolutTipRefund._order_payload
    _mutation_actor = TestRevolutTipRefund._mutation_actor
    _rpc_refund = TestRevolutTipRefund._rpc_refund
    _save_return_draft = TestRevolutTipRefund._save_return_draft
    _rpc_start_refund = TestRevolutTipRefund._rpc_start_refund
    _rpc_refund_sources = TestRevolutTipRefund._rpc_refund_sources
    _response = TestRevolutTipRefund._response
    _refund_response = TestRevolutTipRefund._refund_response
    _stream_response = TestRevolutTipRefund._stream_response
    _terminal_sale = TestRevolutTipRefund._terminal_sale
    _tip_return = TestRevolutTipRefund._tip_return
    _start_allocated = TestRevolutTipRefund._start_allocated
    _complete_rounding_partition = TestRevolutTipRefund._complete_rounding_partition
    _legacy_sale = TestRevolutTipRefund._legacy_sale

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Durable return allocation test", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID, "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({"payment_method_ids": [Command.link(cls.revolut_method.id)],
                                 "auto_validate_terminal_payment": True})
        cls.product = cls.env["product.product"].create({
            "name": "Durable return goods", "available_in_pos": True,
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
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_SETTLEMENT_TEST": "test-only"}))
        self.request = self.enterContext(patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request"))
        self.env.flush_all()

    def _reserve_partition(self, manager, quantity, amount, refunded=0):
        self._tip_return(goods_qty=quantity, tip_qty=0, payment_minor=amount)
        self.payload["amount_total"] = self.session.currency_id.round(self.payload["amount_total"])
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=refunded),
            self._refund_response(amount=amount),
        ]
        return self._start_allocated(amount, 0)

    def test_native_readonly_allocation_echo_cannot_create_or_clear_authority(self):
        self._terminal_sale(tip_minor=0)
        manager = self._mutation_actor()
        self._tip_return(goods_qty=0.25, tip_qty=0, payment_minor=309)
        self.payload["revolut_return_allocation"] = False
        self._save_return_draft(actor=manager)
        draft = self.env["pos.order"].browse(self.payload["id"])
        draft.invalidate_recordset()
        self.assertEqual(sum(row["base_minor"] for row in draft.revolut_return_allocation), 309)
        self.assertEqual(draft.amount_total, -3.09)
        authority = deepcopy(draft.revolut_return_allocation)
        with self.assertRaisesRegex(AccessError, "server-owned"):
            self._rpc_refund(manager, "pos.order", "write", [[draft.id], {
                "revolut_return_allocation": False,
            }])
        forged = deepcopy(self.payload)
        forged.update(state="draft", amount_paid=0, lines=[], payment_ids=[],
                      revolut_return_allocation=[dict(authority[0], base_minor=310)])
        with self.assertRaisesRegex(AccessError, "server-owned"):
            self._rpc_refund(manager, "pos.order", "sync_from_ui", [[forged]])
        self.payload["revolut_return_allocation"] = authority
        returned = self._complete_rounding_partition(manager, 309, 0)
        self.assertEqual(returned.pos_order_id.revolut_return_allocation, authority)

    def test_failed_earlier_claim_releases_without_repricing_survivor(self):
        self._terminal_sale(tip_minor=0)
        manager = self._mutation_actor()
        first = self._reserve_partition(manager, 0.25, 309)
        first_payload, first_reference = deepcopy(self.payload), self.refund_id
        second = self._reserve_partition(manager, 0.25, 308)
        second_payload = deepcopy(self.payload)
        self.refund_id = first_reference
        self.request.side_effect = [self._refund_response("failed", amount=309)]
        failed = self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], first["operation_id"], first_payload["uuid"],
            first_payload["payment_ids"][0][2]["uuid"],
        ])
        self.assertEqual(failed["state"], "failed")
        self.env.invalidate_all()
        survivor = self.env["pos.revolut.refund.operation"].browse(second["operation_id"])
        frozen = deepcopy(survivor.return_allocation)
        self.assertEqual(survivor.return_total_minor, 308)
        self._tip_return(goods_qty=0.75, tip_qty=0, payment_minor=926)
        self.payload["amount_total"] = -9.26
        self.assertEqual(self._rpc_refund_sources(manager)[0]["return_total_minor"], 926)
        self.assertEqual(survivor.return_allocation, frozen)
        self.payload = second_payload
        self.refund_id = survivor.revolut_order_id
        # Existing reservation retries and finalization reuse the frozen 308.
        self.request.side_effect = [self._refund_response("completed", amount=308)]
        payment = self.payload["payment_ids"][0][2]
        self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], survivor.id, self.payload["uuid"], payment["uuid"],
        ])
        payment.update(payment_status="done", transaction_id=self.refund_id)
        self.payload["amount_total"] = -3.08
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        self._tip_return(goods_qty=0.75, tip_qty=0, payment_minor=926)
        self._complete_rounding_partition(manager, 926, 308)
        posts = [call.kwargs["json"]["amount"] for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(posts, [309, 308, 926])
        self.assertEqual(308 + 926, 1234)

    def test_single_line_historical_completed_target_consumes_actual_cents(self):
        self._terminal_sale(tip_minor=0)
        manager = self._mutation_actor()
        self._tip_return(goods_qty=0.25, tip_qty=0, payment_minor=309)
        refund = self._complete_rounding_partition(manager, 309, 0)
        # Simulate an upgrade preserving the original completed amounts and
        # references, but lacking the new per-line JSON fields.
        self.env.cr.execute("UPDATE pos_revolut_refund_operation SET return_allocation = NULL, return_total_minor = 0 WHERE id = %s", [refund.id])
        self.env.cr.execute("UPDATE pos_order SET revolut_return_allocation = NULL WHERE id = %s", [refund.pos_order_id.id])
        self.env.invalidate_all()
        self._tip_return(goods_qty=0.75, tip_qty=0, payment_minor=925)
        self._complete_rounding_partition(manager, 925, 309)
        self.assertEqual(refund.amount_minor, 309)

    def test_ambiguous_historical_multi_line_target_blocks_new_dispatch(self):
        self._terminal_sale(tip_minor=200)
        manager = self._mutation_actor()
        self._tip_return(goods_qty=0.25, tip_qty=0.25, payment_minor=359)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1434,
                           currency=self.session.currency_id.name, refunded_amount=0),
            self._refund_response(amount=359),
        ]
        started = self._start_allocated(309, 50)
        self.env.cr.execute("UPDATE pos_revolut_refund_operation SET return_allocation = NULL WHERE id = %s", [started["operation_id"]])
        self.env.invalidate_all()
        self._tip_return(goods_qty=0.75, tip_qty=0.75, payment_minor=1075)
        before = self.request.call_count
        with self.assertRaisesRegex(UserError, "trustworthy per-line"):
            self._rpc_refund_sources(manager)
        self.assertEqual(self.request.call_count, before)

    def _multi_return(self, quantity, target, tenders):
        self.payload = self._order_payload(str(uuid4()), str(uuid4()), payment_status="waiting")
        template = self.payload["lines"][0][2]
        self.payload["lines"] = [Command.create(dict(
            template, uuid=str(uuid4()), product_id=line.product_id.id,
            qty=-quantity * line.qty, price_unit=line.price_unit,
            price_subtotal=-quantity * line.price_subtotal,
            price_subtotal_incl=-quantity * line.price_subtotal_incl,
            refunded_orderline_id=line.id, tax_ids=[Command.set(line.tax_ids.ids)],
        )) for line in self.original.lines]
        template = self.payload["payment_ids"][0][2]
        self.payload["payment_ids"] = [Command.create(dict(
            template, uuid=str(uuid4()), amount=-minor / 100, transaction_id=False,
        )) for minor in tenders]
        self.payload.update(amount_total=-target / 100, amount_paid=-target / 100)
        self.refund_id = str(uuid4())

    def test_multiple_lines_and_tenders_consume_one_odd_fraction_target(self):
        self._terminal_sale(tip_minor=0, split_lines=True)
        manager = self._mutation_actor()
        self._multi_return(0.25, 308, [150, 158])
        self.assertEqual(self._rpc_refund_sources(manager)[0]["return_total_minor"], 308)
        refunds = []
        refunded = 0
        for minor, command in zip((150, 158), self.payload["payment_ids"]):
            payment = command[2]
            self.refund_id = str(uuid4())
            self.request.side_effect = [
                self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                               currency=self.session.currency_id.name, refunded_amount=refunded),
                self._refund_response(amount=minor), self._refund_response("completed", amount=minor),
            ]
            self._save_return_draft(actor=manager, payment_uuid=payment["uuid"])
            saved = self.env["pos.order"].browse(self.payload["id"])
            normalize = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot
            self.assertEqual(normalize(saved._revolut_order_values(), native_order=True), normalize(self.payload))
            self.assertEqual(saved.state, "draft")
            started = self._rpc_refund(manager, "pos.payment.method", "revolut_start_refund", [
                [self.revolut_method.id], self.session.id, self.payload["uuid"], payment["uuid"],
                payment["amount"], self.session.currency_id.id, self.payload, self.source.id, minor, 0,
            ])
            self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
                [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
            ])
            payment.update(payment_status="done", transaction_id=self.refund_id)
            refunds.append(started["operation_id"])
            refunded += minor
            self.env.invalidate_all()
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        operations = self.env["pos.revolut.refund.operation"].browse(refunds)
        self.assertEqual(operations[0].return_allocation, operations[1].return_allocation)
        self.assertEqual(sum(row["base_minor"] for row in operations[0].return_allocation), 308)
        self._multi_return(0.75, 926, [926])
        self.assertEqual(self._rpc_refund_sources(manager)[0]["return_total_minor"], 926)
        self.request.side_effect = [
            self._response(id=self.source.revolut_order_id, state="completed", amount=1234,
                           currency=self.session.currency_id.name, refunded_amount=308),
            self._refund_response(amount=926), self._refund_response("completed", amount=926),
        ]
        started = self._start_allocated(926, 0)
        payment = self.payload["payment_ids"][0][2]
        self._rpc_refund(manager, "pos.payment.method", "revolut_poll_refund", [
            [self.revolut_method.id], started["operation_id"], self.payload["uuid"], payment["uuid"],
        ])
        payment.update(payment_status="done", transaction_id=self.refund_id)
        self._rpc_refund(manager, "pos.order", "sync_from_ui", [[deepcopy(self.payload)]])
        self.env.invalidate_all()
        last = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        self.assertEqual(last.pos_order_id.amount_total, -9.26)
        self.assertEqual(len(last.return_allocation), 2)
        posts = [call.kwargs["json"]["amount"] for call in self.request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(posts, [150, 158, 926])
        self.assertEqual(sum(posts), 1234)
        # Completed historical multi-line documents still reload their saved
        # amount, even though their missing line split blocks NEW allocations.
        historical_order = operations[0].pos_order_id
        self.env.cr.execute("UPDATE pos_revolut_refund_operation SET return_allocation = NULL WHERE id = ANY(%s)", [refunds])
        self.env.cr.execute("UPDATE pos_order SET revolut_return_allocation = NULL WHERE id = %s", [historical_order.id])
        self.env.invalidate_all()
        loaded = self._rpc_refund(manager, "pos.order", "read_pos_data_uuid", [historical_order.uuid])
        historical = next(row for row in loaded["pos.order"] if row["uuid"] == historical_order.uuid)
        self.assertEqual(historical["amount_total"], -3.08)
        self.assertEqual(historical["revolut_payable_target"], -3.08)
        with self.assertRaisesRegex(UserError, "trustworthy per-line"):
            self._rpc_refund_sources(manager)

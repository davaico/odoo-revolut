import os
from copy import deepcopy
from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.pos_revolut.tests.authorization_fixtures import authorized_start, native_products
from odoo.addons.pos_revolut.tests.test_revolut_payment import TestRevolutPayment
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantContext(TransactionCase):
    LOCATION_ID = TestRevolutPayment.LOCATION_ID
    TERMINAL_ID = TestRevolutPayment.TERMINAL_ID

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        bridge = cls.env["ir.module.module"].search(
            [("name", "=", "pos_revolut_restaurant")], limit=1
        )
        if bridge:
            raise AssertionError("The retired Revolut Restaurant addon is still listed")
        cls.method = cls.env["pos.payment.method"].create({
            "name": "Restaurant Revolut test",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID,
            "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_RESTAURANT_TEST",
        })
        cls.config = cls.env["pos.config"].create({
            "name": "Restaurant Revolut test",
            "payment_method_ids": [Command.link(cls.method.id)],
            "auto_validate_terminal_payment": True,
        })
        dine_in = cls.env.ref("pos_revolut.pos_takein_preset")
        takeout = cls.env.ref("pos_revolut.pos_takeout_preset")
        cls.config.write({
            "module_pos_restaurant": True, "use_presets": True,
            "default_preset_id": dine_in.id,
            "available_preset_ids": [Command.link(dine_in.id), Command.link(takeout.id)],
        })
        cls.product = native_products(cls.env, cls.config)
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id, "state": "opened",
        })
        floor = cls.env["restaurant.floor"].create({
            "name": "Revolut test floor",
            "pos_config_ids": [Command.link(cls.config.id)],
        })
        cls.table = cls.env["restaurant.table"].create({
            "table_number": 1, "floor_id": floor.id, "seats": 2,
        })

    def setUp(self):
        super().setUp()
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)

    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _start(self, preset_id, table_id, *, preset_time=False):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        snapshot = {
            "pricelist_id": self.config.pricelist_id.id,
            "fiscal_position_id": False,
            "restaurant": {"preset_id": preset_id, "table_id": table_id},
            "lines": [{
                "uuid": str(uuid4()), "product_id": self.product.id,
                "qty": 1, "price_unit": 12.34,
                "discount": 0, "tax_ids": [],
            }],
        }
        return authorized_start(self.method,
            self.session.id, order_uuid, line_uuid, 4.34,
            self.config.currency_id.id, False, snapshot, preset_time=preset_time,
        )

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_verified_draft_keeps_order_identity_across_table_change(self, request):
        other_table = self.env["restaurant.table"].create({
            "table_number": 2, "floor_id": self.table.floor_id.id, "seats": 2,
        })
        product = self.env["product.product"].create({
            "name": "Restaurant Revolut product",
            "available_in_pos": True,
            "list_price": 12.34,
            "taxes_id": [Command.clear()],
        })
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = {
            "amount_paid": 4.34,
            "amount_return": 0,
            "amount_tax": 0,
            "amount_total": 12.34,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "pricelist_id": self.config.pricelist_id.id,
            "lines": [list(Command.create({
                "discount": 0, "pack_lot_ids": [], "price_unit": 12.34,
                "product_id": product.id, "price_subtotal": 12.34,
                "price_subtotal_incl": 12.34, "qty": 1,
                "tax_ids": [[6, False, []]], "uuid": str(uuid4()),
            }))],
            "name": f"Order {order_uuid}",
            "session_id": self.session.id,
            "sequence_number": 1,
            "payment_ids": [list(Command.create({
                "amount": 4.34, "name": fields.Datetime.now(),
                "payment_method_id": self.method.id,
                "payment_status": "done", "uuid": line_uuid,
            }))],
            "table_id": self.table.id,
            "uuid": order_uuid,
            "user_id": self.env.uid,
            "to_invoice": False,
            "state": "draft",
        }
        operation = self.env["pos.revolut.payment.operation"].sudo().create({
            "payment_method_id": self.method.id,
            "company_id": self.env.company.id,
            "pos_config_id": self.config.id,
            "pos_session_id": self.session.id,
            "order_uuid": order_uuid,
            "payment_line_uuid": line_uuid,
            "amount": 4.34,
            "amount_minor": 434,
            "currency_id": self.session.currency_id.id,
            "currency_code": self.session.currency_id.name,
            "environment": "sandbox",
            "location_id": self.LOCATION_ID,
            "terminal_id": self.TERMINAL_ID,
            "fulfilment_type": "eat_in",
            "secret_reference": "ODOO_REVOLUT_SECRET_RESTAURANT_TEST",
            "state": "verified",
            "revolut_order_id": str(uuid4()),
            "revolut_payment_intent_id": str(uuid4()),
            "revolut_payment_id": str(uuid4()),
            "financial_snapshot": self.env[
                "pos.revolut.payment.operation"
            ]._normalize_financial_snapshot(payload),
        })
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id
        moved = deepcopy(payload)
        moved["table_id"] = other_table.id

        first = self.env["pos.order"].sync_from_ui([payload])
        draft = self.env["pos.order"].browse(first["pos.order"][0]["id"])
        # Native 18 sends update commands after the first sync assigns IDs.
        moved["lines"][0][:2] = [Command.UPDATE, draft.lines.id]
        moved["payment_ids"][0][:2] = [Command.UPDATE, draft.payment_ids.id]
        edited = deepcopy(moved)
        edited["lines"][0][2]["qty"] = 2
        second = self.env["pos.order"].sync_from_ui([deepcopy(moved)])
        operation.invalidate_recordset()
        self.assertEqual(draft.id, second["pos.order"][0]["id"])
        self.assertEqual(draft.table_id, other_table)
        self.assertEqual(operation.pos_order_id, draft)
        self.assertEqual(operation.pos_payment_id.uuid, line_uuid)
        with self.assertRaisesRegex(UserError, "order changed while Revolut payment"):
            self.env["pos.order"].sync_from_ui([edited])
        draft.invalidate_recordset()
        self.assertEqual(draft.table_id, other_table)
        self.assertEqual(draft.lines.qty, 1)
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_unknown_restaurant_context_does_not_dispatch(self, request):
        with self.assertRaisesRegex(UserError, "Select an available checkout preset"):
            self._start(False, False)
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_unknown_preset_with_table_does_not_dispatch(self, request):
        with self.assertRaisesRegex(UserError, "Select an available checkout preset"):
            self._start(False, self.table.id)
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_dine_in_uses_eat_in_provisional_payload(self, request):
        request.side_effect = [
            self._response({"terminals": [{
                "id": self.TERMINAL_ID, "online": True,
                "operation_mode": "pos", "location_id": self.LOCATION_ID,
            }]}),
            self._response({"id": str(uuid4())}),
            self._response({"id": str(uuid4()), "state": "pending"}),
        ]
        started = self._start(
            self.env.ref("pos_revolut.pos_takein_preset").id, self.table.id
        )
        self.assertEqual(started["state"], "pending")
        order_post = [call for call in request.call_args_list
                      if call.args[0] == "POST"][0]
        self.assertEqual(order_post.kwargs["json"]["fulfilment_type"], "eat_in")
        self.assertEqual(order_post.kwargs["json"]["amount"], 434)
        self.assertEqual(order_post.kwargs["json"]["currency"], self.config.currency_id.name)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_takeaway_uses_take_away_provisional_payload(self, request):
        request.side_effect = [
            self._response({"terminals": [{
                "id": self.TERMINAL_ID, "online": True,
                "operation_mode": "pos", "location_id": self.LOCATION_ID,
            }]}),
            self._response({"id": str(uuid4())}),
            self._response({"id": str(uuid4()), "state": "pending"}),
        ]
        started = self._start(
            self.env.ref("pos_revolut.pos_takeout_preset").id, False,
            preset_time=fields.Datetime.now(),
        )
        self.assertEqual(started["state"], "pending")
        order_post = [call for call in request.call_args_list
                      if call.args[0] == "POST"][0]
        self.assertEqual(order_post.kwargs["json"]["fulfilment_type"], "take_away")
        self.assertEqual(order_post.kwargs["json"]["amount"], 434)

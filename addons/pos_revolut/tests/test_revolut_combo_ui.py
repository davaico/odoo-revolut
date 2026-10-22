"""Configured combo quantities reach native checkout at their authorized price."""

from unittest.mock import Mock, patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.test_frontend import TestPointOfSaleHttpCommon
from odoo.tests import tagged

from .authorization_fixtures import install_zero_reports
from .test_ui import TestRevolutVerifiedCheckout


@tagged("post_install", "-at_install")
class TestRevolutComboCheckout(TestPointOfSaleHttpCommon):
    LOCATION_ID = TestRevolutVerifiedCheckout.LOCATION_ID
    TERMINAL_ID = TestRevolutVerifiedCheckout.TERMINAL_ID

    def _configure_shared_currency_combo(self, *, extra_quantity=True):
        main = self.env["res.company"]._get_main_company()
        company = self.main_pos_config.company_id
        self.assertNotEqual(company, main)
        source = main.currency_id
        target = self.env.ref("base.EUR") if source != self.env.ref("base.EUR") else self.env.ref("base.USD")
        target.active = True
        company.currency_id = target
        self.env["res.currency.rate"].search([
            ("company_id", "=", company.root_id.id), ("name", "=", fields.Date.today()),
            ("currency_id", "in", (source | target).ids),
        ]).unlink()
        self.env["res.currency.rate"].create([
            {"company_id": company.root_id.id, "currency_id": source.id,
             "name": fields.Date.today(), "rate": 1},
            {"company_id": company.root_id.id, "currency_id": target.id,
             "name": fields.Date.today(), "rate": 1.2},
        ])
        self.main_pos_config.write({"restrict_price_control": True, "use_pricelist": False, "pricelist_id": False})
        method = TestRevolutVerifiedCheckout._configure_revolut_checkout(self)
        shared = self.env["product.product"].create({
            "name": "Shared currency choice", "company_id": False, "list_price": 0,
            "available_in_pos": True, "taxes_id": [Command.clear()],
        })
        combo = self.env["product.combo"].create({
            "name": "Shared currency quantity choice", "company_id": company.id,
            "qty_free": 1, "qty_max": 2 if extra_quantity else 1,
            "combo_item_ids": [Command.create({"product_id": shared.id, "extra_price": 1})],
        })
        parent = self.env["product.product"].create({
            "name": "Shared currency quantity combo" if extra_quantity else "Shared currency ordinary combo",
            "company_id": company.id,
            "type": "combo", "list_price": 10, "available_in_pos": True,
            "taxes_id": [Command.clear()], "combo_ids": [Command.set(combo.ids)],
        })
        self.assertEqual(shared.currency_id, source)
        self.assertEqual(combo.combo_item_ids.currency_id, source)
        self.assertNotEqual(source, self.main_pos_config.currency_id)
        self.env.flush_all()
        return method, parent, shared, combo.combo_item_ids, source

    def test_shared_combo_source_currency_is_loaded_and_matches_authorized_amount(self):
        method, parent, shared, item, source = self._configure_shared_currency_combo()
        session = self.main_pos_config.current_session_id
        order = self.env["pos.order"].create({
            "session_id": session.id, "uuid": str(uuid4()), "pricelist_id": False,
            "amount_total": 12.4, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({"uuid": str(uuid4()), "product_id": parent.id, "qty": 1,
                "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0, "tax_ids": [Command.clear()]})],
        })
        parent_line = order.lines
        order.write({"lines": [Command.create({
            "uuid": str(uuid4()), "product_id": shared.id, "qty": 1, "price_unit": price,
            "price_subtotal": price, "price_subtotal_incl": price,
            "combo_parent_id": parent_line.id, "combo_item_id": item.id,
            "tax_ids": [Command.clear()],
        }) for price in (11.2, 1.2)]})
        self.env.flush_all()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            authority = self.env["pos.order"].revolut_prepare_payment(order.id, order.uuid, 0, [{
                "uuid": str(uuid4()), "payment_method_id": method.id, "amount": 12.4,
            }])
            provider.assert_not_called()
        self.assertEqual(authority["canonical"]["total_minor"], 1240)
        self.assertFalse(authority["canonical"]["approval_required"])
        loaded = session.with_user(self.pos_user).load_data([], only_data=True)
        loaded_item = next(row for row in loaded["product.combo.item"]["data"] if row["id"] == item.id)
        self.assertEqual(loaded_item.get("currency_id"), source.id)
        self.assertIn(source.id, [row["id"] for row in loaded["res.currency"]["data"]])

    def test_shared_combo_source_currency_matches_native_cash_display_and_persistence(self):
        _, parent, shared, _, _ = self._configure_shared_currency_combo()
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_combo_shared_currency_cash")
            provider.assert_not_called()
        self.env.invalidate_all()
        order = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.amount_total, 12.4)
        self.assertEqual(order.amount_paid, 12.4)
        self.assertEqual(order.payment_ids.payment_method_id.name, "Cash")
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == parent).price_unit, 0)
        self.assertEqual(sorted(order.lines.filtered(lambda line: line.product_id == shared).mapped("price_unit")), [1.2, 11.2])

    def test_ordinary_shared_currency_combo_keeps_server_price_control(self):
        method, parent, shared, item, _ = self._configure_shared_currency_combo(extra_quantity=False)
        session = self.main_pos_config.current_session_id
        order = self.env["pos.order"].create({
            "session_id": session.id, "uuid": str(uuid4()), "pricelist_id": False,
            "amount_total": 11.2, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({"uuid": str(uuid4()), "product_id": parent.id, "qty": 1,
                "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0, "tax_ids": [Command.clear()]})],
        })
        order.write({"lines": [Command.create({
            "uuid": str(uuid4()), "product_id": shared.id, "qty": 1, "price_unit": 11.2,
            "price_subtotal": 11.2, "price_subtotal_incl": 11.2, "price_type": "original",
            "combo_parent_id": order.lines.id, "combo_item_id": item.id, "tax_ids": [Command.clear()],
        })]})
        tender_uuid = str(uuid4())
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            prepared = self.env["pos.order"].revolut_prepare_payment(order.id, order.uuid, 0, [{
                "uuid": tender_uuid, "payment_method_id": method.id, "amount": 11.2,
            }])
            self.assertEqual(prepared["canonical"]["total_minor"], 1120)
            self.assertFalse(prepared["canonical"]["approval_required"])
            # An original label cannot authorize a real price override.
            order.lines.filtered("combo_parent_id").write({
                "price_unit": 11, "price_subtotal": 11, "price_subtotal_incl": 11,
            })
            order.amount_total = 11
            overridden = self.env["pos.order"].revolut_prepare_payment(order.id, order.uuid, 0, [{
                "uuid": tender_uuid, "payment_method_id": method.id, "amount": 11,
            }])
            self.assertEqual(overridden["status"], "approval_required")
            provider.assert_not_called()

    def test_ordinary_shared_currency_combo_matches_native_cash_display_and_persistence(self):
        _, parent, shared, _, _ = self._configure_shared_currency_combo(extra_quantity=False)
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_combo_ordinary_shared_currency_cash")
            provider.assert_not_called()
        self.env.invalidate_all()
        order = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.amount_total, 11.2)
        self.assertEqual(order.amount_paid, 11.2)
        self.assertEqual(order.payment_ids.amount, 11.2)
        self.assertEqual(order.payment_ids.payment_method_id.name, "Cash")
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == parent).price_unit, 0)
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == shared).price_unit, 11.2)

    def _configure_combo(self, *, extra_quantity):
        method = TestRevolutVerifiedCheckout._configure_revolut_checkout(self)
        first, second = self.env["product.product"].create([
            {"name": "Combo first", "list_price": 4, "available_in_pos": True,
             "taxes_id": [Command.clear()]},
            {"name": "Combo second", "list_price": 6, "available_in_pos": True,
             "taxes_id": [Command.clear()]},
        ])
        combos = self.env["product.combo"].create([
            {"name": "First choice", "qty_free": 1, "qty_max": 2 if extra_quantity else 1,
             "combo_item_ids": [Command.create({"product_id": first.id, "extra_price": 1})]},
            {"name": "Second choice", "combo_item_ids": [Command.create({"product_id": second.id})]},
        ])
        parent = self.env["product.product"].create({
            "name": "Quantity combo" if extra_quantity else "Native combo",
            "type": "combo", "list_price": 15, "available_in_pos": True,
            "taxes_id": [Command.clear()], "combo_ids": [Command.set(combos.ids)],
        })
        return method, parent, first, second

    def _verified_combo_checkout(self, method, tour, amount_minor):
        order_id = "d40466e0-2188-41d0-bebb-aa3a930663a8"
        intent_id = "4ca74d24-7b42-451a-91fb-8aca308e2630"
        payment_id = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"
        calls = []

        def response(payload):
            result = Mock(status_code=200)
            result.json.return_value = payload
            return result

        def request(verb, url, **kwargs):
            calls.append((verb, url, kwargs))
            if verb == "GET" and url.endswith("/api/terminals"):
                return response({"terminals": [{
                    "id": self.TERMINAL_ID, "location_id": self.LOCATION_ID,
                    "online": True, "operation_mode": "pos",
                }]})
            if verb == "POST" and url.endswith("/api/orders"):
                return response({"id": order_id})
            if verb == "POST" and url.endswith("/payment-intents"):
                return response({"id": intent_id, "state": "pending"})
            if verb == "GET" and "/api/payment-intents/" in url:
                return response({"id": intent_id, "order_id": order_id,
                                 "state": "completed", "payment_id": payment_id})
            if verb == "GET" and "/api/payments/" in url:
                return response({"id": payment_id, "order_id": order_id,
                                 "state": "captured", "amount": amount_minor,
                                 "currency": self.main_pos_config.currency_id.name})
            raise AssertionError(f"Unexpected Merchant request: {verb} {url}")

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
                   side_effect=request) as provider:
            install_zero_reports(self.env, provider)
            self.start_pos_tour(tour)

        self.env.invalidate_all()
        operation = self.env["pos.revolut.payment.operation"].search([
            ("payment_method_id", "=", method.id),
        ])
        self.assertEqual(len(operation), 1)
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.amount_minor, amount_minor)
        self.assertEqual(operation.revolut_payment_id, payment_id)
        order = operation.pos_order_id
        self.assertEqual(order.state, "paid")
        self.assertEqual(order.amount_total, amount_minor / 100)
        self.assertEqual(order.amount_paid, amount_minor / 100)
        self.assertEqual(order.payment_ids.amount, amount_minor / 100)
        self.assertEqual(order.payment_ids.transaction_id, payment_id)
        creates = [call for call in calls if call[0] == "POST" and call[1].endswith("/api/orders")]
        self.assertEqual(len(creates), 1)
        self.assertEqual(creates[0][2]["json"]["amount"], amount_minor)
        self.assertEqual(creates[0][2]["json"]["currency"], self.main_pos_config.currency_id.name)
        return order

    def test_extra_combo_selection_is_priced_and_verified_through_native_checkout(self):
        method, parent, first, second = self._configure_combo(extra_quantity=True)
        order = self._verified_combo_checkout(method, "pos_revolut_combo_extra_checkout", 2100)
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == parent).price_unit, 0)
        selected_first = order.lines.filtered(lambda line: line.product_id == first)
        self.assertEqual(sum(selected_first.mapped("qty")), 2)
        self.assertEqual(sorted(selected_first.mapped("price_unit")), [5, 7])
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == second).price_unit, 9)

    def test_ordinary_shared_currency_combo_is_verified_at_displayed_amount(self):
        method, parent, shared, _, _ = self._configure_shared_currency_combo(extra_quantity=False)
        order = self._verified_combo_checkout(method, "pos_revolut_combo_ordinary_shared_currency_revolut", 1120)
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == parent).price_unit, 0)
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == shared).price_unit, 11.2)

    def test_ordinary_combo_keeps_native_sequence_and_decimal_allocation(self):
        TestRevolutVerifiedCheckout._configure_revolut_checkout(self)
        self.main_pos_config.currency_id.rounding = 0.005
        self.env["decimal.precision"].search([("name", "=", "Product Price")]).digits = 3
        children = self.env["product.product"].create([
            {"name": name, "list_price": 1, "available_in_pos": True, "taxes_id": [Command.clear()]}
            for name in ("Last choice", "First choice", "Middle choice")
        ])
        combos = self.env["product.combo"].create([
            {"name": product.name, "sequence": sequence,
             "combo_item_ids": [Command.create({"product_id": product.id})]}
            for product, sequence in zip(children, (30, 10, 20))
        ])
        self.env["product.product"].create({
            "name": "Native decimal combo", "type": "combo", "list_price": 1,
            "available_in_pos": True, "taxes_id": [Command.clear()],
            "combo_ids": [Command.set(combos.ids)],
        })
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_combo_native_decimal_cash")
            provider.assert_not_called()
        self.env.invalidate_all()
        order = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.amount_total, 1.005)
        self.assertEqual(order.payment_ids.amount, 1.005)
        self.assertEqual([order.lines.filtered(lambda line: line.product_id == product).price_unit
                          for product in children], [0.333, 0.333, 0.334])

    def test_native_one_selection_combos_keep_cash_checkout(self):
        _, parent, first, second = self._configure_combo(extra_quantity=False)
        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request") as provider:
            self.start_pos_tour("pos_revolut_combo_native_cash")
            provider.assert_not_called()
        self.env.invalidate_all()
        order = self.env["pos.order"].search([
            ("session_id", "=", self.main_pos_config.current_session_id.id), ("state", "=", "paid"),
        ])
        self.assertEqual(len(order), 1)
        self.assertEqual(order.amount_total, 16)
        self.assertEqual(order.payment_ids.payment_method_id.name, "Cash")
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == parent).price_unit, 0)
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == first).price_unit, 7)
        self.assertEqual(order.lines.filtered(lambda line: line.product_id == second).price_unit, 9)

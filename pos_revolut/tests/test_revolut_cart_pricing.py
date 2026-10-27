from uuid import uuid4
from unittest.mock import patch

from odoo import Command, fields
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import new_test_user, tagged


@tagged("post_install", "-at_install")
class TestRevolutCartPricing(TestPointOfSaleCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.method = cls.bank_payment_method.copy({
            "name": "Revolut canonical pricing", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_PRICING_TEST",
        })
        cls.pos_config.write({
            "payment_method_ids": [Command.link(cls.method.id)],
            "auto_validate_terminal_payment": True,
            "tip_product_id": cls.env["product.product"].create({
                "name": "Canonical terminal tip", "list_price": 0, "taxes_id": [Command.clear()],
            }).id,
            "pricelist_id": cls.env["product.pricelist"].create({
                "name": "Canonical native pricelist", "currency_id": cls.pos_config.currency_id.id,
            }).id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Canonical pricing product", "available_in_pos": True,
            "list_price": 10, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Preparation must never call a financial provider"),
        ))
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.state = "opened"

    def tearDown(self):
        self.request.assert_not_called()
        super().tearDown()

    def test_tip_identity_does_not_depend_on_name_availability_or_browser_flags(self):
        tip = self.pos_config.tip_product_id
        tip.write({"name": "Gratuity", "available_in_pos": True})
        order = self._order(product_id=tip.id)
        self.assertFalse(order.is_tipped)
        self.assertEqual(order.tip_amount, 0)
        self.env.flush_all()
        with self.assertRaisesRegex(
            UserError, "Remove the Odoo-entered tip before using terminal-selected tips",
        ), self.env.cr.savepoint():
            self._prepare(order)

    def test_ineligible_goods_and_linked_returns_keep_generic_rejection(self):
        self.product.name = "Tips"
        for values in ({"active": False}, {"sale_ok": False}, {"available_in_pos": False}):
            with self.subTest(values=values), self.env.cr.savepoint():
                order = self._order()
                order.write({"is_tipped": True, "tip_amount": 10})
                self.product.write(values)
                self.env.flush_all()
                with self.assertRaisesRegex(UserError, "Use eligible sale products; linked returns require refund allocation"):
                    self._prepare(order)
                self.product.write({name: True for name in values})
        original = self._order()
        linked = self._order(refunded_orderline_id=original.lines.id)
        self.assertTrue(linked.is_refund)
        with self.assertRaisesRegex(
            UserError, "Select the exact original draft sale for Revolut payment",
        ), self.env.cr.savepoint():
            self._prepare(linked)

    def _order(self, price=10, **line_values):
        return self.env["pos.order"].create({
            "session_id": self.session.id, "uuid": str(uuid4()), "state": "draft",
            "amount_total": price, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "pricelist_id": self.pos_config.pricelist_id.id,
            "lines": [Command.create({
                "uuid": str(uuid4()),
                "product_id": self.product.id, "qty": 1, "price_unit": price,
                "price_subtotal": price, "price_subtotal_incl": price,
                "tax_ids": [Command.clear()], **line_values,
            })],
        })

    def _prepare(self, order, amount=10):
        # A real RPC sees a persisted draft and flushed native configuration.
        self.env.flush_all()
        return self.env["pos.order"].revolut_prepare_payment(
            order.id, order.uuid, 0,
            [{"uuid": str(uuid4()), "payment_method_id": self.method.id, "amount": amount}],
        )

    def _open_foreign_currency_without_pricelist(self):
        source = self.company.currency_id
        target = self.env.ref("base.EUR") if source != self.env.ref("base.EUR") else self.env.ref("base.USD")
        target.active = True
        self.env["res.currency.rate"].search([
            ("company_id", "=", self.company.id), ("name", "=", fields.Date.today()),
            ("currency_id", "in", (source | target).ids),
        ]).unlink()
        self.env["res.currency.rate"].create([
            {"company_id": self.company.id, "currency_id": source.id,
             "name": fields.Date.today(), "rate": 1},
            {"company_id": self.company.id, "currency_id": target.id,
             "name": fields.Date.today(), "rate": 1.2},
        ])
        journal = self.pos_config.journal_id.copy({
            "name": "Foreign currency authorization", "code": "V52FX", "currency_id": target.id,
        })
        self.pos_config = self.pos_config.copy({
            "name": "Foreign currency without pricelist", "journal_id": journal.id,
            "use_pricelist": False, "pricelist_id": False,
            "available_pricelist_ids": [Command.clear()],
            "revolut_user_ids": [Command.set(self.env.user.ids)],
        })
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.state = "opened"
        self.env.flush_all()
        return self.session.load_data([], only_data=True)

    def test_foreign_currency_without_pricelist_matches_native_loaded_price(self):
        loaded = self._open_foreign_currency_without_pricelist()
        self.assertFalse(loaded["pos.config"]["data"][0]["pricelist_id"])
        product = next(row for row in loaded["product.product"]["data"] if row["id"] == self.product.id)
        self.assertEqual(product["lst_price"], 12)
        order = self._order(price=12)
        self.assertFalse(order.pricelist_id)
        result = self._prepare(order, amount=10)
        self.assertEqual(result["canonical"]["total_minor"], 1200)
        self.assertFalse(result["canonical"]["approval_required"])

    def test_foreign_currency_native_attribute_extra_retains_price_control(self):
        attribute = self.env["product.attribute"].create({"name": "Foreign currency extra", "create_variant": "no_variant"})
        value = self.env["product.attribute.value"].create({"name": "Selected", "attribute_id": attribute.id})
        self.product.product_tmpl_id.with_context(create_product_product=True).write({
            "attribute_line_ids": [Command.create({"attribute_id": attribute.id, "value_ids": [Command.set(value.ids)]})],
        })
        selected = self.product.product_tmpl_id.attribute_line_ids.product_template_value_ids
        selected.price_extra = 2
        loaded = self._open_foreign_currency_without_pricelist()
        product = next(row for row in loaded["product.product"]["data"] if row["id"] == self.product.id)
        extra = next(row for row in loaded["product.template.attribute.value"]["data"] if row["id"] == selected.id)
        self.assertEqual(product["lst_price"], 12)
        self.assertEqual(extra["price_extra"], 2)
        self.pos_config.restrict_price_control = True
        native = self._order(price=14, price_extra=2, attribute_value_ids=[Command.set(selected.ids)])
        result = self._prepare(native, amount=10)
        self.assertEqual(result["canonical"]["total_minor"], 1400)
        self.assertFalse(result["canonical"]["approval_required"])
        override = self._order(price=13, price_type="manual", price_extra=2,
                               attribute_value_ids=[Command.set(selected.ids)])
        approval = self._prepare(override, amount=10)
        self.assertEqual(approval["status"], "approval_required")
        self.assertEqual(approval["canonical"]["total_minor"], 1300)

    def test_native_ordinary_price_and_manual_discount(self):
        result = self._prepare(self._order(discount=20), amount=8)
        self.assertEqual(result["canonical"]["total_minor"], 800)
        self.assertFalse(result["canonical"]["approval_required"])

    def test_required_checkout_context_and_pickup_time_block_preparation(self):
        preset = self.env["pos.preset"].create({"name": "Required pickup context"})
        self.pos_config.write({"use_presets": True, "available_preset_ids": [Command.set(preset.ids)]})
        order = self._order()
        with self.assertRaisesRegex(UserError, "Select an available checkout preset"):
            self._prepare(order)
        order.preset_id = preset
        calendar = self.env["resource.calendar"].create({
            "name": "Required pickup opening hours", "tz": "UTC",
        })
        preset.write({"use_timing": True, "resource_calendar_id": calendar.id})
        with self.assertRaisesRegex(UserError, "select an available pickup time slot"):
            self._prepare(order)

    def test_unavailable_return_and_foreign_presets_cannot_authorize_sale_pricing(self):
        self.pos_config.use_presets = True
        preset = self.env["pos.preset"].create({"name": "Unselected checkout context"})
        order = self._order()
        order.preset_id = preset
        with self.assertRaisesRegex(UserError, "Select an available sale preset"):
            self._prepare(order)
        self.pos_config.available_preset_ids = preset
        preset.is_return = True
        with self.assertRaisesRegex(UserError, "Select an available sale preset"):
            self._prepare(order)
        preset.is_return = False
        self.assertEqual(self._prepare(order)["canonical"]["total_minor"], 1000)
        preset.company_id = self.env["res.company"].create({"name": "Other preset company"})
        with self.assertRaisesRegex(UserError, "Select an available sale preset"):
            self._prepare(order)

    def test_unrestricted_manual_price_preserved(self):
        result = self._prepare(self._order(price=7, price_type="manual"), amount=7)
        self.assertEqual(result["canonical"]["total_minor"], 700)
        self.assertFalse(result["canonical"]["approval_required"])

    def test_restricted_original_label_does_not_authorize_override(self):
        self.pos_config.restrict_price_control = True
        result = self._prepare(self._order(price=7, price_type="original"), amount=7)
        self.assertEqual(result["status"], "approval_required")

    def test_product_tax_is_derived_instead_of_submitted(self):
        tax = self.env["account.tax"].create({
            "name": "Canonical 20 percent", "amount": 20, "amount_type": "percent",
            "company_id": self.company.id,
        })
        self.product.taxes_id = tax
        result = self._prepare(self._order(), amount=12)
        self.assertEqual(result["canonical"]["total_minor"], 1200)
        self.assertEqual(result["status"], "review_required")
        self.assertEqual(result["canonical"]["snapshot"]["lines"][0]["tax_ids"], [tax.id])

    def test_invalid_discount_and_existing_odoo_tip_rejected(self):
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._prepare(self._order(discount=101))
        tip = self.pos_config.tip_product_id
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._prepare(self._order(product_id=tip.id))

    def test_native_odoo_tip_explains_removal_before_product_eligibility(self):
        tip = self.env.ref("point_of_sale.product_product_tip")
        self.assertTrue(tip.active)
        self.assertFalse(tip.available_in_pos)
        self.pos_config.tip_product_id = tip
        order = self._order()
        order.write({
            "amount_total": 11, "is_tipped": True, "tip_amount": 1,
            "lines": [Command.create({
                "uuid": str(uuid4()),
                "product_id": tip.id, "qty": 1, "price_unit": 1,
                "price_subtotal": 1, "price_subtotal_incl": 1,
                "tax_ids": [Command.clear()],
            })],
        })
        with self.assertRaisesRegex(
            UserError, "Remove the Odoo-entered tip before using terminal-selected tips",
        ), self.env.cr.savepoint():
            self._prepare(order, amount=11)
        self.request.assert_not_called()

    def test_fixed_percentage_formula_and_quantity_pricelist_prices(self):
        pricelist = self.pos_config.pricelist_id
        for rule, expected in (
            ({"compute_price": "fixed", "fixed_price": 6}, 6),
            ({"compute_price": "percentage", "percent_price": 25}, 7.5),
            ({"compute_price": "formula", "base": "list_price", "price_discount": 10,
              "price_surcharge": 0.5}, 9.5),
        ):
            with self.subTest(rule=rule), self.env.cr.savepoint():
                item = self.env["product.pricelist.item"].create({
                    "pricelist_id": pricelist.id, "applied_on": "0_product_variant",
                    "product_id": self.product.id, **rule,
                })
                result = self._prepare(self._order(), amount=expected)
                self.assertEqual(result["canonical"]["total_minor"], round(expected * 100))
                self.assertEqual(result["status"], "review_required")
                item.unlink()
        self.env["product.pricelist.item"].create({
            "pricelist_id": pricelist.id, "applied_on": "0_product_variant",
            "product_id": self.product.id, "compute_price": "fixed", "fixed_price": 6,
            "min_quantity": 2,
        })
        result = self._prepare(self._order(qty=2), amount=12)
        self.assertEqual(result["canonical"]["total_minor"], 1200)

    def test_lot_quantity_tier_aggregates_native_separate_lines(self):
        self.product.tracking = "lot"
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pos_config.pricelist_id.id,
            "applied_on": "0_product_variant", "product_id": self.product.id,
            "compute_price": "fixed", "fixed_price": 6, "min_quantity": 2,
        })
        order = self._order()
        order.lines.copy({"order_id": order.id, "uuid": str(uuid4())})
        result = self._prepare(order, amount=12)
        self.assertEqual(result["canonical"]["total_minor"], 1200)
        self.assertEqual([line["price_unit"] for line in result["canonical"]["snapshot"]["lines"]], ["6", "6"])

    def test_included_tax_fiscal_mapping_preserves_native_price(self):
        included = self.env["account.tax"].create({
            "name": "Included twenty", "amount": 20, "amount_type": "percent",
            "company_id": self.company.id, "price_include_override": "tax_included",
        })
        excluded = included.copy({"name": "Excluded twenty", "price_include_override": "tax_excluded"})
        fiscal = self.env["account.fiscal.position"].create({
            "name": "Canonical fiscal mapping", "company_id": self.company.id,
            "tax_ids": [Command.create({"tax_src_id": included.id, "tax_dest_id": excluded.id})],
        })
        self.pos_config.write({"tax_regime_selection": True, "fiscal_position_ids": [Command.link(fiscal.id)]})
        self.product.write({"list_price": 12, "taxes_id": [Command.set(included.ids)]})
        order = self._order(price=12)
        order.fiscal_position_id = fiscal
        result = self._prepare(order, amount=12)
        self.assertEqual(result["canonical"]["total_minor"], 1200)
        self.assertEqual(result["canonical"]["snapshot"]["lines"][0]["price_unit"], "10")

    def test_no_variant_extra_derived_and_foreign_attributes_rejected(self):
        attribute = self.env["product.attribute"].create({"name": "Canonical extra", "create_variant": "no_variant"})
        value = self.env["product.attribute.value"].create({"name": "Selected", "attribute_id": attribute.id})
        self.product.product_tmpl_id.with_context(create_product_product=True).write({
            "attribute_line_ids": [Command.create({"attribute_id": attribute.id, "value_ids": [Command.set(value.ids)]})],
        })
        selected = self.product.product_tmpl_id.attribute_line_ids.product_template_value_ids
        selected.price_extra = 2
        result = self._prepare(self._order(attribute_value_ids=[Command.set(selected.ids)], price_extra=99), amount=12)
        self.assertEqual(result["canonical"]["total_minor"], 1200)
        self.assertEqual(result["canonical"]["contents"][0]["price_extra"], 2)
        other = self.env["product.product"].create({"name": "Other template", "available_in_pos": True})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._prepare(self._order(product_id=other.id, attribute_value_ids=[Command.set(selected.ids)]))

    def test_native_combo_proration_and_extra_selection(self):
        first = self.env["product.product"].create({"name": "Combo first", "list_price": 4,
                                                    "available_in_pos": True, "taxes_id": [Command.clear()]})
        second = self.env["product.product"].create({"name": "Combo second", "list_price": 6,
                                                     "available_in_pos": True, "taxes_id": [Command.clear()]})
        combos = self.env["product.combo"].create([
            {"name": "First choice", "qty_free": 1, "qty_max": 2,
             "combo_item_ids": [Command.create({"product_id": first.id, "extra_price": 1})]},
            {"name": "Second choice", "combo_item_ids": [Command.create({"product_id": second.id})]},
        ])
        parent = self.env["product.product"].create({"name": "Combo", "type": "combo", "list_price": 15,
                                                   "available_in_pos": True, "taxes_id": [Command.clear()],
                                                   "combo_ids": [Command.set(combos.ids)]})
        order = self._order(price=0, product_id=parent.id)
        parent_line = order.lines
        for combo, qty in zip(combos, (2, 1)):
            item = combo.combo_item_ids
            order.write({"lines": [Command.create({
                "uuid": str(uuid4()),
                "product_id": item.product_id.id, "qty": qty, "price_unit": 1,
                "price_subtotal": qty, "price_subtotal_incl": qty,
                "combo_parent_id": parent_line.id, "combo_item_id": item.id,
            })]})
        result = self._prepare(order, amount=21)
        self.assertEqual(result["canonical"]["total_minor"], 2100)
        self.assertEqual(result["status"], "review_required")

    def test_native_ordinary_combo_uses_decimal_precision_and_native_selection_order(self):
        self.pos_config.currency_id.rounding = 0.005
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
        parent = self.env["product.product"].create({
            "name": "Native rounding combo", "type": "combo", "list_price": 1,
            "available_in_pos": True, "taxes_id": [Command.clear()],
            "combo_ids": [Command.set(combos.ids)],
        })
        order = self._order(price=0, product_id=parent.id)
        for combo in combos:
            order.write({"lines": [Command.create({
                "uuid": str(uuid4()), "product_id": combo.combo_item_ids.product_id.id,
                "qty": 1, "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0,
                "combo_parent_id": order.lines.filtered(lambda line: line.product_id == parent).id,
                "combo_item_id": combo.combo_item_ids.id, "tax_ids": [Command.clear()],
            })]})
        result = self._prepare(order, amount=1.005)
        # Native tax lines round each 0.333/0.334 allocation to 0.335 at
        # this currency quantum, while combo unit prices retain 3 decimals.
        self.assertEqual(result["canonical"]["total_minor"], 1005)
        self.assertEqual([order.lines.filtered(lambda line: line.product_id == product).price_unit
                          for product in children], [0.333, 0.333, 0.334])

    def test_combo_quantity_configuration_rejects_invalid_free_or_maximum_bounds(self):
        combo = self.env["product.combo"].create({
            "name": "Bounded native combo", "combo_item_ids": [Command.create({"product_id": self.product.id})],
        })
        self.assertEqual((combo.qty_free, combo.qty_max), (1, 1))
        for values in ({"qty_max": 0}, {"qty_free": -1}, {"qty_free": 2}):
            with self.subTest(values=values), self.assertRaises(ValidationError), self.env.cr.savepoint():
                combo.write(values)

    def test_terminal_tip_precision_preflight_rejects_unrepresentable_tax(self):
        tax = self.env["account.tax"].create({
            "name": "Tip twenty", "amount": 20, "amount_type": "percent", "company_id": self.company.id,
        })
        self.pos_config.tip_product_id.taxes_id = tax
        precision = self.env["decimal.precision"].search([("name", "=", "Product Price")])
        precision.digits = 2
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self._prepare(self._order())
        precision.digits = 4
        result = self._prepare(self._order())
        self.assertEqual(result["canonical"]["total_minor"], 1000)

    def test_manager_approval_is_exact_and_price_edit_revokes_it(self):
        self.pos_config.restrict_price_control = True
        manager = new_test_user(self.env, login="canonical_pricing_manager",
                                groups="point_of_sale.group_pos_manager",
                                company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        self.pos_config.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
        order = self._order(price=7, price_type="manual")
        prepared = self._prepare(order, amount=7)
        self.assertEqual(prepared["status"], "approval_required")
        approved = self.env["pos.order"].with_user(manager).revolut_approve_cart(
            order.id, order.uuid, prepared["cart_version"],
        )
        self.assertEqual(approved["status"], "prepared")
        order.lines.write({"price_unit": 6, "price_subtotal": 6, "price_subtotal_incl": 6})
        revised = self._prepare(order, amount=6)
        self.assertGreater(revised["cart_version"], prepared["cart_version"])
        self.assertTrue(revised["canonical"]["approval_required"])

    def test_negative_sale_line_preserved_with_positive_goods_balance(self):
        order = self._order(price=10)
        order.write({"lines": [Command.create({
            "uuid": str(uuid4()),
            "product_id": self.product.id, "qty": -0.1, "price_unit": 10,
            "price_subtotal": -1, "price_subtotal_incl": -1, "tax_ids": [Command.clear()],
        })]})
        self.product.uom_id.rounding = 0.01
        result = self._prepare(order, amount=9)
        self.assertEqual(result["canonical"]["total_minor"], 900)

    def test_nested_pricelist_and_no_pricelist_native_defaults(self):
        base = self.env["product.pricelist"].create({
            "name": "Nested base", "currency_id": self.pos_config.currency_id.id,
            "item_ids": [Command.create({"applied_on": "0_product_variant", "product_id": self.product.id,
                                          "compute_price": "fixed", "fixed_price": 8})],
        })
        self.env["product.pricelist.item"].create({
            "pricelist_id": self.pos_config.pricelist_id.id, "applied_on": "0_product_variant",
            "product_id": self.product.id, "compute_price": "formula", "base": "pricelist",
            "base_pricelist_id": base.id, "price_discount": 25,
        })
        result = self._prepare(self._order(), amount=6)
        self.assertEqual(result["canonical"]["total_minor"], 600)
        self.pos_config.pricelist_id = False
        result = self._prepare(self._order(), amount=10)
        self.assertEqual(result["canonical"]["total_minor"], 1000)

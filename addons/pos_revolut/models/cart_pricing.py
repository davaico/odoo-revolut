"""Canonical native POS prices; called only inside cart preparation's lock."""

from decimal import Decimal
from uuid import uuid4

from odoo import _, Command, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round

from .financial_snapshot import check_line_count_size, decimal_text, normalize_snapshot


def _stamp(records):
    return [[record.id, record.write_date.isoformat() if record.write_date else False]
            for record in records.sorted("id")]


class PosOrderCartPricing(models.Model):
    _inherit = "pos.order"

    def _revolut_pricing_identity(self):
        self.ensure_one()
        self.check_access("write")
        config = self.session_id.config_id
        if (self.state != "draft" or self.is_refund or self.session_id.state != "opened"
                or self.company_id not in self.env.companies
                or self.company_id != self.session_id.company_id
                or self.config_id != config or self.currency_id != self.session_id.currency_id):
            raise UserError(_("Prepare an open draft sale in its original POS session."))
        if self.pricelist_id and self.pricelist_id not in config._get_available_pricelists():
            raise UserError(_("Select a pricelist available in this Point of Sale."))
        if (self.pricelist_id and (self.pricelist_id.company_id and self.pricelist_id.company_id != self.company_id
                or self.pricelist_id.currency_id != self.currency_id)):
            raise UserError(_("The cart pricelist company or currency is invalid."))
        presets = config.available_preset_ids | config.default_preset_id
        if self.preset_id and (self.preset_id not in presets or self.preset_id.is_return):
            raise UserError(_("Select an available sale preset before Revolut payment."))
        allowed_fiscal = config.fiscal_position_ids | config.default_fiscal_position_id
        if self.partner_id:
            allowed_fiscal |= self.env["account.fiscal.position"]._get_fiscal_position(self.partner_id)
        if self.preset_id:
            allowed_fiscal |= self.preset_id.fiscal_position_id
        if self.fiscal_position_id and (self.fiscal_position_id not in allowed_fiscal
                or self.fiscal_position_id.company_id != self.company_id):
            raise UserError(_("Select an authorized fiscal position for this cart."))
        # Native non-company currencies derive this rate from the company;
        # readonly on the browser field does not make it authoritative.
        rate = self.env["res.currency"]._get_conversion_rate(
            self.company_id.currency_id, self.currency_id, self.company_id,
            self.date_order.date(),
        )
        if float_compare(self.currency_rate, rate, precision_digits=12):
            raise UserError(_("The cart currency rate changed; reload the order before payment."))
        return config

    def _revolut_line_attributes(self, line):
        product = line.product_id
        selected = line.attribute_value_ids
        if len(selected) > 100 or len(line.custom_attribute_value_ids) > 100:
            raise UserError(_("Reduce the selected attributes before preparing payment."))
        if any(value.product_tmpl_id != product.product_tmpl_id or not value.ptav_active for value in selected):
            raise UserError(_("The selected product attributes are invalid."))
        variants = product.product_template_attribute_value_ids
        if any(value.attribute_id.create_variant != "no_variant" and value not in variants for value in selected):
            raise UserError(_("The selected attributes do not belong to the product variant."))
        combination = variants | selected
        if not product.product_tmpl_id._is_combination_possible(combination):
            raise UserError(_("Select a valid product attribute combination before payment."))
        if any(custom.custom_product_template_attribute_value_id not in combination
               or not custom.custom_product_template_attribute_value_id.is_custom
               for custom in line.custom_attribute_value_ids):
            raise UserError(_("The custom product attribute selection is invalid."))
        extra = sum(value.price_extra for value in selected
                    if value.attribute_id.create_variant != "always")
        return combination, extra

    def _revolut_automatic_price(self, line, extra, pricing_time, quantity=None):
        product = line.product_id.with_company(self.company_id).with_context(
            no_variant_attributes_price_extra=extra,
        )
        quantity = line.qty if quantity is None else quantity
        if product.tracking == "lot" and not line.combo_parent_id:
            quantity = sum(self.lines.filtered(lambda sibling: sibling.product_id == line.product_id).mapped("qty"))
        return self.pricelist_id.with_company(self.company_id)._get_product_price(
            product, quantity, uom=product.uom_id, date=pricing_time, currency=self.currency_id,
        )

    def _revolut_combo_prices(self, extras, pricing_time, precision):
        """Port the pinned computeComboItems allocation; all inputs are server records.

        The configurator consumes free selections by combo/item ID and allocates
        the parent's price in that order, with the last included unit receiving
        the rounding remainder. Split differing price chunks just as the native
        configurator does, retaining attributes for canonical review.
        """
        prices, splits = {}, []
        for parent in self.lines.filtered(lambda line: line.product_id.type == "combo"):
            if parent.combo_parent_id or not parent.qty or not parent.combo_line_ids:
                raise UserError(_("The combo parent and selected items are incomplete."))
            combos = parent.product_id.combo_ids
            children = parent.combo_line_ids.sorted(lambda line: (line.combo_item_id.combo_id.id, line.combo_item_id.id, line.id))
            included, additional = [], []
            for combo in combos:
                selections = children.filtered(lambda line: line.combo_item_id.combo_id == combo)
                count = sum(line.qty / parent.qty for line in selections)
                if count < combo.qty_free or count > combo.qty_max:
                    raise UserError(_("The selected combo quantities are outside its allowed range."))
                free = combo.qty_free
                for child in selections:
                    quantity = child.qty / parent.qty
                    if quantity <= 0 or float_compare(quantity, round(quantity), precision_digits=8):
                        raise UserError(_("Combo item quantities must be whole selections per parent."))
                    if (child.combo_item_id.product_id != child.product_id
                            or child.combo_item_id.combo_id not in combos
                            or child.combo_item_id.company_id and child.combo_item_id.company_id != self.company_id):
                        raise UserError(_("The selected combo item does not belong to this product."))
                    free_quantity = min(free, quantity)
                    if free_quantity:
                        included.append((child, free_quantity))
                        free -= free_quantity
                    if quantity > free_quantity:
                        extra_child = child
                        if free_quantity:
                            extra_child = self._revolut_copy_combo_selection(child, (quantity - free_quantity) * parent.qty)
                            child.qty = free_quantity * parent.qty
                            extras[extra_child.id] = extras[child.id]
                            splits.append({"uuid": child.uuid, "qty": child.qty,
                                           "created_uuid": extra_child.uuid, "created_qty": extra_child.qty})
                        additional.append((extra_child, quantity - free_quantity))
            if any(child.combo_item_id.combo_id not in combos for child in children):
                raise UserError(_("The cart contains a foreign combo item."))
            if included and included[-1][1] > 1 and parent.qty == 1:
                child, quantity = included[-1]
                last = self._revolut_copy_combo_selection(child, 1)
                child.qty -= 1
                extras[last.id] = extras[child.id]
                included[-1] = (child, quantity - 1)
                included.append((last, 1))
                splits.append({"uuid": child.uuid, "qty": child.qty,
                               "created_uuid": last.uuid, "created_qty": 1})
            children = parent.combo_line_ids
            parent_price = self._revolut_automatic_price(parent, 0, pricing_time, quantity=1)
            denominator = sum(child.combo_item_id.combo_id.currency_id._convert(
                child.combo_item_id.combo_id.base_price, self.currency_id, self.company_id, pricing_time,
                round=False,
            ) * quantity for child, quantity in included)
            remaining = parent_price
            totals = {child.id: 0 for child in children}
            for index, (child, quantity) in enumerate(included):
                base = child.combo_item_id.combo_id.currency_id._convert(
                    child.combo_item_id.combo_id.base_price, self.currency_id, self.company_id,
                    pricing_time, round=False,
                )
                unit = self.currency_id.round(base * parent_price / denominator) if denominator else 0
                contribution = unit * quantity
                remaining -= contribution
                if index == len(included) - 1:
                    contribution += remaining
                    remaining = 0
                totals[child.id] += contribution
            extra_denominator = sum(child.combo_item_id.combo_id.base_price * quantity
                                    for child, quantity in additional)
            for index, (child, quantity) in enumerate(additional):
                base = child.combo_item_id.combo_id.currency_id._convert(
                    child.combo_item_id.combo_id.base_price, self.currency_id, self.company_id,
                    pricing_time, round=False,
                )
                unit = self.currency_id.round(base)
                if remaining and extra_denominator:
                    share = self.currency_id.round(base * parent_price / extra_denominator)
                    unit += share
                    remaining -= share * quantity
                    if index == len(additional) - 1:
                        unit += remaining / quantity
                        remaining = 0
                totals[child.id] += unit * quantity
            for child in children:
                quantity = child.qty / parent.qty
                extra = child.combo_item_id.currency_id._convert(
                    child.combo_item_id.extra_price, self.currency_id, self.company_id, pricing_time,
                    round=False,
                )
                prices[child.id] = totals[child.id] / quantity + extras[child.id] + extra
            prices[parent.id] = 0
        if any(line.combo_item_id and not line.combo_parent_id for line in self.lines):
            raise UserError(_("A combo item is missing its parent product."))
        return prices, splits

    def _revolut_copy_combo_selection(self, line, quantity):
        check_line_count_size(len(self.lines) + 1)
        return line.copy({
            "qty": quantity, "uuid": str(uuid4()),
            "custom_attribute_value_ids": [Command.create({
                "custom_product_template_attribute_value_id": value.custom_product_template_attribute_value_id.id,
                "custom_value": value.custom_value,
            }) for value in line.custom_attribute_value_ids],
        })

    def _revolut_terminal_tip_values(self, tip_minor):
        """Return a native tip price whose tax-inclusive amount is exactly paid."""
        self.ensure_one()
        product = self.config_id.tip_product_id
        if not product or not product.active or product.company_id and product.company_id != self.company_id:
            raise UserError(_("Configure a valid terminal tip product before Revolut payment."))
        taxes = product.taxes_id.filtered(lambda tax: tax.company_id == self.company_id)
        mapped = self.fiscal_position_id.map_tax(taxes)
        flattened = mapped.flatten_taxes_hierarchy()
        if any(tax.amount_type not in {"percent", "division"} or tax.amount < 0
               or tax.amount_type == "division" and tax.amount >= 100 for tax in flattened):
            raise UserError(_("Terminal tips require nonnegative proportional taxes; review the tip product configuration."))
        precision = self.env["decimal.precision"].precision_get("Product Price")
        slope = mapped._get_tax_details(
            price_unit=1, quantity=1, precision_rounding=self.currency_id.rounding,
            rounding_method="round_globally", product=product,
        )["total_included"]
        quantum = 10 ** -precision
        if slope <= 0 or slope * quantum > self.currency_id.rounding + 1e-12:
            raise UserError(_("Increase Product Price precision so collected terminal tips can be represented exactly."))
        gross = float(Decimal(tip_minor) / (Decimal(10) ** self.currency_id.decimal_places))
        candidate = float_round(gross / slope, precision_digits=precision)
        tax_model = self.env["account.tax"]
        goods = self.lines.filtered(lambda line: line.product_id != product)

        def cart_total(price=None):
            base_lines = goods._prepare_tax_base_line_values()
            if price is not None:
                base_lines.append(tax_model._prepare_base_line_for_taxes_computation(
                    {}, currency_id=self.currency_id, rate=self.currency_rate,
                    product_id=product, tax_ids=mapped, price_unit=price, quantity=1, discount=0,
                ))
            tax_model._add_tax_details_in_base_lines(base_lines, self.company_id)
            tax_model._round_base_lines_tax_details(base_lines, self.company_id)
            return tax_model._get_tax_totals_summary(
                base_lines=base_lines, currency=self.currency_id, company=self.company_id,
                cash_rounding=None,
            )["total_amount_currency"]

        target = cart_total() + gross
        # Global tax rounding can shift the contribution relative to a tip
        # considered alone. Solve the complete cart's incremental total using
        # native base-line calculation, retaining the same frozen goods lines.
        margin = self.currency_id.rounding * (len(flattened) + 2) / slope
        low, high = max(0, candidate - margin), candidate + margin
        for _attempt in range(64):
            price = float_round(candidate, precision_digits=precision)
            comparison = self.currency_id.compare_amounts(cart_total(price), target)
            if comparison == 0:
                result = self.env["pos.order.line"].new({
                    "order_id": self.id, "product_id": product.id, "qty": 1,
                    "price_unit": price, "discount": 0, "tax_ids": [Command.set(taxes.ids)],
                })._compute_amount_line_all()
                return {"product_id": product.id, "qty": 1, "price_unit": price,
                        "discount": 0, "tax_ids": [Command.set(taxes.ids)],
                        "price_subtotal": result["price_subtotal"], "price_subtotal_incl": result["price_subtotal_incl"]}
            if comparison < 0:
                low = price + quantum
            else:
                high = price - quantum
            if high < low:
                break
            candidate = (low + high) / 2
        raise UserError(_("The configured tip taxes cannot represent the collected amount exactly."))

    def _revolut_price_cart(self):
        self.ensure_one()
        config = self._revolut_pricing_identity()
        check_line_count_size(len(self.lines))
        if not self.lines:
            raise UserError(_("Add sale products before preparing Revolut payment."))
        # Existing domain validation bounds numeric text before native arithmetic.
        normalize_snapshot(self._revolut_order_values(), native_order=True)
        precision = self.env["decimal.precision"].precision_get("Product Price")
        pricing_time = fields.Datetime.now()
        extras, attributes = {}, {}
        for line in self.lines:
            product = line.product_id
            if (not product.active or not product.sale_ok or not product.available_in_pos
                    or product.company_id and product.company_id != self.company_id
                    or line.refunded_orderline_id):
                raise UserError(_("Use eligible sale products; linked returns require refund allocation."))
            if product == config.tip_product_id:
                raise UserError(_("Remove the Odoo-entered tip before using terminal-selected tips."))
            if not 0 <= line.discount <= 100 or line.discount and not config.manual_discount:
                raise UserError(_("Use an enabled line discount between zero and 100 percent."))
            if float_compare(line.qty, float_round(line.qty, precision_rounding=product.uom_id.rounding), precision_digits=8):
                raise UserError(_("The product quantity exceeds its unit-of-measure precision."))
            attributes[line.id], extras[line.id] = self._revolut_line_attributes(line)
        combo_prices, corrections = self._revolut_combo_prices(extras, pricing_time, precision)
        for line in self.lines:
            if line.id not in attributes:
                attributes[line.id], extras[line.id] = self._revolut_line_attributes(line)
        contents, approval_required = [], False
        tax_model = self.env["account.tax"]
        for line in self.lines.sorted("id"):
            original = {"price_unit": line.price_unit, "price_extra": line.price_extra,
                        "tax_ids": sorted(line.tax_ids.ids), "price_subtotal": line.price_subtotal,
                        "price_subtotal_incl": line.price_subtotal_incl}
            taxes = line.product_id.taxes_id.filtered(lambda tax: tax.company_id == self.company_id)
            mapped = self.fiscal_position_id.map_tax(taxes)
            automatic = combo_prices.get(line.id)
            if automatic is None:
                automatic = self._revolut_automatic_price(line, extras[line.id], pricing_time)
            automatic = tax_model._fix_tax_included_price_company(automatic, taxes, mapped, self.company_id)
            automatic = float_round(automatic, precision_digits=precision)
            deviation = bool(float_compare(line.price_unit, automatic, precision_digits=precision))
            manual = deviation and (config.restrict_price_control or line.price_type == "manual")
            approval_required |= bool(config.restrict_price_control and deviation)
            price = float_round(line.price_unit if manual else automatic, precision_digits=precision)
            line.write({"price_unit": price, "price_extra": extras[line.id],
                        "tax_ids": [Command.set(taxes.ids)], "extra_tax_data": False})
            amounts = line._compute_amount_line_all()
            line.write(amounts)
            canonical = {"uuid": line.uuid, "price_unit": price, "price_extra": extras[line.id],
                         "tax_ids": sorted(taxes.ids), **amounts}
            changed = any(original[name] != canonical[name] for name in original)
            if changed:
                corrections.append(canonical)
            contents.append({**canonical, "product_id": line.product_id.id, "qty": line.qty,
                             "discount": line.discount, "attribute_value_ids": sorted(attributes[line.id].ids),
                             "custom_attributes": [[value.custom_product_template_attribute_value_id.id, value.custom_value]
                                                   for value in line.custom_attribute_value_ids.sorted("id")],
                             "combo_parent_uuid": line.combo_parent_id.uuid or False,
                             "combo_item_id": line.combo_item_id.id or False,
                             "automatic_price": automatic, "provenance": "manual" if manual else "automatic"})
        base_lines = self.lines._prepare_tax_base_line_values()
        tax_model._add_tax_details_in_base_lines(base_lines, self.company_id)
        tax_model._round_base_lines_tax_details(base_lines, self.company_id)
        summary = tax_model._get_tax_totals_summary(base_lines=base_lines, currency=self.currency_id,
                                                  company=self.company_id, cash_rounding=None)
        total = summary["total_amount_currency"]
        decimal_text(total, "total", 10 ** 12)
        if total <= 0:
            raise UserError(_("A Revolut sale must have a positive authorized total."))
        if self.currency_id.compare_amounts(self.amount_total, total):
            corrections.append({"amount_total": total, "amount_tax": summary["tax_amount_currency"]})
        self.write({"amount_total": total, "amount_tax": summary["tax_amount_currency"],
                    "amount_paid": sum(self.payment_ids.mapped("amount")),
                    "amount_return": -sum(payment.amount for payment in self.payment_ids if payment.amount < 0),
                    "is_tipped": False, "tip_amount": 0})
        # Test the smallest contribution as well as proving the price quantum
        # is no larger than one currency unit after proportional taxes.
        self._revolut_terminal_tip_values(1)
        pricelists = self.pricelist_id
        seen = set()
        frontier = pricelists
        while frontier:
            seen.update(frontier.ids)
            parents = frontier.item_ids.base_pricelist_id.filtered(lambda item: item.id not in seen)
            pricelists |= parents
            frontier = parents
        categories = self.lines.product_id.categ_id
        frontier = categories
        while frontier:
            parents = frontier.parent_id - categories
            categories |= parents
            frontier = parents
        basis = {"config": _stamp(config), "restrict_price_control": config.restrict_price_control,
                 "manual_discount": config.manual_discount, "product_price_precision": precision,
                 "products": _stamp(self.lines.product_id | config.tip_product_id),
                 "product_templates": _stamp((self.lines.product_id | config.tip_product_id).product_tmpl_id),
                 "product_categories": _stamp(categories),
                 "attributes": _stamp(self.lines.attribute_value_ids),
                 "pricelists": _stamp(pricelists), "pricelist_rules": _stamp(pricelists.item_ids),
                 "taxes": _stamp(self.lines.tax_ids | config.tip_product_id.taxes_id),
                 "fiscal_position": _stamp(self.fiscal_position_id),
                 "fiscal_tax_mapping": _stamp(self.fiscal_position_id.tax_ids),
                 "combos": _stamp(self.lines.product_id.combo_ids),
                 "combo_items": _stamp(self.lines.combo_item_id),
                 "company_tax_rounding": self.company_id.tax_calculation_rounding_method,
                 "cash_rounding": config.cash_rounding, "only_round_cash_method": config.only_round_cash_method,
                 "rounding_method": _stamp(config.rounding_method), "currency_rate": self.currency_rate}
        return {"snapshot": normalize_snapshot(self._revolut_order_values(), native_order=True),
                "total_minor": self.env["pos.revolut.payment.operation"].normalize_amount(self.currency_id, total)[1],
                "basis": basis, "approval_required": approval_required, "corrections": corrections,
                "contents": contents, "pricing_time": fields.Datetime.to_string(pricing_time)}

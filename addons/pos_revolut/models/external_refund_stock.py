"""Restore native Odoo 18 return origins before inventory valuation."""
from collections import defaultdict
from decimal import Decimal

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class ExternalRefundStockOrder(models.Model):
    _inherit = "pos.order"

    def _revolut_native_return_pickings(self):
        """Read completed pooled history without assigning old stock records.

        A closed native 18 session can have no per-order picking links. Require
        its entire eligible pool to agree with its native order contents, so
        another return's goods cannot also prove an unprocessed return.
        """
        self.ensure_one()
        if self.picking_ids:
            return self.picking_ids
        empty = self.env["stock.picking"]
        session = self.session_id
        if (session.state != "closed" or not session.update_stock_at_closing
                or self.shipping_date or self._force_create_picking_real_time()
                or self.state not in {"paid", "done", "invoiced"}):
            return empty
        pooled = session.picking_ids.filtered(lambda picking: not picking.pos_order_id and picking.state != "cancel")
        if not pooled or any(picking.state != "done" or picking.company_id != self.company_id for picking in pooled):
            return empty
        picking_type = self.config_id.picking_type_id
        if not picking_type:
            return empty
        customer = picking_type.default_location_dest_id or self.env["stock.warehouse"]._get_partner_locations()[0]
        return_location = (picking_type.return_picking_type_id.default_location_dest_id
                           if picking_type.return_picking_type_id else picking_type.default_location_src_id)
        expected, actual = defaultdict(Decimal), defaultdict(Decimal)
        selected_keys = set()
        orders = session._get_closed_orders().filtered(lambda order:
            not order.picking_ids and not order.shipping_date and not order._force_create_picking_real_time())
        for order in orders:
            destination = order.partner_id.property_stock_customer or customer
            for line in order.lines:
                if line.product_id.type != "consu" or float_is_zero(line.qty, precision_rounding=line.product_id.uom_id.rounding):
                    continue
                source, target = ((picking_type.default_location_src_id, destination) if line.qty > 0
                                  else (destination, return_location))
                attributes = line.attribute_value_ids.filtered(lambda value: value.attribute_id.create_variant == "no_variant")
                lots = line.pack_lot_ids.mapped("lot_name") if line.product_id.tracking != "none" else [False]
                quantity = Decimal(1) if line.product_id.tracking == "serial" else abs(Decimal(str(line.qty)))
                for lot in lots:
                    key = (line.product_id.id, tuple(sorted(attributes.ids)), source.id, target.id, lot)
                    expected[key] += quantity
                    if order == self:
                        selected_keys.add(key)
        selected = empty
        for picking in pooled:
            for move in picking.move_ids.filtered(lambda move: move.state != "cancel"):
                if move.state != "done" or move.company_id != self.company_id:
                    return empty
                for detail in move.move_line_ids:
                    if (detail.company_id != self.company_id
                            or detail.location_id.usage != move.location_id.usage
                            or detail.location_dest_id.usage != move.location_dest_id.usage
                            or move.location_id.usage == "customer" and detail.location_id != move.location_id
                            or move.location_dest_id.usage == "customer" and detail.location_dest_id != move.location_dest_id):
                        return empty
                    key = (move.product_id.id, tuple(sorted(move.never_product_template_attribute_value_ids.ids)),
                           move.location_id.id, move.location_dest_id.id, detail.lot_id.name or False)
                    actual[key] += Decimal(str(detail.quantity_product_uom))
                    if key in selected_keys:
                        selected |= picking
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        if (expected.keys() != actual.keys() or any(
                float_compare(float(quantity), float(actual[key]), precision_digits=precision) != 0
                for key, quantity in expected.items())):
            return empty
        return selected


class ExternalRefundStockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def _create_picking_from_pos_order_lines(self, location_dest_id, lines, picking_type, partner=False):
        returns = lines.order_id.filtered(lambda order: order.sudo().revolut_external_refund_ids)
        if not returns:
            return super()._create_picking_from_pos_order_lines(location_dest_id, lines, picking_type, partner)
        # Closing-time stock normally pools orders. Keep the affected source
        # sale identifiable, and deliver it before returning its goods in the
        # same session; leave unrelated session orders on the native path.
        sources = returns.lines.refunded_orderline_id.order_id & lines.order_id
        pickings = self.env["stock.picking"]
        for order in sources:
            selected = lines.filtered(lambda line: line.order_id == order)
            created = super()._create_picking_from_pos_order_lines(location_dest_id, selected, picking_type, partner)
            created.write({"pos_order_id": order.id})
            pickings |= created
        remaining = lines.filtered(lambda line: line.order_id not in sources | returns)
        if remaining:
            pickings |= super()._create_picking_from_pos_order_lines(location_dest_id, remaining, picking_type, partner)
        for order in returns:
            selected = lines.filtered(lambda line: line.order_id == order)
            created = super()._create_picking_from_pos_order_lines(location_dest_id, selected, picking_type, partner)
            created.write({"pos_order_id": order.id})
            pickings |= created
        return pickings

    def _revolut_original_stock_quantities(self, line):
        original = line.refunded_orderline_id.order_id
        # Earlier native closing-time sales have session pickings only.
        pickings = original.picking_ids or original.session_id.picking_ids
        attributes = line.attribute_value_ids.filtered(lambda value: value.attribute_id.create_variant == "no_variant")
        moves = pickings.move_ids.filtered(lambda move:
            move.state == "done" and move.company_id == self.company_id
            and move.product_id == line.product_id
            and set(move.never_product_template_attribute_value_ids.ids) == set(attributes.ids)
            and move.location_dest_id == self.location_id
            and move.location_id.usage == self.location_dest_id.usage)
        quantities = defaultdict(Decimal)
        for move in moves.sorted("id"):
            previous = move.returned_move_ids.filtered(lambda returned: returned.state != "cancel")
            if previous.filtered(lambda returned: returned.state != "done"):
                raise UserError(_("Finish earlier stock returns before completing this native return."))
            for detail in move.move_line_ids:
                quantities[(move.id, detail.lot_id.id, detail.owner_id.id)] += Decimal(str(detail.quantity_product_uom))
            for detail in previous.move_line_ids:
                quantities[(move.id, detail.lot_id.id, detail.owner_id.id)] -= Decimal(str(detail.quantity_product_uom))
        return quantities

    def _create_move_from_pos_order_lines(self, lines):
        external = lines.filtered(lambda line: line.order_id.sudo().revolut_external_refund_ids)
        if not external:
            return super()._create_move_from_pos_order_lines(lines)
        if lines - external:
            super()._create_move_from_pos_order_lines(lines - external)
        self.ensure_one()
        # Native 18 groups POS moves by product/attributes and does not restore
        # origins. Allocate the selected goods against the original done move
        # details, retaining their lots and owners before stock valuation runs.
        used = defaultdict(Decimal)
        planned = {}
        precision = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        for line in external.sorted("id"):
            remaining = abs(Decimal(str(line.qty)))
            names = set(line.pack_lot_ids.mapped("lot_name"))
            for key, available in self._revolut_original_stock_quantities(line).items():
                move_id, lot_id, owner_id = key
                if line.product_id.tracking != "none" and self.env["stock.lot"].browse(lot_id).name not in names:
                    continue
                quantity = min(remaining, max(available - used[key], Decimal(0)))
                if quantity <= 0:
                    continue
                if move_id not in planned:
                    values = self._prepare_stock_move_vals(line, line)
                    values.update(origin_returned_move_id=move_id, product_uom_qty=0)
                    planned[move_id] = (values, [])
                values, details = planned[move_id]
                values["product_uom_qty"] += float(quantity)
                details.append((quantity, lot_id, owner_id))
                used[key] += quantity
                remaining -= quantity
                if float_compare(float(remaining), 0, precision_digits=precision) == 0:
                    break
            if float_compare(float(remaining), 0, precision_digits=precision) != 0:
                raise UserError(_("The original completed stock transfers cannot cover the selected return goods and lots."))
        for values, details in planned.values():
            move = self.env["stock.move"].create(values)._action_confirm(merge=False)
            # Confirmation may reserve customer stock. Replace reservations
            # with the exact manager-confirmed original lot quantities.
            move.move_line_ids.unlink()
            for quantity, lot_id, owner_id in details:
                detail_values = move._prepare_move_line_vals(float(quantity))
                detail_values.update(lot_id=lot_id, owner_id=owner_id)
                self.env["stock.move.line"].create(detail_values)
            move.picked = True

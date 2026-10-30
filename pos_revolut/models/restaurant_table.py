"""Native table links cannot hide an exposed Restaurant checkout."""
from odoo import _, models
from odoo.exceptions import UserError

from .return_allocation import ReturnAllocation


class RestaurantTable(models.Model):
    _inherit = "restaurant.table"

    def _revolut_linked_tables(self):
        tables = self.sudo()
        frontier = tables
        while frontier:
            neighbours = frontier.parent_id | self.sudo().search([
                ("parent_id", "in", frontier.ids),
            ])
            frontier = neighbours - tables
            tables |= frontier
        return tables

    def write(self, values):
        # Detaching a table must stay available to recover an existing link.
        if not values.get("parent_id"):
            return super().write(values)
        self.check_access("write")
        changing = self.filtered(lambda table: table.parent_id.id != values["parent_id"])
        if not changing:
            return super().write(values)
        target = self.browse(values["parent_id"]).exists()
        tables = (changing | target)._revolut_linked_tables()
        orders = self.env["pos.order"].sudo().search([
            ("table_id", "in", tables.ids), ("state", "=", "draft"),
        ])
        with self.env.cr.savepoint():
            # Use the same session/order locks as payment admission and native
            # transfers before deciding whether either effective table is safe.
            ReturnAllocation(self.env).acquire_native_mutation(orders)
            if any(order._revolut_has_exposure() for order in orders):
                raise UserError(_("Reconcile the Revolut payment before linking tables."))
            return super().write(values)

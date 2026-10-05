"""Remove the asset-only bridge after every module in the graph has loaded."""

from odoo import SUPERUSER_ID, api
from odoo.addons.pos_revolut.hooks import retire_restaurant_bridge


def migrate(cr, version):
    retire_restaurant_bridge(api.Environment(cr, SUPERUSER_ID, {}))

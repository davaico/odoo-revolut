from odoo import SUPERUSER_ID, api
from odoo.modules.module import get_manifest


def migrate(cr, version):
    name = "pos_revolut_restaurant_integration"
    if not get_manifest(name):
        return
    modules = api.Environment(cr, SUPERUSER_ID, {})["ir.module.module"]
    restaurant = modules.search([("name", "=", "pos_restaurant")])
    companion = modules.search([("name", "=", name), ("state", "=", "uninstalled")])
    if companion and restaurant.state in {"installed", "to upgrade"}:
        # Updating already-installed dependencies does not trigger auto-install.
        companion.button_install()

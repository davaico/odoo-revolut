from odoo import SUPERUSER_ID, api
from odoo.modules import Manifest


def migrate(cr, version):
    name = "pos_revolut_restaurant_integration"
    if not Manifest.for_addon(name):
        return
    modules = api.Environment(cr, SUPERUSER_ID, {})["ir.module.module"]
    if modules.search_count([
        ("name", "=", "pos_restaurant"), ("state", "in", ("installed", "to upgrade")),
    ]):
        companion = modules.search([("name", "=", name), ("state", "=", "uninstalled")])
        if companion:
            # Updating already-installed dependencies does not trigger auto-install.
            companion.button_install()

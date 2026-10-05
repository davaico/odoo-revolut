"""Retire the former asset-only Restaurant bridge after consolidation."""

from odoo.exceptions import UserError


LEGACY_RESTAURANT_MODULE = "pos_revolut_restaurant"


def retire_restaurant_bridge(env):
    """Remove bridge registration without uninstalling the main payment addon."""
    modules = env["ir.module.module"].sudo()
    bridge = modules.search([("name", "=", LEGACY_RESTAURANT_MODULE)])
    if not bridge:
        return
    if bridge.state not in {"installed", "uninstalled", "uninstallable"}:
        raise UserError(
            "Finish the pending POS Revolut Restaurant module operation before "
            "upgrading POS Revolut."
        )
    dependents = bridge.downstream_dependencies(
        exclude_states=("uninstalled", "uninstallable")
    )
    if dependents:
        raise UserError(
            "Cannot retire POS Revolut Restaurant while other modules depend on it: "
            + ", ".join(dependents.mapped("name"))
        )
    if bridge.state == "installed":
        # The retired bridge only declares JavaScript assets; it owns no payment
        # models or records. Use the low-level operation in the current upgrade
        # transaction, without starting another registry/module update.
        bridge.module_uninstall()
    bridge.unlink()
    # Asset resolution uses the loaded registry, not module states. The old
    # asset-only module may already have loaded during this upgrade; remove it
    # from that set so the same process cannot serve both copies of the guards.
    env.registry._init_modules.discard(LEGACY_RESTAURANT_MODULE)
    env.registry.clear_cache('assets')


def post_init_hook(env):
    retire_restaurant_bridge(env)

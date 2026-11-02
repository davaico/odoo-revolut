"""Run the framework hook, then discard ORM caches as on a restored server."""

from odoo.modules.neutralize import get_installed_modules, neutralize_database


def neutralize(env):
    env.flush_all()
    assert "pos_revolut" in get_installed_modules(env.cr), "Run copy fixtures after addon installation"
    neutralize_database(env.cr)
    env.invalidate_all(flush=False)
    env.registry.clear_cache()

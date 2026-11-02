"""Run the framework hook, then discard ORM caches as on a restored server."""

from odoo.modules.neutralize import neutralize_database


def neutralize(env):
    env.flush_all()
    neutralize_database(env.cr)
    env.invalidate_all(flush=False)
    env.registry.clear_cache()

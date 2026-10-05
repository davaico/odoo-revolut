"""Retire the Merchant-wide evidence page and its user read permission.

Only interface/access registrations are removed. The internal model, financial
observations, refund reservations and deployment flags must remain intact.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for identifier in (
        "menu_external_refund_evidence",
        "action_external_refund_evidence",
        "view_external_refund_evidence_list",
        "view_external_refund_evidence_form",
        "view_external_refund_evidence_search",
        "access_pos_revolut_external_refund_evidence_manager",
        "rule_revolut_external_refund_evidence_company_manager",
    ):
        record = env.ref(f"pos_revolut.{identifier}", raise_if_not_found=False)
        if record:
            record.unlink()
        env["ir.model.data"].search([
            ("module", "=", "pos_revolut"), ("name", "=", identifier),
        ]).unlink()

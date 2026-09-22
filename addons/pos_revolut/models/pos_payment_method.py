import os
import re

import requests

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


REVOLUT_SECRET_REFERENCE_PATTERN = re.compile(r"ODOO_REVOLUT_SECRET_[A-Z0-9_]+")
REVOLUT_UUID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
REVOLUT_API_VERSION = "2026-08-17"
REVOLUT_API_HOSTS = {
    "sandbox": "https://sandbox-merchant.revolut.com",
    "production": "https://merchant.revolut.com",
}
REVOLUT_REQUEST_TIMEOUT_SECONDS = 10


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    revolut_environment = fields.Selection(
        selection=[("sandbox", "Sandbox"), ("production", "Production")],
        string="Revolut Environment",
        default="sandbox",
        copy=False,
        groups="point_of_sale.group_pos_manager",
    )
    revolut_location_id = fields.Char(
        string="Revolut Location ID",
        copy=False,
        groups="point_of_sale.group_pos_manager",
    )
    revolut_terminal_id = fields.Char(
        string="Revolut Terminal ID",
        copy=False,
        groups="point_of_sale.group_pos_manager",
    )
    revolut_secret_reference = fields.Char(
        string="Revolut Secret Reference",
        copy=False,
        groups="point_of_sale.group_pos_manager",
        help=(
            "Name of a server environment variable in the "
            "ODOO_REVOLUT_SECRET_ namespace. The secret itself is never stored."
        ),
    )

    def _get_payment_terminal_selection(self):
        return super()._get_payment_terminal_selection() + [("revolut", "Revolut")]

    @api.constrains("use_payment_terminal", "revolut_secret_reference")
    def _check_revolut_secret_reference(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if not REVOLUT_SECRET_REFERENCE_PATTERN.fullmatch(
                payment_method.revolut_secret_reference or ""
            ):
                raise ValidationError(
                    _(
                        "The Revolut secret reference must name a variable in the "
                        "ODOO_REVOLUT_SECRET_ namespace."
                    )
                )

    @api.constrains(
        "use_payment_terminal", "revolut_location_id", "revolut_terminal_id"
    )
    def _check_revolut_identifiers(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if not all(
                REVOLUT_UUID_PATTERN.fullmatch(identifier or "")
                for identifier in (
                    payment_method.revolut_location_id,
                    payment_method.revolut_terminal_id,
                )
            ):
                raise ValidationError(
                    _("Revolut location and terminal IDs must be valid UUIDs.")
                )

    @api.constrains("use_payment_terminal", "revolut_environment")
    def _check_revolut_environment(self):
        for payment_method in self.filtered(
            lambda method: method.use_payment_terminal == "revolut"
        ):
            if payment_method.revolut_environment not in REVOLUT_API_HOSTS:
                raise ValidationError(
                    _("Select Sandbox or Production for the Revolut environment.")
                )

    def action_revolut_check_connection(self):
        self.ensure_one()
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(_("Only Point of Sale managers can check a terminal."))
        self.check_access("read")
        if self.company_id not in self.env.companies:
            raise AccessError(_("You cannot check a terminal for another company."))
        if self.use_payment_terminal != "revolut":
            raise UserError(_("This payment method does not use Revolut."))

        if not REVOLUT_SECRET_REFERENCE_PATTERN.fullmatch(
            self.revolut_secret_reference or ""
        ):
            raise UserError(_("The Revolut secret reference is invalid."))
        secret = os.environ.get(self.revolut_secret_reference)
        if not secret:
            raise UserError(
                _("The Revolut credential is not available on the Odoo server.")
            )

        try:
            response = requests.get(
                f"{REVOLUT_API_HOSTS[self.revolut_environment]}/api/terminals",
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Revolut-Api-Version": REVOLUT_API_VERSION,
                },
                params={
                    "operation_mode": "pos",
                    "location_id": self.revolut_location_id,
                },
                timeout=REVOLUT_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            raise UserError(
                _("The Revolut terminal check could not be completed.")
            ) from None

        terminals = payload.get("terminals") if isinstance(payload, dict) else None
        if not isinstance(terminals, list):
            raise UserError(_("Revolut returned an invalid terminal response."))
        terminal = next(
            (
                item
                for item in terminals
                if isinstance(item, dict)
                and item.get("id") == self.revolut_terminal_id
            ),
            None,
        )
        if not terminal:
            raise UserError(
                _("The configured terminal was not found at this Revolut location.")
            )
        if terminal.get("online") is not True:
            raise UserError(_("The configured Revolut terminal is offline."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Revolut terminal connected"),
                "message": _(
                    "%(terminal)s is online.",
                    terminal=terminal.get("name") or self.revolut_terminal_id,
                ),
                "type": "success",
                "sticky": False,
            },
        }

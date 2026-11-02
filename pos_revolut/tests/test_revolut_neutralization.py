"""Exercise Odoo's whole-database neutralization and public payment boundaries."""

from odoo.tests.common import TransactionCase, tagged

from .neutralization_fixtures import neutralize

from .test_revolut_database_credentials import TestRevolutDatabaseCredentials as _Credentials


@tagged("post_install", "-at_install")
class TestRevolutNeutralization(TransactionCase):
    _authority = _Credentials._authority
    _method = _Credentials._method

    def _neutralize(self):
        neutralize(self.env)
        self.assertTrue(self.env["ir.config_parameter"].sudo().get_param("database.is_neutralized"))

    def test_neutralization_clears_all_companies_live_keys_and_configuration_repeatably(self):
        other = self.env["res.company"].create({"name": "Synthetic copied company"})
        credentials = self.env["pos.revolut.merchant.credential"]
        methods = self.env["pos.payment.method"]
        for company in (self.env.company, other):
            for source in ("database", "environment"):
                credential = self._authority(company, environment="production", source=source,
                                             secret_key="synthetic-live-key" if source == "database" else False)
                credentials |= credential
                methods |= self._method(credential)
        sandbox = self._authority()
        sandbox_method = self._method(sandbox)
        crons = (self.env.ref("pos_revolut.ir_cron_reconcile_payments")
                 | self.env.ref("pos_revolut.ir_cron_reconcile_refunds"))
        crons.write({"active": True})
        bindings = methods.read(["company_id", "revolut_environment", "revolut_secret_reference",
                                 "revolut_location_id", "revolut_terminal_id", "use_payment_terminal"])
        for _ in range(2):
            self._neutralize()
            self.assertFalse(any(credentials.mapped("secret_key")))
            self.assertTrue(all(credentials.mapped("revoked")))
            self.assertFalse(any(methods.mapped("active")))
            self.assertFalse(any(crons.mapped("active")))
            self.assertEqual(methods.read(list(bindings[0].keys())), bindings)
            self.assertEqual(sandbox.secret_key, "synthetic-database-merchant-key")
            self.assertFalse(sandbox.revoked)
            self.assertTrue(sandbox_method.active)

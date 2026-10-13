from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..hooks import LEGACY_RESTAURANT_MODULE, retire_restaurant_bridge


@tagged("post_install", "-at_install")
class TestRestaurantConsolidation(TransactionCase):
    def setUp(self):
        super().setUp()
        self.modules = self.env["ir.module.module"]
        self.assertFalse(self.modules.search([
            ("name", "=", LEGACY_RESTAURANT_MODULE),
        ]), "The consolidated installation must not retain the bridge registration")
        self.payment_method = self.env["pos.payment.method"].create({
            "name": "Consolidation payment configuration sentinel",
        })
        self.base = self.modules.search([("name", "=", "pos_revolut")])
        self.base_state = self.base.state

    def _bridge(self, state):
        return self.modules.create({
            "name": LEGACY_RESTAURANT_MODULE,
            "state": state,
        })

    def _assert_base_preserved(self):
        self.assertEqual(self.base.exists(), self.base)
        self.assertEqual(self.base.state, self.base_state)
        self.assertEqual(self.payment_method.exists(), self.payment_method)
        self.assertEqual(
            self.payment_method.name, "Consolidation payment configuration sentinel"
        )

    def test_absent_bridge_is_idempotent(self):
        retire_restaurant_bridge(self.env)
        retire_restaurant_bridge(self.env)
        self._assert_base_preserved()

    def test_uninstalled_bridge_registration_is_removed(self):
        bridge = self._bridge("uninstalled")
        retire_restaurant_bridge(self.env)
        self.assertFalse(bridge.exists())
        self._assert_base_preserved()

    def test_installed_bridge_is_retired(self):
        bridge = self._bridge("installed")
        retire_restaurant_bridge(self.env)
        self.assertFalse(bridge.exists())
        self._assert_base_preserved()

    def test_installed_dependent_blocks_retirement(self):
        bridge = self._bridge("installed")
        dependent = self.modules.create({
            "name": "test_revolut_bridge_dependent",
            "state": "installed",
            "dependencies_id": [(0, 0, {"name": LEGACY_RESTAURANT_MODULE})],
        })
        with self.assertRaisesRegex(UserError, "other modules depend on it"):
            retire_restaurant_bridge(self.env)
        self.assertTrue(bridge.exists())
        self.assertEqual(bridge.state, "installed")
        self.assertTrue(dependent.exists())
        self._assert_base_preserved()

    def test_pending_operation_blocks_retirement(self):
        bridge = self._bridge("to upgrade")
        with self.assertRaisesRegex(UserError, "pending"):
            retire_restaurant_bridge(self.env)
        self.assertEqual(bridge.state, "to upgrade")
        self._assert_base_preserved()

from threading import Barrier
from uuid import uuid4

from odoo import SUPERUSER_ID, Command, api
from odoo.addons.pos_revolut.tests.test_revolut_cart_authority_concurrency import (
    RevolutCartAuthorityConcurrencyFixtures,
)
from odoo.service.model import retrying
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantConcurrency(RevolutCartAuthorityConcurrencyFixtures, TransactionCase):
    def test_cross_session_restaurant_transfers_racing_native_sync_preserve_exposure(self):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            source = env["pos.order"].browse(self.order_id)
            source.session_id.state = "closed"
            preset = env.ref("pos_revolut.pos_takein_preset")
            source.config_id.write({
                "module_pos_restaurant": True, "use_presets": True,
                "default_preset_id": preset.id, "available_preset_ids": [Command.link(preset.id)],
            })
            other_config = source.config_id.copy({"name": "Concurrent shared-floor register"})
            floor = env["restaurant.floor"].create({
                "name": "Concurrent shared floor", "pos_config_ids": [
                    Command.link(source.config_id.id), Command.link(other_config.id),
                ],
            })
            first_table, second_table = env["restaurant.table"].create([
                {"floor_id": floor.id, "table_number": 1},
                {"floor_id": floor.id, "table_number": 2},
            ])
            source.write({"table_id": first_table.id, "preset_id": preset.id})
            other_session = env["pos.session"].create({"config_id": other_config.id, "state": "opened"})
            other = env["pos.order"].create({
                "session_id": other_session.id, "uuid": str(uuid4()), "table_id": second_table.id,
                "date_order": "2099-01-01 12:00:00", "preset_id": preset.id,
                "pricelist_id": source.pricelist_id.id, "amount_total": 100, "amount_tax": 0,
                "amount_paid": 0, "amount_return": 0,
                "lines": [Command.create({
                    "uuid": str(uuid4()), "product_id": source.lines.product_id.id, "qty": 1,
                    "price_unit": 100, "price_subtotal": 100, "price_subtotal_incl": 100,
                    "tax_ids": [Command.clear()],
                })],
            })
            source.session_id.state = "opened"
            source_table, destination_table, other_id = first_table.id, second_table.id, other.id
            other_uuid, other_session_id = other.uuid, other_session.id
            cursor.commit()
        self.save_waiting_tender()
        authority = self.prepare([(self.line_a, 100)])
        started = self.start(authority, self.line_a, 100)
        self.assertEqual(started["state"], "pending")
        self.request.reset_mock()
        barrier = Barrier(2)

        def native_transfer():
            barrier.wait(timeout=10)
            return self.rpc("pos.order", "sync_from_ui", [{
                "uuid": other_uuid, "session_id": other_session_id, "state": "draft",
                "table_id": source_table, "amount_total": 100, "amount_tax": 0,
                "amount_paid": 0, "amount_return": 0, "lines": [], "payment_ids": [],
            }])

        def opposite_transfer():
            barrier.wait(timeout=10)
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                retrying(lambda: env["pos.order"].browse(self.order_id).write({
                    "table_id": destination_table,
                }), env)
                cursor.commit()

        results = self.workers([("native", native_transfer), ("opposite", opposite_transfer)])
        for result in results.values():
            self.assertRegex(result["error"], "occupied table")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            source, other = env["pos.order"].browse([self.order_id, other_id])
            self.assertEqual((source.uuid, source.table_id.id, source.session_id.id),
                             (self.order_uuid, source_table, self.session_id))
            self.assertEqual((other.uuid, other.table_id.id, other.session_id.id),
                             (other_uuid, destination_table, other_session_id))
            self.assertEqual((source.lines.qty, other.lines.qty), (1, 1))
            recovered = env["pos.payment.method"].browse(self.method_id).revolut_find_payment(
                self.order_uuid, self.line_a, self.session_id,
            )
            self.assertEqual(recovered["operation_id"], started["operation_id"])
            self.assertEqual(recovered["state"], "pending")
        self.request.assert_not_called()

"""Authorized base allocation across independent, committed RPC transactions."""
import csv
from copy import deepcopy
from datetime import timedelta
import io
import json
import os
from threading import Barrier, Event, RLock, Thread
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from uuid import uuid4

from odoo import SUPERUSER_ID, Command, api, fields
from odoo.exceptions import UserError
from odoo.orm.registry import Registry
from odoo.service.model import retrying
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestRevolutCartAuthorityConcurrency(TransactionCase):
    def setUp(self):
        super().setUp()
        self.observation_time = fields.Datetime.now()
        self.enterContext(patch(
            "odoo.addons.pos_revolut.models.payment_observation.observation_now",
            side_effect=lambda: self.observation_time,
        ))
        self.registry = self.env.registry
        self.context = {"allowed_company_ids": [self.env.company.id]}
        self.order_uuid = str(uuid4())
        self.line_a, self.line_b = str(uuid4()), str(uuid4())
        self.providers = {}
        self.intents = {}
        self.payment_ids = {}
        self.report_status = "completed"
        self.report_ids = set()
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            self.currency_id, self.currency_code = env.company.currency_id.id, env.company.currency_id.name
            method = env["pos.payment.method"].create({
                "name": "Authorized base concurrency", "payment_method_type": "terminal",
                "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
                "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_CART_RACE_TEST",
            })
            product = env["product.product"].create({
                "name": "Concurrent authorized base", "list_price": 100,
                "available_in_pos": True, "taxes_id": [Command.clear()],
            })
            tip = env["product.product"].create({
                "name": "Concurrent verified terminal tip", "list_price": 0,
                "taxes_id": [Command.clear()],
            })
            pricelist = env["product.pricelist"].create({
                "name": "Concurrent base prices", "currency_id": self.currency_id,
            })
            config = env["pos.config"].create({
                "name": "Authorized base concurrency", "auto_validate_terminal_payment": True,
                "payment_method_ids": [Command.link(method.id)], "tip_product_id": tip.id,
                "use_pricelist": True, "pricelist_id": pricelist.id,
                "available_pricelist_ids": [Command.link(pricelist.id)],
            })
            session = env["pos.session"].create({"config_id": config.id, "state": "opened"})
            order = env["pos.order"].create({
                "session_id": session.id, "uuid": self.order_uuid,
                "amount_total": 100, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
                "pricelist_id": pricelist.id,
                "lines": [Command.create({"product_id": product.id, "qty": 1,
                    "price_unit": 100, "price_subtotal": 100, "price_subtotal_incl": 100,
                    "tax_ids": [Command.clear()]})],
            })
            self.method_id, self.session_id, self.order_id = method.id, session.id, order.id
            self.location_id, self.terminal_id = method.revolut_location_id, method.revolut_terminal_id
            cursor.commit()
        self.enterContext(patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_CART_RACE_TEST": "test-only"}))
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request", side_effect=self.http))

    def rpc(self, model, method, *args):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            target = env[model].browse(self.method_id) if model == "pos.payment.method" else env[model]
            if method == "sync_from_ui":
                # Native RPC receives the ordinary service retry boundary;
                # each retry starts with its original, unmutated JSON input.
                result = retrying(lambda: getattr(target, method)(*deepcopy(args)), env)
            else:
                result = getattr(target, method)(*args)
            cursor.commit()
            return result

    def prepare(self, slots, version=0):
        return self.rpc("pos.order", "revolut_prepare_payment", self.order_id, self.order_uuid, version,
            [{"uuid": uuid, "payment_method_id": self.method_id, "amount": amount} for uuid, amount in slots])

    def start(self, authority, line_uuid, amount):
        return self.rpc("pos.payment.method", "revolut_start_payment", self.session_id, self.order_uuid,
            line_uuid, amount, self.currency_id, False, False,
            authority["authorization_id"], authority["cart_version"], authority["tender_revision"])

    def poll(self, operation_id, line_uuid):
        self.observation_time += timedelta(seconds=1)
        return self.rpc("pos.payment.method", "revolut_poll_payment", operation_id, self.order_uuid, line_uuid)

    def operations(self):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            return env["pos.revolut.payment.operation"].search_read(
                [("order_uuid", "=", self.order_uuid)], ["amount_minor", "state", "payment_line_uuid"])

    def financial_posts(self):
        return [call for call in self.request.call_args_list
                if call.args[0] == "POST" and urlsplit(call.args[1]).path != "/api/report-runs"]

    def save_waiting_tender(self):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            payment = env['pos.payment'].create({'pos_order_id': self.order_id,
                'uuid': self.line_a, 'payment_method_id': self.method_id,
                'amount': 100, 'payment_status': 'waiting'})
            cursor.commit()
            return payment.id

    def recover(self, remove=False):
        return self.rpc('pos.order', 'revolut_remove_unstarted_payment' if remove else 'revolut_recover_unstarted_payment',
            self.order_id, self.order_uuid, self.line_a, self.method_id, 100, self.currency_id)

    def test_recovery_racing_start_either_fences_admission_or_keeps_operation(self):
        self.save_waiting_tender()
        authority = self.prepare([(self.line_a, 100)])
        barrier = Barrier(2)

        def recover():
            barrier.wait(timeout=10)
            return self.recover()

        def start():
            barrier.wait(timeout=10)
            return self.start(authority, self.line_a, 100)

        results = self.workers([('recovery', recover), ('start', start)])
        recovery, started = results['recovery'], results['start']
        if recovery['recovery_status'] == 'unstarted':
            self.assertFalse(started.get('operation_id'))
            self.assertFalse(self.operations())
            self.request.assert_not_called()
        else:
            self.assertEqual(recovery['recovery_status'], 'existing_operation')
            self.assertEqual(recovery['operation_id'], started['operation_id'])
            self.assertEqual(len(self.operations()), 1)
            self.assertEqual(len(self.financial_posts()), 2)

    def test_atomic_removal_racing_start_keeps_charge_visible_or_retires_tender(self):
        self.save_waiting_tender()
        authority = self.prepare([(self.line_a, 100)])
        barrier = Barrier(2)

        def remove():
            barrier.wait(timeout=10)
            return self.recover(remove=True)

        def start():
            barrier.wait(timeout=10)
            return self.start(authority, self.line_a, 100)

        results = self.workers([('removal', remove), ('start', start)])
        retired, started = results['removal'], results['start']
        if 'error' in retired:
            self.assertEqual(retired['error'], 'Another cashier changed this tender. Reload and check its status.')
        state = self.rpc('pos.order', 'revolut_checkout_state', self.order_id, self.order_uuid)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            payments = env['pos.order'].browse(self.order_id).payment_ids
            if retired.get('recovery_status') == 'retired':
                self.assertFalse(payments)
                self.assertEqual(state['recovered_tenders'][self.line_a]['state'], 'retired')
                self.assertFalse(started.get('operation_id'))
                self.assertFalse(self.operations())
                self.request.assert_not_called()
            elif retired.get('recovery_status') == 'existing_operation':
                self.assertEqual(retired['recovery_status'], 'existing_operation')
                self.assertEqual(retired['operation_id'], started['operation_id'])
                self.assertEqual(len(payments), 1)
                self.assertEqual(len(self.operations()), 1)
                self.assertEqual(len(self.financial_posts()), 2)
            else:
                # Exhausting the bounded contention retry never consumes
                # removal authority. The original line and any winning charge
                # remain recoverable through an explicit later status action.
                self.assertIn('error', retired, repr(results))
                self.assertEqual(len(payments), 1)
                recovered = self.recover()
                if started.get('operation_id'):
                    self.assertEqual(recovered['recovery_status'], 'existing_operation')
                    self.assertEqual(recovered['operation_id'], started['operation_id'])
                    self.assertEqual(len(self.operations()), 1)
                    self.assertEqual(len(self.financial_posts()), 2)
                else:
                    self.assertEqual(recovered['recovery_status'], 'unstarted')
                    self.assertFalse(self.operations())
                    self.request.assert_not_called()

    def test_duplicate_recovery_and_delayed_preparation_cannot_dispatch(self):
        self.save_waiting_tender()
        barrier = Barrier(2)

        def recover():
            barrier.wait(timeout=10)
            return self.recover()

        results = self.workers([('cashier-a', recover), ('cashier-b', recover)])
        self.assertEqual(results['cashier-a'], results['cashier-b'])
        with self.assertRaises(UserError):
            self.prepare([(self.line_a, 100)])
        self.assertFalse(self.operations())
        self.request.assert_not_called()

    def test_retired_tender_cannot_start_after_alternative_native_settlement(self):
        self.save_waiting_tender()
        authority = self.prepare([(self.line_a, 100)])
        self.assertEqual(self.recover(remove=True)['recovery_status'], 'retired')
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env['pos.order'].browse(self.order_id)
            # An ordinary configured bank tender settles the sale independently
            # only after the original Revolut admission is durably retired.
            bank = env['pos.payment.method'].create({'name': 'Alternative settlement'})
            order.session_id.state = 'closed'
            order.config_id.payment_method_ids = [Command.link(bank.id)]
            order.session_id.state = 'opened'
            order.payment_ids = [Command.create({'uuid': str(uuid4()), 'payment_method_id': bank.id, 'amount': 100})]
            order.action_pos_order_paid()
            self.assertEqual(order.state, 'paid')
            cursor.commit()
        with self.assertRaises(UserError):
            self.start(authority, self.line_a, 100)
        with self.assertRaises(UserError):
            state = self.rpc('pos.order', 'revolut_checkout_state', self.order_id, self.order_uuid)
            self.rpc('pos.order', 'revolut_prepare_payment', self.order_id, self.order_uuid, 0,
                [{'uuid': self.line_a, 'payment_method_id': self.method_id, 'amount': 100}], state['recovery_revision'])
        self.assertFalse(self.operations())
        self.request.assert_not_called()

    def response(self, payload):
        content = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        response = Mock(status_code=200)
        response.json.return_value = payload
        response.iter_content.return_value = [content]
        return response

    def http(self, method, url, **kwargs):
        path = urlsplit(url).path
        if method == "GET" and path == "/api/terminals":
            return self.response({"terminals": [{"id": self.terminal_id, "online": True,
                "operation_mode": "pos", "location_id": self.location_id}]})
        if method == "POST" and path == "/api/orders":
            identifier = str(uuid4())
            self.providers[identifier] = {"minor": kwargs["json"]["amount"], "payment_id": str(uuid4())}
            return self.response({"id": identifier})
        if method == "POST" and path.endswith("/payment-intents"):
            identifier = str(uuid4())
            order_id = path.split("/")[3]
            self.intents[identifier] = order_id
            self.payment_ids[self.providers[order_id]["payment_id"]] = order_id
            return self.response({"id": identifier, "state": "pending"})
        if method == "GET" and path.startswith("/api/payment-intents/"):
            identifier = path.rsplit("/", 1)[-1]
            order_id = self.intents[identifier]
            provider = self.providers[order_id]
            return self.response({"id": identifier, "order_id": order_id, "state": "completed",
                "payment_id": provider["payment_id"], "amount": provider["minor"],
                "currency": self.currency_code, "terminal_id": self.terminal_id})
        if method == "GET" and path.startswith("/api/payments/"):
            identifier = path.rsplit("/", 1)[-1]
            order_id = self.payment_ids[identifier]
            return self.response({"id": identifier, "order_id": order_id, "state": "captured",
                "amount": self.providers[order_id]["minor"] + self.providers[order_id].get("tip", 0), "currency": self.currency_code,
                "created_at": "2026-10-01T10:00:00Z"})
        if method == "POST" and path == "/api/report-runs":
            identifier = str(uuid4())
            self.report_ids.add(identifier)
            return self.response({"report_run_id": identifier, "status": self.report_status})
        if method == "GET" and path.rsplit("/", 1)[-1] in self.report_ids:
            return self.response({"report_run_id": path.rsplit("/", 1)[-1], "status": self.report_status})
        if method == "GET" and path.startswith("/api/report-runs/") and path.endswith("/file"):
            columns = ("payment_id", "type", "order_id", "state", "amount", "currency", "surcharge_amount",
                "tip_amount", "refunded_amount", "created_date", "captured_date", "location_id")
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(columns)
            for payment_id, order_id in self.payment_ids.items():
                provider = self.providers[order_id]
                writer.writerow([payment_id, "PAYMENT", order_id, "COMPLETED",
                    f"{(provider['minor'] + provider.get('tip', 0)) / 100:.2f}", self.currency_code,
                    "", f"{provider.get('tip', 0) / 100:.2f}", "0.00",
                    "2026-10-01T10:00:00Z", "2026-10-01T10:00:10Z", self.location_id])
            return self.response(output.getvalue().encode())
        if method == "GET" and path.startswith("/api/orders/"):
            order_id = path.rsplit("/", 1)[-1]
            provider = self.providers[order_id]
            return self.response({"id": order_id, "currency": self.currency_code, "location_id": self.location_id,
                "payments": [{"id": provider["payment_id"], "state": "captured",
                              "amount": provider["minor"] + provider.get("tip", 0)}]})
        raise AssertionError(f"Unexpected guarded provider request: {method} {path}")

    def workers(self, tasks):
        results, errors = {}, []

        def run(name, task):
            try:
                results[name] = task()
            except UserError as error:
                results[name] = {"error": str(error)}
            except Exception as error:
                errors.append(error)

        threads = [Thread(target=run, args=(name, task), name=name, daemon=True) for name, task in tasks]
        # Odoo preload owns Registry._lock while tests run. This replacement
        # permits thread Environments while retaining real database cursors.
        with patch.object(Registry, "_lock", RLock()), mute_logger("odoo.sql_db"):
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
        self.assertFalse(any(thread.is_alive() for thread in threads), "Public RPC deadlocked")
        self.assertFalse(errors, repr(errors))
        return results

    def test_distinct_slots_are_reserved_once_then_verified_sequentially(self):
        authority = self.prepare([(self.line_a, 40), (self.line_b, 60)])
        barrier = Barrier(2)

        def start(uuid, amount):
            barrier.wait(timeout=10)
            return self.start(authority, uuid, amount)

        results = self.workers([("card-a", lambda: start(self.line_a, 40)),
                                ("card-b", lambda: start(self.line_b, 60))])
        winners = [value for value in results.values() if value.get("operation_id")]
        self.assertEqual(len(winners), 1)
        reserved = self.operations()
        self.assertEqual(len(reserved), 1)
        self.assertLessEqual(sum(item["amount_minor"] for item in reserved), 10000)
        self.assertEqual(len(self.financial_posts()), 2)
        first = reserved[0]
        self.assertEqual(self.poll(first["id"], first["payment_line_uuid"])["state"], "verified")
        second_uuid, second_amount = (self.line_b, 60) if first["payment_line_uuid"] == self.line_a else (self.line_a, 40)
        second = self.start(authority, second_uuid, second_amount)
        self.assertEqual(self.poll(second["operation_id"], second_uuid)["state"], "verified")
        self.assertEqual(sum(item["amount_minor"] for item in self.operations()), 10000)
        self.assertEqual(len(self.financial_posts()), 4)

    def test_first_reservation_cannot_race_original_session_closure(self):
        authority = self.prepare([(self.line_a, 100)])
        closing_written, start_entered, closing_committed, provider_seen = [Event() for _ in range(4)]
        provider = self.http
        dispatch_before_close_commit = []

        def hold_discovery(method, url, **kwargs):
            provider_seen.set()
            self.assertTrue(closing_committed.wait(timeout=10), "Closing transaction did not finish")
            return provider(method, url, **kwargs)

        self.request.side_effect = hold_discovery

        def close_session():
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                env["pos.session"].browse(self.session_id).write({"state": "closing_control"})
                closing_written.set()
                self.assertTrue(start_entered.wait(timeout=10), "Start RPC never entered")
                # A correct first reservation waits on the uncommitted session
                # boundary. A broken one reaches provider discovery here.
                dispatch_before_close_commit.append(provider_seen.wait(timeout=2))
                cursor.commit()
                closing_committed.set()
                return "closing_control"

        def start_payment():
            self.assertTrue(closing_written.wait(timeout=10), "Closing write never started")
            start_entered.set()
            return self.start(authority, self.line_a, 100)

        result = self.workers([("closing", close_session), ("starting", start_payment)])
        self.assertEqual(result["closing"], "closing_control")
        self.assertFalse(result["starting"].get("operation_id"))
        self.assertEqual(dispatch_before_close_commit, [False])
        self.assertFalse(self.operations())
        self.request.assert_not_called()

    def test_concurrent_tender_replan_cannot_create_second_seventy_allocation(self):
        authority = self.prepare([(self.line_a, 70)])
        barrier = Barrier(2)

        def start_original():
            barrier.wait(timeout=10)
            return self.start(authority, self.line_a, 70)

        def replace_unused_slot():
            barrier.wait(timeout=10)
            revised = self.prepare([(self.line_b, 70)], authority["cart_version"])
            return self.start(revised, self.line_b, 70)

        results = self.workers([("original", start_original), ("replanned", replace_unused_slot)])
        self.assertEqual(sum(bool(item.get("operation_id")) for item in results.values()), 1)
        operations = self.operations()
        self.assertEqual(len(operations), 1)
        self.assertEqual(operations[0]["amount_minor"], 7000)
        self.assertEqual(len(self.financial_posts()), 2)

    def test_verified_partial_payment_consumes_entitlement_after_terminal_release(self):
        authority = self.prepare([(self.line_a, 70)])
        first = self.start(authority, self.line_a, 70)
        self.assertEqual(self.poll(first["operation_id"], self.line_a)["state"], "verified")
        with self.assertRaises(UserError):
            self.prepare([(self.line_a, 70), (self.line_b, 70)], authority["cart_version"])
        self.assertEqual(len(self.operations()), 1)
        self.assertEqual(len(self.financial_posts()), 2)
        remaining = self.prepare([(self.line_a, 70), (self.line_b, 30)], authority["cart_version"])
        second = self.start(remaining, self.line_b, 30)
        self.assertEqual(self.poll(second["operation_id"], self.line_b)["state"], "verified")
        self.assertEqual(sum(item["amount_minor"] for item in self.operations()), 10000)
        self.assertEqual(len(self.financial_posts()), 4)

        with self.assertRaises(UserError):
            self.start(remaining, str(uuid4()), 0.01)
        self.assertEqual(len(self.operations()), 2)
        self.assertEqual(len(self.financial_posts()), 4)

    def test_concurrent_report_polls_project_one_tip_and_gross_tender(self):
        authority = self.prepare([(self.line_a, 100)])
        started = self.start(authority, self.line_a, 100)
        self.providers[started["order_id"]]["tip"] = 300
        barrier = Barrier(2)

        def poll():
            barrier.wait(timeout=10)
            return self.poll(started["operation_id"], self.line_a)

        self.workers([("poll-a", poll), ("poll-b", poll)])
        self.assertEqual(self.poll(started["operation_id"], self.line_a)["state"], "verified")
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(self.order_id)
            self.assertEqual(order.amount_total, 103)
            self.assertEqual(len(order.payment_ids), 1)
            self.assertEqual(order.payment_ids.amount, 103)
            self.assertEqual(len(order.lines.filtered(lambda line: line.product_id == order.config_id.tip_product_id)), 1)
        self.assertEqual(len(self.operations()), 1)
        self.assertEqual(len(self.financial_posts()), 2)
        self.assertEqual(sum(call.args[0] == "POST" and urlsplit(call.args[1]).path == "/api/report-runs"
                             for call in self.request.call_args_list), 1)

    def test_late_tip_verification_racing_remaining_start_keeps_base_capacity(self):
        authority = self.prepare([(self.line_a, 70), (self.line_b, 30)])
        first = self.start(authority, self.line_a, 70)
        self.providers[first["order_id"]]["tip"] = 300
        self.report_status = "processing"
        waiting = self.poll(first["operation_id"], self.line_a)
        self.assertTrue(waiting["awaiting_tip_details"])
        self.report_status = "completed"
        barrier = Barrier(2)

        def finish():
            barrier.wait(timeout=10)
            return self.poll(first["operation_id"], self.line_a)

        def start_second():
            barrier.wait(timeout=10)
            return self.start(authority, self.line_b, 30)

        result = self.workers([("verifying", finish), ("remaining", start_second)])
        self.assertEqual(self.poll(first["operation_id"], self.line_a)["state"], "verified")
        second = result["remaining"]
        if not second.get("operation_id"):
            second = self.start(authority, self.line_b, 30)
        self.providers[second["order_id"]]["tip"] = 200
        self.assertEqual(self.poll(second["operation_id"], self.line_b)["state"], "verified")
        self.assertEqual(sum(item["amount_minor"] for item in self.operations()), 10000)
        self.assertEqual(len(self.financial_posts()), 4)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(self.order_id)
            self.assertEqual(order.amount_total, 105)
            self.assertEqual(sum(order.payment_ids.mapped("amount")), 105)
            self.assertEqual(len(order.lines.filtered(lambda line: line.product_id == order.config_id.tip_product_id)), 1)

    def test_manager_approval_racing_price_edit_cannot_approve_changed_cart(self):
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(self.order_id)
            order.config_id.restrict_price_control = True
            order.lines.write({"price_unit": 90, "price_subtotal": 90, "price_subtotal_incl": 90})
            order.amount_total = 90
            cursor.commit()
        authority = self.prepare([(self.line_a, 90)])
        self.assertEqual(authority["status"], "approval_required")
        barrier = Barrier(2)

        def approve():
            barrier.wait(timeout=10)
            return self.rpc("pos.order", "revolut_approve_cart", self.order_id, self.order_uuid, authority["cart_version"])

        def edit():
            barrier.wait(timeout=10)
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, SUPERUSER_ID, self.context)
                retrying(lambda: env["pos.order"].browse(self.order_id).lines.write({
                    "price_unit": 80, "price_subtotal": 80, "price_subtotal_incl": 80}), env)
                cursor.commit()
                return "edited"

        result = self.workers([("approval", approve), ("editing", edit)])
        self.assertEqual(result["editing"], "edited")
        rejected = self.start(authority, self.line_a, 90)
        self.assertFalse(rejected.get("operation_id"))
        self.assertFalse(self.operations())
        self.request.assert_not_called()

    def test_native_settlement_racing_report_cannot_duplicate_tip_or_finish_without_proof(self):
        authority = self.prepare([(self.line_a, 100)])
        first = self.start(authority, self.line_a, 100)
        self.providers[first["order_id"]]["tip"] = 300
        self.report_status = "processing"
        self.assertTrue(self.poll(first["operation_id"], self.line_a)["awaiting_tip_details"])
        self.report_status = "completed"
        payload = {"uuid": self.order_uuid, "session_id": self.session_id, "state": "paid",
            "date_order": fields.Datetime.to_string(fields.Datetime.now()), "sequence_number": 1,
            "name": f"Order {self.order_uuid}", "amount_total": 103, "amount_paid": 103,
            "amount_tax": 0, "amount_return": 0, "to_invoice": False,
            "lines": [], "payment_ids": []}
        barrier = Barrier(2)

        def verify():
            barrier.wait(timeout=10)
            return self.poll(first["operation_id"], self.line_a)

        def settle():
            barrier.wait(timeout=10)
            return self.rpc("pos.order", "sync_from_ui", [dict(payload)])

        result = self.workers([("verification", verify), ("settlement", settle)])
        self.assertEqual(self.poll(first["operation_id"], self.line_a)["state"], "verified")
        if result["settlement"].get("error"):
            self.rpc("pos.order", "sync_from_ui", [dict(payload)])
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(self.order_id)
            self.assertEqual(order.state, "paid")
            self.assertEqual(order.amount_total, 103)
            self.assertEqual(order.amount_paid, 103)
            self.assertEqual(len(order.payment_ids), 1)
            self.assertEqual(len(order.lines.filtered(lambda line: line.product_id == order.config_id.tip_product_id)), 1)
        self.assertEqual(len(self.operations()), 1)
        self.assertEqual(len(self.financial_posts()), 2)

    def test_cash_correction_racing_remaining_reservation_preserves_net_capacity(self):
        cash_uuid = str(uuid4())
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(self.order_id)
            order.session_id.state = "closed"
            journal = env["account.journal"].create({"name": "Concurrent cash correction",
                "code": f"R{uuid4().hex[:4]}", "type": "cash", "company_id": order.company_id.id})
            cash = env["pos.payment.method"].create({"name": "Concurrent cash", "journal_id": journal.id})
            order.config_id.payment_method_ids = [Command.link(cash.id)]
            order.session_id.state = "opened"
            order.payment_ids = [Command.create({"uuid": cash_uuid, "payment_method_id": cash.id, "amount": 30})]
            cash_method_id = cash.id
            cursor.commit()

        def plan(cash_amount, second_amount, version=0):
            return self.rpc("pos.order", "revolut_prepare_payment", self.order_id, self.order_uuid, version,
                [{"uuid": cash_uuid, "payment_method_id": cash_method_id, "amount": cash_amount},
                 {"uuid": self.line_a, "payment_method_id": self.method_id, "amount": 40},
                 {"uuid": self.line_b, "payment_method_id": self.method_id, "amount": second_amount}])

        authority = plan(30, 30)
        first = self.start(authority, self.line_a, 40)
        self.assertEqual(self.poll(first["operation_id"], self.line_a)["state"], "verified")
        barrier = Barrier(2)

        def reserve_old():
            barrier.wait(timeout=10)
            return self.start(authority, self.line_b, 30)

        def correct():
            barrier.wait(timeout=10)
            return plan(20, 40, authority["cart_version"])

        result = self.workers([("reservation", reserve_old), ("cash-correction", correct)])
        revised = result["cash-correction"]
        if revised.get("authorization_id"):
            self.start(revised, self.line_b, 40)
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, SUPERUSER_ID, self.context)
            order = env["pos.order"].browse(self.order_id)
            cash_minor = round(sum(order.payment_ids.filtered("payment_method_id.is_cash_count").mapped("amount")) * 100)
            self.assertLessEqual(cash_minor + sum(item["amount_minor"] for item in self.operations()), 10000)
            self.assertIn(cash_minor, (2000, 3000))
        self.assertEqual(len(self.operations()), 2)
        self.assertEqual(len(self.financial_posts()), 4)

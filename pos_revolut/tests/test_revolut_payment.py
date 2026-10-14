import os
import json
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Thread
from unittest import SkipTest
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, Command, api, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger
from odoo.service.model import call_kw

from ..models.financial_snapshot import FinancialSnapshotError, normalize_snapshot
from .authorization_fixtures import authorized_start, financial_posts, install_zero_reports, native_products


class TestRevolutPayment(TransactionCase):
    LOCATION_ID = "123e4567-e89b-12d3-a456-426614174000"
    ORDER_ID = "d40466e0-2188-41d0-bebb-aa3a930663a8"
    INTENT_ID = "4ca74d24-7b42-451a-91fb-8aca308e2630"
    PAYMENT_ID = "2c2f3842-c34d-4cc3-a0fc-9ae40b04dfbf"
    TERMINAL_ID = "0e53f673-7705-473a-a263-89a3e7647c3d"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Revolut payment test",
                "payment_method_type": "terminal",
                "use_payment_terminal": "revolut",
                "revolut_environment": "sandbox",
                "revolut_location_id": cls.LOCATION_ID,
                "revolut_terminal_id": cls.TERMINAL_ID,
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_PAYMENT_TEST",
            }
        )
        cls.config = cls.env["pos.config"].create(
            {
                "name": "Revolut payment test",
                "payment_method_ids": [Command.link(cls.payment_method.id)],
                "auto_validate_terminal_payment": True,
            }
        )
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "state": "opened"}
        )
        cls.product = native_products(cls.env, cls.config)

    def setUp(self):
        super().setUp()
        # Reuse the isolated test transaction for cursors explicitly owned by
        # the addon. Production still opens and commits independent cursors.
        registry_test_mode = self.enter_registry_test_mode()
        registry_test_mode.__enter__()
        self.addCleanup(registry_test_mode.__exit__, None, None, None)
        self.revolut_order_id = str(uuid4())
        self.revolut_intent_id = str(uuid4())
        self.revolut_payment_id = str(uuid4())

    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _financial_snapshot(self, order_uuid):
        return {
            "pricelist_id": self.config.pricelist_id.id,
            "fiscal_position_id": False,
            "lines": [{
                "uuid": order_uuid, "product_id": self.product.id,
                "qty": 1, "price_unit": 12.34, "discount": 0,
                "tax_ids": [],
            }],
        }

    def _start(self, order_uuid, payment_line_uuid, amount=12.34):
        return authorized_start(self.payment_method,
            self.session.id,
            order_uuid,
            payment_line_uuid,
            amount,
            self.config.currency_id.id,
            False,
            self._financial_snapshot(order_uuid),
        )

    def _eligible_terminal(self):
        return self._response(
            {
                "terminals": [
                    {
                        "id": self.TERMINAL_ID,
                        "online": True,
                        "operation_mode": "pos",
                        "location_id": self.LOCATION_ID,
                    }
                ]
            }
        )

    def _start_responses(self):
        return [
            self._eligible_terminal(),
            self._response({"id": self.revolut_order_id}),
            self._response({"id": self.revolut_intent_id, "state": "pending"}),
        ]

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_new_payment_requires_original_financial_contents(self, request):
        with self.assertRaises(UserError):
            self.payment_method.revolut_start_payment(
                self.session.id, str(uuid4()), str(uuid4()), 12.34,
                self.config.currency_id.id,
            )
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_terminal_cannot_start_from_another_pos_session(self, request):
        other_method = self.env["pos.payment.method"].create({
            "name": "Other POS terminal",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": self.LOCATION_ID,
            "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_PAYMENT_TEST",
        })
        other_config = self.env["pos.config"].create({
            "name": "Other POS session",
            "payment_method_ids": [Command.link(other_method.id)],
            "auto_validate_terminal_payment": True,
        })
        other_session = self.env["pos.session"].create({
            "config_id": other_config.id, "state": "opened",
        })
        order_uuid, line_uuid = str(uuid4()), str(uuid4())

        with self.assertRaises(UserError):
            authorized_start(self.payment_method,
                other_session.id, order_uuid, line_uuid, 12.34,
                other_config.currency_id.id, False,
                self._financial_snapshot(order_uuid),
            )
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_unresolved_order_blocks_another_terminal(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = self._start_responses()
        started = self._start(order_uuid, line_uuid)
        second = self.env["pos.payment.method"].create({
            "name": "Second Revolut terminal",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": self.LOCATION_ID,
            "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_PAYMENT_TEST",
        })
        second_config = self.env["pos.config"].create({
            "name": "Second Revolut POS",
            "payment_method_ids": [Command.link(second.id)],
            "auto_validate_terminal_payment": True,
        })
        second_session = self.env["pos.session"].create({
            "config_id": second_config.id, "state": "opened",
        })

        second_line_uuid = str(uuid4())
        # An exposed cart retains its original POS ownership and authority.
        with self.assertRaises(UserError):
            authorized_start(second, second_session.id, order_uuid, second_line_uuid,
                             12.34, second_config.currency_id.id, False,
                             self._financial_snapshot(order_uuid))
        self.assertFalse(second.revolut_find_payment(order_uuid, second_line_uuid))
        self.assertEqual(
            self.payment_method.revolut_find_payment(order_uuid, line_uuid),
            started,
        )
        self.assertEqual(len(financial_posts(request)), 2)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_scheduled_reconciliation_verifies_payment_without_browser(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response({
                "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
                "state": "completed", "payment_id": self.revolut_payment_id,
            }),
            self._response({
                "id": self.revolut_payment_id, "order_id": self.revolut_order_id,
                "amount": 1234, "currency": self.config.currency_id.name,
                "state": "captured",
            }),
        ]
        started = self._start(order_uuid, line_uuid)

        self.env.ref("pos_revolut.ir_cron_reconcile_payments").method_direct_trigger()

        recovered = self.payment_method.revolut_find_payment(order_uuid, line_uuid)
        self.assertEqual(recovered["operation_id"], started["operation_id"])
        self.assertEqual(recovered["state"], "verified")
        self.assertEqual(recovered["payment_id"], self.revolut_payment_id)
        self.assertEqual(len(financial_posts(request)), 2)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_scheduled_network_error_backs_off_without_new_dispatch(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            requests.ConnectionError("temporary provider outage"),
        ]
        started = self._start(order_uuid, line_uuid)
        cron = self.env.ref("pos_revolut.ir_cron_reconcile_payments")
        cron.method_direct_trigger()
        after_error = self.payment_method.revolut_find_payment(order_uuid, line_uuid)
        operation = self.env["pos.revolut.payment.operation"].browse(started["operation_id"])
        operation.invalidate_recordset()
        self.assertEqual(after_error["state"], "unresolved")
        self.assertEqual(operation.reconcile_failures, 1)
        self.assertGreater(operation.next_reconcile_at, fields.Datetime.now())

        cron.method_direct_trigger()
        self.assertEqual(request.call_count, 4)
        self.assertEqual(len(financial_posts(request)), 2)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_scheduled_reconciliation_never_replays_lost_intent_creation(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [
            self._eligible_terminal(),
            self._response({"id": self.revolut_order_id}),
            requests.ConnectionError("lost intent response"),
        ]
        started = self._start(order_uuid, line_uuid)
        self.assertEqual(started["state"], "unresolved")

        self.env.ref("pos_revolut.ir_cron_reconcile_payments").method_direct_trigger()

        recovered = self.payment_method.revolut_find_payment(order_uuid, line_uuid)
        self.assertEqual(recovered["operation_id"], started["operation_id"])
        self.assertEqual(recovered["order_id"], self.revolut_order_id)
        self.assertFalse(recovered["payment_intent_id"])
        self.assertFalse(recovered["retry_safe"])
        self.assertEqual(request.call_count, 3)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_pending_cancellation_is_reconciled_and_not_repeated(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        intent = {"id": self.revolut_intent_id,
                  "order_id": self.revolut_order_id, "state": "pending"}
        request.side_effect = [
            *self._start_responses(), self._response(intent),
            self._response({}),
            self._response({**intent, "state": "cancelled"}),
        ]
        started = self._start(order_uuid, line_uuid)
        result = self.payment_method.revolut_cancel_payment(
            started["operation_id"], order_uuid, line_uuid
        )
        repeated = self.payment_method.revolut_cancel_payment(
            started["operation_id"], order_uuid, line_uuid
        )
        self.assertEqual(result["state"], "cancelled")
        self.assertTrue(result["retry_safe"])
        self.assertEqual(repeated, {**result, "observation_fresh": False})
        cancellations = [call for call in request.call_args_list
                         if call.args[1].endswith("/cancel")]
        self.assertEqual(len(cancellations), 1)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_safe_retry_retains_attempt_and_deduplicates_start(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response({"id": self.revolut_intent_id,
                            "order_id": self.revolut_order_id, "state": "cancelled"}),
        ]
        first = self._start(order_uuid, line_uuid)
        failed = self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        old_order = self.revolut_order_id
        self.revolut_order_id, self.revolut_intent_id = str(uuid4()), str(uuid4())
        request.side_effect = self._start_responses()
        retry = authorized_start(self.payment_method,
            self.session.id, order_uuid, line_uuid, 12.34,
            self.config.currency_id.id, first["operation_id"],
            self._financial_snapshot(order_uuid),
        )
        repeated = authorized_start(self.payment_method,
            self.session.id, order_uuid, line_uuid, 12.34,
            self.config.currency_id.id, first["operation_id"],
            self._financial_snapshot(order_uuid),
        )
        self.assertTrue(failed["retry_safe"])
        self.assertNotEqual(retry["operation_id"], first["operation_id"])
        self.assertEqual(repeated, retry)
        self.assertNotEqual(retry["order_id"], old_order)
        self.assertEqual(self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, line_uuid
        ), {**failed, "observation_fresh": False})
        self.assertEqual(len(financial_posts(request)), 4)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_processing_cancellation_and_unsafe_retry_do_not_dispatch(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [*self._start_responses(), self._response({
            "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
            "state": "processing",
        })]
        first = self._start(order_uuid, line_uuid)
        result = self.payment_method.revolut_cancel_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        self.assertEqual(result["provider_state"], "processing")
        self.assertFalse(result["retry_safe"])
        with self.assertRaises(UserError):
            authorized_start(self.payment_method,
                self.session.id, order_uuid, line_uuid, 12.34,
                self.config.currency_id.id, first["operation_id"],
                self._financial_snapshot(order_uuid),
            )
        with self.assertRaises(UserError):
            self._start(order_uuid, line_uuid, amount=99)
        second_line_uuid = str(uuid4())
        with self.assertRaisesRegex(UserError, "remaining order balance"):
            self._start(order_uuid, second_line_uuid)
        self.assertFalse(self.payment_method.revolut_find_payment(
            order_uuid, second_line_uuid
        ))
        self.assertEqual(len(financial_posts(request)), 2)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_lost_cancellation_is_unresolved_and_never_replayed(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        pending = {"id": self.revolut_intent_id,
                   "order_id": self.revolut_order_id, "state": "pending"}
        request.side_effect = [
            *self._start_responses(), self._response(pending),
            requests.Timeout("cancel response lost"),
            requests.ConnectionError("status unavailable"), self._response(pending),
        ]
        first = self._start(order_uuid, line_uuid)
        result = self.payment_method.revolut_cancel_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        self.assertEqual(result["state"], "unresolved")
        self.assertEqual(result["local_outcome"], "interrupted")
        self.assertFalse(result["retry_safe"])
        repeated = self.payment_method.revolut_cancel_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        self.assertFalse(repeated["retry_safe"])
        self.assertEqual(len([call for call in request.call_args_list
                              if call.args[1].endswith("/cancel")]), 1)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_cancel_rejection_reconciles_payment_success(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        intent = {"id": self.revolut_intent_id, "order_id": self.revolut_order_id}
        request.side_effect = [
            *self._start_responses(), self._response({**intent, "state": "pending"}),
            requests.HTTPError("processing now"),
            self._response({**intent, "state": "completed", "payment_id": self.revolut_payment_id}),
            self._response({"id": self.revolut_payment_id, "order_id": self.revolut_order_id,
                            "state": "captured", "amount": 1234,
                            "currency": self.config.currency_id.name}),
        ]
        first = self._start(order_uuid, line_uuid)
        result = self.payment_method.revolut_cancel_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        self.assertEqual(result["state"], "verified")
        self.assertFalse(result["retry_safe"])
        self.assertEqual(self.payment_method.revolut_mark_timeout(
            first["operation_id"], order_uuid, line_uuid
        ), result)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_lost_create_response_is_interrupted_and_blocks_retry(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [self._eligible_terminal(), requests.Timeout("lost response")]
        result = self._start(order_uuid, line_uuid)
        self.assertEqual(result["state"], "unresolved")
        self.assertEqual(result["local_outcome"], "interrupted")
        self.assertFalse(result["retry_safe"])
        with self.assertRaises(UserError):
            authorized_start(self.payment_method,
                self.session.id, order_uuid, line_uuid, 12.34,
                self.config.currency_id.id, result["operation_id"],
                self._financial_snapshot(order_uuid),
            )
        self.assertEqual(self._start(order_uuid, line_uuid), result)
        self.assertEqual(request.call_count, 2)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_pre_upgrade_unsuccessful_attempt_is_reconciled_before_retry(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = self._start_responses()
        first = self._start(order_uuid, line_uuid)
        # Ticket 03 persisted final failure but retained the order blocker and
        # had no retry_safe column. This is its state after a schema upgrade.
        operation = self.env["pos.revolut.payment.operation"].browse(first["operation_id"])
        operation.write({"state": "cancelled", "provider_state": "cancelled",
                         "blocking_terminal_key": False, "retry_safe": False})
        operation.flush_recordset()
        request.side_effect = [self._response({
            "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
            "state": "cancelled",
        })]
        result = self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        self.assertTrue(result["retry_safe"])
        self.revolut_order_id, self.revolut_intent_id = str(uuid4()), str(uuid4())
        request.side_effect = self._start_responses()
        retry = authorized_start(self.payment_method,
            self.session.id, order_uuid, line_uuid, 12.34,
            self.config.currency_id.id, first["operation_id"],
            self._financial_snapshot(order_uuid),
        )
        self.assertNotEqual(first["operation_id"], retry["operation_id"])
        self.assertEqual(retry["state"], "pending")

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_pre_upgrade_terminal_check_failure_remains_safe_without_dispatch(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = requests.ConnectionError("terminal discovery unavailable")
        first = self._start(order_uuid, line_uuid)
        operation = self.env["pos.revolut.payment.operation"].browse(first["operation_id"])
        operation.write({"retry_safe": False,
                         "blocking_order_key": f"{self.env.company.id}:{order_uuid}"})
        operation.flush_recordset()
        result = self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, line_uuid
        )
        self.assertEqual(result["state"], "failed")
        self.assertTrue(result["retry_safe"])
        self.assertEqual(request.call_count, 1)

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_deployment_guard_tracks_active_and_uncertain_operations(self, request):
        request.side_effect = self._start_responses()
        started = self._start(str(uuid4()), str(uuid4()))
        operation = self.env["pos.revolut.payment.operation"].browse(
            started["operation_id"]
        )

        self.assertTrue(operation.deployment_blocking)
        operation.write({"state": "failed"})
        self.assertFalse(operation.deployment_blocking)
        operation.write({"state": "unresolved"})
        self.assertTrue(operation.deployment_blocking)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_verified_partial_line_allows_a_second_revolut_allocation(self, request):
        order_uuid, first_uuid, second_uuid = str(uuid4()), str(uuid4()), str(uuid4())
        second_order_id, second_intent_id = str(uuid4()), str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response({
                "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
                "state": "completed", "payment_id": self.revolut_payment_id,
            }),
            self._response({
                "id": self.revolut_payment_id, "order_id": self.revolut_order_id,
                "state": "captured", "amount": 434,
                "currency": self.config.currency_id.name,
            }),
            self._eligible_terminal(),
            self._response({"id": second_order_id}),
            self._response({"id": second_intent_id, "state": "pending"}),
        ]
        first = self._start(order_uuid, first_uuid, amount=4.34)
        verified = self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, first_uuid
        )
        second = self._start(order_uuid, second_uuid, amount=8.00)

        self.assertEqual(verified["state"], "verified")
        self.assertEqual(second["state"], "pending")
        posts = financial_posts(request)
        self.assertEqual([call.kwargs["json"]["amount"] for call in posts],
                         [434, 434, 800, 800])
        self.assertEqual(posts[2].kwargs["json"]["metadata"]["pos_order_uuid"], order_uuid)
        self.assertEqual(posts[3].kwargs["json"]["terminal_id"], self.TERMINAL_ID)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_second_terminal_waits_for_first_line_then_starts(self, request):
        order_uuid, first_uuid, second_uuid = str(uuid4()), str(uuid4()), str(uuid4())
        second_terminal_id = str(uuid4())
        second_method = self.env["pos.payment.method"].create({
            "name": "Second split-tender terminal",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": self.LOCATION_ID,
            "revolut_terminal_id": second_terminal_id,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_PAYMENT_TEST",
        })
        self.config = self.env["pos.config"].create({
            "name": "Split tender with two Revolut terminals",
            "payment_method_ids": [
                Command.link(self.payment_method.id), Command.link(second_method.id),
            ],
            "auto_validate_terminal_payment": True,
        })
        self.session = self.env["pos.session"].create({
            "config_id": self.config.id, "state": "opened",
        })
        request.side_effect = [
            *self._start_responses(),
            self._response({
                "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
                "state": "completed", "payment_id": self.revolut_payment_id,
            }),
            self._response({
                "id": self.revolut_payment_id, "order_id": self.revolut_order_id,
                "state": "captured", "amount": 434,
                "currency": self.config.currency_id.name,
            }),
            self._response({"terminals": [{
                "id": second_terminal_id, "online": True,
                "operation_mode": "pos", "location_id": self.LOCATION_ID,
            }]}),
            self._response({"id": str(uuid4())}),
            self._response({"id": str(uuid4()), "state": "pending"}),
        ]
        first = self._start(order_uuid, first_uuid, amount=4.34)
        rejected = authorized_start(second_method,
            self.session.id, order_uuid, second_uuid, 8.00,
            self.config.currency_id.id, False,
            self._financial_snapshot(order_uuid),
        )
        self.assertEqual(rejected, {
            "start_rejected": "terminal_busy",
            "dispatched": False,
            "order_uuid": order_uuid,
            "payment_line_uuid": second_uuid,
            "previous_operation_id": False,
        })
        self.assertEqual(request.call_count, 3)
        verified = self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, first_uuid
        )
        second = authorized_start(second_method,
            self.session.id, order_uuid, second_uuid, 8.00,
            self.config.currency_id.id, False,
            self._financial_snapshot(order_uuid),
        )
        self.assertEqual(verified["state"], "verified")
        self.assertEqual(second["state"], "pending")
        self.assertNotEqual(first["operation_id"], second["operation_id"])
        posts = financial_posts(request)
        self.assertEqual([call.kwargs["json"]["amount"] for call in posts],
                         [434, 434, 800, 800])
        self.assertEqual(posts[-1].kwargs["json"]["terminal_id"], second_terminal_id)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_verified_line_blocks_new_charge_after_cart_edit(self, request):
        order_uuid, first_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response({
                "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
                "state": "completed", "payment_id": self.revolut_payment_id,
            }),
            self._response({
                "id": self.revolut_payment_id, "order_id": self.revolut_order_id,
                "state": "captured", "amount": 434,
                "currency": self.config.currency_id.name,
            }),
        ]
        first = self._start(order_uuid, first_uuid, amount=4.34)
        self.payment_method.revolut_poll_payment(first["operation_id"], order_uuid, first_uuid)
        changed = self._financial_snapshot(order_uuid)
        changed["lines"][0]["qty"] = 2

        calls_before_edit = request.call_count
        with self.assertRaisesRegex(UserError, "contents cannot be changed"):
            authorized_start(self.payment_method,
                self.session.id, order_uuid, str(uuid4()), 8.00,
                self.config.currency_id.id, False, changed,
            )
        self.assertEqual(request.call_count, calls_before_edit)

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_success_is_idempotent_and_uses_currency_exponent(
        self, request
    ):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response(
                {
                    "id": self.revolut_intent_id,
                    "order_id": self.revolut_order_id,
                    "state": "completed",
                    "payment_id": self.revolut_payment_id,
                }
            ),
            self._response(
                {
                    "id": self.revolut_payment_id,
                    "order_id": self.revolut_order_id,
                    "state": "captured",
                    "amount": 1234,
                    "currency": self.config.currency_id.name,
                }
            ),
        ]

        started = self._start(order_uuid, payment_line_uuid)
        duplicate = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_poll_payment(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(started["state"], "pending")
        self.assertEqual(duplicate["operation_id"], started["operation_id"])
        self.assertEqual(completed["state"], "verified")
        self.assertEqual(completed["payment_id"], self.revolut_payment_id)
        posts = financial_posts(request)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].kwargs["json"]["amount"], 1234)
        self.assertEqual(posts[1].kwargs["json"]["amount"], 1234)
        self.assertEqual(posts[0].kwargs["json"]["metadata"], {
            "pos_partner_name": "davai-akae-integration",
            "pos_order_uuid": order_uuid,
            "pos_payment_line_uuid": payment_line_uuid,
        })

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_completed_intent_with_failed_payment_is_not_success(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response(
                {
                    "id": self.revolut_intent_id,
                    "order_id": self.revolut_order_id,
                    "state": "completed",
                    "payment_id": self.revolut_payment_id,
                }
            ),
            self._response(
                {
                    "id": self.revolut_payment_id,
                    "order_id": self.revolut_order_id,
                    "state": "failed",
                    "amount": 1234,
                    "currency": self.config.currency_id.name,
                }
            ),
        ]

        started = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_poll_payment(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(completed["state"], "failed")
        self.assertEqual(completed["payment_id"], self.revolut_payment_id)

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_declined_payment_is_not_success(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response(
                {
                    "id": self.revolut_intent_id,
                    "order_id": self.revolut_order_id,
                    "state": "completed",
                    "payment_id": self.revolut_payment_id,
                }
            ),
            self._response(
                {
                    "id": self.revolut_payment_id,
                    "order_id": self.revolut_order_id,
                    "state": "declined",
                    "amount": 1234,
                    "currency": self.config.currency_id.name,
                }
            ),
        ]

        started = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_poll_payment(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(completed["state"], "declined")
        self.assertEqual(completed["payment_id"], self.revolut_payment_id)

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_cancelled_intent_is_not_success(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response(
                {
                    "id": self.revolut_intent_id,
                    "order_id": self.revolut_order_id,
                    "state": "cancelled",
                }
            ),
        ]

        started = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_poll_payment(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(completed["state"], "cancelled")
        self.assertFalse(completed["payment_id"])

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_poll_transport_interruption_stays_unresolved(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            requests.ConnectionError("simulated polling interruption"),
        ]

        started = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_poll_payment(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(completed["state"], "unresolved")
        self.assertFalse(completed["retry_safe"])

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_foreground_timeout_stays_unresolved(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = self._start_responses()

        started = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_mark_timeout(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(completed["state"], "unresolved")
        self.assertFalse(completed["retry_safe"])
        operation = self.env["pos.revolut.payment.operation"].browse(started["operation_id"])
        operation.invalidate_recordset()
        self.assertLessEqual(
            operation.next_reconcile_at,
            fields.Datetime.now() + timedelta(seconds=60),
        )

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_payment_reference_mismatch_stays_unresolved(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            *self._start_responses(),
            self._response(
                {
                    "id": self.revolut_intent_id,
                    "order_id": self.revolut_order_id,
                    "state": "completed",
                    "payment_id": self.revolut_payment_id,
                }
            ),
            self._response(
                {
                    "id": self.revolut_payment_id,
                    "order_id": str(uuid4()),
                    "state": "captured",
                    "amount": 1234,
                    "currency": self.config.currency_id.name,
                }
            ),
        ]

        started = self._start(order_uuid, payment_line_uuid)
        completed = self.payment_method.revolut_poll_payment(
            started["operation_id"], order_uuid, payment_line_uuid
        )

        self.assertEqual(completed["state"], "unresolved")
        self.assertFalse(completed["retry_safe"])

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_crash_after_order_dispatch_keeps_claim_and_blocks_replay(self, request):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        request.side_effect = [
            self._eligible_terminal(),
            self._response({"id": self.revolut_order_id}),
        ]

        with patch.object(
            type(self.payment_method),
            "_apply_revolut_observation_owned",
            autospec=True,
            side_effect=RuntimeError("simulated crash after HTTP dispatch"),
        ):
            try:
                self._start(order_uuid, payment_line_uuid)
            except RuntimeError:
                pass
            else:
                self.fail("The simulated post-dispatch crash did not propagate")
            visible = self.payment_method.revolut_find_payment(
                order_uuid, payment_line_uuid
            )
            replay = self._start(order_uuid, payment_line_uuid)

        operation = self.env["pos.revolut.payment.operation"].search(
            [
                ("order_uuid", "=", order_uuid),
                ("payment_line_uuid", "=", payment_line_uuid),
            ]
        )
        dispatch = self.env["pos.revolut.payment.dispatch"].search(
            [("operation_id", "=", operation.id), ("action", "=", "create_order")]
        )
        self.assertEqual(replay["state"], "unresolved")
        self.assertEqual(visible["state"], "unresolved")
        self.assertEqual(visible["operation_id"], operation.id)
        self.assertEqual(operation.state, "dispatching_order")
        self.assertFalse(dispatch.completed_at)
        self.assertEqual(request.call_count, 2)

    @patch.dict(
        os.environ,
        {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only-not-a-credential"},
    )
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_start_requires_standard_automatic_terminal_validation(self, request):
        self.config.auto_validate_terminal_payment = False

        with self.assertRaises(UserError):
            self._start(str(uuid4()), str(uuid4()))

        request.assert_not_called()

    def test_operation_amount_and_currency_are_immutable(self):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        values = self.payment_method._revolut_operation_values(
            self.session,
            self.config.currency_id,
            12.34,
            1234,
            order_uuid,
            payment_line_uuid,
        )
        operation = self.env["pos.revolut.payment.operation"].sudo().create(values)

        with self.assertRaises(ValidationError):
            operation.write({"amount_minor": 999})

    def test_minor_units_follow_currency_exponent(self):
        currency = self.env["res.currency"].create(
            {"name": "XTS", "symbol": "x", "rounding": 0.001}
        )

        _normalized, amount_minor = self.env[
            "pos.revolut.payment.operation"
        ].normalize_amount(currency, "12.345")

        self.assertEqual(amount_minor, 12345)

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_operation_from_another_company_is_not_pollable(self, request):
        other_company = self.env["res.company"].create({"name": "Other payment company"})
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        values = self.payment_method._revolut_operation_values(
            self.session,
            self.config.currency_id,
            12.34,
            1234,
            order_uuid,
            payment_line_uuid,
        )
        values.update({"company_id": other_company.id, "state": "unresolved"})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["pos.revolut.payment.operation"].sudo().create(values)
        values["company_id"] = self.env.company.id
        operation = self.env["pos.revolut.payment.operation"].sudo().create(values)
        # Simulate an inconsistent historical row: new operations cannot be
        # created this way, but recovery must reject legacy evidence as well.
        self.cr.execute(
            "UPDATE pos_revolut_payment_operation SET company_id = %s WHERE id = %s",
            [other_company.id, operation.id],
        )
        operation.invalidate_recordset()

        with self.assertRaises(AccessError):
            self.payment_method.with_context(
                allowed_company_ids=[self.env.company.id]
            ).revolut_poll_payment(
                operation.id, order_uuid, payment_line_uuid
            )
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_manager_associates_lost_references_and_verifies_payment(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        request.side_effect = [self._eligible_terminal(), requests.Timeout()]
        started = self._start(order_uuid, line_uuid)
        self.assertEqual(started["state"], "unresolved")
        operation = self.env["pos.revolut.payment.operation"].browse(
            started["operation_id"]
        )
        request.side_effect = [
            self._response({
                "id": self.revolut_order_id, "amount": 1234,
                "currency": self.config.currency_id.name,
                "location_id": self.LOCATION_ID,
                "metadata": {
                    "pos_order_uuid": order_uuid,
                    "pos_payment_line_uuid": line_uuid,
                },
            }),
            self._response({
                "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
                "amount": 1234, "currency": self.config.currency_id.name,
                "terminal_id": self.TERMINAL_ID, "state": "completed",
                "payment_id": self.revolut_payment_id,
            }),
            self._response({
                "id": self.revolut_intent_id, "order_id": self.revolut_order_id,
                "state": "completed", "payment_id": self.revolut_payment_id,
            }),
            self._response({
                "id": self.revolut_payment_id, "order_id": self.revolut_order_id,
                "amount": 1234, "currency": self.config.currency_id.name,
                "state": "captured",
            }),
        ]
        manager = new_test_user(
            self.env, login="revolut_lost_id_manager",
            groups="point_of_sale.group_pos_manager",
            company_id=self.env.company.id,
        )
        self.config.sudo().write({"revolut_user_ids": [Command.link(manager.id)]})
        install_zero_reports(self.env, request)
        operation.with_user(manager).action_revolut_associate(
            self.revolut_order_id, self.revolut_intent_id
        )
        operation.with_user(manager).action_revolut_reconcile()
        operation.invalidate_recordset()
        self.assertEqual(operation.state, "verified")
        self.assertEqual(operation.revolut_payment_id, self.revolut_payment_id)
        self.assertEqual(
            operation.audit_ids.mapped("action"), ["associate", "reconcile"]
        )
        self.assertEqual(operation.audit_ids.mapped("actor_id"), manager)


    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_cashier_snapshot_expansion_rejected_before_dispatch(self, request):
        cashier = new_test_user(
            self.env, login="snapshot_bounds_cashier",
            groups="base.group_user,point_of_sale.group_pos_user", company_id=self.env.company.id,
        )
        self.config.sudo().write({"revolut_user_ids": [Command.link(cashier.id)]})
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        snapshot = self._financial_snapshot(order_uuid)
        snapshot["lines"][0].update(qty="1e1000", price_unit="1e-1000", discount="1e1000")
        request.side_effect = self._start_responses()
        with self.assertRaises(UserError):
            call_kw(self.payment_method.with_user(cashier), "revolut_start_payment", [
                [self.payment_method.id], self.session.id, order_uuid, line_uuid,
                12.34, self.config.currency_id.id, False, snapshot,
            ], {})
        with self.assertRaises(FinancialSnapshotError):
            normalize_snapshot(snapshot)
        self.assertFalse(self.payment_method.with_user(cashier).revolut_find_payment(order_uuid, line_uuid))
        self.assertFalse(self.env["pos.revolut.order.lock"].sudo().search([
            ("order_uuid", "=", order_uuid),
        ]))
        request.assert_not_called()

    def test_snapshot_normalizer_not_rpc_callable(self):
        for role, groups in (
            ("cashier", "base.group_user,point_of_sale.group_pos_user"),
            ("manager", "base.group_user,point_of_sale.group_pos_manager"),
            ("internal", "base.group_user"),
            ("portal", "base.group_portal"),
        ):
            user = new_test_user(self.env, login=f"snapshot_rpc_{role}", groups=groups)
            with self.subTest(role=role):
                with self.assertRaises(AttributeError):
                    call_kw(self.env["pos.revolut.payment.operation"].with_user(user),
                            "normalize_financial_snapshot", [self._financial_snapshot(str(uuid4()))], {})
                with self.assertRaises(AccessError):
                    call_kw(self.env["pos.revolut.payment.operation"].with_user(user),
                            "_normalize_financial_snapshot", [self._financial_snapshot(str(uuid4()))], {})


    def _snapshot_bounds_and_unbound_rpc(self, snapshot, order_uuid=None, line_uuid=None):
        # The removed amount+snapshot entry point must refuse every request.
        # Retain the numeric/resource regression controls at the existing pure
        # normalization seam; its result alone supplies no payment authority.
        order_uuid, line_uuid = order_uuid or str(uuid4()), line_uuid or str(uuid4())
        with self.assertRaises(UserError):
            call_kw(self.payment_method, "revolut_start_payment", [
                [self.payment_method.id], self.session.id, order_uuid,
                line_uuid, 12.34, self.config.currency_id.id, False, snapshot,
            ], {})
        try:
            normalized = normalize_snapshot(snapshot)
        except FinancialSnapshotError as error:
            if self.payment_method.revolut_find_payment(order_uuid, line_uuid):
                raise
            return {"start_rejected": "snapshot_invalid", "dispatched": False,
                    "message": str(error), "payment_line_uuid": line_uuid}
        return {"financial_snapshot": normalized, "dispatched": False}

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_snapshot_numeric_representations_rejected_without_expansion(self, request):
        # Capped text only; never allocate the expanded adversarial result.
        invalid = ["1e1000", "1e-1000", "-1e1000", "-1e-1000", "1e325", "1e-325",
                   "1" * 65, "0.12345678901234567890123456789", "NaN", "Infinity",
                   "-Infinity", "1_000", " 1", "1/2", True, False, None, "", [], {}, [1], {"value": 1}]
        for field in ("qty", "price_unit", "discount"):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    snapshot = self._financial_snapshot(str(uuid4()))
                    snapshot["lines"][0][field] = value
                    with patch("odoo.addons.pos_revolut.models.financial_snapshot.Decimal",
                               wraps=Decimal) as parsing:
                        result = self._snapshot_bounds_and_unbound_rpc(snapshot)
                    self.assertEqual(result["start_rejected"], "snapshot_invalid")
                    self.assertNotIn(str(value), [call.args[0] for call in parsing.call_args_list])
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_snapshot_cart_count_rejected_before_iteration(self, request):
        class NoTraversal(list):
            def __iter__(self):
                raise AssertionError("Oversized cart was traversed")
        snapshot = self._financial_snapshot(str(uuid4()))
        snapshot["lines"] = NoTraversal([None] * 1001)
        self.assertEqual(self._snapshot_bounds_and_unbound_rpc(snapshot)["start_rejected"], "snapshot_invalid")
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_snapshot_collection_and_retained_scalar_limits(self, request):
        invalid = (
            {"uuid": "x" * 129}, {"uuid": ["bad"]}, {"product_id": "1" * 65},
            {"product_id": 2147483648}, {"refunded_orderline_id": "1" * 65},
            {"tax_ids": [1] * 101}, {"tax_ids": [[6, 0, [1] * 101]]},
            {"tax_ids": [[6]]}, {"tax_ids": [[6, 0, []], [6, 0, []]]},
            {"tax_ids": [2147483648]}, {"qty": None}, {"price_unit": None},
        )
        for changes in invalid:
            with self.subTest(changes=changes):
                snapshot = self._financial_snapshot(str(uuid4()))
                snapshot["lines"][0].update(changes)
                self.assertEqual(self._snapshot_bounds_and_unbound_rpc(snapshot)["start_rejected"], "snapshot_invalid")
        for lines in ([], [[0]], [[6, 0, {}]], [None]):
            with self.subTest(lines=lines):
                snapshot = dict(self._financial_snapshot(str(uuid4())), lines=lines)
                self.assertEqual(self._snapshot_bounds_and_unbound_rpc(snapshot)["start_rejected"], "snapshot_invalid")
        for changes in ({"amount_total": "1e1000"}, {"pricelist_id": "1" * 65},
                        {"fiscal_position_id": 2147483648}, {"restaurant": {"preset_id": "1" * 65}},
                        {"restaurant": {"table_id": 2147483648}}):
            with self.subTest(changes=changes):
                snapshot = dict(self._financial_snapshot(str(uuid4())), **changes)
                self.assertEqual(self._snapshot_bounds_and_unbound_rpc(snapshot)["start_rejected"], "snapshot_invalid")
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_snapshot_valid_numeric_boundaries_remain_canonical(self, request):
        request.return_value = self._response({"terminals": []})
        controls = (
            ("qty", "1000000000", "1000000000"), ("qty", "-1000000000", "-1000000000"),
            ("price_unit", "1000000000", "1000000000"),
            ("price_unit", "-1000000000", "-1000000000"),
            ("discount", "1000000", "1000000"), ("discount", "-1000000", "-1000000"),
            ("qty", "-0.001", "-0.001"), ("qty", "-0.5", "-0.5"),
            ("qty", 0.30000000000000004, "0.30000000000000004"),
            ("price_unit", "1.234e1", "12.34"), ("discount", "17.7333333333", "17.7333333333"),
            ("qty", "0.1234567890123456789012345678", "0.1234567890123456789012345678"),
            ("qty", "5e-324", "0." + "0" * 323 + "5"),
            ("qty", "0.1234567890123456789012345678e-324",
             "0." + "0" * 324 + "1234567890123456789012345678"),
            ("qty", "-0", "-0"), ("qty", "0e324", "0"),
            ("qty", "0" * 63 + "1", "1"),
        )
        for field, value, expected in controls:
            with self.subTest(field=field, value=value):
                snapshot = self._financial_snapshot(str(uuid4()))
                snapshot["lines"][0][field] = value
                result = self._snapshot_bounds_and_unbound_rpc(snapshot)
                self.assertEqual(result["financial_snapshot"]["lines"][0][field], expected)
        for field, value in (("qty", "-0.1234567890123456789012345678e-324"),
                             ("qty", "1000000000.000000001"), ("qty", "-1000000000.000000001"),
                             ("price_unit", "1000000000.000000001"),
                             ("price_unit", "-1000000000.000000001"),
                             ("discount", "1000000.000000001"), ("discount", "-1000000.000000001")):
            with self.subTest(outside=field, value=value):
                snapshot = self._financial_snapshot(str(uuid4()))
                snapshot["lines"][0][field] = value
                self.assertEqual(self._snapshot_bounds_and_unbound_rpc(snapshot)["start_rejected"], "snapshot_invalid")
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_snapshot_aggregate_budget_includes_taxes_and_return_ids(self, request):
        # 1000 compact, valid lines fit; a 200-line bounded cart with 100 taxes
        # each crosses the 256 KiB aggregate without numeric expansion.
        request.return_value = self._response({"terminals": []})
        snapshot = self._financial_snapshot(str(uuid4()))
        template = snapshot["lines"][0]
        snapshot["lines"] = [dict(template, uuid=str(i)) for i in range(1000)]
        result = self._snapshot_bounds_and_unbound_rpc(snapshot)
        stored = result["financial_snapshot"]
        self.assertEqual(len(stored["lines"]), 1000)
        self.assertLessEqual(len(json.dumps(stored)), 256 * 1024)
        request.reset_mock()
        template = dict(template, uuid="x" * 126, tax_ids=[2147483647] * 100,
                        refunded_orderline_id=2147483647)
        snapshot["lines"] = [dict(template, uuid=f"{i:03d}" + "x" * 125) for i in range(200)]
        result = self._snapshot_bounds_and_unbound_rpc(snapshot)
        self.assertEqual(result["start_rejected"], "snapshot_invalid")
        self.assertIn("256 KiB", result["message"])
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_snapshot_exact_retained_budget_boundary(self, request):
        request.return_value = self._response({"terminals": []})
        snapshot = self._financial_snapshot(str(uuid4()))
        snapshot.update(pricelist_id=2147483647, fiscal_position_id=2147483647)
        template = dict(snapshot["lines"][0], product_id=1, tax_ids=[2147483647] * 100,
                        refunded_orderline_id=2147483647)
        snapshot["lines"] = [dict(template, uuid=f"{i:03d}" + "x" * 125) for i in range(180)]
        # Default JSON is exactly 262,144 bytes: 180 bounded lines, with
        # 76 fewer taxes on the last line and three escaped identifier quotes.
        snapshot["lines"][-1].update(tax_ids=[2147483647] * 24,
                                      uuid="179" + "x" * 122 + '"' * 3)
        accepted = self._snapshot_bounds_and_unbound_rpc(snapshot)
        stored = accepted["financial_snapshot"]
        self.assertEqual(len(json.dumps(stored)), 262144)
        request.reset_mock()
        snapshot["lines"][-1]["uuid"] = "179" + "x" * 121 + '"' * 4
        rejected = self._snapshot_bounds_and_unbound_rpc(snapshot)
        self.assertEqual(rejected["start_rejected"], "snapshot_invalid")
        self.assertIn("256 KiB", rejected["message"])
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_PAYMENT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_rejected_snapshot_can_be_corrected_but_uncertain_start_stays_guarded(self, request):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        snapshot = self._financial_snapshot(order_uuid)
        snapshot["lines"][0]["qty"] = "1e1000"
        rejected = self._snapshot_bounds_and_unbound_rpc(snapshot, order_uuid, line_uuid)
        self.assertEqual(rejected["payment_line_uuid"], line_uuid)
        request.assert_not_called()
        snapshot["lines"][0]["qty"] = 1
        request.side_effect = [self._eligible_terminal(), requests.Timeout()]
        uncertain = self._start(order_uuid, line_uuid)
        self.assertEqual(uncertain["state"], "unresolved")
        request.reset_mock()
        snapshot["lines"][0]["qty"] = "1e-1000"
        with self.assertRaises(UserError):
            self._snapshot_bounds_and_unbound_rpc(snapshot, order_uuid, line_uuid)
        request.assert_not_called()
        self.assertEqual(self.payment_method.revolut_find_payment(order_uuid, line_uuid), uncertain)
        self.assertEqual(self.env["pos.revolut.payment.operation"].sudo().search_count([
            ("order_uuid", "=", order_uuid),
        ]), 1)


@tagged("post_install", "-at_install")
class TestRevolutConcurrentStart(TransactionCase):
    def test_competing_start_dispatch_claims_are_atomic(self):
        location_id = str(uuid4())
        terminal_id = str(uuid4())
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        company_id = self.env.company.id
        with self.env.registry.cursor() as cursor:
            setup_env = api.Environment(
                cursor,
                SUPERUSER_ID,
                {"allowed_company_ids": [company_id]},
            )
            payment_method = setup_env["pos.payment.method"].create(
                {
                    "name": "Revolut concurrent start test",
                    "payment_method_type": "terminal",
                    "use_payment_terminal": "revolut",
                    "revolut_environment": "sandbox",
                    "revolut_location_id": location_id,
                    "revolut_terminal_id": terminal_id,
                    "revolut_fulfilment_type": "eat_in",
                    "revolut_secret_reference": (
                        "ODOO_REVOLUT_SECRET_CONCURRENCY_TEST"
                    ),
                }
            )
            config = setup_env["pos.config"].create(
                {
                    "name": "Revolut concurrent start test",
                    "payment_method_ids": [Command.link(payment_method.id)],
                    "auto_validate_terminal_payment": True,
                }
            )
            session = setup_env["pos.session"].create(
                {"config_id": config.id, "state": "opened"}
            )
            operation = setup_env["pos.revolut.payment.operation"].create(
                {
                    "payment_method_id": payment_method.id,
                    "company_id": company_id,
                    "pos_config_id": config.id,
                    "pos_session_id": session.id,
                    "order_uuid": order_uuid,
                    "payment_line_uuid": payment_line_uuid,
                    "amount": 12.34,
                    "amount_minor": 1234,
                    "currency_id": config.currency_id.id,
                    "currency_code": config.currency_id.name,
                    "environment": "sandbox",
                    "location_id": location_id,
                    "terminal_id": terminal_id,
                    "fulfilment_type": "eat_in",
                    "secret_reference": "ODOO_REVOLUT_SECRET_CONCURRENCY_TEST",
                    "blocking_order_key": f"{company_id}:{order_uuid}",
                    "blocking_terminal_key": (
                        f"{company_id}:sandbox:{terminal_id}"
                    ),
                }
            )
            operation_id = operation.id
            cursor.commit()

        barrier = Barrier(2)
        claimed = []
        errors = []

        def claim_dispatch():
            try:
                with self.env.registry.cursor() as cursor:
                    try:
                        barrier.wait()
                        cursor.execute(
                            "SELECT id FROM pos_revolut_payment_operation "
                            "WHERE id = %s FOR UPDATE",
                            [operation_id],
                        )
                        cursor.execute(
                            "SELECT id FROM pos_revolut_payment_dispatch "
                            "WHERE operation_id = %s AND action = %s",
                            [operation_id, "create_order"],
                        )
                        if cursor.fetchone():
                            claimed.append(False)
                        else:
                            cursor.execute(
                                "INSERT INTO pos_revolut_payment_dispatch "
                                "(operation_id, action, claimed_at, create_uid, "
                                "create_date, write_uid, write_date) "
                                "VALUES (%s, %s, NOW() AT TIME ZONE 'UTC', %s, "
                                "NOW() AT TIME ZONE 'UTC', %s, "
                                "NOW() AT TIME ZONE 'UTC')",
                                [
                                    operation_id,
                                    "create_order",
                                    SUPERUSER_ID,
                                    SUPERUSER_ID,
                                ],
                            )
                            cursor.execute(
                                "UPDATE pos_revolut_payment_operation "
                                "SET state = %s WHERE id = %s",
                                ["dispatching_order", operation_id],
                            )
                            claimed.append(True)
                        cursor.commit()
                    except (IntegrityError, SerializationFailure):
                        cursor.rollback()
                        claimed.append(False)
            except Exception as error:  # noqa: BLE001 - propagate worker failures
                errors.append(error)

        workers = [Thread(target=claim_dispatch) for _index in range(2)]
        with mute_logger("odoo.sql_db"):
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(timeout=15)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertFalse(errors)
        self.assertCountEqual(claimed, [True, False])
        with self.env.registry.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM pos_revolut_payment_dispatch "
                "WHERE operation_id = %s",
                [operation_id],
            )
            self.assertEqual(cursor.fetchone()[0], 1)


@tagged("post_install", "-at_install")
class TestRevolutOrderSettlement(CommonPosTest):
    LOCATION_ID = TestRevolutPayment.LOCATION_ID
    ORDER_ID = TestRevolutPayment.ORDER_ID
    INTENT_ID = TestRevolutPayment.INTENT_ID
    PAYMENT_ID = TestRevolutPayment.PAYMENT_ID
    TERMINAL_ID = TestRevolutPayment.TERMINAL_ID

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config_usd.sudo().write({"revolut_user_ids": [Command.link(cls.env.uid)]})
        cls.revolut_method = cls.bank_payment_method.copy(
            {
                "name": "Revolut settlement test",
                "payment_method_type": "terminal",
                "use_payment_terminal": "revolut",
                "revolut_environment": "sandbox",
                "revolut_location_id": cls.LOCATION_ID,
                "revolut_terminal_id": cls.TERMINAL_ID,
                "revolut_fulfilment_type": "eat_in",
                "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
            }
        )
        cls.pos_config_usd.write(
            {
                "payment_method_ids": [Command.link(cls.revolut_method.id)],
                "auto_validate_terminal_payment": True,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Revolut verified product",
                "available_in_pos": True,
                "list_price": 12.34,
                "taxes_id": [Command.clear()],
            }
        )

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id

    def _operation(self, order_uuid, payment_line_uuid, state="verified", **values):
        revolut_order_id = values.pop("revolut_order_id", str(uuid4()))
        revolut_intent_id = values.pop("revolut_payment_intent_id", str(uuid4()))
        revolut_payment_id = values.pop("revolut_payment_id", str(uuid4()))
        operation_values = {
            "payment_method_id": self.revolut_method.id,
            "company_id": self.company.id,
            "pos_config_id": self.pos_config_usd.id,
            "pos_session_id": self.session.id,
            "order_uuid": order_uuid,
            "payment_line_uuid": payment_line_uuid,
            "amount": 12.34,
            "amount_minor": 1234,
            "currency_id": self.session.currency_id.id,
            "currency_code": self.session.currency_id.name,
            "environment": "sandbox",
            "location_id": self.LOCATION_ID,
            "terminal_id": self.TERMINAL_ID,
            "fulfilment_type": "eat_in",
            "secret_reference": self.revolut_method.revolut_secret_reference,
            "state": state,
            "revolut_order_id": revolut_order_id,
            "revolut_payment_intent_id": revolut_intent_id,
            "revolut_payment_id": revolut_payment_id,
            "blocking_order_key": f"{self.company.id}:{order_uuid}",
            "blocking_terminal_key": (
                False
                if state in {"verified", "failed", "declined", "cancelled"}
                else f"{self.company.id}:sandbox:{self.TERMINAL_ID}"
            ),
        }
        operation_values.update(values)
        return self.env["pos.revolut.payment.operation"].sudo().create(
            operation_values
        )

    def _order_payload(
        self,
        order_uuid,
        payment_line_uuid,
        payment_method=None,
        payment_status="done",
        transaction_id=None,
    ):
        payment_method = payment_method or self.revolut_method
        return {
            "amount_paid": 12.34,
            "amount_return": 0,
            "amount_tax": 0,
            "amount_total": 12.34,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "pricelist_id": self.pos_config_usd.pricelist_id.id,
            "lines": [
                Command.create(
                    {
                        "discount": 0,
                        "pack_lot_ids": [],
                        "price_unit": 12.34,
                        "product_id": self.product.id,
                        "price_subtotal": 12.34,
                        "price_subtotal_incl": 12.34,
                        "qty": 1,
                        "tax_ids": [[6, False, []]],
                        "uuid": str(uuid4()),
                    }
                )
            ],
            "name": f"Order {order_uuid}",
            "session_id": self.session.id,
            "sequence_number": 1,
            "payment_ids": [
                Command.create(
                    {
                        "amount": 12.34,
                        "name": fields.Datetime.now(),
                        "payment_method_id": payment_method.id,
                        "payment_status": payment_status,
                        "transaction_id": transaction_id or self.PAYMENT_ID,
                        "uuid": payment_line_uuid,
                    }
                )
            ],
            "uuid": order_uuid,
            "user_id": self.env.uid,
            "to_invoice": False,
        }

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_cash_only_large_cart_does_not_use_revolut_snapshot_limits(self, request):
        payload = self._order_payload(str(uuid4()), str(uuid4()), payment_method=self.cash_payment_method)
        first = payload["lines"][0][2]
        payload["lines"] += [[0, 0, dict(first, uuid=str(uuid4()), price_unit=0,
                                       price_subtotal=0, price_subtotal_incl=0)] for _ in range(1000)]
        result = call_kw(self.env["pos.order"], "sync_from_ui", [[payload]], {})
        order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        self.assertEqual(order.state, "paid")
        self.assertEqual(len(order.lines), 1001)
        request.assert_not_called()

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_invalid_snapshot_cannot_settle_verified_payment(self, request):
        cases = (
            ("qty", "1e1000"), ("qty", "-1e1000"), ("qty", "1e-1000"),
            ("price_unit", "9" * 65),
            ("price_unit", "0.12345678901234567890123456789"),
            ("discount", "NaN"), ("discount", "12x"),
            ("discount", None), ("discount", ""), ("discount", []), ("discount", {}),
            ("amount_total", "1e1000"), ("line_count", None), ("aggregate_size", None),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                order_uuid, payment_uuid = str(uuid4()), str(uuid4())
                payload = self._order_payload(order_uuid, payment_uuid)
                snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
                operation = self._operation(order_uuid, payment_uuid, financial_snapshot=snapshot)
                payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id
                references = (operation.revolut_order_id, operation.revolut_payment_intent_id,
                              operation.revolut_payment_id)
                if field == "line_count":
                    payload["lines"] = payload["lines"] * 1001
                elif field == "aggregate_size":
                    # A small request would expand beyond the retained budget;
                    # the payload stays capped at 250 otherwise valid lines.
                    template = payload["lines"][0][2]
                    payload["lines"] = [Command.create({
                        **template, "uuid": f"snapshot-{index:04d}-" + "x" * 110,
                        "qty": "1e-324", "price_unit": "1e-324", "discount": "1e-324",
                    }) for index in range(250)]
                elif field == "amount_total":
                    payload[field] = value
                else:
                    payload["lines"][0][2][field] = value

                with self.assertRaisesRegex(UserError, "Revolut cart"):
                    self.env["pos.order"].sync_from_ui([payload])
                self.assertFalse(self.env["pos.order"].search_count([("uuid", "=", order_uuid)]))
                operation.invalidate_recordset()
                self.assertEqual(operation.state, "verified")
                self.assertEqual(operation.financial_snapshot, snapshot)
                self.assertEqual((operation.revolut_order_id, operation.revolut_payment_intent_id,
                                  operation.revolut_payment_id), references)
                self.assertEqual(operation.blocking_order_key, f"{self.company.id}:{order_uuid}")
                self.assertFalse(operation.pos_order_id)
                self.assertFalse(operation.pos_payment_id)
                request.assert_not_called()

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_persisted_canonical_snapshots_remain_settleable(self, request):
        taxes = self.env["account.tax"].create([
            {"name": "Snapshot zero tax A", "amount": 0, "amount_type": "percent", "company_id": self.company.id},
            {"name": "Snapshot zero tax B", "amount": 0, "amount_type": "percent", "company_id": self.company.id},
        ])
        for contents in ("ordinary", "native_zero_discount", "fractional_scientific_discount"):
            with self.subTest(contents=contents):
                order_uuid, payment_uuid = str(uuid4()), str(uuid4())
                payload = self._order_payload(order_uuid, payment_uuid)
                line = payload["lines"][0][2]
                # Literal evidence produced by the previous normalizer, kept
                # independent of the implementation under test.
                persisted = {
                    "pricelist_id": payload["pricelist_id"], "fiscal_position_id": 0,
                    "lines": [{
                        "uuid": line["uuid"], "product_id": self.product.id,
                        "qty": "1", "price_unit": "12.34", "discount": "0", "tax_ids": [],
                    }],
                }
                amount, minor = 12.34, 1234
                if contents == "native_zero_discount":
                    # Pinned Odoo's native relational serializer sends an
                    # unset float discount as False; payment start sends 0.
                    line["discount"] = False
                if contents == "fractional_scientific_discount":
                    first_uuid = "00000000-0000-4000-8000-000000000001"
                    second_uuid = "00000000-0000-4000-8000-000000000002"
                    line.update(uuid=second_uuid, qty=-0.5, price_unit="1e1", discount="2e1",
                                price_subtotal=-4, price_subtotal_incl=-4,
                                tax_ids=[[6, False, list(reversed(taxes.ids))]])
                    payload["lines"].append(Command.create({
                        **line, "uuid": first_uuid, "qty": 1.5, "price_unit": 10.0, "discount": 20.0,
                        "price_subtotal": 12, "price_subtotal_incl": 12,
                    }))
                    persisted["lines"] = [{
                        "uuid": uuid, "product_id": self.product.id, "qty": qty,
                        "price_unit": "10", "discount": "20", "tax_ids": sorted(taxes.ids),
                    } for uuid, qty in ((first_uuid, "1.5"), (second_uuid, "-0.5"))]
                    amount, minor = 8, 800
                    payload.update(amount_total=amount, amount_paid=amount)
                    payload["payment_ids"][0][2]["amount"] = amount
                operation = self._operation(
                    order_uuid, payment_uuid, amount=amount, amount_minor=minor, financial_snapshot=persisted,
                )
                payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id

                saved = self.env["pos.order"].sync_from_ui([payload])
                order = self.env["pos.order"].browse(next(
                    item["id"] for item in saved["pos.order"] if item["uuid"] == order_uuid
                ))
                operation.invalidate_recordset()
                self.assertEqual(order.state, "paid")
                self.assertEqual(order.amount_total, amount)
                self.assertEqual(operation.pos_order_id, order)
                self.assertEqual(operation.pos_payment_id, order.payment_ids)
                self.assertEqual(operation.financial_snapshot, persisted)
                self.assertFalse(operation.blocking_order_key)
                request.assert_not_called()

    def test_verified_payment_settles_once_and_stores_references(self):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        payload = self._order_payload(order_uuid, payment_line_uuid)
        snapshot = self.env[
            "pos.revolut.payment.operation"
        ]._normalize_financial_snapshot(payload)
        operation = self._operation(
            order_uuid, payment_line_uuid, financial_snapshot=snapshot
        )
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id

        result = self.env["pos.order"].sync_from_ui([payload])

        order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        operation.invalidate_recordset()
        self.assertEqual(order.state, "paid")
        self.assertEqual(
            order.payment_ids.transaction_id, operation.revolut_payment_id
        )
        self.assertEqual(order.payment_ids.payment_ref_no, operation.revolut_order_id)
        self.assertEqual(
            order.payment_ids.revolut_payment_intent_id,
            operation.revolut_payment_intent_id,
        )
        self.assertEqual(operation.pos_order_id, order)
        self.assertEqual(operation.pos_payment_id, order.payment_ids)
        self.assertFalse(operation.blocking_order_key)

    def test_verified_revolut_line_and_cash_settle_exact_allocations(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, line_uuid)
        payload["payment_ids"][0][2]["amount"] = 4.34
        payload["payment_ids"].append(Command.create({
            "amount": 8.00,
            "name": fields.Datetime.now(),
            "payment_method_id": self.cash_payment_method.id,
            "uuid": str(uuid4()),
        }))
        operation = self._operation(
            order_uuid, line_uuid, amount=4.34, amount_minor=434,
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        )
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id

        result = self.env["pos.order"].sync_from_ui([payload])

        order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        operation.invalidate_recordset()
        self.assertEqual(order.state, "paid")
        self.assertEqual(len(order.payment_ids), 2)
        self.assertEqual(operation.pos_payment_id.amount, 4.34)
        self.assertEqual(operation.pos_payment_id.uuid, line_uuid)
        self.assertEqual(operation.pos_payment_id.revolut_order_id, operation.revolut_order_id)
        self.assertEqual(order.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.cash_payment_method
        ).amount, 8.00)

    def test_two_verified_revolut_lines_keep_separate_references(self):
        order_uuid = str(uuid4())
        first_uuid, second_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, first_uuid)
        payload["payment_ids"][0][2]["amount"] = 4.00
        payload["payment_ids"].append(Command.create({
            "amount": 8.34,
            "name": fields.Datetime.now(),
            "payment_method_id": self.revolut_method.id,
            "payment_status": "done",
            "uuid": second_uuid,
        }))
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
        first = self._operation(order_uuid, first_uuid, amount=4.00, amount_minor=400,
                                blocking_order_key=False, financial_snapshot=snapshot)
        second = self._operation(order_uuid, second_uuid, amount=8.34, amount_minor=834,
                                 blocking_order_key=False, financial_snapshot=snapshot)
        payload["payment_ids"][0][2]["transaction_id"] = first.revolut_payment_id
        payload["payment_ids"][1][2]["transaction_id"] = second.revolut_payment_id

        result = self.env["pos.order"].sync_from_ui([payload])

        order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        first.invalidate_recordset()
        second.invalidate_recordset()
        self.assertEqual(order.state, "paid")
        self.assertEqual(first.pos_payment_id.uuid, first_uuid)
        self.assertEqual(second.pos_payment_id.uuid, second_uuid)
        self.assertEqual(first.pos_payment_id.amount, 4.00)
        self.assertEqual(second.pos_payment_id.amount, 8.34)
        self.assertEqual(first.pos_payment_id.revolut_order_id, first.revolut_order_id)
        self.assertEqual(second.pos_payment_id.revolut_order_id, second.revolut_order_id)

    def test_each_revolut_line_checks_amount_currency_and_reference(self):
        other_currency = self.env.ref("base.EUR")
        if other_currency == self.session.currency_id:
            other_currency = self.env.ref("base.USD")
        for mismatch in ("amount", "currency", "reference"):
            with self.subTest(mismatch=mismatch):
                order_uuid = str(uuid4())
                first_uuid, second_uuid = str(uuid4()), str(uuid4())
                payload = self._order_payload(order_uuid, first_uuid)
                payload["payment_ids"][0][2]["amount"] = 4.00
                payload["payment_ids"].append(Command.create({
                    "amount": 8.34, "name": fields.Datetime.now(),
                    "payment_method_id": self.revolut_method.id,
                    "payment_status": "done", "uuid": second_uuid,
                }))
                snapshot = self.env[
                    "pos.revolut.payment.operation"
                ]._normalize_financial_snapshot(payload)
                first = self._operation(order_uuid, first_uuid, amount=4.00,
                                        amount_minor=400, blocking_order_key=False,
                                        financial_snapshot=snapshot)
                second_values = {
                    "amount": 8.34, "amount_minor": 834,
                    "blocking_order_key": False, "financial_snapshot": snapshot,
                }
                if mismatch == "currency":
                    second_values.update({
                        "currency_id": other_currency.id,
                        "currency_code": other_currency.name,
                    })
                second = self._operation(order_uuid, second_uuid, **second_values)
                payload["payment_ids"][0][2]["transaction_id"] = first.revolut_payment_id
                payload["payment_ids"][1][2]["transaction_id"] = second.revolut_payment_id
                if mismatch == "amount":
                    payload["payment_ids"][1][2]["amount"] = 8.35
                elif mismatch == "reference":
                    payload["payment_ids"][1][2]["transaction_id"] = str(uuid4())

                with self.assertRaises(UserError):
                    self.env["pos.order"].sync_from_ui([payload])

    def test_unresolved_second_line_cannot_be_replaced_with_cash(self):
        order_uuid = str(uuid4())
        first_uuid, second_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, first_uuid)
        payload["payment_ids"][0][2]["amount"] = 4.00
        payload["payment_ids"].append(Command.create({
            "amount": 8.34,
            "name": fields.Datetime.now(),
            "payment_method_id": self.cash_payment_method.id,
            "uuid": str(uuid4()),
        }))
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
        first = self._operation(order_uuid, first_uuid, amount=4.00, amount_minor=400,
                                blocking_order_key=False, financial_snapshot=snapshot)
        self._operation(order_uuid, second_uuid, state="unresolved", amount=8.34,
                        amount_minor=834, revolut_payment_id=False,
                        financial_snapshot=snapshot)
        payload["payment_ids"][0][2]["transaction_id"] = first.revolut_payment_id

        with self.assertRaisesRegex(UserError, "unresolved"):
            self.env["pos.order"].sync_from_ui([payload])

    def test_copied_verified_line_cannot_pay_another_order_as_cash(self):
        original_uuid, line_uuid = str(uuid4()), str(uuid4())
        operation = self._operation(original_uuid, line_uuid)
        copied = self._order_payload(str(uuid4()), line_uuid,
                                     payment_method=self.cash_payment_method,
                                     payment_status=False,
                                     transaction_id=operation.revolut_payment_id)
        with self.assertRaisesRegex(UserError, "another POS order"):
            self.env["pos.order"].sync_from_ui([copied])

    def test_partially_paid_draft_keeps_payment_for_later_checkout(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, line_uuid)
        payload["payment_ids"][0][2]["amount"] = 4.34
        payload["amount_paid"] = 4.34
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
        operation = self._operation(order_uuid, line_uuid, amount=4.34,
                                    amount_minor=434, financial_snapshot=snapshot)
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id
        final_payload = deepcopy(payload)
        final_payload["state"] = "paid"
        final_payload["lines"] = [list(command) for command in final_payload["lines"]]
        final_payload["payment_ids"] = [list(command) for command in final_payload["payment_ids"]]
        final_payload["amount_paid"] = 12.34
        final_payload["payment_ids"].append(Command.create({
            "amount": 8.00,
            "name": fields.Datetime.now(),
            "payment_method_id": self.cash_payment_method.id,
            "uuid": str(uuid4()),
        }))
        payload["state"] = "draft"

        draft_result = self.env["pos.order"].sync_from_ui([payload])
        draft = self.env["pos.order"].browse(draft_result["pos.order"][0]["id"])
        operation.invalidate_recordset()
        self.assertEqual(draft.state, "draft")
        self.assertEqual(operation.pos_order_id, draft)
        self.assertEqual(operation.pos_payment_id.uuid, line_uuid)

        final_result = self.env["pos.order"].sync_from_ui([final_payload])
        final = self.env["pos.order"].browse(final_result["pos.order"][0]["id"])
        self.assertEqual(final, draft)
        self.assertEqual(final.state, "paid")
        self.assertEqual(len(final.payment_ids), 2)

    def test_partially_paid_draft_rejects_financial_edit(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, line_uuid)
        payload["payment_ids"][0][2]["amount"] = 4.34
        payload["amount_paid"] = 4.34
        snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
        operation = self._operation(order_uuid, line_uuid, amount=4.34,
                                    amount_minor=434, financial_snapshot=snapshot)
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id
        payload["state"] = "draft"
        self.env["pos.order"].sync_from_ui([deepcopy(payload)])
        payload["lines"][0][2]["qty"] = 2

        with self.assertRaisesRegex(UserError, "order changed"):
            self.env["pos.order"].sync_from_ui([payload])

    def test_pre_upgrade_verified_payment_requires_manager_reconciliation(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        operation = self._operation(order_uuid, line_uuid)
        payload = self._order_payload(
            order_uuid, line_uuid, transaction_id=operation.revolut_payment_id
        )
        # A pre-upgrade attempt has no original cart snapshot. Matching totals
        # cannot establish that the product, tax, or destination is unchanged.
        self.assertFalse(operation.financial_snapshot)
        with self.assertRaisesRegex(UserError, "Reconcile"):
            self.env["pos.order"].sync_from_ui([payload])
        self.assertFalse(self.env["pos.order"].search_count([
            ("uuid", "=", order_uuid), ("state", "=", "paid"),
        ]))

    def test_late_success_cannot_settle_edited_financial_content(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, line_uuid)
        original_line = payload["lines"][0][2]
        snapshot = {
            "pricelist_id": payload["pricelist_id"],
            "fiscal_position_id": False,
            "lines": [{
                "uuid": original_line["uuid"],
                "product_id": self.product.id,
                "qty": 1,
                "price_unit": 12.34,
                "discount": 0,
                "tax_ids": [],
            }],
        }
        operation = self._operation(
            order_uuid, line_uuid, financial_snapshot=snapshot
        )
        payload["lines"][0][2]["price_unit"] = 15.00
        payload["lines"][0][2]["discount"] = 17.7333333333
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id

        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([payload])
        self.assertFalse(self.env["pos.order"].search_count([
            ("uuid", "=", order_uuid), ("state", "=", "paid"),
        ]))

    def test_unsuccessful_attempts_cannot_settle_a_sale(self):
        for state in ("declined", "failed", "cancelled", "unresolved"):
            with self.subTest(state=state):
                order_uuid, line_uuid = str(uuid4()), str(uuid4())
                operation = self._operation(
                    order_uuid, line_uuid, state=state,
                    blocking_terminal_key=False,
                )
                payload = self._order_payload(
                    order_uuid, line_uuid, transaction_id=operation.revolut_payment_id
                )
                with self.assertRaises(UserError):
                    self.env["pos.order"].sync_from_ui([payload])
                self.assertFalse(self.env["pos.order"].search_count([
                    ("uuid", "=", order_uuid), ("state", "=", "paid"),
                ]))

    def test_forged_done_status_without_verified_operation_is_rejected(self):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())

        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui(
                [self._order_payload(order_uuid, payment_line_uuid)]
            )

    def test_forged_payment_saved_on_draft_cannot_bypass_verification(self):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        draft_payload = self._order_payload(order_uuid, payment_line_uuid)
        draft_payload["state"] = "draft"
        with self.assertRaisesRegex(UserError, "not been verified"):
            self.env["pos.order"].sync_from_ui([deepcopy(draft_payload)])
        draft_payload["payment_ids"][0][2]["payment_status"] = "waiting"
        result = self.env["pos.order"].sync_from_ui([draft_payload])
        draft_order = self.env["pos.order"].browse(result["pos.order"][0]["id"])
        self.assertEqual(draft_order.state, "draft")

        final_payload = self._order_payload(order_uuid, str(uuid4()))
        final_payload["payment_ids"] = []

        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui([final_payload])

    def test_unresolved_operation_blocks_payment_method_substitution(self):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        self._operation(
            order_uuid,
            payment_line_uuid,
            state="unresolved",
            revolut_payment_id=False,
        )

        with self.assertRaises(UserError):
            self.env["pos.order"].sync_from_ui(
                [
                    self._order_payload(
                        order_uuid,
                        str(uuid4()),
                        payment_method=self.cash_payment_method,
                        payment_status=False,
                        transaction_id=False,
                    )
                ]
            )

    def test_retry_safe_failed_line_cannot_count_as_paid(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        self._operation(order_uuid, line_uuid, state="failed", retry_safe=True,
                        provider_state="failed", blocking_order_key=False)
        payload = self._order_payload(order_uuid, line_uuid, payment_status="retry")
        with self.assertRaisesRegex(UserError, "not been verified"):
            self.env["pos.order"].sync_from_ui([payload])

    def test_revolut_reference_cannot_be_copied_to_a_cash_line(self):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = self._order_payload(order_uuid, line_uuid)
        payload["payment_ids"][0][2]["amount"] = 4.34
        operation = self._operation(order_uuid, line_uuid, amount=4.34,
                                    amount_minor=434,
                                    financial_snapshot=self.env[
                                        "pos.revolut.payment.operation"
                                    ]._normalize_financial_snapshot(payload))
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id
        payload["payment_ids"].append(Command.create({
            "amount": 8.00, "name": fields.Datetime.now(),
            "payment_method_id": self.cash_payment_method.id,
            "transaction_id": operation.revolut_payment_id,
            "uuid": str(uuid4()),
        }))
        with self.assertRaisesRegex(UserError, "another payment line"):
            self.env["pos.order"].sync_from_ui([payload])

    def test_revolut_payment_reference_cannot_be_reused(self):
        payment_id = str(uuid4())
        self._operation(
            str(uuid4()), str(uuid4()), revolut_payment_id=payment_id
        )

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self._operation(str(uuid4()), str(uuid4()), revolut_payment_id=payment_id)


@tagged("post_install", "-at_install", "pos_revolut_restaurant")
class TestRevolutRestaurantContext(TransactionCase):
    LOCATION_ID = TestRevolutPayment.LOCATION_ID
    TERMINAL_ID = TestRevolutPayment.TERMINAL_ID

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        restaurant = cls.env["ir.module.module"].search(
            [("name", "=", "pos_restaurant")], limit=1
        )
        if restaurant.state != "installed":
            raise SkipTest("pos_restaurant is not installed in this test phase")
        bridge = cls.env["ir.module.module"].search(
            [("name", "=", "pos_revolut_restaurant")], limit=1
        )
        if bridge:
            raise AssertionError("The retired Revolut Restaurant addon is still listed")
        cls.method = cls.env["pos.payment.method"].create({
            "name": "Restaurant Revolut test",
            "payment_method_type": "terminal",
            "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID,
            "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_RESTAURANT_TEST",
        })
        cls.config = cls.env["pos.config"].create({
            "name": "Restaurant Revolut test",
            "payment_method_ids": [Command.link(cls.method.id)],
            "auto_validate_terminal_payment": True,
        })
        dine_in = cls.env.ref("pos_restaurant.pos_takein_preset")
        takeout = cls.env.ref("pos_restaurant.pos_takeout_preset")
        cls.config.write({
            "module_pos_restaurant": True, "use_presets": True,
            "default_preset_id": dine_in.id,
            "available_preset_ids": [Command.link(dine_in.id), Command.link(takeout.id)],
        })
        cls.product = native_products(cls.env, cls.config)
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id, "state": "opened",
        })
        floor = cls.env["restaurant.floor"].create({
            "name": "Revolut test floor",
            "pos_config_ids": [Command.link(cls.config.id)],
        })
        cls.table = cls.env["restaurant.table"].create({
            "table_number": 1, "floor_id": floor.id, "seats": 2,
        })

    def setUp(self):
        super().setUp()
        registry_test_mode = self.enter_registry_test_mode()
        registry_test_mode.__enter__()
        self.addCleanup(registry_test_mode.__exit__, None, None, None)

    def _response(self, payload):
        response = Mock()
        response.json.return_value = payload
        return response

    def _start(self, preset_id, table_id, *, preset_time=False):
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        snapshot = {
            "pricelist_id": self.config.pricelist_id.id,
            "fiscal_position_id": False,
            "restaurant": {"preset_id": preset_id, "table_id": table_id},
            "lines": [{
                "uuid": str(uuid4()), "product_id": self.product.id,
                "qty": 1, "price_unit": 12.34,
                "discount": 0, "tax_ids": [],
            }],
        }
        return authorized_start(self.method,
            self.session.id, order_uuid, line_uuid, 4.34,
            self.config.currency_id.id, False, snapshot, preset_time=preset_time,
        )

    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_verified_draft_keeps_order_identity_across_table_change(self, request):
        other_table = self.env["restaurant.table"].create({
            "table_number": 2, "floor_id": self.table.floor_id.id, "seats": 2,
        })
        product = self.env["product.product"].create({
            "name": "Restaurant Revolut product",
            "available_in_pos": True,
            "list_price": 12.34,
            "taxes_id": [Command.clear()],
        })
        order_uuid, line_uuid = str(uuid4()), str(uuid4())
        payload = {
            "amount_paid": 4.34,
            "amount_return": 0,
            "amount_tax": 0,
            "amount_total": 12.34,
            "date_order": fields.Datetime.to_string(fields.Datetime.now()),
            "fiscal_position_id": False,
            "pricelist_id": self.config.pricelist_id.id,
            "lines": [list(Command.create({
                "discount": 0, "pack_lot_ids": [], "price_unit": 12.34,
                "product_id": product.id, "price_subtotal": 12.34,
                "price_subtotal_incl": 12.34, "qty": 1,
                "tax_ids": [[6, False, []]], "uuid": str(uuid4()),
            }))],
            "name": f"Order {order_uuid}",
            "session_id": self.session.id,
            "sequence_number": 1,
            "payment_ids": [list(Command.create({
                "amount": 4.34, "name": fields.Datetime.now(),
                "payment_method_id": self.method.id,
                "payment_status": "done", "uuid": line_uuid,
            }))],
            "table_id": self.table.id,
            "uuid": order_uuid,
            "user_id": self.env.uid,
            "to_invoice": False,
            "state": "draft",
        }
        operation = self.env["pos.revolut.payment.operation"].sudo().create({
            "payment_method_id": self.method.id,
            "company_id": self.env.company.id,
            "pos_config_id": self.config.id,
            "pos_session_id": self.session.id,
            "order_uuid": order_uuid,
            "payment_line_uuid": line_uuid,
            "amount": 4.34,
            "amount_minor": 434,
            "currency_id": self.session.currency_id.id,
            "currency_code": self.session.currency_id.name,
            "environment": "sandbox",
            "location_id": self.LOCATION_ID,
            "terminal_id": self.TERMINAL_ID,
            "fulfilment_type": "eat_in",
            "secret_reference": "ODOO_REVOLUT_SECRET_RESTAURANT_TEST",
            "state": "verified",
            "revolut_order_id": str(uuid4()),
            "revolut_payment_intent_id": str(uuid4()),
            "revolut_payment_id": str(uuid4()),
            "financial_snapshot": self.env[
                "pos.revolut.payment.operation"
            ]._normalize_financial_snapshot(payload),
        })
        payload["payment_ids"][0][2]["transaction_id"] = operation.revolut_payment_id
        moved = deepcopy(payload)
        moved["table_id"] = other_table.id
        edited = deepcopy(moved)
        edited["lines"][0][2]["qty"] = 2

        first = self.env["pos.order"].sync_from_ui([payload])
        draft = self.env["pos.order"].browse(first["pos.order"][0]["id"])
        second = self.env["pos.order"].sync_from_ui([moved])
        operation.invalidate_recordset()
        self.assertEqual(draft.id, second["pos.order"][0]["id"])
        self.assertEqual(draft.table_id, other_table)
        self.assertEqual(operation.pos_order_id, draft)
        self.assertEqual(operation.pos_payment_id.uuid, line_uuid)
        with self.assertRaisesRegex(UserError, "order changed while Revolut payment"):
            self.env["pos.order"].sync_from_ui([edited])
        draft.invalidate_recordset()
        self.assertEqual(draft.table_id, other_table)
        self.assertEqual(draft.lines.qty, 1)
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_unknown_restaurant_context_does_not_dispatch(self, request):
        with self.assertRaisesRegex(UserError, "Dine In or Takeout"):
            self._start(False, False)
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_unknown_preset_with_table_does_not_dispatch(self, request):
        with self.assertRaisesRegex(UserError, "Dine In or Takeout"):
            self._start(False, self.table.id)
        request.assert_not_called()

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_dine_in_uses_eat_in_provisional_payload(self, request):
        request.side_effect = [
            self._response({"terminals": [{
                "id": self.TERMINAL_ID, "online": True,
                "operation_mode": "pos", "location_id": self.LOCATION_ID,
            }]}),
            self._response({"id": str(uuid4())}),
            self._response({"id": str(uuid4()), "state": "pending"}),
        ]
        started = self._start(
            self.env.ref("pos_restaurant.pos_takein_preset").id, self.table.id
        )
        self.assertEqual(started["state"], "pending")
        order_post = [call for call in request.call_args_list
                      if call.args[0] == "POST"][0]
        self.assertEqual(order_post.kwargs["json"]["fulfilment_type"], "eat_in")
        self.assertEqual(order_post.kwargs["json"]["amount"], 434)
        self.assertEqual(order_post.kwargs["json"]["currency"], self.config.currency_id.name)

    @patch.dict(os.environ, {"ODOO_REVOLUT_SECRET_RESTAURANT_TEST": "test-only"})
    @patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request")
    def test_takeaway_uses_take_away_provisional_payload(self, request):
        request.side_effect = [
            self._response({"terminals": [{
                "id": self.TERMINAL_ID, "online": True,
                "operation_mode": "pos", "location_id": self.LOCATION_ID,
            }]}),
            self._response({"id": str(uuid4())}),
            self._response({"id": str(uuid4()), "state": "pending"}),
        ]
        started = self._start(
            self.env.ref("pos_restaurant.pos_takeout_preset").id, False,
            preset_time=fields.Datetime.now(),
        )
        self.assertEqual(started["state"], "pending")
        order_post = [call for call in request.call_args_list
                      if call.args[0] == "POST"][0]
        self.assertEqual(order_post.kwargs["json"]["fulfilment_type"], "take_away")
        self.assertEqual(order_post.kwargs["json"]["amount"], 434)

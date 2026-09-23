import os
from threading import Barrier, Thread
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from psycopg2 import IntegrityError
from psycopg2.errors import SerializationFailure

from odoo import SUPERUSER_ID, Command, api, fields
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


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

    def _start(self, order_uuid, payment_line_uuid, amount=12.34):
        return self.payment_method.revolut_start_payment(
            self.session.id,
            order_uuid,
            payment_line_uuid,
            amount,
            self.config.currency_id.id,
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
        self.assertEqual(repeated, result)
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
        retry = self.payment_method.revolut_start_payment(
            self.session.id, order_uuid, line_uuid, 12.34,
            self.config.currency_id.id, first["operation_id"]
        )
        repeated = self.payment_method.revolut_start_payment(
            self.session.id, order_uuid, line_uuid, 12.34,
            self.config.currency_id.id, first["operation_id"]
        )
        self.assertTrue(failed["retry_safe"])
        self.assertNotEqual(retry["operation_id"], first["operation_id"])
        self.assertEqual(repeated, retry)
        self.assertNotEqual(retry["order_id"], old_order)
        self.assertEqual(self.payment_method.revolut_poll_payment(
            first["operation_id"], order_uuid, line_uuid
        ), failed)
        self.assertEqual(len([call for call in request.call_args_list
                              if call.args[0] == "POST"]), 4)

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
            self.payment_method.revolut_start_payment(
                self.session.id, order_uuid, line_uuid, 12.34,
                self.config.currency_id.id, first["operation_id"]
            )
        with self.assertRaises(UserError):
            self._start(order_uuid, line_uuid, amount=99)
        with self.assertRaises(UserError):
            self._start(order_uuid, str(uuid4()))
        self.assertEqual(len([call for call in request.call_args_list
                              if call.args[0] == "POST"]), 2)

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
            self.payment_method.revolut_start_payment(
                self.session.id, order_uuid, line_uuid, 12.34,
                self.config.currency_id.id, result["operation_id"]
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
        retry = self.payment_method.revolut_start_payment(
            self.session.id, order_uuid, line_uuid, 12.34,
            self.config.currency_id.id, first["operation_id"]
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
        posts = [call for call in request.call_args_list if call.args[0] == "POST"]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].kwargs["json"]["amount"], 1234)
        self.assertEqual(posts[1].kwargs["json"]["amount"], 1234)

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
            "_complete_revolut_dispatch_owned",
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

    def test_operation_from_another_company_is_not_pollable(self):
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
        operation = self.env["pos.revolut.payment.operation"].sudo().create(values)

        with self.assertRaises(AccessError):
            self.payment_method.with_context(
                allowed_company_ids=[self.env.company.id]
            ).revolut_poll_payment(
                operation.id, order_uuid, payment_line_uuid
            )


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
            "secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
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

    def test_verified_payment_settles_once_and_stores_references(self):
        order_uuid = str(uuid4())
        payment_line_uuid = str(uuid4())
        operation = self._operation(order_uuid, payment_line_uuid)

        result = self.env["pos.order"].sync_from_ui(
            [
                self._order_payload(
                    order_uuid,
                    payment_line_uuid,
                    transaction_id=operation.revolut_payment_id,
                )
            ]
        )

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

    def test_revolut_payment_reference_cannot_be_reused(self):
        payment_id = str(uuid4())
        self._operation(
            str(uuid4()), str(uuid4()), revolut_payment_id=payment_id
        )

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self._operation(str(uuid4()), str(uuid4()), revolut_payment_id=payment_id)

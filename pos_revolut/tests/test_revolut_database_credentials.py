"""Database Merchant keys exercise the real authority and mocked HTTP boundary."""

import io
import logging
import os
from contextlib import contextmanager
from copy import deepcopy
from unittest.mock import Mock, patch
from uuid import uuid4

import requests
from psycopg2 import IntegrityError

from odoo import Command, api, fields
from odoo.api import call_kw
from odoo.addons.point_of_sale.tests.common import TestPointOfSaleCommon
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .authorization_fixtures import authorized_start, financial_posts, install_zero_reports
from .test_revolut_payment import TestRevolutOrderSettlement as _SettlementFixtures
from .test_revolut_refund import TestRevolutRefund as _RefundFixtures


class TestRevolutDatabaseCredentials(TransactionCase):
    @contextmanager
    def _capture_sql_logs(self):
        logger = logging.getLogger("odoo.sql_db")
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        previous_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            # Cursor logging settings are captured at construction. A fresh,
            # rollback-only cursor exercises real SQL debug/error logging.
            with self.registry.cursor() as cursor:
                env = api.Environment(cursor, self.env.uid, dict(self.env.context))
                cursor.execute("SELECT %s", ["synthetic-sql-log-control"])
                try:
                    yield env, output
                finally:
                    cursor.rollback()
        finally:
            logger.setLevel(previous_level)
            logger.removeHandler(handler)
            handler.close()

    def _authority(self, company=None, **overrides):
        return self.env["pos.revolut.merchant.credential"].create({
            "company_id": (company or self.env.company).id,
            "environment": "sandbox",
            "secret_reference": f"ODOO_REVOLUT_SECRET_DATABASE_{uuid4().hex.upper()}",
            "source": "database", "secret_key": "synthetic-database-merchant-key",
            **overrides,
        })

    def _method(self, credential):
        return self.env["pos.payment.method"].create({
            "name": "Database Merchant terminal", "company_id": credential.company_id.id,
            "payment_method_type": "terminal", "use_payment_terminal": "revolut",
            "revolut_environment": credential.environment,
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": credential.secret_reference,
        })

    def test_database_authority_checks_connection_without_environment_key(self):
        reference = "ODOO_REVOLUT_SECRET_DATABASE_FIRST"
        self.env["pos.revolut.merchant.credential"].create({
            "company_id": self.env.company.id,
            "environment": "sandbox", "secret_reference": reference,
            "source": "database", "secret_key": "synthetic-database-merchant-key",
        })
        method = self.env["pos.payment.method"].create({
            "name": "Database Merchant terminal", "company_id": self.env.company.id,
            "payment_method_type": "terminal", "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox", "revolut_location_id": str(uuid4()),
            "revolut_terminal_id": str(uuid4()), "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": reference,
        })
        response = Mock(status_code=200)
        response.json.return_value = {"terminals": [{
            "id": method.revolut_terminal_id, "online": True,
        }]}
        with patch.dict(os.environ), patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
            return_value=response,
        ) as provider:
            os.environ.pop(reference, None)
            result = method.action_revolut_check_connection()
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(provider.call_args.kwargs["headers"]["Authorization"],
                         "Bearer synthetic-database-merchant-key")
        self.assertNotIn("synthetic-database-merchant-key", repr(result))

    def test_database_creation_keeps_key_out_of_debug_sql_logs(self):
        secret = "synthetic-debug-key-must-never-be-logged"
        with self._capture_sql_logs() as (env, output):
            call_kw(env["pos.revolut.merchant.credential"], "create", [{
                "company_id": env.company.id, "environment": "sandbox",
                "secret_reference": f"ODOO_REVOLUT_SECRET_SQL_{uuid4().hex.upper()}",
                "source": "database", "secret_key": secret,
            }], {})
            call_kw(env["pos.revolut.merchant.credential"].with_context(
                default_source="database", default_secret_key=secret,
            ), "create", [{
                "company_id": env.company.id, "environment": "sandbox",
                "secret_reference": f"ODOO_REVOLUT_SECRET_SQL_DEFAULT_{uuid4().hex.upper()}",
            }], {})
            env.flush_all()
        logs = output.getvalue()
        self.assertIn("synthetic-sql-log-control", logs)
        self.assertNotIn(secret, logs)

    def test_duplicate_database_reference_keeps_key_out_of_sql_error_logs(self):
        secret = "synthetic-duplicate-key-must-never-be-logged"
        with self._capture_sql_logs() as (env, output):
            target = env["pos.revolut.merchant.credential"]
            values = {
                "company_id": env.company.id, "environment": "sandbox",
                "secret_reference": f"ODOO_REVOLUT_SECRET_SQL_{uuid4().hex.upper()}",
                "source": "database", "secret_key": secret,
            }
            call_kw(target, "create", [values], {})
            env.flush_all()
            with self.assertRaises(IntegrityError) as error, env.cr.savepoint():
                call_kw(target, "create", [values], {})
                env.flush_all()
        logs = output.getvalue()
        self.assertIn("synthetic-sql-log-control", logs)
        self.assertNotIn(secret, logs)
        self.assertNotIn(secret, str(error.exception))

    def test_database_key_access_is_denied_through_rpc_and_exports(self):
        credential = self._authority()
        for role in ("point_of_sale.group_pos_manager", "point_of_sale.group_pos_user"):
            actor = new_test_user(self.env, login=f"database_key_{uuid4()}",
                                  groups=f"{role},base.group_allow_export")
            target = self.env[credential._name].with_user(actor)
            for method, args in (
                ("search_read", [[], ["secret_key"]]),
                ("read", [[credential.id], ["secret_key"]]),
                ("export_data", [[credential.id], ["secret_key"]]),
                ("write", [[credential.id], {"secret_key": "forbidden-replacement"}]),
                ("write", [[credential.id], {"revoked": True}]),
                ("unlink", [[credential.id]]),
                ("create", [{"company_id": self.env.company.id,
                             "environment": "sandbox", "source": "database",
                             "secret_reference": "ODOO_REVOLUT_SECRET_FORBIDDEN",
                             "secret_key": "forbidden-key"}]),
            ):
                with self.subTest(role=role, method=method), self.assertRaises(AccessError):
                    call_kw(target, method, args, {})
            description = call_kw(target, "fields_get", [], {})
            self.assertNotIn("secret_key", description)
        loaded = self.env["pos.payment.method"]._load_pos_data_fields(self.env["pos.config"])
        self.assertNotIn("secret_key", loaded)
        self.assertNotIn("revolut_secret_reference", loaded)

    def test_credential_rpc_arguments_are_redacted_before_debug_logging(self):
        secret = "synthetic-rpc-key-must-never-be-logged"
        credentials = self.env["pos.revolut.merchant.credential"]
        with self.assertLogs("odoo.api", level="DEBUG") as captured:
            credential_id = call_kw(credentials, "create", [{
                "company_id": self.env.company.id, "environment": "sandbox",
                "secret_reference": f"ODOO_REVOLUT_SECRET_RPC_{uuid4().hex.upper()}",
                "source": "database", "secret_key": secret,
            }], {})
            with self.assertRaises(ValidationError):
                call_kw(credentials, "write", [[credential_id], {"secret_key": secret}], {})
            call_kw(self.env["res.company"], "read", [[self.env.company.id], ["name"]], {})
        messages = "\n".join(captured.output)
        self.assertIn(".create(", messages)
        self.assertIn(".write(", messages)
        self.assertIn("res.company", messages)
        self.assertNotIn(secret, messages)

    def test_rotation_cannot_replace_immutable_database_key_or_binding(self):
        credential = self._authority()
        other_company = self.env["res.company"].create({"name": "Synthetic successor company"})
        for values in (
            {"secret_key": "replacement-key"}, {"source": "environment"},
            {"company_id": other_company.id}, {"environment": "production"},
            {"secret_reference": "ODOO_REVOLUT_SECRET_REPLACEMENT"},
        ):
            with self.subTest(values=list(values)), self.assertRaises(ValidationError):
                credential.write(values)
        replacement = self._authority(secret_key="synthetic-successor-merchant-key")
        self.assertNotEqual(credential.secret_reference, replacement.secret_reference)
        self.assertEqual(credential.secret_key, "synthetic-database-merchant-key")
        credential.write({"revoked": True})
        self.assertTrue(credential.revoked)
        self.assertFalse(replacement.revoked)

    def test_database_source_never_falls_back_to_same_named_environment_key(self):
        credential = self._authority()
        method = self._method(credential)
        credential.write({"revoked": True})
        with patch.dict(os.environ, {credential.secret_reference: "wrong-fallback-key"}), patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
        ) as provider:
            with self.assertRaises(UserError) as error:
                method.action_revolut_check_connection()
        provider.assert_not_called()
        self.assertNotIn("wrong-fallback-key", str(error.exception))
        self.assertNotIn("synthetic-database-merchant-key", str(error.exception))

    def test_database_source_ignores_competing_environment_key_and_sanitizes_errors(self):
        credential = self._authority()
        method = self._method(credential)
        response = Mock(status_code=200)
        response.json.return_value = {"terminals": [{
            "id": method.revolut_terminal_id, "online": True,
        }]}
        with patch.dict(os.environ, {credential.secret_reference: "wrong-fallback-key"}), patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
            return_value=response,
        ) as provider:
            method.action_revolut_check_connection()
            self.assertEqual(provider.call_args.kwargs["headers"]["Authorization"],
                             "Bearer synthetic-database-merchant-key")
            provider.side_effect = requests.HTTPError("Bearer synthetic-database-merchant-key")
            with self.assertRaises(UserError) as error:
                method.action_revolut_check_connection()
        self.assertNotIn("synthetic-database-merchant-key", str(error.exception))
        self.assertNotIn("wrong-fallback-key", str(error.exception))

    def test_database_key_required_and_environment_source_cannot_store_key(self):
        for values in ({"secret_key": False}, {"source": "environment"}):
            with self.subTest(values=list(values)), self.assertRaises(ValidationError), self.cr.savepoint():
                self._authority(**values)

    def test_broad_manager_checks_each_company_and_terminal_with_bound_key(self):
        other_company = self.env["res.company"].create({"name": "Synthetic second installation"})
        broad_manager = new_test_user(
            self.env, login="database_key_multi_company_manager",
            groups="point_of_sale.group_pos_manager", company_id=self.env.company.id,
            company_ids=[Command.set((self.env.company | other_company).ids)],
        )
        authorities = [self._authority(), self._authority(other_company, secret_key="synthetic-independent-key")]
        methods = [self._method(authorities[0]), self._method(authorities[0]), self._method(authorities[1])]
        observed = []

        def provider_response(url, **kwargs):
            observed.append(kwargs)
            selected = next(method for method in methods
                            if method.revolut_location_id == kwargs["params"]["location_id"])
            response = Mock(status_code=200)
            response.json.return_value = {"terminals": [{
                "id": selected.revolut_terminal_id, "online": True,
            }]}
            return response

        with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.get",
                   side_effect=provider_response):
            for method in methods:
                result = method.with_user(broad_manager).with_context(
                    allowed_company_ids=(self.env.company | other_company).ids,
                ).action_revolut_check_connection()
                self.assertEqual(result["params"]["type"], "success")
        self.assertEqual([call["headers"]["Authorization"] for call in observed], [
            "Bearer synthetic-database-merchant-key", "Bearer synthetic-database-merchant-key",
            "Bearer synthetic-independent-key",
        ])
        with self.assertRaises(UserError), self.cr.savepoint():
            methods[0].with_user(broad_manager).write({
                "revolut_secret_reference": authorities[1].secret_reference,
            })
        self.assertEqual(methods[0].revolut_secret_reference, authorities[0].secret_reference)


@tagged("post_install", "-at_install")
class TestRevolutDatabaseCredentialFlow(TestPointOfSaleCommon):
    """Native sales and returns retain their original database key after rotation."""

    REFERENCE = "ODOO_REVOLUT_SECRET_SYNTHETIC_DATABASE_SHOP"
    PAYMENT_ID = "bf0484b8-18af-4e1d-b442-257d323d9730"
    _order_payload = _SettlementFixtures._order_payload
    _save_return_draft = _RefundFixtures._save_return_draft
    _refund_response = _RefundFixtures._refund_response

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.authority = cls.env["pos.revolut.merchant.credential"].create({
            "company_id": cls.company.id, "environment": "sandbox",
            "secret_reference": cls.REFERENCE, "source": "database",
            "secret_key": "synthetic-original-shop-key",
        })
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Synthetic database shop terminal", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in", "revolut_secret_reference": cls.REFERENCE,
        })
        cls.pos_config.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
            "revolut_user_ids": [Command.link(cls.env.uid)],
        })
        cls.product = cls.env["product.product"].create({
            "name": "Synthetic database shop product", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })

    def setUp(self):
        super().setUp()
        self.pos_config.open_ui()
        self.session = self.pos_config.current_session_id
        self.session.write({"state": "opened"})
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
        self.enterContext(patch.dict(os.environ))
        os.environ.pop(self.REFERENCE, None)
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
        ))
        self.order_id, self.intent_id, self.payment_id = (str(uuid4()) for _ in range(3))

    def _response(self, **payload):
        response = Mock(status_code=200)
        response.json.return_value = payload
        return response

    def _start_sale(self):
        self.sale = self._order_payload(str(uuid4()), str(uuid4()))
        self.sale["payment_ids"][0][2].update(payment_status="waiting", transaction_id=False)
        self.request.side_effect = [
            self._response(terminals=[{
                "id": self.revolut_method.revolut_terminal_id, "online": True,
                "operation_mode": "pos", "location_id": self.revolut_method.revolut_location_id,
            }]),
            self._response(id=self.order_id),
            self._response(id=self.intent_id, state="pending"),
        ]
        started = authorized_start(
            self.revolut_method, self.session.id, self.sale["uuid"],
            self.sale["payment_ids"][0][2]["uuid"], 12.34,
            self.session.currency_id.id, False, self.sale,
        )
        self.assertEqual(started["state"], "pending")
        self.source = self.env["pos.revolut.payment.operation"].browse(started["operation_id"])
        self.source.invalidate_recordset()
        self.assertEqual(self.source.credential_id, self.authority)
        return started

    def _capture_sale(self, started, *, scheduled=False):
        self.request.side_effect = [
            self._response(id=self.intent_id, order_id=self.order_id,
                           state="completed", payment_id=self.payment_id),
            self._response(id=self.payment_id, order_id=self.order_id,
                           state="captured", amount=1234, currency=self.session.currency_id.name),
        ]
        install_zero_reports(self.env, self.request)
        if scheduled:
            self.env.ref("pos_revolut.ir_cron_reconcile_payments").method_direct_trigger()
        else:
            self.revolut_method.revolut_poll_payment(
                started["operation_id"], self.sale["uuid"], self.sale["payment_ids"][0][2]["uuid"],
            )
        self.env.invalidate_all()
        self.assertEqual(self.source.state, "verified")
        self.sale["payment_ids"][0][2].update(payment_status="done", transaction_id=self.payment_id)
        draft = self.env["pos.order"].search([("uuid", "=", self.sale["uuid"])])
        self.sale["id"] = draft.id
        for name in ("lines", "payment_ids"):
            existing = {row.uuid: row.id for row in draft[name]}
            self.sale[name] = [
                [Command.UPDATE, existing[command[2]["uuid"]], command[2]]
                if command[2]["uuid"] in existing else [Command.CREATE, 0, command[2]]
                for command in self.sale[name]
            ]
        self.env["pos.order"].sync_from_ui([deepcopy(self.sale)])
        self.source.invalidate_recordset()
        self.original = self.source.pos_order_id
        self.assertEqual(self.original.state, "paid")
        self.assertEqual(self.original.payment_ids.transaction_id, self.payment_id)

    def _rotate(self):
        replacement = self.env["pos.revolut.merchant.credential"].create({
            "company_id": self.company.id, "environment": "sandbox",
            "secret_reference": "ODOO_REVOLUT_SECRET_SYNTHETIC_DATABASE_ROTATED",
            "source": "database", "secret_key": "synthetic-new-shop-key",
        })
        # Test-only legacy/copy fixture: closure normally rejects pending
        # payments and native Odoo freezes open-session method configuration.
        # Bypass those guards only to exercise frozen authority recovery after
        # historical configuration changes; this is not an operational flow.
        self.env.flush_all()
        self.cr.execute("UPDATE pos_session SET state = 'closed' WHERE id = %s", [self.session.id])
        self.session.invalidate_recordset()
        self.revolut_method.write({"revolut_secret_reference": replacement.secret_reference})
        self.session.write({"state": "opened"})
        return replacement

    def _return_payload(self, amount):
        self.refund_id = str(uuid4())
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        self.payload.update(amount_total=-amount, amount_paid=-amount)
        self.payload["lines"][0][2].update(
            qty=-amount / 12.34, price_subtotal=-amount, price_subtotal_incl=-amount,
            refunded_orderline_id=self.original.lines.id,
        )
        self.payload["payment_ids"][0][2].update(amount=-amount, payment_status="waiting", transaction_id=False)

    def _start_return(self):
        self._save_return_draft()
        payment = self.payload["payment_ids"][0][2]
        return self.revolut_method.revolut_start_refund(
            self.session.id, self.payload["uuid"], payment["uuid"], payment["amount"],
            self.session.currency_id.id, self.payload,
            original_operation_id=self.source.id,
            base_amount_minor=round(-payment["amount"] * 100), tip_amount_minor=0,
        )

    def _finish_return(self, started, amount, *, scheduled=False):
        self.request.side_effect = [self._refund_response("completed", amount=round(amount * 100))]
        install_zero_reports(self.env, self.request)
        if scheduled:
            self.env["pos.revolut.refund.operation"].sudo().browse(started["operation_id"]).write({
                "next_reconcile_at": fields.Datetime.now(),
            })
            self.env.ref("pos_revolut.ir_cron_reconcile_refunds").method_direct_trigger()
        else:
            self.revolut_method.revolut_poll_refund(
                started["operation_id"], self.payload["uuid"], self.payload["payment_ids"][0][2]["uuid"],
            )
        self.env.invalidate_all()
        refund = self.env["pos.revolut.refund.operation"].browse(started["operation_id"])
        self.assertEqual(refund.state, "verified")
        self.payload["payment_ids"][0][2].update(payment_status="done", transaction_id=self.refund_id)
        self.env["pos.order"].sync_from_ui([deepcopy(self.payload)])
        refund.invalidate_recordset()
        self.assertEqual(refund.pos_order_id.state, "paid")
        self.assertEqual(refund.original_operation_id, self.source)
        self.assertEqual(refund.pos_payment_id.amount, -amount)
        return refund

    def test_database_setup_payment_and_full_refund_after_rotation(self):
        started = self._start_sale()
        self._capture_sale(started)
        self._rotate()
        self._return_payload(12.34)
        self.request.side_effect = [self._refund_response(amount=1234)]
        install_zero_reports(self.env, self.request)
        refund = self._start_return()
        self.assertEqual(refund["state"], "pending")
        self._finish_return(refund, 12.34)
        self.assertTrue(all(call.kwargs["headers"]["Authorization"] == "Bearer synthetic-original-shop-key"
                            for call in self.request.call_args_list))
        self.assertEqual(len(financial_posts(self.request)), 3)

    def test_database_pending_payment_and_partial_refund_recover_after_rotation(self):
        started = self._start_sale()
        self._rotate()
        self._capture_sale(started, scheduled=True)
        self._return_payload(6.17)
        self.request.side_effect = [self._refund_response(amount=617)]
        install_zero_reports(self.env, self.request)
        refund = self._start_return()
        self.assertEqual(refund["state"], "pending")
        self._finish_return(refund, 6.17, scheduled=True)
        self.assertEqual(self.source.secret_reference, self.REFERENCE)
        self.assertTrue(all(call.kwargs["headers"]["Authorization"] == "Bearer synthetic-original-shop-key"
                            for call in self.request.call_args_list))
        self.assertEqual(len(financial_posts(self.request)), 3)

    def test_revoked_original_key_blocks_refund_without_replacement(self):
        started = self._start_sale()
        self._capture_sale(started)
        self._rotate()
        self.authority.write({"revoked": True})
        self._return_payload(12.34)
        self.request.reset_mock(side_effect=True)
        with self.assertRaisesRegex(UserError, "revoked"):
            self._start_return()
        self.request.assert_not_called()
        self.assertFalse(self.env["pos.revolut.refund.operation"].search([
            ("order_uuid", "=", self.payload["uuid"]),
        ]))

    def test_foreign_method_cannot_poll_database_bound_operation(self):
        started = self._start_sale()
        foreign_method = self.revolut_method.copy({
            "name": "Another synthetic terminal", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in", "revolut_secret_reference": self.REFERENCE,
        })
        self.request.reset_mock(side_effect=True)
        with self.assertRaises(AccessError):
            foreign_method.revolut_poll_payment(
                started["operation_id"], self.sale["uuid"], self.sale["payment_ids"][0][2]["uuid"],
            )
        self.request.assert_not_called()
        self.source.invalidate_recordset()
        self.assertEqual(self.source.state, "pending")

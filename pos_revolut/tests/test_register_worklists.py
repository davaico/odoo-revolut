"""Financial search and direct reads respect live grants and native rules."""

from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, new_test_user

from .authorization_fixtures import native_products, prepare_fixture


class TestRevolutRegisterWorklists(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = new_test_user(
            cls.env, login="revolut_worklist_manager", groups="point_of_sale.group_pos_manager",
            company_id=cls.env.company.id, company_ids=[Command.set(cls.env.company.ids)],
        )
        cls.method = cls.env["pos.payment.method"].create({
            "name": "Revolut worklist fixture", "payment_method_type": "terminal",
            "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
            "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_WORKLIST_TEST",
        })
        cls.config = cls.env["pos.config"].create({
            "name": "Revolut worklist register", "auto_validate_terminal_payment": True,
            "payment_method_ids": [Command.link(cls.method.id)],
            "revolut_user_ids": [Command.link(cls.manager.id)],
        })
        cls.product = native_products(cls.env, cls.config)
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id, "state": "opened",
        })

    def setUp(self):
        super().setUp()
        mode = self.enter_registry_test_mode()
        mode.__enter__()
        self.addCleanup(mode.__exit__, None, None, None)
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Worklist access must not contact Revolut"),
        ))
        self.order_uuid, self.line_uuid = str(uuid4()), str(uuid4())
        self.snapshot = {
            "pricelist_id": self.config.pricelist_id.id, "fiscal_position_id": False,
            "lines": [{"uuid": str(uuid4()), "product_id": self.product.id, "qty": 1,
                       "price_unit": 12.34, "discount": 0, "tax_ids": []}],
        }
        authority = prepare_fixture(
            self.method.with_user(self.manager), self.session.id, self.order_uuid,
            self.line_uuid, 12.34, self.snapshot,
        )
        self.authority = self.env["pos.revolut.cart.authorization"].sudo().browse(authority["authorization_id"])
        self.order = self.authority.pos_order_id
        # Unassociated payment still binds the draft through cart authority.
        self.operation = self.env["pos.revolut.payment.operation"].sudo().create(
            self._operation_values(authorization_id=self.authority.id)
        )
        self.dispatch = self.env["pos.revolut.payment.dispatch"].sudo().create({
            "operation_id": self.operation.id, "action": "create_order", "outcome": "succeeded",
            "provider_reference": str(uuid4()),
        })
        self.audit = self.env["pos.revolut.reconciliation.audit"].sudo().create({
            "operation_id": self.operation.id, "company_id": self.env.company.id,
            "actor_id": self.manager.id, "action": "reconcile", "resulting_state": "unresolved",
            "evidence_reference": "mocked worklist evidence",
        })
        self.return_draft = self.env["pos.order"].create({
            "session_id": self.session.id, "uuid": str(uuid4()),
            "amount_total": 0, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
        })
        self.refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": self.operation.id, "pos_session_id": self.session.id,
            "order_uuid": self.return_draft.uuid, "payment_line_uuid": str(uuid4()),
            "amount": 1, "amount_minor": 100, "currency_id": self.session.currency_id.id,
            "financial_snapshot": {"fixture": "visibility only"},
        })
        self.lock = self.env["pos.revolut.order.lock"].sudo().search([
            ("company_id", "=", self.env.company.id), ("order_uuid", "=", self.order_uuid),
        ])
        self.assertTrue(self.lock)
        self.records = (
            (self.operation, "order_uuid"), (self.authority, "order_uuid"),
            (self.refund, "order_uuid"), (self.dispatch, "action"),
            (self.audit, "evidence_reference"), (self.lock, "order_uuid"),
        )
        self.caller_env = self.env["pos.config"].with_user(self.manager).with_context(
            allowed_company_ids=self.env.company.ids,
        ).env
        self.env.flush_all()

    def _operation_values(self, **extra):
        return {
            "payment_method_id": self.method.id, "company_id": self.env.company.id,
            "pos_config_id": self.config.id, "pos_session_id": self.session.id,
            "order_uuid": self.order_uuid, "payment_line_uuid": self.line_uuid,
            "amount": 12.34, "amount_minor": 1234,
            "currency_id": self.session.currency_id.id, "currency_code": self.session.currency_id.name,
            "environment": "sandbox", "location_id": self.method.revolut_location_id,
            "terminal_id": self.method.revolut_terminal_id, "fulfilment_type": "eat_in",
            "secret_reference": "ODOO_REVOLUT_SECRET_WORKLIST_TEST", "state": "unresolved",
            **extra,
        }

    def test_pending_refund_worklist_identifies_saved_return_without_settling_it(self):
        draft = self.return_draft
        evidence = self.refund.read(["pos_order_id", "native_reconciliation_status", "state"])
        row = call_kw(self.caller_env[self.refund._name], "read", [
            [self.refund.id], ["display_return_id", "native_completion_label"],
        ], {})[0]
        self.assertEqual(row["display_return_id"][0], draft.id)
        self.assertEqual(row["native_completion_label"], "Return awaiting refund confirmation")
        self.assertEqual(self.refund.read(["pos_order_id", "native_reconciliation_status", "state"]), evidence)
        self.request.assert_not_called()

    def _assert_visibility(self, allowed, records=None):
        for record, field in records or self.records:
            with self.subTest(model=record._name, allowed=allowed):
                model = self.caller_env[record._name]
                kwargs = {"context": dict(self.caller_env.context)}
                found = call_kw(model, "search_read", [[("id", "=", record.id)], [field]], kwargs)
                self.assertEqual([row["id"] for row in found], [record.id] if allowed else [])
                if allowed:
                    self.assertEqual(call_kw(model, "read", [[record.id], [field]], kwargs)[0]["id"], record.id)
                else:
                    with self.assertRaises(AccessError):
                        call_kw(model, "read", [[record.id], [field]], kwargs)
        self.request.assert_not_called()

    def _deny(self, model, record):
        return self.env["ir.rule"].sudo().create({
            "name": "Worklist native denial",
            "model_id": self.env["ir.model"]._get_id(model),
            "domain_force": f"[('id', '!=', {record.id})] if user.id == {self.manager.id} else []",
            "perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False,
        })

    def test_revocation_and_regrant_refresh_search_and_known_id_reads(self):
        self._assert_visibility(True)
        self.config.sudo().write({"revolut_user_ids": [Command.unlink(self.manager.id)]})
        self.env.flush_all()
        self._assert_visibility(False)
        self.config.sudo().write({"revolut_user_ids": [Command.link(self.manager.id)]})
        self.env.flush_all()
        self._assert_visibility(True)

    def test_each_native_rule_denies_financial_search_and_known_id_reads(self):
        self._assert_visibility(True)
        for model, record in (("pos.config", self.config), ("pos.session", self.session),
                              ("pos.order", self.order)):
            with self.subTest(native_model=model):
                rule = self._deny(model, record)
                self.env.flush_all()
                self._assert_visibility(False)
                rule.unlink()
                self.env.flush_all()
                self._assert_visibility(True)

    def test_legacy_unassociated_attempt_respects_matching_hidden_draft(self):
        legacy = self.env["pos.revolut.payment.operation"].sudo().create(
            self._operation_values(payment_line_uuid=str(uuid4()))
        )
        records = ((legacy, "order_uuid"),)
        self.assertFalse(legacy.pos_order_id)
        self.assertFalse(legacy.authorization_id)
        self.env.flush_all()
        self._assert_visibility(True, records)
        rule = self._deny("pos.order", self.order)
        self.env.flush_all()
        self._assert_visibility(False, records)
        rule.unlink()
        self.env.flush_all()
        self._assert_visibility(True, records)

    def test_orphan_lock_cannot_supply_register_authority(self):
        orphan = self.env["pos.revolut.order.lock"].sudo().create({
            "company_id": self.env.company.id, "order_uuid": str(uuid4()),
        })
        self.env.flush_all()
        self._assert_visibility(False, ((orphan, "order_uuid"),))
        self._assert_visibility(True, ((self.lock, "order_uuid"),))

    def test_refund_return_register_requires_its_own_grant_and_native_access(self):
        other = self.config.copy({"name": "Separate refund return register"})
        session = self.env["pos.session"].create({"config_id": other.id, "state": "opened"})
        refund = self.env["pos.revolut.refund.operation"].sudo().create({
            "original_operation_id": self.operation.id, "pos_session_id": session.id,
            "order_uuid": str(uuid4()), "payment_line_uuid": str(uuid4()),
            "amount": 1, "amount_minor": 100, "currency_id": session.currency_id.id,
            "financial_snapshot": {"fixture": "historical return visibility"},
        })
        records = ((refund, "order_uuid"),)
        self.env.flush_all()
        self._assert_visibility(False, records)
        other.sudo().write({"revolut_user_ids": [Command.link(self.manager.id)]})
        self.env.flush_all()
        self._assert_visibility(True, records)
        rule = self._deny("pos.session", session)
        self.env.flush_all()
        self._assert_visibility(False, records)
        rule.unlink()
        self.env.flush_all()
        self._assert_visibility(True, records)

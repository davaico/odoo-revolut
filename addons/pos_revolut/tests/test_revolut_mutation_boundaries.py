from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from odoo import Command
from odoo.addons.point_of_sale.tests.common import CommonPosTest
from odoo.exceptions import AccessError, UserError
from odoo.service.model import call_kw
from odoo.tests.common import new_test_user, tagged

from .test_revolut_payment import TestRevolutOrderSettlement


@tagged("post_install", "-at_install")
class TestRevolutMutationBoundaries(CommonPosTest):
    LOCATION_ID = TestRevolutOrderSettlement.LOCATION_ID
    TERMINAL_ID = TestRevolutOrderSettlement.TERMINAL_ID
    PAYMENT_ID = TestRevolutOrderSettlement.PAYMENT_ID
    _operation = TestRevolutOrderSettlement._operation
    _order_payload = TestRevolutOrderSettlement._order_payload

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.revolut_method = cls.bank_payment_method.copy({
            "name": "Revolut mutation boundary test",
            "payment_method_type": "terminal", "use_payment_terminal": "revolut",
            "revolut_environment": "sandbox",
            "revolut_location_id": cls.LOCATION_ID,
            "revolut_terminal_id": cls.TERMINAL_ID,
            "revolut_fulfilment_type": "eat_in",
            "revolut_secret_reference": "ODOO_REVOLUT_SECRET_SETTLEMENT_TEST",
        })
        cls.pos_config_usd.write({
            "payment_method_ids": [Command.link(cls.revolut_method.id)],
            "auto_validate_terminal_payment": True,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Mutation boundary product", "available_in_pos": True,
            "list_price": 12.34, "taxes_id": [Command.clear()],
        })
        cls.cashier = new_test_user(
            cls.env, login="revolut_mutation_cashier",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )
        cls.other_company = cls.env["res.company"].create({"name": "Mutation foreign company"})
        cls.manager = new_test_user(
            cls.env, login="revolut_mutation_manager",
            groups="base.group_user,point_of_sale.group_pos_manager",
            company_id=cls.company.id, company_ids=[Command.set([cls.company.id])],
        )
        cls.multi_manager = new_test_user(
            cls.env, login="revolut_mutation_multi_manager",
            groups="base.group_user,point_of_sale.group_pos_manager",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id, cls.other_company.id])],
        )
        cls.unauthorized = new_test_user(
            cls.env, login="revolut_mutation_unauthorized", groups="base.group_user",
            company_id=cls.company.id, company_ids=[Command.set([cls.company.id])],
        )

    def setUp(self):
        super().setUp()
        self.pos_config_usd.open_ui()
        self.session = self.pos_config_usd.current_session_id
        self.session.write({"state": "opened"})
        self.payload = self._order_payload(str(uuid4()), str(uuid4()))
        self.payload.update(state="draft", user_id=self.cashier.id)
        self.request = self.enterContext(patch(
            "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
            side_effect=AssertionError("Direct settlement must not call Revolut"),
        ))

    def tearDown(self):
        self.request.assert_not_called()
        super().tearDown()

    def _rpc(self, model, method, args, user=None, **context):
        return call_kw(self.env[model].with_user(user or self.cashier), method, args, {
            "context": {"allowed_company_ids": [self.company.id], **context},
        })

    def _matched_operation_payload(self, state="verified", amount=12.34):
        payload = deepcopy(self.payload)
        payload["uuid"] = str(uuid4())
        payload["lines"][0][2]["uuid"] = str(uuid4())
        payment = payload["payment_ids"][0][2]
        payment["uuid"] = str(uuid4())
        payment["amount"] = amount
        payload["amount_paid"] = amount
        operation = self._operation(
            payload["uuid"], payment["uuid"], state=state,
            amount=amount, amount_minor=round(amount * 100),
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        )
        payment["payment_status"] = "done" if state == "verified" else "waiting"
        payment["transaction_id"] = operation.revolut_payment_id if state == "verified" else False
        return payload, operation

    def _draft_with_operation(self, state="verified", amount=12.34):
        payload, operation = self._matched_operation_payload(state, amount)
        order_id = self._rpc("pos.order", "create", [payload])
        return self.env["pos.order"].browse(order_id), operation

    def test_public_create_rejects_fabricated_done_tender_atomically(self):
        self.assertFalse(self.env["pos.order"].with_user(self.cashier).env.su)
        self.assertFalse(self.cashier.has_group("point_of_sale.group_pos_manager"))
        with TestCase.assertRaisesRegex(self, UserError, "Revolut payment has not been verified"):
            self._rpc("pos.order", "create", [deepcopy(self.payload)])
        self.assertFalse(self.env["pos.order"].search([
            ("uuid", "=", self.payload["uuid"]),
        ]))
        self.assertFalse(self.env["pos.payment"].search([
            ("uuid", "=", self.payload["payment_ids"][0][2]["uuid"]),
        ]))

    def test_inherited_add_payment_rejects_fabricated_settlement_atomically(self):
        payment = dict(self.payload.pop("payment_ids")[0][2])
        self.payload["amount_paid"] = 0
        order_id = self._rpc("pos.order", "create", [self.payload])
        payment["pos_order_id"] = order_id
        with TestCase.assertRaisesRegex(self, UserError, "Revolut payment has not been verified"):
            self._rpc("pos.order", "add_payment", [[order_id], payment])
        order = self.env["pos.order"].browse(order_id)
        self.assertEqual(order.state, "draft")
        self.assertEqual(order.amount_paid, 0)
        self.assertFalse(order.payment_ids)

    def test_public_finalizers_reject_waiting_unverified_tender(self):
        self.payload["payment_ids"][0][2]["payment_status"] = "waiting"
        order_id = self._rpc("pos.order", "create", [self.payload])
        for method, args in (
            ("action_pos_order_paid", [[order_id]]),
            ("write", [[order_id], {"state": "paid"}]),
            ("write", [[order_id], {"state": "done"}]),
        ):
            with self.subTest(method=method, args=args):
                with TestCase.assertRaisesRegex(self, UserError, "Revolut payment has not been verified"):
                    self._rpc("pos.order", method, args)
                self.assertEqual(self.env["pos.order"].browse(order_id).state, "draft")

    def test_direct_payment_edits_cannot_detach_or_change_verified_evidence(self):
        for values in (
            {"revolut_operation_id": False}, {"amount": 10},
            {"uuid": str(uuid4())}, {"payment_status": "waiting"},
            {"transaction_id": str(uuid4())}, {"payment_ref_no": str(uuid4())},
            {"revolut_order_id": False}, {"revolut_payment_intent_id": str(uuid4())},
            {"payment_method_id": self.cash_payment_method.id},
        ):
            with self.subTest(values=values):
                order, operation = self._draft_with_operation()
                payment = order.payment_ids
                proof_fields = ["uuid", "amount", "payment_method_id", "pos_order_id",
                                "payment_status", "transaction_id", "payment_ref_no",
                                "revolut_order_id", "revolut_payment_intent_id",
                                "revolut_operation_id", "revolut_refund_operation_id"]
                before = payment.read(proof_fields)[0]
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.payment", "write", [[payment.id], values],
                              skip_revolut_validation=True, revolut_internal=True)
                self.assertEqual(payment.read(proof_fields)[0], before)
                self.assertEqual(operation.pos_order_id, order)
                self.assertEqual(operation.pos_payment_id, payment)

    def test_unlink_and_relational_commands_cannot_remove_financial_evidence(self):
        for model, relation in (("pos.order", None), ("pos.payment", "payment_ids"),
                                ("pos.order.line", "lines")):
            with self.subTest(model=model):
                order, operation = self._draft_with_operation()
                record = order[relation] if relation else order
                with TestCase.assertRaises(self, UserError):
                    self._rpc(model, "unlink", [[record.id]])
                self.assertTrue(record.exists())
                self.assertEqual(operation.pos_order_id, order)
        for relation in ("lines", "payment_ids"):
            order, operation = self._draft_with_operation()
            before = order[relation].ids
            with TestCase.assertRaises(self, UserError):
                self._rpc("pos.order", "write", [[order.id], {relation: [Command.clear()]}])
            self.assertEqual(order[relation].ids, before)
            self.assertEqual(operation.pos_order_id, order)

    def test_direct_line_creation_cannot_extend_a_verified_cart(self):
        order, operation = self._draft_with_operation()
        line = dict(self.payload["lines"][0][2], uuid=str(uuid4()), order_id=order.id)
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order.line", "create", [line])
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(operation.pos_order_id, order)

    def test_pending_operation_cannot_be_finalized_substituted_or_erased(self):
        order, operation = self._draft_with_operation(state="pending")
        payment = order.payment_ids
        for model, method, args in (
            ("pos.order", "action_pos_order_paid", [[order.id]]),
            ("pos.payment", "write", [[payment.id], {"payment_status": "done"}]),
            ("pos.payment", "write", [[payment.id], {"payment_method_id": self.cash_payment_method.id}]),
            ("pos.payment", "unlink", [[payment.id]]),
            ("pos.order", "unlink", [[order.id]]),
            ("pos.order", "action_pos_order_cancel", [[order.id]]),
            ("pos.order", "remove_from_ui", [[order.id]]),
        ):
            with self.subTest(model=model, method=method, args=args):
                with TestCase.assertRaises(self, UserError):
                    self._rpc(model, method, args)
                self.assertEqual(order.state, "draft")
                self.assertEqual(order.payment_ids, payment)
                self.assertEqual(payment.payment_method_id, self.revolut_method)
                self.assertEqual(payment.payment_status, "waiting")
                self.assertEqual(operation.state, "pending")
                self.assertFalse(operation.pos_payment_id)

    def test_order_identity_and_contents_remain_protected_after_exposure(self):
        for values in ({"uuid": str(uuid4())}, {"amount_total": 99},
                       {"amount_tax": 99}, {"lines": [Command.clear()]}):
            with self.subTest(values=values):
                order, operation = self._draft_with_operation()
                protected = ["uuid", "session_id", "company_id", "state", "amount_total",
                             "amount_tax", "amount_paid", "lines", "payment_ids"]
                before = order.read(protected)[0]
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "write", [[order.id], values])
                self.assertEqual(order.read(protected)[0], before)
                self.assertEqual(operation.pos_order_id, order)

    def test_direct_cart_line_mutations_cannot_change_verified_contents(self):
        for values in ({"qty": 2}, {"price_unit": 99}, {"discount": 20},
                       {"uuid": str(uuid4())}):
            with self.subTest(values=values):
                order, operation = self._draft_with_operation()
                protected = ["uuid", "order_id", "qty", "price_unit", "discount", "tax_ids"]
                before = order.lines.read(protected)[0]
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order.line", "write", [[order.lines.id], values])
                self.assertEqual(order.lines.read(protected)[0], before)
                self.assertEqual(operation.pos_order_id, order)

    def test_supplied_operation_and_provider_references_must_match(self):
        for field in ("revolut_operation_id", "revolut_order_id",
                      "revolut_payment_intent_id", "payment_ref_no"):
            with self.subTest(field=field):
                payload = deepcopy(self.payload)
                payload["uuid"] = str(uuid4())
                payload["lines"][0][2]["uuid"] = str(uuid4())
                payment = payload["payment_ids"][0][2]
                payment["uuid"] = str(uuid4())
                operation = self._operation(
                    payload["uuid"], payment["uuid"],
                    financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
                )
                payment["transaction_id"] = operation.revolut_payment_id
                payment[field] = self._operation(str(uuid4()), str(uuid4())).id if field == "revolut_operation_id" else str(uuid4())
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "create", [payload])
                self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
                self.assertFalse(operation.pos_order_id)

    def test_original_line_subtotals_cannot_be_changed_after_verification(self):
        order, operation = self._draft_with_operation()
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order.line", "write", [[order.lines.id], {"price_subtotal_incl": 99}])
        self.assertEqual(order.lines.price_subtotal_incl, 12.34)
        self.assertEqual(operation.pos_order_id, order)

    def test_verified_public_checkout_and_cash_bank_checkout_remain_allowed(self):
        order, operation = self._draft_with_operation()
        self._rpc("pos.order", "action_pos_order_paid", [[order.id]])
        self.assertEqual(order.state, "paid")
        self.assertEqual(operation.pos_payment_id, order.payment_ids)
        for method in (self.cash_payment_method, self.bank_payment_method):
            payload = self._order_payload(str(uuid4()), str(uuid4()), payment_method=method)
            payload.update(state="draft", user_id=self.cashier.id)
            order_id = self._rpc("pos.order", "create", [payload])
            self._rpc("pos.order", "action_pos_order_paid", [[order_id]])
            self.assertEqual(self.env["pos.order"].browse(order_id).state, "paid")

    def test_missing_pending_failed_and_mismatched_evidence_cannot_be_created_done(self):
        for mismatch in ("pending", "failed", "amount", "currency", "company", "cart"):
            with self.subTest(mismatch=mismatch):
                payload = deepcopy(self.payload)
                payload["uuid"] = str(uuid4())
                payload["lines"][0][2]["uuid"] = str(uuid4())
                payment = payload["payment_ids"][0][2]
                payment["uuid"] = str(uuid4())
                snapshot = self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload)
                values = {"financial_snapshot": snapshot, "blocking_terminal_key": False}
                if mismatch in {"pending", "failed"}:
                    values["state"] = mismatch
                    values["retry_safe"] = mismatch == "failed"
                elif mismatch == "amount":
                    values.update(amount=10, amount_minor=1000)
                elif mismatch == "currency":
                    values["currency_id"] = self.env.ref("base.EUR").id
                elif mismatch == "cart":
                    snapshot["lines"][0]["qty"] = "2"
                operation = self._operation(payload["uuid"], payment["uuid"], **values)
                if mismatch == "company":
                    # The create boundary now prevents this mismatch. Preserve
                    # coverage of corrupt pre-upgrade settlement evidence.
                    self.cr.execute(
                        "UPDATE pos_revolut_payment_operation SET company_id = %s WHERE id = %s",
                        [self.other_company.id, operation.id],
                    )
                    operation.invalidate_recordset()
                payment["transaction_id"] = operation.revolut_payment_id
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "create", [payload])
                self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
                self.assertFalse(operation.pos_order_id)

    def test_reassignment_and_reused_cash_reference_are_rejected_on_both_orders(self):
        order, operation = self._draft_with_operation()
        destination = deepcopy(self.payload)
        destination.update(uuid=str(uuid4()), payment_ids=[], amount_paid=0)
        destination["lines"][0][2]["uuid"] = str(uuid4())
        other = self.env["pos.order"].browse(self._rpc("pos.order", "create", [destination]))
        for model, record, field in (("pos.payment", order.payment_ids, "pos_order_id"),
                                     ("pos.order.line", order.lines, "order_id")):
            with TestCase.assertRaises(self, UserError):
                self._rpc(model, "write", [[record.id], {field: other.id}])
            self.assertEqual(record[field], order)
        forged = self._order_payload(str(uuid4()), str(uuid4()), payment_method=self.cash_payment_method,
                                     transaction_id=operation.revolut_payment_id)
        forged.update(state="paid", user_id=self.cashier.id)
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order", "create", [forged])
        self.assertFalse(other.payment_ids)
        self.assertEqual(operation.pos_order_id, order)

    def test_unauthorized_and_restricted_company_roles_cannot_mutate_orders(self):
        order, operation = self._draft_with_operation()
        for user, companies in ((self.unauthorized, [self.company.id]),
                                (self.multi_manager, [self.other_company.id])):
            with TestCase.assertRaises(self, AccessError):
                self._rpc("pos.order", "write", [[order.id], {"amount_total": 99}],
                          user=user, allowed_company_ids=companies)
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order", "write", [[order.id], {"uuid": str(uuid4())}], user=self.manager)
        self.assertEqual(operation.pos_order_id, order)

    def test_batch_creation_rejection_rolls_back_the_valid_order_too(self):
        cash = self._order_payload(str(uuid4()), str(uuid4()), payment_method=self.cash_payment_method)
        cash.update(state="draft", user_id=self.cashier.id)
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order", "create", [[cash, deepcopy(self.payload)]])
        self.assertFalse(self.env["pos.order"].search([("uuid", "in", [cash["uuid"], self.payload["uuid"]])]))

    def test_order_company_must_match_the_verified_operation_and_session(self):
        payload = deepcopy(self.payload)
        payment = payload["payment_ids"][0][2]
        operation = self._operation(
            payload["uuid"], payment["uuid"],
            financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
        )
        payment["transaction_id"] = operation.revolut_payment_id
        payload["company_id"] = self.other_company.id
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order", "create", [payload], user=self.multi_manager,
                      allowed_company_ids=[self.company.id, self.other_company.id])
        self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
        self.assertFalse(operation.pos_order_id)

    def test_public_order_lock_helper_cannot_mutate_internal_records(self):
        for user, company_id, companies in (
            (self.cashier, self.other_company.id, [self.company.id]),
            (self.manager, self.company.id, [self.company.id]),
            (self.multi_manager, self.company.id, [self.other_company.id]),
            (self.unauthorized, self.company.id, [self.company.id]),
        ):
            with self.subTest(user=user.login, company=company_id):
                order_uuid = str(uuid4())
                with TestCase.assertRaises(self, (AttributeError, AccessError)):
                    self._rpc("pos.revolut.payment.operation", "lock_order", [company_id, order_uuid],
                              user=user, allowed_company_ids=companies)
                self.assertFalse(self.env["pos.revolut.order.lock"].sudo().search([
                    ("company_id", "=", company_id), ("order_uuid", "=", order_uuid),
                ]))
                with TestCase.assertRaises(self, AccessError):
                    self._rpc("pos.revolut.payment.operation", "_lock_order", [company_id, order_uuid],
                              user=user, allowed_company_ids=companies)

    def test_direct_pos_configuration_reassignment_cannot_escape_session_ownership(self):
        order, operation = self._draft_with_operation()
        other_config = self.pos_config_usd.copy({"name": "Foreign POS ownership destination"})
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order", "write", [[order.id], {"config_id": other_config.id}])
        self.assertEqual(order.config_id, self.session.config_id)
        self.assertEqual(operation.pos_config_id, order.config_id)

    def test_stored_related_payment_and_line_ownership_cannot_diverge(self):
        other_config = self.pos_config_usd.copy({"name": "Other payment session ownership"})
        other_session = self.env["pos.session"].create({
            "config_id": other_config.id, "user_id": self.cashier.id,
        })
        for model, relation, values in (
            ("pos.payment", "payment_ids", {"company_id": self.other_company.id}),
            ("pos.payment", "payment_ids", {"session_id": other_session.id}),
            ("pos.order.line", "lines", {"company_id": self.other_company.id}),
        ):
            with self.subTest(model=model, values=values):
                order, operation = self._draft_with_operation()
                record = order[relation]
                before = record.read(list(values))[0]
                with TestCase.assertRaises(self, UserError):
                    self._rpc(model, "write", [[record.id], values], user=self.multi_manager,
                              allowed_company_ids=[self.company.id, self.other_company.id])
                self.assertEqual(record.read(list(values))[0], before)
                self.assertEqual(operation.pos_order_id, order)

    def test_exposed_conversion_rate_and_refund_document_type_are_immutable(self):
        for values in ({"currency_rate": 2.0}, {"is_refund": True}):
            with self.subTest(values=values):
                order, operation = self._draft_with_operation()
                before = order.read(list(values))[0]
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "write", [[order.id], values])
                self.assertEqual(order.read(list(values))[0], before)
                self.assertEqual(operation.pos_order_id, order)

    def test_public_create_normalizes_stored_child_ownership(self):
        for relation in ("lines", "payment_ids"):
            with self.subTest(relation=relation):
                payload = deepcopy(self.payload)
                payload["uuid"] = str(uuid4())
                payload["lines"][0][2]["uuid"] = str(uuid4())
                payment = payload["payment_ids"][0][2]
                payment["uuid"] = str(uuid4())
                operation = self._operation(
                    payload["uuid"], payment["uuid"],
                    financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
                )
                payment["transaction_id"] = operation.revolut_payment_id
                payload[relation][0][2]["company_id"] = self.other_company.id
                order_id = self._rpc("pos.order", "create", [payload], user=self.multi_manager,
                                     allowed_company_ids=[self.company.id, self.other_company.id])
                order = self.env["pos.order"].browse(order_id)
                self.assertEqual(order.lines.company_id, order.company_id)
                self.assertEqual(order.payment_ids.company_id, order.company_id)
                self.assertEqual(order.payment_ids.session_id, order.session_id)
                self.assertEqual(operation.pos_order_id, order)

    def test_date_change_cannot_recompute_an_exposed_conversion_rate(self):
        order, operation = self._draft_with_operation()
        before = (order.date_order, order.currency_rate)
        with patch.object(type(self.env["res.currency"]), "_get_conversion_rate", return_value=2.0):
            with TestCase.assertRaises(self, UserError):
                self._rpc("pos.order", "write", [[order.id], {"date_order": "2000-01-01 12:00:00"}])
        self.assertEqual((order.date_order, order.currency_rate), before)
        self.assertEqual(operation.pos_order_id, order)

    def test_public_create_checks_document_classification_and_normalizes_rate(self):
        for values in ({"is_refund": True}, {"currency_rate": 2.0}):
            with self.subTest(values=values):
                payload = deepcopy(self.payload)
                payload.update(uuid=str(uuid4()), **values)
                payload["lines"][0][2]["uuid"] = str(uuid4())
                payment = payload["payment_ids"][0][2]
                payment["uuid"] = str(uuid4())
                operation = self._operation(
                    payload["uuid"], payment["uuid"],
                    financial_snapshot=self.env["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
                )
                payment["transaction_id"] = operation.revolut_payment_id
                if values.get("is_refund"):
                    with TestCase.assertRaises(self, UserError):
                        self._rpc("pos.order", "create", [payload])
                    self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
                    self.assertFalse(operation.pos_order_id)
                else:
                    order_id = self._rpc("pos.order", "create", [payload])
                    order = self.env["pos.order"].browse(order_id)
                    rate = self.env["res.currency"]._get_conversion_rate(
                        order.company_id.currency_id, order.currency_id,
                        order.company_id, order.date_order.date(),
                    )
                    self.assertEqual(order.currency_rate, rate)
                    self.assertEqual(operation.pos_order_id, order)

    def test_initial_stored_line_subtotals_must_match_the_verified_cart(self):
        for name in ("price_subtotal", "price_subtotal_incl"):
            with self.subTest(field=name):
                payload, operation = self._matched_operation_payload()
                payload["lines"][0][2][name] = 99
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "create", [payload])
                self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
                self.assertFalse(operation.pos_order_id)

    def test_public_finalization_requires_the_complete_split_balance(self):
        for state in ("paid", "done"):
            with self.subTest(state=state):
                payload, operation = self._matched_operation_payload(amount=6.17)
                payload["state"] = state
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "create", [payload])
                self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
                self.assertFalse(operation.pos_order_id)
                order, operation = self._draft_with_operation(amount=6.17)
                with TestCase.assertRaises(self, UserError):
                    self._rpc("pos.order", "write", [[order.id], {"state": state}])
                self.assertEqual(order.state, "draft")
                self.assertEqual(order.amount_paid, 6.17)
                self.assertEqual(operation.pos_order_id, order)
                cash = dict(self.payload["payment_ids"][0][2], uuid=str(uuid4()),
                            amount=6.17, payment_method_id=self.cash_payment_method.id,
                            transaction_id=False, pos_order_id=order.id)
                self._rpc("pos.order", "write", [[order.id], {
                    "payment_ids": [Command.create(cash)],
                }])
                self._rpc("pos.order", "write", [[order.id], {"state": state}])
                self.assertEqual(order.state, state)
                self.assertEqual(order.amount_paid, 12.34)

    def test_cash_return_origin_cannot_reduce_a_verified_sale_balance(self):
        original = self._order_payload(str(uuid4()), str(uuid4()), payment_method=self.cash_payment_method)
        original.update(amount_total=-12.34, amount_paid=-6.17, user_id=self.cashier.id)
        original["lines"][0][2].update(qty=-1, price_subtotal=-12.34, price_subtotal_incl=-12.34)
        original["payment_ids"][0][2].update(amount=-6.17, transaction_id=False)
        original_id = self._rpc("pos.order", "create", [original])
        original_line = self.env["pos.order"].browse(original_id).lines
        payload, operation = self._matched_operation_payload(amount=6.17)
        payload["state"] = "paid"
        payload["lines"][0][2]["refunded_orderline_id"] = original_line.id
        with TestCase.assertRaises(self, UserError):
            self._rpc("pos.order", "create", [payload])
        self.assertFalse(self.env["pos.order"].search([("uuid", "=", payload["uuid"])]))
        self.assertFalse(operation.pos_order_id)

    def test_unexposed_waiting_drafts_can_be_cancelled_and_removed(self):
        for method, args_for_id in (
            ("action_pos_order_cancel", lambda order_id: [[order_id]]),
            ("remove_from_ui", lambda order_id: [[order_id]]),
        ):
            with self.subTest(method=method):
                payload = deepcopy(self.payload)
                payload["uuid"] = str(uuid4())
                payload["lines"][0][2]["uuid"] = str(uuid4())
                payload["payment_ids"][0][2].update(uuid=str(uuid4()), payment_status="waiting")
                order_id = self._rpc("pos.order", "create", [payload])
                self._rpc("pos.order", method, args_for_id(order_id))
                order = self.env["pos.order"].browse(order_id).exists()
                self.assertTrue(not order or order.state == "cancel")

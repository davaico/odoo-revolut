"""Persist historical Odoo 18 invoice/partial-return fixtures for actual PDFs."""
import json
import os
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import Command, fields
from odoo.addons.pos_revolut.tests.test_revolut_terminal_tip import TerminalTipFixtures

company = env["res.company"].create({
    "name": "Native document verification", "country_id": env.ref("base.us").id,
    "currency_id": env.ref("base.USD").id,
})
env["account.chart.template"].try_loading("generic_coa", company)
native = env(context={**env.context, "allowed_company_ids": company.ids})
native["stock.warehouse"].create({
    "name": "Native document warehouse", "code": "DOC", "company_id": company.id,
})
manager = native["res.users"].create({
    "name": "Native document manager", "login": "native-document-manager",
    "company_id": company.id, "company_ids": [Command.set(company.ids)],
    "groups_id": [Command.set([env.ref("base.group_user").id,
                              env.ref("point_of_sale.group_pos_manager").id])],
})
env.ref("base.user_admin").write({"company_ids": [Command.link(company.id)]})
method = native["pos.payment.method"].create({
    "name": "Synthetic Revolut", "payment_method_type": "terminal",
    "journal_id": native["account.journal"].search([("type", "=", "bank"),
                                                                 ("company_id", "=", company.id)], limit=1).id,
    "use_payment_terminal": "revolut", "revolut_environment": "sandbox",
    "revolut_location_id": str(uuid4()), "revolut_terminal_id": str(uuid4()),
    "revolut_fulfilment_type": "eat_in",
    "revolut_secret_reference": "ODOO_REVOLUT_SECRET_TEST_TERMINAL",
})
config = native["pos.config"].create({
    "name": "Historical document register", "payment_method_ids": [Command.set(method.ids)],
    "auto_validate_terminal_payment": True,
})
config.with_user(manager).open_ui()
session = config.current_session_id
session.set_opening_control(0, "Synthetic native document fixture")
partner = native["res.partner"].create({"name": "Historical document customer"})
product = native["product.product"].create({
    "name": "Historical document service", "type": "service", "available_in_pos": True,
    "list_price": 12.34, "taxes_id": [Command.clear()],
})
event = fields.Datetime.now() - timedelta(days=8)
reference, payment_uuid = str(uuid4()), str(uuid4())
payload = {
    "uuid": str(uuid4()), "name": "Historical verified sale", "session_id": session.id,
    "user_id": env.uid, "state": "paid", "sequence_number": 1, "partner_id": partner.id,
    "pricelist_id": config.pricelist_id.id, "fiscal_position_id": False,
    "amount_total": 12.34, "amount_tax": 0, "amount_paid": 12.34, "amount_return": 0,
    "date_order": fields.Datetime.to_string(event), "to_invoice": False,
    "lines": [Command.create({
        "uuid": str(uuid4()), "product_id": product.id, "qty": 1, "price_unit": 12.34,
        "discount": 0, "tax_ids": [Command.set([])], "price_subtotal": 12.34,
        "price_subtotal_incl": 12.34, "pack_lot_ids": [],
    })],
    "payment_ids": [Command.create({
        "uuid": payment_uuid, "payment_method_id": method.id, "amount": 12.34,
        "payment_status": "done", "transaction_id": reference, "payment_ref_no": reference,
        "ticket": f"Revolut payment: {reference}",
    })],
}
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Native document fixtures must not contact Revolut")) as provider:
    source = native["pos.revolut.payment.operation"].create({
        "payment_method_id": method.id, "company_id": company.id, "pos_config_id": config.id,
        "pos_session_id": session.id, "order_uuid": payload["uuid"], "payment_line_uuid": payment_uuid,
        "amount": 12.34, "amount_minor": 1234, "currency_id": company.currency_id.id,
        "currency_code": company.currency_id.name, "environment": "sandbox",
        "location_id": method.revolut_location_id, "terminal_id": method.revolut_terminal_id,
        "fulfilment_type": "eat_in", "secret_reference": method.revolut_secret_reference,
        "state": "verified", "provider_state": "captured", "verified_at": event,
        "revolut_order_id": str(uuid4()), "revolut_payment_intent_id": str(uuid4()),
        "revolut_payment_id": reference,
        "financial_snapshot": native["pos.revolut.payment.operation"]._normalize_financial_snapshot(payload),
    })
    payload["payment_ids"][0][2]["payment_ref_no"] = source.revolut_order_id
    native["pos.order"].sync_from_ui([payload])
    source.invalidate_recordset()
    original = source.pos_order_id
    orders = original
    refunds = native["pos.revolut.refund.operation"]
    for quantity, minor in ((0.25, 309), (0.75, 925)):
        refund_reference = str(uuid4())
        returned = dict(payload, uuid=str(uuid4()), name=f"Historical partial return {minor}",
                        amount_total=-minor / 100, amount_paid=-minor / 100)
        returned["lines"] = [Command.create(dict(payload["lines"][0][2], uuid=str(uuid4()),
            qty=-quantity, price_subtotal=-12.34 * quantity, price_subtotal_incl=-12.34 * quantity,
            refunded_orderline_id=original.lines.id))]
        returned["payment_ids"] = [Command.create(dict(payload["payment_ids"][0][2],
            uuid=str(uuid4()), amount=-minor / 100, transaction_id=refund_reference,
            payment_ref_no=refund_reference, ticket=f"Revolut refund: {refund_reference}"))]
        refund = native["pos.revolut.refund.operation"].create({
            "original_operation_id": source.id, "pos_session_id": session.id,
            "order_uuid": returned["uuid"], "payment_line_uuid": returned["payment_ids"][0][2]["uuid"],
            "amount": minor / 100, "amount_minor": minor, "return_total_minor": minor,
            "currency_id": company.currency_id.id, "state": "verified", "provider_state": "completed",
            "verified_at": event + timedelta(days=1), "revolut_order_id": refund_reference,
            "financial_snapshot": native["pos.revolut.payment.operation"]._normalize_financial_snapshot(returned),
        })
        native["pos.order"].sync_from_ui([returned])
        refund.invalidate_recordset()
        assert refund.pos_order_id.amount_total == -minor / 100
        orders |= refund.pos_order_id
        refunds |= refund
    # Real session posting followed by later invoicing, rather than setting closed.
    session.close_session_from_ui()
    assert session.state == "closed"
    moves = native["account.move"]
    for order, total in zip(orders, (12.34, 3.09, 9.25)):
        order.with_context(generate_pdf=False).action_pos_order_invoice()
        move = order.account_move
        assert move.state == "posted" and move.amount_total == total
        assert move.move_type == ("out_invoice" if order == original else "out_refund")
        moves |= move
    config.with_user(manager).open_ui()
    config.current_session_id.set_opening_control(0, "Fresh register after historical close")
    assert orders.session_id == session and session.state == "closed"
    provider.assert_not_called()

# Exercise the authenticated report-based tip path on a new register session.
# Three decimal price precision requires a conserved .07 base for a .09 tip
# with .02 native tax. Native rounding cannot represent .09 from its raw
# .075 unit price, so the accepted base must be conserved explicitly.
tip_session = config.current_session_id
company.tax_calculation_rounding_method = "round_globally"
env.ref("product.decimal_price").digits = 3
env.flush_all()
env.registry.clear_cache()
assert native["decimal.precision"].precision_get("Product Price") == 3
tax_group = native["account.tax.group"].create({"name": "Tip tax 20%", "company_id": company.id})
tax = native["account.tax"].create({
    "name": "Tip tax 20%", "amount": 20, "tax_group_id": tax_group.id,
    "amount_type": "percent", "company_id": company.id,
})
tip_product = native["product.product"].create({
    "name": "Authenticated conserved terminal tip", "type": "service", "list_price": 0,
    "taxes_id": [Command.set(tax.ids)],
})
tip_goods = native["product.product"].create({
    "name": "Historical document service", "type": "service", "available_in_pos": True,
    "list_price": 100, "taxes_id": [Command.clear()],
})
config.write({"tip_product_id": tip_product.id, "revolut_user_ids": [Command.link(env.uid)]})
tip_sale = native["pos.order"].create({
    "session_id": tip_session.id, "uuid": str(uuid4()), "partner_id": partner.id,
    "amount_total": 100, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
    "pricelist_id": config.pricelist_id.id,
    "lines": [Command.create({"uuid": str(uuid4()), "product_id": tip_goods.id,
        "qty": 1, "price_unit": 100, "price_subtotal": 100, "price_subtotal_incl": 100,
        "tax_ids": [Command.clear()]})],
})
tip_fixture = TerminalTipFixtures()
tip_fixture.method, tip_fixture.order = method, tip_sale
tip_fixture.provider_order_id, tip_fixture.provider_intent_id, tip_fixture.provider_payment_id = [str(uuid4()) for _ in range(3)]
tip_fixture.gross_minor, tip_fixture.tip_minor = 10009, 9
tip_fixture.report_status, tip_fixture.active_run_id = "completed", ""
tip_fixture.report_post_count, tip_fixture.csv_content, tip_fixture.order_payments = 0, None, None
tip_payment_uuid = str(uuid4())
env.cr.commit()
with patch.dict(os.environ, {method.revolut_secret_reference: "synthetic-document-secret"}), patch(
        "odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
        side_effect=tip_fixture.provider_response) as tip_provider:
    prepared = native["pos.order"].revolut_prepare_payment(tip_sale.id, tip_sale.uuid, 0, [{
        "uuid": tip_payment_uuid, "payment_method_id": method.id, "amount": 100,
    }])
    # Each public POS request normally receives a fresh database transaction.
    # Preparation/start persist in owned cursors; release this shell snapshot.
    env.cr.commit()
    native.invalidate_all()
    started = method.revolut_start_payment(tip_session.id, tip_sale.uuid, tip_payment_uuid,
        100, company.currency_id.id, False, False, prepared["authorization_id"],
        prepared["cart_version"], prepared["tender_revision"])
    env.cr.commit()
    native.invalidate_all()
    with patch("odoo.addons.pos_revolut.models.payment_observation.observation_now",
               return_value=fields.Datetime.now() + timedelta(seconds=2)):
        verified = method.revolut_poll_payment(started["operation_id"], tip_sale.uuid, tip_payment_uuid)
    assert verified["state"] == "verified", verified
    assert sum(call.args[0] == "POST" and not call.args[1].endswith("/report-runs")
               for call in tip_provider.call_args_list) == 2
env.cr.commit()
native.invalidate_all()
tip_operation = native["pos.revolut.payment.operation"].browse(started["operation_id"])
with patch("odoo.addons.pos_revolut.models.pos_payment_method.requests.request",
           side_effect=AssertionError("Saved tip accounting must not contact Revolut")) as provider:
    assert (tip_sale.amount_total, tip_sale.amount_tax) == (100.09, 0.02), (
        tip_sale.read(["amount_total", "amount_tax"]),
        tip_sale.lines.read(["product_id", "price_unit", "price_subtotal", "price_subtotal_incl", "tax_ids"]),
    )
    native["pos.order"].sync_from_ui([{
        "uuid": tip_sale.uuid, "session_id": tip_session.id, "state": "paid",
        "date_order": fields.Datetime.to_string(fields.Datetime.now()), "sequence_number": 1,
        "name": "Authenticated conserved terminal tip sale", "amount_total": 100.09,
        "amount_paid": 100.09, "amount_tax": 0.02, "amount_return": 0,
        "to_invoice": False, "partner_id": partner.id, "lines": [], "payment_ids": [],
    }])
    tip_session.close_session_from_ui()
    assert tip_session.state == "closed"
    tip_sale.with_context(generate_pdf=False).action_pos_order_invoice()
    tip_invoice = tip_sale.account_move
    assert tip_invoice.amount_total == 100.09 and tip_invoice.amount_untaxed == 100.07
    assert tip_invoice.amount_tax == 0.02 and tip_invoice.state == "posted"
    assert tip_invoice.invoice_line_ids.filtered("revolut_terminal_tip_line_id").price_subtotal == 0.07
    orders |= tip_sale
    moves |= tip_invoice
    config.with_user(manager).open_ui()
    config.current_session_id.set_opening_control(0, "Fresh register after conserved tip sale")
    provider.assert_not_called()

native["ir.config_parameter"].set_param("pos_revolut_test.native_documents", json.dumps({
    "company": company.id, "orders": orders.ids, "invoices": moves.ids,
    "source": source.id, "refunds": refunds.ids, "session": session.id,
    "sources": (source | tip_operation).ids, "sessions": (session | tip_session).ids,
    "amounts": ["12.34", "3.09", "9.25", "100.09"], "tip_invoice": tip_invoice.id,
}))
env.cr.commit()
print("NATIVE_DOCUMENTS_SEED_OK: closed sessions, reopened register, later invoices, conserved credit notes and taxable tip")

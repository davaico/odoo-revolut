"""Seed native business history before the first pos_revolut installation.

Run through Odoo shell after installing point_of_sale and pos_restaurant.
This fixture uses no Revolut model, credentials, or provider traffic.
"""
import json
from uuid import uuid4

from odoo import Command


assert env["ir.module.module"].search([("name", "=", "pos_revolut")]).state != "installed"
company = env["res.company"].create({
    "name": "Existing native installation",
    "country_id": env.ref("base.us").id,
    "currency_id": env.ref("base.USD").id,
})
env["account.chart.template"].try_loading("generic_coa", company)
native = env(context={**env.context, "allowed_company_ids": company.ids})
native["stock.warehouse"].create({
    "name": "Existing native warehouse", "code": "V18N", "company_id": company.id,
})
manager = native["res.users"].create({
    "name": "Existing native register manager", "login": "native-install-manager",
    "company_id": company.id, "company_ids": [Command.set(company.ids)],
    "groups_id": [Command.set([
        env.ref("base.group_user").id, env.ref("point_of_sale.group_pos_manager").id,
    ])],
})
partner = native["res.partner"].create({
    "name": "Existing native customer", "ref": "V18-PRESERVE",
    "email": "native-install@example.invalid",
})
income = native["account.account"].search([
    ("company_ids", "in", company.ids), ("account_type", "=", "income"),
], limit=1)
product = native["product.product"].create({
    "name": "Existing native service", "default_code": "V18-PRESERVE",
    "type": "service", "available_in_pos": True, "list_price": 12.34,
    "taxes_id": [Command.clear()], "property_account_income_id": income.id,
})
cash_journal = native["account.journal"].search([("type", "=", "cash")], limit=1)
cash_journal.pos_payment_method_ids.unlink()
cash = native["pos.payment.method"].create({
    "name": "Existing native cash", "journal_id": cash_journal.id,
})
config = native["pos.config"].create({
    "name": "Existing native register",
    "payment_method_ids": [Command.set(cash.ids)],
})
config.with_user(manager).open_ui()
session = config.current_session_id
session.set_opening_control(0, "Native installation preservation fixture")
order = native["pos.order"].create({
    "uuid": str(uuid4()), "session_id": session.id,
    "partner_id": partner.id, "pos_reference": "Existing native sale",
    "amount_total": 12.34, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
    "lines": [Command.create({
        "uuid": str(uuid4()), "product_id": product.id, "qty": 1,
        "price_unit": 12.34, "price_subtotal": 12.34, "price_subtotal_incl": 12.34,
        "tax_ids": [Command.clear()],
    })],
})
order.add_payment({"pos_order_id": order.id, "payment_method_id": cash.id, "amount": 12.34})
order.action_pos_order_paid()
invoice = native["account.move"].create({
    "move_type": "out_invoice", "partner_id": partner.id,
    "invoice_date": "2026-10-20",
    "invoice_line_ids": [Command.create({
        "product_id": product.id, "quantity": 1, "price_unit": 5.67,
        "account_id": income.id, "tax_ids": [Command.clear()],
    })],
})
invoice.action_post()
assert order.state == "paid" and invoice.state == "posted"

history = [
    (company, ["name", "currency_id", "country_id"]),
    (manager, ["login", "company_id", "company_ids", "groups_id"]),
    (partner, ["name", "ref", "email"]),
    (product, ["name", "default_code", "list_price", "available_in_pos", "taxes_id"]),
    (config, ["name", "company_id", "payment_method_ids", "journal_id", "invoice_journal_id"]),
    (session, ["name", "config_id", "state", "user_id"]),
    (cash, ["name", "journal_id", "company_id", "payment_method_type"]),
    (order, ["name", "uuid", "state", "session_id", "partner_id", "amount_total", "amount_tax", "amount_paid", "amount_return"]),
    (order.lines, ["uuid", "product_id", "qty", "price_unit", "price_subtotal", "price_subtotal_incl"]),
    (order.payment_ids, ["pos_order_id", "payment_method_id", "amount"]),
    (invoice, ["name", "state", "move_type", "partner_id", "amount_total", "amount_residual"]),
    (invoice.line_ids, ["move_id", "account_id", "debit", "credit", "balance", "amount_currency"]),
]
snapshot = [{"model": records._name, "ids": records.ids, "fields": names,
             "values": records.read(names, load=False)} for records, names in history]
env["ir.config_parameter"].sudo().set_param(
    "pos_revolut_test.native_install", json.dumps(snapshot, default=str, sort_keys=True),
)
env.cr.commit()
print("Seeded existing native customer, product, register, paid sale and posted invoice")

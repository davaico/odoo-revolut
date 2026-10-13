"""Native public preparation used by pre-authority payment regression fixtures."""

import csv
import io
import json
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import requests

from odoo import Command, api

from ..models.financial_snapshot import normalize_snapshot


def native_products(env, config):
    """Configure real untaxed products for canonical pricing regression carts."""
    income = env["account.account"].search([
        ("company_ids", "in", env.company.ids), ("account_type", "=", "income"),
    ], limit=1) or env["account.account"].create({
        "name": "Revolut regression income", "code": "RVTEST",
        "account_type": "income", "company_ids": [Command.set(env.company.ids)],
    })
    product = env["product.product"].create({
        "name": "Revolut priced fixture", "available_in_pos": True, "list_price": 12.34,
        "taxes_id": [Command.clear()], "property_account_income_id": income.id,
    })
    config.tip_product_id = env["product.product"].create({
        "name": "Revolut terminal tip fixture", "taxes_id": [Command.clear()],
        "property_account_income_id": income.id,
    })
    return product


def prepare_fixture(method, session_id, order_uuid, line_uuid, amount, snapshot, *,
                    commit_draft=False, preset_time=False):
    """Persist a fixture draft, then obtain real server authority through RPC."""
    env = method.env
    env.invalidate_all()
    session = env["pos.session"].browse(session_id)
    normalized = normalize_snapshot(snapshot)
    order = env["pos.order"].search([("company_id", "=", session.company_id.id), ("uuid", "=", order_uuid)])
    if not order:
        total = sum(Decimal(line["price_unit"]) * Decimal(line["qty"])
                    * (1 - Decimal(line["discount"]) / 100) for line in normalized["lines"])
        order = env["pos.order"].create({
            "session_id": session_id, "uuid": order_uuid, "state": "draft",
            "pricelist_id": normalized["pricelist_id"],
            "fiscal_position_id": normalized["fiscal_position_id"],
            "amount_total": float(total), "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                "uuid": line["uuid"], "product_id": line["product_id"],
                "qty": float(line["qty"]), "price_unit": float(line["price_unit"]),
                "price_type": "manual", "discount": float(line["discount"]),
                "price_subtotal": float(Decimal(line["price_unit"]) * Decimal(line["qty"])),
                "price_subtotal_incl": float(Decimal(line["price_unit"]) * Decimal(line["qty"])),
                "tax_ids": [Command.set(line["tax_ids"])],
            }) for line in normalized["lines"]],
        })
        if snapshot.get("restaurant"):
            order.write({"preset_id": snapshot["restaurant"]["preset_id"],
                         "table_id": snapshot["restaurant"].get("table_id") or False})
    elif normalize_snapshot(order._revolut_order_values(), native_order=True) != normalized:
        desired = []
        by_uuid = {line.uuid: line for line in order.lines}
        for line in normalized["lines"]:
            values = {"product_id": line["product_id"], "qty": float(line["qty"]),
                      "price_unit": float(line["price_unit"]), "discount": float(line["discount"]),
                      "tax_ids": [Command.set(line["tax_ids"])]}
            if line["uuid"] in by_uuid:
                desired.append(Command.update(by_uuid[line["uuid"]].id, values))
            else:
                desired.append(Command.create({**values, "uuid": line["uuid"],
                                               "price_subtotal": 0, "price_subtotal_incl": 0}))
        for uuid, line in by_uuid.items():
            if uuid not in {item["uuid"] for item in normalized["lines"]}:
                desired.append(Command.delete(line.id))
        order.write({"lines": desired, "pricelist_id": normalized["pricelist_id"],
                     "fiscal_position_id": normalized["fiscal_position_id"]})
    # Pickup scheduling is native draft data, outside financial identity.
    if preset_time:
        order.write({"preset_time": preset_time})
        env.flush_all()
    current = order.revolut_authorization_id.sudo()
    plan = [{"uuid": slot["uuid"], "payment_method_id": slot["method_id"],
             "amount": float(Decimal(slot["minor"]) / (Decimal(10) ** order.currency_id.decimal_places))}
            for slot in current.tenders or [] if slot["uuid"] != line_uuid]
    plan.append({"uuid": line_uuid, "payment_method_id": method.id, "amount": amount})
    if commit_draft:
        env.cr.commit()
    result = env["pos.order"].revolut_prepare_payment(order.id, order_uuid, current.cart_version or 0, plan)
    if result["status"] == "review_required":
        result = env["pos.order"].revolut_prepare_payment(order.id, order_uuid, result["cart_version"], plan)
    return result


def authorized_start(method, session_id, order_uuid, line_uuid, amount, currency_id,
                     previous_operation_id=False, snapshot=False, *, commit_draft=False, preset_time=False):
    if not snapshot:
        return method.revolut_start_payment(session_id, order_uuid, line_uuid, amount, currency_id,
                                           previous_operation_id, snapshot)
    install_zero_reports(method.env, requests.request)
    authority = prepare_fixture(method, session_id, order_uuid, line_uuid, amount, snapshot,
                                commit_draft=commit_draft, preset_time=preset_time)
    return method.revolut_start_payment(session_id, order_uuid, line_uuid, amount, currency_id,
                                       previous_operation_id, False, authority["authorization_id"],
                                       authority["cart_version"], authority["tender_revision"])


def zero_report_response(env, verb, url):
    """Extra provider responses for explicit zero-tip evidence; never a bypass."""
    operations = env["pos.revolut.payment.operation"].sudo()
    if "/api/report-runs" in url:
        operation = operations.search([("authorization_id", "!=", False), ("captured_amount_minor", ">", 0)], order="id desc", limit=1)
        if not operation:
            return None
        run_id = operation.report_run_id or str(uuid4())
        response = Mock(status_code=200)
        if url.endswith("/file"):
            output = io.StringIO()
            columns = ["payment_id", "order_id", "currency", "location_id", "type", "state",
                       "amount", "tip_amount", "surcharge_amount", "refunded_amount", "created_date", "captured_date"]
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            stamp = operation.captured_payment_created_at.isoformat() + "Z[UTC]"
            writer.writerow({"payment_id": operation.revolut_payment_id, "order_id": operation.revolut_order_id,
                             "currency": operation.currency_code, "location_id": operation.location_id,
                             "type": "PAYMENT", "state": "CAPTURED",
                             "amount": str(Decimal(operation.captured_amount_minor) / (Decimal(10) ** operation.currency_id.decimal_places)),
                             "tip_amount": "0.00", "surcharge_amount": "0.00", "refunded_amount": "0.00",
                             "created_date": stamp, "captured_date": stamp})
            content = output.getvalue().encode()
        else:
            content = json.dumps({"report_run_id": run_id, "status": "completed"}).encode()
        response.iter_content.return_value = [content]
        return response
    if verb == "GET" and "/api/orders/" in url:
        order_id = url.rsplit("/", 1)[-1]
        operation = operations.search([("revolut_order_id", "=", order_id), ("authorization_id", "!=", False),
                                       ("captured_amount_minor", ">", 0)], limit=1)
        if operation:
            verified_refunds = env["pos.revolut.refund.operation"].sudo().search([
                ("original_operation_id", "=", operation.id), ("state", "=", "verified"),
            ])
            response = Mock(status_code=200)
            response.json.return_value = {"id": order_id, "currency": operation.currency_code,
                                         "location_id": operation.location_id,
                                         "type": "payment", "state": "completed",
                                         "amount": operation.captured_amount_minor,
                                         "refunded_amount": sum(verified_refunds.mapped("amount_minor")),
                                         "payments": [{"id": operation.revolut_payment_id,
                                                                        "state": "captured",
                                                                        "amount": operation.captured_amount_minor}]}
            response.iter_content.return_value = [json.dumps(response.json.return_value).encode()]
            return response
    return None


def financial_posts(request):
    return [call for call in request.call_args_list if call.args[0] == "POST" and "/api/report-runs" not in call.args[1]]


def install_zero_reports(env, request):
    if not isinstance(request, Mock):
        raise AssertionError("Provider fixtures must run behind mocked HTTP")
    previous = request.__dict__.get("_zero_report_router")
    if previous is not None and request.side_effect is previous:
        return
    original = request.side_effect

    def route(verb, url, **kwargs):
        with env.registry.cursor() as cursor:
            fresh = api.Environment(cursor, env.uid, dict(env.context))
            result = zero_report_response(fresh, verb, url)
            if result is not None:
                return result
        if callable(original):
            result = original(verb, url, **kwargs)
        elif isinstance(original, BaseException):
            raise original
        elif original is None:
            result = request.return_value
        else:
            result = next(original)
            if isinstance(result, BaseException):
                raise result
        if isinstance(result, Mock):
            payload = result.json.return_value
            if isinstance(payload, dict):
                with env.registry.cursor() as cursor:
                    fresh = api.Environment(cursor, env.uid, dict(env.context))
                    operation = fresh["pos.revolut.payment.operation"].sudo().search([
                        ("revolut_payment_intent_id", "=", payload.get("id") or ""),
                        ("authorization_id", "!=", False),
                    ], limit=1)
                    if operation:
                        for key, value in {"amount": operation.amount_minor, "currency": operation.currency_code,
                                           "terminal_id": operation.terminal_id}.items():
                            payload.setdefault(key, value)
                if payload.get("state") in {"captured", "completed"} and "amount" in payload and "currency" in payload:
                    payload.setdefault("created_at", "2026-10-01T08:00:00Z")
        return result

    request.side_effect = route
    request.__dict__["_zero_report_router"] = route

"""Hosted, mocked acceptance of interrupted native cron workers.

This standalone fixture is not imported by the addon. Run only on a disposable
staging database, with the Merchant HTTP guard enabled and both addon jobs
inactive. The native-worker launcher controls process lifetime separately.
"""

import csv
import io
import json
import os
import runpy
import time
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from uuid import uuid4

from odoo import Command, api, fields
from odoo.addons.pos_revolut.models.payment_observation import OBSERVATION_CADENCE_SECONDS
from odoo.addons.pos_revolut.models.terminal_tip import REPORT_COLUMNS


CHECKPOINT = "pos_revolut.cron_restart_fixture"
REFERENCE = "ODOO_REVOLUT_SECRET_TEST_TERMINAL"
FAKE_KEY = "synthetic-native-cron-key"
JOBS = {
    "payment": "pos_revolut.ir_cron_reconcile_payments",
    "refund": "pos_revolut.ir_cron_reconcile_refunds",
}


def response(payload):
    result = Mock(status_code=200)
    result.json.return_value = payload
    result.iter_content.return_value = [
        payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    ]
    return result


def guard(env):
    assert os.environ.get("ODOO_STAGE") == "staging"
    assert os.environ.get("ODOO_REVOLUT_BLOCK_MERCHANT_HTTP") == "1"
    assert REFERENCE not in os.environ
    assert env["ir.config_parameter"].sudo().get_param("database.is_neutralized")
    assert all(not env.ref(xml_id).active for xml_id in JOBS.values())


def save(env, data):
    env["ir.config_parameter"].sudo().set_param(CHECKPOINT, json.dumps(data, default=str))
    env.cr.commit()


def identity(records, names):
    return json.loads(json.dumps(records.read(names, load=False), default=str))


def seed(env, root):
    """Keep existing users and shared product taxes intact during native setup."""
    guard(env)
    before = {
        "res.groups": identity(env["res.groups"].search([]), ["implied_ids"]),
        "res.users": identity(env["res.users"].with_context(active_test=False).search([]), ["groups_id"]),
        "product.template": identity(env["product.template"].with_context(active_test=False).search([]),
                                     ["taxes_id", "supplier_taxes_id"]),
    }
    try:
        return _seed(env, root)
    finally:
        # Native company/chart/product setup can enable product-variant groups
        # and append a new company's taxes to shared products. These are test
        # setup side effects, not part of payment/recovery acceptance.
        env.cr.rollback()
        with env.registry.cursor() as cursor:
            cleanup = api.Environment(cursor, env.uid, dict(env.context), su=env.su)
            for model, rows in before.items():
                for row in rows:
                    record = cleanup[model].browse(row["id"]).exists()
                    assert record, "Existing setup record disappeared"
                    values = {name: [Command.set(ids)] for name, ids in row.items()
                              if name != "id" and set(record[name].ids) != set(ids)}
                    if values:
                        record.write(values)
            cursor.commit()
        env.invalidate_all()


def _seed(env, root):
    """Reuse committed restart carts; retain one pending payment and one refund."""
    guard(env)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    previous = env["ir.config_parameter"].sudo().get_param(CHECKPOINT)
    fixtures = Path(__file__).parent
    if previous:
        data = json.loads(previous)
        if data["stage"] == "ready":
            (root / "fixture.json").write_text(json.dumps(data))
            return data
        assert data["stage"] == "carts_seeded", "Inspect incomplete seed; never dispatch a replacement"
        env = env(context={**env.context, "allowed_company_ids": [data["company_id"]]})
        authority = env["pos.revolut.merchant.credential"].browse(data["credential_id"])
        history = data["history"]
        originals = env["pos.revolut.payment.operation"].browse([item["operation_id"] for item in history])
        assert all(item.captured_amount_minor and item.report_run_id for item in originals)
        assert authority._resolve_secret() == FAKE_KEY
    else:
        assert not env["pos.revolut.merchant.credential"].search([
            ("secret_reference", "=", REFERENCE),
        ]), "Existing restart fixture requires inspection, not reseeding"
        assert not env["pos.revolut.payment.operation"].search_count([
            ("state", "in", ["pending", "unresolved", "dispatching_intent"]),
        ])
        assert not env["pos.revolut.refund.operation"].search_count([
            ("state", "in", ["dispatching", "pending", "unresolved"]),
        ])
        company = env["res.company"].create({
            "name": "Synthetic native cron restart", "country_id": env.ref("base.us").id,
            "currency_id": env.ref("base.USD").id,
        })
        env["account.chart.template"].try_loading("generic_coa", company)
        env = env(context={**env.context, "allowed_company_ids": company.ids})
        env["stock.warehouse"].create({
            "name": "Synthetic cron warehouse", "code": "T80C", "company_id": company.id,
        })
        authority = env["pos.revolut.merchant.credential"].create({
            "company_id": company.id, "environment": "sandbox", "source": "database",
            "secret_reference": REFERENCE, "secret_key": FAKE_KEY,
        })
        runpy.run_path(str(fixtures / "restart_seed.py"), init_globals={"env": env})
        history = json.loads(env["ir.config_parameter"].sudo().get_param("pos_revolut.restart_fixture"))
        data = {"stage": "carts_seeded", "company_id": company.id,
                "credential_id": authority.id, "history": history}
        save(env, data)
        runpy.run_path(str(fixtures / "restart_wait.py"), init_globals={"env": env})
    # The unchanged final fixture settles the zero-tip source only. The other
    # cart retains its pending captured payment/report for worker interruption.
    env["ir.config_parameter"].sudo().set_param("pos_revolut.restart_fixture", json.dumps(history[:1]))
    env.cr.commit()
    try:
        source = env["pos.revolut.payment.operation"].browse(history[0]["operation_id"])
        if source.state != "verified":
            time.sleep(OBSERVATION_CADENCE_SECONDS + 0.1)
            runpy.run_path(str(fixtures / "restart_verify.py"), init_globals={"env": env})
    finally:
        env.cr.rollback()
        env["ir.config_parameter"].sudo().set_param("pos_revolut.restart_fixture", json.dumps(history))
        env.cr.commit()
    source = env["pos.revolut.payment.operation"].browse(history[0]["operation_id"])
    source_order = source.pos_order_id
    assert source.state == "verified"
    if source_order.state == "draft":
        source_order.action_pos_order_paid()
    assert source_order.state == "paid"
    order_uuid, line_uuid, refund_provider = [str(uuid4()) for _ in range(3)]
    payload = {
        "uuid": order_uuid, "name": "Synthetic native cron partial return",
        "session_id": source.pos_session_id.id, "user_id": env.uid,
        "state": "draft", "sequence_number": 2, "amount_total": -6.17,
        "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
        "date_order": fields.Datetime.to_string(fields.Datetime.now()),
        "pricelist_id": source_order.pricelist_id.id, "fiscal_position_id": False,
        "to_invoice": False,
        "lines": [Command.create({
            "uuid": str(uuid4()), "product_id": source_order.lines.product_id.id,
            "qty": -0.5, "price_unit": 12.34, "discount": 0,
            "price_subtotal": -6.17, "price_subtotal_incl": -6.17,
            "tax_ids": [Command.set([])], "pack_lot_ids": [],
            "refunded_orderline_id": source_order.lines.id,
        })],
        "payment_ids": [Command.create({
            "uuid": line_uuid, "payment_method_id": source.payment_method_id.id,
            "amount": -6.17, "payment_status": "waiting", "transaction_id": False,
            "name": fields.Datetime.to_string(fields.Datetime.now()),
        })],
    }
    payload = data.get("refund_payload", payload)
    refund_provider = data.get("refund_provider", refund_provider)
    order_uuid = payload["uuid"]
    line_uuid = payload["payment_ids"][0][2]["uuid"]
    draft = env["pos.order"].search([("uuid", "=", order_uuid)])
    if not draft:
        env["pos.order"].sync_from_ui([payload])
    draft = env["pos.order"].search([("uuid", "=", order_uuid)])
    assert draft.state == "draft" and draft.amount_total == -6.17
    payload["id"] = draft.id
    for name in ("lines", "payment_ids"):
        by_uuid = {record.uuid: record.id for record in draft[name]}
        payload[name] = [[Command.UPDATE, by_uuid[item[2]["uuid"]], item[2]] for item in payload[name]]
    data.update(refund_payload=payload, refund_provider=refund_provider)
    save(env, data)
    had_refund = env["pos.revolut.refund.operation"].search_count([
        ("order_uuid", "=", order_uuid), ("payment_line_uuid", "=", line_uuid),
    ])
    with patch("requests.request", side_effect=[
        response({"id": source.revolut_order_id, "state": "completed", "amount": 1234,
                  "currency": "USD", "refunded_amount": 0}),
        response({"id": refund_provider, "type": "refund", "state": "pending",
                  "related_order_id": source.revolut_order_id, "amount": 617, "currency": "USD"}),
    ]) as provider:
        started = source.payment_method_id.revolut_start_refund(
            source.pos_session_id.id, order_uuid, line_uuid, -6.17, source.currency_id.id,
            payload, original_operation_id=source.id, base_amount_minor=617, tip_amount_minor=0,
        )
        assert started["state"] == "pending", started
        if had_refund:
            provider.assert_not_called()
        else:
            assert [call.args[0] for call in provider.call_args_list] == ["GET", "POST"]
        assert all(call.kwargs["headers"]["Authorization"] == "Bearer " + FAKE_KEY
                   for call in provider.call_args_list)
    env.cr.rollback()
    env.invalidate_all()
    payment = env["pos.revolut.payment.operation"].browse(history[1]["operation_id"])
    refund = env["pos.revolut.refund.operation"].browse(started["operation_id"])
    assert payment.state == refund.state == "pending"
    assert payment.credential_id == refund.original_operation_id.credential_id == authority
    overdue = fields.Datetime.now() - timedelta(hours=2)
    payment.next_reconcile_at = overdue
    refund.next_reconcile_at = overdue
    payment_fields = ["company_id", "credential_id", "authorization_id", "order_uuid", "payment_line_uuid",
                      "revolut_order_id", "revolut_payment_intent_id", "revolut_payment_id",
                      "report_run_id", "attempt_number", "previous_operation_id", "financial_snapshot"]
    refund_fields = ["original_operation_id", "order_uuid", "payment_line_uuid", "revolut_order_id",
                     "idempotency_key", "amount_minor", "base_amount_minor", "tip_amount_minor",
                     "financial_snapshot", "return_allocation"]
    data.update({
        "stage": "ready", "payment_id": payment.id, "refund_id": refund.id,
        "payment_terminal": payment.terminal_id, "payment_location": payment.location_id,
        "refund_provider": refund_provider, "refund_payload": payload,
        "payment_fields": payment_fields, "refund_fields": refund_fields,
        "payment_identity": identity(payment, payment_fields),
        "refund_identity": identity(refund, refund_fields),
        "dispatch_ids": env["pos.revolut.payment.dispatch"].search([
            ("operation_id", "in", [item["operation_id"] for item in history]),
        ]).ids,
        "dispatch_identity": identity(env["pos.revolut.payment.dispatch"].search([
            ("operation_id", "in", [item["operation_id"] for item in history]),
        ]), ["operation_id", "action", "claimed_at", "completed_at", "outcome", "provider_reference"]),
    })
    save(env, data)
    (root / "fixture.json").write_text(json.dumps(data, default=str))
    print("T80_CRON_SEED_OK: two original payments, one partial refund, Database key", flush=True)
    return data


def install_provider_mock(root, phase):
    """Return a process-local fail-closed mock; no request reaches the network."""
    root = Path(root)
    data = json.loads((root / "fixture.json").read_text())
    payment = data["history"][1]
    source = data["history"][0]

    def route(verb, url, **kwargs):
        parsed = urlsplit(url)
        assert verb == "GET", "Restart recovery attempted a provider dispatch"
        assert parsed.scheme == "https" and parsed.hostname == "sandbox-merchant.revolut.com"
        assert not parsed.query
        assert kwargs["headers"]["Authorization"] == "Bearer " + FAKE_KEY
        path = parsed.path
        target = (path == "/api/payment-intents/" + payment["provider_intent"]
                  if phase.startswith("payment") else path == "/api/orders/" + data["refund_provider"])
        allowed = {
            "/api/payment-intents/" + payment["provider_intent"],
            "/api/payments/" + payment["provider_payment"],
            "/api/report-runs/" + payment["report_id"],
            "/api/report-runs/" + payment["report_id"] + "/file",
            "/api/orders/" + payment["provider_order"],
            "/api/orders/" + data["refund_provider"], "/api/orders",
        }
        assert path in allowed, "Unexpected provider read in restart fixture"
        with (root / "requests.jsonl").open("a") as log:
            log.write(json.dumps({"phase": phase, "pid": os.getpid(), "verb": verb,
                                  "path": path, "credential_matched": True}) + "\n")
        marker = root / (phase + "-provider-ready.json")
        if target and not marker.exists():
            marker.write_text(json.dumps({"pid": os.getpid(), "credential_matched": True}))
        if target and phase.endswith("-kill"):
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                time.sleep(0.05)
            raise AssertionError("Supervisor did not interrupt the native worker")
        if path.startswith("/api/payment-intents/"):
            payload = {"id": payment["provider_intent"], "order_id": payment["provider_order"],
                       "state": "completed", "payment_id": payment["provider_payment"],
                       "amount": 1234, "currency": "USD", "terminal_id": None}
            # Exact terminal identity is read from the committed fixture, not
            # inferred from the currently configured payment method.
            payload["terminal_id"] = data["payment_terminal"]
        elif path.startswith("/api/payments/"):
            payload = {"id": payment["provider_payment"], "order_id": payment["provider_order"],
                       "state": "captured", "amount": 1534, "currency": "USD",
                       "created_at": payment["created_at"]}
        elif path.endswith("/file"):
            output = io.StringIO(newline="")
            writer = csv.DictWriter(output, fieldnames=REPORT_COLUMNS)
            writer.writeheader()
            writer.writerow({
                "payment_id": payment["provider_payment"], "type": "PAYMENT",
                "order_id": payment["provider_order"], "state": "COMPLETED",
                "amount": "15.34", "currency": "USD", "surcharge_amount": "",
                "tip_amount": "3.00", "refunded_amount": "0.00",
                "created_date": payment["created_at"], "captured_date": payment["captured_at"],
                "location_id": data["payment_location"],
            })
            return response(output.getvalue().encode())
        elif path.startswith("/api/report-runs/"):
            payload = {"report_run_id": payment["report_id"], "status": "completed"}
        elif path == "/api/orders/" + data["refund_provider"]:
            payload = {"id": data["refund_provider"], "type": "refund", "state": "completed",
                       "related_order_id": source["provider_order"], "amount": 617, "currency": "USD"}
        elif path == "/api/orders":
            payload = {"orders": []}
        else:
            payload = {"id": payment["provider_order"], "currency": "USD",
                       "location_id": data["payment_location"],
                       "payments": [{"id": payment["provider_payment"], "state": "captured", "amount": 1534}]}
        return response(payload)

    return patch("requests.request", side_effect=route)


def run_cron(env, phase, root):
    """Run real inactive cron action code; preserve the killed payment's lease."""
    guard(env)
    root = Path(root)
    data = json.loads((root / "fixture.json").read_text())
    kind = phase.split("-", 1)[0]
    model = "pos.revolut.payment.operation" if kind == "payment" else "pos.revolut.refund.operation"
    operation = env[model].browse(data[kind + "_id"])
    assert operation.state == "pending"
    job = env.ref(JOBS[kind])
    assert job.user_id == env.ref("base.user_root") and not job.active
    authority = env["pos.revolut.merchant.credential"].browse(data["credential_id"])
    assert authority.source == "database" and authority._resolve_secret() == FAKE_KEY
    if phase == "payment-recover":
        assert operation.observation_token and operation.observation_expires_at
        expiry = operation.observation_expires_at
        before = (root / "requests.jsonl").read_text()
        assert expiry > fields.Datetime.now(), "Expected the killed worker's live lease"
        job.method_direct_trigger()
        env.cr.rollback()
        env.invalidate_all()
        assert operation.state == "pending" and operation.observation_expires_at == expiry
        assert (root / "requests.jsonl").read_text() == before
        (root / "payment-lease-preserved.json").write_text(json.dumps({
            "pid": os.getpid(), "expiry": str(expiry), "no_http": True,
        }))
        print("T80_NATIVE_CRON_LEASE_PRESERVED: waiting for original expiry", flush=True)
        while fields.Datetime.now() <= expiry:
            time.sleep(min(1, max(0.05, (expiry - fields.Datetime.now()).total_seconds())))
        env.cr.rollback()
        env.invalidate_all()
    job.method_direct_trigger()
    env.cr.rollback()
    env.invalidate_all()
    assert operation.state == "verified", "Native worker did not verify original attempt"
    (root / (phase + "-cron-ok.json")).write_text(json.dumps({"pid": os.getpid(), "verified": True}))


def verify(env, root):
    """Fresh observer: exact identities, one projection and zero-HTTP replays."""
    guard(env)
    root = Path(root)
    data = json.loads((root / "fixture.json").read_text())
    env = env(context={**env.context, "allowed_company_ids": [data["company_id"]]})
    payment = env["pos.revolut.payment.operation"].browse(data["payment_id"])
    refund = env["pos.revolut.refund.operation"].browse(data["refund_id"])
    assert payment.state == refund.state == "verified"
    assert identity(payment, data["payment_fields"]) == data["payment_identity"]
    assert identity(refund, data["refund_fields"]) == data["refund_identity"]
    assert env["pos.revolut.payment.operation"].search_count([("company_id", "=", data["company_id"])]) == 2
    assert env["pos.revolut.refund.operation"].search_count([("company_id", "=", data["company_id"])]) == 1
    assert env["pos.revolut.payment.dispatch"].search([
        ("operation_id", "in", [item["operation_id"] for item in data["history"]]),
    ]).ids == data["dispatch_ids"]
    assert identity(env["pos.revolut.payment.dispatch"].browse(data["dispatch_ids"]),
                    ["operation_id", "action", "claimed_at", "completed_at", "outcome", "provider_reference"]) == data["dispatch_identity"]
    order = payment.pos_order_id
    authority = payment.authorization_id
    assert order.state == "draft" and order.amount_total == 15.34
    assert payment.terminal_tip_minor == 300 and payment.terminal_tip_evidence
    assert len(order.lines.filtered(lambda line: line.product_id == authority.tip_product_id)) == 1
    assert len(order.payment_ids) == 1 and order.payment_ids.amount == 15.34
    revision = authority.projection_revision
    assert refund.amount_minor == refund.base_amount_minor == 617 and refund.tip_amount_minor == 0
    fixture = data["history"][1]
    with patch("requests.request", side_effect=AssertionError("Replay attempted HTTP")) as provider:
        for _ in range(2):
            restarted = payment.payment_method_id.revolut_start_payment(
                fixture["session_id"], fixture["order_uuid"], fixture["line_uuid"],
                12.34, payment.currency_id.id, False, False,
                authority.id, authority.cart_version, authority.tender_revision,
            )
            polled = payment.payment_method_id.revolut_poll_payment(
                payment.id, payment.order_uuid, payment.payment_line_uuid,
            )
            assert restarted["operation_id"] == polled["operation_id"] == payment.id
            assert restarted["state"] == polled["state"] == "verified"
            restarted_refund = refund.payment_method_id.revolut_start_refund(
                refund.pos_session_id.id, refund.order_uuid, refund.payment_line_uuid,
                -6.17, refund.currency_id.id, data["refund_payload"],
                original_operation_id=refund.original_operation_id.id,
                base_amount_minor=617, tip_amount_minor=0,
            )
            polled_refund = refund.payment_method_id.revolut_poll_refund(
                refund.id, refund.order_uuid, refund.payment_line_uuid,
            )
            assert restarted_refund["operation_id"] == polled_refund["operation_id"] == refund.id
            assert restarted_refund["state"] == polled_refund["state"] == "verified"
        provider.assert_not_called()
    assert authority.projection_revision == revision
    requests = [json.loads(line) for line in (root / "requests.jsonl").read_text().splitlines()]
    assert requests and all(item["verb"] == "GET" and item["credential_matched"] for item in requests)
    assert (root / "payment-lease-preserved.json").exists()
    env.cr.rollback()
    print("T80_NATIVE_CRON_RECOVERY_OK: same payment/refund, exact tips, zero POST/replay HTTP", flush=True)

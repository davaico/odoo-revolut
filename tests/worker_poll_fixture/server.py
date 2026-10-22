"""Test-only launcher: bounded mocked provider holds inherited by HTTP workers."""

import fcntl
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests


ROOT = Path("/var/lib/odoo/status-poll-probe")
fixture = json.loads((ROOT / "fixture.json").read_text())
intents = {item["provider_intent"]: item for item in fixture}
real_request = requests.request


def mocked_request(method, url, **kwargs):
    parsed = urlsplit(url)
    if parsed.hostname not in {"merchant.revolut.com", "sandbox-merchant.revolut.com"}:
        return real_request(method, url, **kwargs)
    intent_id = parsed.path.removeprefix("/api/payment-intents/")
    if method != "GET" or intent_id not in intents or parsed.query:
        raise AssertionError("Unexpected Merchant request in worker probe")
    with (ROOT / "arrivals.jsonl").open("a+") as log:
        fcntl.flock(log, fcntl.LOCK_EX)
        log.seek(0)
        sequence = sum(1 for _ in log) + 1
        log.write(json.dumps({"sequence": sequence, "pid": os.getpid(),
                              "cashier": intents[intent_id]["cashier"],
                              "arrived_monotonic": time.monotonic()}) + "\n")
        log.flush()
    deadline = time.monotonic() + 25
    while not (ROOT / f"release-{sequence}").exists():
        if time.monotonic() >= deadline:
            raise AssertionError("Bounded worker provider hold expired")
        time.sleep(0.02)
    item = intents[intent_id]
    result = requests.Response()
    result.status_code = 200
    result._content = json.dumps({
        "id": intent_id, "order_id": item["provider_order"], "state": "pending",
        "amount": 1234, "currency": item["currency"], "terminal_id": item["terminal"],
    }).encode()
    result.headers["Content-Type"] = "application/json"
    return result


assert os.environ.get("ODOO_REVOLUT_BLOCK_MERCHANT_HTTP") == "1"
requests.request = mocked_request
import odoo.cli
from odoo.tools import config

sys.argv = ["odoo", *sys.argv[1:]]
config.parse_config(sys.argv[1:], setup_logging=False)
assert config["workers"] == 2 and config["max_cron_threads"] == 1
(ROOT / "runtime.json").write_text(json.dumps({
    "http_workers": config["workers"], "max_cron_threads": config["max_cron_threads"],
    "master_pid": os.getpid(), "database": config["db_name"],
}))
odoo.cli.main()

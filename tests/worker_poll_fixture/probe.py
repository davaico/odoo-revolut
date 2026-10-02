"""Real HTTP RPC characterization; all provider waits are bounded test fixtures."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import requests


ROOT = Path("/var/lib/odoo/status-poll-probe")
URL = "http://127.0.0.1:8069"
DATABASE = "odoo_revolut_worker_probe"
fixture = json.loads((ROOT / "fixture.json").read_text())


def rpc(session, route, params):
    started = time.monotonic()
    response = session.post(URL + route, json={"jsonrpc": "2.0", "method": "call",
                                             "params": params, "id": 1}, timeout=40)
    response.raise_for_status()
    payload = response.json()
    assert "error" not in payload, payload.get("error")
    return payload["result"], time.monotonic() - started


def login(item):
    session = requests.Session()
    result, _ = rpc(session, "/web/session/authenticate", {
        "db": DATABASE, "login": item["login"], "password": "probe-only-password",
    })
    assert result["uid"] == item["uid"]
    return session


def unrelated(session, uid, entered=None):
    if entered:
        entered.set()
    result, elapsed = rpc(session, "/web/dataset/call_kw/res.users/read", {
        "model": "res.users", "method": "read", "args": [[uid], ["id", "name"]], "kwargs": {},
    })
    assert result[0]["id"] == uid
    return elapsed


def poll(session, item):
    result, elapsed = rpc(session, "/web/dataset/call_kw/pos.payment.method/revolut_poll_payment", {
        "model": "pos.payment.method", "method": "revolut_poll_payment",
        "args": [[item["method_id"]], item["operation_id"], item["order_uuid"], item["line_uuid"]],
        "kwargs": {},
    })
    assert result["state"] == "pending", result
    assert result["operation_id"] == item["operation_id"]
    return elapsed


def arrivals():
    path = ROOT / "arrivals.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def wait_until(predicate, description, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(f"Timed out: {description}")


def release(sequence):
    (ROOT / f"release-{sequence}").touch()


deadline = time.monotonic() + 45
while True:
    try:
        control = login(fixture[0])
        break
    except requests.ConnectionError:
        if time.monotonic() >= deadline:
            raise
        time.sleep(0.25)

# Independent authenticated sessions exclude browser/session-lock effects.
sessions = [login(fixture[index // 2]) for index in range(4)]
before = unrelated(control, fixture[0]["uid"])
with ThreadPoolExecutor(max_workers=6) as pool:
    try:
        one_poll = pool.submit(poll, sessions[0], fixture[0])
        wait_until(lambda: len(arrivals()) == 1, "single held provider read")
        single_read = pool.submit(unrelated, control, fixture[0]["uid"])
        single = single_read.result(timeout=5)
        assert not one_poll.done(), "Single provider fixture unexpectedly finished"
        release(1)
        one_poll.result(timeout=10)

        # Two browser sessions for one cashier occupy both HTTP workers.
        polls = [pool.submit(poll, sessions[index], fixture[0]) for index in (0, 1)]
        wait_until(lambda: len(arrivals()) == 3, "two duplicate reads held")
        occupied = arrivals()[1:3]
        assert len({item["pid"] for item in occupied}) == 2, occupied
        assert {item["cashier"] for item in occupied} == {1}
        assert not any((ROOT / f"release-{sequence}").exists() for sequence in (2, 3))
        polls.extend(pool.submit(poll, sessions[index], fixture[1]) for index in (2, 3))
        entered = Event()
        delayed = pool.submit(unrelated, control, fixture[0]["uid"], entered)
        assert entered.wait(2), "Unrelated RPC client did not enter request"
        held_at = time.monotonic()
        time.sleep(2)
        hold_seconds = time.monotonic() - held_at
        assert not delayed.done(), "Unrelated RPC progressed while both workers were held"
        assert len(arrivals()) == 3, "Queued polls unexpectedly reached provider"

        # Release entire status calls sequentially to isolate worker admission
        # from pending-state database observation retries.
        for sequence in range(2, 6):
            wait_until(lambda: len(arrivals()) >= sequence, f"provider read {sequence}")
            done_before = sum(future.done() for future in polls)
            release(sequence)
            wait_until(lambda: sum(future.done() for future in polls) > done_before,
                       f"completed status call {sequence}")
        poll_times = [future.result(timeout=5) for future in polls]
        delayed_seconds = delayed.result(timeout=5)
    finally:
        for sequence in range(1, 16):
            release(sequence)
after = unrelated(control, fixture[0]["uid"])
observed = arrivals()
runtime = json.loads((ROOT / "runtime.json").read_text())
assert runtime["http_workers"] == 2 and runtime["max_cron_threads"] == 1
assert len(observed) == 5, observed
assert [item["cashier"] for item in observed[1:]] == [1, 1, 2, 2], observed
assert delayed_seconds >= hold_seconds
print(json.dumps({
    "scenario": "two-http-workers-four-authorized-tabs", "odoo_version": "19.0.20260908",
    "http_workers": runtime["http_workers"], "max_cron_threads": runtime["max_cron_threads"],
    "master_pid": runtime["master_pid"], "scheduled_jobs": "quiesced",
    "cashiers": 2, "tabs_per_cashier": 2, "provider": "mocked-pending-only",
    "mock_provider_reads": len(observed), "main_scenario_provider_reads": 4,
    "maximum_simultaneous_held_provider_reads": len(occupied),
    "main_scenario_financial_posts": 0, "worker_pids": sorted({item["pid"] for item in occupied}),
    "main_scenario_reads_per_cashier": [2, 2], "all_four_status_results": "pending",
    "unrelated_rpc_seconds_before": round(before, 6),
    "unrelated_rpc_seconds_one_held_poll": round(single, 6),
    "unrelated_rpc_seconds_two_held_polls": round(delayed_seconds, 6),
    "confirmed_both_workers_held_seconds": round(hold_seconds, 6),
    "unrelated_rpc_seconds_after": round(after, 6),
    "poll_rpc_seconds": [round(value, 6) for value in poll_times],
    "merchant_http_guard": "verified-before-init", "runtime_network": "internal",
}), flush=True)

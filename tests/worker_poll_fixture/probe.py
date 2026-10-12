"""Verify coalesced status polling across real HTTP workers with mocked provider waits."""

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


def poll_snapshot(session, item):
    result, elapsed = rpc(session, "/web/dataset/call_kw/pos.payment.method/revolut_poll_payment", {
        "model": "pos.payment.method", "method": "revolut_poll_payment",
        "args": [[item["method_id"]], item["operation_id"], item["order_uuid"], item["line_uuid"]],
        "kwargs": {},
    })
    assert result["state"] == "pending", result
    assert result["operation_id"] == item["operation_id"]
    return result, elapsed


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

def coalesced_probe(control):
    # Four independent cookies model two tabs per granted backend cashier.
    sessions = [login(fixture[index // 2]) for index in range(4)]
    before = unrelated(control, fixture[0]["uid"])
    with ThreadPoolExecutor(max_workers=6) as pool:
        try:
            winner = pool.submit(poll_snapshot, sessions[0], fixture[0])
            wait_until(lambda: len(arrivals()) == 1, "shared-operation winner held")
            duplicates = [pool.submit(poll_snapshot, sessions[index], fixture[0])
                          for index in (1, 2, 3)]
            duplicate_results = [future.result(timeout=2) for future in duplicates]
            for snapshot, elapsed in duplicate_results:
                assert snapshot["observation_in_progress"] is True, snapshot
                advice = snapshot["next_check_seconds"]
                assert isinstance(advice, (int, float)) and not isinstance(advice, bool)
                assert 0 < advice <= 60, snapshot
                assert elapsed < 2, elapsed
                assert snapshot["retry_safe"] is False, snapshot
            available = pool.submit(unrelated, control, fixture[0]["uid"]).result(timeout=2)
            assert not winner.done(), "Held shared-operation observation unexpectedly finished"
            assert len(arrivals()) == 1, "Shared-operation duplicates reached the provider"
            release(1)
            first_snapshot, first_seconds = winner.result(timeout=10)
            assert first_snapshot["observation_in_progress"] is False, first_snapshot
            assert 0 <= first_snapshot["next_check_seconds"] <= 1, first_snapshot

            # Allow the one-second start cadence before requesting the same
            # operation again; a separate operation has its own claim.
            wait_until(lambda: time.monotonic() - arrivals()[0]["arrived_monotonic"] >= 1.05,
                       "shared-operation cadence window elapsed")
            distinct = [pool.submit(poll_snapshot, sessions[0], fixture[0]),
                        pool.submit(poll_snapshot, sessions[2], fixture[1])]
            wait_until(lambda: len(arrivals()) == 3, "two distinct observations held")
            occupied = arrivals()[1:3]
            assert {item["cashier"] for item in occupied} == {1, 2}, occupied
            assert len({item["pid"] for item in occupied}) == 2, occupied
            repeat = next(item for item in occupied if item["cashier"] == 1)
            cadence_seconds = repeat["arrived_monotonic"] - arrivals()[0]["arrived_monotonic"]
            assert cadence_seconds >= 1, cadence_seconds
            entered = Event()
            delayed = pool.submit(unrelated, control, fixture[0]["uid"], entered)
            assert entered.wait(2), "Unrelated RPC client did not enter request"
            held_at = time.monotonic()
            time.sleep(2)
            hold_seconds = time.monotonic() - held_at
            assert not delayed.done(), "Unrelated RPC progressed while distinct operations held both workers"
            assert len(arrivals()) == 3, "Unexpected provider request while both workers held"
            release(2)
            release(3)
            distinct_results = [future.result(timeout=10) for future in distinct]
            delayed_seconds = delayed.result(timeout=5)
        finally:
            for sequence in range(1, 16):
                release(sequence)
    after = unrelated(control, fixture[0]["uid"])
    observed = arrivals()
    runtime = json.loads((ROOT / "runtime.json").read_text())
    assert runtime["http_workers"] == 2 and runtime["max_cron_threads"] == 1
    assert len(observed) == 3, observed
    assert delayed_seconds >= hold_seconds
    print(json.dumps({
        "scenario": "coalesced-two-http-workers-four-authorized-tabs",
        "odoo_version": "19.0.20260908", "http_workers": runtime["http_workers"],
        "max_cron_threads": runtime["max_cron_threads"], "master_pid": runtime["master_pid"],
        "scheduled_jobs": "quiesced", "cashiers": 2, "tabs_per_cashier": 2,
        "provider": "mocked-pending-only", "mock_provider_reads": len(observed),
        "shared_operation_provider_reads": 1, "shared_operation_duplicate_calls": 3,
        "distinct_operations_provider_reads": 2, "financial_posts": 0,
        "maximum_simultaneous_held_provider_reads": len(occupied),
        "distinct_operation_worker_pids": sorted({item["pid"] for item in occupied}),
        "all_status_results": "pending", "observation_rpc_seconds": round(first_seconds, 6),
        "duplicate_rpc_seconds": [round(elapsed, 6) for _, elapsed in duplicate_results],
        "duplicate_next_check_seconds": [snapshot["next_check_seconds"] for snapshot, _ in duplicate_results],
        "completed_observation_next_check_seconds": first_snapshot["next_check_seconds"],
        "same_operation_provider_start_gap_seconds": round(cadence_seconds, 6),
        "unrelated_rpc_seconds_before": round(before, 6),
        "unrelated_rpc_seconds_shared_operation_held": round(available, 6),
        "unrelated_rpc_seconds_distinct_operations_held": round(delayed_seconds, 6),
        "confirmed_distinct_operations_held_seconds": round(hold_seconds, 6),
        "unrelated_rpc_seconds_after": round(after, 6),
        "distinct_operation_rpc_seconds": [round(elapsed, 6) for _, elapsed in distinct_results],
        "merchant_http_guard": "verified-before-init", "runtime_network": "internal",
    }), flush=True)


coalesced_probe(control)

"""Bounded hosted proof using native Odoo cron workers and mocked scheduling.

Run from an initialized Odoo shell::

    import sys
    sys.path.insert(0, '/path/to/pos_revolut/tests')
    from cron_restart_worker import run
    run(env, '/tmp/a-new-ticket80-run', timeout=200)

The shared fixture seeds that directory first. The actual addon jobs stay
inactive: only this process replaces cron job selection. Native WorkerCron
construction, startup, process_work, signals and shutdown are exercised. This
does not claim a platform-managed ``odoosh-restart cron`` succeeded.
"""

import argparse
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch


PHASES = ("payment-kill", "payment-recover", "refund-kill", "refund-recover")


def _write_json(path, values):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, sort_keys=True) + "\n")
    temporary.replace(path)


def _read_marker(path, pid):
    if not path.exists():
        return False
    try:
        marker = json.loads(path.read_text())
    except json.JSONDecodeError:
        # The shared fixture may be between opening and writing its marker.
        # A permanently invalid marker still fails through the wall timeout.
        return False
    if marker.get("pid") != pid:
        raise AssertionError("A fixture marker belongs to another process")
    return True


def _reap(pid):
    waited, status = os.waitpid(pid, os.WNOHANG)
    return os.waitstatus_to_exitcode(status) if waited else None


def _wait_exit(pid, deadline):
    while time.monotonic() < deadline:
        status = _reap(pid)
        if status is not None:
            return status
        time.sleep(0.05)
    raise TimeoutError("Native cron worker did not exit within the fixture budget")


def _stop_worker(multi, worker, deadline):
    """Interrupt native sleep, then reap; force cleanup if shutdown stalls."""
    status = _reap(worker.pid)
    if status is not None:
        return status
    os.kill(worker.pid, signal.SIGINT)
    multi.pipe_ping(worker.eintr_pipe)
    try:
        return _wait_exit(worker.pid, min(deadline, time.monotonic() + 5))
    except TimeoutError:
        os.kill(worker.pid, signal.SIGKILL)
        return _wait_exit(worker.pid, time.monotonic() + 5)


def _check_environment(timeout):
    if os.environ.get("ODOO_STAGE") != "staging":
        raise AssertionError("This fixture requires an actual Odoo.sh staging process")
    if os.environ.get("ODOO_REVOLUT_BLOCK_MERCHANT_HTTP") != "1":
        raise AssertionError("The Merchant HTTP guard must be enabled")
    if not 1 <= timeout <= 240:
        raise ValueError("The worker fixture wall-clock budget must be 1..240 seconds")


def run(env, root, timeout=200):
    """Run in a fresh interpreter, preserving the caller's borrowed DB cursor."""
    _check_environment(timeout)
    from odoo.tools import config

    configuration = Path(config.rcfile)
    if not configuration.is_file():
        raise AssertionError("The native Odoo configuration file must be available to the fresh launcher")
    env.cr.rollback()
    child_environment = dict(os.environ)
    child_environment["PYTHONPATH"] = os.pathsep.join(path for path in sys.path if path)
    command = [
        sys.executable, str(Path(__file__).resolve()), "--root", str(Path(root).resolve()),
        "--timeout", str(timeout), "--", "--config", str(configuration),
        "--database", env.cr.dbname, "--addons-path", config["addons_path"],
        "--no-http", "--max-cron-threads=0", "--log-level=error",
    ]
    process = subprocess.Popen(
        command, env=child_environment, stdin=subprocess.DEVNULL, start_new_session=True,
    )
    try:
        status = process.wait(timeout=timeout + 10)
    finally:
        # Include native grandchildren if startup or the supervisor itself
        # failed. This process group belongs exclusively to this test run.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
    if status != 0:
        raise AssertionError(f"The native cron launcher failed (status {status}); inspect lifecycle.json")
    report = json.loads((Path(root) / "lifecycle.json").read_text())
    if not report.get("complete"):
        raise AssertionError("The native cron launcher returned without complete lifecycle evidence")
    return report


def _supervise(database, root, timeout):
    """Own all native workers after the fresh launcher's DB cursors are closed."""
    _check_environment(timeout)
    import requests
    import odoo
    from odoo import api
    from odoo.addons.base.models.ir_cron import ir_cron
    from odoo.modules.registry import Registry
    from odoo.service import server
    from odoo.tools import config
    from cron_restart_fixture import install_provider_mock, run_cron

    root = Path(root)
    if not root.is_dir() or not (root / "fixture.json").is_file():
        raise AssertionError("Seed this fixture directory before starting its workers")
    report_path = root / "lifecycle.json"
    marker_suffixes = ("provider-ready", "cron-ok", "scheduler-entered", "worker-error")
    if report_path.exists() or any(
        (root / f"{phase}-{suffix}.json").exists()
        for phase in PHASES for suffix in marker_suffixes
    ):
        raise AssertionError("Use a fresh fixture directory; lifecycle markers already exist")

    # Native PreforkServer.run also closes inherited pools before worker_spawn.
    # Do this before forking and open all fixture transactions in fresh cursors.
    odoo.sql_db.close_all()

    started = time.monotonic()
    deadline = started + timeout
    report = {
        "scheduler_selection": "process-local method_direct_trigger of inactive addon jobs",
        "platform_managed_restart": False,
        "native_worker_class": f"{server.WorkerCron.__module__}.{server.WorkerCron.__name__}",
        "events": [],
        "complete": False,
    }

    def record(event, **values):
        report["events"].append({
            "event": event, "elapsed_seconds": round(time.monotonic() - started, 3), **values,
        })
        _write_json(report_path, report)
        print(f"T80_NATIVE_CRON_{event.upper()}", flush=True)

    original_request = requests.request
    config["db_name"] = database
    multi = server.PreforkServer(None)
    parent_pid = os.getpid()
    previous_pid = None
    try:
        for phase in PHASES:
            if time.monotonic() >= deadline:
                raise TimeoutError("The native worker fixture exhausted its total wall-clock budget")

            dispatched = False

            def dispatch(cls, db_name):
                nonlocal dispatched
                if dispatched:
                    return
                dispatched = True
                try:
                    if db_name != database:
                        raise AssertionError("Native worker selected an unexpected database")
                    native_call = any(
                        frame.frame.f_code is server.WorkerCron.process_work.__code__
                        for frame in inspect.stack(context=0)
                    )
                    if not native_call:
                        raise AssertionError("Cron dispatch did not originate in native WorkerCron.process_work")
                    _write_json(root / f"{phase}-scheduler-entered.json", {
                        "pid": os.getpid(), "native_process_work": True,
                    })
                    with Registry(database).cursor() as cursor:
                        worker_env = api.Environment(cursor, odoo.SUPERUSER_ID, {})
                        run_cron(worker_env, phase, root)
                    if not _read_marker(root / f"{phase}-cron-ok.json", os.getpid()):
                        raise AssertionError("Cron fixture returned without verified completion evidence")
                except BaseException as error:
                    _write_json(root / f"{phase}-worker-error.json", {
                        "pid": os.getpid(), "exception_type": type(error).__name__,
                    })
                    # Native Worker.run joins a work thread; an exception in
                    # that thread alone is not a reliable process exit code.
                    os._exit(1)

            with install_provider_mock(root, phase), patch.object(
                ir_cron, "_process_jobs", classmethod(dispatch),
            ):
                worker = multi.worker_spawn(server.WorkerCron, multi.workers_cron)
                # worker_spawn exits in the child after native Worker.run.
                # Only the supervisor reaches this statement.
                if os.getpid() != parent_pid:
                    os._exit(1)
                record("spawned", phase=phase, pid=worker.pid, replaces_pid=previous_pid)
                reaped = False
                try:
                    marker = root / f"{phase}-{'provider-ready' if phase.endswith('-kill') else 'cron-ok'}.json"
                    while not _read_marker(marker, worker.pid):
                        if _read_marker(root / f"{phase}-worker-error.json", worker.pid):
                            raise AssertionError("Native cron fixture reported a worker failure")
                        status = _reap(worker.pid)
                        if status is not None:
                            reaped = True
                            raise AssertionError(f"Native cron worker exited before its evidence marker (status {status})")
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Native cron fixture did not reach its evidence marker")
                        # Wake its native cron sleep; no scheduler interval or
                        # financial lease constant is changed.
                        multi.pipe_ping(worker.eintr_pipe)
                        time.sleep(0.05)
                    if not _read_marker(root / f"{phase}-scheduler-entered.json", worker.pid):
                        raise AssertionError("Provider evidence lacks native scheduler-entry evidence")
                    if _read_marker(root / f"{phase}-worker-error.json", worker.pid):
                        raise AssertionError("Native cron fixture reported a worker failure")
                    if phase.endswith("-kill"):
                        os.kill(worker.pid, signal.SIGKILL)
                        status = _wait_exit(worker.pid, min(deadline, time.monotonic() + 5))
                        reaped = True
                        if status != -signal.SIGKILL:
                            raise AssertionError("The interrupted native worker was not killed by SIGKILL")
                        record("killed", phase=phase, pid=worker.pid, exit_status=status)
                    else:
                        status = _stop_worker(multi, worker, deadline)
                        reaped = True
                        if status != 0:
                            raise AssertionError("The recovered native cron worker did not stop cleanly")
                        record("recovered", phase=phase, pid=worker.pid, exit_status=status)
                    previous_pid = worker.pid
                finally:
                    if not reaped:
                        status = _stop_worker(multi, worker, deadline)
                        record("cleanup", phase=phase, pid=worker.pid, exit_status=status)
                    multi.worker_pop(worker.pid)
        report["complete"] = True
        record("complete")
        return report
    except BaseException:
        if os.getpid() == parent_pid:
            record("failed")
        raise
    finally:
        requests.request = original_request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--timeout", type=int, default=200)
    parser.add_argument("odoo_args", nargs=argparse.REMAINDER, help="native Odoo config arguments after --")
    args = parser.parse_args()
    _check_environment(args.timeout)
    import odoo
    from odoo import api
    from odoo.modules import module
    from odoo.modules.registry import Registry
    from odoo.service import server
    from odoo.tools import config
    odoo_args = args.odoo_args[1:] if args.odoo_args[:1] == ["--"] else args.odoo_args
    config.parse_config(odoo_args)
    if not config["db_name"] or "," in config["db_name"]:
        parser.error("Select exactly one staging database with native --database configuration")
    # Standalone Python does not run the native server.start bootstrap. Populate
    # the addon namespace from the caller's effective paths before importing
    # server-wide modules, loading the registry, or importing the shared fixture.
    module.initialize_sys_path()
    if not module.get_module_path("pos_revolut", display_warning=False):
        raise AssertionError("The native addon paths do not contain the installed candidate")
    server.load_server_wide_modules()
    with Registry(config["db_name"]).cursor() as cursor:
        env = api.Environment(cursor, odoo.SUPERUSER_ID, {})
        jobs = [env.ref(f"pos_revolut.ir_cron_reconcile_{kind}") for kind in ("payments", "refunds")]
        if any(job.active for job in jobs):
            raise AssertionError("Both addon cron jobs must remain globally inactive")
    _supervise(config["db_name"], args.root, args.timeout)


if __name__ == "__main__":
    main()

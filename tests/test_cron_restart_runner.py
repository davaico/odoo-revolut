"""Fail-closed configuration and real child-process cleanup for the probe."""

import importlib.util
import json
import os
from pathlib import Path
import select
import signal
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "pos_revolut/tests/cron_restart_worker.py"
SPEC = importlib.util.spec_from_file_location("cron_restart_runner", SOURCE)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class CronRestartRunnerTests(unittest.TestCase):
    def test_refuses_other_stages_and_missing_http_guard(self):
        for stage in ("production", "dev", "", "support"):
            with self.subTest(stage=stage), patch.dict(os.environ, {
                "ODOO_STAGE": stage, "ODOO_REVOLUT_BLOCK_MERCHANT_HTTP": "1",
            }):
                with self.assertRaises(AssertionError):
                    runner._check_environment(200)
        with patch.dict(os.environ, {"ODOO_STAGE": "staging", "ODOO_REVOLUT_BLOCK_MERCHANT_HTTP": "0"}):
            with self.assertRaises(AssertionError):
                runner._check_environment(200)

    def test_rejects_unbounded_runtime(self):
        with patch.dict(os.environ, {"ODOO_STAGE": "staging", "ODOO_REVOLUT_BLOCK_MERCHANT_HTTP": "1"}):
            for budget in (0, 241):
                with self.subTest(budget=budget), self.assertRaises(ValueError):
                    runner._check_environment(budget)

    def test_marker_cannot_authorize_killing_another_process(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "marker.json"
            marker.write_text(json.dumps({"pid": os.getpid() + 1}))
            with self.assertRaises(AssertionError):
                runner._read_marker(marker, os.getpid())

    def test_partial_marker_is_not_completion(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "marker.json"
            marker.write_text('{"pid":')
            self.assertFalse(runner._read_marker(marker, os.getpid()))

    @unittest.skipUnless(hasattr(os, "fork"), "POSIX worker lifecycle")
    def test_unresponsive_child_is_killed_and_reaped_before_deadline(self):
        reader, writer = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(reader)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            os.write(writer, b"ready")
            os.close(writer)
            while True:
                signal.pause()
        os.close(writer)
        reaped = False
        try:
            self.assertTrue(select.select([reader], [], [], 2)[0], "Child did not become ready")
            self.assertEqual(os.read(reader, 5), b"ready")
            worker = SimpleNamespace(pid=pid, eintr_pipe=None)
            supervisor = SimpleNamespace(pipe_ping=lambda pipe: None)
            started = time.monotonic()
            status = runner._stop_worker(supervisor, worker, started + 0.15)
            reaped = True
            self.assertEqual(status, -signal.SIGKILL)
            self.assertLess(time.monotonic() - started, 2)
            with self.assertRaises(ChildProcessError):
                os.waitpid(pid, os.WNOHANG)
        finally:
            os.close(reader)
            if not reaped:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass


if __name__ == "__main__":
    unittest.main()

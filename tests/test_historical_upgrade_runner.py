"""Exercise historical runner commands without starting Docker or contacting Revolut."""
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "cart-authority": (
        "295ae79ad6404a0e0dc2c9798421731b03cb715d", "upgrade",
        "odoo-revolut-cart-upgrade", "odoo_revolut_cart_upgrade",
    ),
    "credential-authority": (
        "2f4328cef1fdef51a02883faad45d9c24f5eb99c", "credential_upgrade",
        "odoo-revolut-credential-upgrade", "odoo_revolut_credential_upgrade",
    ),
    "evidence-retirement": (
        "412e1b21e64431970d9bab7a29177d7b9cd2c624", "evidence_retirement",
        "odoo-revolut-evidence-retirement", "odoo_revolut_evidence_retirement",
    ),
    "external-native": (
        "4301fa653a46bb53ec4eeca2ec4383c11b544569", "external_native_upgrade",
        "odoo-revolut-external-native-upgrade", "odoo_revolut_external_native_upgrade",
    ),
    "receipt-retirement": (
        "2de85210ff99757624e058396b19dec9d7784e82", "receipt_retirement",
        "odoo-revolut-receipt-retirement", "odoo_revolut_receipt_retirement",
    ),
    "register-access": (
        "71bce6238c299b35fa2648dd16f76633493ae13c", "register_upgrade",
        "odoo-revolut-register-upgrade", "odoo_revolut_register_upgrade",
    ),
    "return-rounding": (
        "a07b43704fc8982883d9b1e641101f7e2bcb831e", "return_rounding_upgrade",
        "odoo-revolut-return-rounding-upgrade", "odoo_revolut_return_rounding_upgrade",
    ),
}

# This executable adapter records the CLI seam and mount contents, then fails or
# waits at a selected phase. Git archive, Bash, traps and filesystem are real.
FAKE_DOCKER = r'''
import hashlib
import json
import os
import sys
import time
from pathlib import Path

args = sys.argv[1:]
log = Path(os.environ["FAKE_DOCKER_LOG"])
previous = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
if args[0] == "rm":
    phase = "reports-cleanup"
    project = args[-1].removesuffix("-native-reports")
else:
    project = args[args.index("--project-name") + 1]
    if "down" in args:
        phase = "cleanup" if any(row["phase"] == "reset" and row["project"] == project for row in previous) else "reset"
    elif "build" in args:
        phase = "build"
    elif "dpkg-query" in args:
        phase = "version"
    elif "python3" in args:
        phase = "guard"
    elif "up" in args:
        phase = "database"
    elif "--init" in args:
        phase = "install"
    elif "shell" in args:
        phase = "verify" if any(row["phase"] == "seed" and row["project"] == project for row in previous) else "seed"
    elif "--update" in args:
        phase = "upgrade"
    elif "--detach" in args:
        phase = "reports"
    else:
        raise AssertionError(args)
mount = Path(os.environ["ODOO_REVOLUT_ADDONS_DIR"])
row = {"args": args, "project": project, "phase": phase, "mount": str(mount),
       "addons": sorted(path.name for path in mount.iterdir() if (path / "__manifest__.py").is_file()),
       "manifest": hashlib.sha256((mount / "pos_revolut/__manifest__.py").read_bytes()).hexdigest()}
if (mount / "pos_revolut_restaurant/__manifest__.py").exists():
    row["legacy_manifest"] = hashlib.sha256((mount / "pos_revolut_restaurant/__manifest__.py").read_bytes()).hexdigest()
if phase in {"seed", "verify"}:
    row["stdin"] = hashlib.sha256(sys.stdin.buffer.read()).hexdigest()
with log.open("a") as stream:
    stream.write(json.dumps(row) + "\n")
if phase == os.environ.get("FAKE_PAUSE_PHASE"):
    Path(os.environ["FAKE_PAUSE_MARKER"]).touch()
    while not Path(os.environ["FAKE_PAUSE_RELEASE"]).exists():
        time.sleep(0.01)
if phase in os.environ.get("FAKE_FAIL_PHASES", "").split(","):
    sys.exit(37)
if phase == os.environ.get("FAKE_PAUSE_PHASE"):
    Path(os.environ["FAKE_PHASE_COMPLETE_MARKER"]).touch()
if phase == "version":
    print(os.environ.get("FAKE_ODOO_VERSION", "19.0.20260908"), end="")
'''


def digest(content):
    return hashlib.sha256(content).hexdigest()


class TestHistoricalUpgradeRunner(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="revolut-runner-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        docker = self.bin / "docker"
        docker.write_text(f"#!{sys.executable}\n" + FAKE_DOCKER)
        docker.chmod(0o755)
        self.log = self.root / "docker.jsonl"
        self.env = dict(os.environ)
        self.env.pop("ODOO_REVOLUT_TEST_PROJECT", None)
        self.env.update(PATH=f"{self.bin}:{self.env['PATH']}",
                        TMPDIR=str(self.root), FAKE_DOCKER_LOG=str(self.log))

    def run_scenario(self, scenario="cart-authority", **environment):
        return subprocess.run(
            [str(REPOSITORY_ROOT / "scripts" / f"test-{scenario}-upgrade")],
            env={**self.env, **environment}, capture_output=True, text=True, timeout=30,
            cwd=self.root,
        )

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def assert_temporaries_removed(self, calls):
        for row in calls:
            if row["mount"] != str(REPOSITORY_ROOT):
                self.assertFalse(Path(row["mount"]).exists(), row)

    def test_all_historical_scenarios_preserve_revisions_fixtures_and_processes(self):
        for scenario, (revision, prefix, project, database) in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                self.log.unlink(missing_ok=True)
                result = self.run_scenario(scenario)
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = self.calls()
                phases = [row["phase"] for row in calls]
                expected = ["reset", "build", "version", "guard", "database", "install", "seed", "upgrade"]
                if scenario == "receipt-retirement":
                    expected += ["reports", "verify", "reports-cleanup", "cleanup"]
                else:
                    expected += ["verify", "cleanup"]
                self.assertEqual(phases, expected)
                self.assertTrue(all(row["project"] == project for row in calls))
                old_manifest = subprocess.check_output(
                    ["git", "-C", str(REPOSITORY_ROOT), "show", f"{revision}:addons/pos_revolut/__manifest__.py"]
                )
                by_phase = {row["phase"]: row for row in calls}
                self.assertEqual(by_phase["install"]["manifest"], digest(old_manifest))
                self.assertEqual(by_phase["seed"]["mount"], by_phase["install"]["mount"])
                for phase, suffix in (("seed", "seed"), ("verify", "verify")):
                    fixture = REPOSITORY_ROOT / "pos_revolut/tests" / f"{prefix}_{suffix}.py"
                    self.assertEqual(by_phase[phase]["stdin"], digest(fixture.read_bytes()))
                    self.assertIn("--no-http", by_phase[phase]["args"])
                    self.assertIn("--shell-interface", by_phase[phase]["args"])
                current = str(REPOSITORY_ROOT)
                self.assertEqual(by_phase["verify"]["mount"], current)
                for phase in ("install", "seed", "upgrade", "verify"):
                    args = by_phase[phase]["args"]
                    self.assertEqual(args[args.index("--database") + 1], database)
                    self.assertIn("--rm", args)
                if "legacy_manifest" in by_phase["install"]:
                    self.assertEqual(by_phase["upgrade"]["addons"], ["pos_revolut", "pos_revolut_restaurant"])
                    legacy = subprocess.check_output([
                        "git", "-C", str(REPOSITORY_ROOT), "show",
                        f"{revision}:addons/pos_revolut_restaurant/__manifest__.py",
                    ])
                    self.assertEqual(by_phase["upgrade"]["legacy_manifest"], digest(legacy))
                else:
                    self.assertEqual(by_phase["upgrade"]["mount"], current)
                if scenario == "receipt-retirement":
                    self.assertEqual(by_phase["reports"]["mount"], current)
                    self.assertIn("--use-aliases", by_phase["reports"]["args"])
                    self.assertIn(f"{project}-native-reports", by_phase["reports-cleanup"]["args"])
                self.assertEqual(by_phase["upgrade"]["manifest"], digest(
                    (REPOSITORY_ROOT / "pos_revolut/__manifest__.py").read_bytes()
                ))
                self.assert_temporaries_removed(calls)
                self.assertTrue(result.stdout.strip())

    def test_each_phase_failure_stops_execution_and_cleans_owned_resources(self):
        for phase in ("reset", "build", "version", "guard", "database", "install", "seed", "upgrade", "reports", "verify"):
            with self.subTest(phase=phase):
                self.log.unlink(missing_ok=True)
                result = self.run_scenario("receipt-retirement", FAKE_FAIL_PHASES=phase)
                self.assertEqual(result.returncode, 37, result.stderr)
                calls = self.calls()
                phases = [row["phase"] for row in calls]
                following = phases[phases.index(phase) + 1:]
                self.assertEqual(following, ["reports-cleanup", "cleanup"] if phase in {"reports", "verify"} else ["cleanup"])
                self.assertIn("failed (exit 37)", result.stderr)
                self.assertNotIn("Receipt retirement upgrade preserves", result.stdout)
                self.assert_temporaries_removed(calls)

    def test_overlay_copy_failure_cleans_both_temporary_trees(self):
        marker = self.root / "overlay-path"
        copy = self.bin / "cp"
        copy.write_text(f"#!{sys.executable}\n" +
                        "import os, sys\nfrom pathlib import Path\n" +
                        "Path(os.environ['FAKE_OVERLAY_PATH']).write_text(sys.argv[-1])\n" +
                        "sys.exit(42)\n")
        copy.chmod(0o755)
        result = self.run_scenario("receipt-retirement", FAKE_OVERLAY_PATH=str(marker))
        self.assertEqual(result.returncode, 42, result.stderr)
        self.assertIn("prepare legacy Restaurant addon overlay failed", result.stderr)
        self.assertEqual([row["phase"] for row in self.calls()][-2:], ["seed", "cleanup"])
        self.assertFalse(Path(marker.read_text()).exists())
        self.assert_temporaries_removed(self.calls())

    def test_cleanup_failure_is_reported_and_preserves_original_failure(self):
        for failure, expected in (("cleanup", 1), ("reports-cleanup", 1), ("verify,cleanup,reports-cleanup", 37)):
            with self.subTest(failure=failure):
                self.log.unlink(missing_ok=True)
                result = self.run_scenario("receipt-retirement", FAKE_FAIL_PHASES=failure)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertIn("Failed to", result.stderr)
                self.assertNotIn("Receipt retirement upgrade preserves", result.stdout)
                self.assert_temporaries_removed(self.calls())

    def test_wrong_runtime_stops_before_guard_and_install(self):
        result = self.run_scenario(FAKE_ODOO_VERSION="19.0.other")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Expected Odoo 19.0.20260908", result.stderr)
        self.assertEqual([row["phase"] for row in self.calls()], ["reset", "build", "version", "cleanup"])
        self.assert_temporaries_removed(self.calls())

    def test_archive_failure_removes_temporary_tree_without_touching_docker(self):
        git = self.bin / "git"
        git.write_text("#!/usr/bin/env bash\nexit 41\n")
        git.chmod(0o755)
        result = self.run_scenario()
        self.assertEqual(result.returncode, 41, result.stderr)
        self.assertIn("archive historical addons failed", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["bin"])

    def test_invalid_interface_is_rejected_without_resources(self):
        for args in ([], ["unknown"], ["cart-authority", "extra"]):
            with self.subTest(args=args):
                result = subprocess.run(
                    [str(REPOSITORY_ROOT / "scripts/test-historical-upgrade"), *args],
                    env=self.env, capture_output=True, text=True, timeout=10,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(self.calls(), [])
        result = self.run_scenario(ODOO_REVOLUT_TEST_PROJECT="../invalid")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def start_paused(self, scenario, phase, project, **environment):
        marker = self.root / "paused"
        marker.unlink(missing_ok=True)
        release = self.root / "resume"
        release.unlink(missing_ok=True)
        completed = self.root / "completed"
        completed.unlink(missing_ok=True)
        process = subprocess.Popen(
            [str(REPOSITORY_ROOT / "scripts" / f"test-{scenario}-upgrade")],
            env={**self.env, **environment, "FAKE_PAUSE_PHASE": phase, "FAKE_PAUSE_MARKER": str(marker),
                 "FAKE_PAUSE_RELEASE": str(release),
                 "FAKE_PHASE_COMPLETE_MARKER": str(completed),
                 "ODOO_REVOLUT_TEST_PROJECT": project},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
        )
        self.addCleanup(self.stop_process, process, release)
        deadline = time.monotonic() + 10
        while not marker.exists():
            if process.poll() is not None or time.monotonic() >= deadline:
                self.fail("Runner did not reach the paused phase")
            time.sleep(0.01)
        return process

    @staticmethod
    def stop_process(process, release=None):
        if release is not None:
            release.touch()
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        process.communicate(timeout=10)

    def test_same_project_is_locked_while_different_project_is_isolated(self):
        project = f"upgrade-runner-test-{self.root.name}"
        process = self.start_paused("cart-authority", "build", project)
        before = self.calls()
        collision = self.run_scenario(ODOO_REVOLUT_TEST_PROJECT=project)
        self.assertEqual(collision.returncode, 2, collision.stderr)
        self.assertIn("already in use", collision.stderr)
        self.assertEqual(self.calls(), before)
        independent = self.run_scenario(ODOO_REVOLUT_TEST_PROJECT=f"{project}-other")
        self.assertEqual(independent.returncode, 0, independent.stderr)
        self.assertTrue(Path(before[0]["mount"]).exists())
        self.stop_process(process)
        self.assertEqual(process.returncode, 143)
        self.assert_temporaries_removed(self.calls())
        # The persistent lock inode must be reusable once its holder exits.
        result = self.run_scenario(ODOO_REVOLUT_TEST_PROJECT=project)
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_interrupted_run_cleaned_up(self, process, interrupted, *, reports_started,
                                         during_cleanup=False, expected_exit=None):
        stdout, stderr = process.communicate(timeout=5)
        if expected_exit is None:
            expected_exit = 130 if interrupted == signal.SIGINT else 143
        self.assertEqual(process.returncode, expected_exit, stderr)
        diagnostic = "interrupted during cleanup" if during_cleanup else "interrupted during"
        self.assertIn(diagnostic, stderr)
        self.assertNotIn("Receipt retirement upgrade preserves", stdout)
        expected_phases = ["reports-cleanup", "cleanup"] if reports_started else ["cleanup"]
        self.assertEqual([row["phase"] for row in self.calls()][-len(expected_phases):], expected_phases)
        self.assert_temporaries_removed(self.calls())
        if during_cleanup:
            self.assertTrue((self.root / "completed").exists(), "Docker teardown was interrupted")
            self.assertNotIn("Failed to", stderr)

    def test_runner_termination_during_cleanup_finishes_and_releases_project(self):
        for phase in ("reports-cleanup", "cleanup"):
            for interrupted in (signal.SIGINT, signal.SIGTERM):
                with self.subTest(phase=phase, interrupted=interrupted):
                    self.log.unlink(missing_ok=True)
                    project = f"upgrade-runner-test-{self.root.name}"
                    process = self.start_paused("receipt-retirement", phase, project)
                    try:
                        process.send_signal(interrupted)
                    finally:
                        (self.root / "resume").touch()
                    self.assert_interrupted_run_cleaned_up(process, interrupted,
                                                          reports_started=True, during_cleanup=True)
                    result = self.run_scenario("receipt-retirement", ODOO_REVOLUT_TEST_PROJECT=project)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_process_group_termination_during_cleanup_finishes_teardown(self):
        for phase in ("reports-cleanup", "cleanup"):
            for interrupted in (signal.SIGINT, signal.SIGTERM):
                with self.subTest(phase=phase, interrupted=interrupted):
                    self.log.unlink(missing_ok=True)
                    project = f"upgrade-runner-test-{self.root.name}"
                    process = self.start_paused("receipt-retirement", phase, project)
                    try:
                        os.killpg(process.pid, interrupted)
                    finally:
                        (self.root / "resume").touch()
                    self.assert_interrupted_run_cleaned_up(process, interrupted,
                                                          reports_started=True, during_cleanup=True)
                    result = self.run_scenario("receipt-retirement", ODOO_REVOLUT_TEST_PROJECT=project)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_process_group_signal_during_temporary_removal_finishes_cleanup(self):
        real_rm = shutil.which("rm")
        remove = self.bin / "rm"
        remove.write_text(f"#!{sys.executable}\n" +
                          "import os, subprocess, sys, time\nfrom pathlib import Path\n" +
                          "paused = os.environ.get('FAKE_PAUSE_PHASE') == 'delete' and Path(sys.argv[-1]).parent == Path(os.environ['TMPDIR'])\n" +
                          "if paused:\n" +
                          "    Path(os.environ['FAKE_PAUSE_MARKER']).touch()\n" +
                          "    while not Path(os.environ['FAKE_PAUSE_RELEASE']).exists():\n" +
                          "        time.sleep(0.01)\n" +
                          f"status = subprocess.call([{real_rm!r}, *sys.argv[1:]])\n" +
                          "if paused and status == 0:\n" +
                          "    Path(os.environ['FAKE_PHASE_COMPLETE_MARKER']).touch()\n" +
                          "sys.exit(status)\n")
        remove.chmod(0o755)
        project = f"upgrade-runner-test-{self.root.name}"
        process = self.start_paused("receipt-retirement", "delete", project)
        try:
            os.killpg(process.pid, signal.SIGTERM)
        finally:
            (self.root / "resume").touch()
        self.assert_interrupted_run_cleaned_up(process, signal.SIGTERM,
                                              reports_started=True, during_cleanup=True)
        result = self.run_scenario("receipt-retirement", ODOO_REVOLUT_TEST_PROJECT=project)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cleanup_signal_preserves_prior_phase_failure(self):
        project = f"upgrade-runner-test-{self.root.name}"
        process = self.start_paused("receipt-retirement", "cleanup", project, FAKE_FAIL_PHASES="verify")
        try:
            process.send_signal(signal.SIGTERM)
        finally:
            (self.root / "resume").touch()
        self.assert_interrupted_run_cleaned_up(process, signal.SIGTERM, reports_started=True,
                                              during_cleanup=True, expected_exit=37)
        result = self.run_scenario("receipt-retirement", ODOO_REVOLUT_TEST_PROJECT=project)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runner_pid_termination_forwards_to_docker_and_cleans_resources(self):
        for phase, interrupted in (("version", signal.SIGTERM), ("verify", signal.SIGTERM), ("verify", signal.SIGINT)):
            with self.subTest(phase=phase, interrupted=interrupted):
                self.log.unlink(missing_ok=True)
                process = self.start_paused("receipt-retirement", phase,
                                            f"upgrade-runner-test-{self.root.name}-{phase}-{interrupted}")
                process.send_signal(interrupted)
                self.assert_interrupted_run_cleaned_up(process, interrupted, reports_started=phase == "verify")

    def test_interruptions_remove_overlay_and_report_process(self):
        for phase, interrupted in (("upgrade", signal.SIGTERM), ("verify", signal.SIGTERM), ("verify", signal.SIGINT)):
            with self.subTest(phase=phase, interrupted=interrupted):
                self.log.unlink(missing_ok=True)
                process = self.start_paused("receipt-retirement", phase, f"upgrade-runner-test-{self.root.name}")
                os.killpg(process.pid, interrupted)
                self.assert_interrupted_run_cleaned_up(process, interrupted, reports_started=phase == "verify")


if __name__ == "__main__":
    unittest.main()

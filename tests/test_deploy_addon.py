import importlib.machinery
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = REPOSITORY_ROOT / "scripts" / name
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if callable(response):
            return response(command, kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=response, stderr="")


class TestLocalDeploymentCli(unittest.TestCase):
    def test_git_status_failure_is_reported_without_remote_commands(self):
        deploy_addon = load_script("deploy-addon")
        failure = subprocess.CalledProcessError(
            128, ["git", "status"], stderr="not a git repository"
        )
        runner = FakeRunner([failure])
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as repository:
            exit_code = deploy_addon.main(
                [
                    "deploy",
                    "--repository",
                    repository,
                    "--revision",
                    "a" * 40,
                    "--ssh-target",
                    "root@staging.example.test",
                    "--database",
                    "revolut_staging",
                    "--customer",
                    "revolut",
                    "--environment",
                    "staging",
                    "--mode",
                    "upgrade",
                ],
                runner=runner,
                stdout=io.StringIO(),
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("Repository cleanliness check failed", stderr.getvalue())
        self.assertFalse(any(call[0][0] in {"scp", "ssh"} for call in runner.calls))

    def test_dirty_source_is_rejected_before_remote_commands(self):
        deploy_addon = load_script("deploy-addon")
        runner = FakeRunner([" M addons/pos_revolut/__manifest__.py\n"])
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as repository:
            exit_code = deploy_addon.main(
                [
                    "deploy",
                    "--repository",
                    repository,
                    "--revision",
                    "a" * 40,
                    "--ssh-target",
                    "root@staging.example.test",
                    "--database",
                    "revolut_staging",
                    "--customer",
                    "revolut",
                    "--environment",
                    "staging",
                    "--mode",
                    "upgrade",
                ],
                runner=runner,
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("working tree is not clean", stderr.getvalue())
        self.assertEqual(len(runner.calls), 1)
        self.assertEqual(runner.calls[0][0][:3], ["git", "status", "--porcelain"])

    def test_exact_revision_is_archived_uploaded_and_reported(self):
        deploy_addon = load_script("deploy-addon")
        revision = "1" * 40

        def create_archive(command, _kwargs):
            archive = Path(command[command.index("--output") + 1])
            archive.write_bytes(b"reviewed archive")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        runner = FakeRunner(
            [
                "",
                revision + "\n",
                revision + "\n",
                "",
                create_archive,
                "#!/usr/bin/env python3\nprint('remote')\n",
                "",
                f"Deployed POS Revolut revision {revision}\n",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as repository:
            exit_code = deploy_addon.main(
                [
                    "deploy",
                    "--repository",
                    repository,
                    "--revision",
                    revision,
                    "--ssh-target",
                    "root@staging.example.test",
                    "--database",
                    "revolut_staging",
                    "--customer",
                    "revolut",
                    "--environment",
                    "staging",
                    "--mode",
                    "upgrade",
                ],
                runner=runner,
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(f"Deployed POS Revolut revision {revision}", stdout.getvalue())
        commands = [call[0] for call in runner.calls]
        self.assertEqual(
            commands[1], ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"]
        )
        self.assertEqual(
            commands[3],
            ["git", "merge-base", "--is-ancestor", revision, "origin/main"],
        )
        self.assertEqual(commands[4][:3], ["git", "archive", "--format=tar.gz"])
        self.assertIn(revision, commands[4])
        self.assertEqual(commands[6][0], "scp")
        self.assertEqual(commands[7][0], "ssh")
        self.assertIn("root@staging.example.test", commands[7])
        self.assertIn("--expected-sha256", commands[7])
        self.assertIn("#!/usr/bin/env python3", runner.calls[7][1]["input"])

    def test_revision_outside_reviewed_ref_is_rejected_before_upload(self):
        deploy_addon = load_script("deploy-addon")
        revision = "5" * 40
        not_reviewed = subprocess.CalledProcessError(
            1,
            ["git", "merge-base", "--is-ancestor", revision, "origin/main"],
        )
        runner = FakeRunner(["", revision + "\n", "6" * 40 + "\n", not_reviewed])
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as repository:
            exit_code = deploy_addon.main(
                [
                    "deploy",
                    "--repository",
                    repository,
                    "--revision",
                    revision,
                    "--ssh-target",
                    "root@staging.example.test",
                    "--database",
                    "revolut_staging",
                    "--customer",
                    "revolut",
                    "--environment",
                    "staging",
                    "--mode",
                    "upgrade",
                ],
                runner=runner,
                stdout=io.StringIO(),
                stderr=stderr,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("not contained in reviewed ref origin/main", stderr.getvalue())
        self.assertFalse(any(call[0][0] in {"scp", "ssh"} for call in runner.calls))


class TestRemoteDeploymentWorkflow(unittest.TestCase):
    def _artifact(self, root):
        source = root / "source" / "addons" / "pos_revolut"
        source.mkdir(parents=True)
        (source / "__manifest__.py").write_text("{'name': 'POS Revolut'}\n")
        archive = root / "artifact.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(source, arcname="addons/pos_revolut")
        return archive

    def _target_configuration(self, root):
        config = root / "etc" / "odoo" / "odoo.conf"
        config.parent.mkdir(parents=True)
        config.write_text(
            "[options]\n"
            "addons_path = /opt/odoo-hosting/addons,"
            "/usr/lib/python3/dist-packages/odoo/addons\n"
        )
        drop_in = root / "etc" / "systemd" / "system" / "odoo.service.d"
        drop_in.mkdir(parents=True)
        (drop_in / "python.conf").write_text("[Service]\nExecStart=/usr/bin/odoo\n")

    def _deployment(
        self, remote, runner, root, archive, revision="4" * 40, mode="upgrade"
    ):
        return remote.RemoteDeployment(
            runner=runner,
            root=root,
            archive=archive,
            expected_sha256=remote.sha256(archive),
            revision=revision,
            database="revolut_staging",
            customer="revolut",
            environment="staging",
            mode=mode,
        )

    def test_financial_blocker_aborts_before_backup_or_service_stop(self):
        remote = load_script("deploy-addon-remote")
        revision = "2" * 40
        runner = FakeRunner(["pos_revolut_payment_operation\n", "1\n"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "artifact.tar.gz"
            archive.write_bytes(b"reviewed archive")
            deployment = remote.RemoteDeployment(
                runner=runner,
                root=root,
                archive=archive,
                expected_sha256=remote.sha256(archive),
                revision=revision,
                database="revolut_staging",
                customer="revolut",
                environment="staging",
                mode="upgrade",
            )

            with self.assertRaisesRegex(
                remote.DeploymentError, "financial operation blocks deployment"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertFalse(
            any(
                command[:3] == ["systemctl", "start", "odoo-backup.service"]
                for command in commands
            )
        )
        self.assertFalse(
            any(command[:3] == ["systemctl", "stop", "odoo"] for command in commands)
        )

    def test_successful_upgrade_installs_release_then_restarts_and_checks_health(self):
        remote = load_script("deploy-addon-remote")
        revision = "3" * 40
        runner = FakeRunner(
            [
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "active\n",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            secret_directory = root / "etc" / "odoo-revolut"
            secret_directory.mkdir()
            secret_file = secret_directory / "revolut.env"
            secret_file.write_text("ODOO_REVOLUT_SECRET_TEST=not-a-real-secret\n")
            secret_file.chmod(0o600)
            previous_release = root / "opt" / "odoo-releases" / "previous"
            previous_release.mkdir(parents=True)
            current = root / "opt" / "odoo-hosting" / "addons" / "pos_revolut"
            current.parent.mkdir(parents=True)
            current.symlink_to(previous_release, target_is_directory=True)
            deployment = remote.RemoteDeployment(
                runner=runner,
                root=root,
                archive=archive,
                expected_sha256=remote.sha256(archive),
                revision=revision,
                database="revolut_staging",
                customer="revolut",
                environment="staging",
                mode="upgrade",
            )

            report = deployment.execute()

            release = (
                root
                / "opt"
                / "odoo-releases"
                / "revolut"
                / "staging"
                / revision
                / "pos_revolut"
            )
            self.assertEqual((release / "REVISION").read_text().strip(), revision)
            self.assertEqual(release.parent.stat().st_mode & 0o222, 0)
            self.assertEqual(release.stat().st_mode & 0o222, 0)
            self.assertEqual(
                (release / "__manifest__.py").stat().st_mode & 0o222, 0
            )
            self.assertTrue(current.is_symlink())
            self.assertEqual(current.resolve(), release)
            self.assertIn(f"Deployed POS Revolut revision {revision}", report)
            backup_files = list(
                (root / "var" / "backups" / "odoo-revolut-deploy").glob(
                    "*/etc/odoo/odoo.conf"
                )
            )
            self.assertEqual(len(backup_files), 1)
            backup = backup_files[0].parents[2]
            self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
            copied_secret = backup / "etc" / "odoo-revolut" / "revolut.env"
            self.assertEqual(copied_secret.read_text(), secret_file.read_text())
            manifest = json.loads((backup / "deployment.json").read_text())
            self.assertEqual(manifest["previous_release"], str(previous_release))

        commands = [call[0] for call in runner.calls]
        self.assertIn(["systemctl", "start", "odoo-backup.service"], commands)
        self.assertIn(["systemctl", "stop", "odoo"], commands)
        update = next(command for command in commands if "/usr/bin/odoo" in command)
        self.assertIn("--update", update)
        self.assertIn("pos_revolut", update)
        self.assertIn("--stop-after-init", update)
        self.assertIn("--no-http", update)
        self.assertIn("--workers=0", update)
        self.assertLess(
            commands.index(update), commands.index(["systemctl", "start", "odoo"])
        )

    def test_final_preflight_race_leaves_odoo_stopped_without_updating(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner(
            [
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "pos_revolut_payment_operation\n",
                "1\n",
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(remote, runner, root, archive)

            with self.assertRaisesRegex(
                remote.DeploymentError, "after checkout quiescence"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertIn(["systemctl", "stop", "odoo"], commands)
        self.assertFalse(any("/usr/bin/odoo" in command for command in commands))
        self.assertNotIn(["systemctl", "start", "odoo"], commands)

    def test_backup_failure_does_not_stop_or_update_odoo(self):
        remote = load_script("deploy-addon-remote")
        failure = subprocess.CalledProcessError(
            1, ["systemctl", "start", "odoo-backup.service"], stderr="backup failed"
        )
        runner = FakeRunner(
            ["pos_revolut_payment_operation\n", "0\n", failure]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(remote, runner, root, archive)

            with self.assertRaisesRegex(
                remote.DeploymentError, "Database and filestore backup failed"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertNotIn(["systemctl", "stop", "odoo"], commands)
        self.assertFalse(any("/usr/bin/odoo" in command for command in commands))

    def test_update_failure_is_reported_and_never_restarts_odoo(self):
        remote = load_script("deploy-addon-remote")
        failure = subprocess.CalledProcessError(
            1, ["odoo"], stderr="module update failed"
        )
        runner = FakeRunner(
            [
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "pos_revolut_payment_operation\n",
                "0\n",
                failure,
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(remote, runner, root, archive)

            with self.assertRaisesRegex(
                remote.DeploymentError, "Odoo module update failed"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertIn(["systemctl", "stop", "odoo"], commands)
        self.assertNotIn(["systemctl", "start", "odoo"], commands)

    def test_existing_release_requires_matching_artifact_checksum(self):
        remote = load_script("deploy-addon-remote")
        revision = "7" * 40
        runner = FakeRunner(
            [
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "pos_revolut_payment_operation\n",
                "0\n",
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            release = (
                root
                / "opt"
                / "odoo-releases"
                / "revolut"
                / "staging"
                / revision
                / "pos_revolut"
            )
            release.mkdir(parents=True)
            (release / "REVISION").write_text(revision + "\n")
            deployment = self._deployment(
                remote, runner, root, archive, revision=revision
            )

            with self.assertRaisesRegex(
                remote.DeploymentError, "artifact checksum marker"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertNotIn(["systemctl", "start", "odoo"], commands)

    def test_existing_release_contents_must_match_uploaded_artifact(self):
        remote = load_script("deploy-addon-remote")
        revision = "9" * 40
        runner = FakeRunner(
            [
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "pos_revolut_payment_operation\n",
                "0\n",
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            release = (
                root
                / "opt"
                / "odoo-releases"
                / "revolut"
                / "staging"
                / revision
                / "pos_revolut"
            )
            release.mkdir(parents=True)
            (release / "__manifest__.py").write_text("{'tampered': True}\n")
            (release / "REVISION").write_text(revision + "\n")
            (release / "ARTIFACT_SHA256").write_text(remote.sha256(archive) + "\n")
            deployment = self._deployment(
                remote, runner, root, archive, revision=revision
            )

            with self.assertRaisesRegex(
                remote.DeploymentError, "contents do not match"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertNotIn(["systemctl", "start", "odoo"], commands)

    def test_fresh_install_uses_init_with_offline_worker_flags(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner(
            [
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "active\n",
                "",
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(
                remote, runner, root, archive, mode="install"
            )
            deployment.execute()

        commands = [call[0] for call in runner.calls]
        install = next(command for command in commands if "/usr/bin/odoo" in command)
        self.assertIn("--init", install)
        self.assertNotIn("--update", install)
        self.assertIn("--stop-after-init", install)
        self.assertIn("--no-http", install)
        self.assertIn("--workers=0", install)

    def test_health_failure_is_reported_after_successful_restart(self):
        remote = load_script("deploy-addon-remote")
        failure = subprocess.CalledProcessError(
            3, ["systemctl", "is-active", "odoo"], stderr="inactive"
        )
        runner = FakeRunner(
            [
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                "pos_revolut_payment_operation\n",
                "0\n",
                "",
                "",
                failure,
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(remote, runner, root, archive)

            with self.assertRaisesRegex(
                remote.DeploymentError, "Odoo service health check failed"
            ):
                deployment.execute()

        commands = [call[0] for call in runner.calls]
        self.assertIn(["systemctl", "start", "odoo"], commands)

    def test_remote_cli_uses_lock_reports_revision_and_removes_artifact(self):
        remote = load_script("deploy-addon-remote")
        revision = "8" * 40
        runner = FakeRunner(
            [
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "active\n",
                "",
            ]
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            exit_code = remote.main(
                [
                    "--archive",
                    str(archive),
                    "--expected-sha256",
                    remote.sha256(archive),
                    "--revision",
                    revision,
                    "--database",
                    "revolut_staging",
                    "--customer",
                    "revolut",
                    "--environment",
                    "staging",
                    "--mode",
                    "install",
                ],
                runner=runner,
                stdout=stdout,
                stderr=stderr,
                root=root,
                effective_uid=0,
            )

            self.assertFalse(archive.exists())
            lock = root / "run" / "lock" / "pos-revolut-deploy.lock"
            self.assertTrue(lock.exists())

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn(f"Deployed POS Revolut revision {revision}", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()

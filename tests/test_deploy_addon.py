import importlib.machinery
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CAPTURED_PAYMENT_SCHEMA = "\n".join(
    table + "." + column
    for table, columns in {
        "pos_revolut_payment_operation": (
            "id", "state", "provider_state", "amount_minor", "captured_amount_minor",
            "captured_payment_created_at", "retry_safe", "authorization_id",
            "revolut_order_id", "revolut_payment_intent_id", "revolut_payment_id", "report_run_id",
        ),
        "pos_revolut_payment_dispatch": (
            "operation_id", "action", "completed_at", "outcome", "provider_reference",
        ),
        "pos_revolut_cart_authorization": ("id",),
    }.items()
    for column in columns
)


def load_script(name):
    path = REPOSITORY_ROOT / "scripts" / name
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, responses, *, pdf_response="ODOO_PDF_PREFLIGHT_OK\n",
                 service_response="User=odoo\nMainPID=123\n", financial_responses=(),
                 captured_schema=CAPTURED_PAYMENT_SCHEMA):
        self.pdf_response = pdf_response
        self.service_response = service_response
        self.responses = list(responses)
        self.financial_responses = list(financial_responses)
        self.calls = []
        self.captured_schema = captured_schema

    def run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command[0] == "runuser" and command[-1].startswith("SELECT COALESCE(jsonb_agg"):
            response = self.financial_responses.pop(0) if self.financial_responses else "[]"
        elif command[0] == "runuser" and command[-1].startswith("SELECT table_name || '.' || column_name"):
            response = self.captured_schema
        elif command[:3] == ["systemctl", "show", "odoo"]:
            response = self.service_response
        elif command[:2] == ["/usr/sbin/runuser", "--preserve-environment"]:
            response = self.pdf_response
        else:
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
        self.assertEqual(
            commands[4][-1:], ["addons/pos_revolut"]
        )
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
    def test_reviewed_archive_extracts_single_delivered_addon(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "reviewed.tar.gz"
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, text=True
            ).strip()
            subprocess.run(
                [
                    "git", "archive", "--format=tar.gz", "--output", str(archive),
                    revision, "--", "addons/pos_revolut",
                ],
                cwd=REPOSITORY_ROOT,
                check=True,
            )
            deployment = self._deployment(
                remote, FakeRunner([]), root, archive, revision=revision
            )
            release = deployment._extract_release()
            self.assertTrue((release / "pos_revolut" / "__manifest__.py").is_file())
            self.assertFalse((release / "pos_revolut_restaurant").exists())

    def _artifact(self, root):
        source = root / "source" / "addons" / "pos_revolut"
        source.mkdir(parents=True)
        (source / "__manifest__.py").write_text("{'name': 'POS Revolut'}\n")
        archive = root / "artifact.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(source, arcname="addons/pos_revolut")
        return archive

    def _git_shaped_artifact(self, root):
        source = root / "source" / "addons" / "pos_revolut"
        source.mkdir(parents=True)
        (source / "__manifest__.py").write_text("{'name': 'POS Revolut'}\n")
        archive = root / "git-shaped-artifact.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            parent = tarfile.TarInfo("addons/")
            parent.type = tarfile.DIRTYPE
            parent.mode = 0o755
            bundle.addfile(parent)
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
        process = root / "proc" / "123"
        process.mkdir(parents=True)
        (process / "environ").write_bytes(b"PATH=/usr/local/bin:/usr/bin:/bin\0SECRET=do-not-forward\0")
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

    def test_pdf_failure_aborts_before_any_deployment_mutation(self):
        remote = load_script("deploy-addon-remote")
        failures = [
            subprocess.CalledProcessError(1, ["runuser"], stderr="PDF probe: renderer missing"),
            subprocess.CalledProcessError(1, ["runuser"], stderr="PDF probe: renderer incompatible"),
            subprocess.CalledProcessError(1, ["runuser"], stderr="PDF probe: renderer could not execute"),
            subprocess.CalledProcessError(1, ["runuser"], stderr="PDF probe: unreadable PDF"),
            subprocess.TimeoutExpired(["runuser"], 35),
            "unexpected output",
        ]
        for failure in failures:
            with self.subTest(failure=str(failure)):
                runner = FakeRunner(["pos_revolut_payment_operation\n", "0\n"], pdf_response=failure)
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    archive = self._artifact(root)
                    self._target_configuration(root)
                    current = root / "opt" / "odoo-hosting" / "addons" / "pos_revolut"
                    current.parent.mkdir(parents=True)
                    current.symlink_to("/previous/release")
                    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
                    with self.assertRaisesRegex(remote.DeploymentError, "PDF.*odoo-install-pdf"):
                        self._deployment(remote, runner, root, archive).execute()
                    self.assertEqual({path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}, before)
                    self.assertEqual(current.readlink(), Path("/previous/release"))
                    self.assertFalse((root / "opt" / "odoo-releases").exists())
                    self.assertFalse((root / "var" / "backups").exists())
                commands = [call[0] for call in runner.calls]
                self.assertFalse(any(command[:2] in (["systemctl", "stop"], ["systemctl", "start"]) for command in commands))
                self.assertTrue(all("SELECT" in command[-1] for command in commands if "psql" in command))

    def test_pdf_probe_uses_running_service_environment_before_backup(self):
        remote = load_script("deploy-addon-remote")

        def inspect_probe(command, kwargs):
            self.assertEqual(command[:6], ["/usr/sbin/runuser", "--preserve-environment", "-u", "odoo", "--", "/usr/bin/python3"])
            self.assertEqual(kwargs["env"], {"PATH": "/usr/local/bin:/usr/bin:/bin"})
            self.assertLessEqual(kwargs["timeout"], 35)
            self.assertIn("--header-html", kwargs["input"])
            return subprocess.CompletedProcess(command, 0, stdout="ODOO_PDF_PREFLIGHT_OK\n", stderr="")

        # Reaching the backup refusal proves the successful probe permits the next phase.
        backup_failure = subprocess.CalledProcessError(1, ["systemctl"], stderr="backup unavailable")
        runner = FakeRunner(["pos_revolut_payment_operation\n", "0\n", backup_failure], pdf_response=inspect_probe)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            with self.assertRaisesRegex(remote.DeploymentError, "Database and filestore backup failed"):
                self._deployment(remote, runner, root, archive).execute()
        self.assertFalse(any(call[0][:2] == ["systemctl", "stop"] for call in runner.calls))

    def test_pdf_preflight_requires_observable_running_odoo_service(self):
        remote = load_script("deploy-addon-remote")
        for service in ("User=root\nMainPID=123\n", "User=odoo\nMainPID=0\n", "User=odoo\nMainPID=999\n"):
            with self.subTest(service=service), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = self._artifact(root)
                self._target_configuration(root)
                runner = FakeRunner(["pos_revolut_payment_operation\n", "0\n"], service_response=service)
                with self.assertRaisesRegex(remote.DeploymentError, "PDF preflight refused.*odoo-install-pdf"):
                    self._deployment(remote, runner, root, archive).execute()
                self.assertFalse(any(call[0][:2] in (["systemctl", "stop"], ["systemctl", "start"]) for call in runner.calls))

    def test_git_archive_parent_directory_is_accepted(self):
        remote = load_script("deploy-addon-remote")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._git_shaped_artifact(root)
            deployment = self._deployment(remote, FakeRunner([]), root, archive)

            release = deployment._extract_release()

            self.assertTrue((release / "pos_revolut" / "__manifest__.py").is_file())
            self.assertFalse((release / "pos_revolut_restaurant").exists())

    def test_archive_missing_manifest_is_refused(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "addons" / "pos_revolut"
            source.mkdir(parents=True)
            archive = root / "base-only.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                bundle.add(source, arcname="addons/pos_revolut")
            deployment = self._deployment(remote, FakeRunner([]), root, archive)
            with self.assertRaisesRegex(remote.DeploymentError, "POS Revolut addon manifest"):
                deployment._extract_release()

    def test_extraction_failure_leaves_no_partial_revision(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            deployment = self._deployment(remote, FakeRunner([]), root, archive)
            with mock.patch.object(remote.shutil, "move", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(remote.DeploymentError, "extraction failed"):
                    deployment._extract_release()
            revision_root = (
                root / "opt" / "odoo-releases" / "revolut" / "staging" / ("4" * 40)
            )
            self.assertFalse(revision_root.exists())

    def test_permission_failure_removes_published_release_before_retry(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            deployment = self._deployment(remote, FakeRunner([]), root, archive)
            with mock.patch.object(
                deployment, "_make_release_read_only", side_effect=OSError("chmod failed")
            ):
                with self.assertRaisesRegex(remote.DeploymentError, "extraction failed"):
                    deployment._extract_release()
            revision_root = (
                root / "opt" / "odoo-releases" / "revolut" / "staging" / ("4" * 40)
            )
            self.assertFalse(revision_root.exists())
            self.assertEqual(deployment._extract_release(), revision_root)
            self.assertEqual(revision_root.stat().st_mode & 0o222, 0)

    def test_repeat_deployment_restores_read_only_permissions(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            deployment = self._deployment(remote, FakeRunner([]), root, archive)
            release = deployment._extract_release()
            release.chmod(0o755)
            self.assertEqual(deployment._extract_release(), release)
            self.assertEqual(release.stat().st_mode & 0o222, 0)

    def test_non_symlink_bridge_blocks_activation_before_base_changes(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            deployment = self._deployment(remote, FakeRunner([]), root, archive)
            release = deployment._extract_release()
            addons = root / "opt" / "odoo-hosting" / "addons"
            addons.mkdir(parents=True)
            previous = root / "previous"
            previous.mkdir()
            base_link = addons / "pos_revolut"
            base_link.symlink_to(previous, target_is_directory=True)
            (addons / "pos_revolut_restaurant").mkdir()
            with self.assertRaisesRegex(remote.DeploymentError, "not a release symlink"):
                deployment._activate_release(release)
            self.assertEqual(base_link.resolve(), previous)

    def test_failed_base_activation_keeps_odoo_stopped(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner([
            "pos_revolut_payment_operation\n", "0\n", "", "",
            "pos_revolut_payment_operation\n", "0\n",
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(remote, runner, root, archive)
            replace = remote.os.replace

            def fail_base_activation(source, destination):
                if Path(destination).name == "pos_revolut":
                    raise OSError("simulated activation failure")
                return replace(source, destination)

            with mock.patch.object(remote.os, "replace", side_effect=fail_base_activation):
                with self.assertRaisesRegex(remote.DeploymentError, "activate"):
                    deployment.execute()
        commands = [call[0] for call in runner.calls]
        self.assertIn(["systemctl", "stop", "odoo"], commands)
        self.assertNotIn(["systemctl", "start", "odoo"], commands)

    def test_addons_parent_must_be_a_directory(self):
        remote = load_script("deploy-addon-remote")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe-artifact.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                parent = tarfile.TarInfo("addons")
                parent.size = 0
                bundle.addfile(parent, io.BytesIO())
            deployment = self._deployment(remote, FakeRunner([]), root, archive)

            with self.assertRaisesRegex(remote.DeploymentError, "unsafe path"):
                deployment._extract_release()

    def test_update_uses_system_odoo_when_optional_venv_is_absent(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner(["", "", "pos_revolut|installed\npos_restaurant|installed\n"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "artifact.tar.gz"
            archive.write_bytes(b"unused")
            deployment = self._deployment(remote, runner, root, archive)

            deployment._update_module()

        self.assertEqual(
            runner.calls[1][0][:5],
            ["runuser", "-u", "odoo", "--", "/usr/bin/odoo"],
        )

    def test_upgrade_uses_single_addon_when_restaurant_is_installed(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner([
            "pos_restaurant|installed\n",
            "",
            "pos_revolut|installed\npos_restaurant|installed\n",
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unused.tar.gz"
            archive.write_bytes(b"unused")
            self._deployment(remote, runner, root, archive)._update_module()
        update = runner.calls[1][0]
        self.assertEqual(update[update.index("--update") + 1], "pos_revolut")
        self.assertNotIn("--init", update)

    def test_upgrade_merges_installed_bridge(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner([
            "pos_restaurant|installed\npos_revolut_restaurant|installed\n",
            "",
            "pos_revolut|installed\npos_restaurant|installed\n",
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unused.tar.gz"
            archive.write_bytes(b"unused")
            legacy = root / "opt" / "odoo-hosting" / "addons" / "pos_revolut_restaurant"
            legacy.parent.mkdir(parents=True)
            legacy.symlink_to(root / "old-release" / "pos_revolut_restaurant")
            self._deployment(remote, runner, root, archive)._update_module()
            self.assertFalse(legacy.is_symlink())
        update = runner.calls[1][0]
        self.assertEqual(
            update[update.index("--update") + 1],
            "pos_revolut",
        )

    def test_uninstalled_bridge_listing_blocks_completion(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner([
            "pos_revolut_restaurant|uninstalled\n", "",
            "pos_revolut|installed\npos_restaurant|installed\npos_revolut_restaurant|uninstalled\n",
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unused.tar.gz"
            archive.write_bytes(b"unused")
            with self.assertRaisesRegex(remote.DeploymentError, "bridge was not merged"):
                self._deployment(remote, runner, root, archive)._update_module()

    def test_pending_bridge_operation_blocks_module_update(self):
        remote = load_script("deploy-addon-remote")
        for state in ("to install", "to upgrade", "to remove"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "unused.tar.gz"
                archive.write_bytes(b"unused")
                runner = FakeRunner([f"pos_revolut_restaurant|{state}\n"])
                with self.assertRaisesRegex(remote.DeploymentError, "pending module operation"):
                    self._deployment(remote, runner, root, archive)._update_module()
                self.assertEqual(len(runner.calls), 1)

    def test_missing_restaurant_dependency_blocks_update(self):
        remote = load_script("deploy-addon-remote")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unused.tar.gz"
            archive.write_bytes(b"unused")
            runner = FakeRunner(["", "", "pos_revolut|installed\n"])
            with self.assertRaisesRegex(remote.DeploymentError, "dependency is not installed"):
                self._deployment(remote, runner, root, archive)._update_module()

    def test_unmerged_bridge_after_update_blocks_service_restart(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner([
            "pos_revolut_payment_operation\n", "0\n", "", "",
            "pos_revolut_payment_operation\n", "0\n",
            "pos_restaurant|installed\n", "",
            "pos_revolut|installed\npos_restaurant|installed\npos_revolut_restaurant|installed\n",
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            deployment = self._deployment(remote, runner, root, archive)
            with self.assertRaisesRegex(remote.DeploymentError, "bridge was not merged"):
                deployment.execute()
        commands = [call[0] for call in runner.calls]
        self.assertIn(["systemctl", "stop", "odoo"], commands)
        self.assertNotIn(["systemctl", "start", "odoo"], commands)

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

    def test_refund_without_provider_reference_blocks_deployment_before_backup(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner([
            "pos_revolut_payment_operation\npos_revolut_refund_operation\n",
            "0\n",
            "1\n",
        ])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "artifact.tar.gz"
            archive.write_bytes(b"reviewed archive")
            deployment = remote.RemoteDeployment(
                runner=runner,
                root=root,
                archive=archive,
                expected_sha256=remote.sha256(archive),
                revision="a" * 40,
                database="revolut_staging",
                customer="revolut",
                environment="staging",
                mode="upgrade",
            )

            with self.assertRaisesRegex(
                remote.DeploymentError,
                "pos_revolut_refund_operation=1",
            ):
                deployment.execute()

        self.assertFalse(any(
            call[0][:3] == ["systemctl", "start", "odoo-backup.service"]
            or call[0][:3] == ["systemctl", "stop", "odoo"]
            for call in runner.calls
        ))

    def test_unresolved_external_evidence_does_not_prevent_guarded_upgrade(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner(["pos_revolut_external_refund_evidence\n", "1\n"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "artifact.tar.gz"
            archive.write_bytes(b"reviewed archive")
            deployment = remote.RemoteDeployment(
                runner=runner, root=root, archive=archive,
                expected_sha256=remote.sha256(archive), revision="a" * 40,
                database="revolut_staging", customer="revolut",
                environment="staging", mode="upgrade",
            )
            self.assertEqual(deployment._financial_blockers(), [])

    def test_install_and_unknown_models_keep_conservative_financial_guards(self):
        remote = load_script("deploy-addon-remote")
        cases = [
            ("install", "pos_revolut_external_refund_evidence"),
            ("install", "pos_revolut_refund_operation"),
            ("install", "pos_revolut_payment_operation"),
            ("upgrade", "pos_revolut_future_operation"),
        ]
        for mode, table in cases:
            with self.subTest(mode=mode, table=table), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = self._artifact(root)
                runner = FakeRunner([table + "\n", "1\n"])
                deployment = self._deployment(remote, runner, root, archive, mode=mode)
                self.assertEqual(deployment._financial_blockers(), [table + "=1"])

    def test_captured_report_upgrade_has_bounded_read_only_guard(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner(["pos_revolut_payment_operation\n", "0\n"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            deployment = self._deployment(remote, runner, root, self._artifact(root))
            self.assertEqual(deployment._financial_blockers(), [])
        sql = runner.calls[-1][0][-1]
        self.assertIn("provider_state IN ('captured', 'completed')", sql)
        self.assertIn("COALESCE(retry_safe, FALSE) IS FALSE", sql)
        self.assertIn("pos_revolut_payment_dispatch", sql)
        self.assertIn("pos_revolut_cart_authorization", sql)
        self.assertIn("NOT COALESCE", sql)
        self.assertNotIn("UPDATE", sql)

    def test_missing_captured_payment_or_dispatch_schema_keeps_original_guard(self):
        remote = load_script("deploy-addon-remote")
        for missing in CAPTURED_PAYMENT_SCHEMA.splitlines():
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                runner = FakeRunner(["pos_revolut_payment_operation\n", "1\n"],
                                    captured_schema=CAPTURED_PAYMENT_SCHEMA.replace(missing, ""))
                deployment = self._deployment(remote, runner, root, self._artifact(root))
                self.assertEqual(deployment._financial_blockers(), ["pos_revolut_payment_operation=1"])
                self.assertEqual(runner.calls[-1][0][-1],
                                 'SELECT count(*) FROM "pos_revolut_payment_operation" operation WHERE deployment_blocking')

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
                "pos_restaurant|installed\npos_revolut_restaurant|installed\n",
                "",
                "pos_revolut|installed\npos_restaurant|installed\n",
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
            self.assertEqual((release.parent / "REVISION").read_text().strip(), revision)
            self.assertEqual(release.parent.stat().st_mode & 0o222, 0)
            self.assertEqual(release.stat().st_mode & 0o222, 0)
            self.assertEqual(
                (release / "__manifest__.py").stat().st_mode & 0o222, 0
            )
            self.assertTrue(current.is_symlink())
            self.assertEqual(current.resolve(), release)
            bridge = root / "opt" / "odoo-hosting" / "addons" / "pos_revolut_restaurant"
            self.assertFalse(bridge.exists())
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
            self.assertEqual(manifest["previous_releases"]["pos_revolut"], str(previous_release))
            self.assertIsNone(manifest["previous_releases"]["pos_revolut_restaurant"])

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

    def _pending_upgrade_runner(self, before, after, table="pos_revolut_refund_operation"):
        return FakeRunner([
            table + "\n", "0\n", "", "",
            table + "\n", "0\n",
            "pos_restaurant|installed\n", "",
            "pos_revolut|installed\npos_restaurant|installed\n", "",
            "active\n", "",
        ], financial_responses=[json.dumps(before), json.dumps(after)])

    def test_captured_upgrade_preserves_authority_dispatch_and_reservations(self):
        remote = load_script("deploy-addon-remote")
        payment = {"id": 40, "state": "unresolved", "provider_state": "captured",
                   "amount_minor": 1, "captured_amount_minor": 1, "retry_safe": False,
                   "authorization_id": 6, "report_run_id": "original-report",
                   "deployment_blocking": True, "blocking_order_key": "original-order",
                   "blocking_terminal_key": "original-terminal"}
        authority = {"id": 6, "state": "prepared", "canonical": {"base": 1},
                     "tenders": [{"operation": 40}], "projection_revision": 0}
        dispatch = {"id": 10, "operation_id": 40, "action": "create_order",
                    "outcome": "succeeded", "provider_reference": "original-provider-order"}
        runner = self._pending_upgrade_runner([], [], "pos_revolut_payment_operation")
        runner.financial_responses = [json.dumps([row]) for row in
                                      (payment, authority, dispatch, payment, authority, dispatch)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._target_configuration(root)
            result = self._deployment(remote, runner, root, self._artifact(root)).execute()
            saved = next((root / "var/backups/odoo-revolut-deploy").glob("*/financial-state.json"))
            self.assertEqual(json.loads(saved.read_text()), {
                "pos_revolut_payment_operation": [payment],
                "pos_revolut_cart_authorization": [authority],
                "pos_revolut_payment_dispatch": [dispatch],
            })
            self.assertIn("Financial state preserved", result)

    def test_changed_captured_authority_or_dispatch_keeps_odoo_stopped(self):
        remote = load_script("deploy-addon-remote")
        payment = {"id": 40, "state": "unresolved", "captured_amount_minor": 1,
                   "deployment_blocking": True, "blocking_terminal_key": "reserved"}
        authority = {"id": 6, "canonical": {"base": 1}, "projection_revision": 0}
        dispatch = {"id": 10, "outcome": "succeeded", "provider_reference": "original-ref"}
        cases = [
            (dict(payment, captured_amount_minor=0), authority, dispatch),
            (dict(payment, deployment_blocking=False), authority, dispatch),
            (dict(payment, blocking_terminal_key=None), authority, dispatch),
            (payment, dict(authority, canonical={}), dispatch),
            (payment, dict(authority, projection_revision=1), dispatch),
            (payment, authority, dict(dispatch, outcome="unresolved")),
            (payment, authority, dict(dispatch, provider_reference="replacement-ref")),
        ]
        for after in cases:
            with self.subTest(after=after), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self._target_configuration(root)
                runner = self._pending_upgrade_runner([], [], "pos_revolut_payment_operation")
                runner.financial_responses = [json.dumps([row]) for row in
                                              (payment, authority, dispatch, *after)]
                with self.assertRaisesRegex(remote.DeploymentError, "Financial records changed during upgrade"):
                    self._deployment(remote, runner, root, self._artifact(root)).execute()
                self.assertNotIn(["systemctl", "start", "odoo"], [call[0] for call in runner.calls])

    def test_pending_refund_upgrade_preserves_private_financial_snapshot(self):
        remote = load_script("deploy-addon-remote")
        row = {"id": 7, "state": "pending", "revolut_order_id": "a" * 8 + "-1111-4111-8111-" + "b" * 12,
               "original_operation_id": 3, "amount_minor": 1, "idempotency_key": "original-key",
               "return_allocation": {"line": 1}, "deployment_blocking": True,
               "previous_operation_id": 2, "retry_safe": False,
               "report_run_history": ["original-run"], "financial_correction_move_id": 4,
               "native_reconciliation_status": "native_draft", "native_lot_snapshot": {"lot": 5}}
        runner = self._pending_upgrade_runner([row], [dict(row, new_schema_default=False)])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            report = self._deployment(remote, runner, root, archive).execute()
            snapshots = list((root / "var/backups/odoo-revolut-deploy").glob("*/financial-state.json"))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(snapshots[0].read_text()), {"pos_revolut_refund_operation": [row]})
            self.assertIn("Financial state preserved", report)
        self.assertIn(["systemctl", "start", "odoo"], [call[0] for call in runner.calls])

    def test_changed_or_lost_refund_ledger_keeps_odoo_stopped(self):
        remote = load_script("deploy-addon-remote")
        row = {"id": 7, "state": "pending", "revolut_order_id": "original-refund",
               "original_operation_id": 3, "amount_minor": 1, "idempotency_key": "original-key",
               "return_allocation": {"line": 1}, "deployment_blocking": True,
               "previous_operation_id": 2, "retry_safe": False,
               "report_run_history": ["original-run"], "financial_correction_move_id": 4,
               "native_reconciliation_status": "native_draft", "native_lot_snapshot": {"lot": 5}}
        changes = [[], [dict(row, state="verified")], [dict(row, amount_minor=2)],
                   [dict(row, revolut_order_id="replacement-refund")],
                   [dict(row, idempotency_key="replacement-key")],
                   [dict(row, return_allocation={"line": 2})],
                   [dict(row, deployment_blocking=False)], [row, dict(row, id=8)],
                   [dict(row, previous_operation_id=None)], [dict(row, retry_safe=True)],
                   [dict(row, report_run_history=[])], [dict(row, financial_correction_move_id=None)],
                   [dict(row, native_reconciliation_status="native_completed")],
                   [dict(row, native_lot_snapshot={})]]
        for after in changes:
            with self.subTest(after=after), tempfile.TemporaryDirectory() as directory:
                runner = self._pending_upgrade_runner([row], after)
                root = Path(directory)
                archive = self._artifact(root)
                self._target_configuration(root)
                with self.assertRaisesRegex(remote.DeploymentError, "Financial records changed"):
                    self._deployment(remote, runner, root, archive).execute()
                commands = [call[0] for call in runner.calls]
                self.assertIn(["systemctl", "stop", "odoo"], commands)
                self.assertNotIn(["systemctl", "start", "odoo"], commands)

    def test_financial_snapshot_detects_sub_float_precision_amount_change(self):
        remote = load_script("deploy-addon-remote")
        runner = self._pending_upgrade_runner([], [])
        runner.financial_responses = [
            '[{"id":7,"amount":0.010000000000000000001}]',
            '[{"id":7,"amount":0.010000000000000000002}]',
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = self._artifact(root)
            self._target_configuration(root)
            with self.assertRaisesRegex(remote.DeploymentError, "Financial records changed"):
                self._deployment(remote, runner, root, archive).execute()
        self.assertNotIn(["systemctl", "start", "odoo"], [call[0] for call in runner.calls])

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
            )
            release.mkdir(parents=True)
            (release / "pos_revolut").mkdir()
            (release / "pos_revolut" / "__manifest__.py").write_text("{'tampered': True}\n")
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
                "pos_revolut|installed\npos_restaurant|installed\n",
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
                "pos_revolut|installed\npos_restaurant|installed\n",
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

    def test_http_health_check_waits_for_odoo_startup(self):
        remote = load_script("deploy-addon-remote")
        runner = FakeRunner(["", ""])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "artifact.tar.gz"
            archive.write_bytes(b"unused")
            deployment = self._deployment(remote, runner, root, archive)

            deployment._health_check()

        curl = runner.calls[1][0]
        self.assertIn("--retry", curl)
        self.assertIn("--retry-connrefused", curl)
        self.assertIn("--retry-delay", curl)
        self.assertIn("--retry-max-time", curl)

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
                "pos_revolut|installed\npos_restaurant|installed\n",
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

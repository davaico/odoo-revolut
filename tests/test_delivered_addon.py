"""Exercise committed addon artifacts without Docker or provider traffic."""

import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


REPOSITORY = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY / "scripts" / "test-delivered-addon"
loader = importlib.machinery.SourceFileLoader("delivered_addon", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
delivered = importlib.util.module_from_spec(spec)
loader.exec_module(delivered)

FAKE_TEST_ADDON = r'''
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
result = {"args": args, "trees": {}}
for option in ("--addons-dir", "--legacy-addons-dir"):
    if option in args:
        root = Path(args[args.index(option) + 1])
        result["trees"][option] = {
            "root": str(root),
            "files": {str(path.relative_to(root)): path.read_text()
                      for path in root.rglob("*") if path.is_file()},
        }
Path(os.environ["DELIVERED_TEST_LOG"]).write_text(json.dumps(result))
sys.exit(int(os.environ.get("DELIVERED_TEST_EXIT", "0")))
'''


class TestDeliveredAddon(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="revolut-delivered-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repository"
        self.repo.mkdir()
        (self.repo / "scripts").mkdir()
        shutil.copy2(SCRIPT, self.repo / "scripts/test-delivered-addon")
        fake = self.repo / "scripts/test-addon"
        fake.write_text(f"#!{sys.executable}\n" + FAKE_TEST_ADDON)
        fake.chmod(0o755)
        self.log = self.root / "delegation.json"
        self.env = dict(os.environ, DELIVERED_TEST_LOG=str(self.log))
        self.git("init", "--quiet")
        self.git("config", "user.name", "Artifact Test")
        self.git("config", "user.email", "artifact-test@example.invalid")
        self.write_addon("pos_revolut", "original")

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.repo, text=True, stderr=subprocess.PIPE,
        ).strip()

    def write_addon(self, name, version):
        addon = self.repo / "addons" / name
        addon.mkdir(parents=True, exist_ok=True)
        (addon / "__manifest__.py").write_text(repr({"version": version}) + "\n")
        (addon / "__init__.py").write_text(f"# {version}\n")

    def commit(self):
        self.git("add", ".")
        self.git("commit", "--quiet", "--message", "Record fixture")
        return self.git("rev-parse", "HEAD")

    def run_cli(self, revision, scenario="retail", legacy=None, env=None):
        command = [sys.executable, str(self.repo / "scripts/test-delivered-addon"),
                   "--revision", revision, "--scenario", scenario]
        if legacy is not None:
            command += ["--migration-from", legacy]
        return subprocess.run(command, cwd=self.repo, env=env or self.env,
                              capture_output=True, text=True, timeout=20)

    def test_retail_uses_exact_committed_addon_and_reports_archive_digest(self):
        revision = self.commit()
        expected = (self.repo / "addons/pos_revolut/__manifest__.py").read_text()
        self.write_addon("pos_revolut", "newer-commit")
        self.commit()
        self.write_addon("pos_revolut", "dirty-working-tree")
        (self.repo / "private-note.txt").write_text("not part of the addon\n")
        archive = subprocess.check_output(
            ["git", "archive", "--format=tar.gz", revision, "--", "addons/pos_revolut"],
            cwd=self.repo,
        )

        result = self.run_cli(revision)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"Artifact revision: {revision}", result.stdout)
        self.assertIn(f"Artifact SHA256: {hashlib.sha256(archive).hexdigest()}", result.stdout)
        call = json.loads(self.log.read_text())
        self.assertEqual(call["args"][-2:], ["--delivered-scenario", "retail"])
        files = call["trees"]["--addons-dir"]["files"]
        self.assertEqual(files, {"pos_revolut/__manifest__.py": expected,
                                 "pos_revolut/__init__.py": "# original\n"})
        self.assertFalse(Path(call["trees"]["--addons-dir"]["root"]).exists())

    def test_migration_delegates_original_two_addon_tree_and_current_candidate(self):
        self.write_addon("pos_revolut_restaurant", "legacy-bridge")
        legacy = self.commit()
        shutil.rmtree(self.repo / "addons/pos_revolut_restaurant")
        self.write_addon("pos_revolut", "combined")
        revision = self.commit()

        result = self.run_cli(revision, "migration", legacy)

        self.assertEqual(result.returncode, 0, result.stderr)
        call = json.loads(self.log.read_text())
        self.assertEqual(call["args"][-2:], ["--delivered-scenario", "migration"])
        current = call["trees"]["--addons-dir"]["files"]
        old = call["trees"]["--legacy-addons-dir"]["files"]
        self.assertEqual(current["pos_revolut/__init__.py"], "# combined\n")
        self.assertNotIn("pos_revolut_restaurant/__init__.py", current)
        self.assertEqual(old["pos_revolut/__init__.py"], "# original\n")
        self.assertEqual(old["pos_revolut_restaurant/__init__.py"], "# legacy-bridge\n")
        self.assertTrue(all(not Path(tree["root"]).exists() for tree in call["trees"].values()))

    def test_bad_revisions_and_missing_migration_input_do_not_delegate(self):
        revision = self.commit()
        for candidate, scenario, legacy in [
            (revision[:7], "retail", None),
            ("f" * 40, "retail", None),
            (revision, "migration", None),
            (revision, "migration", "f" * 40),
        ]:
            with self.subTest(candidate=candidate, scenario=scenario, legacy=legacy):
                result = self.run_cli(candidate, scenario, legacy)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_git_symlinks_in_candidate_or_legacy_are_refused_before_delegation(self):
        self.write_addon("pos_revolut_restaurant", "legacy")
        outside = self.root / "outside"
        outside.write_text("outside archive\n")
        link = self.repo / "addons/pos_revolut_restaurant/linked.txt"
        link.symlink_to(outside)
        legacy = self.commit()
        shutil.rmtree(self.repo / "addons/pos_revolut_restaurant")
        revision = self.commit()
        result = self.run_cli(revision, "migration", legacy)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe path or member type", result.stderr)
        self.assertFalse(self.log.exists())
        (self.repo / "addons/pos_revolut/linked.txt").symlink_to(outside)
        result = self.run_cli(self.commit())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe path or member type", result.stderr)
        self.assertFalse(self.log.exists())
        self.assertEqual(outside.read_text(), "outside archive\n")

    def test_downstream_failure_is_reported_and_extracted_tree_is_removed(self):
        result = self.run_cli(self.commit(), env=dict(self.env, DELIVERED_TEST_EXIT="29"))
        self.assertNotEqual(result.returncode, 0)
        call = json.loads(self.log.read_text())
        self.assertFalse(Path(call["trees"]["--addons-dir"]["root"]).exists())

    def archive(self, entries):
        archive = self.root / "crafted.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, kind, content in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = "../../outside"
                if kind == tarfile.REGTYPE:
                    member.size = len(content)
                bundle.addfile(member, io.BytesIO(content) if member.isfile() else None)
        return archive

    def test_unsafe_archive_paths_and_member_types_are_refused(self):
        manifest = ("addons/pos_revolut/__manifest__.py", tarfile.REGTYPE, b"{}")
        for name, kind in [
            ("../outside", tarfile.REGTYPE),
            (str(self.root / "outside"), tarfile.REGTYPE),
            ("addons/pos_revolut/../../outside", tarfile.REGTYPE),
            ("addons/another_addon/file", tarfile.REGTYPE),
            ("addons/pos_revolut/link", tarfile.SYMTYPE),
            ("addons/pos_revolut/link", tarfile.LNKTYPE),
            ("addons/pos_revolut/fifo", tarfile.FIFOTYPE),
        ]:
            with self.subTest(name=name, kind=kind):
                archive = self.archive([manifest, (name, kind, b"unsafe")])
                destination = self.root / "extracted"
                with self.assertRaises(delivered.ArtifactError):
                    delivered.extract_addons(archive, destination, ("pos_revolut",))
                self.assertFalse((self.root / "outside").exists())
                self.assertFalse((destination / "addons/pos_revolut/__manifest__.py").exists())

    def test_required_manifests_and_archive_limits_are_checked(self):
        entries = [("addons/pos_revolut/__init__.py", tarfile.REGTYPE, b"# addon")]
        with self.assertRaises(delivered.ArtifactError):
            delivered.extract_addons(self.archive(entries), self.root / "missing", ("pos_revolut",))
        entries.append(("addons/pos_revolut/__manifest__.py", tarfile.REGTYPE, b"{}"))
        with self.assertRaises(delivered.ArtifactError):
            delivered.extract_addons(self.archive(entries), self.root / "bridge",
                                     ("pos_revolut", "pos_revolut_restaurant"))
        for setting, limit in [("MAX_ARCHIVE_MEMBERS", 1), ("MAX_ARCHIVE_BYTES", 1)]:
            with self.subTest(setting=setting), patch.object(delivered, setting, limit):
                with self.assertRaises(delivered.ArtifactError):
                    delivered.extract_addons(self.archive(entries), self.root / setting, ("pos_revolut",))


if __name__ == "__main__":
    unittest.main()

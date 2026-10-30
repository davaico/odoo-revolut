"""Verify that root and historical addons produce the same guarded archive layout."""

import importlib.machinery
import importlib.util
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


class TestStorePackaging(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="revolut-store-package-")
        self.addCleanup(directory.cleanup)
        self.repository = Path(directory.name)
        self.git("init", "--quiet")
        loader = importlib.machinery.SourceFileLoader(
            "store_delivered_addon", str(ROOT / "scripts/test-delivered-addon"),
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.delivered = importlib.util.module_from_spec(spec)
        loader.exec_module(self.delivered)
        override = patch.object(self.delivered, "REPOSITORY", self.repository)
        override.start()
        self.addCleanup(override.stop)

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repository), *args], text=True,
        ).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=Packaging fixture", "-c",
                 "user.email=packaging@example.invalid", "commit", "--quiet", "-m", "Fixture")
        return self.git("rev-parse", "HEAD")

    def addon(self, parent):
        addon = self.repository / parent / "pos_revolut"
        addon.mkdir(parents=True)
        (addon / "__manifest__.py").write_text("{'version': '18.0.1.0.4'}\n")
        (addon / "__init__.py").write_text("# committed fixture\n")
        return addon

    def test_root_and_legacy_snapshots_produce_identical_addon_paths(self):
        for parent in ("", "addons"):
            with self.subTest(parent=parent):
                addon = self.addon(parent)
                revision = self.commit()
                archive = self.repository / "release.tar.gz"
                self.delivered.archive_addons(revision, archive)
                with tarfile.open(archive) as bundle:
                    files = {item.name for item in bundle.getmembers() if item.isfile()}
                    self.assertEqual(files, {
                        "addons/pos_revolut/__manifest__.py", "addons/pos_revolut/__init__.py",
                    })
                    self.assertEqual(
                        bundle.extractfile("addons/pos_revolut/__init__.py").read(),
                        b"# committed fixture\n",
                    )
                archive.unlink()
                for file in addon.iterdir():
                    file.unlink()
                addon.rmdir()

    def test_missing_or_ambiguous_addon_is_rejected_before_archive_creation(self):
        (self.repository / "README").write_text("fixture\n")
        revision = self.commit()
        archive = self.repository / "release.tar.gz"
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.delivered.archive_addons(revision, archive)
        self.assertFalse(archive.exists())
        self.addon("")
        self.addon("addons")
        revision = self.commit()
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.delivered.archive_addons(revision, archive)
        self.assertFalse(archive.exists())

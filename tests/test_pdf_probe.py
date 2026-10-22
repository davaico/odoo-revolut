"""Execute the deployment PDF probe against disposable renderer processes.

All failure fixtures are local executables without external URLs. Run with the
supported Odoo Python environment to exercise parsing/rendering checks too.
"""

import importlib.util
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROBE = runpy.run_path(str(ROOT / "scripts" / "deploy-addon-remote"))["PDF_PROBE"]
HAS_ODOO = importlib.util.find_spec("odoo") is not None


class TestPdfProbe(unittest.TestCase):
    def _reject(self, script, diagnostic, *, executable=True):
        with tempfile.TemporaryDirectory(prefix="test-pdf-probe-") as directory:
            if script is not None:
                renderer = Path(directory) / "wkhtmltopdf"
                renderer.write_text("#!/bin/sh\n" + script)
                renderer.chmod(0o700 if executable else 0o600)
            result = subprocess.run(
                [sys.executable, "-"], input=PROBE, text=True, capture_output=True,
                env=dict(os.environ, PATH=directory), timeout=35,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(diagnostic, result.stderr)
        self.assertNotIn("ODOO_PDF_PREFLIGHT_OK", result.stdout)

    def test_missing_executable_is_rejected(self):
        self._reject(None, "renderer not found")

    def test_inaccessible_executable_is_rejected(self):
        self._reject("exit 0\n", "renderer not found", executable=False)

    def test_unpatched_build_is_rejected(self):
        self._reject("echo 'wkhtmltopdf 0.12.6 (without patched Qt)'\n", "renderer incompatible")

    def test_execution_failure_is_rejected(self):
        self._reject("exit 2\n", "could not execute or render")

    @unittest.skipUnless(HAS_ODOO, "Run in the supported Odoo image for PDF parsing")
    def test_rendering_failure_is_rejected_after_compatible_version(self):
        self._reject(
            'if [ "$1" = --version ]; then\n'
            "  echo 'wkhtmltopdf 0.12.6.1 (with patched qt)'\n"
            "else\n  exit 2\nfi\n", "could not execute or render",
        )

    @unittest.skipUnless(HAS_ODOO, "Run in the supported Odoo image for PDF parsing")
    def test_successful_renderer_with_unreadable_output_is_rejected(self):
        self._reject(
            'if [ "$1" = --version ]; then\n'
            "  echo 'wkhtmltopdf 0.12.6.1 (with patched qt)'\n"
            "else\n  for argument do output=$argument; done\n"
            '  printf "unreadable document" > "$output"\nfi\n', "nonempty PDF",
        )

    @unittest.skipUnless(HAS_ODOO, "Run in the supported Odoo image for real rendering")
    def test_real_renderer_produces_readable_body_header_and_footer(self):
        result = subprocess.run(
            [sys.executable, "-"], input=PROBE, text=True, capture_output=True, timeout=35,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "ODOO_PDF_PREFLIGHT_OK")

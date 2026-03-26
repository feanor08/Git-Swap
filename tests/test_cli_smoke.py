"""
tests/test_cli_smoke.py
-----------------------
Smoke tests for the CLI entry point.

Validates that all modules import cleanly, the argparse parser builds
without errors, and every registered subcommand appears in the help text.
"""

import subprocess
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).parent.parent.resolve()
_CLI  = _ROOT / "git_identity_switcher.py"

EXPECTED_SUBCOMMANDS = [
    "setup",
    "swap",
    "status",
    "use-personal",
    "use-work",
    "set-identity",
    "show-remote",
    "test-personal",
    "test-work",
    "uninstall",
]


class TestImports(unittest.TestCase):

    def test_all_modules_importable(self):
        """Every gitswap module must import without errors."""
        modules = [
            "gitswap",
            "gitswap.constants",
            "gitswap.utils",
            "gitswap.config",
            "gitswap.ssh",
            "gitswap.git_ops",
            "gitswap.swap",
            "gitswap.cli",
            "gitswap.ui.installer",
            "gitswap.ui.theme",
            "gitswap.ui.widgets",
        ]
        for name in modules:
            with self.subTest(module=name):
                import importlib
                importlib.import_module(name)


class TestParser(unittest.TestCase):

    def _help(self) -> str:
        result = subprocess.run(
            [sys.executable, str(_CLI), "--help"],
            capture_output=True, text=True,
        )
        return result.stdout + result.stderr

    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(_CLI), "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)

    def test_all_subcommands_in_help(self):
        help_text = self._help()
        for cmd in EXPECTED_SUBCOMMANDS:
            with self.subTest(subcommand=cmd):
                self.assertIn(cmd, help_text)

    def test_unknown_subcommand_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(_CLI), "not-a-real-command"],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)


class TestEmailValidationRegex(unittest.TestCase):
    """The email regex used in the UI should accept valid and reject invalid."""

    def setUp(self):
        import re
        self.re = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

    def test_accepts_valid_emails(self):
        for addr in ("user@example.com", "me+tag@sub.domain.org", "a@b.io"):
            with self.subTest(email=addr):
                self.assertRegex(addr, self.re)

    def test_rejects_invalid_emails(self):
        for addr in ("notanemail", "@nodomain", "missing@tld", "spaces @x.com"):
            with self.subTest(email=addr):
                self.assertNotRegex(addr, self.re)


if __name__ == "__main__":
    unittest.main()

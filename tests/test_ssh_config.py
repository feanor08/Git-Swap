"""
tests/test_ssh_config.py
------------------------
Unit tests for gitswap.ssh — SSH config block management.

These tests write to a temporary file instead of ~/.ssh/config so they
are completely safe to run without touching the real system.
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch


def _with_temp_config(test_fn):
    """Decorator: run `test_fn(tmp_config_path)` using a fresh temp file."""
    def wrapper(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            tmp = Path(f.name)
        try:
            test_fn(self, tmp)
        finally:
            tmp.unlink(missing_ok=True)
    wrapper.__name__ = test_fn.__name__
    return wrapper


class TestEnsureSshConfigBlock(unittest.TestCase):

    def _run(self, tmp: Path, alias: str, hostname: str):
        """Call ensure_ssh_config_block pointing at `tmp` instead of ~/.ssh/config."""
        from gitswap import ssh
        key_path = Path(f"/fake/.ssh/id_ed25519_{alias}")
        with patch.object(ssh, "SSH_CONFIG", tmp):
            ssh.ensure_ssh_config_block(alias, hostname, key_path)

    @_with_temp_config
    def test_appends_new_block(self, tmp: Path):
        """Block is written to an empty config."""
        self._run(tmp, "git-personal", "github.com")
        content = tmp.read_text()
        self.assertIn("Host git-personal", content)
        self.assertIn("HostName github.com", content)

    @_with_temp_config
    def test_idempotent_same_hostname(self, tmp: Path):
        """Calling twice with the same args writes only one block."""
        self._run(tmp, "git-personal", "github.com")
        self._run(tmp, "git-personal", "github.com")
        content = tmp.read_text()
        self.assertEqual(content.count("Host git-personal"), 1)

    @_with_temp_config
    def test_updates_changed_hostname(self, tmp: Path):
        """When the hostname changes, the old block is replaced."""
        self._run(tmp, "git-work", "gitlab.com")
        self._run(tmp, "git-work", "gitlab.mycompany.com")
        content = tmp.read_text()
        self.assertEqual(content.count("Host git-work"), 1)
        self.assertNotIn("HostName gitlab.com\n", content)
        self.assertIn("HostName gitlab.mycompany.com", content)

    @_with_temp_config
    def test_does_not_touch_other_blocks(self, tmp: Path):
        """Updating one alias leaves other Host blocks intact."""
        self._run(tmp, "git-personal", "github.com")
        self._run(tmp, "git-work",     "gitlab.com")
        self._run(tmp, "git-work",     "gitlab.mycompany.com")
        content = tmp.read_text()
        self.assertIn("Host git-personal", content)
        self.assertIn("HostName github.com", content)


class TestRemoveSshConfigBlock(unittest.TestCase):

    def _run_ensure(self, tmp: Path, alias: str, hostname: str):
        from gitswap import ssh
        key_path = Path(f"/fake/.ssh/id_ed25519_{alias}")
        with patch.object(ssh, "SSH_CONFIG", tmp):
            ssh.ensure_ssh_config_block(alias, hostname, key_path)

    def _run_remove(self, tmp: Path, alias: str) -> bool:
        from gitswap import ssh
        with patch.object(ssh, "SSH_CONFIG", tmp):
            return ssh.remove_ssh_config_block(alias)

    @_with_temp_config
    def test_removes_existing_block(self, tmp: Path):
        self._run_ensure(tmp, "git-personal", "github.com")
        removed = self._run_remove(tmp, "git-personal")
        self.assertTrue(removed)
        self.assertNotIn("Host git-personal", tmp.read_text())

    @_with_temp_config
    def test_returns_false_when_not_found(self, tmp: Path):
        removed = self._run_remove(tmp, "git-personal")
        self.assertFalse(removed)

    def test_returns_false_when_file_missing(self):
        from gitswap import ssh
        missing = Path("/tmp/does_not_exist_gitswap_test.conf")
        with patch.object(ssh, "SSH_CONFIG", missing):
            result = ssh.remove_ssh_config_block("git-personal")
        self.assertFalse(result)

    @_with_temp_config
    def test_leaves_other_blocks_intact(self, tmp: Path):
        self._run_ensure(tmp, "git-personal", "github.com")
        self._run_ensure(tmp, "git-work",     "gitlab.com")
        self._run_remove(tmp, "git-personal")
        content = tmp.read_text()
        self.assertNotIn("Host git-personal", content)
        self.assertIn("Host git-work", content)


if __name__ == "__main__":
    unittest.main()

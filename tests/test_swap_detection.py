"""
tests/test_swap_detection.py
-----------------------------
Unit tests for gitswap.swap.detect_current_profile.

All git subprocess calls are mocked so these tests run without a real repo.
"""

import unittest
from unittest.mock import patch


_CONFIG = {
    "personal": {"host": "github.com",    "email": "me@personal.com"},
    "work":     {"host": "gitlab.work.com", "email": "me@work.com"},
}


class TestDetectCurrentProfile(unittest.TestCase):

    def _detect(self, url: str | None, email: str | None) -> str | None:
        from gitswap.swap import detect_current_profile
        with (
            patch("gitswap.swap.get_remote_url", return_value=url),
            patch("gitswap.swap.get_local_email", return_value=email),
        ):
            return detect_current_profile(_CONFIG)

    # ── Step 1: SSH alias in URL ───────────────────────────────────────────

    def test_detects_personal_by_alias(self):
        result = self._detect("git@git-personal:user/repo.git", None)
        self.assertEqual(result, "personal")

    def test_detects_work_by_alias(self):
        result = self._detect("git@git-work:team/repo.git", None)
        self.assertEqual(result, "work")

    # ── Step 2: repo-local user.email ─────────────────────────────────────

    def test_detects_personal_by_email(self):
        result = self._detect("git@github.com:user/repo.git", "me@personal.com")
        self.assertEqual(result, "personal")

    def test_detects_work_by_email(self):
        result = self._detect("git@gitlab.work.com:team/repo.git", "me@work.com")
        self.assertEqual(result, "work")

    # ── Step 3: hostname in URL ───────────────────────────────────────────

    def test_detects_personal_by_hostname(self):
        result = self._detect("git@github.com:user/repo.git", None)
        self.assertEqual(result, "personal")

    def test_detects_work_by_hostname(self):
        result = self._detect("git@gitlab.work.com:team/repo.git", None)
        self.assertEqual(result, "work")

    # ── Fallback ──────────────────────────────────────────────────────────

    def test_returns_none_when_unrecognised(self):
        result = self._detect("git@unknown.host:someone/repo.git", "other@email.com")
        self.assertIsNone(result)

    def test_returns_none_with_no_remote(self):
        result = self._detect(None, None)
        self.assertIsNone(result)

    def test_alias_takes_priority_over_email(self):
        # Remote already swapped to work alias, but local email is personal —
        # the alias (step 1) should win.
        result = self._detect("git@git-work:team/repo.git", "me@personal.com")
        self.assertEqual(result, "work")


if __name__ == "__main__":
    unittest.main()

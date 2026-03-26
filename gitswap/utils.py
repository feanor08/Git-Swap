"""
gitswap/utils.py
----------------
Subprocess wrapper and terminal output helpers.

These utilities are intentionally dependency-free (no internal package
imports) so they can be safely imported by every other module.
"""

import subprocess
import sys
from typing import Any


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess:
    """
    Thin wrapper around subprocess.run with project-wide defaults.

    Args:
        cmd:     Command and arguments as a list (never a shell string).
        check:   Raise CalledProcessError on non-zero exit when True (default).
        capture: Capture stdout/stderr when True; otherwise they go to the
                 terminal.  When captured, access via result.stdout/.stderr.
        **kwargs: Forwarded verbatim to subprocess.run.
    """
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        **kwargs,
    )


# ── Terminal output helpers ───────────────────────────────────────────────────
# Consistent prefix characters make log lines easy to scan at a glance.

def success(msg: str) -> None:
    """Print a green-flavoured success line."""
    print(f"  [ok]  {msg}")


def info(msg: str) -> None:
    """Print a neutral informational line."""
    print(f"  [..]  {msg}")


def warn(msg: str) -> None:
    """Print a warning to stderr (non-fatal)."""
    print(f"  [!!]  {msg}", file=sys.stderr)


def die(msg: str) -> None:
    """Print an error to stderr and exit with code 1 (fatal)."""
    print(f"  [XX]  {msg}", file=sys.stderr)
    sys.exit(1)

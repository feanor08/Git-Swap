"""
gitswap/config.py
-----------------
Load and persist the user's identity configuration.

Config schema (stored in ~/.git_identity_switcher.json):

    {
        "personal": {
            "platform": "GitHub",           # display name from PLATFORMS
            "host":     "github.com",       # SSH hostname
            "name":     "Jane Doe",         # git commit author name
            "email":    "jane@example.com", # git commit author email
            "path":     "janedoe"           # GitHub username or GitLab group/path
        },
        "work": {
            "platform": "Other",
            "host":     "gitlab.company.com",
            "name":     "Jane Doe",
            "email":    "jane@company.com",
            "path":     "team/backend"
        },
        "alias":          "gitSwap",        # name of the installed shell command
        "setup_complete": true
    }

Two loaders are provided:
  load_config()          — used by the CLI; calls die() on failure.
  load_config_or_none()  — used by the UI; returns None on failure (no crash).
"""

import json

from gitswap.constants import CONFIG_FILE
from gitswap.utils import die


def load_config() -> dict:
    """
    Load the config file and return its contents as a dict.
    Exits the process with a helpful message if the file is missing or corrupt.
    Intended for CLI subcommands where a missing config is always an error.
    """
    if not CONFIG_FILE.exists():
        die(
            "No config found. Run the UI first:\n"
            "    python3 git_identity_ui.py"
        )
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception as exc:
        die(f"Failed to read config ({CONFIG_FILE}): {exc}")


def load_config_or_none() -> dict | None:
    """
    Load the config file and return its contents, or None if unavailable.
    Never calls die() — safe to use in UI code where a silent absence is normal
    (e.g., first-run check before the setup form is shown).
    """
    if not CONFIG_FILE.exists():
        return None
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return None


def save_config(data: dict) -> None:
    """
    Write `data` to the config file as formatted JSON.
    Sets permissions to 0o600 (owner read/write only) because the file may
    contain email addresses that the user might prefer to keep private.
    """
    CONFIG_FILE.write_text(json.dumps(data, indent=2))
    CONFIG_FILE.chmod(0o600)

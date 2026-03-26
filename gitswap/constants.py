"""
gitswap/constants.py
--------------------
All path constants and identity string constants for the entire package.

Changing a value here propagates to every module automatically — nothing is
hardcoded anywhere else.  This file has zero internal package imports so it
is always safe to import without triggering side-effects.
"""

from pathlib import Path

# ── SSH paths ─────────────────────────────────────────────────────────────────

SSH_DIR    = Path.home() / ".ssh"
SSH_CONFIG = SSH_DIR / "config"

# Private key files.  Public keys are the same path with a ".pub" suffix.
PERSONAL_KEY = SSH_DIR / "id_ed25519_personal"
WORK_KEY     = SSH_DIR / "id_ed25519_work"

PERSONAL_PUB = PERSONAL_KEY.with_suffix(".pub")
WORK_PUB     = WORK_KEY.with_suffix(".pub")

# SSH host aliases used in git remote URLs:
#   git@git-personal:username/repo.git
#   git@git-work:group/path/repo.git
PERSONAL_HOST_ALIAS = "git-personal"
WORK_HOST_ALIAS     = "git-work"

# ── App config ────────────────────────────────────────────────────────────────

# JSON file written by the UI and read by the CLI's swap subcommand.
CONFIG_FILE = Path.home() / ".git_identity_switcher.json"

# ── Shell script installation ─────────────────────────────────────────────────

# Candidate directories for the gitSwap shell wrapper, tried in order.
# Falls back to ~/.local/bin (always writable) when /usr/local/bin is not.
INSTALL_DIRS = [
    Path("/usr/local/bin"),
    Path.home() / ".local" / "bin",
]

# ── Platform presets ──────────────────────────────────────────────────────────

# Maps display name → default SSH hostname.
# "Other" has an empty string so the host field is left editable in the UI.
PLATFORMS: dict[str, str] = {
    "GitHub":    "github.com",
    "GitLab":    "gitlab.com",
    "Bitbucket": "bitbucket.org",
    "Other":     "",
}

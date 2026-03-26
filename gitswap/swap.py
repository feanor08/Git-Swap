"""
gitswap/swap.py
---------------
Identity detection and the core swap logic.

This is the semantic heart of Git-Swap.  It answers two questions:
  1. Which identity is currently active in this repo?  (detect_current_profile)
  2. How do we switch to a different identity?          (apply_profile)

Detection cascade used by bare `gitSwap` (no argument):
  Step 1 — SSH alias in remote URL
            Most reliable signal after the first swap has been performed.
            Looks for "git-personal" or "git-work" in the origin URL.

  Step 2 — Repo-local user.email
            Matches .git/config user.email against the stored personal/work
            emails.  Catches repos where identity was set manually without
            changing the remote URL.

  Step 3 — Hostname in remote URL
            Matches the raw hostname (e.g. github.com, gitlab.company.com)
            against stored hosts.  Catches freshly cloned repos before the
            first swap, where the remote still uses the canonical hostname
            rather than a Git-Swap alias.

If all three steps fail, the caller must supply an explicit profile name.
"""

from __future__ import annotations

from gitswap.constants import PERSONAL_HOST_ALIAS, WORK_HOST_ALIAS
from gitswap.config import load_config, load_config_or_none
from gitswap.git_ops import (
    require_git_repo,
    get_remote_url,
    get_local_email,
    infer_repo_name,
    set_remote_url,
    set_local_identity,
)
from gitswap.utils import run, info, success, die


def detect_current_profile(config: dict) -> str | None:
    """
    Inspect the current repo and return "personal", "work", or None.

    None means the active identity could not be determined — the caller should
    ask the user to be explicit (gitSwap work / gitSwap personal).
    """
    url = get_remote_url() or ""

    # ── Step 1: SSH alias ─────────────────────────────────────────────────
    if PERSONAL_HOST_ALIAS in url:
        return "personal"
    if WORK_HOST_ALIAS in url:
        return "work"

    # ── Step 2: repo-local user.email ─────────────────────────────────────
    local_email = get_local_email()
    if local_email:
        if local_email == config.get("personal", {}).get("email", ""):
            return "personal"
        if local_email == config.get("work", {}).get("email", ""):
            return "work"

    # ── Step 3: hostname in remote URL ────────────────────────────────────
    p_host = config.get("personal", {}).get("host", "")
    w_host = config.get("work", {}).get("host", "")
    if p_host and p_host in url:
        return "personal"
    if w_host and w_host in url:
        return "work"

    return None


def apply_profile(profile: str, config: dict) -> None:
    """
    Apply `profile` ("personal" or "work") to the current repo:
      - Rewrites the origin remote URL to use the appropriate SSH host alias.
      - Sets repo-local user.name and user.email from the stored config.

    Neither the global ~/.gitconfig nor any other repo is touched.
    """
    repo = infer_repo_name()

    if profile == "personal":
        p       = config["personal"]
        new_url = f"git@{PERSONAL_HOST_ALIAS}:{p['path']}/{repo}.git"
        set_remote_url(new_url)
        set_local_identity(p["name"], p["email"])
        print(f"\n  Switched to personal identity  ({p['host']})")
        success(f"email  : {p['email']}")
        success(f"remote : {new_url}\n")

    elif profile == "work":
        w       = config["work"]
        new_url = f"git@{WORK_HOST_ALIAS}:{w['path']}/{repo}.git"
        set_remote_url(new_url)
        set_local_identity(w["name"], w["email"])
        print(f"\n  Switched to work identity  ({w['host']})")
        success(f"email  : {w['email']}")
        success(f"remote : {new_url}\n")

    else:
        die(f"Unknown profile '{profile}'.  Use 'work' or 'personal'.")


def cmd_status(args) -> None:
    """
    Print the current Git identity for this repo without making any changes.

    Shows:
      - Active profile (personal / work / unknown)
      - Repo-local user.name and user.email
      - Current origin remote URL
    """
    require_git_repo()
    config = load_config_or_none()

    url   = get_remote_url()
    email = get_local_email()
    name  = run(
        ["git", "config", "--local", "user.name"], check=False, capture=True
    ).stdout.strip()

    profile = "(config not found)"
    if config:
        detected = detect_current_profile(config)
        profile  = detected or "unknown — run: gitSwap work  OR  gitSwap personal"

    print("\n=== Current Git Identity ===\n")
    print(f"  profile  : {profile}")
    print(f"  name     : {name  or '(not set locally)'}")
    print(f"  email    : {email or '(not set locally)'}")
    print(f"  remote   : {url   or '(none)'}")
    print()


def cmd_swap(args) -> None:
    """
    Entry point for the `swap` subcommand and the `gitSwap` shell command.

    Called with no positional argument → auto-detect and toggle.
    Called with "personal" or "work"   → force that profile.
    """
    require_git_repo()
    config  = load_config()
    profile = getattr(args, "profile", None)

    if not profile:
        current = detect_current_profile(config)
        if current == "personal":
            profile = "work"
            info("Detected personal → switching to work")
        elif current == "work":
            profile = "personal"
            info("Detected work → switching to personal")
        else:
            die(
                "Cannot auto-detect the current identity.\n"
                "  Use:  gitSwap work   OR   gitSwap personal"
            )

    apply_profile(profile, config)

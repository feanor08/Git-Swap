"""
gitswap/cli.py
--------------
Argparse CLI: subcommand definitions, handlers, and the main() entry point.

Each cmd_* function is a thin handler that validates its arguments and
delegates all real work to the appropriate domain module (ssh, git_ops, swap).
The CLI itself contains no business logic.

Subcommands
-----------
  setup          Generate SSH keys, update ~/.ssh/config, add keys to agent.
  swap           Toggle or force a Git identity in the current repo.
                 This is what the installed `gitSwap` shell script calls.
  status         Show the current identity for this repo (no changes made).
  use-personal   Manually point origin at the personal SSH alias.
  use-work       Manually point origin at the work SSH alias.
  set-identity   Set repo-local user.name and user.email.
  show-remote    Print current remotes and the repo-local git identity.
  test-personal  Run ssh -T to verify the personal SSH alias works.
  test-work      Run ssh -T to verify the work SSH alias works.
  uninstall      Remove the gitSwap shell script, SSH config blocks, and config.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from gitswap.constants import (
    PERSONAL_KEY,
    WORK_KEY,
    PERSONAL_HOST_ALIAS,
    WORK_HOST_ALIAS,
)
from gitswap.config import load_config
from gitswap.ssh import (
    ensure_ssh_dir,
    generate_key,
    ensure_ssh_config_block,
    remove_ssh_config_block,
    add_key_to_agent,
)
from gitswap.git_ops import (
    require_git_repo,
    get_remote_url,
    infer_repo_name,
    set_remote_url,
    set_local_identity,
)
from gitswap.swap import cmd_swap, cmd_status
from gitswap.utils import run, info, success, warn, die


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------

def cmd_setup(args) -> None:
    """
    One-time (idempotent) setup:
      1. Generate ed25519 key pairs for personal and work identities.
      2. Write Host blocks to ~/.ssh/config.
      3. Load keys into ssh-agent (macOS Keychain when available).
      4. Print the public keys so the user can paste them into GitHub/GitLab/etc.
    """
    personal_host = (getattr(args, "personal_host", None) or "github.com").strip()
    work_host     = (getattr(args, "work_host",     None) or "gitlab.com").strip()

    print("\n=== Setting up SSH identities ===\n")

    ensure_ssh_dir()
    generate_key(PERSONAL_KEY, comment="git-personal")
    generate_key(WORK_KEY,     comment="git-work")
    ensure_ssh_config_block(PERSONAL_HOST_ALIAS, personal_host, PERSONAL_KEY)
    ensure_ssh_config_block(WORK_HOST_ALIAS,     work_host,     WORK_KEY)
    add_key_to_agent(PERSONAL_KEY)
    add_key_to_agent(WORK_KEY)

    print("\n=== Public keys — add these to your Git hosting accounts ===\n")
    print(f"── Personal  ({personal_host}) ──")
    print(PERSONAL_KEY.with_suffix(".pub").read_text().strip())
    print()
    print(f"── Work  ({work_host}) ──")
    print(WORK_KEY.with_suffix(".pub").read_text().strip())
    print()
    success("Done.  Add the keys above to your platforms, then run:")
    print("    python3 git_identity_switcher.py test-personal")
    print("    python3 git_identity_switcher.py test-work")


# ---------------------------------------------------------------------------
# use-personal / use-work
# ---------------------------------------------------------------------------

def cmd_use_personal(args) -> None:
    """
    Manually set the current repo's origin remote to the personal SSH alias.
    Falls back to the path stored in the config when --path is omitted.
    """
    require_git_repo()
    config = load_config()
    p      = config["personal"]
    path   = args.path or p.get("path")
    if not path:
        die("Pass --path USERNAME_OR_GROUP")
    repo   = args.repo or infer_repo_name()
    url    = f"git@{PERSONAL_HOST_ALIAS}:{path}/{repo}.git"
    set_remote_url(url)
    success(f"origin → {url}")


def cmd_use_work(args) -> None:
    """
    Manually set the current repo's origin remote to the work SSH alias.
    Falls back to the path stored in the config when --path is omitted.
    """
    require_git_repo()
    config = load_config()
    w      = config["work"]
    path   = args.path or w.get("path")
    if not path:
        die("Pass --path USERNAME_OR_GROUP")
    repo   = args.repo or infer_repo_name()
    url    = f"git@{WORK_HOST_ALIAS}:{path}/{repo}.git"
    set_remote_url(url)
    success(f"origin → {url}")


# ---------------------------------------------------------------------------
# set-identity
# ---------------------------------------------------------------------------

def cmd_set_identity(args) -> None:
    """
    Write user.name and user.email to .git/config (repo-local only).
    The global ~/.gitconfig is never modified.
    """
    require_git_repo()
    set_local_identity(args.name, args.email)
    success(f"user.name  = {args.name}")
    success(f"user.email = {args.email}")
    info("These settings are local to this repo only.")


# ---------------------------------------------------------------------------
# show-remote
# ---------------------------------------------------------------------------

def cmd_show_remote(args) -> None:
    """Print current remote URLs and the repo-local git identity."""
    require_git_repo()

    print("\n=== Remotes ===\n")
    r = run(["git", "remote", "-v"], check=False, capture=True)
    print(r.stdout.strip() or "  (none configured)")

    print("\n=== Repo-local identity ===\n")
    for key in ("user.name", "user.email"):
        r = run(["git", "config", "--local", key], check=False, capture=True)
        print(f"  {key} = {r.stdout.strip() or '(not set locally)'}")
    print()


# ---------------------------------------------------------------------------
# test-personal / test-work
# ---------------------------------------------------------------------------

def _test_ssh(alias: str, label: str) -> None:
    """
    Run `ssh -T git@<alias>` and interpret the response.

    GitHub returns exit code 1 even on success ("Hi username! You've
    successfully authenticated…"), so we check the output text rather than
    the exit code.
    """
    print(f"\n=== Testing SSH: {alias} ({label}) ===\n")
    info(f"Running: ssh -T git@{alias}")
    r      = run(["ssh", "-T", f"git@{alias}"], check=False, capture=True)
    output = (r.stdout + r.stderr).strip()
    print(f"  {output}")

    greetings = ("authenticated", "welcome", "logged in")
    if any(g in output.lower() for g in greetings):
        success("SSH authentication succeeded!")
    else:
        warn("No success greeting received.")
        warn("Make sure the public key has been added to your account on the platform.")
    print()


def cmd_test_personal(args) -> None:
    _test_ssh(PERSONAL_HOST_ALIAS, "personal")


def cmd_test_work(args) -> None:
    _test_ssh(WORK_HOST_ALIAS, "work")


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------

def cmd_uninstall(args) -> None:
    """
    Remove all artifacts created by Git-Swap setup:
      - The gitSwap shell wrapper (found via PATH / stored config alias)
      - SSH config blocks for git-personal and git-work
      - The ~/.git_identity_switcher.json config file

    SSH key files (~/.ssh/id_ed25519_personal / _work) are NOT deleted
    because they may have been added to hosting platforms and are hard to
    re-register.  Delete them manually if you want a full wipe.
    """
    from gitswap.config import load_config_or_none
    from gitswap.constants import CONFIG_FILE

    cfg   = load_config_or_none()
    alias = (cfg or {}).get("alias", "gitSwap")

    print("\n=== Uninstalling Git-Swap ===\n")

    # 1. Remove the shell wrapper
    wrapper = shutil.which(alias)
    if wrapper:
        try:
            Path(wrapper).unlink()
            success(f"Removed shell wrapper: {wrapper}")
        except PermissionError:
            warn(f"Permission denied removing {wrapper} — try: sudo rm {wrapper}")
    else:
        info(f"Shell wrapper '{alias}' not found on PATH — skipping")

    # 2. Remove SSH config blocks
    removed_p = remove_ssh_config_block(PERSONAL_HOST_ALIAS)
    removed_w = remove_ssh_config_block(WORK_HOST_ALIAS)
    if not removed_p:
        info(f"No SSH config block found for '{PERSONAL_HOST_ALIAS}'")
    if not removed_w:
        info(f"No SSH config block found for '{WORK_HOST_ALIAS}'")

    # 3. Remove the identity config file
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        success(f"Removed config file: {CONFIG_FILE}")
    else:
        info(f"Config file not found: {CONFIG_FILE}")

    print()
    success("Uninstall complete.")
    info("SSH keys were NOT deleted — remove them manually if desired:")
    info("  rm ~/.ssh/id_ed25519_personal ~/.ssh/id_ed25519_personal.pub")
    info("  rm ~/.ssh/id_ed25519_work      ~/.ssh/id_ed25519_work.pub")
    print()


# ---------------------------------------------------------------------------
# Argparse setup
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "setup":         cmd_setup,
    "swap":          cmd_swap,
    "status":        cmd_status,
    "use-personal":  cmd_use_personal,
    "use-work":      cmd_use_work,
    "set-identity":  cmd_set_identity,
    "show-remote":   cmd_show_remote,
    "test-personal": cmd_test_personal,
    "test-work":     cmd_test_work,
    "uninstall":     cmd_uninstall,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git_identity_switcher.py",
        description=(
            "Git-Swap — manage two Git SSH identities (personal + work) on macOS.\n"
            "Supports GitHub, GitLab, Bitbucket, and self-hosted instances."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # First-time setup (or after changing hosts)
  python3 git_identity_switcher.py setup
  python3 git_identity_switcher.py setup --personal-host github.com \\
                                          --work-host gitlab.company.com

  # Swap identity in any repo (toggle / force)
  gitSwap
  gitSwap work
  gitSwap personal

  # Check which identity is active (read-only)
  python3 git_identity_switcher.py status

  # One-off repo configuration
  python3 git_identity_switcher.py set-identity --name "Ada" --email "ada@co.com"
  python3 git_identity_switcher.py show-remote

  # Verify SSH connectivity
  python3 git_identity_switcher.py test-personal
  python3 git_identity_switcher.py test-work

  # Remove all Git-Swap artifacts
  python3 git_identity_switcher.py uninstall
""",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # setup
    p_setup = sub.add_parser("setup",
                             help="Generate SSH keys and configure ~/.ssh/config.")
    p_setup.add_argument("--personal-host", metavar="HOST", default="github.com",
                         help="Hostname for the personal identity (default: github.com).")
    p_setup.add_argument("--work-host",     metavar="HOST", default="gitlab.com",
                         help="Hostname for the work identity (default: gitlab.com).")

    # swap  (called by the gitSwap shell script)
    p_swap = sub.add_parser("swap",
                            help="Toggle or force a Git identity in the current repo.")
    p_swap.add_argument("profile", nargs="?", choices=["personal", "work"],
                        help="Profile to switch to.  Omit to toggle automatically.")

    # status
    sub.add_parser("status",
                   help="Show the active identity for this repo (read-only).")

    # use-personal
    p_up = sub.add_parser("use-personal",
                          help="Set origin to git@git-personal:<path>/<repo>.git")
    p_up.add_argument("--path", metavar="USER_OR_PATH",
                      help="Username or group path (uses stored config when omitted).")
    p_up.add_argument("--repo", metavar="REPO_NAME",
                      help="Repo name (inferred from existing remote when omitted).")

    # use-work
    p_uw = sub.add_parser("use-work",
                          help="Set origin to git@git-work:<path>/<repo>.git")
    p_uw.add_argument("--path", metavar="USER_OR_PATH",
                      help="Username or group path (uses stored config when omitted).")
    p_uw.add_argument("--repo", metavar="REPO_NAME",
                      help="Repo name (inferred from existing remote when omitted).")

    # set-identity
    p_id = sub.add_parser("set-identity",
                          help="Set repo-local user.name and user.email.")
    p_id.add_argument("--name",  required=True, help="Full name for git commits.")
    p_id.add_argument("--email", required=True, help="Email for git commits.")

    # show-remote
    sub.add_parser("show-remote",
                   help="Print current remotes and local git identity.")

    # test-personal / test-work
    sub.add_parser("test-personal",
                   help="Run ssh -T git@git-personal to verify connectivity.")
    sub.add_parser("test-work",
                   help="Run ssh -T git@git-work to verify connectivity.")

    # uninstall
    sub.add_parser("uninstall",
                   help="Remove gitSwap script, SSH config blocks, and config file.")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser  = build_parser()
    args    = parser.parse_args()
    handler = COMMAND_MAP.get(args.command)

    if not handler:
        parser.print_help()
        sys.exit(1)

    try:
        handler(args)
    except subprocess.CalledProcessError as exc:
        die(
            f"Command failed: {' '.join(exc.cmd)}\n"
            f"  {exc.stderr or exc.stdout or ''}"
        )
    except KeyboardInterrupt:
        print()
        sys.exit(130)

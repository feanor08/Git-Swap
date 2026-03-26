#!/usr/bin/env python3
"""
git_identity_switcher.py
------------------------
Manage two SSH-based Git identities on macOS.
Platform-agnostic: GitHub, GitLab, Bitbucket, self-hosted, etc.

Identities : "personal"  and  "work"
SSH aliases: git-personal  →  host you chose for personal
             git-work      →  host you chose for work
SSH keys   : ~/.ssh/id_ed25519_personal
             ~/.ssh/id_ed25519_work
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SSH_DIR    = Path.home() / ".ssh"
SSH_CONFIG = SSH_DIR / "config"

PERSONAL_KEY         = SSH_DIR / "id_ed25519_personal"
WORK_KEY             = SSH_DIR / "id_ed25519_work"
PERSONAL_HOST_ALIAS  = "git-personal"
WORK_HOST_ALIAS      = "git-work"

# Config written by the UI and read by the swap subcommand.
CONFIG_FILE = Path.home() / ".git_identity_switcher.json"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def success(msg):  print(f"  [ok]  {msg}")
def info(msg):     print(f"  [..]  {msg}")
def warn(msg):     print(f"  [!!]  {msg}", file=sys.stderr)
def die(msg):
    print(f"  [XX]  {msg}", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------

def run(cmd, *, check=True, capture=False, **kw):
    return subprocess.run(cmd, check=check, capture_output=capture, text=True, **kw)

def require_git_repo():
    r = run(["git", "rev-parse", "--show-toplevel"], check=False, capture=True)
    if r.returncode != 0:
        die("Not inside a git repository. cd into one first.")
    return Path(r.stdout.strip())

def get_remote_url(remote="origin"):
    r = run(["git", "remote", "get-url", remote], check=False, capture=True)
    return r.stdout.strip() if r.returncode == 0 else None

def infer_repo_name():
    """Guess repo name from current remote URL, or fall back to cwd name."""
    url = get_remote_url()
    if url:
        return Path(url.rstrip("/").split("/")[-1]).stem
    return Path.cwd().name

def load_config():
    if not CONFIG_FILE.exists():
        die("No config found. Run the UI first:\n    python3 git_identity_ui.py")
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception as e:
        die(f"Failed to read config: {e}")

# ---------------------------------------------------------------------------
# SSH key generation
# ---------------------------------------------------------------------------

def ensure_ssh_dir():
    SSH_DIR.mkdir(mode=0o700, exist_ok=True)

def generate_key(key_path, comment):
    if key_path.exists():
        info(f"SSH key already exists: {key_path}")
        return
    info(f"Generating SSH key: {key_path}")
    run(["ssh-keygen", "-t", "ed25519", "-C", comment,
         "-f", str(key_path), "-N", ""])
    key_path.chmod(0o600)
    success(f"Created {key_path}")

# ---------------------------------------------------------------------------
# SSH config management
# ---------------------------------------------------------------------------

def ensure_ssh_config_block(alias, hostname, key_path):
    """Append the SSH host block only if it is not already present."""
    existing = SSH_CONFIG.read_text() if SSH_CONFIG.exists() else ""
    if f"Host {alias}" in existing:
        info(f"SSH config block already present for '{alias}'")
        return
    block = (
        f"\nHost {alias}\n"
        f"    HostName {hostname}\n"
        f"    User git\n"
        f"    IdentityFile {key_path}\n"
        f"    AddKeysToAgent yes\n"
        f"    UseKeychain yes\n"
        f"    IdentitiesOnly yes\n"
    )
    with SSH_CONFIG.open("a") as f:
        f.write(block)
    SSH_CONFIG.chmod(0o600)
    success(f"Added SSH config: '{alias}' → {hostname}")

# ---------------------------------------------------------------------------
# ssh-agent / Keychain
# ---------------------------------------------------------------------------

def add_key_to_agent(key_path):
    info(f"Adding {key_path.name} to ssh-agent …")
    r = run(["ssh-add", "--apple-use-keychain", str(key_path)],
            check=False, capture=True)
    if r.returncode == 0:
        success("Added via macOS Keychain")
        return
    r = run(["ssh-add", str(key_path)], check=False, capture=True)
    if r.returncode == 0:
        success("Added (plain ssh-add)")
    else:
        warn(f"Could not add {key_path.name}: {r.stderr.strip()}")
        warn(f"Add manually: ssh-add {key_path}")

# ---------------------------------------------------------------------------
# Apply identity to repo
# ---------------------------------------------------------------------------

def _apply_identity(remote_url, name, email):
    current = get_remote_url()
    if current:
        run(["git", "remote", "set-url", "origin", remote_url])
    else:
        run(["git", "remote", "add", "origin", remote_url])
    run(["git", "config", "user.name",  name])
    run(["git", "config", "user.email", email])

# ---------------------------------------------------------------------------
# Subcommand: setup
# ---------------------------------------------------------------------------

def cmd_setup(args):
    """Generate keys, write SSH config, add to agent, print public keys."""
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

    print("\n=== Public keys — add these to your Git hosts ===\n")
    print(f"-- Personal  ({personal_host}) --")
    print(PERSONAL_KEY.with_suffix(".pub").read_text().strip())
    print()
    print(f"-- Work  ({work_host}) --")
    print(WORK_KEY.with_suffix(".pub").read_text().strip())
    print()
    success("Setup complete.")

# ---------------------------------------------------------------------------
# Subcommand: swap  (called by the gitSwap shell command)
# ---------------------------------------------------------------------------

def _detect_current_profile(config) -> str | None:
    """
    Figure out which identity is currently active in this repo.
    Checks (in order):
      1. SSH alias in remote URL  (git-personal / git-work)
      2. repo-local user.email    matched against stored emails
      3. hostname in remote URL   matched against stored hosts
    Returns "personal", "work", or None if unknown.
    """
    url = get_remote_url() or ""

    # 1. SSH aliases — most reliable indicator after first swap
    if PERSONAL_HOST_ALIAS in url:
        return "personal"
    if WORK_HOST_ALIAS in url:
        return "work"

    # 2. repo-local user.email
    r = run(["git", "config", "--local", "user.email"], check=False, capture=True)
    local_email = r.stdout.strip()
    if local_email:
        if local_email == config.get("personal", {}).get("email", ""):
            return "personal"
        if local_email == config.get("work", {}).get("email", ""):
            return "work"

    # 3. hostname anywhere in the remote URL
    p_host = config.get("personal", {}).get("host", "")
    w_host = config.get("work", {}).get("host", "")
    if p_host and p_host in url:
        return "personal"
    if w_host and w_host in url:
        return "work"

    return None


def cmd_swap(args):
    """Switch the current repo to personal or work identity. Toggles if no arg."""
    require_git_repo()
    config = load_config()
    profile = getattr(args, "profile", None)

    if not profile:
        current = _detect_current_profile(config)
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

    repo = infer_repo_name()

    if profile == "personal":
        p = config["personal"]
        new_url = f"git@{PERSONAL_HOST_ALIAS}:{p['path']}/{repo}.git"
        _apply_identity(new_url, p["name"], p["email"])
        print(f"\n  Switched to personal identity  ({p['host']})")
        success(f"email  : {p['email']}")
        success(f"remote : {new_url}\n")

    elif profile == "work":
        w = config["work"]
        new_url = f"git@{WORK_HOST_ALIAS}:{w['path']}/{repo}.git"
        _apply_identity(new_url, w["name"], w["email"])
        print(f"\n  Switched to work identity  ({w['host']})")
        success(f"email  : {w['email']}")
        success(f"remote : {new_url}\n")

    else:
        die(f"Unknown profile '{profile}'. Use 'work' or 'personal'.")

# ---------------------------------------------------------------------------
# Subcommand: use-personal / use-work
# ---------------------------------------------------------------------------

def cmd_use_personal(args):
    require_git_repo()
    config = load_config()
    p = config["personal"]
    repo = args.repo or infer_repo_name() or die("Pass --repo REPO_NAME")
    path = args.path or p.get("path") or die("Pass --path USERNAME_OR_GROUP")
    new_url = f"git@{PERSONAL_HOST_ALIAS}:{path}/{repo}.git"
    current = get_remote_url()
    if current:
        run(["git", "remote", "set-url", "origin", new_url])
        success(f"Updated origin → {new_url}")
    else:
        run(["git", "remote", "add", "origin", new_url])
        success(f"Added origin: {new_url}")

def cmd_use_work(args):
    require_git_repo()
    config = load_config()
    w = config["work"]
    repo = args.repo or infer_repo_name() or die("Pass --repo REPO_NAME")
    path = args.path or w.get("path") or die("Pass --path USERNAME_OR_GROUP")
    new_url = f"git@{WORK_HOST_ALIAS}:{path}/{repo}.git"
    current = get_remote_url()
    if current:
        run(["git", "remote", "set-url", "origin", new_url])
        success(f"Updated origin → {new_url}")
    else:
        run(["git", "remote", "add", "origin", new_url])
        success(f"Added origin: {new_url}")

# ---------------------------------------------------------------------------
# Subcommand: set-identity
# ---------------------------------------------------------------------------

def cmd_set_identity(args):
    require_git_repo()
    print("\n=== Setting repo-local git identity ===\n")
    run(["git", "config", "user.name",  args.name])
    run(["git", "config", "user.email", args.email])
    success(f"user.name  = {args.name}")
    success(f"user.email = {args.email}")
    info("Local to this repo only.")

# ---------------------------------------------------------------------------
# Subcommand: show-remote
# ---------------------------------------------------------------------------

def cmd_show_remote(args):
    require_git_repo()
    print("\n=== Remotes ===\n")
    r = run(["git", "remote", "-v"], check=False, capture=True)
    print(r.stdout.strip() or "  (none)")
    print("\n=== Repo-local identity ===\n")
    for key in ("user.name", "user.email"):
        r = run(["git", "config", "--local", key], check=False, capture=True)
        print(f"  {key} = {r.stdout.strip() or '(not set locally)'}")
    print()

# ---------------------------------------------------------------------------
# Subcommand: test-personal / test-work
# ---------------------------------------------------------------------------

def _test_ssh(alias, label):
    print(f"\n=== Testing SSH: {alias} ({label}) ===\n")
    info(f"Running: ssh -T git@{alias}")
    r = run(["ssh", "-T", f"git@{alias}"], check=False, capture=True)
    output = (r.stdout + r.stderr).strip()
    print(f"  {output}")
    if any(w in output.lower() for w in ("authenticated", "welcome", "logged in")):
        success("SSH authentication succeeded!")
    else:
        warn("No success greeting. Make sure the public key is added to your account.")
    print()

def cmd_test_personal(args): _test_ssh(PERSONAL_HOST_ALIAS, "personal")
def cmd_test_work(args):     _test_ssh(WORK_HOST_ALIAS,     "work")

# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="git_identity_switcher.py",
        description="Manage two Git SSH identities (personal + work) on macOS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # First-time setup
  python3 git_identity_switcher.py setup
  python3 git_identity_switcher.py setup --personal-host github.com --work-host gitlab.yourco.com

  # Toggle / force identity in current repo
  gitSwap
  gitSwap work
  gitSwap personal

  # Set repo-local identity manually
  python3 git_identity_switcher.py set-identity --name "Ada" --email "ada@co.com"

  # Inspect current repo
  python3 git_identity_switcher.py show-remote

  # Test SSH connectivity
  python3 git_identity_switcher.py test-personal
  python3 git_identity_switcher.py test-work
""",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # setup
    p_setup = sub.add_parser("setup", help="Generate SSH keys and update ~/.ssh/config.")
    p_setup.add_argument("--personal-host", metavar="HOST", default="github.com",
                         help="Hostname for personal identity (default: github.com).")
    p_setup.add_argument("--work-host",     metavar="HOST", default="gitlab.com",
                         help="Hostname for work identity (default: gitlab.com).")

    # swap
    p_swap = sub.add_parser("swap", help="Switch identity in current repo (used by gitSwap).")
    p_swap.add_argument("profile", nargs="?", choices=["personal", "work"],
                        help="Identity to switch to. Omit to toggle.")

    # use-personal
    p_up = sub.add_parser("use-personal", help="Set origin to personal identity.")
    p_up.add_argument("--path", metavar="USER_OR_PATH",
                      help="Username or group path (defaults to value saved during setup).")
    p_up.add_argument("--repo", metavar="REPO_NAME",
                      help="Repo name (inferred from existing remote if omitted).")

    # use-work
    p_uw = sub.add_parser("use-work", help="Set origin to work identity.")
    p_uw.add_argument("--path", metavar="USER_OR_PATH",
                      help="Username or group path (defaults to value saved during setup).")
    p_uw.add_argument("--repo", metavar="REPO_NAME",
                      help="Repo name (inferred from existing remote if omitted).")

    # set-identity
    p_id = sub.add_parser("set-identity", help="Set repo-local user.name and user.email.")
    p_id.add_argument("--name",  required=True)
    p_id.add_argument("--email", required=True)

    # show-remote
    sub.add_parser("show-remote", help="Print current remotes and local identity.")

    # test-personal / test-work
    sub.add_parser("test-personal", help="Run ssh -T git@git-personal.")
    sub.add_parser("test-work",     help="Run ssh -T git@git-work.")

    return parser

COMMAND_MAP = {
    "setup":        cmd_setup,
    "swap":         cmd_swap,
    "use-personal": cmd_use_personal,
    "use-work":     cmd_use_work,
    "set-identity": cmd_set_identity,
    "show-remote":  cmd_show_remote,
    "test-personal": cmd_test_personal,
    "test-work":    cmd_test_work,
}

def main():
    parser = build_parser()
    args = parser.parse_args()
    handler = COMMAND_MAP.get(args.command)
    if not handler:
        parser.print_help()
        sys.exit(1)
    try:
        handler(args)
    except subprocess.CalledProcessError as exc:
        die(f"Command failed: {' '.join(exc.cmd)}\n  {exc.stderr or exc.stdout or ''}")
    except KeyboardInterrupt:
        print()
        sys.exit(130)

if __name__ == "__main__":
    main()

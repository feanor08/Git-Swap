"""
gitswap/ssh.py
--------------
SSH key generation, ~/.ssh/config management, and ssh-agent integration.

All public functions are idempotent — they check current state before acting
and are safe to call multiple times (e.g., re-running setup).

macOS-specific notes:
  - UseKeychain yes  stores the key passphrase in the macOS Keychain so you
    are not prompted on every use.
  - ssh-add --apple-use-keychain  is the modern equivalent of the old -K flag
    (renamed in macOS 12 Monterey).  We fall back to plain ssh-add if the flag
    is not recognised (e.g., Linux CI, older macOS).
  - IdentitiesOnly yes  prevents SSH from offering keys from the agent that
    were not explicitly listed for this host, which avoids "too many auth
    failures" errors on servers that limit authentication attempts.
"""

from pathlib import Path

from gitswap.constants import SSH_DIR, SSH_CONFIG
from gitswap.utils import run, info, success, warn


def ensure_ssh_dir() -> None:
    """Create ~/.ssh with the correct permissions (700) if it does not exist."""
    SSH_DIR.mkdir(mode=0o700, exist_ok=True)


def generate_key(key_path: Path, comment: str) -> None:
    """
    Generate an ed25519 SSH key pair at `key_path` if one does not exist yet.

    The key is created without a passphrase for automation convenience.  Users
    who want a passphrase can add one afterwards with:
        ssh-keygen -p -f ~/.ssh/id_ed25519_personal
    """
    if key_path.exists():
        info(f"SSH key already exists: {key_path}")
        return

    info(f"Generating SSH key: {key_path}")
    run([
        "ssh-keygen",
        "-t", "ed25519",
        "-C", comment,       # label shown in authorized_keys on the server
        "-f", str(key_path),
        "-N", "",            # empty passphrase
    ])
    key_path.chmod(0o600)    # private key must not be world-readable
    success(f"Created {key_path}")


def ensure_ssh_config_block(alias: str, hostname: str, key_path: Path) -> None:
    """
    Append a Host block to ~/.ssh/config for `alias` if one does not exist.

    The block maps the alias to the real hostname and pins the identity file,
    so SSH always uses the right key regardless of what the agent offers.

    Example block written:
        Host git-personal
            HostName github.com
            User git
            IdentityFile ~/.ssh/id_ed25519_personal
            AddKeysToAgent yes
            UseKeychain yes
            IdentitiesOnly yes
    """
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
    with SSH_CONFIG.open("a") as fh:
        fh.write(block)
    SSH_CONFIG.chmod(0o600)
    success(f"Added SSH config: '{alias}' → {hostname}")


def add_key_to_agent(key_path: Path) -> None:
    """
    Load the private key into ssh-agent.

    Tries --apple-use-keychain first (macOS Keychain integration) then falls
    back to plain ssh-add for compatibility with non-macOS environments.
    """
    info(f"Adding {key_path.name} to ssh-agent …")

    # Preferred: store passphrase in macOS Keychain (no prompt on reboot)
    r = run(
        ["ssh-add", "--apple-use-keychain", str(key_path)],
        check=False,
        capture=True,
    )
    if r.returncode == 0:
        success("Added via macOS Keychain")
        return

    # Fallback: plain ssh-add (still loads the key, just no Keychain storage)
    r = run(["ssh-add", str(key_path)], check=False, capture=True)
    if r.returncode == 0:
        success("Added to agent (plain ssh-add, no Keychain)")
    else:
        warn(f"Could not add {key_path.name} to ssh-agent: {r.stderr.strip()}")
        warn(f"Add manually with:  ssh-add {key_path}")

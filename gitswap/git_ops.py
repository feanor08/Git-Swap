"""
gitswap/git_ops.py
------------------
Low-level git operations: repo detection, remote URL management, and local
identity (user.name / user.email).

Design constraints:
  - None of these functions touch ~/.gitconfig (global config).  All identity
    changes are written to .git/config of the current repo only.
  - Functions call die() rather than raising exceptions so CLI error messages
    are consistent across the codebase.
  - This module has no knowledge of identity profiles or SSH aliases — it only
    speaks raw git commands.  Profile logic lives in swap.py.
"""

from __future__ import annotations

from pathlib import Path

from gitswap.utils import run, die


def require_git_repo() -> Path:
    """
    Return the absolute path of the current repo root.
    Exits with a helpful error if the working directory is not inside a git repo.
    """
    r = run(["git", "rev-parse", "--show-toplevel"], check=False, capture=True)
    if r.returncode != 0:
        die("Not inside a git repository.  cd into one first.")
    return Path(r.stdout.strip())


def get_remote_url(remote: str = "origin") -> str | None:
    """Return the current URL for `remote`, or None if the remote is not set."""
    r = run(["git", "remote", "get-url", remote], check=False, capture=True)
    return r.stdout.strip() if r.returncode == 0 else None


def get_local_email() -> str | None:
    """
    Return the repo-local user.email value, or None if not set.
    Only reads from .git/config — never the global config.
    """
    r = run(["git", "config", "--local", "user.email"], check=False, capture=True)
    return r.stdout.strip() or None


def infer_repo_name() -> str:
    """
    Guess the repository name from the current remote URL or the directory name.

    Priority:
      1. Last path segment of the current origin URL (strips .git suffix).
         Works for both SSH  (git@host:group/repo.git)
                    and HTTPS (https://host/group/repo.git).
      2. Name of the current working directory (fallback for repos with no remote).
    """
    url = get_remote_url()
    if url:
        return Path(url.rstrip("/").split("/")[-1]).stem
    return Path.cwd().name


def set_remote_url(url: str, remote: str = "origin") -> None:
    """
    Point `remote` at `url`.  Creates the remote if it does not exist yet;
    updates it in-place if it does.
    """
    if get_remote_url(remote):
        run(["git", "remote", "set-url", remote, url])
    else:
        run(["git", "remote", "add", remote, url])


def set_local_identity(name: str, email: str) -> None:
    """
    Write user.name and user.email to .git/config.
    These settings are local to the current repo and never affect other repos
    or the global ~/.gitconfig.
    """
    run(["git", "config", "user.name",  name])
    run(["git", "config", "user.email", email])

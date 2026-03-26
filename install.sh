#!/bin/bash
# install.sh — one-command installer for Git-Swap
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/feanor08/Git-Swap/main/install.sh | bash
#
# What it does:
#   1. Checks for Python 3 and git
#   2. Clones (or updates) the repo to ~/.git-swap
#   3. Opens the Git-Swap UI so you can complete setup

set -euo pipefail

REPO_URL="https://github.com/feanor08/Git-Swap.git"
INSTALL_DIR="$HOME/.git-swap"

# ── Colour helpers ────────────────────────────────────────────────────────────
green()  { printf '\033[32m  [ok]  %s\033[0m\n' "$*"; }
info()   { printf '\033[34m  [..]  %s\033[0m\n' "$*"; }
warn()   { printf '\033[33m  [!!]  %s\033[0m\n' "$*" >&2; }
die()    { printf '\033[31m  [XX]  %s\033[0m\n' "$*" >&2; exit 1; }

# ── Preflight checks ──────────────────────────────────────────────────────────
printf '\n  Git-Swap Installer\n  ==================\n\n'

command -v python3 &>/dev/null \
    || die "Python 3 not found. Install from https://python.org or: brew install python3"

command -v git &>/dev/null \
    || die "git not found. Install Xcode Command Line Tools: xcode-select --install"

PY_VER=$(python3 -c 'import sys; print(sys.version_info[:2] >= (3,9))')
[ "$PY_VER" = "True" ] \
    || die "Python 3.9+ is required. Found: $(python3 --version)"

green "Python $(python3 --version | cut -d' ' -f2) found"

# ── Clone or update ───────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    info "Updating existing installation at $INSTALL_DIR …"
    git -C "$INSTALL_DIR" pull --ff-only \
        || warn "Could not pull latest — continuing with existing version"
else
    info "Cloning Git-Swap to $INSTALL_DIR …"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

green "Repo ready at $INSTALL_DIR"

# ── Launch UI ─────────────────────────────────────────────────────────────────
printf '\n'
info "Opening the setup UI…"
info "Fill in your identities and click Run Setup."
printf '\n'

python3 "$INSTALL_DIR/git_identity_ui.py"

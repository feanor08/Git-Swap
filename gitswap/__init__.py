"""
gitswap
-------
Platform-agnostic dual Git identity manager for macOS.

Supports GitHub, GitLab, Bitbucket, and any self-hosted Git service.

Usage (CLI):
    python3 git_identity_switcher.py setup
    gitSwap            # toggle between identities
    gitSwap work       # force work identity
    gitSwap personal   # force personal identity

Usage (UI):
    python3 git_identity_ui.py
    -- or --
    Double-click "Git Identity Switcher.command" in Finder
"""

__version__ = "1.0.0"
__author__  = "feanor08"
__repo__    = "https://github.com/feanor08/Git-Swap"

__all__ = ["__version__"]

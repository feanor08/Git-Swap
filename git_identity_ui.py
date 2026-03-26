#!/usr/bin/env python3
"""
git_identity_ui.py
------------------
GUI entry point for Git-Swap.

All logic lives in the gitswap package.  This file exists so the tool can be
launched as:
    python3 git_identity_ui.py
and so the "Git Identity Switcher.command" Finder launcher has a stable target.

See gitswap/ui/app.py for the full UI implementation.
"""

import sys
from pathlib import Path

# Make the repo root importable as a package regardless of where the script
# is invoked from.
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from gitswap.ui.app import main

if __name__ == "__main__":
    main()

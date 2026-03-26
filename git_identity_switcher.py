#!/usr/bin/env python3
"""
git_identity_switcher.py
------------------------
CLI entry point for Git-Swap.

All logic lives in the gitswap package.  This file exists so the tool can be
invoked as:
    python3 git_identity_switcher.py <subcommand>
and so the gitSwap shell script (installed during setup) has a stable target.

See gitswap/cli.py for the full list of subcommands and their documentation.
"""

import sys
from pathlib import Path

# Make the repo root importable as a package regardless of where the script
# is invoked from.
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from gitswap.cli import main

if __name__ == "__main__":
    main()

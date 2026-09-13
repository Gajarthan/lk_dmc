"""Compatibility entry point for dataset README generation."""

import sys

from dmc.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["readme", *sys.argv[1:]]))

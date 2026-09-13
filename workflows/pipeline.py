"""Compatibility entry point: pipeline.py DATASET [SECONDS] [options]."""

import sys

from dmc.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["scrape", *sys.argv[1:]]))

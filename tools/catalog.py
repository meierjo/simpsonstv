#!/usr/bin/env python3
"""Audit a local Simpsons episode directory without modifying it."""

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.catalog import format_report, scan_library  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(
        description="Read-only audit of Simpsons episodes from seasons 1-10."
    )
    parser.add_argument(
        "library",
        nargs="?",
        default=REPOSITORY_ROOT / "videos",
        type=Path,
        help="directory containing episode videos (default: repository videos folder)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit with status 1 when the library is incomplete or has anomalies",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        report = scan_library(args.library)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    print(format_report(report))
    if args.strict and not report.is_complete:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())


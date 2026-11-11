#!/usr/bin/env python3
"""Safely migrate an existing library to canonical episode filenames."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.catalog import scan_library  # noqa: E402
from tv.channels import load_episode_metadata  # noqa: E402
from tv.naming import canonical_episode_filename  # noqa: E402


@dataclass(frozen=True)
class Rename:
    source: Path
    destination: Path


def build_rename_plan(library, metadata):
    """Build and validate a rename plan without changing any files."""
    report = scan_library(library)
    if report.duplicate_ids or report.unexpected_ids or report.unrecognized_paths:
        raise ValueError(
            "Library has duplicate, unexpected, or unrecognized videos; "
            "run tools/catalog.py and resolve them before renaming"
        )

    plan = []
    destinations = set()
    for episode in report.episodes:
        filename = canonical_episode_filename(episode.path, metadata)
        destination = episode.path.with_name(filename)
        if destination == episode.path:
            continue
        if destination in destinations:
            raise ValueError("Multiple files would become %s" % destination)
        if destination.exists() and not os.path.samefile(episode.path, destination):
            raise ValueError("Destination already exists: %s" % destination)
        destinations.add(destination)
        plan.append(Rename(episode.path, destination))
    return tuple(plan)


def apply_rename_plan(plan):
    """Apply a previously validated rename plan."""
    for rename in plan:
        rename.source.rename(rename.destination)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Rename episode videos to 'SxxExx - Title.mp4'."
    )
    parser.add_argument("library", type=Path, help="directory containing episode videos")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the renames (the default is a read-only preview)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        metadata = load_episode_metadata(REPOSITORY_ROOT / "config" / "episodes.json")
        plan = build_rename_plan(args.library, metadata)
    except ValueError as error:
        print("Cannot rename library: %s" % error, file=sys.stderr)
        return 2

    for rename in plan:
        print("%s  ->  %s" % (rename.source.name, rename.destination.name))

    if not plan:
        print("All episode filenames are already canonical.")
    elif args.apply:
        apply_rename_plan(plan)
        print("Renamed %d episode files." % len(plan))
    else:
        print("Preview only: %d files would be renamed." % len(plan))
        print("Run again with --apply to perform these changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


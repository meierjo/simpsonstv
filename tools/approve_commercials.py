#!/usr/bin/env python3
"""Promote visually reviewed commercial manifests for player use."""

import argparse
import json
from pathlib import Path
import sys

try:
    from tools.review_commercials import reset_conservative
except ImportError:  # Direct execution adds tools/, rather than the repo, to sys.path.
    from review_commercials import reset_conservative


def approve_manifests(root):
    manifest_directory = Path(root).expanduser().resolve() / "manifests"
    paths = sorted(manifest_directory.glob("*.json"))
    if not paths:
        raise ValueError("No commercial manifests found in %s" % manifest_directory)
    approved = 0
    for path in paths:
        with path.open() as manifest_file:
            manifest = json.load(manifest_file)
        clips = manifest.get("clips")
        if not isinstance(clips, list):
            raise ValueError("Invalid clips in %s" % path)
        for clip in clips:
            clip["approved"] = True
            approved += 1
        manifest["status"] = "approved"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return len(paths), approved


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Approve every clip after visually reviewing an importer output root."
    )
    parser.add_argument("root", type=Path, help="import root, such as commercials/v2")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--confirm-reviewed",
        action="store_true",
        help="approve every clip after reviewing every generated clip",
    )
    actions.add_argument(
        "--reset-conservative",
        action="store_true",
        help="keep only normal commercials and confirmed sponsor bumpers",
    )
    args = parser.parse_args(argv)
    try:
        if args.reset_conservative:
            manifests, clips = reset_conservative(args.root)
        else:
            manifests, clips = approve_manifests(args.root)
    except (OSError, ValueError) as error:
        print("Could not approve commercials: %s" % error, file=sys.stderr)
        return 1
    print("Kept %d clips across %d manifests." % (clips, manifests))
    return 0


if __name__ == "__main__":
    sys.exit(main())

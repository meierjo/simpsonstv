#!/usr/bin/env python3
"""Add or remove a commercial-break cue for one episode."""

import argparse
import json
import os
from pathlib import Path
import re
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = REPOSITORY_ROOT / "config" / "break_cues.json"
EPISODE_PATTERN = re.compile(r"^S\d{2}E\d{2}$")


def parse_time(value):
    parts = value.split(":")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        raise ValueError("Cue must be seconds, mm:ss, or hh:mm:ss")
    if len(numbers) == 1:
        seconds = numbers[0]
    elif len(numbers) == 2:
        seconds = numbers[0] * 60 + numbers[1]
    elif len(numbers) == 3:
        seconds = numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    else:
        raise ValueError("Cue must be seconds, mm:ss, or hh:mm:ss")
    if seconds <= 0:
        raise ValueError("Cue must be greater than zero")
    return round(seconds, 3)


def set_episode_cue(path, episode_id, cue=None):
    path = Path(path)
    with path.open() as cue_file:
        data = json.load(cue_file)
    episode_cues = data.setdefault("episode_cues", {})
    if cue is None:
        episode_cues.pop(episode_id, None)
    else:
        episode_cues[episode_id] = float(cue)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(str(temporary), str(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Set a post-opening commercial cue.")
    parser.add_argument("episode_id", help="normalized ID such as S05E10")
    parser.add_argument("cue", nargs="?", help="seconds, mm:ss, or hh:mm:ss")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--config", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)
    episode_id = args.episode_id.upper()
    if not EPISODE_PATTERN.match(episode_id):
        parser.error("episode ID must look like S05E10")
    if args.remove and args.cue is not None:
        parser.error("cue and --remove cannot be used together")
    if not args.remove and args.cue is None:
        parser.error("cue is required unless --remove is used")
    try:
        cue = None if args.remove else parse_time(args.cue)
        set_episode_cue(args.config, episode_id, cue)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("Could not update break cue: %s" % error, file=sys.stderr)
        return 1
    if cue is None:
        print("Removed break cue for %s." % episode_id)
    else:
        print("Set %s commercial break cue to %.1f seconds." % (episode_id, cue))
    return 0


if __name__ == "__main__":
    sys.exit(main())

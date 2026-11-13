#!/usr/bin/env python3
"""Build commercial break cues from plausible first-chapter timestamps."""

import argparse
import json
from pathlib import Path
import sys


def collect_chapter_cues(candidate_paths, minimum=10.0, maximum=180.0):
    cues = {}
    for path in candidate_paths:
        payload = json.loads(Path(path).read_text())
        for episode_id, episode in payload.get("episodes", {}).items():
            cue = episode.get("chapter_end")
            if not isinstance(cue, (int, float)) or not minimum <= cue <= maximum:
                continue
            cue = round(float(cue), 3)
            previous = cues.get(episode_id)
            if previous is not None and previous != cue:
                raise ValueError(
                    "Conflicting chapter cues for %s: %s and %s"
                    % (episode_id, previous, cue)
                )
            cues[episode_id] = cue
    return dict(sorted(cues.items()))


def build_config(candidate_paths, destination, minimum=10.0, maximum=180.0):
    cues = collect_chapter_cues(candidate_paths, minimum=minimum, maximum=maximum)
    payload = {"episode_cues": cues, "season_defaults": {}}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n")
    return len(cues)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum", type=float, default=10.0)
    parser.add_argument("--maximum", type=float, default=180.0)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        count = build_config(
            args.candidates,
            args.output,
            minimum=args.minimum,
            maximum=args.maximum,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("Cue build failed: %s" % error, file=sys.stderr)
        return 1
    print("Wrote %d chapter-based cues to %s" % (count, args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())

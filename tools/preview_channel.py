#!/usr/bin/env python3
"""Preview channel scheduling without playing or changing any media."""

import argparse
from pathlib import Path
import random
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.catalog import scan_library  # noqa: E402
from tv.channels import load_channels, load_episode_metadata  # noqa: E402
from tv.scheduler import EpisodeScheduler  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(
        description="Preview a Simpsons TV channel without playing video."
    )
    parser.add_argument("library", type=Path, help="directory containing episode videos")
    parser.add_argument(
        "--channel",
        default="springfield-tv",
        help="channel ID from config/channels.json",
    )
    parser.add_argument("--count", type=int, default=10, help="number of selections")
    parser.add_argument("--seed", type=int, default=1990, help="repeatable preview seed")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.count < 1:
        print("--count must be at least 1", file=sys.stderr)
        return 2

    try:
        report = scan_library(args.library)
        channels = load_channels(REPOSITORY_ROOT / "config" / "channels.json")
        metadata = load_episode_metadata(REPOSITORY_ROOT / "config" / "episodes.json")
        channel = channels[args.channel]
    except (KeyError, ValueError) as error:
        print("Could not preview channel: %s" % error, file=sys.stderr)
        return 2

    scheduler = EpisodeScheduler(
        report.episodes,
        metadata,
        random_source=random.Random(args.seed),
    )
    print(channel.name)
    for number in range(1, args.count + 1):
        episode = scheduler.choose_next(channel)
        print("%2d. %s - %s" % (number, episode.episode_id, episode.title))
    return 0


if __name__ == "__main__":
    sys.exit(main())


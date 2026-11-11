#!/usr/bin/env python3
"""Select the channel used for the next episode."""

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.channels import load_channels  # noqa: E402
from tv.state import StateStore  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(description="Select a Simpsons TV channel.")
    parser.add_argument("channel", nargs="?", help="channel ID to select")
    parser.add_argument(
        "--list", action="store_true", help="list channels without changing state"
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    channels = load_channels(REPOSITORY_ROOT / "config" / "channels.json")
    if args.list or not args.channel:
        for channel in channels.values():
            print("%-24s %s" % (channel.channel_id, channel.name))
        return 0

    channel = channels.get(args.channel)
    if channel is None:
        print("Unknown channel: %s" % args.channel, file=sys.stderr)
        print("Use --list to see valid channel IDs.", file=sys.stderr)
        return 2

    store = StateStore(REPOSITORY_ROOT / "runtime" / "state.json")
    store.set_channel(channel.channel_id)
    print("Next episode channel: %s" % channel.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())


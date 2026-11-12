#!/usr/bin/env python3
"""Run the Simpsons TV broadcast continuously."""

import json
from pathlib import Path
import sys
import time

from tv.catalog import scan_library
from tv.channels import load_channels, load_episode_metadata
from tv.commercials import CommercialScheduler, load_approved_clips, load_broadcast_years
from tv.playback import OmxPlayerBackend, PlaybackController
from tv.scheduler import EpisodeScheduler
from tv.state import StateStore


REPOSITORY_ROOT = Path(__file__).resolve().parent


def load_commercial_scheduler():
    """Load optional local commercials without making them a startup dependency."""
    config_path = REPOSITORY_ROOT / "config" / "commercials.json"
    try:
        with config_path.open() as config_file:
            config = json.load(config_file)
        if not config.get("enabled", True):
            return None
        root = (REPOSITORY_ROOT / config.get("root", "commercials/v2")).resolve()
        clips = load_approved_clips(root)
        if not clips:
            print("No approved commercials found in %s; episodes only" % root, flush=True)
            return None
        print("Loaded %d approved commercial clips from %s" % (len(clips), root), flush=True)
        return CommercialScheduler(
            clips,
            recent_limit=config.get("recent_limit", 12),
            include_bumpers=config.get("include_sponsor_bumpers", True),
        )
    except (OSError, ValueError, TypeError) as error:
        print("Commercial library unavailable (%s); episodes only" % error, file=sys.stderr, flush=True)
        return None


def main():
    library = REPOSITORY_ROOT / "videos"
    report = scan_library(library)
    if not report.episodes:
        print("No recognized episode videos found in %s" % library, file=sys.stderr)
        return 1

    metadata = load_episode_metadata(REPOSITORY_ROOT / "config" / "episodes.json")
    channels = load_channels(REPOSITORY_ROOT / "config" / "channels.json")
    try:
        broadcast_years = load_broadcast_years(
            REPOSITORY_ROOT / "config" / "broadcast_years.json"
        )
    except ValueError as error:
        print("Broadcast years unavailable (%s); episodes only" % error, file=sys.stderr, flush=True)
        broadcast_years = {}
    state_store = StateStore(REPOSITORY_ROOT / "runtime" / "state.json")
    initial_state = state_store.load()
    if initial_state.channel_id not in channels:
        initial_state = state_store.set_channel("springfield-tv")
    scheduler = EpisodeScheduler(
        report.episodes,
        metadata,
        recent_ids=initial_state.recent_ids,
    )
    controller = PlaybackController(
        channels=channels,
        scheduler=scheduler,
        state_store=state_store,
        backend=OmxPlayerBackend(),
        commercial_scheduler=load_commercial_scheduler(),
        episode_metadata=metadata,
        broadcast_years=broadcast_years,
    )

    print(
        "Loaded %d episodes; starting %s"
        % (report.unique_episode_count, channels[initial_state.channel_id].name),
        flush=True,
    )
    while True:
        try:
            if state_store.load().menu_open:
                time.sleep(0.1)
                continue
            episode, return_code = controller.play_next()
            if return_code:
                print(
                    "Playback failed for %s with status %s"
                    % (episode.episode_id, return_code),
                    file=sys.stderr,
                    flush=True,
                )
                time.sleep(2)
        except Exception as error:
            print("Playback error: %s" % error, file=sys.stderr, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())

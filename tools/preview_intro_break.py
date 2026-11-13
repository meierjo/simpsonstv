#!/usr/bin/env python3
"""Play one deterministic opening-commercial-resume pilot on the Pi."""

import argparse
import json
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.breaks import break_cue_for_episode, load_break_cues  # noqa: E402
from tv.catalog import scan_library  # noqa: E402
from tv.channels import load_episode_metadata  # noqa: E402
from tv.commercials import (  # noqa: E402
    CommercialScheduler,
    broadcast_year_for_episode,
    load_approved_clips,
    load_broadcast_years,
)
from tv.playback import OmxPlayerBackend  # noqa: E402


def find_episode(library, episode_id):
    report = scan_library(library)
    matches = [episode for episode in report.episodes if episode.episode_id == episode_id]
    if len(matches) != 1:
        raise ValueError("Expected one %s video in %s; found %d" % (episode_id, library, len(matches)))
    return matches[0]


def build_pilot(episode_id, repository_root=REPOSITORY_ROOT):
    repository_root = Path(repository_root)
    episode = find_episode(repository_root / "videos", episode_id)
    metadata = load_episode_metadata(repository_root / "config" / "episodes.json")
    broadcast_years = load_broadcast_years(repository_root / "config" / "broadcast_years.json")
    break_cues = load_break_cues(repository_root / "config" / "break_cues.json")
    cue = break_cue_for_episode(episode, break_cues)
    if cue is None:
        raise ValueError("%s has no reviewed intro cue" % episode_id)

    with (repository_root / "config" / "commercials.json").open() as config_file:
        commercial_config = json.load(config_file)
    commercial_root = repository_root / commercial_config.get("root", "commercials/v2")
    scheduler = CommercialScheduler(
        load_approved_clips(commercial_root),
        recent_limit=commercial_config.get("recent_limit", 12),
        include_bumpers=commercial_config.get("include_sponsor_bumpers", True),
    )
    year = broadcast_year_for_episode(episode, metadata, broadcast_years)
    preroll = scheduler.choose_preroll(year)
    if not preroll:
        raise ValueError("No approved %d commercial is available" % year)
    return episode, cue, preroll


def run(args):
    episode, cue, preroll = build_pilot(args.episode_id.upper())
    backend = OmxPlayerBackend()
    print("Pilot opening: %s to %.3f seconds" % (episode.episode_id, cue), flush=True)
    return_code = backend.play(episode, stop_after=cue)
    if return_code:
        return return_code
    for clip in preroll:
        print("Pilot %s: %s" % (clip.kind, clip.path.name), flush=True)
        return_code = backend.play(clip)
        if return_code:
            print("Pilot preroll failed with status %s; continuing" % return_code, flush=True)
    print("Pilot resume: %s at %.3f seconds" % (episode.episode_id, cue), flush=True)
    return backend.play(episode, start_at=cue, stop_after=args.resume_seconds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("episode_id", help="reviewed episode ID, such as S05E10")
    parser.add_argument(
        "--resume-seconds",
        type=float,
        default=15.0,
        help="seconds of resumed episode to play before exiting (default: 15)",
    )
    args = parser.parse_args(argv)
    if args.resume_seconds <= 0:
        parser.error("--resume-seconds must be greater than zero")
    try:
        return run(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("Intro-break pilot failed: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

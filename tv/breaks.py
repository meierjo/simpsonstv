"""Optional episode cue points for placing commercials after the opening."""

import json
from pathlib import Path


def load_break_cues(path):
    path = Path(path)
    try:
        with path.open() as cue_file:
            data = json.load(cue_file)
    except (OSError, ValueError) as error:
        raise ValueError("Could not load break cues from %s: %s" % (path, error))
    episode_cues = data.get("episode_cues", {})
    season_defaults = data.get("season_defaults", {})
    if not isinstance(episode_cues, dict) or not isinstance(season_defaults, dict):
        raise ValueError("Break cues must contain episode_cues and season_defaults objects")
    return {
        "episode_cues": {str(key): float(value) for key, value in episode_cues.items()},
        "season_defaults": {int(key): float(value) for key, value in season_defaults.items()},
    }


def break_cue_for_episode(episode, cues):
    """Return a verified episode cue, a season fallback, or ``None``."""
    cue = cues.get("episode_cues", {}).get(episode.episode_id)
    if cue is None:
        cue = cues.get("season_defaults", {}).get(episode.season)
    if cue is None:
        return None
    cue = float(cue)
    return cue if cue > 0 else None


def format_omx_position(seconds):
    """Format seconds as the documented OMXPlayer ``hh:mm:ss`` position."""
    total_seconds = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)

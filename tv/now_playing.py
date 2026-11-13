"""Atomic current-program metadata shared with the touch overlay."""

import json
import os
from pathlib import Path
import tempfile


class NowPlayingStore:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, episode, channel, air_year=None):
        payload = {
            "episode_id": episode.episode_id,
            "episode": episode.episode,
            "season": episode.season,
            "title": episode.title,
            "channel_id": channel.channel_id,
            "channel_name": channel.name,
            "air_year": air_year,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="now-playing-", suffix=".json", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(descriptor, "w") as temporary_file:
                json.dump(payload, temporary_file, indent=2, sort_keys=True)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, str(self.path))
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
        return payload

    def load(self):
        try:
            with self.path.open() as metadata_file:
                payload = json.load(metadata_file)
            if not isinstance(payload, dict) or not payload.get("episode_id"):
                return None
            return payload
        except (OSError, ValueError):
            return None

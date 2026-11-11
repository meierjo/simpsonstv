"""Small atomic state file shared by playback and future touch controls."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile


DEFAULT_CHANNEL_ID = "springfield-tv"


@dataclass(frozen=True)
class PlayerState:
    channel_id: str = DEFAULT_CHANNEL_ID
    recent_ids: tuple = ()


class StateStore:
    """Read and atomically replace persistent player state."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.is_file():
            return PlayerState()
        try:
            with self.path.open() as state_file:
                data = json.load(state_file)
            channel_id = data.get("channel", DEFAULT_CHANNEL_ID)
            recent_ids = data.get("recent", [])
            if not isinstance(channel_id, str) or not isinstance(recent_ids, list):
                raise ValueError("invalid state values")
            return PlayerState(channel_id, tuple(recent_ids))
        except (OSError, ValueError):
            # State is convenience, not media. A partial write or manual edit
            # must never keep the television off the air.
            return PlayerState()

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="state-", suffix=".json", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(descriptor, "w") as temporary_file:
                json.dump(
                    {"channel": state.channel_id, "recent": list(state.recent_ids)},
                    temporary_file,
                    indent=2,
                    sort_keys=True,
                )
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

    def set_channel(self, channel_id):
        state = self.load()
        updated = PlayerState(channel_id=channel_id, recent_ids=state.recent_ids)
        self.save(updated)
        return updated


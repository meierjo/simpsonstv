"""Small atomic state file shared by playback and future touch controls."""

from dataclasses import dataclass
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import tempfile


DEFAULT_CHANNEL_ID = "springfield-tv"


@dataclass(frozen=True)
class PlayerState:
    channel_id: str = DEFAULT_CHANNEL_ID
    recent_ids: tuple = ()
    menu_open: bool = False


class StateStore:
    """Read and atomically replace persistent player state."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        with self._lock(exclusive=False):
            return self._load_unlocked()

    def _load_unlocked(self):
        if not self.path.is_file():
            return PlayerState()
        try:
            with self.path.open() as state_file:
                data = json.load(state_file)
            channel_id = data.get("channel", DEFAULT_CHANNEL_ID)
            recent_ids = data.get("recent", [])
            menu_open = data.get("menu_open", False)
            if (
                not isinstance(channel_id, str)
                or not isinstance(recent_ids, list)
                or not isinstance(menu_open, bool)
            ):
                raise ValueError("invalid state values")
            return PlayerState(channel_id, tuple(recent_ids), menu_open)
        except (OSError, ValueError):
            # State is convenience, not media. A partial write or manual edit
            # must never keep the television off the air.
            return PlayerState()

    def save(self, state):
        with self._lock(exclusive=True):
            self._save_unlocked(state)

    def _save_unlocked(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix="state-", suffix=".json", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(descriptor, "w") as temporary_file:
                json.dump(
                    {
                        "channel": state.channel_id,
                        "menu_open": state.menu_open,
                        "recent": list(state.recent_ids),
                    },
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

    @contextmanager
    def _lock(self, exclusive):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(self.path.suffix + ".lock").open("a+") as lock_file:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_file.fileno(), operation)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _update(self, channel_id=None, recent_ids=None, menu_open=None):
        with self._lock(exclusive=True):
            state = self._load_unlocked()
            updated = PlayerState(
                channel_id=state.channel_id if channel_id is None else channel_id,
                recent_ids=state.recent_ids if recent_ids is None else tuple(recent_ids),
                menu_open=state.menu_open if menu_open is None else bool(menu_open),
            )
            self._save_unlocked(updated)
            return updated

    def set_channel(self, channel_id):
        return self._update(channel_id=channel_id)

    def set_menu_open(self, menu_open):
        return self._update(menu_open=menu_open)

    def set_recent_ids(self, recent_ids):
        """Update playback history without overwriting touch-owned state."""
        return self._update(recent_ids=recent_ids)


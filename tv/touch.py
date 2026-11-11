"""Hardware-independent touch gestures and channel actions."""

from tv.state import DEFAULT_CHANNEL_ID


TREEHOUSE_CHANNEL_ID = "treehouse-after-dark"


class ThreeFingerHoldDetector:
    """Trigger once when at least three contacts remain down long enough."""

    def __init__(self, hold_seconds=2.0, finger_count=3):
        self.hold_seconds = hold_seconds
        self.finger_count = finger_count
        self._started_at = None
        self._triggered = False

    def update(self, active_count, timestamp):
        if active_count < self.finger_count:
            self._started_at = None
            self._triggered = False
            return False

        if self._started_at is None:
            self._started_at = timestamp
            return False

        if not self._triggered and timestamp - self._started_at >= self.hold_seconds:
            self._triggered = True
            return True
        return False


def toggle_treehouse_channel(state_store):
    """Toggle between normal television and Treehouse After Dark."""
    state = state_store.load()
    if state.channel_id == TREEHOUSE_CHANNEL_ID:
        channel_id = DEFAULT_CHANNEL_ID
    else:
        channel_id = TREEHOUSE_CHANNEL_ID
    state_store.set_channel(channel_id)
    return channel_id


"""Hardware-independent touch gestures and channel actions."""

from tv.state import DEFAULT_CHANNEL_ID


TREEHOUSE_CHANNEL_ID = "treehouse-after-dark"


class HoldDetector:
    """Trigger once when the requested contacts remain down long enough."""

    def __init__(self, hold_seconds=2.0, finger_count=1):
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


class ThreeFingerHoldDetector(HoldDetector):
    """Compatibility wrapper for the original prototype gesture."""

    def __init__(self, hold_seconds=2.0):
        super().__init__(hold_seconds=hold_seconds, finger_count=3)


class TouchMapper:
    """Map raw portrait touch coordinates onto the landscape display."""

    def __init__(
        self,
        x_min,
        x_max,
        y_min,
        y_max,
        width=640,
        height=480,
        rotation=90,
    ):
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.width = width
        self.height = height
        self.rotation = rotation

    def map(self, raw_x, raw_y):
        x = self._normalize(raw_x, self.x_min, self.x_max)
        y = self._normalize(raw_y, self.y_min, self.y_max)
        if self.rotation == 0:
            screen_x, screen_y = x, y
        elif self.rotation == 90:
            screen_x, screen_y = y, 1.0 - x
        elif self.rotation == 180:
            screen_x, screen_y = 1.0 - x, 1.0 - y
        elif self.rotation == 270:
            screen_x, screen_y = 1.0 - y, x
        else:
            raise ValueError("Touch rotation must be 0, 90, 180, or 270")
        return (
            min(self.width - 1, max(0, int(screen_x * self.width))),
            min(self.height - 1, max(0, int(screen_y * self.height))),
        )

    @staticmethod
    def _normalize(value, minimum, maximum):
        if maximum == minimum:
            return 0.0
        return min(1.0, max(0.0, (value - minimum) / float(maximum - minimum)))


class MultiTouchTracker:
    """Track active Linux multi-touch slots without depending on evdev."""

    def __init__(self):
        self.current_slot = 0
        self.contacts = {}
        self.last_released_position = None

    @property
    def active_count(self):
        return len(self.contacts)

    def select_slot(self, slot):
        self.current_slot = slot

    def set_tracking_id(self, tracking_id):
        if tracking_id == -1:
            contact = self.contacts.pop(self.current_slot, None)
            if contact and contact.get("x") is not None and contact.get("y") is not None:
                self.last_released_position = (contact["x"], contact["y"])
        else:
            self.contacts[self.current_slot] = {"id": tracking_id, "x": None, "y": None}

    def set_x(self, value):
        if self.current_slot in self.contacts:
            self.contacts[self.current_slot]["x"] = value

    def set_y(self, value):
        if self.current_slot in self.contacts:
            self.contacts[self.current_slot]["y"] = value

    def take_released_position(self):
        position = self.last_released_position
        self.last_released_position = None
        return position


def toggle_treehouse_channel(state_store):
    """Toggle between normal television and Treehouse After Dark."""
    state = state_store.load()
    if state.channel_id == TREEHOUSE_CHANNEL_ID:
        channel_id = DEFAULT_CHANNEL_ID
    else:
        channel_id = TREEHOUSE_CHANNEL_ID
    state_store.set_channel(channel_id)
    return channel_id


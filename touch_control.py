#!/usr/bin/env python3
"""Listen for the hidden three-finger channel gesture."""

from pathlib import Path
import sys

from tv.state import StateStore
from tv.touch import HoldDetector, toggle_treehouse_channel


REPOSITORY_ROOT = Path(__file__).resolve().parent
TOUCH_NAME = "Goodix Capacitive TouchScreen"


def find_touch_device(evdev):
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == TOUCH_NAME or "touch" in device.name.lower():
            return device
    names = ", ".join(device.name for device in devices) or "none"
    raise RuntimeError("Touchscreen not found; input devices: %s" % names)


def run():
    try:
        import evdev
        from evdev import ecodes
    except ImportError:
        print(
            "Touch support requires python3-evdev: sudo apt-get install python3-evdev",
            file=sys.stderr,
        )
        return 2

    device = find_touch_device(evdev)
    state_store = StateStore(REPOSITORY_ROOT / "runtime" / "state.json")
    detector = HoldDetector(hold_seconds=2.0, finger_count=1)
    active_slots = set()
    current_slot = 0

    print("Listening for one-finger hold on %s (%s)" % (device.name, device.path), flush=True)
    for event in device.read_loop():
        if event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_SLOT:
            current_slot = event.value
        elif event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_TRACKING_ID:
            if event.value == -1:
                active_slots.discard(current_slot)
            else:
                active_slots.add(current_slot)
        elif event.type == ecodes.EV_SYN and event.code == ecodes.SYN_REPORT:
            if detector.update(len(active_slots), event.timestamp()):
                channel_id = toggle_treehouse_channel(state_store)
                print("Touch gesture selected channel: %s" % channel_id, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(run())


#!/usr/bin/env python3
"""Open and control the hidden touchscreen channel menu."""

import json
from pathlib import Path
import select
import signal
import sys
import time

from tv.menu import OmxChannelMenu, channel_at
from tv.state import StateStore
from tv.touch import HoldDetector, MultiTouchTracker, TouchMapper, toggle_treehouse_channel


REPOSITORY_ROOT = Path(__file__).resolve().parent
TOUCH_NAME = "Goodix Capacitive TouchScreen"
MENU_TIMEOUT_SECONDS = 10.0


def find_touch_device(evdev):
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if device.name == TOUCH_NAME or "touch" in device.name.lower():
            return device
    names = ", ".join(device.name for device in devices) or "none"
    raise RuntimeError("Touchscreen not found; input devices: %s" % names)


def build_mapper(device, ecodes):
    with (REPOSITORY_ROOT / "config" / "display.json").open() as display_file:
        display = json.load(display_file)
    x_info = get_abs_info(device, ecodes.ABS_MT_POSITION_X, ecodes)
    y_info = get_abs_info(device, ecodes.ABS_MT_POSITION_Y, ecodes)
    raw_width = x_info.max - x_info.min
    raw_height = y_info.max - y_info.min
    display_is_landscape = display["width"] >= display["height"]
    raw_is_landscape = raw_width >= raw_height
    rotation = 0 if display_is_landscape == raw_is_landscape else display["touch_rotation"]
    return TouchMapper(
        x_info.min,
        x_info.max,
        y_info.min,
        y_info.max,
        width=display["width"],
        height=display["height"],
        rotation=rotation,
    )


def get_abs_info(device, axis_code, ecodes):
    """Read axis information from both old and new python-evdev releases."""
    if hasattr(device, "absinfo"):
        return device.absinfo(axis_code)

    capabilities = device.capabilities(absinfo=True)
    for code, abs_info in capabilities.get(ecodes.EV_ABS, []):
        if code == axis_code:
            return abs_info
    raise RuntimeError("Touchscreen does not report axis %s" % axis_code)


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
    mapper = build_mapper(device, ecodes)
    state_store = StateStore(REPOSITORY_ROOT / "runtime" / "state.json")
    state_store.set_menu_open(False)
    detector = HoldDetector(hold_seconds=2.0, finger_count=1)
    tracker = MultiTouchTracker()
    menu = None
    menu_open = False
    menu_armed = False
    menu_deadline = None
    pending_released_position = None

    def stop_service(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, stop_service)
    print("Listening for one-finger hold on %s (%s)" % (device.name, device.path), flush=True)

    try:
        while True:
            readable, _, _ = select.select([device.fd], [], [], 0.1)
            if readable:
                for event in device.read():
                    released_position = _track_event(tracker, event, ecodes)
                    if released_position is not None:
                        pending_released_position = released_position
                    if event.type != ecodes.EV_SYN or event.code != ecodes.SYN_REPORT:
                        continue

                    released_position = pending_released_position
                    pending_released_position = None

                    if not menu_open:
                        if detector.update(tracker.active_count, event.timestamp()):
                            try:
                                state_store.set_menu_open(True)
                                time.sleep(0.4)
                                menu = OmxChannelMenu(REPOSITORY_ROOT / "assets")
                                menu.show(state_store.load().channel_id)
                                menu_open = True
                                menu_armed = False
                                menu_deadline = time.monotonic() + MENU_TIMEOUT_SECONDS
                                print("Channel menu opened", flush=True)
                            except Exception as error:
                                if menu is not None:
                                    menu.close()
                                    menu = None
                                state_store.set_menu_open(False)
                                channel_id = toggle_treehouse_channel(state_store)
                                print(
                                    "Menu unavailable (%s); selected channel: %s"
                                    % (error, channel_id),
                                    flush=True,
                                )
                    else:
                        if not menu_armed and tracker.active_count == 0:
                            # Ignore the release belonging to the opening hold.
                            menu_armed = True
                        elif (
                            menu_armed
                            and released_position is not None
                            and tracker.active_count == 0
                        ):
                            selected = channel_at(mapper.map(*released_position))
                            if selected is not None:
                                state_store.set_channel(selected)
                                print("Channel menu selected: %s" % selected, flush=True)
                                menu_open = _close_menu(menu, state_store)
                                menu = None
                                detector.update(0, event.timestamp())

            if menu_open and time.monotonic() >= menu_deadline:
                print("Channel menu timed out", flush=True)
                menu_open = _close_menu(menu, state_store)
                menu = None
                detector.update(0, time.time())
    except KeyboardInterrupt:
        return 0
    finally:
        if menu_open:
            _close_menu(menu, state_store)


def _track_event(tracker, event, ecodes):
    if event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_SLOT:
        tracker.select_slot(event.value)
    elif event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_TRACKING_ID:
        tracker.set_tracking_id(event.value)
    elif event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_POSITION_X:
        tracker.set_x(event.value)
    elif event.type == ecodes.EV_ABS and event.code == ecodes.ABS_MT_POSITION_Y:
        tracker.set_y(event.value)
    return tracker.take_released_position()


def _close_menu(menu, state_store):
    state_store.set_menu_open(False)
    if menu is not None:
        menu.close()
    return False


if __name__ == "__main__":
    sys.exit(run())


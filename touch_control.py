#!/usr/bin/env python3
"""Open and control the hidden touchscreen channel menu."""

import json
from pathlib import Path
import select
import signal
import sys
import time

from tv.menu import (
    OmxChannelMenu,
    OmxInfoOverlay,
    channel_at,
    page_after_swipe,
    page_for_channel,
    shutdown_at,
    swipe_returns_to_playback,
)
from tv.now_playing import NowPlayingStore
from tv.state import StateStore
from tv.touch import (
    HoldDetector,
    MultiTouchTracker,
    ReleaseGestureDetector,
    TouchMapper,
    toggle_treehouse_channel,
)


REPOSITORY_ROOT = Path(__file__).resolve().parent
TOUCH_NAME = "Goodix Capacitive TouchScreen"
MENU_TIMEOUT_SECONDS = 10.0


def load_touch_config():
    defaults = {
        "tap_slop_pixels": 24,
        "swipe_distance_pixels": 80,
        "swipe_axis_ratio": 1.5,
        "menu_hold_seconds": 2.0,
        "shutdown_hold_seconds": 1.0,
    }
    try:
        with (REPOSITORY_ROOT / "config" / "touch.json").open() as config_file:
            configured = json.load(config_file)
        defaults.update(configured)
    except (OSError, ValueError, TypeError):
        pass
    return defaults


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
    return TouchMapper(
        x_info.min,
        x_info.max,
        y_info.min,
        y_info.max,
        width=display["width"],
        height=display["height"],
        # Goodix reports a 640x480 range on this build even though its axes
        # still need the configured portrait-to-landscape transformation.
        # Axis ranges alone therefore cannot determine touch rotation.
        rotation=display["touch_rotation"],
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
    touch_config = load_touch_config()
    state_store = StateStore(REPOSITORY_ROOT / "runtime" / "state.json")
    now_playing_store = NowPlayingStore(
        REPOSITORY_ROOT / "runtime" / "now_playing.json"
    )
    state_store.set_menu_open(False)
    detector = HoldDetector(
        hold_seconds=float(touch_config["menu_hold_seconds"]), finger_count=1
    )
    shutdown_detector = HoldDetector(
        hold_seconds=float(touch_config["shutdown_hold_seconds"]), finger_count=1
    )
    gesture_detector = ReleaseGestureDetector(
        tap_slop=float(touch_config["tap_slop_pixels"]),
        swipe_distance=float(touch_config["swipe_distance_pixels"]),
        swipe_axis_ratio=float(touch_config["swipe_axis_ratio"]),
    )
    tracker = MultiTouchTracker()
    menu = None
    info_overlay = OmxInfoOverlay(
        REPOSITORY_ROOT / "assets",
        REPOSITORY_ROOT / "runtime",
    )
    menu_open = False
    menu_armed = False
    menu_page = 0
    menu_deadline = None
    pending_released_position = None
    shutdown_hold_active = False

    def stop_service(signum, frame):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, stop_service)
    print("Listening for one-finger hold on %s (%s)" % (device.name, device.path), flush=True)
    print(
        "Touch mapping: x=%s..%s y=%s..%s rotation=%s display=%sx%s"
        % (
            mapper.x_min,
            mapper.x_max,
            mapper.y_min,
            mapper.y_max,
            mapper.rotation,
            mapper.width,
            mapper.height,
        ),
        flush=True,
    )

    def open_channel_menu():
        nonlocal menu, menu_open, menu_armed, menu_page, menu_deadline
        nonlocal shutdown_hold_active
        try:
            info_overlay.close()
            state_store.set_menu_open(True)
            time.sleep(0.4)
            menu = OmxChannelMenu(REPOSITORY_ROOT / "assets")
            active_channel = state_store.load().channel_id
            menu_page = page_for_channel(active_channel)
            menu.show_buffered(active_channel, page=menu_page)
            menu_open = True
            menu_armed = False
            shutdown_hold_active = False
            gesture_detector.reset()
            menu_deadline = time.monotonic() + MENU_TIMEOUT_SECONDS
            print("Channel menu opened", flush=True)
        except Exception as error:
            gesture_detector.reset()
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
                    active_raw_position = tracker.primary_position
                    active_position = (
                        mapper.map(*active_raw_position)
                        if active_raw_position is not None
                        else None
                    )
                    mapped_released_position = (
                        mapper.map(*released_position)
                        if released_position is not None
                        else None
                    )
                    if tracker.active_count == 1 and active_position is not None:
                        gesture_detector.update(active_position, event.timestamp())
                    elif tracker.active_count > 1:
                        gesture_detector.reset()

                    if not menu_open:
                        if (
                            mapped_released_position is not None
                            and tracker.active_count == 0
                        ):
                            gesture = gesture_detector.release(
                                mapped_released_position, event.timestamp()
                            )
                            _log_gesture(gesture, "playback")
                            if (
                                gesture is not None
                                and gesture.kind == "tap"
                                and gesture.duration
                                < float(touch_config["menu_hold_seconds"])
                            ):
                                details = now_playing_store.load()
                                if details is None:
                                    print("Now-playing details unavailable", flush=True)
                                else:
                                    try:
                                        if info_overlay.show_details(details):
                                            print(
                                                "Now-playing card: %s"
                                                % details["episode_id"],
                                                flush=True,
                                            )
                                        else:
                                            print(
                                                "Now-playing card already visible",
                                                flush=True,
                                            )
                                    except Exception as error:
                                        print(
                                            "Now-playing card unavailable (%s)" % error,
                                            flush=True,
                                        )
                    else:
                        if not menu_armed and tracker.active_count == 0:
                            # Ignore the release belonging to the opening hold.
                            menu_armed = True
                            gesture_detector.reset()
                        elif (
                            menu_armed
                            and mapped_released_position is not None
                            and tracker.active_count == 0
                        ):
                            gesture = gesture_detector.release(
                                mapped_released_position, event.timestamp()
                            )
                            _log_gesture(gesture, "menu")
                            print(
                                "Touch selection: raw=%s mapped=%s"
                                % (released_position, mapped_released_position),
                                flush=True,
                            )
                            if gesture is not None and gesture.kind.startswith("swipe-"):
                                if swipe_returns_to_playback(menu_page, gesture.kind):
                                    print("Channel menu returned to playback", flush=True)
                                    menu_open = _close_menu(menu, state_store)
                                    menu = None
                                    detector.update(0, event.timestamp())
                                    shutdown_detector.update(0, event.timestamp())
                                else:
                                    next_page = page_after_swipe(menu_page, gesture.kind)
                                    if next_page != menu_page:
                                        menu_page = next_page
                                        menu.switch_buffered_page(
                                            state_store.load().channel_id, page=menu_page
                                        )
                                        print(
                                            "Channel menu page: %d" % (menu_page + 1),
                                            flush=True,
                                        )
                                    menu_deadline = time.monotonic() + MENU_TIMEOUT_SECONDS
                            elif gesture is not None and gesture.kind == "tap":
                                selected = channel_at(
                                    mapped_released_position, page=menu_page
                                )
                                if selected is not None:
                                    state_store.set_channel(selected)
                                    print(
                                        "Channel menu selected: %s" % selected,
                                        flush=True,
                                    )
                                    menu_open = _close_menu(menu, state_store)
                                    menu = None
                                    detector.update(0, event.timestamp())

            # Goodix sends no events while a finger is perfectly still. Drive
            # the hold timers from the polling clock so stationary holds still
            # fire at their configured durations.
            now = time.time()
            if not menu_open:
                if shutdown_hold_active:
                    print("Safe shutdown hold cancelled", flush=True)
                    shutdown_hold_active = False
                hold_contacts = (
                    tracker.active_count if gesture_detector.hold_eligible else 0
                )
                if detector.update(hold_contacts, now):
                    open_channel_menu()
            else:
                active_raw_position = tracker.primary_position
                active_position = (
                    mapper.map(*active_raw_position)
                    if active_raw_position is not None
                    else None
                )
                shutdown_contact = (
                    menu_armed
                    and active_position is not None
                    and shutdown_at(active_position)
                )
                shutdown_hold_eligible = (
                    shutdown_contact and gesture_detector.hold_eligible
                )
                if shutdown_hold_eligible:
                    # A deliberate shutdown hold is activity. Do not let the
                    # general menu timeout win while its timer is running.
                    menu_deadline = time.monotonic() + MENU_TIMEOUT_SECONDS
                    if not shutdown_hold_active:
                        print("Safe shutdown hold started", flush=True)
                        shutdown_hold_active = True
                elif shutdown_hold_active:
                    print("Safe shutdown hold cancelled", flush=True)
                    shutdown_hold_active = False
                if shutdown_detector.update(
                    1 if shutdown_hold_eligible else 0,
                    now,
                ):
                    print("Safe shutdown requested", flush=True)
                    shutdown_hold_active = False
                    _request_shutdown(menu, state_store)
                    menu_open = False
                    menu = None
                    detector.update(0, now)
                    continue

            if menu_open and time.monotonic() >= menu_deadline:
                print("Channel menu timed out", flush=True)
                menu_open = _close_menu(menu, state_store)
                menu = None
                detector.update(0, time.time())
                shutdown_detector.update(0, time.time())
    except KeyboardInterrupt:
        return 0
    finally:
        info_overlay.close()
        if menu_open:
            _close_menu(menu, state_store)


def _log_gesture(gesture, context):
    if gesture is None:
        return
    print(
        "Touch gesture: context=%s kind=%s duration=%.3f dx=%d dy=%d travel=%.1f"
        % (
            context,
            gesture.kind,
            gesture.duration,
            gesture.delta_x,
            gesture.delta_y,
            gesture.distance,
        ),
        flush=True,
    )


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


def _request_shutdown(menu, state_store):
    if menu is not None:
        menu.close()
    goodbye = OmxChannelMenu(REPOSITORY_ROOT / "assets")
    try:
        goodbye.show_asset("good_night_springfield.mp4")
        # OMXPlayer spends much of its startup time before drawing a frame.
        # Five seconds leaves the farewell readable for roughly three seconds.
        time.sleep(5.0)
    finally:
        goodbye.close()

    request_path = REPOSITORY_ROOT / "runtime" / "shutdown.request"
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_path.touch()
    # tvpower.service removes the request before invoking shutdown. Only
    # resume playback when no installed path unit consumed it.
    time.sleep(2)
    if request_path.exists():
        request_path.unlink()
        print(
            "Safe shutdown handler unavailable; playback resumed",
            flush=True,
        )
        state_store.set_menu_open(False)
    else:
        print("Safe shutdown request accepted by tvpower.service", flush=True)


if __name__ == "__main__":
    sys.exit(run())


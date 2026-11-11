"""OMXPlayer-backed channel menu for the Raspberry Pi Zero."""

import os
from pathlib import Path
import signal
import subprocess


LEFT_CARD = (28, 112, 278, 260)
RIGHT_CARD = (334, 112, 278, 260)
SHUTDOWN_CARD = (150, 390, 340, 72)


def channel_at(position):
    """Return the channel ID at a display coordinate, or ``None``."""
    x, y = position
    if _contains(LEFT_CARD, x, y):
        return "springfield-tv"
    if _contains(RIGHT_CARD, x, y):
        return "treehouse-after-dark"
    return None


def shutdown_at(position):
    """Return True when *position* is inside the guarded shutdown card."""
    return _contains(SHUTDOWN_CARD, position[0], position[1])


def _contains(rectangle, x, y):
    left, top, width, height = rectangle
    return left <= x < left + width and top <= y < top + height


class OmxChannelMenu:
    """Display a pre-rendered menu clip using the proven video path."""

    def __init__(self, asset_directory):
        self.asset_directory = Path(asset_directory)
        self.process = None

    def show(self, active_channel_id):
        stem = "channel_menu_" + active_channel_id.replace("-", "_") + ".mp4"
        asset = self.asset_directory / stem
        if not asset.is_file():
            raise RuntimeError("Channel menu asset is missing: %s" % asset)
        self.show_asset(stem)

    def show_asset(self, filename):
        asset = self.asset_directory / filename
        if not asset.is_file():
            raise RuntimeError("Menu asset is missing: %s" % asset)
        self.process = subprocess.Popen(
            ["omxplayer", "--no-osd", "--aspect-mode", "fill", str(asset)],
            start_new_session=True,
        )

    def close(self):
        if self.process is None or self.process.poll() is not None:
            return
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait()


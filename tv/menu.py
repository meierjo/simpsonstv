"""OMXPlayer-backed channel menu for the Raspberry Pi Zero."""

import os
from pathlib import Path
import signal
import subprocess


LEFT_CARD = (28, 112, 278, 223)
RIGHT_CARD = (334, 112, 278, 223)
SPECIAL_LEFT_CARD = (18, 112, 190, 223)
SPECIAL_CENTER_CARD = (225, 112, 190, 223)
SPECIAL_RIGHT_CARD = (432, 112, 190, 223)
SHUTDOWN_CARD = (70, 345, 500, 100)
MENU_PAGE_COUNT = 2


def channel_at(position, page=0):
    """Return the channel ID at a display coordinate, or ``None``."""
    x, y = position
    if page == 0:
        if _contains(LEFT_CARD, x, y):
            return "springfield-tv"
        if _contains(RIGHT_CARD, x, y):
            return "treehouse-after-dark"
    elif page == 1:
        if _contains(SPECIAL_LEFT_CARD, x, y):
            return "holiday-special"
        if _contains(SPECIAL_CENTER_CARD, x, y):
            return "sideshow-bob"
        if _contains(SPECIAL_RIGHT_CARD, x, y):
            return "krusty-classics"
    return None


def page_for_channel(channel_id):
    if channel_id in ("holiday-special", "sideshow-bob", "krusty-classics"):
        return 1
    return 0


def page_after_swipe(page, direction):
    if direction == "swipe-left":
        return min(MENU_PAGE_COUNT - 1, page + 1)
    if direction == "swipe-right":
        return max(0, page - 1)
    return page


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
        self._processes = []
        self._next_layer = 10
        self._buffered_pages = {}
        self._current_page = None

    def show(self, active_channel_id, page=None):
        if page is None:
            page = page_for_channel(active_channel_id)
        self.show_asset(self._menu_filename(active_channel_id, page))

    @staticmethod
    def _menu_filename(active_channel_id, page):
        return "channel_menu_page%d_%s.mp4" % (
            page,
            active_channel_id.replace("-", "_"),
        )

    def show_buffered(self, active_channel_id, page):
        """Show *page* and preload its neighbor underneath for instant swipes."""
        self._current_page = page
        current = self._start_asset(
            self._menu_filename(active_channel_id, page), layer=10
        )
        other_page = 1 - page
        other = self._start_asset(
            self._menu_filename(active_channel_id, other_page), layer=9
        )
        self._buffered_pages = {page: current, other_page: other}
        self.process = current
        self._next_layer = 8

    def switch_buffered_page(self, active_channel_id, page):
        """Reveal a preloaded page and rebuild the old page below it."""
        if self._current_page == page:
            return
        target = self._buffered_pages.get(page)
        if target is None or target.poll() is not None:
            self.show(active_channel_id, page=page)
            self._current_page = page
            return

        previous_page = self._current_page
        previous = self._buffered_pages.pop(previous_page, None)
        self._close_process(previous)
        if previous in self._processes:
            self._processes.remove(previous)

        self._current_page = page
        self.process = target
        replacement = self._start_asset(
            self._menu_filename(active_channel_id, previous_page),
            layer=self._next_layer,
        )
        self._next_layer -= 1
        self._buffered_pages[previous_page] = replacement

    def show_asset(self, filename):
        self.process = self._start_asset(filename, layer=self._next_layer)
        self._next_layer += 1

    def _start_asset(self, filename, layer):
        asset = self.asset_directory / filename
        if not asset.is_file():
            raise RuntimeError("Menu asset is missing: %s" % asset)
        process = subprocess.Popen(
            [
                "omxplayer",
                "--no-osd",
                "--layer",
                str(layer),
                "--aspect-mode",
                "fill",
                str(asset),
            ],
            start_new_session=True,
        )
        self._processes.append(process)
        return process

    def close(self):
        processes = list(self._processes)
        if self.process is not None and self.process not in processes:
            processes.append(self.process)
        for process in reversed(processes):
            self._close_process(process)
        self._processes = []
        self.process = None
        self._buffered_pages = {}
        self._current_page = None

    @staticmethod
    def _close_process(process):
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


class OmxInfoOverlay(OmxChannelMenu):
    """Show a short, silent program card above uninterrupted playback."""

    def __init__(self, asset_directory, runtime_directory):
        super().__init__(asset_directory)
        self.runtime_directory = Path(runtime_directory)

    def show_details(self, details):
        asset = self.asset_directory / "now_playing_background.mp4"
        if not asset.is_file():
            raise RuntimeError("Now-playing background is missing: %s" % asset)
        if self.process is not None and self.process.poll() is None:
            return False
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        subtitle = self.runtime_directory / "now_playing.srt"
        subtitle.write_text(self._subtitle_text(details))
        self.process = subprocess.Popen(
            [
                "omxplayer",
                "--no-osd",
                "--no-keys",
                "--layer",
                "10",
                "--win",
                "0,300,640,480",
                "--aspect-mode",
                "stretch",
                "--vol",
                "-6000",
                "--subtitles",
                str(subtitle),
                "--font-size",
                "140",
                "--align",
                "center",
                "--no-ghost-box",
                "--lines",
                "4",
                str(asset),
            ],
            start_new_session=True,
        )
        return True

    @staticmethod
    def _subtitle_text(details):
        title = str(details.get("title") or details.get("episode_id") or "UNKNOWN")
        title = title.replace("\r", " ").replace("\n", " ")
        season = details.get("season", "?")
        episode = details.get("episode", "?")
        year = details.get("air_year") or "YEAR UNKNOWN"
        channel = str(details.get("channel_name") or "SPRINGFIELD TV")
        return (
            "1\n00:00:00,100 --> 00:00:03,900\n"
            "%s\nSEASON %s  |  EPISODE %s  |  %s\n%s\n\n"
            % (title, season, episode, year, channel)
        )


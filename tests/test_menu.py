import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tv.menu import OmxChannelMenu


class MenuTests(unittest.TestCase):
    @mock.patch("tv.menu.subprocess.Popen")
    def test_menu_uses_omxplayer_with_the_active_channel_asset(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            asset_directory = Path(temporary_directory)
            asset = asset_directory / "channel_menu_springfield_tv.mp4"
            asset.touch()

            OmxChannelMenu(asset_directory).show("springfield-tv")

            popen.assert_called_once_with(
                ["omxplayer", "--no-osd", "--aspect-mode", "fill", str(asset)],
                start_new_session=True,
            )

    @mock.patch("tv.menu.os.killpg")
    def test_menu_stops_its_complete_player_group(self, killpg):
        menu = OmxChannelMenu("assets")
        menu.process = mock.Mock(pid=321)
        menu.process.poll.return_value = None

        menu.close()

        killpg.assert_called_once_with(321, signal.SIGTERM)
        menu.process.wait.assert_called_once_with(timeout=2)

    def test_missing_menu_asset_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            menu = OmxChannelMenu(temporary_directory)

            with self.assertRaisesRegex(RuntimeError, "asset is missing"):
                menu.show("springfield-tv")

    @mock.patch("tv.menu.subprocess.Popen")
    def test_goodnight_clip_uses_same_player_path(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            asset_directory = Path(temporary_directory)
            asset = asset_directory / "good_night_springfield.mp4"
            asset.touch()

            OmxChannelMenu(asset_directory).show_asset(asset.name)

            popen.assert_called_once_with(
                ["omxplayer", "--no-osd", "--aspect-mode", "fill", str(asset)],
                start_new_session=True,
            )


if __name__ == "__main__":
    unittest.main()


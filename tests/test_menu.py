import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tv.menu import OmxChannelMenu, OmxInfoOverlay


class MenuTests(unittest.TestCase):
    @mock.patch("tv.menu.subprocess.Popen")
    def test_menu_uses_omxplayer_with_the_active_channel_asset(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            asset_directory = Path(temporary_directory)
            asset = asset_directory / "channel_menu_page0_springfield_tv.mp4"
            asset.touch()

            OmxChannelMenu(asset_directory).show("springfield-tv")

            popen.assert_called_once_with(
                [
                    "omxplayer",
                    "--no-osd",
                    "--loop",
                    "--layer",
                    "10",
                    "--aspect-mode",
                    "fill",
                    str(asset),
                ],
                start_new_session=True,
            )

    @mock.patch("tv.menu.os.killpg")
    def test_menu_stops_its_complete_player_group(self, killpg):
        menu = OmxChannelMenu("assets")
        process = mock.Mock(pid=321)
        process.poll.return_value = None
        menu.process = process

        menu.close()

        killpg.assert_called_once_with(321, signal.SIGTERM)
        process.wait.assert_called_once_with(timeout=2)

    def test_missing_menu_asset_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            menu = OmxChannelMenu(temporary_directory)

            with self.assertRaisesRegex(RuntimeError, "asset is missing"):
                menu.show("springfield-tv")

    @mock.patch("tv.menu.subprocess.Popen")
    def test_special_channel_opens_on_special_page(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            asset_directory = Path(temporary_directory)
            asset = asset_directory / "channel_menu_page1_krusty_classics.mp4"
            asset.touch()

            OmxChannelMenu(asset_directory).show("krusty-classics")

            self.assertEqual(popen.call_args.args[0][-1], str(asset))

    @mock.patch("tv.menu.subprocess.Popen")
    def test_goodnight_clip_uses_same_player_path(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            asset_directory = Path(temporary_directory)
            asset = asset_directory / "good_night_springfield.mp4"
            asset.touch()

            OmxChannelMenu(asset_directory).show_asset(asset.name)

            popen.assert_called_once_with(
                [
                    "omxplayer",
                    "--no-osd",
                    "--layer",
                    "10",
                    "--aspect-mode",
                    "fill",
                    str(asset),
                ],
                start_new_session=True,
            )

    @mock.patch("tv.menu.subprocess.Popen")
    def test_confirmation_overlay_uses_foreground_layer(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            asset_directory = Path(temporary_directory)
            asset = asset_directory / "shutdown_confirmation.mp4"
            asset.touch()

            OmxChannelMenu(asset_directory, start_layer=20).show_asset(asset.name)

            command = popen.call_args.args[0]
            self.assertEqual(command[command.index("--layer") + 1], "20")

    @mock.patch("tv.menu.os.killpg")
    @mock.patch("tv.menu.subprocess.Popen")
    def test_menu_pages_are_preloaded_for_an_instant_handoff(self, popen, killpg):
        with tempfile.TemporaryDirectory() as temporary_directory:
            assets = Path(temporary_directory)
            (assets / "channel_menu_page0_springfield_tv.mp4").touch()
            (assets / "channel_menu_page1_springfield_tv.mp4").touch()
            processes = [mock.Mock(pid=100 + index) for index in range(3)]
            for process in processes:
                process.poll.return_value = None
            popen.side_effect = processes
            menu = OmxChannelMenu(assets)

            menu.show_buffered("springfield-tv", page=0)
            menu.switch_buffered_page("springfield-tv", page=1)

            first_command = popen.call_args_list[0].args[0]
            second_command = popen.call_args_list[1].args[0]
            replacement_command = popen.call_args_list[2].args[0]
            self.assertEqual(first_command[first_command.index("--layer") + 1], "10")
            self.assertEqual(second_command[second_command.index("--layer") + 1], "9")
            self.assertEqual(
                replacement_command[replacement_command.index("--layer") + 1], "8"
            )
            self.assertIs(menu.process, processes[1])
            killpg.assert_called_once_with(100, signal.SIGTERM)

    @mock.patch("tv.menu.subprocess.Popen")
    def test_info_overlay_uses_higher_layer_and_dynamic_subtitles(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            assets = root / "assets"
            assets.mkdir()
            background = assets / "now_playing_background.mp4"
            background.touch()
            overlay = OmxInfoOverlay(assets, root / "runtime")

            shown = overlay.show_details(
                {
                    "title": "Springfield",
                    "season": 5,
                    "episode": 10,
                    "air_year": 1993,
                    "channel_name": "Channel 6",
                }
            )

            command = popen.call_args.args[0]
            self.assertIn("--layer", command)
            self.assertEqual(command[command.index("--layer") + 1], "10")
            self.assertEqual(command[command.index("--win") + 1], "0,300,640,480")
            self.assertEqual(command[command.index("--font-size") + 1], "140")
            self.assertNotIn("--alpha", command)
            self.assertIn("--no-ghost-box", command)
            self.assertIn("--subtitles", command)
            self.assertTrue(shown)
            subtitle = root / "runtime" / "now_playing.srt"
            self.assertIn("Springfield", subtitle.read_text())
            self.assertIn("SEASON 5  |  EPISODE 10  |  1993", subtitle.read_text())

    @mock.patch("tv.menu.subprocess.Popen")
    def test_info_overlay_ignores_repeat_tap_while_visible(self, popen):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            assets = root / "assets"
            assets.mkdir()
            (assets / "now_playing_background.mp4").touch()
            popen.return_value.poll.return_value = None
            overlay = OmxInfoOverlay(assets, root / "runtime")
            details = {"title": "Springfield"}

            self.assertTrue(overlay.show_details(details))
            self.assertFalse(overlay.show_details(details))

            popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()


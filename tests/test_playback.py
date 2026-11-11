import tempfile
import unittest
from pathlib import Path
from unittest import mock
import signal
import subprocess

from tv.catalog import Episode
from tv.channels import Channel
from tv.playback import OmxPlayerBackend, PlaybackController
from tv.scheduler import EpisodeScheduler
from tv.state import PlayerState, StateStore


class FakeBackend:
    def __init__(self):
        self.played = []

    def play(self, episode, should_stop=None):
        self.played.append(episode)
        return 0


class PlaybackTests(unittest.TestCase):
    def make_episode(self, episode_id):
        return Episode(
            episode_id,
            1,
            int(episode_id[-2:]),
            episode_id,
            Path(episode_id + ".mp4"),
        )

    @mock.patch("subprocess.Popen")
    def test_omxplayer_uses_argument_list(self, popen):
        popen.return_value.wait.return_value = 0
        popen.return_value.poll.return_value = 0
        popen.return_value.returncode = 0
        episode = self.make_episode("S01E01")

        result = OmxPlayerBackend().play(episode)

        self.assertEqual(result, 0)
        popen.assert_called_once_with(
            ["omxplayer", "--no-osd", "--aspect-mode", "fill", "S01E01.mp4"],
            start_new_session=True,
        )

    @mock.patch("tv.playback.time.sleep")
    @mock.patch("tv.playback.os.killpg")
    @mock.patch("subprocess.Popen")
    def test_omxplayer_stops_group_when_channel_changes(self, popen, killpg, sleep):
        popen.return_value.poll.return_value = None
        popen.return_value.pid = 123
        episode = self.make_episode("S01E01")

        result = OmxPlayerBackend().play(episode, should_stop=lambda: True)

        self.assertEqual(result, 0)
        killpg.assert_called_once_with(123, signal.SIGTERM)
        popen.return_value.wait.assert_called_once_with(timeout=3)
        sleep.assert_not_called()

    @mock.patch("tv.playback.os.killpg")
    def test_stubborn_omxplayer_group_is_force_killed(self, killpg):
        process = mock.Mock(pid=456)
        process.wait.side_effect = [subprocess.TimeoutExpired("omxplayer", 3), 0]

        OmxPlayerBackend()._stop_process_group(process)

        self.assertEqual(
            killpg.call_args_list,
            [mock.call(456, signal.SIGTERM), mock.call(456, signal.SIGKILL)],
        )

    def test_controller_uses_persisted_channel_and_saves_recent_id(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")
            store.save(PlayerState("treehouse", ()))
            episode = self.make_episode("S01E01")
            scheduler = EpisodeScheduler(
                (episode,), {"S01E01": {"tags": ["spooky"]}}
            )
            backend = FakeBackend()
            controller = PlaybackController(
                channels={
                    "springfield-tv": Channel("springfield-tv", "Normal", ()),
                    "treehouse": Channel("treehouse", "Treehouse", ("spooky",)),
                },
                scheduler=scheduler,
                state_store=store,
                backend=backend,
            )

            selected, result = controller.play_next()

            self.assertEqual(result, 0)
            self.assertEqual(selected, episode)
            self.assertEqual(backend.played, [episode])
            self.assertEqual(store.load().recent_ids, ("S01E01",))

    def test_state_survives_round_trip_and_channel_change(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "nested" / "state.json"
            store = StateStore(path)
            store.save(PlayerState("springfield-tv", ("S01E01", "S01E02")))

            store.set_channel("treehouse-after-dark")
            loaded = store.load()

            self.assertEqual(loaded.channel_id, "treehouse-after-dark")
            self.assertEqual(loaded.recent_ids, ("S01E01", "S01E02"))

    def test_corrupt_state_falls_back_to_normal_tv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "state.json"
            path.write_text("not json")

            loaded = StateStore(path).load()

            self.assertEqual(loaded, PlayerState())


if __name__ == "__main__":
    unittest.main()


import tempfile
import unittest
from pathlib import Path
from unittest import mock
import signal
import subprocess

from tv.catalog import Episode
from tv.channels import Channel
from tv.commercials import CommercialClip
from tv.now_playing import NowPlayingStore
from tv.playback import OmxPlayerBackend, PlaybackController
from tv.scheduler import EpisodeScheduler
from tv.state import PlayerState, StateStore


class FakeBackend:
    def __init__(self):
        self.played = []
        self.options = []

    def play(
        self,
        episode,
        should_stop=None,
        should_pause=None,
        start_at=None,
        stop_after=None,
    ):
        self.played.append(episode)
        self.options.append({"start_at": start_at, "stop_after": stop_after})
        return 0


class FakeCommercialScheduler:
    def __init__(self, clips):
        self.clips = clips
        self.requested_years = []

    def choose_preroll(self, year):
        self.requested_years.append(year)
        return self.clips


class FailingCommercialBackend(FakeBackend):
    def play(
        self,
        item,
        should_stop=None,
        should_pause=None,
        start_at=None,
        stop_after=None,
    ):
        self.played.append(item)
        self.options.append({"start_at": start_at, "stop_after": stop_after})
        return 1 if isinstance(item, CommercialClip) else 0


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

    @mock.patch("subprocess.Popen")
    def test_omxplayer_resume_uses_documented_position(self, popen):
        popen.return_value.poll.return_value = 0
        popen.return_value.returncode = 0
        episode = self.make_episode("S01E01")

        OmxPlayerBackend().play(episode, start_at=75)

        popen.assert_called_once_with(
            [
                "omxplayer",
                "--no-osd",
                "--aspect-mode",
                "fill",
                "--pos",
                "00:01:15",
                "S01E01.mp4",
            ],
            start_new_session=True,
        )

    @mock.patch("tv.playback.time.sleep")
    @mock.patch("tv.playback.time.monotonic", side_effect=[10.0, 71.0])
    @mock.patch("tv.playback.os.killpg")
    @mock.patch("subprocess.Popen")
    def test_omxplayer_stops_at_segment_cue(self, popen, killpg, monotonic, sleep):
        popen.return_value.poll.return_value = None
        popen.return_value.pid = 321

        result = OmxPlayerBackend().play(self.make_episode("S01E01"), stop_after=60)

        self.assertEqual(result, 0)
        killpg.assert_called_once_with(321, signal.SIGTERM)
        sleep.assert_not_called()

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

    @mock.patch("tv.playback.time.sleep")
    @mock.patch("tv.playback.time.monotonic", side_effect=[10.0, 11.0, 13.0])
    @mock.patch("tv.playback.os.killpg")
    @mock.patch("subprocess.Popen")
    def test_touch_menu_pauses_and_resumes_existing_player(
        self, popen, killpg, monotonic, sleep
    ):
        popen.return_value.poll.side_effect = [None, None, 0]
        popen.return_value.returncode = 0
        popen.return_value.pid = 222
        pause_states = iter((True, False))

        result = OmxPlayerBackend().play(
            self.make_episode("S01E01"),
            should_stop=lambda: False,
            should_pause=lambda: next(pause_states),
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            killpg.call_args_list,
            [mock.call(222, signal.SIGSTOP), mock.call(222, signal.SIGCONT)],
        )
        self.assertEqual(sleep.call_count, 2)

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

    def test_controller_plays_period_preroll_before_episode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")
            episode = self.make_episode("S01E01")
            scheduler = EpisodeScheduler((episode,), {})
            commercial = CommercialClip(Path("1989-ad.mp4"), 1989)
            commercial_scheduler = FakeCommercialScheduler((commercial,))
            backend = FakeBackend()
            controller = PlaybackController(
                channels={"springfield-tv": Channel("springfield-tv", "Normal", ())},
                scheduler=scheduler,
                state_store=store,
                backend=backend,
                commercial_scheduler=commercial_scheduler,
                broadcast_years={1: ((1, 1989), (13, 1990))},
                suppress_initial_preroll=False,
            )

            selected, result = controller.play_next()

            self.assertEqual(result, 0)
            self.assertEqual(selected, episode)
            self.assertEqual(commercial_scheduler.requested_years, [1989])
            self.assertEqual(backend.played, [commercial, episode])

    def test_controller_publishes_current_episode_details(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = StateStore(root / "state.json")
            now_playing = NowPlayingStore(root / "now_playing.json")
            episode = self.make_episode("S01E01")
            controller = PlaybackController(
                channels={"springfield-tv": Channel("springfield-tv", "Channel 6", ())},
                scheduler=EpisodeScheduler((episode,), {}),
                state_store=store,
                backend=FakeBackend(),
                broadcast_years={1: ((1, 1989), (13, 1990))},
                now_playing_store=now_playing,
            )

            controller.play_next()

            details = now_playing.load()
            self.assertEqual(details["episode_id"], "S01E01")
            self.assertEqual(details["air_year"], 1989)
            self.assertEqual(details["channel_name"], "Channel 6")

    def test_failed_commercial_does_not_prevent_episode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")
            episode = self.make_episode("S01E01")
            commercial = CommercialClip(Path("broken.mp4"), 1989)
            backend = FailingCommercialBackend()
            controller = PlaybackController(
                channels={"springfield-tv": Channel("springfield-tv", "Normal", ())},
                scheduler=EpisodeScheduler((episode,), {}),
                state_store=store,
                backend=backend,
                commercial_scheduler=FakeCommercialScheduler((commercial,)),
                broadcast_years={1: ((1, 1989), (13, 1990))},
                suppress_initial_preroll=False,
            )

            selected, result = controller.play_next()

            self.assertEqual((selected, result), (episode, 0))
            self.assertEqual(backend.played, [commercial, episode])

    def test_cold_start_never_begins_with_commercial_without_cue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")
            episode = self.make_episode("S01E01")
            commercial = CommercialClip(Path("1989-ad.mp4"), 1989)
            backend = FakeBackend()
            controller = PlaybackController(
                channels={"springfield-tv": Channel("springfield-tv", "Normal", ())},
                scheduler=EpisodeScheduler((episode,), {}),
                state_store=store,
                backend=backend,
                commercial_scheduler=FakeCommercialScheduler((commercial,)),
                broadcast_years={1: ((1, 1989), (13, 1990))},
            )

            controller.play_next()
            controller.play_next()

            self.assertEqual(backend.played, [episode, commercial, episode])

    def test_verified_cue_plays_opening_then_ad_then_resumes_episode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")
            episode = self.make_episode("S01E01")
            commercial = CommercialClip(Path("1989-ad.mp4"), 1989)
            backend = FakeBackend()
            controller = PlaybackController(
                channels={"springfield-tv": Channel("springfield-tv", "Normal", ())},
                scheduler=EpisodeScheduler((episode,), {}),
                state_store=store,
                backend=backend,
                commercial_scheduler=FakeCommercialScheduler((commercial,)),
                broadcast_years={1: ((1, 1989), (13, 1990))},
                break_cues={"episode_cues": {"S01E01": 75.0}},
            )

            selected, result = controller.play_next()

            self.assertEqual((selected, result), (episode, 0))
            self.assertEqual(backend.played, [episode, commercial, episode])
            self.assertEqual(
                backend.options,
                [
                    {"start_at": None, "stop_after": 75.0},
                    {"start_at": None, "stop_after": None},
                    {"start_at": 75.0, "stop_after": None},
                ],
            )

    def test_state_survives_round_trip_and_channel_change(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "nested" / "state.json"
            store = StateStore(path)
            store.save(PlayerState("springfield-tv", ("S01E01", "S01E02")))

            store.set_channel("treehouse-after-dark")
            loaded = store.load()

            self.assertEqual(loaded.channel_id, "treehouse-after-dark")
            self.assertEqual(loaded.recent_ids, ("S01E01", "S01E02"))
            self.assertFalse(loaded.menu_open)

    def test_menu_state_is_persisted_without_losing_channel(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = StateStore(Path(temporary_directory) / "state.json")
            store.set_channel("treehouse-after-dark")

            opened = store.set_menu_open(True)
            closed = store.set_menu_open(False)

            self.assertTrue(opened.menu_open)
            self.assertEqual(opened.channel_id, "treehouse-after-dark")
            self.assertFalse(closed.menu_open)
            self.assertEqual(closed.channel_id, "treehouse-after-dark")

    def test_corrupt_state_falls_back_to_normal_tv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "state.json"
            path.write_text("not json")

            loaded = StateStore(path).load()

            self.assertEqual(loaded, PlayerState())


if __name__ == "__main__":
    unittest.main()

